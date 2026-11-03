//! Guardian: активный супервайзер жизненного цикла nexxusd.
//!
//! Монитор запускается ПЕРЕД нодой и:
//!   1. Проверяет, запущен ли nexxusd (через pgrep + проверка порта 4010)
//!   2. Если нет — запускает nexxusd с правильным store-путём
//!   3. Ждёт готовности локального API (WebSocket на 127.0.0.1:4010)
//!   4. Мониторит здоровье ноды через периодические JSON-RPC запросы
//!   5. При потере связи — автоперезапуск nexxusd
//!   6. Все события отправляет в Telegram бота «Мастер Инквизитор»
//!
//! Архитектура:
//!   - Guardian хранит состояние: Stopped / Starting / Running / Unhealthy / Restarting
//!   - Фоновая задача (tokio::spawn) каждые N секунд проверяет здоровье
//!   - Все команды доступны через Tauri invoke для фронтенда

use crate::api_client::NexxusApiClient;
use crate::telegram::get_bot;
use serde::{Deserialize, Serialize};
use std::process::{Command, Stdio};
use std::sync::Arc;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use tokio::sync::Mutex;
use tokio::time::sleep;

/// Путь к бинарнику nexxusd.
const DAEMON_PATH: &str = "/home/thomas/build/cache/cargo-target/release/nexxusd";
/// Путь к файлу хранилища redb.
const STORE_PATH: &str = "/home/thomas/.nexxus/store.redb";
/// Адрес локального API nexxusd.
const API_URL: &str = "ws://127.0.0.1:4010";
/// Интервал проверки здоровья (секунды).
const HEALTH_CHECK_INTERVAL_SECS: u64 = 10;
/// Таймаут одного запроса к API (секунды).
const API_REQUEST_TIMEOUT_SECS: u64 = 5;
/// Количество неудачных проверок перед автоперезапуском.
const MAX_FAILED_CHECKS: u32 = 3;

/// Состояние guardian-а.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum GuardianState {
    /// Монитор запущен, но nexxusd ещё не запускался.
    Stopped,
    /// nexxusd запускается, ожидание готовности API.
    Starting,
    /// nexxusd запущен и отвечает на запросы.
    Running,
    /// nexxusd не отвечает на проверки здоровья.
    Unhealthy,
    /// В процессе автоперезапуска.
    Restarting,
}

/// Информация о текущем состоянии ноды (для фронтенда и Telegram).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeHealthInfo {
    pub state: GuardianState,
    pub node_id: Option<String>,
    pub uptime_ms: Option<u128>,
    pub peers: Option<usize>,
    pub bound_addr: Option<String>,
    pub last_check: Option<u64>, // unix timestamp
    pub failed_checks: u32,
    pub nexxusd_pid: Option<u32>,
}

/// Guardian: управляет жизненным циклом nexxusd.
pub struct Guardian {
    /// Текущее состояние.
    state: Arc<Mutex<GuardianState>>,
    /// API клиент для связи с nexxusd.
    api_client: Arc<NexxusApiClient>,
    /// Информация о здоровье ноды.
    health: Arc<Mutex<NodeHealthInfo>>,
    /// Флаг остановки guardian-а (для корректного завершения фоновой задачи).
    running: Arc<Mutex<bool>>,
    /// PID процесса nexxusd (если запущен через guardian).
    nexxusd_pid: Arc<Mutex<Option<u32>>>,
}

impl Guardian {
    pub fn new() -> Self {
        Self {
            state: Arc::new(Mutex::new(GuardianState::Stopped)),
            api_client: Arc::new(NexxusApiClient::new(API_URL)),
            health: Arc::new(Mutex::new(NodeHealthInfo {
                state: GuardianState::Stopped,
                node_id: None,
                uptime_ms: None,
                peers: None,
                bound_addr: None,
                last_check: None,
                failed_checks: 0,
                nexxusd_pid: None,
            })),
            running: Arc::new(Mutex::new(false)),
            nexxusd_pid: Arc::new(Mutex::new(None)),
        }
    }

    /// Получить текущее состояние.
    pub async fn state(&self) -> GuardianState {
        self.state.lock().await.clone()
    }

    /// Получить полную информацию о здоровье ноды.
    pub async fn health_info(&self) -> NodeHealthInfo {
        self.health.lock().await.clone()
    }

