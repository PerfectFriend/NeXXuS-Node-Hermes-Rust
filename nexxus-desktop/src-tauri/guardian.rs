//! Ядро "ангела-хранителя" ноды NeXXus.
//! Управляет жизненным циклом nexxusd:
//!   - проверка запущенности (pgrep)
//!   - автозапуск nexxusd при отсутствии
//!   - ожидание готовности JSON-RPC API (порт 4010)
//!   - периодический health-check через node_status (каждые 10 сек)
//!   - автоперезапуск при потере связи (3 неудачи подряд)
//!   - отправка событий в Telegram через TelegramBot

use crate::telegram::get_bot;
use serde_json::{json, Value};
use std::process::{Command, Stdio};
use std::sync::Arc;
use std::time::{Duration, SystemTime};
use tokio::sync::Mutex;
use tokio::time::sleep;

const NEXXUSD_BIN: &str = "/home/thomas/build/cache/cargo-target/release/nexxusd";
const NEXXUSD_STORE: &str = "/home/thomas/.nexxus/store.redb";
const API_HOST: &str = "127.0.0.1";
const API_PORT: u16 = 4010;
pub const API_URL: &str = "ws://127.0.0.1:4010";
const HEALTH_INTERVAL_SEC: u64 = 10;
const MAX_HEALTH_FAILURES: u32 = 3;

/// Состояние монитора ноды.
#[derive(Clone, Debug, serde::Serialize, Default, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum MonitorState {
    #[default]
    Stopped,
    Starting,
    Running,
    Unhealthy,
    Restarting,
}

/// Состояние узла (из API).
#[derive(Clone, Debug, serde::Serialize)]
#[serde(rename_all = "snake_case")]
pub struct NodeStatus {
    pub node_id: String,
    pub uptime_ms: u128,
    pub peers: usize,
    pub chunks: usize,
    pub smp: String,
    pub epoch: u64,
    pub tor: String,
    pub api_reachable: bool,
}

/// Текущее состояние гардиана.
pub struct GuardianState {
    pub state: Mutex<MonitorState>,
    pub node_status: Mutex<Option<NodeStatus>>,
    pub start_time: Mutex<Option<SystemTime>>,
    pub health_failures: Mutex<u32>,
    pub nexxusd_pid: Mutex<Option<u32>>,
    pub monitor_enabled: Mutex<bool>,
}

impl GuardianState {
    pub fn new() -> Self {
        Self {
            state: Mutex::new(MonitorState::Stopped),
            node_status: Mutex::new(None),
            start_time: Mutex::new(None),
            health_failures: Mutex::new(0),
            nexxusd_pid: Mutex::new(None),
            monitor_enabled: Mutex::new(true),
        }
    }
}

/// Является ли процесс nexxusd запущенным.
pub fn is_nexxusd_running() -> bool {
    let output = Command::new("pgrep")
        .args(&["-f", "nexxusd.*store.redb"])
        .stdout(Stdio::piped())
        .output();
    match output {
        Ok(out) => !out.stdout.is_empty(),
        Err(_) => false,
    }
}

/// Запускает nexxusd в фоне.
pub fn start_nexxusd() -> Result<(), String> {
    if is_nexxusd_running() {
        return Ok(());
    }

    // Удаляем залоченный файл БД если есть
    let _ = std::fs::remove_file(format!("{}.lock", NEXXUSD_STORE));

    let _child = Command::new(NEXXUSD_BIN)
        .arg(NEXXUSD_STORE)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| format!("Не удалось запустить nexxusd: {e}"))?;

    Ok(())
}

/// Ожидает готовности API (пробует подключиться к WebSocket).
pub async fn wait_for_api_ready(timeout_sec: u64) -> bool {
    let interval = Duration::from_millis(500);
    let total = Duration::from_secs(timeout_sec);
    let mut elapsed = Duration::from_secs(0);

    while elapsed < total {
        if api_is_reachable().await {
            return true;
        }
        sleep(interval).await;
        elapsed += interval;
    }
    false
}

/// Проверяет доступность API через простой HTTP/WebSocket запрос.
pub async fn api_is_reachable() -> bool {
    // Пробуем TCP подключение к порту 4010
    match tokio::net::TcpStream::connect(format!("{API_HOST}:{API_PORT}")).await {
        Ok(_) => true,
        Err(_) => false,
    }
}

