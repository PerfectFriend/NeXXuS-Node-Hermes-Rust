#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use crate::commands::{
    guardian_check_health_cmd, guardian_restart_node_cmd, guardian_shutdown_cmd,
    guardian_start_node_cmd, guardian_status_cmd, guardian_stop_node_cmd,
    guardian_toggle_monitor_cmd, node_api_cmd, node_config_get_cmd, node_config_set_cmd,
    node_config_validate_cmd, node_install_cmd, node_install_status_cmd, node_log_tail_cmd,
    node_uninstall_cmd, onboarding_advance_cmd, onboarding_get_cmd, onboarding_reset_cmd,
    run_health_loop, tg_config_check_cmd, tg_config_save_cmd, tg_config_status_cmd,
    tg_send_alert_cmd, tg_send_test_cmd, AppState, selftest_cmd,
};
use crate::guardian::{
    guardian_check_health, guardian_restart_node, guardian_shutdown_everything,
    guardian_start_node, guardian_stop_node, tg_send_test,
};
use crate::telegram::get_bot;
use std::sync::Arc;
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Builder, Manager, WindowEvent,
};

mod api_client;
mod commands;
mod guardian;
mod instance;
mod node_config;
mod node_unit;
mod onboarding;
mod telegram;

/// Обновляет подсказку трея — единственный способ дать пользователю
/// обратную связь от пунктов меню без открытого окна.
fn set_tray_tooltip(app: &AppHandle, text: &str) {
    if let Some(tray) = app.tray_by_id("main") {
        let _ = tray.set_tooltip(Some(text));
    }
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
    // Флаг --shutdown (из .desktop-действия Quit): работающий экземпляр
    // держит lock, поэтому этот процесс не запустится — вместо этого он
    // оставляет файл-запрос, и работающий монитор выполнит полное
    // отключение на ближайшем тике health loop.
    if std::env::args().any(|a| a == "--shutdown") {
        let _ = std::fs::write(guardian::shutdown_request_path(), "shutdown\n");
        eprintln!("Запрошено полное отключение — работающий монитор остановит ноду и выйдет.");
        std::process::exit(0);
    }

    // Однократный запуск: второй экземпляр (повторный клик по ярлыку) не
    // поднимает вторую ноду и не воскрешает остановленную — выходит тихо.
    let _instance_lock = match instance::InstanceLock::acquire() {
        Ok(lock) => lock,
        Err(msg) => {
            let log = crate::node_config::config_dir().join("monitor.log");
            let _ = std::fs::write(&log, format!("{}\n", msg));
            eprintln!("{msg}");
            std::process::exit(0);
        }
    };

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
                        // Проверка здоровья реально опрашивает ноду и
                        // показывает результат в подсказке трея; дашборд
                        // открывается параллельно.
                        "health" => {
                            show_dashboard(&app);
                            tauri::async_runtime::spawn(async move {
                                match guardian_check_health(guardian).await {
                                    Ok(status) => set_tray_tooltip(
                                        &app,
                                        &format!("NeXXus Monitor — здоровье: {status}"),
                                    ),
                                    Err(e) => set_tray_tooltip(
                                        &app,
                                        &format!("NeXXus Monitor — ошибка здоровья: {e}"),
                                    ),
                                }
                            });
                        }
                        "tg" => {
                            tauri::async_runtime::spawn(async move {
                                let _ = tg_send_test().await;
                            });
                        }
                        "start" => {
                            tauri::async_runtime::spawn(async move {
                                match guardian_start_node(guardian).await {
                                    Ok(_) => set_tray_tooltip(&app, "NeXXus Monitor — нода запущена"),
                                    Err(e) => set_tray_tooltip(&app, &format!("NeXXus Monitor — ошибка запуска: {e}")),
                                }
                            });
                        }
                        "restart" => {
                            tauri::async_runtime::spawn(async move {
                                match guardian_restart_node(guardian).await {
                                    Ok(_) => set_tray_tooltip(&app, "NeXXus Monitor — нода перезапущена"),
                                    Err(e) => set_tray_tooltip(&app, &format!("NeXXus Monitor — ошибка перезапуска: {e}")),
                                }
                            });
                        }
                        // Ошибку остановки нельзя проглатывать: раньше
                        // `let _ =` делал кнопку визуально нерабочей.
                        "stop" => {
                            tauri::async_runtime::spawn(async move {
                                match guardian_stop_node(guardian).await {
                                    Ok(_) => set_tray_tooltip(&app, "NeXXus Monitor — нода остановлена"),
                                    Err(e) => set_tray_tooltip(&app, &format!("NeXXus Monitor — ошибка остановки: {e}")),
                                }
                            });
                        }
                        // Полное отключение: стоп ноды + отчёт + выгрузка монитора.
                        // Таймаут жёсткий: даже если Telegram недоступен,
                        // процесс обязан уйти из памяти — иначе кнопка
                        // «не срабатывает» при любой сетевой проблеме.
                        "shutdown" => {
                            tauri::async_runtime::spawn(async move {
                                let _ = tokio::time::timeout(
                                    std::time::Duration::from_secs(15),
                                    guardian_shutdown_everything(guardian),
                                )
                                .await;
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
                run_health_loop(guardian).await;
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
            guardian_shutdown_cmd,
            tg_send_test_cmd,
            tg_send_alert_cmd,
            tg_config_status_cmd,
            tg_config_save_cmd,
            tg_config_check_cmd,
            node_api_cmd,
            selftest_cmd,
            node_log_tail_cmd,
            onboarding_get_cmd,
            onboarding_advance_cmd,
            onboarding_reset_cmd,
            node_config_get_cmd,
            node_config_set_cmd,
            node_config_validate_cmd,
            node_install_cmd,
            node_uninstall_cmd,
            node_install_status_cmd,
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