    /// Проверяет, запущен ли процесс nexxusd в системе.
    fn is_nexxusd_running() -> bool {
        let output = Command::new("pgrep")
            .args(["-f", "nexxusd.*store.redb"])
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .output();
        match output {
            Ok(o) => o.status.success(),
            Err(_) => false,
        }
    }

    /// Проверяет, отвечает ли локальный API (порт 4010).
    async fn is_api_responding(&self) -> bool {
        // Пробуем подключиться к WebSocket и сделать node_status запрос
        match self.api_client.request("node_status", serde_json::json!({})).await {
            Ok(_) => true,
            Err(_) => false,
        }
    }

    /// Запускает nexxusd процесс (если ещё не запущен).
    pub async fn start_nexxusd(&self) -> Result<(), String> {
        // Проверяем, не запущен ли уже
        if Self::is_nexxusd_running() {
            // nexxusd уже работает где-то — не запускаем второй экземпляр
            let bot = get_bot().await;
            let _ = bot.notify_node_started("unknown", "127.0.0.1:4010").await;
            return Ok(());
        }

        // Запускаем nexxusd в фоне
        let mut child = Command::new(DAEMON_PATH)
            .arg(STORE_PATH)
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .spawn()
            .map_err(|e| format!("Не удалось запустить nexxusd: {e}"))?;

        let pid = child.id();
        *self.nexxusd_pid.lock().await = Some(pid);

        // Отсоединяем процесс, чтобы он продолжал работать после выхода guardian
        // (в Tauri контексте процесс будет дочерним, но мы не ждём его завершения)
        std::mem::forget(child);

        // Отправляем уведомление в Telegram
        let bot = get_bot().await;
        let _ = bot.notify_node_starting().await;

        // Ждём готовности API (до 30 секунд)
        let mut waited = 0;
        while waited < 30 {
            sleep(Duration::from_secs(1)).await;
            waited += 1;
            if self.is_api_responding().await {
                // API отвечает — нода готова
                *self.state.lock().await = GuardianState::Running;
                let _ = self.update_health_from_api().await;
                let bot = get_bot().await;
                let health = self.health.lock().await.clone();
                let node_id = health.node_id.as_deref().unwrap_or("unknown");
                let bound = health.bound_addr.as_deref().unwrap_or("127.0.0.1:4010");
                let _ = bot.notify_node_started(node_id, bound).await;
                return Ok(());
            }
        }

        Err("nexxusd запущен, но API не отвечает в течение 30 секунд".into())
    }

    /// Обновляет информацию о здоровье из API.
    pub async fn update_health_from_api(&self) -> Result<(), String> {
        let status = self.api_client.request("node_status", serde_json::json!({})).await
            .map_err(|e| format!("API ошибка: {e}"))?;

        let node_id = status.get("node_id").and_then(|v| v.as_str()).map(|s| s.to_string());
        let uptime_ms = status.get("uptime_ms").and_then(|v| v.as_u64()).map(|v| v as u128);
        let peers = status.get("peer_count").and_then(|v| v.as_u64()).map(|v| v as usize);
        let bound_addr = status.get("bound_addr").and_then(|v| v.as_str()).map(|s| s.to_string());

        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);

        *self.health.lock().await = NodeHealthInfo {
            state: GuardianState::Running,
            node_id,
            uptime_ms,
            peers,
            bound_addr,
            last_check: Some(now),
            failed_checks: 0,
            nexxusd_pid: *self.nexxusd_pid.lock().await,
        };

