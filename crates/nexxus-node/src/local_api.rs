//! Local WebSocket API for the NeXXus desktop monitor application.
//! Listens on 127.0.0.1:4010 (configurable via NEXXUS_API_ADDR) and speaks
//! JSON-RPC 2.0 over WebSocket so `nexxus-desktop` can query node status,
//! peers, chunks, SMP history, Epoch finalize, and Tor state.
//
//! Протокол:
//!   - Клиент подключается по ws://127.0.0.1:4010
//!   - Отправляет JSON-RPC 2.0 запрос в виде текстового WebSocket сообщения
//!   - Сервер отвечает JSON-RPC 2.0 ответом и закрывает соединение
//!   - Каждый запрос = новое соединение (простая модель для MVP)

use crate::identity_store::{identity_status, import_mnemonic, read_mnemonic};
use crate::net::network::{InboundSmp, P2pNetwork};
use crate::storage::ChunkStore;
use curve25519_dalek::MontgomeryPoint;
use nexxus_core::{
    error::NexxusError,
    types::NodeId,
    wire::payloads::SmpEnvelope,
};
use futures_util::{SinkExt, StreamExt};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::net::SocketAddr;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::net::TcpListener;
use tokio::sync::{mpsc, Mutex};
use tokio_tungstenite::accept_async;
use tokio_tungstenite::tungstenite::Message;

/// Default bind address for the local API WebSocket server.
pub const DEFAULT_API_ADDR: &str = "127.0.0.1:4010";

/// Information about a connected peer (for the local API).
#[derive(Debug, Clone, Serialize)]
pub struct ConnectedPeerInfo {
    pub node_id: String,
    pub addr: String,
    pub direction: String, // "inbound" or "outbound"
    pub connected_at: u64, // unix seconds
}

/// Information about an SMP message (for the local API).
#[derive(Debug, Clone, Serialize)]
pub struct SmpMessageInfo {
    pub id: String,
    pub direction: String, // "sent" or "received"
    pub sender_node_id: String, // hex; empty for "sent"
    pub recipient_node_id: String,
    pub payload_size: usize,
    pub status: String, // "sent", "delivered", "failed", "pending"
    pub timestamp: u64,
}

/// Epoch finalize status (for the local API).
#[derive(Debug, Clone, Serialize)]
pub struct EpochInfo {
    pub epoch_number: u64,
    pub merkle_root: String,
    pub total_bytes: u64,
    pub signature_count: usize,
    pub threshold: usize,
    pub quorum_met: bool,
}

/// Node status (for the local API).
#[derive(Debug, Clone, Serialize)]
pub struct NodeStatus {
    pub node_id: String,
    pub version: String,
    pub listen_addr: String,
    pub bound_addr: Option<String>,
    pub uptime_ms: u128,
    pub peer_count: usize,
    pub tor_enabled: bool,
    pub paused: bool,
    pub x25519_pub: String,
    pub ed25519_pub: String,
}

/// Chunk store stats (for the local API).
#[derive(Debug, Clone, Serialize)]
pub struct ChunkStats {
    pub total_chunks: usize,
    pub chunk_size_bytes: usize,
    pub used_bytes: u64,
    pub free_gb: u64,
}

/// Tor status (for the local API).
#[derive(Debug, Clone, Serialize)]
pub struct TorStatus {
    pub enabled: bool,
    pub onion_address: Option<String>,
    pub connected: bool,
}

/// JSON-RPC 2.0 request.
#[derive(Debug, Deserialize)]
struct JsonRpcRequest {
    jsonrpc: Option<String>,
    method: String,
    params: Option<Value>,
    id: Option<Value>,
}

/// JSON-RPC 2.0 response.
#[derive(Debug, Serialize)]
struct JsonRpcResponse {
    jsonrpc: String,
    id: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<JsonRpcError>,
}

/// JSON-RPC 2.0 error.
#[derive(Debug, Serialize)]
struct JsonRpcError {
    code: i32,
    message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    data: Option<Value>,
}

const ERR_INVALID_REQUEST: i32 = -32600;
const ERR_METHOD_NOT_FOUND: i32 = -32601;
const ERR_INTERNAL_ERROR: i32 = -32603;

fn error_response(id: Option<Value>, code: i32, message: String) -> JsonRpcResponse {
    JsonRpcResponse {
        jsonrpc: "2.0".into(),
        id,
        result: None,
        error: Some(JsonRpcError {
            code,
            message,
            data: None,
        }),
    }
}

fn ok_response(id: Option<Value>, result: Value) -> JsonRpcResponse {
    JsonRpcResponse {
        jsonrpc: "2.0".into(),
        id,
        result: Some(result),
        error: None,
    }
}