/// Выполняет JSON-RPC запрос к локальному API (через WebSocket).
pub async fn api_call(method: &str, params: Option<Value>) -> Result<Value, String> {
    use futures_util::{SinkExt, StreamExt};
    use tokio_tungstenite::connect_async;
    use url::Url;

    let url = Url::parse(API_URL).map_err(|e| format!("Неверный URL API: {e}"))?;
    let (ws_stream, _) = connect_async(url).await.map_err(|e| format!("WebSocket connect failed: {e}"))?;
    let (mut sender, mut receiver) = ws_stream.split();

    let request = json!({
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    });

    sender.send(request.to_string().into()).await.map_err(|e| format!("WebSocket send failed: {e}"))?;

    let timeout = Duration::from_secs(5);
    match tokio::time::timeout(timeout, receiver.next()).await {
        Ok(Some(Ok(msg))) => {
            let _ = sender.close().await;
            let text = msg.to_text().map_err(|e| format!("WebSocket text error: {e}"))?;
            let resp: Value = serde_json::from_str(text).map_err(|e| format!("JSON parse error: {e}"))?;
            Ok(resp)
        }
        Ok(Some(Err(e))) => Err(format!("WebSocket receive error: {e}")),
        Ok(None) => Err("WebSocket connection closed".into()),
        Err(_) => Err("WebSocket timeout".into()),
    }
}

/// Получает статус ноды через API.
pub async fn get_node_status() -> Result<NodeStatus, String> {
    let resp = api_call("node_status", None).await?;
    let result = resp.get("result").ok_or("Отсутствует поле result")?;

    Ok(NodeStatus {
        node_id: result.get("node_id").and_then(|v| v.as_str()).unwrap_or("unknown").to_string(),
        uptime_ms: result.get("uptime_ms").and_then(|v| v.as_u64()).unwrap_or(0) as u128,
        peers: result.get("peers").and_then(|v| v.as_u64()).unwrap_or(0) as usize,
        chunks: result.get("chunks").and_then(|v| v.as_u64()).unwrap_or(0) as usize,
        smp: result.get("smp").and_then(|v| v.as_str()).unwrap_or("unknown").to_string(),
        epoch: result.get("epoch").and_then(|v| v.as_u64()).unwrap_or(0),
        tor: result.get("tor").and_then(|v| v.as_str()).unwrap_or("unknown").to_string(),
        api_reachable: true,
    })
}

/// Получает информацию о пирах.
pub async fn get_node_peers() -> Result<Value, String> {
    api_call("node_peers", None).await
}

/// Получает информацию о чанках.
pub async fn get_node_chunks() -> Result<Value, String> {
    api_call("node_chunks", None).await
}

/// Получает информацию об эпохе.
pub async fn get_node_epoch() -> Result<Value, String> {
    api_call("node_epoch", None).await
}

/// Получает информацию о Tor.
pub async fn get_node_tor() -> Result<Value, String> {
    api_call("node_tor", None).await
}

/// Фоновый цикл мониторинга здоровья.
pub async fn health_loop(state: Arc<GuardianState>) {
    let bot = get_bot().await;
    let _ = bot.notify_monitor_started().await;

    loop {
        sleep(Duration::from_secs(HEALTH_INTERVAL_SEC)).await;

        let enabled = *state.monitor_enabled.lock().await;
        if !enabled {
            continue;
        }

        let mut state_lock = state.state.lock().await;

        match get_node_status().await {
            Ok(status) => {
                *state.health_failures.lock().await = 0;
                *state.node_status.lock().await = Some(status.clone());
                if *state_lock == MonitorState::Unhealthy || *state_lock == MonitorState::Restarting {
                    let _ = bot.notify_node_restarted().await;
                }
                *state_lock = MonitorState::Running;
            }
            Err(e) => {
                let mut failures = state.health_failures.lock().await;
                *failures += 1;
                let current_failures = *failures;
                drop(failures);

                let _ = bot.notify_node_unhealthy(&e).await;

                if current_failures >= MAX_HEALTH_FAILURES {
                    *state_lock = MonitorState::Restarting;
                    let _ = bot.notify_node_restarting("Потеря связи с API (3 неудачи)").await;

                    if let Err(err) = start_nexxusd() {
                        let _ = bot.notify_node_start_failed(&err).await;
                        *state_lock = MonitorState::Unhealthy;
                    } else if wait_for_api_ready(30).await {
                        match get_node_status().await {
                            Ok(status) => {
                                *state.node_status.lock().await = Some(status);
                                *state_lock = MonitorState::Running;
                                let _ = bot.notify_node_restarted().await;
                            }
                            Err(e) => {
                                let _ = bot.notify_node_start_failed(&e).await;
                                *state_lock = MonitorState::Unhealthy;
                            }
                        }
                    } else {
                        let _ = bot.notify_node_start_failed("API не отвечает после запуска").await;
                        *state_lock = MonitorState::Unhealthy;
                    }
                } else {
                    *state_lock = MonitorState::Unhealthy;
                }
            }
        }
    }
}

