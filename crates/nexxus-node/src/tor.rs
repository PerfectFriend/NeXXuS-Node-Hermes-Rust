//! Tor transport via arti-client (ADR-0006).
//! Реализация Phase 9: реальный arti-client с onion v3_hidden service.
//! Собирается только при `cargo build --features tor`;
//! по умолчанию демон работает по TCP/WS без Tor.

#[cfg(feature = "tor")]
use std::sync::Arc;
#[cfg(feature = "tor")]
use arti_client::{TorClient, TorClientConfig};
#[cfg(feature = "tor")]
use tor_rtcompat::PreferredRuntime as TokioRuntime;

#[cfg(feature = "tor")]
type TorClientType = TorClient<TokioRuntime>;

/// Tor-сессия для маршрутизации SMP-конвертов через onion v3 адреса.
#[cfg(feature = "tor")]
#[allow(dead_code)]
pub struct TorSession {
    client: Arc<TorClientType>,
    our_onion: Option<String>, // .onion адрес нашего скрытого сервиса
}

#[cfg(feature = "tor")]
#[allow(dead_code)]
impl TorSession {
    /// Создаёт bootstrapped Tor-клиент через arti.
    pub async fn new() -> std::io::Result<Self> {
        let config = TorClientConfig::default();
        let client = TorClient::create_bootstrapped(config)
            .await
            .map_err(|e| {
                std::io::Error::new(
                    std::io::ErrorKind::Other,
                    format!("tor bootstrap: {e}"),
                )
            })?;
        Ok(Self {
            client,
            our_onion: None,
        })
    }

    /// Подключиться к onion v3 адресу (например, "abcdef...onion:4001").
    pub async fn connect_onion(
        &self,
        onion_addr: &str,
    ) -> std::io::Result<arti_client::DataStream> {
        self.client
            .connect(onion_addr)
            .await
            .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, format!("tor connect: {e}")))
    }

    /// Наш текущий onion v3 адрес (если скрытый сервис опубликован).
    pub fn our_onion(&self) -> Option<&str> {
        self.our_onion.as_deref()
    }

    /// Ссылка на внутренний TorClient (для расширенного использования).
    pub fn client(&self) -> &TorClientType {
        &self.client
    }
}

/// Заглушка без включённого feature `tor`: демон работает по TCP/WS.
#[cfg(not(feature = "tor"))]
#[allow(dead_code)]
pub struct TorSession;

#[cfg(not(feature = "tor"))]
#[allow(dead_code)]
impl TorSession {
    pub async fn new() -> std::io::Result<Self> {
        Err(std::io::Error::other(
            "Tor feature disabled — rebuild with --features tor",
        ))
    }

    pub async fn connect_onion(&self, _onion_addr: &str) -> std::io::Result<std::io::Empty> {
        Err(std::io::Error::other(
            "Tor feature disabled — rebuild with --features tor",
        ))
    }

    pub fn our_onion(&self) -> Option<&str> {
        None
    }
}
