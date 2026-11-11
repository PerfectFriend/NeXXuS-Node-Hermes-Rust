//! Интеграция с Telegram ботом «Мастер Инквизитор» (Master Inquisitor).
//! Отправляет уведомления о событиях жизненного цикла ноды NeXXus.

use reqwest::Client;
use serde_json::json;
use std::sync::Arc;
use std::time::Duration;
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
        // Токен: env → secrets-файл проекта → ~/.nexxus/telegram.json (вводится из UI).
        // Значение никогда не логируется и не попадает в конфиги.
        let home = std::env::var("HOME").unwrap_or_else(|_| "/tmp".into());
        let json_cfg = read_json_config();
        let token = std::env::var("NEXXUS_TG_BOT_TOKEN").ok().filter(|t| !t.is_empty()).or(json_cfg.0).or_else(|| {
            std::fs::read_to_string(format!("{home}/.hermes/secrets/cathedral_bot_token"))
                .ok()
                .map(|s| s.trim().to_string())
                .filter(|t| !t.is_empty())
        });

        // Chat ID: env → secrets-файл → ~/.nexxus/telegram.json.
        // В репозитории идентификатора нет — он не должен попадать в git.
        let chat_id = std::env::var("NEXXUS_TG_CHAT_ID")
            .ok()
            .filter(|c| !c.is_empty())
            .or(json_cfg.1)
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

// --- Конфиг Telegram из UI (Phase C: панель настроек) ---

/// Путь к файлу конфига Telegram монитора (`~/.nexxus/telegram.json`).
fn json_config_path() -> std::path::PathBuf {
    crate::node_config::config_dir().join("telegram.json")
}

/// Читает (bot_token, chat_id) из telegram.json. Значения не логируются.
fn read_json_config() -> (Option<String>, Option<String>) {
    let Ok(text) = std::fs::read_to_string(json_config_path()) else {
        return (None, None);
    };
    let v: serde_json::Value = match serde_json::from_str(&text) {
        Ok(v) => v,
        Err(_) => return (None, None),
    };
    let token = v.get("bot_token").and_then(|x| x.as_str()).map(|s| s.trim().to_string()).filter(|s| !s.is_empty());
    let chat = v.get("chat_id").and_then(|x| x.as_str()).map(|s| s.trim().to_string()).filter(|s| !s.is_empty());
    (token, chat)
}

/// Сохраняет конфиг Telegram из UI: атомарная запись, права 0600.
/// Значения в лог/ошибки не попадают.
pub fn save_telegram_config(bot_token: &str, chat_id: &str) -> Result<(), String> {
    let token = bot_token.trim();
    let chat = chat_id.trim();
    if token.is_empty() || chat.is_empty() {
        return Err("токен и chat_id не должны быть пустыми".into());
    }
    let path = json_config_path();
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir).map_err(|e| format!("create_dir_all: {e}"))?;
    }
    let tmp = path.with_extension("json.tmp");
    let text = serde_json::to_string_pretty(&serde_json::json!({
        "bot_token": token,
        "chat_id": chat,
    })).map_err(|e| format!("serialize: {e}"))?;
    {
        use std::io::Write;
        let mut f = std::fs::File::create(&tmp).map_err(|e| format!("create: {e}"))?;
        f.write_all(text.as_bytes()).map_err(|e| format!("write: {e}"))?;
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            std::fs::set_permissions(&tmp, std::fs::Permissions::from_mode(0o600))
                .map_err(|e| format!("chmod: {e}"))?;
        }
    }
    std::fs::rename(&tmp, &path).map_err(|e| format!("rename: {e}"))?;
    Ok(())
}

