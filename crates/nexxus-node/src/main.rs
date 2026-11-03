//! NeXXUs storage daemon (nexxusd).
//! Phase 8: full network protocol daemon — redb persistent chunk index,
//! P2P network listener (wire v3), NodeAnnounce/SmpEnvelope/EpochFinalize/PoR handlers.

use std::env;
use std::net::SocketAddr;
use std::process;
use std::sync::Arc;

use hex::encode as hex_encode;
use nexxus_core::types::NodeId;
use rand::rngs::OsRng;
use rand::Rng;

mod net;
mod storage;
mod tor;
mod local_api;

use crate::net::P2pNetwork;
use crate::storage::ChunkStore;
use crate::local_api::LocalApi;

fn main() {
    let path = env::args().nth(1).unwrap_or_else(|| {
        eprintln!("usage: nexxusd <store-path>");
        process::exit(2);
    });

    let listen_addr: SocketAddr = env::var("NEXXUS_LISTEN")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or_else(|| "127.0.0.1:4001".parse().unwrap());

    let api_addr: SocketAddr = env::var("NEXXUS_API_ADDR")
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or_else(|| "127.0.0.1:4010".parse().unwrap());

    let mut node_id_bytes = [0u8; 32];
    OsRng.fill(&mut node_id_bytes);
    let our_id = NodeId(node_id_bytes);

    let rt = tokio::runtime::Runtime::new().expect("tokio runtime");

    rt.block_on(async {
        let store = match ChunkStore::open(&path) {
            Ok(s) => Arc::new(s),
            Err(e) => {
                eprintln!("nexxusd: failed to open store: {e}");
                process::exit(1);
            }
        };

        let net = Arc::new(P2pNetwork::new(our_id, listen_addr, Arc::clone(&store)));
        let api = Arc::new(LocalApi::new(Arc::clone(&net), Arc::clone(&store)));
        net.set_local_api(Arc::clone(&api)).await;

        println!(
            "nexxusd {} — node {} listening on {}",
            env!("CARGO_PKG_VERSION"),
            hex_encode(our_id.0),
            listen_addr
        );

        // Run P2P network and local API server concurrently
        let net_clone = Arc::clone(&net);
        let p2p_task = tokio::spawn(async move {
            if let Err(e) = net_clone.run().await {
                eprintln!("nexxusd: network error: {e}");
                process::exit(1);
            }
        });

        let api_task = tokio::spawn(async move {
            if let Err(e) = api.run(api_addr).await {
                eprintln!("nexxusd: API error: {e}");
                process::exit(1);
            }
        });

        // Wait for either task to complete
        tokio::select! {
            _ = p2p_task => {},
            _ = api_task => {},
        }
    });
}
