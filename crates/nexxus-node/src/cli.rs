//! CLI subcommands (plan phase 6). Hand-rolled arg parsing — no extra deps.
//!
//!   nexxusd serve [store-path]        — daemon (default subcommand)
//!   nexxusd init [--mnemonic "..."] [store-path]
//!   nexxusd id [store-path]
//!   nexxusd status | peers | peer add <IP:PORT>
//!   nexxusd upload <file> | download <root-hex> <out>
//!   nexxusd test-por | test-interhost <IP:PORT>
//!   nexxusd logs [-n N] | benchmark

use std::env;
use std::path::PathBuf;
use std::process;
use std::time::Instant;

use futures_util::{SinkExt, StreamExt};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};

pub fn default_store() -> PathBuf {
    let home = env::var("HOME").unwrap_or_else(|_| ".".to_string());
    PathBuf::from(home).join(".nexxus").join("store.redb")
}

fn api_addr() -> String {
    env::var("NEXXUS_API_ADDR").unwrap_or_else(|_| "127.0.0.1:4010".to_string())
}

/// One JSON-RPC call over WebSocket to the local daemon.
pub async fn ws_call(method: &str, params: Value) -> Result<Value, String> {
    let url = format!("ws://{}", api_addr());
    let (ws, _resp) = tokio_tungstenite::connect_async(&url)
        .await
        .map_err(|e| format!("connect {url}: {e} (is `nexxusd serve` running?)"))?;
    let (mut write, mut read) = ws.split();
    let req = serde_json::to_string(&json!({
        "jsonrpc": "2.0", "id": 1, "method": method, "params": params,
    }))
    .unwrap();
    write
        .send(tokio_tungstenite::tungstenite::Message::Text(req))
        .await
        .map_err(|e| format!("send: {e}"))?;
    while let Some(msg) = read.next().await {
        if let Ok(tokio_tungstenite::tungstenite::Message::Text(t)) = msg {
            let v: Value = serde_json::from_str(&t).map_err(|e| format!("bad json: {e}"))?;
            if let Some(err) = v.get("error") {
                if !err.is_null() {
                    return Err(err.to_string());
                }
            }
            return Ok(v.get("result").cloned().unwrap_or(Value::Null));
        }
    }
    Err("connection closed before response".to_string())
}

fn print_result(r: Result<Value, String>) -> i32 {
    match r {
        Ok(v) => {
            println!("{}", serde_json::to_string_pretty(&v).unwrap());
            0
        }
        Err(e) => fail(&e),
    }
}

fn fail(msg: &str) -> i32 {
    eprintln!("error: {msg}");
    1
}

/// Entry point for CLI subcommands. Builds its own tokio runtime.
pub fn run(args: Vec<String>) {
    let rt = tokio::runtime::Runtime::new().expect("tokio runtime");
    let code = rt.block_on(async_main(args));
    process::exit(code);
}

