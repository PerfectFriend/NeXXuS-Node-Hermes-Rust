//! Tauri-команды монитора.
//!
//! Все команды, доступные фронтенду, объявлены здесь — `main.rs` отвечает
//! только за инициализацию, трей и регистрацию обработчика.

use crate::guardian::{
    guardian_check_health, guardian_restart_node, guardian_shutdown_everything,
    guardian_start_node, guardian_status, guardian_stop_node, guardian_toggle_monitor,
    health_loop, tg_send_test,
};
use crate::node_config::{self, NodeConfig};
use serde_json::{json, Value};
use std::sync::Arc;
use tauri::{command, State};

/// Общее состояние приложения.
pub struct AppState {
    pub guardian: Arc<crate::guardian::GuardianState>,
}

// --- Управление нодой ---

#[command]
pub async fn guardian_start_node_cmd(state: State<'_, AppState>) -> Result<Value, String> {
    guardian_start_node(state.inner().guardian.clone()).await
}

#[command]
pub async fn guardian_check_health_cmd(state: State<'_, AppState>) -> Result<Value, String> {
    guardian_check_health(state.inner().guardian.clone()).await
}

#[command]
pub async fn guardian_restart_node_cmd(state: State<'_, AppState>) -> Result<Value, String> {
    guardian_restart_node(state.inner().guardian.clone()).await
}

#[command]
pub async fn guardian_stop_node_cmd(state: State<'_, AppState>) -> Result<Value, String> {
    guardian_stop_node(state.inner().guardian.clone()).await
}

#[command]
pub async fn guardian_status_cmd(state: State<'_, AppState>) -> Result<Value, String> {
    guardian_status(state.inner().guardian.clone()).await
}

#[command]
pub async fn guardian_toggle_monitor_cmd(state: State<'_, AppState>) -> Result<Value, String> {
    guardian_toggle_monitor(state.inner().guardian.clone()).await
}

/// Полное отключение: стоп ноды + Telegram-отчёт. Процесс монитора
/// завершает себя сам после отчёта (выгрузка из памяти).
#[command]
pub async fn guardian_shutdown_cmd(state: State<'_, AppState>) -> Result<Value, String> {
    guardian_shutdown_everything(state.inner().guardian.clone()).await;
    // «Паника»: жёсткая выгрузка процесса монитора из памяти.
    std::process::exit(0);
}

#[command]
pub async fn tg_send_test_cmd() -> Result<Value, String> {
    tg_send_test().await
}

// --- Настройки Telegram из UI ---

/// Статус конфига Telegram (флаги + источники, без значений токена).
#[command]
pub fn tg_config_status_cmd() -> Result<Value, String> {
    Ok(crate::telegram::telegram_config_status())
}

/// Сохраняет bot token + chat id в ~/.nexxus/telegram.json (0600), валидирует
/// токен через getMe и перезагружает бота. Значения не логируются.
#[command]
pub async fn tg_config_save_cmd(bot_token: String, chat_id: String) -> Result<Value, String> {
    crate::telegram::check_bot_token(&bot_token).await?;
    crate::telegram::save_telegram_config(&bot_token, &chat_id)?;
    crate::telegram::reload_bot().await;
    let mut st = crate::telegram::telegram_config_status();
    st["bot"] = crate::telegram::check_bot_token(&bot_token).await.unwrap_or(Value::Null);
    st["saved"] = json!(true);
    Ok(st)
}

/// Проверка токена без сохранения (getMe).
#[command]
pub async fn tg_config_check_cmd(bot_token: String) -> Result<Value, String> {
    crate::telegram::check_bot_token(&bot_token).await
}

// --- Универсальный прокси к локальному API ноды (для панелей дашборда) ---

/// Выполняет произвольный метод локального WS API ноды (с auth по токену):
/// node_peers, node_chunks, node_smp, node_epoch, node_tor, node_pause,
/// node_resume, node_connect, node_dial_onion, node_upload, node_download,
/// node_por, panic_status и т.д. — все панели дашборда ходят через неё.
#[command]
pub async fn node_api_cmd(method: String, params: Option<Value>) -> Result<Value, String> {
    crate::guardian::api_call(&method, params).await
}

