//! Tor transport via arti-client (ADR-0006).
//! Feature `tor` включён по умолчанию (`default = ["tor"]`); демон bootstrap'ит
//! arti-клиент, публикует onion v3 hidden service на P2P-порту и умеет диалить
//! чужие `.onion` адреса. NEXXUS_TOR=0 выключает Tor на рантайме.

#[cfg(feature = "tor")]
mod imp {
    use std::net::SocketAddr;
    use std::sync::Arc;

    use arti_client::TorClient;
    use futures_util::StreamExt;
    use safelog::DisplayRedacted;
    use tor_rtcompat::PreferredRuntime as TokioRuntime;

    type TorClientType = TorClient<TokioRuntime>;

    fn io_err(e: impl std::fmt::Display) -> std::io::Error {
        std::io::Error::other(format!("{e}"))
    }

    /// Tor-сессия: bootstrapped arti-клиент + опубликованный onion v3 сервис.
    pub struct TorSession {
        client: Arc<TorClientType>,
        our_onion: Option<String>,
    }

    impl TorSession {
        /// Bootstrap Tor-клиента; state/cache живут в ~/.nexxus/tor.
        pub async fn new() -> std::io::Result<Self> {
            let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
            let base = std::path::Path::new(&home).join(".nexxus").join("tor");
            std::fs::create_dir_all(&base)?;
            let config = arti_client::config::TorClientConfigBuilder::from_directories(
                base.join("state"),
                base.join("cache"),
            )
            .build()
            .map_err(io_err)?;
            let client = TorClient::create_bootstrapped(config)
                .await
                .map_err(io_err)?;
            Ok(Self {
                client,
                our_onion: None,
            })
        }

        /// Опубликовать onion v3 hidden service, форвардящий на локальный P2P-порт.
        /// Возвращает адрес вида `<56 base32>.onion`.
        pub async fn publish_onion(&mut self, local_addr: SocketAddr) -> std::io::Result<String> {
            let svc_cfg = tor_hsservice::config::OnionServiceConfigBuilder::default()
                .nickname(
                    tor_hsservice::HsNickname::new("nexxus".to_string()).map_err(io_err)?,
                )
                .build()
                .map_err(io_err)?;
            let launched = self.client.launch_onion_service(svc_cfg).map_err(io_err)?;
            let (running, requests) =
                launched.ok_or_else(|| io_err("onion service disabled in config"))?;
            let onion = running
                .onion_address()
                .ok_or_else(|| io_err("onion service has no address"))?
                .display_unredacted()
                .to_string();
            // Accept loop: входящие onion-стримы форвардим на локальный P2P порт.
            // Задача держит Arc сервиса, пока жив TorSession.
            tokio::spawn(async move {
                let mut requests = tor_hsservice::handle_rend_requests(requests);
                while let Some(sr) = requests.next().await {
                    tokio::spawn(async move {
                        if let Ok(mut onion_stream) =
                            sr.accept(tor_cell::relaycell::msg::Connected::new_empty()).await
                        {
                            if let Ok(mut local) = tokio::net::TcpStream::connect(local_addr).await {
                                let _ =
                                    tokio::io::copy_bidirectional(&mut onion_stream, &mut local)
                                        .await;
                            }
                        }
                    });
                }
                drop(running);
            });
            self.our_onion = Some(onion.clone());
            Ok(onion)
        }

        /// Подключиться к onion v3 адресу (например, "<id>.onion:4001").
        /// Используется в `P2pNetwork::dial_onion` для P2P-соединений через Tor.
        pub async fn connect_onion(
            &self,
            onion_addr: &str,
        ) -> std::io::Result<arti_client::DataStream> {
            self.client.connect(onion_addr).await.map_err(io_err)
        }

        /// Наш onion v3 адрес, если сервис опубликован.
        pub fn our_onion(&self) -> Option<&str> {
            self.our_onion.as_deref()
        }
    }
}

#[cfg(feature = "tor")]
pub use imp::TorSession;