async fn async_main(args: Vec<String>) -> i32 {
    let cmd = args[0].clone();
    let rest: Vec<String> = args[1..].to_vec();
    match cmd.as_str() {
        "init" => cmd_init(&rest),
        "id" => cmd_id(&rest).await,
        "status" => print_result(ws_call("node_status", json!({})).await),
        "peers" => print_result(ws_call("node_peers", json!({})).await),
        "peer" => match rest.first().map(|s| s.as_str()) {
            Some("add") => match rest.get(1) {
                Some(addr) => print_result(ws_call("node_connect", json!({ "addr": addr })).await),
                None => {
                    eprintln!("usage: nexxusd peer add <IP:PORT>");
                    2
                }
            },
            Some("dial-onion") => match rest.get(1) {
                Some(addr) => {
                    print_result(ws_call("node_dial_onion", json!({ "addr": addr })).await)
                }
                None => {
                    eprintln!("usage: nexxusd peer dial-onion <xxxx.onion:PORT>");
                    2
                }
            },
            _ => {
                eprintln!("usage: nexxusd peer add <IP:PORT> | nexxusd peer dial-onion <xxxx.onion:PORT>");
                2
            }
        },
        "upload" => match rest.first() {
            Some(f) => {
                let abs = std::fs::canonicalize(f).unwrap_or_else(|_| PathBuf::from(f));
                print_result(ws_call("node_upload", json!({ "path": abs.display().to_string() })).await)
            }
            None => {
                eprintln!("usage: nexxusd upload <file>");
                2
            }
        },
        "download" => match (rest.first(), rest.get(1)) {
            (Some(root), Some(out)) => {
                print_result(ws_call("node_download", json!({ "root": root, "out": out })).await)
            }
            _ => {
                eprintln!("usage: nexxusd download <root-hex> <out-file>");
                2
            }
        },
        "test-por" => print_result(ws_call("node_por", json!({})).await),
        "test-interhost" => match rest.first() {
            Some(addr) => {
                print_result(ws_call("node_test_interhost", json!({ "addr": addr })).await)
            }
            None => {
                eprintln!("usage: nexxusd test-interhost <IP:PORT>");
                2
            }
        },
        "logs" => cmd_logs(&rest),
        "benchmark" => cmd_benchmark(),
        other => {
            eprintln!("unknown command: {other}");
            2
        }
    }
}

fn open_store(rest: &[String]) -> Result<(PathBuf, crate::storage::ChunkStore), String> {
    let path = rest
        .iter()
        .find(|a| !a.starts_with('-'))
        .map(PathBuf::from)
        .unwrap_or_else(default_store);
    if let Some(p) = path.parent() {
        let _ = std::fs::create_dir_all(p);
    }
    let db = crate::storage::ChunkStore::open(&path).map_err(|e| e.to_string())?;
    Ok((path, db))
}

fn cmd_init(rest: &[String]) -> i32 {
    let mut mnemonic: Option<String> = None;
    let mut positional: Vec<String> = Vec::new();
    let mut i = 0;
    while i < rest.len() {
        let a = &rest[i];
        if a == "--mnemonic" {
            mnemonic = rest.get(i + 1).cloned();
            i += 2;
        } else if let Some(v) = a.strip_prefix("--mnemonic=") {
            mnemonic = Some(v.to_string());
            i += 1;
        } else if !a.starts_with('-') {
            positional.push(a.clone());
            i += 1;
        } else {
            i += 1;
        }
    }
    let (path, db) = match open_store(&positional) {
        Ok(x) => x,
        Err(e) => return fail(&e),
    };
    match crate::identity_store::init_identity(&db, mnemonic.as_deref()) {
        Ok((iden, created)) => {
            println!(
                "{}",
                serde_json::to_string_pretty(&json!({
                    "store": path.display().to_string(),
                    "node_id": hex::encode(iden.node_id.0),
                    "ed25519_pub": hex::encode(iden.identity.verifying_key.to_bytes()),
                    "x25519_pub": hex::encode(crate::identity_store::x25519_pub(&iden.x25519_secret)),
                    "mnemonic": created,
                }))
                .unwrap()
            );
            if created.is_some() {
                eprintln!("note: the mnemonic is shown once — back it up; it lives in the redb meta table");
            }
            0
        }
        Err(e) => fail(&e.to_string()),
    }
}

