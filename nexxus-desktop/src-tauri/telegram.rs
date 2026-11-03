//! Интеграция с Telegram ботом «Мастер Инквизитор» (Master Inquisitor).
//! Отправляет уведомления о событиях жизненного цикла ноды NeXXus:
//!   - запуск / остановка nexxusd
//!   - ошибки подключения к API
//!   - сбои здоровья ноды и автоперезапуск
//!   - периодические отчёты о здоровье (heartbeat)
//
//! Настройка через переменные окружения:
//!   NEXXUS_TG_BOT_TOKEN — токен бота (от @BotFather)
//!   NEXXUS_TG_CHAT_ID   — ID чата пользователя/мастера
//!
//! Если переменные не заданы — уведомления отключаются (работа в офлайн-режиме).

use reqwest::Client;
use serde_json::json;
use std::sync::Arc;
use tokio::sync::Mutex;

/// Клиент Telegram Bot API.
#[derive(Clone)]
pub struct TelegramBot {
    client: Client,
    token: Option<String>,
    chat_id: Option<String>,
}

impl TelegramBot {
    pub fn new() -> Self {
        let token = std::env::var("NEXXUS_TG_BOT_TOKEN").ok();
        let chat_id = std::env::var("NEXXUS_TG_CHAT_ID").ok();
        Self {
            client: Client::new(),
            token,
            chat_id,
        }
    }

    /// Проверяет, настроен ли бот (есть ли токен и chat_id).
    pub fn is_configured(&self) -> bool {
        self.token.is_some() && self.chat_id.is_some()
    }

    /// Отправляет текстовое сообщение в чат.
    pub async fn send_message(&self, text: &str) -> Result<(), String> {
        let token = match &self.token {
            Some(t) => t.clone(),
            None => return Err("Telegram bot token not configured".into()),
        };
        let chat_id = match &self.chat_id {
            Some(c) => c.clone(),
            None => return Err("Telegram chat ID not configured".into()),
        };

        let url = format!("https://api.telegram.org/bot{token}/sendMessage");
        let payload = json!({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": true,
        });

        let response = self.client.post(&url).json(&payload).send().await
            .map_err(|e| format!("Telegram request failed: {e}"))?;

        if response.status().is_success() {
            Ok(())
        } else {
            let status = response.status();
            let body = response.text().await.unwrap_or_default();
            Err(format!("Telegram API error: {status} {body}"))
        }
    }

    /// Отправляет уведомление о запуске монитора.
    pub async fn notify_monitor_started(&self) -> Result<(), String> {
        if !self.is_configured() {
            return Ok(());
        }
        self.send_message(
            "🛡️ <b>NeXXus Guardian запущен</b>\n\nМонитор ноды активирован. Ожидание nexxusd...",
        )
        .await
    }

    /// Отправляет уведомление о запуске nexxusd.
    pub async fn notify_node_starting(&self) -> Result<(), String> {
        if !self.is_configured() {
            return Ok(());
        }
        self.send_message(
            "🔄 <b>Запуск nexxusd...</b>\n\nОжидание инициализации узла и API...",
        )
        .await
    }

    /// Отправляет уведомление о successful запуске ноды.
    pub async fn notify_node_started(&self, node_id: &str, listen_addr: &str) -> Result<(), String> {
        if !self.is_configured() {
            return Ok(());
        }
        self.send_message(&format!(
            "✅ <b>nexxusd запущен</b>\n\nNode ID: <code>{}</code>\nAPI: <code>{}</code>\nСтатус: онлайн",
            node_id, listen_addr
        ))
        .await
    }

    /// Отправляет уведомление о сбое запуска ноды.
    pub async fn notify_node_start_failed(&self, error: &str) -> Result<(), String> {
        if !self.is_configured() {
            return Ok(());
        }
        self.send_message(&format!(
            "❌ <b>Ошибка запуска nexxusd</b>\n\n{}",
            error
        ))
        .await
    }

    /// Отправляет уведомление о потере связи с нодой.
    pub async fn notify_node_unhealthy(&self, error: &str) -> Result<(), String> {
        if !self.is_configured() {
            return Ok(());
        }
        self.send_message(&format!(
            "⚠️ <b>nexxusd не отвечает</b>\n\n{}",
            error
        ))
        .await
    }

    /// Отправляет уведомление об автоперезапуске ноды.
    pub async fn notify_node_restarting(&self, reason: &str) -> Result<(), String> {
        if !self.is_configured() {
            return Ok(());
        }
        self.send_message(&format!(
            "🔄 <b>Автоперезапуск nexxusd</b>\n\nПричина: {}",
            reason
        ))
        .await
    }

    /// Отправляет уведомление об успешном автоперезапуске.
    pub async fn notify_node_restarted(&self) -> Result<(), String> {
        if !self.is_configured() {
            return Ok(());
        }
        self.send_message("✅ <b>nexxusd перезапущен и отвечает</b>").await
    }

    /// Отправляет периодический отчёт о здоровье ноды.
    pub async fn notify_heartbeat(&self, node_id: &str, peers: usize, uptime_ms: u128) -> Result<(), String> {
        if !self.is_configured() {
            return Ok(());
        }
        let uptime_min = uptime_ms / 60_000;
        self.send_message(&format!(
            "💓 <b>NeXXus Heartbeat</b>\n\nNode ID: <code>{}</code>\nПиры: {}\nАптайм: {} мин",
            node_id, peers, uptime_min
        ))
        .await
    }

    /// Отправляет уведомление об остановке монитора.
    pub async fn notify_monitor_stopped(&self) -> Result<(), String> {
        if !self.is_configured() {
            return Ok(());
        }
        self.send_message("🛑 <b>NeXXus Guardian остановлен</b>").await
    }
}

/// Глобальный экземпляр бота (инициализируется один раз при старте).
static TELEGRAM_BOT: Mutex<Option<TelegramBot>> = Mutex::const_new(None);

/// Получить или инициализировать глобальный бот-клиент.
pub async fn get_bot() -> Arc<TelegramBot> {
    let guard = TELEGRAM_BOT.lock().await;
    if guard.is_none() {
        drop(guard);
        let mut guard = TELEGRAM_BOT.lock().await;
        if guard.is_none() {
            *guard = Some(TelegramBot::new());
        }
    }
    Arc::new(TELEGRAM_BOT.lock().await.as_ref().unwrap().clone())
}
