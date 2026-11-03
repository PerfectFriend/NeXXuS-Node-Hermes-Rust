//! Tor transport via arti-client (ADR-0006).
//! Тяжёлая зависимость — собирается только при `cargo build --features tor`;
//! по умолчанию демон работает по TCP/WS без Tor.
//!
//! Под --features tor эта структура является заглушкой: arti-client 0.47
//! требует настройки конфигурации и bootstrap-подключения к сети Tor,
//! что вынесено на отдельный этап (Phase 9+). Коробка собирается,
//! но реальное onion-соединение ещё не проложено.

/// Tor-сессия для маршрутизации SMP-конвертов через onion v3 адреса.
#[cfg(feature = "tor")]
#[allow(dead_code)]
pub struct TorSession {
    _private: (),
}

#[cfg(feature = "tor")]
#[allow(dead_code)]
impl TorSession {
    pub async fn new() -> std::io::Result<Self> {
        Err(std::io::Error::other(
            "Tor session not yet wired — arti-client 0.47 bootstrap config pending (Phase 9)",
        ))
    }
}

/// Заглушка без включённого feature `tor`: демон работает по TCP/WS.
#[cfg(not(feature = "tor"))]
#[allow(dead_code)]
pub struct TorSession;

#[cfg(not(feature = "tor"))]
#[allow(dead_code)]
impl TorSession {
    pub fn new() -> std::io::Result<Self> {
        Err(std::io::Error::other(
            "Tor feature disabled — rebuild with --features tor",
        ))
    }
}
