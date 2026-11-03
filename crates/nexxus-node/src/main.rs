//! NeXXUs storage daemon (nexxusd).
//! Phase 8: full network protocol daemon — redb persistent chunk index,
//! P2P network listener (wire v3), NodeAnnounce/SmpEnvelope/EpochFinalize/PoR handlers.
//!
//! Запуск:
//!   nexxusd <store-path>
//! Переменные окружения:
//!   NEXXUS_LISTEN       — адрес P2P слушателя (по умолчанию 127.0.0.1:4001)
//!   NEXXUS_API_ADDR     — адрес локального WebSocket API (по умолчанию 127.0.0.1:4010)

use std::env;
use std::net::SocketAddr;
use std::process;
use std::sync::Arc;

use hex::encode as hex_encode;
use nexxus_core::types::NodeId;
use rand::rngs::OsRng;
use rand::Rng;
use tokio::signal::unix::{signal, SignalKind};

mod net;
mod storage;
mod tor;
mod local_api;

use crate::net::P2pNetwork;
use crate::storage::ChunkStore;
use crate::local_api::LocalApi;

fn main() {
    // --- Аргументы командной строки ---
    // Первый позиционный аргумент — путь к файлу хранилища redb.
    let path = env::args().nth(1).unwrap_or_else(|| {
        eprintln!("usage: nexxusd <store-path>");
        process::exit(2);
    });

    // --- Адреса слушателей ---
    // NEXXUS_LISTEN — адрес для P2P соединений (не для API).
    let listen_addr: SocketAddr = env::var("NEXXUS_LISTEN")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or_else(|| "127.0.0.1:4001".parse().unwrap());

    // NEXXUS_API_ADDR — адрес для локального WebSocket API (для nexxus-desktop).
    let api_addr: SocketAddr = env::var("NEXXUS_API_ADDR")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or_else(|| "127.0.0.1:4010".parse().unwrap());

    // --- Идентификатор узла ---
    // Генерируем случайный 32-байтовый NodeId через криптографически стойкий OsRng.
    // ВНИМАНИЕ: при каждом перезапуске узел получает НОВЫЙ ID. Для production
    // необходимо заменить на детерминированную деривацию из seed (SLIP-0010),
    // сохранённого в хранилище, чтобы узел был идентифицируем между запусками.
    let mut node_id_bytes = [0u8; 32];
    OsRng.fill(&mut node_id_bytes);
    let our_id = NodeId(node_id_bytes);

    // --- Tokio runtime ---
    let rt = tokio::runtime::Runtime::new().expect("tokio runtime");

    rt.block_on(async {
        // --- Хранилище чанков (redb) ---
        // Открываем persistent базу данных по указанному пути.
        let store = match ChunkStore::open(&path) {
            Ok(s) => Arc::new(s),
            Err(e) => {
                eprintln!("nexxusd: failed to open store: {e}");
                process::exit(1);
            }
        };

        // --- P2P сеть ---
        let net = Arc::new(P2pNetwork::new(our_id, listen_addr, Arc::clone(&store)));

        // --- Локальное WebSocket API ---
        let api = Arc::new(LocalApi::new(Arc::clone(&net), Arc::clone(&store)));
        // Привязываем API к сети, чтобы сеть могла регистрировать пиров в API.
        net.set_local_api(Arc::clone(&api)).await;

        println!(
            "nexxusd {} — node {} listening on {}",
            env!("CARGO_PKG_VERSION"),
            hex_encode(our_id.0),
            listen_addr
        );

        // --- Запуск задач ---
        // P2P сеть: принимает входящие соединения, обрабатывает опкоды.
        let net_clone = Arc::clone(&net);
        let p2p_task = tokio::spawn(async move {
            if let Err(e) = net_clone.run().await {
                eprintln!("nexxusd: network error: {e}");
                process::exit(1);
            }
        });

        // Локальное WebSocket API: принимает соединения от nexxus-desktop.
        let api_task = tokio::spawn(async move {
            if let Err(e) = api.run(api_addr).await {
                eprintln!("nexxusd: API error: {e}");
                process::exit(1);
            }
        });

        // --- Обработка сигналов завершения ---
        // Корректно завершаем по SIGINT (Ctrl+C) или SIGTERM.
        let mut sigint = signal(SignalKind::interrupt()).expect("failed to register SIGINT");
        let mut sigterm = signal(SignalKind::terminate()).expect("failed to register SIGTERM");

        tokio::select! {
            _ = p2p_task => {
                eprintln!("nexxusd: P2P task exited");
            }
            _ = api_task => {
                eprintln!("nexxusd: API task exited");
            }
            _ = sigint.recv() => {
                eprintln!("nexxusd: received SIGINT, shutting down");
            }
            _ = sigterm.recv() => {
                eprintln!("nexxusd: received SIGTERM, shutting down");
            }
        }
    });
}
