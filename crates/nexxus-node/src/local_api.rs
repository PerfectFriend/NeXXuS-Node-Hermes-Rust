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

use crate::net::network::P2pNetwork;
use crate::storage::ChunkStore;
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
use tokio::sync::Mutex;
use tokio_tungstenite::accept_async;
use tokio_tungstenite::tungstenite::Message;

/// Default bind address for the local API WebSocket server.
#[allow(dead_code)]
const DEFAULT_API_ADDR: &str = "127.0.0.1:4010";

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
    #[allow(dead_code)]
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
    /// Статус финализации эпохи (кворум, merkle_root и т.д.).
    epoch_info: Arc<Mutex<EpochInfo>>,
    /// Статус Tor (включен, onion адрес, подключён).
    tor_status: Arc<Mutex<TorStatus>>,
}

impl LocalApi {
    pub fn new(network: Arc<P2pNetwork>, store: Arc<ChunkStore>) -> Self {
        Self {
            network,
            store,
            start_time: SystemTime::now(),
            connected_peers: Arc::new(Mutex::new(HashMap::new())),
            smp_history: Arc::new(Mutex::new(Vec::new())),
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
        let mut history = self.smp_history.lock().await;
        let id = format!("smp-{}", history.len() + 1);
        history.push(SmpMessageInfo {
            id,
            direction: direction.into(),
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
    #[allow(dead_code)]
    pub async fn set_epoch_info(&self, info: EpochInfo) {
        *self.epoch_info.lock().await = info;
    }

    #[allow(dead_code)]
    pub async fn set_tor_status(&self, status: TorStatus) {
        *self.tor_status.lock().await = status;
    }

    /// Handle a single JSON-RPC request and return a response value.
    async fn handle_request(&self, req: JsonRpcRequest) -> JsonRpcResponse {
        let id = req.id.clone();
        let result = match req.method.as_str() {
            "node_status" => self.handle_node_status().await,
            "node_peers" => self.handle_node_peers().await,
            "node_chunks" => self.handle_node_chunks().await,
            "node_smp" => self.handle_node_smp().await,
            "node_epoch" => self.handle_node_epoch().await,
            "node_tor" => self.handle_node_tor().await,
            "send_smp_envelope" => self.handle_send_smp_envelope(req.params).await,
            "node_pause" => self.handle_node_pause().await,
            "node_resume" => self.handle_node_resume().await,
            _ => return error_response(id, ERR_METHOD_NOT_FOUND, format!("method '{}' not found", req.method)),
        };
        match result {
            Ok(v) => ok_response(id, v),
            Err(e) => error_response(id, ERR_INTERNAL_ERROR, e.to_string()),
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
        }).map_err(|e| NexxusError::Io(e.to_string()))
    }

    async fn handle_node_peers(&self) -> Result<Value, NexxusError> {
        let peers = self.connected_peers.lock().await.clone();
        let list: Vec<Value> = peers
            .into_values()
            .map(|p| serde_json::to_value(p).unwrap_or(Value::Null))
            .collect();
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
        serde_json::to_value(ChunkStats {
            total_chunks: total,
            chunk_size_bytes: 16_384,
            used_bytes,
            free_gb: 0, // placeholder; would need disk info
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
        let status = self.tor_status.lock().await.clone();
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
        let addr: String = params
            .get("addr")
            .and_then(|v| v.as_str())
            .map(|s| s.into())
            .unwrap_or_else(|| "127.0.0.1:4001".into());

        // Parse recipient node id
        let recipient_bytes = hex::decode(&recipient).map_err(|e| NexxusError::Io(e.to_string()))?;
        if recipient_bytes.len() != 32 {
            return Err(NexxusError::Io("recipient_node_id must be 32 bytes hex".into()));
        }
        let recipient_id = NodeId(recipient_bytes.try_into().map_err(|_| {
            NexxusError::Io("recipient_node_id invalid length".into())
        })?);

        // Parse address
        let peer_addr: SocketAddr = addr.parse().map_err(|e: std::net::AddrParseError| NexxusError::Io(e.to_string()))?;

        // Build and seal SMP envelope
        let (ephemeral_pub, env) = SmpEnvelope::seal(
            self.network.node_id().0,
            recipient_id.0,
            &self.network.x25519_pub(),
            &payload,
        );

        // Send to peer
        let result = self.network.send_smp_envelope(peer_addr, &env).await;

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
        Ok(serde_json::json!({ "status": "paused" }))
    }

    async fn handle_node_resume(&self) -> Result<Value, NexxusError> {
        Ok(serde_json::json!({ "status": "resumed" }))
    }

    /// Run the WebSocket server forever.
    pub async fn run(self: Arc<Self>, api_addr: SocketAddr) -> Result<(), NexxusError> {
        let listener = TcpListener::bind(api_addr)
            .await
            .map_err(|e| NexxusError::Io(format!("api bind failed: {e}")))?;
        println!("nexxusd local API listening on {api_addr}");

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
                    let resp = self.handle_request(req).await;
                    let text = serde_json::to_string(&resp).unwrap_or_default();
                    if ws_sender.send(Message::Text(text)).await.is_err() {
                        break;
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
