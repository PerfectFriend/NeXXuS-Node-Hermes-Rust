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
use tokio::net::TcpStream;
use tokio::sync::Mutex;
use tokio::time::sleep;

const NEXXUSD_BIN: &str = "/home/thomas/build/cache/cargo-target-nexxus/release/nexxusd";
const NEXXUSD_STORE: &str = "/home/thomas/.nexxus/store.redb";
/// Файл лога ноды — его же читает команда `nexxusd logs`.
const NEXXUSD_LOG: &str = "/home/thomas/.nexxus/nexxusd.log";
/// Шаблон командной строки процесса ноды.
///
/// По одному только имени `nexxusd` искать нельзя: под этим именем
/// запускается сам бинарь, а совпадение строилось по `store.redb`, который
/// есть не у всех способов запуска. Привязываемся к пути бинаря —
/// у монитора путь оканчивается на `nexxus-desktop`, поэтому совпадения
/// с ним не происходит.
const NEXXUSD_MATCH: &str = "cargo-target-nexxus/release/nexxusd";

/// Адрес локального WS API ноды — из конфига монитора (node.conf, поле `api`),
/// по умолчанию 127.0.0.1:4010. Раньше здесь был зашитый порт 4010, из-за чего
/// при `api=127.0.0.1:5010` в node.conf монитор не находил API и падал
/// «ошибка запуска nexxusd» после wait_for_api_ready.
pub fn api_addr() -> String {
    crate::node_config::load().api
}

/// ws:// URL локального API ноды.
pub fn api_url() -> String {
    format!("ws://{}", api_addr())
}
const HEALTH_INTERVAL_SEC: u64 = 10;
const MAX_HEALTH_FAILURES: u32 = 3;
const HEARTBEAT_INTERVAL_SEC: u64 = 3600;

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
    /// PID запущенной ноды (заполняется при старте).
    #[allow(dead_code)]
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
        .args(["-f", NEXXUSD_MATCH])
        .stdout(Stdio::piped())
        .output();
    match output {
        Ok(out) => !out.stdout.is_empty(),
        Err(_) => false,
    }
}

/// Останавливает nexxusd (SIGTERM, затем добивание SIGKILL).
///
/// Если нода стоит как systemd-юнит, останавливаем её через systemctl —
/// иначе `Restart=on-failure` её воскресит, и кнопка «Остановить» снова
/// будет выглядеть нерабочей.
pub fn stop_nexxusd() -> Result<(), String> {
    if crate::node_unit::is_installed() {
        let _ = Command::new("systemctl")
            .args(["--user", "stop", crate::node_unit::NODE_UNIT_NAME])
            .status();
        std::thread::sleep(Duration::from_millis(800));
    }

    let _ = Command::new("pkill")
        .args(["-f", NEXXUSD_MATCH])
        .status();
    std::thread::sleep(Duration::from_millis(1500));
    // Если пережил SIGTERM — SIGKILL
    if is_nexxusd_running() {
        let _ = Command::new("pkill")
            .args(["-9", "-f", NEXXUSD_MATCH])
            .status();
        std::thread::sleep(Duration::from_millis(500));
    }
    if is_nexxusd_running() {
        return Err("nexxusd не завершился после SIGKILL".into());
    }
    Ok(())
}

/// Полное отключение: стоп ноды + Telegram-отчёт. Вызывается из трея;
/// после возврата вызывающий завершает процесс монитора (выгрузка из памяти).
pub async fn guardian_shutdown_everything(state: Arc<GuardianState>) {
    *state.monitor_enabled.lock().await = false;
    *state.state.lock().await = MonitorState::Stopped;
    let bot = get_bot().await;
    if let Err(e) = stop_nexxusd() {
        let _ = bot.notify_node_start_failed(&format!("При полном отключении: {e}")).await;
    }
    let _ = bot.notify_guardian_shutdown().await;
}

