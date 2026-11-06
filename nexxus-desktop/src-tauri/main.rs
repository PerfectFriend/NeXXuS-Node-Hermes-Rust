#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use crate::guardian::{
    guardian_check_health, guardian_restart_node, guardian_shutdown_everything,
    guardian_start_node, guardian_status, guardian_stop_node, guardian_toggle_monitor,
    health_loop, tg_send_test,
};
use crate::telegram::get_bot;
use std::sync::Arc;
use tauri::{
    command, menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Builder, Manager, State, WindowEvent,
};

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

/// Показать окно дашборда (из трея).
fn show_dashboard(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn main() {
    let guardian_state = Arc::new(guardian::GuardianState::new());
    let app_state = AppState { guardian: guardian_state.clone() };

    let app = Builder::default()
        .manage(app_state)
        .setup(|app| {
            // Окно не показывается при старте — только иконка в трее
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.hide();
            }

            // --- Иконка трея: красная N в синем семиугольнике ---
            let open_i = MenuItem::with_id(app, "open", "📊 Открыть дашборд", true, None::<&str>)?;
            let start_i = MenuItem::with_id(app, "start", "▶️ Запустить ноду", true, None::<&str>)?;
            let restart_i = MenuItem::with_id(app, "restart", "🔄 Перезапустить ноду", true, None::<&str>)?;
            let stop_i = MenuItem::with_id(app, "stop", "⏹ Остановить ноду", true, None::<&str>)?;
            let health_i = MenuItem::with_id(app, "health", "🩺 Проверить здоровье", true, None::<&str>)?;
            let sep1 = PredefinedMenuItem::separator(app)?;
            let tg_i = MenuItem::with_id(app, "tg", "🧪 Тест Telegram", true, None::<&str>)?;
            let sep2 = PredefinedMenuItem::separator(app)?;
            let quit_i = MenuItem::with_id(app, "shutdown", "⛔ Полное отключение (нода + монитор)", true, None::<&str>)?;
            let menu = Menu::with_items(
                app,
                &[&open_i, &sep1, &start_i, &restart_i, &stop_i, &health_i, &sep2, &tg_i, &sep2, &quit_i],
            )?;

            TrayIconBuilder::with_id("main")
                .icon(tauri::include_image!("src-tauri/icons/tray-icon.png"))
                .tooltip("NeXXus Node Monitor — запуск...")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| {
                    let app = app.clone();
                    let guardian = app.state::<AppState>().guardian.clone();
                    match event.id().as_ref() {
                        "open" => show_dashboard(&app),
                        "health" => show_dashboard(&app),
                        "tg" => {
                            tauri::async_runtime::spawn(async move {
                                let _ = tg_send_test().await;
                            });
                        }
                        "start" => {
                            tauri::async_runtime::spawn(async move {
                                let _ = guardian_start_node(guardian).await;
                            });
                        }
                        "restart" => {
                            tauri::async_runtime::spawn(async move {
                                let _ = guardian_restart_node(guardian).await;
                            });
                        }
                        "stop" => {
                            tauri::async_runtime::spawn(async move {
                                let _ = guardian_stop_node(guardian).await;
                            });
                        }
                        // Полное отключение: стоп ноды + отчёт + выгрузка монитора
                        "shutdown" => {
                            tauri::async_runtime::spawn(async move {
                                guardian_shutdown_everything(guardian).await;
                                // «Паника»: жёсткая выгрузка процесса монитора из памяти
                                std::process::exit(0);
                            });
                        }
                        _ => {}
                    }
                })
                .on_tray_icon_event(|tray, event| {
                    // Левый клик по иконке — открыть дашборд
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        show_dashboard(tray.app_handle());
                    }
                })
                .build(app)?;

            // --- Автостарт ноды + фоновый мониторинг здоровья ---
            let guardian = app.state::<AppState>().guardian.clone();
            tauri::async_runtime::spawn(async move {
                if !guardian::is_nexxusd_running() {
                    if let Err(e) = guardian::start_nexxusd() {
                        let bot = get_bot().await;
                        let _ = bot.notify_node_start_failed(&e).await;
                    }
                }
                if guardian::wait_for_api_ready(30).await {
                    let _ = guardian_start_node(guardian.clone()).await;
                }
                // Основной цикл: health-check каждые 10 сек + Telegram-отчёты
                health_loop(guardian).await;
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
        .on_window_event(|window, event| {
            // Закрытие окна = свернуть в трей, монитор продолжает жить
            if let WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .build(tauri::generate_context!())
        .unwrap_or_else(|e| panic!("Не удалось инициализировать приложение: {e}"));

    // Монитор живёт в трее: запрещаем Tauri завершаться при закрытии окна.
    // Без этого под systemd процесс выходил с кодом 0 через несколько секунд
    // после старта (окно закрывалось → event loop завершался → обычный выход,
    // а Restart=on-failure на штатный exit 0 не срабатывал).
    app.run(|_handle, event| {
        if let tauri::RunEvent::ExitRequested { api, .. } = event {
            api.prevent_exit();
        }
    });
}

