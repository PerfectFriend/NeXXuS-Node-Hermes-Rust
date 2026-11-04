#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use crate::guardian::{
    guardian_check_health, guardian_restart_node, guardian_start_node, guardian_status,
    guardian_stop_node, guardian_toggle_monitor, tg_send_test,
};
use crate::telegram::get_bot;
use serde_json::json;
use std::sync::Arc;
use tauri::{command, generate_context, Builder, Manager, State};

mod api_client;
mod guardian;
mod telegram;

/// Общее состояние приложения.
pub struct AppState {
    pub guardian: Arc<guardian::GuardianState>,
}

#[command]
async fn guardian_start_node_cmd(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    guardian_start_node(state.inner().guardian.clone()).await
}

#[command]
async fn guardian_check_health_cmd(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    guardian_check_health(state.inner().guardian.clone()).await
}

#[command]
async fn guardian_restart_node_cmd(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    guardian_restart_node(state.inner().guardian.clone()).await
}

#[command]
async fn guardian_stop_node_cmd(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    guardian_stop_node(state.inner().guardian.clone()).await
}

#[command]
async fn guardian_status_cmd(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    guardian_status(state.inner().guardian.clone()).await
}

#[command]
async fn guardian_toggle_monitor_cmd(state: State<'_, AppState>) -> Result<serde_json::Value, String> {
    guardian_toggle_monitor(state.inner().guardian.clone()).await
}

#[command]
async fn tg_send_test_cmd() -> Result<serde_json::Value, String> {
    tg_send_test().await
}

fn main() {
    let guardian_state = Arc::new(guardian::GuardianState::new());
    let app_state = AppState { guardian: guardian_state.clone() };

    Builder::default()
        .manage(app_state)
        .setup(|app| {
            // Окно не показывается при старте — только иконка в трее
            let window = app.get_webview_window("main").unwrap();
            window.hide().unwrap();

            // Автоматический запуск nexxusd при старте гардиана
            let state = app.state::<AppState>();
            let guardian = state.guardian.clone();
            std::thread::spawn(move || {
                let rt = tokio::runtime::Runtime::new().unwrap();
                rt.block_on(async move {
                    if !guardian::is_nexxusd_running() {
                        let _ = guardian::start_nexxusd();
                        if guardian::wait_for_api_ready(30).await {
                            let _ = guardian::guardian_start_node(guardian).await;
                        }
                    }
                });
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            guardian_start_node_cmd,
            guardian_check_health_cmd,
            guardian_restart_node_cmd,
            guardian_stop_node_cmd,
            guardian_status_cmd,
            guardian_toggle_monitor_cmd,
            tg_send_test_cmd,
        ])
        .run(tauri::generate_context!());
}