/// Хвост лог-файла ноды (~/.nexxus/nexxusd.log) для панели «Логи».
#[command]
pub fn node_log_tail_cmd(lines: Option<u32>) -> Result<Value, String> {
    let path = std::path::PathBuf::from(crate::guardian::nexxusd_log_path());
    let n = lines.unwrap_or(200).max(1) as usize;
    let content = std::fs::read_to_string(&path)
        .map_err(|e| format!("Не удалось прочитать {}: {e}", path.display()))?;
    let tail: Vec<&str> = content.lines().rev().take(n).collect::<Vec<_>>().into_iter().rev().collect();
    Ok(json!({ "path": path.to_string_lossy(), "lines": tail, "total_lines": content.lines().count() }))
}

// --- Конфигурация ноды ---

/// Возвращает текущую конфигурацию ноды (из `~/.nexxus/node.conf`).
#[command]
pub fn node_config_get_cmd() -> Result<Value, String> {
    let cfg = node_config::load();
    serde_json::to_value(&cfg).map_err(|e| format!("Не удалось сериализовать конфиг: {e}"))
}

/// Сохраняет конфигурацию ноды. Перезапуск ноды выполняется отдельно
/// (`guardian_restart_node_cmd`), чтобы пользователь видел результат.
#[command]
pub fn node_config_set_cmd(cfg: NodeConfig) -> Result<Value, String> {
    node_config::validate(&cfg)?;
    node_config::save(&cfg)?;
    Ok(json!({
        "status": "saved",
        "config": cfg,
        "env": node_config::to_env(&cfg)
            .into_iter()
            .map(|(k, v)| json!({ "key": k, "value": v }))
            .collect::<Vec<_>>(),
    }))
}

/// Проверяет конфигурацию без сохранения (dry-run для UI).
#[command]
pub fn node_config_validate_cmd(cfg: NodeConfig) -> Result<Value, String> {
    node_config::validate(&cfg)?;
    Ok(json!({ "valid": true }))
}

// --- Установка / удаление ноды как системной службы ---

/// Ставит ноду как user-юнит systemd: генерирует файл из текущего конфига,
/// делает daemon-reload и enable --now.
#[command]
pub fn node_install_cmd() -> Result<Value, String> {
    let cfg = node_config::load();
    let path = crate::node_unit::install_unit(&cfg)?;
    crate::node_unit::enable_and_start()?;
    Ok(json!({
        "status": "installed",
        "unit": path.to_string_lossy(),
        "unit_state": crate::node_unit::unit_state(),
    }))
}

/// Останавливает и выключает юнит ноды (сам монитор остаётся работать).
#[command]
pub fn node_uninstall_cmd() -> Result<Value, String> {
    crate::node_unit::disable_and_stop()?;
    Ok(json!({
        "status": "uninstalled",
        "unit_state": crate::node_unit::unit_state(),
    }))
}

/// Состояние установки ноды (для дашборда).
#[command]
pub fn node_install_status_cmd() -> Result<Value, String> {
    Ok(json!({
        "installed": crate::node_unit::is_installed(),
        "unit_path": crate::node_unit::node_unit_path().to_string_lossy(),
        "unit_state": crate::node_unit::unit_state(),
        "monitor_unit_state": crate::node_unit::monitor_unit_state(),
    }))
}

// --- Онбординг (Phase C1): персистентная машина состояний ---

/// Текущее состояние онбординга (шаг + пройденные).
#[command]
pub fn onboarding_get_cmd() -> Result<Value, String> {
    let s = crate::onboarding::load()?;
    serde_json::to_value(&s).map_err(|e| format!("сериализация: {e}"))
}

/// Закрывает шаг онбординга (идемпотентно, без пропусков). step: snake_case id.
#[command]
pub fn onboarding_advance_cmd(step: String) -> Result<Value, String> {
    let step_id = crate::onboarding::StepId::from_str(&step)
        .ok_or_else(|| format!("неизвестный шаг онбординга: {step}"))?;
    let state = crate::onboarding::load()?;
    let state = crate::onboarding::advance(state, step_id)?;
    crate::onboarding::save(&state)?;
    serde_json::to_value(&state).map_err(|e| format!("сериализация: {e}"))
}

/// Сброс онбординга (повторное прохождение).
#[command]
pub fn onboarding_reset_cmd() -> Result<Value, String> {
    let s = crate::onboarding::reset()?;
    serde_json::to_value(&s).map_err(|e| format!("сериализация: {e}"))
}

/// Запускает фоновый цикл мониторинга (используется в setup main.rs).
pub async fn run_health_loop(state: Arc<crate::guardian::GuardianState>) {
    health_loop(state).await;
}
