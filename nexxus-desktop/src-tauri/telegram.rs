//! Интеграция с Telegram ботом «Мастер Инквизитор» (Master Inquisitor).
//! Отправляет уведомления о событиях жизненного цикла ноды NeXXus.

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
        // Токен: env → secrets-файл проекта (тот же источник, что у orchestration-скриптов).
        // Значение никогда не логируется и не попадает в конфиги.
        let home = std::env::var("HOME").unwrap_or_else(|_| "/tmp".into());
        let token = std::env::var("NEXXUS_TG_BOT_TOKEN").ok().filter(|t| !t.is_empty()).or_else(|| {
            std::fs::read_to_string(format!("{home}/.hermes/secrets/cathedral_bot_token"))
                .ok()
                .map(|s| s.trim().to_string())
                .filter(|t| !t.is_empty())
        });

        // Chat ID: env → secrets-файл. В репозитории идентификатора нет —
        // он не является публичным значением и не должен попадать в git.
        let chat_id = std::env::var("NEXXUS_TG_CHAT_ID")
            .ok()
            .filter(|c| !c.is_empty())
            .or_else(|| {
                std::fs::read_to_string(format!("{home}/.hermes/secrets/nexxus_chat_id"))
                    .ok()
                    .map(|s| s.trim().to_string())
                    .filter(|c| !c.is_empty())
            });

        Self {
            // Таймауты обязательны: без них зависший Telegram-запрос блокировал
            // «полное отключение» — процесс не доходил до выгрузки из памяти.
            client: Client::builder()
                .connect_timeout(std::time::Duration::from_secs(5))
                .timeout(std::time::Duration::from_secs(10))
                .build()
                .unwrap_or_default(),
            token,
            chat_id,
        }
    }

    pub fn is_configured(&self) -> bool {
        self.token.is_some() && self.chat_id.is_some()
    }

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

    pub async fn notify_monitor_started(&self) -> Result<(), String> {
        if !self.is_configured() { return Ok(()); }
        self.send_message("🛡️ <b>NeXXus Guardian запущен</b>\n\nМонитор ноды активирован. Ожидание nexxusd...").await
    }

    pub async fn notify_node_starting(&self) -> Result<(), String> {
        if !self.is_configured() { return Ok(()); }
        self.send_message("🔄 <b>Запуск nexxusd...</b>\n\nОжидание инициализации узла и API...").await
    }

    pub async fn notify_node_started(&self, node_id: &str, listen_addr: &str) -> Result<(), String> {
        if !self.is_configured() { return Ok(()); }
        self.send_message(&format!(
            "✅ <b>nexxusd запущен</b>\n\nNode ID: <code>{}</code>\nAPI: <code>{}</code>\nСтатус: онлайн",
            node_id, listen_addr
        )).await
    }

    pub async fn notify_node_start_failed(&self, error: &str) -> Result<(), String> {
        if !self.is_configured() { return Ok(()); }
        self.send_message(&format!("❌ <b>Ошибка запуска nexxusd</b>\n\n{}", error)).await
    }

    pub async fn notify_node_unhealthy(&self, error: &str) -> Result<(), String> {
        if !self.is_configured() { return Ok(()); }
        self.send_message(&format!("⚠️ <b>nexxusd не отвечает</b>\n\n{}", error)).await
    }

    pub async fn notify_node_restarting(&self, reason: &str) -> Result<(), String> {
        if !self.is_configured() { return Ok(()); }
        self.send_message(&format!("🔄 <b>Автоперезапуск nexxusd</b>\n\nПричина: {}", reason)).await
    }

    pub async fn notify_node_restarted(&self) -> Result<(), String> {
        if !self.is_configured() { return Ok(()); }
        self.send_message("✅ <b>nexxusd перезапущен и отвечает</b>").await
    }

    pub async fn notify_node_stopping(&self) -> Result<(), String> {
        if !self.is_configured() { return Ok(()); }
        self.send_message("⏹ <b>Остановка nexxusd...</b>\n\nРучная остановка ноды через монитор.").await
    }

    pub async fn notify_node_stopped(&self) -> Result<(), String> {
        if !self.is_configured() { return Ok(()); }
        self.send_message("🛑 <b>nexxusd остановлен</b>\n\nПроцесс ноды выгружен из памяти.").await
    }

    pub async fn notify_node_tor(&self, tor: &str) -> Result<(), String> {
        if !self.is_configured() { return Ok(()); }
        self.send_message(&format!(
            "🧅 <b>Tor-сервис активирован</b>\n\n{}",
            tor
        )).await
    }

    pub async fn notify_guardian_shutdown(&self) -> Result<(), String> {
        if !self.is_configured() { return Ok(()); }
        self.send_message("⛔ <b>NeXXus полностью отключён</b>\n\nНода и монитор выгружены из памяти. Автоперезапуск отключён — запуск вручную.").await
    }

    pub async fn notify_heartbeat(&self, node_id: &str, peers: usize, uptime_ms: u128) -> Result<(), String> {
        if !self.is_configured() { return Ok(()); }
        let uptime_min = uptime_ms / 60_000;
        self.send_message(&format!(
            "💓 <b>NeXXus Heartbeat</b>\n\nNode ID: <code>{}</code>\nПиры: {}\nАптайм: {} мин",
            node_id, peers, uptime_min
        )).await
    }

    #[allow(dead_code)]
    pub async fn notify_monitor_stopped(&self) -> Result<(), String> {
        if !self.is_configured() { return Ok(()); }
        self.send_message("🛑 <b>NeXXus Guardian остановлен</b>").await
    }
}

static TELEGRAM_BOT: Mutex<Option<TelegramBot>> = Mutex::const_new(None);

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