/// Local API server state, shared with P2pNetwork.
///
/// Все Mutex-поля защищают разделяемое состояние между задачами WebSocket.
pub struct LocalApi {
    /// Ссылка на P2P сеть (для node_id, bound_addr, отправки SMP).
    network: Arc<P2pNetwork>,
    /// Ссылка на хранилище чанков (для статистики).
    store: Arc<ChunkStore>,
    /// Время запуска daemon (для расчёта uptime).
    start_time: SystemTime,
    /// Подключённые пиры: адрес -> информация о пире.
    connected_peers: Arc<Mutex<HashMap<SocketAddr, ConnectedPeerInfo>>>,
    /// История SMP сообщений (последние 500 записей).
    smp_history: Arc<Mutex<Vec<SmpMessageInfo>>>,
    /// Inbound SMP channel: sender side goes to P2pNetwork, receiver is
    /// drained into smp_history by a task spawned in run().
    smp_inbox_tx: mpsc::UnboundedSender<InboundSmp>,
    smp_inbox_rx: Arc<Mutex<Option<mpsc::UnboundedReceiver<InboundSmp>>>>,
    /// Статус финализации эпохи (кворум, merkle_root и т.д.).
    epoch_info: Arc<Mutex<EpochInfo>>,
    /// Статус Tor (включен, onion адрес, подключён).
    tor_status: Arc<Mutex<TorStatus>>,
    /// Живая Tor-сессия (feature `tor`) — для dial_onion через чужие .onion.
    #[cfg(feature = "tor")]
    tor_session: Arc<Mutex<Option<Arc<crate::tor::TorSession>>>>,
    /// Токен доступа к API (api_auth). None = fail-closed: кроме ping ничего не доступно.
    api_token: std::sync::Mutex<Option<String>>,
    /// Panic PIN менеджер (Phase A3): состояние в panic.state рядом со store.
    panic: Arc<std::sync::Mutex<crate::panic::PanicManager>>,
    /// Выставляется при duress-PIN: после отправки ответа — wipe стора + выход.
    duress_wipe: std::sync::atomic::AtomicBool,
}

/// JSON-RPC error code: не пройдена аутентификация.
pub const ERR_UNAUTHORIZED: i32 = -32001;

/// Гейт аутентификации: вызывается до диспетчеризации метода.
///
/// Возвращает `Some((response, close_after))`, если запрос обработан
/// самим гейтом (ping / auth / отказ), и `None`, если надо диспетчить
/// обычным образом (соединение уже аутентифицировано).
///
/// Fail-closed: без настроенного токена (`expected == None`) доступен
/// только `ping`.
fn auth_gate(
    expected: Option<&str>,
    req: &JsonRpcRequest,
    authenticated: &mut bool,
) -> Option<(JsonRpcResponse, bool)> {
    if *authenticated {
        return None;
    }
    match req.method.as_str() {
        "ping" => Some((
            ok_response(req.id.clone(), serde_json::json!({"pong": true})),
            false, // соединение остаётся открытым
        )),
        "auth" => {
            let supplied = req
                .params
                .as_ref()
                .and_then(|p| p.get("token"))
                .and_then(|t| t.as_str())
                .unwrap_or("");
            match expected {
                Some(expected) if !supplied.is_empty() && supplied == expected => {
                    *authenticated = true;
                    Some((
                        ok_response(req.id.clone(), serde_json::json!({"authenticated": true})),
                        false, // после успешного auth ждём настоящий запрос на этом же соединении
                    ))
                }
                _ => Some((
                    error_response(req.id.clone(), ERR_UNAUTHORIZED, "invalid or missing token".into()),
                    true, // закрываем соединение
                )),
            }
        }
        _ => Some((
            error_response(
                req.id.clone(),
                ERR_UNAUTHORIZED,
                format!("method '{}' requires auth", req.method),
            ),
            true,
        )),
    }
}

impl LocalApi {
    pub fn new(network: Arc<P2pNetwork>, store: Arc<ChunkStore>) -> Self {
        let (smp_inbox_tx, smp_inbox_rx) = mpsc::unbounded_channel();
        let panic_path = crate::panic::PanicManager::default_path(store.path());
        Self {
            network,
            store,
            start_time: SystemTime::now(),
            connected_peers: Arc::new(Mutex::new(HashMap::new())),
            smp_history: Arc::new(Mutex::new(Vec::new())),
            smp_inbox_tx,
            smp_inbox_rx: Arc::new(Mutex::new(Some(smp_inbox_rx))),
            api_token: std::sync::Mutex::new(None),
            panic: Arc::new(std::sync::Mutex::new(
                crate::panic::PanicManager::load(panic_path)
                .unwrap_or_else(|_| {
                    // Невалидный panic.state — fail-closed: панику нельзя обойти
                    // молча. Создаём "не armed" менеджер и пишем ошибку в лог.
                    eprintln!("nexxusd: WARNING: panic.state unreadable, panic disabled");
                    crate::panic::PanicManager::load(
                        std::env::temp_dir().join("nexxus-panic-unreadable.state"),
                    )
                    .expect("temp panic state must load")
                }),
            )),
            duress_wipe: std::sync::atomic::AtomicBool::new(false),
            epoch_info: Arc::new(Mutex::new(EpochInfo {
                epoch_number: 0,
                merkle_root: hex::encode([0u8; 32]),
                total_bytes: 0,
                signature_count: 0,
                threshold: 0,
                quorum_met: false,
            })),
            tor_status: Arc::new(Mutex::new(TorStatus {
                enabled: false,
                onion_address: None,
                connected: false,
            })),
            #[cfg(feature = "tor")]
            tor_session: Arc::new(Mutex::new(None)),
        }
    }

    /// Register a connected peer (called from handle_connection).
    pub async fn register_peer(&self, addr: SocketAddr, node_id: Option<NodeId>, direction: &str) {
        let mut peers = self.connected_peers.lock().await;
        peers.insert(
            addr,
            ConnectedPeerInfo {
                node_id: node_id
                    .map(|n| hex::encode(n.0))
                    .unwrap_or_else(|| "unknown".into()),
                addr: addr.to_string(),
                direction: direction.into(),
                connected_at: SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .map(|d| d.as_secs())
                    .unwrap_or(0),
            },
        );
    }

    /// Unregister a disconnected peer.
    pub async fn unregister_peer(&self, addr: &SocketAddr) {
        self.connected_peers.lock().await.remove(addr);
    }

    /// Record an SMP message in history.
    pub async fn record_smp(&self, direction: &str, recipient: &str, payload_size: usize, status: &str) {
        self.record_smp_full(direction, "", recipient, payload_size, status).await;
    }