/// Запускает ноду (команда из UI / трея).
pub async fn guardian_start_node(state: Arc<GuardianState>) -> Result<Value, String> {
    {
        let mut state_lock = state.state.lock().await;
        *state_lock = MonitorState::Starting;
    }

    let bot = get_bot().await;
    let _ = bot.notify_node_starting().await;

    if let Err(e) = start_nexxusd() {
        let mut state_lock = state.state.lock().await;
        *state_lock = MonitorState::Unhealthy;
        let _ = bot.notify_node_start_failed(&e).await;
        return Err(e);
    }

    if !wait_for_api_ready(30).await {
        let mut state_lock = state.state.lock().await;
        *state_lock = MonitorState::Unhealthy;
        let _ = bot.notify_node_start_failed("API не отвечает после запуска").await;
        return Err("API не отвечает после запуска nexxusd".into());
    }

    match get_node_status().await {
        Ok(status) => {
            *state.start_time.lock().await = Some(SystemTime::now());
            *state.node_status.lock().await = Some(status.clone());
            let mut state_lock = state.state.lock().await;
            *state_lock = MonitorState::Running;
            let _ = bot.notify_node_started(&status.node_id, &API_URL).await;
            Ok(json!({"status": "started", "node_id": status.node_id}))
        }
        Err(e) => {
            let mut state_lock = state.state.lock().await;
            *state_lock = MonitorState::Unhealthy;
            let _ = bot.notify_node_start_failed(&e).await;
            Err(e)
        }
    }
}

/// Проверяет здоровье ноды (команда из UI / трея).
pub async fn guardian_check_health(state: Arc<GuardianState>) -> Result<Value, String> {
    match get_node_status().await {
        Ok(status) => {
            *state.node_status.lock().await = Some(status.clone());
            *state.state.lock().await = MonitorState::Running;
            Ok(serde_json::to_value(&status).unwrap())
        }
        Err(e) => {
            *state.state.lock().await = MonitorState::Unhealthy;
            Ok(json!({"error": e, "status": "unhealthy"}))
        }
    }
}

/// Перезапускает ноду.
pub async fn guardian_restart_node(state: Arc<GuardianState>) -> Result<Value, String> {
    let bot = get_bot().await;
    let _ = bot.notify_node_restarting("Ручной перезапуск").await;

    // Убиваем nexxusd
    let _ = Command::new("pkill").args(&["-f", "nexxusd.*store.redb"]).status();
    sleep(Duration::from_secs(2)).await;

    guardian_start_node(state).await
}

/// Останавливает мониторинг (не ноду).
pub async fn guardian_stop_node(state: Arc<GuardianState>) -> Result<Value, String> {
    *state.monitor_enabled.lock().await = false;
    *state.state.lock().await = MonitorState::Stopped;
    let bot = get_bot().await;
    let _ = bot.notify_monitor_stopped().await;
    Ok(json!({"status": "stopped"}))
}

/// Возвращает текущее состояние гардиана.
pub async fn guardian_status(state: Arc<GuardianState>) -> Result<Value, String> {
    let state_val = { state.state.lock().await.clone() };
    let node_status = { state.node_status.lock().await.clone() };
    let enabled = { state.monitor_enabled.lock().await.clone() };

    Ok(json!({
        "state": format!("{:?}", state_val),
        "monitor_enabled": enabled,
        "node_status": node_status,
        "api_reachable": api_is_reachable().await,
    }))
}

/// Переключает мониторинг ВКЛ/ВЫКЛ.
pub async fn guardian_toggle_monitor(state: Arc<GuardianState>) -> Result<Value, String> {
    let mut enabled = state.monitor_enabled.lock().await;
    *enabled = !*enabled;

    if *enabled {
        // Запускаем цикл мониторинга в фоне
        let state_clone = Arc::clone(&state);
        tokio::spawn(async move {
            health_loop(state_clone).await;
        });
    }

    Ok(json!({"monitor_enabled": *enabled}))
}

/// Отправляет тестовое сообщение в Telegram.
pub async fn tg_send_test() -> Result<Value, String> {
    let bot = get_bot().await;
    bot.send_message("🧪 <b>Тест от NeXXus Guardian</b>\n\nПодключение к Telegram работает.").await?;
    Ok(json!({"status": "sent"}))
}