/// Запускает nexxusd в фоне с параметрами из `~/.nexxus/node.conf`.
///
/// Если нода уже установлена как systemd-юнит и запущена — монитор её не
/// трогает: второй процесс занял бы тот же порт и упал бы с `address in use`.
pub fn start_nexxusd() -> Result<(), String> {
    if is_nexxusd_running() {
        return Ok(());
    }

    // Нода под управлением systemd — оставляем её как есть.
    if crate::node_unit::is_installed() && crate::node_unit::unit_state() == "active" {
        return Ok(());
    }

    // Lock-файл БД НЕ удаляем: redb держит его через flock, после падения
    // процесса flock снимается ОС сама, а удаление файла под живым процессом
    // (запущенным по другому пути, не попавшему под pgrep) давало бы второму
    // экземпляру открыть ту же БД — риск двойной записи и порчи store.redb.

    // Конфиг ноды (монитор — единственный источник настроек).
    let cfg = crate::node_config::load();
    let env = crate::node_config::to_env(&cfg);

    // Лог ноды: stderr перенаправляем в файл (иначе `nexxusd logs` не найдёт его).
    let log_path = std::path::PathBuf::from(NEXXUSD_LOG);
    if let Some(parent) = log_path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    let log_out = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(&log_path)
        .map_err(|e| format!("Не удалось открыть лог {}: {e}", log_path.display()))?;
    let log_err = log_out
        .try_clone()
        .map_err(|e| format!("Не удалось клонировать лог: {e}"))?;

    let mut cmd = Command::new(NEXXUSD_BIN);
    cmd.arg(NEXXUSD_STORE)
        .env("NEXXUS_LOG", &log_path)
        .stdout(Stdio::from(log_out))
        .stderr(Stdio::from(log_err));
    for (key, value) in env {
        cmd.env(key, value);
    }

    let _child = cmd
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

/// Проверяет доступность API через WebSocket-handshake.
///
/// Раньше здесь был голый TCP-connect: нода принимала соединение и тут же
/// писала в лог «WebSocket accept failed: Handshake not finished», засоряя
/// лог при каждом health-check. Теперь отправляем настоящий WS-handshake
/// и ждём ответ 101 Switching Protocols.
pub async fn api_is_reachable() -> bool {
    use tokio::io::{AsyncReadExt, AsyncWriteExt};

    let addr = api_addr();
    let Ok(mut stream) = TcpStream::connect(&addr).await else {
        return false;
    };

    let request = format!(
        "GET / HTTP/1.1\r\nHost: {addr}\r\n\
         Upgrade: websocket\r\nConnection: Upgrade\r\n\
         Sec-WebSocket-Version: 13\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n"
    );
    if stream.write_all(request.as_bytes()).await.is_err() {
        return false;
    }

    let mut buf = [0u8; 64];
    let Ok(n) = tokio::time::timeout(Duration::from_secs(3), stream.read(&mut buf)).await else {
        return false;
    };
    let Ok(n) = n else {
        return false;
    };
    let response = String::from_utf8_lossy(&buf[..n]);
    response.starts_with("HTTP/1.1 101")
}

/// Выполняет JSON-RPC запрос к локальному API (через WebSocket).
/// Делегирует в `crate::api_client::api_call`, которая сначала делает
/// `auth` с токеном из `~/.nexxus/api.token`.
pub async fn api_call(method: &str, params: Option<Value>) -> Result<Value, String> {
    crate::api_client::api_call(method, params).await
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

/// Получает информацию о пирах (для дашборда/расширений).
#[allow(dead_code)]
pub async fn get_node_peers() -> Result<Value, String> {
    api_call("node_peers", None).await
}

/// Получает информацию о чанках.
#[allow(dead_code)]
pub async fn get_node_chunks() -> Result<Value, String> {
    api_call("node_chunks", None).await
}

/// Получает информацию об эпохе.
#[allow(dead_code)]
pub async fn get_node_epoch() -> Result<Value, String> {
    api_call("node_epoch", None).await
}

/// Получает информацию о Tor.
#[allow(dead_code)]
pub async fn get_node_tor() -> Result<Value, String> {
    api_call("node_tor", None).await
}

/// Путь к файлу-запросу на полное отключение.
///
/// Второй экземпляр монитора не может сам остановить первый (lock-файл
/// занят), поэтому оставляет запрос — работающий экземпляр подхватит его
/// на ближайшем тике health loop.
pub fn shutdown_request_path() -> std::path::PathBuf {
    crate::node_config::config_dir().join("monitor.shutdown")
}

/// Создан ли файл-запрос на отключение.
pub fn shutdown_requested() -> bool {
    shutdown_request_path().exists()
}

/// Фоновый цикл мониторинга здоровья.
/// Алерты — только на переходах состояния (без спама каждые 10 сек),
/// heartbeat — раз в час, отчёт об активации Tor — при смене состояния.
pub async fn health_loop(state: Arc<GuardianState>) {
    let bot = get_bot().await;
    let _ = bot.notify_monitor_started().await;

    let mut heartbeat_ticks: u64 = 0;
    let mut last_tor: String = String::new();

    loop {
        sleep(Duration::from_secs(HEALTH_INTERVAL_SEC)).await;

        // Запрос на полное отключение извне (второй экземпляр с --shutdown,
        // .desktop-действие Quit). Обрабатываем всегда, даже когда мониторинг
        // выключен кнопкой «Остановить ноду».
        if shutdown_requested() {
            let _ = std::fs::remove_file(shutdown_request_path());
            guardian_shutdown_everything(state.clone()).await;
            std::process::exit(0);
        }

        if !*state.monitor_enabled.lock().await {
            continue;
        }

        let mut state_lock = state.state.lock().await;
        let prev_state = state_lock.clone();

        match get_node_status().await {
            Ok(status) => {
                *state.health_failures.lock().await = 0;
                *state.node_status.lock().await = Some(status.clone());

                // Восстановление после нездоровья/перезапуска
                if prev_state == MonitorState::Unhealthy || prev_state == MonitorState::Restarting {
                    let _ = bot.notify_node_restarted().await;
                }

                // Активация Tor: отчёт при первом появлении onion-адреса
                if status.tor != last_tor {
                    if !status.tor.is_empty() && status.tor != "unknown" && status.tor != "disabled"
                        && !last_tor.is_empty()
                    {
                        let _ = bot.notify_node_tor(&status.tor).await;
                    }
                    last_tor = status.tor.clone();
                }

                *state_lock = MonitorState::Running;

                // Heartbeat раз в час
                heartbeat_ticks += 1;
                if heartbeat_ticks * HEALTH_INTERVAL_SEC >= HEARTBEAT_INTERVAL_SEC {
                    heartbeat_ticks = 0;
                    let _ = bot.notify_heartbeat(&status.node_id, status.peers, status.uptime_ms).await;
                }
            }
            Err(e) => {
                let mut failures = state.health_failures.lock().await;
                *failures += 1;
                let current_failures = *failures;
                drop(failures);

                // Алерт только на ПЕРВОЙ неудаче эпизода (transition-only)
                if prev_state != MonitorState::Unhealthy && prev_state != MonitorState::Restarting {
                    let _ = bot.notify_node_unhealthy(&e).await;
                }

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

    // Мониторинг включаем здесь: после «Остановить ноду» он был выключен,
    // и без этого нода поднималась «мёртвой» — без health-check и отчётов.
    *state.monitor_enabled.lock().await = true;

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
            let _ = bot.notify_node_started(&status.node_id, &api_url()).await;
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
    let _ = Command::new("pkill").args(["-f", "nexxusd.*store.redb"]).status();
    sleep(Duration::from_secs(2)).await;

    guardian_start_node(state).await
}

/// Останавливает ноду (реальный pkill) и мониторинг.
pub async fn guardian_stop_node(state: Arc<GuardianState>) -> Result<Value, String> {
    *state.monitor_enabled.lock().await = false;
    *state.state.lock().await = MonitorState::Stopped;
    let bot = get_bot().await;
    let _ = bot.notify_node_stopping().await;
    let result = stop_nexxusd();
    match &result {
        Ok(_) => {
            let _ = bot.notify_node_stopped().await;
        }
        Err(e) => {
            let _ = bot.notify_node_start_failed(&format!("Остановка ноды: {e}")).await;
        }
    }
    result?;
    Ok(json!({"status": "node_stopped"}))
}

/// Возвращает текущее состояние гардиана.
pub async fn guardian_status(state: Arc<GuardianState>) -> Result<Value, String> {
    let state_val = { state.state.lock().await.clone() };
    let node_status = { state.node_status.lock().await.clone() };
    let enabled = { *state.monitor_enabled.lock().await };

    Ok(json!({
        "state": format!("{:?}", state_val),
        "monitor_enabled": enabled,
        "node_status": node_status,
        "api_reachable": api_is_reachable().await,
    }))
}

/// Переключает мониторинг ВКЛ/ВЫКЛ (сам цикл живёт постоянно —
/// это только флаг участия в мониторинге).
pub async fn guardian_toggle_monitor(state: Arc<GuardianState>) -> Result<Value, String> {
    let mut enabled = state.monitor_enabled.lock().await;
    *enabled = !*enabled;
    Ok(json!({"monitor_enabled": *enabled}))
}

/// Отправляет тестовое сообщение в Telegram.
pub async fn tg_send_test() -> Result<Value, String> {
    let bot = get_bot().await;
    bot.send_message("🧪 <b>Тест от NeXXus Guardian</b>\n\nПодключение к Telegram работает.").await?;
    Ok(json!({"status": "sent"}))
}

#[cfg(test)]
mod start_flow_tests {
    use super::*;
    use std::time::Instant;

    /// Прогоняет реальный флоу кнопки «Start»: start_nexxusd → wait_for_api_ready →
    /// node_status, с замерами каждого шага. Ловит зависание на Starting.
    #[tokio::test]
    async fn start_flow_completes_with_timings() {
        let _ = stop_nexxusd();
        let t0 = Instant::now();
        start_nexxusd().expect("start_nexxusd");
        eprintln!("[t+{:.1?}] spawned", t0.elapsed());

        let ready = wait_for_api_ready(30).await;
        eprintln!("[t+{:.1?}] wait_for_api_ready(30) = {ready}", t0.elapsed());
        assert!(ready, "API не поднялся за 30с — это и есть 'зависание на Starting'");

        let status = get_node_status().await;
        eprintln!("[t+{:.1?}] get_node_status = {:?}", t0.elapsed(), status.as_ref().map(|s| &s.node_id));
        assert!(status.is_ok(), "node_status failed: {:?}", status.err());

        let _ = stop_nexxusd();
        eprintln!("[t+{:.1?}] done", t0.elapsed());
    }
}