    /// Record an inbound (delivered) SMP message in history.
    pub async fn record_smp_inbound(&self, sender: &str, recipient: &str, payload_size: usize, status: &str) {
        self.record_smp_full("received", sender, recipient, payload_size, status).await;
    }

    async fn record_smp_full(&self, direction: &str, sender: &str, recipient: &str, payload_size: usize, status: &str) {
        let mut history = self.smp_history.lock().await;
        let id = format!("smp-{}", history.len() + 1);
        history.push(SmpMessageInfo {
            id,
            direction: direction.into(),
            sender_node_id: sender.into(),
            recipient_node_id: recipient.into(),
            payload_size,
            status: status.into(),
            timestamp: SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0),
        });
        // keep only last 500 entries
        if history.len() > 500 {
            let drain_count = history.len() - 500;
            history.drain(0..drain_count);
        }
    }

    /// Update epoch finalize status.
    pub async fn set_epoch_info(&self, info: EpochInfo) {
        *self.epoch_info.lock().await = info;
    }

    /// Устанавливает токен доступа к API (из api_auth::load_or_create_token).
    pub fn set_api_token(&self, token: String) {
        *self.api_token.lock().unwrap() = Some(token);
    }

    #[cfg(feature = "tor")]
    pub async fn set_tor_status(&self, status: TorStatus) {
        *self.tor_status.lock().await = status;
    }

    /// Attach the live Tor session so `node_dial_onion` can reach .onion peers.
    #[cfg(feature = "tor")]
    pub async fn set_tor_session(&self, ts: Arc<crate::tor::TorSession>) {
        *self.tor_session.lock().await = Some(ts);
    }

    /// Handle a single JSON-RPC request and return a response value.
    async fn handle_request(&self, req: JsonRpcRequest) -> JsonRpcResponse {
        let id = req.id.clone();
        // JSON-RPC 2.0: если поле jsonrpc присутствует, оно обязано быть "2.0".
        if let Some(v) = &req.jsonrpc {
            if v != "2.0" {
                return error_response(
                    id,
                    ERR_INVALID_REQUEST,
                    format!("unsupported jsonrpc version: {v}"),
                );
            }
        }
        let result = match req.method.as_str() {
            "ping" => Ok(serde_json::json!({"pong": true})),
            "node_status" => self.handle_node_status().await,
            "node_peers" => self.handle_node_peers().await,
            "node_chunks" => self.handle_node_chunks().await,
            "node_smp" => self.handle_node_smp().await,
            "node_epoch" => self.handle_node_epoch().await,
            "node_tor" => self.handle_node_tor().await,
            "send_smp_envelope" => self.handle_send_smp_envelope(req.params).await,
            "node_pause" => self.handle_node_pause().await,
            "node_resume" => self.handle_node_resume().await,
            "node_connect" => self.handle_node_connect(req.params).await,
            "node_dial_onion" => self.handle_node_dial_onion(req.params).await,
            "node_upload" => self.handle_node_upload(req.params).await,
            "node_download" => self.handle_node_download(req.params).await,
            "node_por" => self.handle_node_por().await,
            "node_test_interhost" => self.handle_node_test_interhost(req.params).await,
            "panic_status" => self.handle_panic_status(),
            "panic_arm" => self.handle_panic_arm(req.params),
            "panic_enter" => self.handle_panic_enter(req.params),
            "node_identity_status" => self.handle_node_identity_status(),
            "node_identity_export" => self.handle_node_identity_export(req.params),
            "node_identity_import" => self.handle_node_identity_import(req.params),
            "node_seed_vault_status" => self.handle_seed_vault_status(),
            "node_seed_backup" => self.handle_seed_backup(req.params),
            "node_seed_restore" => self.handle_seed_restore(req.params),
            "node_backup" => self.handle_node_backup(),
            "node_backup_list" => self.handle_node_backup_list(),
            "node_backup_verify" => self.handle_node_backup_verify(req.params),
            "node_backup_restore" => self.handle_node_backup_restore(req.params),
            "node_doctor" => self.handle_node_doctor(),
            "node_econ" => self.handle_node_econ(),
            _ => return error_response(id, ERR_METHOD_NOT_FOUND, format!("method '{}' not found", req.method)),
        };
        match result {
            Ok(v) => ok_response(id, v),
            Err(e) => error_response(id, ERR_INTERNAL_ERROR, e.to_string()),
        }
    }

    /// Identity status for the monitor UI: is a BIP-39 identity persisted,
    /// how many words it has, and the resulting node_id.
    fn handle_node_identity_status(&self) -> Result<Value, NexxusError> {
        let (initialized, word_count) = identity_status(&self.store)?;
        Ok(serde_json::json!({
            "initialized": initialized,
            "word_count": word_count,
            "node_id": hex::encode(self.network.node_id().0),
        }))
    }

    /// One-time export of the mnemonic. Requires params.confirm == true.
    /// The mnemonic is returned in the RPC response only — it is never
    /// written to logs by this handler.
    fn handle_node_identity_export(&self, params: Option<Value>) -> Result<Value, NexxusError> {
        let confirm = params
            .as_ref()
            .and_then(|p| p.get("confirm"))
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        if !confirm {
            return Err(NexxusError::Vault(
                "param 'confirm' must be true to export the mnemonic".into(),
            ));
        }
        match read_mnemonic(&self.store)? {
            Some(phrase) => Ok(serde_json::json!({
                "mnemonic": phrase,
                "word_count": phrase.split_whitespace().count(),
            })),
            None => Err(NexxusError::Io("identity not initialized".into())),
        }
    }

    /// Import a mnemonic. Refuses on a store already initialized with a
    /// different seed (store key is derived from the seed). On a live daemon
    /// the identity is already loaded, so a matching phrase returns "already".
    fn handle_node_identity_import(&self, params: Option<Value>) -> Result<Value, NexxusError> {
        let phrase = params
            .as_ref()
            .and_then(|p| p.get("mnemonic"))
            .and_then(|v| v.as_str())
            .ok_or_else(|| NexxusError::Vault("param 'mnemonic' required".into()))?;
        let (node_id, status) = import_mnemonic(&self.store, phrase)?;
        Ok(serde_json::json!({
            "status": status,
            "node_id": hex::encode(node_id.0),
        }))
    }

    /// Seed vault (encrypted BIP39 backup) metadata — no secrets, no decryption.
    fn handle_seed_vault_status(&self) -> Result<Value, NexxusError> {
        match crate::seed_vault::seed_vault_status(&self.store)? {
            Some(st) => Ok(serde_json::json!({
                "exists": true,
                "path": st.path.to_string_lossy(),
                "created_at": st.created_at,
                "has_duress_pin": st.has_duress_pin,
                "kdf_rounds": st.kdf_rounds,
            })),
            None => Ok(serde_json::json!({"exists": false})),
        }
    }

    /// Create/overwrite the encrypted seed vault. Params: pin (required, >=4),
    /// duress_pin (optional). The mnemonic never leaves the process in plaintext
    /// except into the encrypted vault file (0600).
    fn handle_seed_backup(&self, params: Option<Value>) -> Result<Value, NexxusError> {
        let pin = params
            .as_ref()
            .and_then(|p| p.get("pin"))
            .and_then(|v| v.as_str())
            .ok_or_else(|| NexxusError::Vault("param 'pin' required".into()))?;
        let duress = params
            .as_ref()
            .and_then(|p| p.get("duress_pin"))
            .and_then(|v| v.as_str());
        let path = crate::seed_vault::backup_seed(&self.store, pin, duress)?;
        Ok(serde_json::json!({
            "ok": true,
            "path": path.to_string_lossy(),
        }))
    }

    /// Restore the seed from the vault with a PIN. Returns one of:
    /// "imported" | "already" | "duress" | "wrong_pin" (+ node_id when applicable).
    /// On "duress" the real seed is NOT imported — the monitor must alert, not celebrate.
    fn handle_seed_restore(&self, params: Option<Value>) -> Result<Value, NexxusError> {
        let pin = params
            .as_ref()
            .and_then(|p| p.get("pin"))
            .and_then(|v| v.as_str())
            .ok_or_else(|| NexxusError::Vault("param 'pin' required".into()))?;
        use crate::seed_vault::RestoreOutcome;
        let r = match crate::seed_vault::restore_seed(&self.store, pin)? {
            RestoreOutcome::Imported(id) => serde_json::json!({"status": "imported", "node_id": hex::encode(id.0)}),
            RestoreOutcome::Already(id) => serde_json::json!({"status": "already", "node_id": hex::encode(id.0)}),
            RestoreOutcome::Duress => serde_json::json!({"status": "duress"}),
            RestoreOutcome::WrongPin => serde_json::json!({"status": "wrong_pin"}),
        };
        Ok(r)
    }

    /// Store backup (R3): file-level copy + manifest. Safe on a running node.
    fn handle_node_backup(&self) -> Result<Value, NexxusError> {
        let m = crate::backup::backup_store(&self.store)?;
        serde_json::to_value(m).map_err(|e| NexxusError::Io(e.to_string()))
    }

    fn handle_node_backup_list(&self) -> Result<Value, NexxusError> {
        let list = crate::backup::list_backups(&self.store)?;
        serde_json::to_value(list).map_err(|e| NexxusError::Io(e.to_string()))
    }

    fn handle_node_backup_verify(&self, params: Option<Value>) -> Result<Value, NexxusError> {
        let name = params
            .as_ref()
            .and_then(|p| p.get("name"))
            .and_then(|v| v.as_str())
            .ok_or_else(|| NexxusError::Io("param 'name' required".into()))?;
        let (m, ok, detail) = crate::backup::verify_backup(&self.store, name)?;
        Ok(serde_json::json!({
            "name": m.name,
            "ok": ok,
            "detail": detail,
            "sha256": m.sha256,
            "chunk_count": m.chunk_count,
            "created_at": m.created_at,
        }))
    }

    /// Restore = verify + write a *.restore-candidate.redb next to the live
    /// store. The live store is never overwritten via API; swap happens via
    /// `nexxusd restore <name>` with the daemon stopped.
    fn handle_node_backup_restore(&self, params: Option<Value>) -> Result<Value, NexxusError> {
        let name = params
            .as_ref()
            .and_then(|p| p.get("name"))
            .and_then(|v| v.as_str())
            .ok_or_else(|| NexxusError::Io("param 'name' required".into()))?;
        let confirm = params
            .as_ref()
            .and_then(|p| p.get("confirm"))
            .and_then(|v| v.as_bool())
            .unwrap_or(false);
        if !confirm {
            return Err(NexxusError::Vault(
                "param 'confirm' must be true to stage a restore candidate".into(),
            ));
        }
        let cand = crate::backup::restore_candidate(&self.store, name)?;
        Ok(serde_json::json!({
            "status": "staged",
            "candidate": cand.to_string_lossy(),
            "note": "live store untouched; swap with `nexxusd restore <name>` while stopped",
        }))
    }

    /// Health report (R3 doctor) as JSON.
    fn handle_node_doctor(&self) -> Result<Value, NexxusError> {
        let r = crate::backup::doctor(&self.store);
        serde_json::to_value(r).map_err(|e| NexxusError::Io(e.to_string()))
    }

    /// Economics panel (R4): storage GB, section split, daily reward/cost,
    /// anti-loop invariant, 56-day vesting progress, health.
    fn handle_node_econ(&self) -> Result<Value, NexxusError> {
        use nexxus_econ::degradation::{health_from_offline, Health};
        use nexxus_econ::sections::{
            anti_loop_invariant_holds, daily_storer_reward, daily_subscription_cost,
            split_into_sections,
        };
        use nexxus_econ::vesting::VestingSchedule;
        use nexxus_econ::{VESTING_LOCK_DAYS, DAILY_NEXX_RATE_PER_GB, SUBSCRIPTION_DAILY_COST_PER_GB};

        const META_VESTING_START: &str = "econ_vesting_start_ts";
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);
        // Vesting start: зафиксировать при первом вызове.
        let start_ts = match self.store.get_meta(META_VESTING_START)? {
            Some(b) => String::from_utf8_lossy(&b).parse::<u64>().unwrap_or(now),
            None => {
                self.store.put_meta(META_VESTING_START, now.to_string().as_bytes())?;
                now
            }
        };
        let hashes = self.store.list_chunk_hashes()?;
        let used_bytes: u64 = hashes
            .iter()
            .filter_map(|h| self.store.get_chunk(h).ok().flatten())
            .map(|d| d.len() as u64)
            .sum();
        let free_gb = fs2::available_space(self.store.path())
            .map(|b| b / (1u64 << 30))
            .unwrap_or(0);
        let used_gb = used_bytes / 1_000_000_000;
        let split = split_into_sections(free_gb);
        let daily_reward = daily_storer_reward(used_gb);
        let daily_cost = daily_subscription_cost(used_gb);
        let days_elapsed = now.saturating_sub(start_ts) / 86_400;
        let mut vest = VestingSchedule::new(nexxus_core::types::Money(daily_reward.0 * VESTING_LOCK_DAYS as i64));
        vest.advance(days_elapsed.min(VESTING_LOCK_DAYS));
        let health = health_from_offline(0); // нода online, пока API отвечает
        let health_str = match health {
            Health::Online => "online",
            Health::RewardsFrozen => "rewards_frozen",
            Health::Warning14d => "warning_14d",
            Health::Degraded28d => "degraded_28d",
        };
        Ok(serde_json::json!({
            "used_gb": used_gb,
            "free_gb": free_gb,
            "sections": {
                "sections_16gb": split.sections_16gb,
                "remainder_gb": split.remainder_gb,
                "vault_quota_gb": split.vault_quota_gb,
            },
            "daily": {
                "reward_per_gb_micro": DAILY_NEXX_RATE_PER_GB,
                "cost_per_gb_micro": SUBSCRIPTION_DAILY_COST_PER_GB,
                "reward_total_micro": daily_reward.0,
                "cost_total_micro": daily_cost.0,
                "anti_loop_ok": anti_loop_invariant_holds(),
            },
            "vesting": {
                "lock_days": VESTING_LOCK_DAYS,
                "start_ts": start_ts,
                "days_elapsed": days_elapsed.min(VESTING_LOCK_DAYS),
                "total_micro": vest.total.0,
                "vested_micro": vest.vested().0,
                "unvested_micro": vest.unvested().0,
                "fully_vested": vest.is_fully_vested(),
            },
            "health": health_str,
        }))
    }

    fn handle_panic_status(&self) -> Result<Value, NexxusError> {
        let st = self.panic.lock().unwrap().status();
        Ok(serde_json::json!({
            "armed": st.armed,
            "fail_count": st.fail_count,
            "cooldown_remaining_secs": st.cooldown_remaining_secs,
        }))
    }

    fn handle_panic_arm(&self, params: Option<Value>) -> Result<Value, NexxusError> {
        let pin = params
            .as_ref()
            .and_then(|p| p.get("pin"))
            .and_then(|v| v.as_str())
            .ok_or_else(|| NexxusError::Vault("param 'pin' required".into()))?;
        let duress = params
            .as_ref()
            .and_then(|p| p.get("duress_pin"))
            .and_then(|v| v.as_str());
        self.panic.lock().unwrap().arm(pin, duress)?;
        Ok(serde_json::json!({"armed": true}))
    }

    fn handle_panic_enter(&self, params: Option<Value>) -> Result<Value, NexxusError> {
        use crate::panic::EnterOutcome;
        let pin = params
            .as_ref()
            .and_then(|p| p.get("pin"))
            .and_then(|v| v.as_str())
            .ok_or_else(|| NexxusError::Vault("param 'pin' required".into()))?;
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_secs())
            .unwrap_or(0);
        match self.panic.lock().unwrap().enter(pin, now)? {
            EnterOutcome::Ok => Ok(serde_json::json!({"ok": true})),
            EnterOutcome::Duress => {
                // Ложный успех: снаружи неотличимо от Ok. После отправки
                // ответа handle_ws затрёт стор и завершит процесс.
                self.duress_wipe
                    .store(true, std::sync::atomic::Ordering::SeqCst);
                Ok(serde_json::json!({"ok": true}))
            }
            EnterOutcome::Wrong { cooldown_secs } => {
                Ok(serde_json::json!({"ok": false, "cooldown_secs": cooldown_secs}))
            }
            EnterOutcome::Cooldown { remaining_secs } => {
                Ok(serde_json::json!({"ok": false, "cooldown_remaining_secs": remaining_secs}))
            }
        }
    }

    async fn handle_node_status(&self) -> Result<Value, NexxusError> {
        let bound = self.network.bound_addr().await;
        let peers = self.connected_peers.lock().await.len();
        let uptime = self
            .start_time
            .elapsed()
            .map(|d| d.as_millis())
            .unwrap_or(0);
        let tor = self.tor_status.lock().await.clone();
        serde_json::to_value(NodeStatus {
            node_id: hex::encode(self.network.node_id().0),
            version: env!("CARGO_PKG_VERSION").into(),
            listen_addr: self.network.listen_addr_str().to_string(),
            bound_addr: bound.map(|a| a.to_string()),
            uptime_ms: uptime,
            peer_count: peers,
            tor_enabled: tor.enabled,
            paused: self.network.is_paused(),
            x25519_pub: hex::encode(self.network.x25519_pub().0),
            ed25519_pub: hex::encode(self.network.identity_pubkey()),
        }).map_err(|e| NexxusError::Io(e.to_string()))
    }

    async fn handle_node_peers(&self) -> Result<Value, NexxusError> {
        let peers = self.connected_peers.lock().await.clone();
        let mut list: Vec<Value> = peers
            .into_values()
            .map(|p| serde_json::to_value(p).unwrap_or(Value::Null))
            .collect();
        // Merge in routing-table peers (known by address even if not
        // holding a live connection right now).
        for p in self.network.known_peers().await {
            let addr = p.addr.to_string();
            if !list
                .iter()
                .any(|v| v.get("addr").and_then(|a| a.as_str()) == Some(addr.as_str()))
            {
                list.push(serde_json::json!({
                    "node_id": hex::encode(p.node_id.0),
                    "addr": addr,
                    "connected": false,
                }));
            }
        }
        Ok(serde_json::json!({ "peers": list }))
    }

    async fn handle_node_chunks(&self) -> Result<Value, NexxusError> {
        let hashes = self.store.list_chunk_hashes()?;
        let total = hashes.len();
        let used_bytes: u64 = hashes
            .iter()
            .filter_map(|h| self.store.get_chunk(h).ok().flatten())
            .map(|d| d.len() as u64)
            .sum();
        // Реальное свободное место на диске стора (statvfs через fs2).
        let free_gb = fs2::available_space(self.store.path())
            .map(|b| b / (1u64 << 30))
            .unwrap_or(0);
        serde_json::to_value(ChunkStats {
            total_chunks: total,
            chunk_size_bytes: 16_384,
            used_bytes,
            free_gb,
        }).map_err(|e| NexxusError::Io(e.to_string()))
    }

    async fn handle_node_smp(&self) -> Result<Value, NexxusError> {
        let history = self.smp_history.lock().await.clone();
        let list: Vec<Value> = history
            .into_iter()
            .map(|m| serde_json::to_value(m).unwrap_or(Value::Null))
            .collect();
        Ok(serde_json::json!({ "messages": list }))
    }

    async fn handle_node_epoch(&self) -> Result<Value, NexxusError> {
        let info = self.epoch_info.lock().await.clone();
        serde_json::to_value(info).map_err(|e| NexxusError::Io(e.to_string()))
    }

    async fn handle_node_tor(&self) -> Result<Value, NexxusError> {
        #[cfg_attr(not(feature = "tor"), allow(unused_mut))]
        let mut status = self.tor_status.lock().await.clone();
        // Если сессия поднята, но статус ещё без адреса — добираем из самой сессии.
        #[cfg(feature = "tor")]
        if status.onion_address.is_none() {
            if let Some(ts) = self.tor_session.lock().await.as_ref() {
                status.onion_address = ts.our_onion().map(|s| s.to_string());
            }
        }
        serde_json::to_value(status).map_err(|e| NexxusError::Io(e.to_string()))
    }

    async fn handle_send_smp_envelope(&self, params: Option<Value>) -> Result<Value, NexxusError> {
        let params = params.ok_or_else(|| NexxusError::Io("missing params".into()))?;
        let recipient: String = params
            .get("recipient_node_id")
            .and_then(|v| v.as_str())
            .map(|s| s.into())
            .ok_or_else(|| NexxusError::Io("missing recipient_node_id".into()))?;
        let payload: Vec<u8> = params
            .get("payload")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_u64().map(|b| b as u8))
                    .collect()
            })
            .unwrap_or_default();
        let addr: Option<String> = params
            .get("addr")
            .and_then(|v| v.as_str())
            .map(|s| s.into());

        // Parse recipient node id
        let recipient_bytes = hex::decode(&recipient).map_err(|e| NexxusError::Io(e.to_string()))?;
        if recipient_bytes.len() != 32 {
            return Err(NexxusError::Io("recipient_node_id must be 32 bytes hex".into()));
        }
        let recipient_id = NodeId(recipient_bytes.try_into().map_err(|_| {
            NexxusError::Io("recipient_node_id invalid length".into())
        })?);

        // Recipient X25519 pubkey: explicit param, else our own (loopback/self-test)
        let recipient_pub = match params.get("recipient_x25519_pub").and_then(|v| v.as_str()) {
            Some(h) => {
                let bytes = hex::decode(h).map_err(|e| NexxusError::Io(e.to_string()))?;
                let arr: [u8; 32] = bytes.try_into().map_err(|_| {
                    NexxusError::Io("recipient_x25519_pub must be 32 bytes hex".into())
                })?;
                MontgomeryPoint(arr)
            }
            None => self.network.x25519_pub(),
        };

        // Build and seal SMP envelope
        let (ephemeral_pub, env) = SmpEnvelope::seal(
            self.network.node_id().0,
            recipient_id.0,
            &recipient_pub,
            &payload,
        );

        // Send: explicit addr if given, otherwise route via the Kademlia table
        let result = match &addr {
            Some(a) => {
                let peer_addr: SocketAddr = a
                    .parse()
                    .map_err(|e: std::net::AddrParseError| NexxusError::Io(e.to_string()))?;
                self.network.send_smp_envelope(peer_addr, &env).await
            }
            None => self.network.route_smp_envelope(&env).await,
        };

        // Record in history
        self.record_smp(
            "sent",
            &recipient,
            payload.len(),
            if result.is_ok() { "sent" } else { "failed" },
        )
        .await;

        match result {
            Ok(()) => Ok(serde_json::json!({ "status": "sent", "envelope_id": hex::encode(ephemeral_pub) })),
            Err(e) => Err(e),
        }
    }

    async fn handle_node_pause(&self) -> Result<Value, NexxusError> {
        self.network.set_paused(true);
        Ok(serde_json::json!({ "status": "paused", "paused": true }))
    }

    async fn handle_node_resume(&self) -> Result<Value, NexxusError> {
        self.network.set_paused(false);
        Ok(serde_json::json!({ "status": "resumed", "paused": false }))
    }

    async fn handle_node_connect(&self, params: Option<Value>) -> Result<Value, NexxusError> {
        let addr_str = params
            .and_then(|p| p.get("addr").and_then(|v| v.as_str()).map(|s| s.to_string()))
            .ok_or_else(|| NexxusError::Io("missing 'addr'".into()))?;
        let addr: std::net::SocketAddr = addr_str
            .parse()
            .map_err(|_| NexxusError::Io(format!("bad addr: {addr_str}")))?;
        let peer = self.network.send_node_announce(addr).await?;
        Ok(serde_json::json!({
            "addr": addr.to_string(),
            "peer_node_id": hex::encode(peer.0),
        }))
    }

    /// Dial a peer through its Tor onion v3 address (`<56ch>.onion:port`).
    #[cfg(feature = "tor")]
    async fn handle_node_dial_onion(&self, params: Option<Value>) -> Result<Value, NexxusError> {
        let addr = params
            .and_then(|p| p.get("addr").and_then(|v| v.as_str()).map(|s| s.to_string()))
            .ok_or_else(|| NexxusError::Io("missing 'addr'".into()))?;
        if !addr.contains(".onion") {
            return Err(NexxusError::Io(format!("not an onion address: {addr}")));
        }
        let ts = self
            .tor_session
            .lock()
            .await
            .clone()
            .ok_or_else(|| NexxusError::Io("tor session not running (NEXXUS_TOR=0?)".into()))?;
        let peer = self.network.dial_onion(&ts, &addr).await?;
        Ok(serde_json::json!({
            "onion": addr,
            "peer_node_id": hex::encode(peer.0),
        }))
    }

    #[cfg(not(feature = "tor"))]
    async fn handle_node_dial_onion(&self, _params: Option<Value>) -> Result<Value, NexxusError> {
        Err(NexxusError::Io(
            "built without tor feature — rebuild with default features".into(),
        ))
    }

    async fn handle_node_upload(&self, params: Option<Value>) -> Result<Value, NexxusError> {
        let path = params
            .and_then(|p| p.get("path").and_then(|v| v.as_str()).map(|s| s.to_string()))
            .ok_or_else(|| NexxusError::Io("missing 'path'".into()))?;
        crate::vault::upload_file(&self.network, self.network.store(), std::path::Path::new(&path)).await
    }

    async fn handle_node_download(&self, params: Option<Value>) -> Result<Value, NexxusError> {
        let params = params.unwrap_or(Value::Null);
        let root = params
            .get("root").and_then(|v| v.as_str()).map(|s| s.to_string())
            .ok_or_else(|| NexxusError::Io("missing 'root'".into()))?;
        let out = params
            .get("out").and_then(|v| v.as_str()).map(|s| s.to_string())
            .ok_or_else(|| NexxusError::Io("missing 'out'".into()))?;
        crate::vault::download_file(&self.network, self.network.store(), &root, std::path::Path::new(&out)).await
    }

    async fn handle_node_por(&self) -> Result<Value, NexxusError> {
        crate::vault::run_por(self.network.store())
    }

    async fn handle_node_test_interhost(&self, params: Option<Value>) -> Result<Value, NexxusError> {
        let addr_str = params
            .and_then(|p| p.get("addr").and_then(|v| v.as_str()).map(|s| s.to_string()))
            .ok_or_else(|| NexxusError::Io("missing 'addr'".into()))?;
        let addr: std::net::SocketAddr = addr_str
            .parse()
            .map_err(|_| NexxusError::Io(format!("bad addr: {addr_str}")))?;
        crate::vault::test_interhost(&self.network, addr).await
    }

    /// Run the WebSocket server forever.
    pub async fn run(self: Arc<Self>, api_addr: SocketAddr) -> Result<(), NexxusError> {
        let listener = TcpListener::bind(api_addr)
            .await
            .map_err(|e| NexxusError::Io(format!("api bind failed: {e}")))?;
        println!("nexxusd local API listening on {api_addr}");

        // Inbound SMP: hand the inbox sender to the network and drain received
        // envelopes into smp_history.
        self.network.set_smp_inbox(self.smp_inbox_tx.clone()).await;
        if let Some(mut rx) = self.smp_inbox_rx.lock().await.take() {
            let api = Arc::clone(&self);
            tokio::spawn(async move {
                while let Some(msg) = rx.recv().await {
                    api.record_smp_inbound(
                        &hex::encode(msg.sender_node_id),
                        &hex::encode(msg.recipient_node_id),
                        msg.plaintext.len(),
                        "delivered",
                    )
                    .await;
                }
            });
        }

        while let Ok((stream, _addr)) = listener.accept().await {
            let api = Arc::clone(&self);
            tokio::spawn(async move {
                let ws_stream = match accept_async(stream).await {
                    Ok(ws) => ws,
                    Err(e) => {
                        eprintln!("nexxusd API: WebSocket accept failed: {e}");
                        return;
                    }
                };
                if let Err(e) = api.handle_ws(ws_stream).await {
                    eprintln!("nexxusd API: WebSocket error: {e}");
                }
            });
        }
        Ok(())
    }

    async fn handle_ws(
        &self,
        ws_stream: tokio_tungstenite::WebSocketStream<tokio::net::TcpStream>,
    ) -> Result<(), NexxusError> {
        let (mut ws_sender, mut ws_receiver) = ws_stream.split();
        // Соединение начинается неаутентифицированным; после успешного
        // `auth` на нём можно выполнить один настоящий запрос.
        let mut authenticated = false;
        while let Some(msg) = ws_receiver.next().await {
            let msg = msg.map_err(|e| NexxusError::Io(e.to_string()))?;
            match msg {
                Message::Text(text) => {
                    let req: JsonRpcRequest = match serde_json::from_str(&text) {
                        Ok(r) => r,
                        Err(_) => {
                            let resp = error_response(None, ERR_INVALID_REQUEST, "invalid JSON".into());
                            let _ = ws_sender
                                .send(Message::Text(serde_json::to_string(&resp).unwrap()))
                                .await;
                            continue;
                        }
                    };

                    // Гейт аутентификации: обрабатывает ping/auth/отказы сам.
                    let expected = self.api_token.lock().unwrap().clone();
                    if let Some((resp, close_after)) = auth_gate(expected.as_deref(), &req, &mut authenticated) {
                        let text = serde_json::to_string(&resp).unwrap_or_default();
                        if ws_sender.send(Message::Text(text)).await.is_err() {
                            break;
                        }
                        if close_after {
                            let _ = ws_sender.close().await;
                            break;
                        }
                        continue;
                    }

                    let resp = self.handle_request(req).await;
                    let text = serde_json::to_string(&resp).unwrap_or_default();
                    if ws_sender.send(Message::Text(text)).await.is_err() {
                        break;
                    }
                    // Duress-PIN: ответ уже отправлен (ложный успех) —
                    // теперь необратимо затираем стор и выходим.
                    if self.duress_wipe.load(std::sync::atomic::Ordering::SeqCst) {
                        let _ = ws_sender.close().await;
                        let store_path = self.store.path().to_path_buf();
                        eprintln!(
                            "nexxusd: DURESS PIN entered — wiping store {} and panic state",
                            store_path.display()
                        );
                        let _ = crate::panic::wipe_file(&store_path);
                        let _ = crate::panic::wipe_file(&crate::panic::PanicManager::default_path(&store_path));
                        std::process::exit(0);
                    }
                    // Корректно закрываем WebSocket соединение после ответа,
                    // чтобы клиент не оставлял висячие соединения.
                    let _ = ws_sender.close().await;
                    break;
                }
                Message::Close(_) => break,
                _ => {}
            }
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn req(method: &str, params: Option<Value>) -> JsonRpcRequest {
        JsonRpcRequest {
            jsonrpc: Some("2.0".into()),
            method: method.into(),
            params,
            id: Some(serde_json::json!(1)),
        }
    }

    fn resp_code(resp: &JsonRpcResponse) -> i32 {
        resp.error.as_ref().map(|e| e.code).unwrap_or(0)
    }

    #[test]
    fn gate_denies_methods_without_auth() {
        let mut auth = false;
        let r = auth_gate(Some("secret"), &req("node_status", None), &mut auth).unwrap();
        assert_eq!(resp_code(&r.0), ERR_UNAUTHORIZED);
        assert!(r.1, "соединение должно закрываться");
        assert!(!auth);
    }

    #[test]
    fn gate_allows_ping_without_auth() {
        let mut auth = false;
        let r = auth_gate(Some("secret"), &req("ping", None), &mut auth).unwrap();
        assert_eq!(resp_code(&r.0), 0);
        assert!(!r.1, "ping не закрывает соединение");
        assert!(!auth);
    }

    #[test]
    fn gate_rejects_wrong_token_and_closes() {
        let mut auth = false;
        let r = auth_gate(
            Some("secret"),
            &req("auth", Some(serde_json::json!({"token": "wrong"}))),
            &mut auth,
        )
        .unwrap();
        assert_eq!(resp_code(&r.0), ERR_UNAUTHORIZED);
        assert!(r.1);
        assert!(!auth);
    }

    #[test]
    fn gate_accepts_correct_token_and_keeps_connection_open() {
        let mut auth = false;
        let r = auth_gate(
            Some("secret"),
            &req("auth", Some(serde_json::json!({"token": "secret"}))),
            &mut auth,
        )
        .unwrap();
        assert_eq!(resp_code(&r.0), 0);
        assert!(!r.1, "после auth соединение остаётся открытым для запроса");
        assert!(auth);

        // После auth гейт больше не перехватывает — диспетчеризация обычная.
        assert!(auth_gate(Some("secret"), &req("node_status", None), &mut auth).is_none());
    }

    #[test]
    fn gate_fails_closed_without_configured_token() {
        let mut auth = false;
        // Даже верный-looking auth отклоняется, если токен не задан.
        let r = auth_gate(None, &req("auth", Some(serde_json::json!({"token": "x"}))), &mut auth).unwrap();
        assert_eq!(resp_code(&r.0), ERR_UNAUTHORIZED);
        // ping по-прежнему работает — для health-check монитора.
        let r = auth_gate(None, &req("ping", None), &mut auth).unwrap();
        assert_eq!(resp_code(&r.0), 0);
    }
}
