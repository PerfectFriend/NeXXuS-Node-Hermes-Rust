//! Точка входа Tauri для NeXXus Node Monitor — «Ангел-хранитель» ноды.
//!
//! Монитор запускается ПЕРЕД nexxusd и:
//!   1. Запускает nexxusd если он не работает
//!   2. Мониторит здоровье ноды через периодические JSON-RPC запросы
//!   3. При потере связи — автоперезапуск nexxusd
//!   4. Все события отправляет в Telegram бота «Мастер Инквизитор»
//!   5. Проксирует JSON-RPC запросы к локальному API nexxusd (ws://127.0.0.1:4010)
//!
//! Стек: Tauri 2.x (Rust бэкенд + веб-фронтенд), локальный WebSocket API на 127.0.0.1:4010.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri::{Manager, command};
use std::sync::Arc;
use tokio::sync::Mutex;

mod api_client;
mod guardian;
mod telegram;

use api_client::NexxusApiClient;
use guardian::Guardian;
use telegram::TelegramBot;

/// Shared application state managed by Tauri.
/// Хранит клиента API, Guardian и Telegram бота.
struct AppState {
    api_client: Arc<Mutex<NexxusApiClient>>,
    guardian: Arc<Guardian>,
    telegram_bot: Arc<Mutex<Option<TelegramBot>>>,
}

/// Команда: запустить nexxusd через Guardian (ангел-хранитель).
#[command]
async fn guardian_start_node(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let guardian = &state.guardian;
    let bot = crate::telegram::get_bot().await;
    let _ = bot.notify_monitor_started().await;

    match guardian.start_nexxusd().await {
        Ok(()) => {
            let status = guardian.status_for_frontend().await;
            Ok(serde_json::to_value(&status).unwrap())
        }
        Err(e) => {
            let _ = bot.notify_node_start_failed(&e).await;
            Err(e)
        }
    }
}

/// Команда: проверить здоровье ноды вручную.
#[command]
async fn guardian_check_health(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let guardian = &state.guardian;
    let healthy = guardian.check_health().await;
    if healthy {
        let status = guardian.status_for_frontend().await;
        Ok(serde_json::to_value(&status).unwrap())
    } else {
        let status = guardian.status_for_frontend().await;
        // Возвращаем ошибку, но статус всё равно передаём фронтенду
        Err(serde_json::to_string(&status).unwrap_or_else(|_| "node unhealthy".into()))
    }
}

/// Команда: автоперезапуск nexxusd.
#[command]
async fn guardian_restart_node(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let guardian = &state.guardian;
    match guardian.restart_nexxusd().await {
        Ok(()) => {
            let status = guardian.status_for_frontend().await;
            Ok(serde_json::to_value(&status).unwrap())
        }
        Err(e) => Err(e),
    }
}

/// Команда: остановить nexxusd.
#[command]
async fn guardian_stop_node(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let guardian = &state.guardian;
    match guardian.stop_nexxusd().await {
        Ok(()) => {
            let status = guardian.status_for_frontend().await;
            Ok(serde_json::to_value(&status).unwrap())
        }
        Err(e) => Err(e),
    }
}

/// Команда: получить статус guardian-а (для фронтенда).
#[command]
async fn guardian_status(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let guardian = &state.guardian;
    let status = guardian.status_for_frontend().await;
    Ok(serde_json::to_value(&status).unwrap())
}

/// Команда: включить/выключить фоновый мониторинг здоровья.
#[command]
async fn guardian_toggle_monitor(
    state: tauri::State<'_, AppState>,
    enable: bool,
) -> Result<serde_json::Value, String> {
    let guardian = &state.guardian;
    if enable {
        let g = Arc::clone(guardian);
        Guardian::start_health_monitor(g).await;
        Ok(serde_json::json!({ "monitoring": true }))
    } else {
        guardian.stop_health_monitor().await;
        Ok(serde_json::json!({ "monitoring": false }))
    }
}