/// Статус конфига Telegram для UI: флаги и источники, без значений.
pub fn telegram_config_status() -> serde_json::Value {
    let json_cfg = read_json_config();
    let home = std::env::var("HOME").unwrap_or_else(|_| "/tmp".into());
    let env_token = std::env::var("NEXXUS_TG_BOT_TOKEN").ok().filter(|t| !t.is_empty()).is_some();
    let env_chat = std::env::var("NEXXUS_TG_CHAT_ID").ok().filter(|c| !c.is_empty()).is_some();
    let sec_token = std::path::Path::new(&format!("{home}/.hermes/secrets/cathedral_bot_token")).exists();
    let sec_chat = std::path::Path::new(&format!("{home}/.hermes/secrets/nexxus_chat_id")).exists();
    serde_json::json!({
        "token_set": env_token || json_cfg.0.is_some() || sec_token,
        "token_source": if env_token { "env" } else if json_cfg.0.is_some() { "ui (~/.nexxus/telegram.json)" } else if sec_token { "secrets file" } else { "none" },
        "chat_set": env_chat || json_cfg.1.is_some() || sec_chat,
        "chat_source": if env_chat { "env" } else if json_cfg.1.is_some() { "ui (~/.nexxus/telegram.json)" } else if sec_chat { "secrets file" } else { "none" },
        "configured": (env_token || json_cfg.0.is_some() || sec_token) && (env_chat || json_cfg.1.is_some() || sec_chat),
        "config_path": json_config_path().to_string_lossy(),
    })
}

/// Сбрасывает кэш бота, чтобы новый конфиг подхватился сразу.
pub async fn reload_bot() {
    let mut guard = TELEGRAM_BOT.lock().await;
    *guard = None;
}

/// Проверяет токен через getMe (ничего не сохраняет, токен не логируется).
pub async fn check_bot_token(bot_token: &str) -> Result<serde_json::Value, String> {
    let token = bot_token.trim();
    if token.is_empty() {
        return Err("пустой токен".into());
    }
    let client = reqwest::Client::builder()
        .connect_timeout(Duration::from_secs(5))
        .timeout(Duration::from_secs(10))
        .build()
        .map_err(|e| e.to_string())?;
    let url = format!("https://api.telegram.org/bot{token}/getMe");
    let resp = client.get(&url).send().await.map_err(|e| format!("getMe: {e}"))?;
    let v: serde_json::Value = resp.json().await.map_err(|e| format!("getMe json: {e}"))?;
    if v.get("ok").and_then(|o| o.as_bool()) == Some(true) {
        Ok(v.get("result").cloned().unwrap_or(serde_json::Value::Null))
    } else {
        Err(format!("getMe не ok: {}", v.get("description").and_then(|d| d.as_str()).unwrap_or("?")))
    }
}

#[cfg(test)]
mod config_tests {
    use super::*;
    use std::sync::Mutex;

    static ENV_LOCK: Mutex<()> = Mutex::new(());

    fn with_temp_dir(f: impl FnOnce()) {
        let _g = ENV_LOCK.lock().unwrap();
        let dir = std::env::temp_dir().join(format!("nexxus-tg-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::env::set_var("NEXXUS_CONFIG_DIR", &dir);
        f();
        std::env::remove_var("NEXXUS_CONFIG_DIR");
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn save_then_read_roundtrip_and_perms() {
        with_temp_dir(|| {
            save_telegram_config("123:ABC", "42").unwrap();
            let (t, c) = read_json_config();
            assert_eq!(t.as_deref(), Some("123:ABC"));
            assert_eq!(c.as_deref(), Some("42"));
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                let mode = std::fs::metadata(json_config_path()).unwrap().permissions().mode();
                assert_eq!(mode & 0o777, 0o600);
            }
            let st = telegram_config_status();
            assert_eq!(st["token_set"], true);
            assert_eq!(st["chat_set"], true);
            // значения не утекают в статус
            let s = st.to_string();
            assert!(!s.contains("123:ABC"));
            assert!(!s.contains("\"42\""));
        });
    }

    #[test]
    fn save_rejects_empty() {
        with_temp_dir(|| {
            assert!(save_telegram_config("", "42").is_err());
            assert!(save_telegram_config("123:ABC", "  ").is_err());
        });
    }

    #[test]
    fn missing_config_is_none() {
        with_temp_dir(|| {
            assert_eq!(read_json_config(), (None, None));
        });
    }
}
