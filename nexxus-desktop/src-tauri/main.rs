#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{Manager, SystemTray, SystemTrayEvent, SystemTrayMenu, SystemTrayMenuItem};
use tauri::command;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::Mutex;

mod commands;
mod api_client;

use api_client::NexxusApiClient;

struct AppState {
    api_client: Arc<Mutex<NexxusApiClient>>,
}

#[command]
async fn node_status(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let client = state.api_client.lock().await;
    client.request("node_status", serde_json::json!({})).await
        .map_err(|e| e.to_string())
}

#[command]
async fn node_peers(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let client = state.api_client.lock().await;
    client.request("node_peers", serde_json::json!({})).await
        .map_err(|e| e.to_string())
}

#[command]
async fn node_chunks(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let client = state.api_client.lock().await;
    client.request("node_chunks", serde_json::json!({})).await
        .map_err(|e| e.to_string())
}

#[command]
async fn node_smp(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let client = state.api_client.lock().await;
    client.request("node_smp", serde_json::json!({})).await
        .map_err(|e| e.to_string())
}

#[command]
async fn node_epoch(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let client = state.api_client.lock().await;
    client.request("node_epoch", serde_json::json!({})).await
        .map_err(|e| e.to_string())
}

#[command]
async fn node_tor(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let client = state.api_client.lock().await;
    client.request("node_tor", serde_json::json!({})).await
        .map_err(|e| e.to_string())
}

#[command]
async fn send_smp_envelope(
    state: tauri::State<'_, AppState>,
    recipient_node_id: String,
    payload: Vec<u8>,
    addr: Option<String>,
) -> Result<serde_json::Value, String> {
    let client = state.api_client.lock().await;
    let mut params = serde_json::json!({
        "recipient_node_id": recipient_node_id,
        "payload": payload,
    });
    if let Some(a) = addr {
        params["addr"] = serde_json::Value::String(a);
    }
    client.request("send_smp_envelope", params).await
        .map_err(|e| e.to_string())
}

#[command]
async fn node_pause(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let client = state.api_client.lock().await;
    client.request("node_pause", serde_json::json!({})).await
        .map_err(|e| e.to_string())
}

#[command]
async fn node_resume(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let client = state.api_client.lock().await;
    client.request("node_resume", serde_json::json!({})).await
        .map_err(|e| e.to_string())
}

fn main() {
    let api_client = Arc::new(Mutex::new(NexxusApiClient::new("ws://127.0.0.1:4010")));

    let system_tray = SystemTrayMenu::new()
        .add_item(SystemTrayMenuItem::new("Открыть дашборд", true, None, "show_dashboard"))
        .add_item(SystemTrayMenuItem::new("Статус узла", true, None, "node_status"))
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(SystemTrayMenuItem::new("Пауза узла", true, None, "node_pause"))
        .add_item(SystemTrayMenuItem::new("Перезапуск узла", true, None, "node_restart"))
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(SystemTrayMenuItem::new("Настройки", true, None, "settings"))
        .add_item(SystemTrayMenuItem::new("Выход", true, None, "quit"));

    tauri::Builder::default()
        .manage(AppState { api_client })
        .system_tray(SystemTray::new().with_menu(system_tray))
        .on_system_tray_event(|app, event| match event {
            SystemTrayEvent::MenuItemClick { id, .. } => match id.as_str() {
                "show_dashboard" => {
                    let window = app.get_window("main").unwrap();
                    window.show().unwrap();
                }
                "quit" => {
                    std::process::exit(0);
                }
                _ => {}
            },
            SystemTrayEvent::DoubleClick { .. } => {
                let window = app.get_window("main").unwrap();
                window.show().unwrap();
            }
            _ => {}
        })
        .invoke_handler(tauri::generate_handler![
            node_status,
            node_peers,
            node_chunks,
            node_smp,
            node_epoch,
            node_tor,
            send_smp_envelope,
            node_pause,
            node_resume,
        ])
        .setup(|app| {
            let window = app.get_window("main").unwrap();
            let window_clone = window.clone();

            // Hide window on close, keep running in tray
            window.on_window_event(move |event| {
                if let tauri::WindowEvent::CloseRequested { .. } = event {
                    window_clone.hide().unwrap();
                }
            });

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