/// Команда: отправить тестовое сообщение в Telegram.
#[command]
async fn tg_send_test(_state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let bot = crate::telegram::get_bot().await;
    if !bot.is_configured() {
        return Err("Telegram не настроен. Установите NEXXUS_TG_BOT_TOKEN и NEXXUS_TG_CHAT_ID".into());
    }
    match bot.send_message("🧪 <b>Тестовое сообщение от NeXXus Guardian</b>\n\nПодключение к боту «Мастер Инквизитор» работает.").await {
        Ok(()) => Ok(serde_json::json!({ "sent": true })),
        Err(e) => Err(e),
    }
}

/// Существующие команды (проксирование к API nexxusd).
/// Эти команды работают только если nexxusd запущен.

/// Команда: получить статус узла (node_id, uptime, peers, bound_addr).
#[command]
async fn node_status(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let client = state.api_client.lock().await;
    client.request("node_status", serde_json::json!({}))
        .await
        .map_err(|e| e.to_string())
}

/// Команда: получить список подключённых пиров.
#[command]
async fn node_peers(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let client = state.api_client.lock().await;
    client.request("node_peers", serde_json::json!({}))
        .await
        .map_err(|e| e.to_string())
}

/// Команда: получить статистику хранилища чанков.
#[command]
async fn node_chunks(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let client = state.api_client.lock().await;
    client.request("node_chunks", serde_json::json!({}))
        .await
        .map_err(|e| e.to_string())
}

/// Команда: получить историю SMP сообщений.
#[command]
async fn node_smp(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let client = state.api_client.lock().await;
    client.request("node_smp", serde_json::json!({}))
        .await
        .map_err(|e| e.to_string())
}

/// Команда: получить статус финализации эпохи.
#[command]
async fn node_epoch(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let client = state.api_client.lock().await;
    client.request("node_epoch", serde_json::json!({}))
        .await
        .map_err(|e| e.to_string())
}

/// Команда: получить статус Tor.
#[command]
async fn node_tor(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let client = state.api_client.lock().await;
    client.request("node_tor", serde_json::json!({}))
        .await
        .map_err(|e| e.to_string())
}

/// Команда: отправить SMP envelope на указанный адрес.
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
    client.request("send_smp_envelope", params)
        .await
        .map_err(|e| e.to_string())
}

/// Команда: поставить узел на паузу.
#[command]
async fn node_pause(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let client = state.api_client.lock().await;
    client.request("node_pause", serde_json::json!({}))
        .await
        .map_err(|e| e.to_string())
}

/// Команда: возобновить работу узла.
#[command]
async fn node_resume(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let client = state.api_client.lock().await;
    client.request("node_resume", serde_json::json!({}))
        .await
        .map_err(|e| e.to_string())
}

fn main() {
    // Создаём клиент API для связи с nexxusd.
    let api_client = Arc::new(Mutex::new(NexxusApiClient::new("ws://127.0.0.1:4010")));

    // Создаём Guardian — ангела-хранителя ноды.
    let guardian = Arc::new(Guardian::new());

    // Инициализируем Telegram бота (чтение из env переменных).
    let telegram_bot = Arc::new(Mutex::new(Some(TelegramBot::new())));

    tauri::Builder::default()
        .manage(AppState {
            api_client,
            guardian: Arc::clone(&guardian),
            telegram_bot,
        })
        .setup(move |app| {
            let window = app.get_webview_window("main").unwrap();
            let window_clone = window.clone();

            // Показываем окно явно после создания WebView.
            let _ = window.show();
            let _ = window.set_focus();

            // При закрытии окна скрываем его вместо полного завершения,
            // чтобы daemon продолжал работать в фоне (системный трей).
            window.on_window_event(move |event| {
                if let tauri::WindowEvent::CloseRequested { .. } = event {
                    let _ = window_clone.hide();
                }
            });

            // Запускаем фоновый мониторинг здоровья ноды при старте приложения.
            let g = Arc::clone(&guardian);
            tauri::async_runtime::spawn(async move {
                Guardian::start_health_monitor(g).await;
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            // Guardian команды
            guardian_start_node,
            guardian_check_health,
            guardian_restart_node,
            guardian_stop_node,
            guardian_status,
            guardian_toggle_monitor,
            tg_send_test,
            // API прокси команды
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
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
