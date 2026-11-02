//! Tor transport via arti-client (ADR-0006).
//! Тяжёлая зависимость — собирается только при `cargo build --features tor`;
//! по умолчанию демон работает по TCP/WS без Tor.

/// Tor-сессия для маршрутизации SMP-конвертов через onion v3 адреса.
#[cfg(feature = "tor")]
#[allow(dead_code)]
pub struct TorSession {
    client: arti_client::TorClient,
}

#[cfg(feature = "tor")]
#[allow(dead_code)]
impl TorSession {
    pub async fn new() -> std::io::Result<Self> {
        let client = arti_client::TorClient::create_bootstrapped()
            .await
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;
        Ok(Self { client })
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
        Err(std::io::Error::other("Tor feature disabled — rebuild with --features tor"))
    }
}