        Ok(())
    }

    /// Проверка здоровья ноды (вызывается фоновой задачей).
    pub async fn check_health(&self) -> bool {
        match self.api_client.request("node_status", serde_json::json!({})).await {
            Ok(status) => {
                let node_id = status.get("node_id").and_then(|v| v.as_str()).map(|s| s.to_string());
                let uptime_ms = status.get("uptime_ms").and_then(|v| v.as_u64()).map(|v| v as u128);
                let peers = status.get("peer_count").and_then(|v| v.as_u64()).map(|v| v as usize);
                let bound_addr = status.get("bound_addr").and_then(|v| v.as_str()).map(|s| s.to_string());

                let now = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .map(|d| d.as_secs())
                    .unwrap_or(0);

                // Обновляем здоровье
                *self.health.lock().await = NodeHealthInfo {
                    state: GuardianState::Running,
                    node_id,
                    uptime_ms,
                    peers,
                    bound_addr,
                    last_check: Some(now),
                    failed_checks: 0,
                    nexxusd_pid: *self.nexxusd_pid.lock().await,
                };
                *self.state.lock().await = GuardianState::Running;
                true
            }
            Err(e) => {
                // API не отвечает — увеличиваем счётчик неудач
                let mut health = self.health.lock().await;
                health.failed_checks += 1;
                health.state = if health.failed_checks >= MAX_FAILED_CHECKS {
                    GuardianState::Unhealthy
                } else {
                    GuardianState::Running // пока ещё неcritical, но уже есть проблемы
                };
                *self.state.lock().await = health.state.clone();

                if health.failed_checks >= MAX_FAILED_CHECKS {
                    // Критическое количество неудач — отправляем уведомление
                    drop(health);
                    let bot = get_bot().await;
                    let _ = bot.notify_node_unhealthy(&e.to_string()).await;
                }

                false
            }
        }
    }

    /// Автоперезапуск nexxusd при потере связи.
    pub async fn restart_nexxusd(&self) -> Result<(), String> {
        let bot = get_bot().await;
        let _ = bot.notify_node_restarting("потеря связи с API").await;

        *self.state.lock().await = GuardianState::Restarting;

        // Убиваем старый процесс если есть
        if let Some(pid) = *self.nexxusd_pid.lock().await {
            let _ = Command::new("kill").arg(pid.to_string()).status();
        }
        // Также убиваем все процессы nexxusd по имени
        let _ = Command::new("pkill").args(["-9", "-f", "nexxusd.*store.redb"]).status();

        sleep(Duration::from_secs(2)).await;

        // Запускаем заново
        match self.start_nexxusd().await {
            Ok(()) => {
                let _ = bot.notify_node_restarted().await;
                Ok(())
            }
            Err(e) => {
                let _ = bot.notify_node_start_failed(&e).await;
                Err(e)
            }
        }
    }

    /// Остановить nexxusd (если запущен через guardian).
    pub async fn stop_nexxusd(&self) -> Result<(), String> {
        if let Some(pid) = *self.nexxusd_pid.lock().await {
            let _ = Command::new("kill").arg(pid.to_string()).status();
        } else {
            let _ = Command::new("pkill").args(["-9", "-f", "nexxusd.*store.redb"]).status();
        }
        *self.state.lock().await = GuardianState::Stopped;
        *self.health.lock().await = NodeHealthInfo {
            state: GuardianState::Stopped,
            node_id: None,
            uptime_ms: None,
            peers: None,
            bound_addr: None,
            last_check: None,
            failed_checks: 0,
            nexxusd_pid: None,
        };
        Ok(())
    }

    /// Запуск фоновой задачи мониторинга здоровья.
    /// Вызывается один раз при старте приложения.
    pub async fn start_health_monitor(self: Arc<Self>) {
        let running = Arc::clone(&self.running);
        *running.lock().await = true;

        let running_clone = Arc::clone(&running);
        tokio::spawn(async move {
            loop {
                {
                    let run = running_clone.lock().await;
                    if !*run {
                        break;
                    }
                }

                let guardian = Arc::clone(&self);
                let healthy = guardian.check_health().await;

                if !healthy {
                    let state = guardian.state().await;
                    if state == GuardianState::Unhealthy {
                        // Пытаемся автоперезапустить
                        let _ = guardian.restart_nexxusd().await;
                    }
                }

                sleep(Duration::from_secs(HEALTH_CHECK_INTERVAL_SECS)).await;
            }
        });
    }

    /// Остановить фоновую задачу мониторинга.
    pub async fn stop_health_monitor(&self) {
        *self.running.lock().await = false;
    }
}

/// Статус guardian-а для фронтенда (упрощённый).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GuardianStatus {
    pub state: String,
    pub node_id: Option<String>,
    pub uptime_ms: Option<u128>,
    pub peers: Option<usize>,
    pub bound_addr: Option<String>,
    pub failed_checks: u32,
    pub tg_configured: bool,
}

impl Guardian {
    /// Получить упрощённый статус для фронтенда.
    pub async fn status_for_frontend(&self) -> GuardianStatus {
        let health = self.health.lock().await.clone();
        let bot = get_bot().await;
        GuardianStatus {
            state: format!("{:?}", health.state),
            node_id: health.node_id,
            uptime_ms: health.uptime_ms,
            peers: health.peers,
            bound_addr: health.bound_addr,
            failed_checks: health.failed_checks,
            tg_configured: bot.is_configured(),
        }
    }
}

impl Default for Guardian {
    fn default() -> Self {
        Self::new()
    }
}