async fn cmd_id(rest: &[String]) -> i32 {
    let path = rest
        .iter()
        .find(|a| !a.starts_with('-'))
        .map(PathBuf::from)
        .unwrap_or_else(default_store);
    match crate::storage::ChunkStore::open(&path) {
        Ok(db) => match crate::identity_store::load_or_create_identity(&db) {
            Ok((iden, _)) => {
                println!(
                    "{}",
                    serde_json::to_string_pretty(&json!({
                        "store": path.display().to_string(),
                        "source": "store",
                        "node_id": hex::encode(iden.node_id.0),
                        "ed25519_pub": hex::encode(iden.identity.verifying_key.to_bytes()),
                        "x25519_pub": hex::encode(crate::identity_store::x25519_pub(&iden.x25519_secret)),
                    }))
                    .unwrap()
                );
                0
            }
            Err(e) => fail(&e.to_string()),
        },
        Err(e) => {
            // Store is locked (a daemon holds it) — ask the running daemon.
            match ws_call("node_status", json!({})).await {
                Ok(s) => {
                    println!(
                        "{}",
                        serde_json::to_string_pretty(&json!({
                            "store": path.display().to_string(),
                            "source": "daemon (store locked: daemon is running)",
                            "note": e.to_string(),
                            "node_id": s["node_id"],
                            "ed25519_pub": s["ed25519_pub"],
                            "x25519_pub": s["x25519_pub"],
                        }))
                        .unwrap()
                    );
                    0
                }
                Err(e2) => fail(&format!(
                    "cannot open {}: {e}; daemon not reachable either: {e2}",
                    path.display()
                )),
            }
        }
    }
}

fn cmd_logs(rest: &[String]) -> i32 {
    let mut n = 50usize;
    let mut i = 0;
    while i < rest.len() {
        if rest[i] == "-n" {
            if let Some(v) = rest.get(i + 1) {
                n = v.parse().unwrap_or(n);
            }
            i += 2;
        } else if let Some(v) = rest[i].strip_prefix("-n") {
            n = v.parse().unwrap_or(n);
            i += 1;
        } else {
            i += 1;
        }
    }
    let log = env::var("NEXXUS_LOG")
        .ok()
        .map(PathBuf::from)
        .unwrap_or_else(|| {
            let home = env::var("HOME").unwrap_or_else(|_| ".".to_string());
            PathBuf::from(home).join(".nexxus").join("nexxusd.log")
        });
    match std::fs::read_to_string(&log) {
        Ok(content) => {
            let lines: Vec<&str> = content.lines().collect();
            let start = lines.len().saturating_sub(n);
            for l in &lines[start..] {
                println!("{l}");
            }
            0
        }
        Err(_) => fail(&format!(
            "no log file at {} — run the daemon with output redirected, e.g. `nexxusd serve 2>>{}`",
            log.display(),
            log.display()
        )),
    }
}

fn cmd_benchmark() -> i32 {
    let dir = default_store()
        .parent()
        .map(|p| p.to_path_buf())
        .unwrap_or_else(|| PathBuf::from("."));
    let _ = std::fs::create_dir_all(&dir);
    let path = dir.join(".nexxus-bench.tmp");
    let mb: usize = 64;
    let block = vec![0xABu8; 1024 * 1024];
    let t = Instant::now();
    {
        use std::io::Write;
        let mut f = match std::fs::File::create(&path) {
            Ok(f) => f,
            Err(e) => return fail(&e.to_string()),
        };
        for _ in 0..mb {
            if let Err(e) = f.write_all(&block) {
                return fail(&e.to_string());
            }
        }
        if let Err(e) = f.sync_all() {
            return fail(&e.to_string());
        }
    }
    let write_s = t.elapsed().as_secs_f64();
    let t = Instant::now();
    if let Err(e) = std::fs::read(&path) {
        return fail(&e.to_string());
    }
    let read_s = t.elapsed().as_secs_f64();
    let _ = std::fs::remove_file(&path);
    let leaves: Vec<[u8; 32]> = (0..4096u32)
        .map(|i| {
            let mut h = Sha256::new();
            h.update(i.to_be_bytes());
            h.finalize().into()
        })
        .collect();
    let t = Instant::now();
    let root = nexxus_core::merkle::merkle_root(&leaves);
    let merkle_ms = t.elapsed().as_millis() as u64;
    let total = (mb * 1024 * 1024) as f64;
    println!(
        "{}",
        serde_json::to_string_pretty(&json!({
            "bytes": mb * 1024 * 1024,
            "write_mbps": (total / write_s / 1e6) as u64,
            "read_mbps": (total / read_s / 1e6) as u64,
            "merkle_4096_leaves_ms": merkle_ms,
            "merkle_root": hex::encode(root),
        }))
        .unwrap()
    );
    0
}
