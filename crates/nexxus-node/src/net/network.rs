//! P2pNetwork: bind/listen, dial, routing table, opcode dispatcher.
//! Integrates with ChunkStore (redb) for StoreChunk/FetchChunk.
//! Phase 8: full protocol — NodeAnnounce, SmpEnvelope, EpochFinalize,
//! PorChallenge/Response, StoreChunkAck, FetchChunkResp.
//
//! Архитектура:
//!   - P2pNetwork хранит идентичность узла (Ed25519 + X25519), таблицу маршрутизации
//!     (Kademlia k-buckets) и ссылку на ChunkStore.
//!   - Принимает входящие TCP соединения на listen_addr, каждое обрабатывается в
//!     отдельной tokio-задаче.
//!   - Все исходящие frames подписываются Ed25519 ключом узла (wire v3).
//!   - local_api (опционально) связывает сеть с десктоп-монитором через WebSocket.

use std::net::{IpAddr, SocketAddr};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use curve25519_dalek::MontgomeryPoint;
use ed25519_dalek::{VerifyingKey};
use nexxus_core::{
    error::NexxusError,
    epoch::verify_epoch_finalize,
    keys::identity::Identity,
    types::{ChunkHash, NodeId},
    wire::header::v3_signing_bytes,
    wire::opcode::Opcode,
    wire::payloads::{
        ErrorResponse, FetchChunk, FetchChunkResp, KadFindNode, KadNodesFound, KadPeer,
        NodeAnnounce, Payload, PorChallenge, PorResponse, SmpEnvelope, StoreChunk,
        StoreChunkAck,
    },
};
use crate::net::frame::{MAX_FRAME_LEN, send_frame};
use crate::storage::ChunkStore;
#[cfg(test)]
use rand::Rng;
use sha2::Digest;
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::{mpsc, Mutex};
use tokio::task;

/// Connected peer tracked for the lifetime of a stream.
///
/// Хранит node_id (если известен после NodeAnnounce handshake) и адрес.
struct ConnectedPeer {
    node_id: Option<NodeId>,
    addr: SocketAddr,
}

/// Decrypted inbound SMP message, delivered to the upper layer (LocalApi)
/// through the `smp_inbox` channel.
#[derive(Debug, Clone)]
pub struct InboundSmp {
    pub sender_node_id: [u8; 32],
    pub recipient_node_id: [u8; 32],
    pub plaintext: Vec<u8>,
}

/// P2P network node. Holds identity (Ed25519 + X25519), routing table +
/// chunk store, accepts inbound connections and dials outbound peers.
///
/// Поля:
///   - our_id — NodeId этого узла (публичный идентификатор в сети).
///   - identity — Ed25519 ключ для подписи кадров и верификации чужих.
///   - x25519_secret / x25519_pub — ключи для шифрования SMP конвертов.
///   - listen_addr — адрес, на котором слушаем входящие соединения.
///   - bound_addr — фактический адрес после bind (заполняется в run()).
///   - routing — Kademlia таблица маршрутизации (k-buckets).
///   - store — persistent хранилище чанков (redb).
///   - auditors — реестр публичных ключей аудиторов для EpochFinalize (M-of-N).
///   - threshold — порог количества подписей для принятия EpochFinalize.
///   - local_api — ссылка на локальное WebSocket API (для регистрации пиров).
pub struct P2pNetwork {
    our_id: NodeId,
    identity: Identity,
    x25519_secret: [u8; 32],
    x25519_pub: MontgomeryPoint,
    listen_addr: SocketAddr,
    bound_addr: Arc<Mutex<Option<SocketAddr>>>,
    routing: Arc<Mutex<crate::net::routing::RoutingTable>>,
    store: Arc<ChunkStore>,
    /// Registered committee auditors (Ed25519 verifying keys). Empty = no EpochFinalize gating.
    auditors: Vec<VerifyingKey>,
    /// M-of-N threshold for EpochFinalize acceptance.
    threshold: usize,
    /// Optional local API for desktop monitor (peer registration).
    pub local_api: Arc<Mutex<Option<Arc<crate::local_api::LocalApi>>>>,
    /// Pause flag: while set, inbound frames are rejected with 0x0007
    /// (driven by local API node_pause/node_resume).
    paused: Arc<AtomicBool>,
    /// Inbound SMP inbox (attached by LocalApi): decrypted envelopes land here.
    smp_inbox: Arc<Mutex<Option<mpsc::UnboundedSender<InboundSmp>>>>,
}

impl P2pNetwork {
    /// Create a new node with a fresh Ed25519 identity and X25519 key pair.
    #[cfg(test)]
    pub fn new(our_id: NodeId, listen_addr: SocketAddr, store: Arc<ChunkStore>) -> Self {
        Self::with_auditors(our_id, listen_addr, store, Vec::new(), 0)
    }

    /// Create from existing keys with an auditor registry (tests / committee setup).
    #[cfg(test)]
    pub fn with_auditors(
        our_id: NodeId,
        listen_addr: SocketAddr,
        store: Arc<ChunkStore>,
        auditors: Vec<VerifyingKey>,
        threshold: usize,
    ) -> Self {
        let mut os_rng = rand::rngs::OsRng;
        let identity = Identity::generate();
        let mut x25519_secret = [0u8; 32];
        os_rng.fill(&mut x25519_secret);
        let x25519_pub = nexxus_core::wire::payloads::X25519_BASEPOINT.mul_clamped(x25519_secret);
        Self {
            our_id,
            identity,
            x25519_secret,
            x25519_pub,
            listen_addr,
            bound_addr: Arc::new(Mutex::new(None)),
            routing: Arc::new(Mutex::new(crate::net::routing::RoutingTable::new(our_id))),
            store,
            auditors,
            threshold,
            local_api: Arc::new(Mutex::new(None)),
            paused: Arc::new(AtomicBool::new(false)),
            smp_inbox: Arc::new(Mutex::new(None)),
        }
    }

    /// Create from an existing identity + X25519 keys (for reconnect/restart).
    /// Used by main when no auditor registry is configured.
    pub fn with_keys(
        our_id: NodeId,
        identity: Identity,
        x25519_secret: [u8; 32],
        listen_addr: SocketAddr,
        store: Arc<ChunkStore>,
    ) -> Self {
        Self::with_keys_and_auditors(our_id, identity, x25519_secret, listen_addr, store, Vec::new(), 0)
    }
    /// Create from existing keys with auditor registry.
    pub fn with_keys_and_auditors(
        our_id: NodeId,
        identity: Identity,
        x25519_secret: [u8; 32],
        listen_addr: SocketAddr,
        store: Arc<ChunkStore>,
        auditors: Vec<VerifyingKey>,
        threshold: usize,
    ) -> Self {
        let x25519_pub = nexxus_core::wire::payloads::X25519_BASEPOINT.mul_clamped(x25519_secret);
        Self {
            our_id,
            identity,
            x25519_secret,
            x25519_pub,
            listen_addr,
            bound_addr: Arc::new(Mutex::new(None)),
            routing: Arc::new(Mutex::new(crate::net::routing::RoutingTable::new(our_id))),
            store,
            auditors,
            threshold,
            local_api: Arc::new(Mutex::new(None)),
            paused: Arc::new(AtomicBool::new(false)),
            smp_inbox: Arc::new(Mutex::new(None)),
        }
    }

    /// Attach the local API instance for peer registration and monitoring.
    pub async fn set_local_api(&self, api: Arc<crate::local_api::LocalApi>) {
        *self.local_api.lock().await = Some(api);
    }

    /// Ed25519 verifying key (our node public key).
    pub fn verifying_key(&self) -> VerifyingKey {
        self.identity.verifying_key
    }

    /// Our NodeId.
    pub fn node_id(&self) -> NodeId {
        self.our_id
    }

    /// Listen address as string.
    pub fn listen_addr_str(&self) -> String {
        self.listen_addr.to_string()
    }

    /// Static X25519 public key (for SMP envelope sealing by peers).
    pub fn x25519_pub(&self) -> MontgomeryPoint {
        self.x25519_pub
    }

    /// Actual address the listener is bound to (None until `run()` binds).
    pub async fn bound_addr(&self) -> Option<SocketAddr> {
        *self.bound_addr.lock().await
    }

    /// Session nonce for v3 frame signing.
    ///
    /// ВНИМАНИЕ: сейчас фиксированный нулевой нонс, так как полноценного
    /// рукопожатия (handshake) между узлами ещё нет (Phase 9+).
    /// Каждый v3 кадр подписывается Ed25519 с этим нонсом. После внедрения
    /// рукопожатия нонс должен становиться случайным за сессию.
    const SESSION_NONCE: [u8; 32] = [0u8; 32];

    /// Sign v3 signing bytes with our Ed25519 identity key.
    fn sign_v3(&self, opcode: Opcode, request_id: u32, payload: &[u8]) -> [u8; 64] {
        let msg = v3_signing_bytes(opcode, request_id, payload, &Self::SESSION_NONCE);
        self.identity.sign(&msg)
    }

    /// Send a v3 frame signed with our Ed25519 identity key.
    async fn send_signed_frame<T: Payload, S: tokio::io::AsyncRead + tokio::io::AsyncWrite + Unpin + Send>(
        &self,
        stream: &mut S,
        opcode: Opcode,
        request_id: u32,
        payload: &T,
    ) -> Result<(), NexxusError> {
        let encoded = payload.encode();
        let signature = self.sign_v3(opcode, request_id, &encoded);
        send_frame(stream, opcode, request_id, payload, &signature).await
    }

    /// Pause/resume inbound frame processing (local API node_pause/node_resume).
    pub fn set_paused(&self, v: bool) {
        self.paused.store(v, Ordering::SeqCst);
    }

    pub fn is_paused(&self) -> bool {
        self.paused.load(Ordering::SeqCst)
    }

    /// Attach the inbound SMP channel (LocalApi drains it into smp_history).
    pub async fn set_smp_inbox(&self, tx: mpsc::UnboundedSender<InboundSmp>) {
        *self.smp_inbox.lock().await = Some(tx);
    }

    /// Our own NodeAnnounce payload (includes the Ed25519 pubkey so peers can
    /// verify our frames on this connection).
    fn our_announce(&self) -> NodeAnnounce {
        let (ip, port) = match self.bound_addr.try_lock() {
            Ok(guard) => match *guard {
                Some(a) => (
                    match a.ip() {
                        // wire convention: ip is the host-order u32 of the IPv4
                        // address (0x7f000001 for 127.0.0.1, see kad tests);
                        // the receiver uses Ipv4Addr::from(ip) directly.
                        IpAddr::V4(v4) => u32::from(v4),
                        IpAddr::V6(_) => 0,
                    },
                    a.port(),
                ),
                None => (0, self.listen_addr.port()),
            },
            Err(_) => (0, self.listen_addr.port()),
        };
        NodeAnnounce {
            node_id: self.our_id.0,
            pubkey: self.verifying_key().to_bytes(),
            ip,
            port,
        }
    }

    /// Client side of the announce handshake over any stream (TCP or Tor
    /// onion): send our signed NodeAnnounce, expect the peer's NodeAnnounce
    /// reply on the same request id, and return the peer's node id.
    pub async fn announce_on<S: tokio::io::AsyncRead + tokio::io::AsyncWrite + Unpin + Send>(
        &self,
        stream: &mut S,
        req_id: u32,
    ) -> Result<NodeId, NexxusError> {
        let our = self.our_announce();
        self.send_signed_frame(stream, Opcode::NodeAnnounce, req_id, &our)
            .await?;
        let (op, rid, payload, _sig) = crate::net::frame::recv_frame(stream).await?;
        if op != Opcode::NodeAnnounce || rid != req_id {
            return Err(NexxusError::Io(format!(
                "expected NodeAnnounce reply, got opcode 0x{:02x} rid={rid:#x}",
                op.to_u8()
            )));
        }
        let their = NodeAnnounce::decode(&payload)?;
        Ok(NodeId(their.node_id))
    }

    /// Dial a peer through its Tor onion v3 address (`<56ch>.onion:port`):
    /// открываем arti DataStream и делаем signed NodeAnnounce handshake поверх
    /// него. Требует feature `tor` (включён по умолчанию).
    #[cfg(feature = "tor")]
    pub async fn dial_onion(
        &self,
        tor: &crate::tor::TorSession,
        onion_addr: &str,
    ) -> Result<NodeId, NexxusError> {
        let mut stream = tor
            .connect_onion(onion_addr)
            .await
            .map_err(|e| NexxusError::Io(format!("tor connect {onion_addr}: {e}")))?;
        self.announce_on(&mut stream, 0x0013).await
    }

    /// Bind listen address and accept connections forever. Each connection
    /// is handled in its own task.
    pub async fn run(self: Arc<Self>) -> Result<(), NexxusError> {
        let listener = TcpListener::bind(self.listen_addr)
            .await
            .map_err(|e| NexxusError::Io(e.to_string()))?;
        let bound = listener.local_addr().map_err(|e| NexxusError::Io(e.to_string()))?;
        *self.bound_addr.lock().await = Some(bound);
        loop {
            let (stream, addr) = listener
                .accept()
                .await
                .map_err(|e| NexxusError::Io(e.to_string()))?;
            let net = Arc::clone(&self);
            task::spawn(async move {
                let peer = ConnectedPeer {
                    node_id: None,
                    addr,
                };
                if let Err(e) = net.handle_connection(stream, peer).await {
                    let _ = e;
                }
            });
        }
    }

    /// Dial a peer and perform a Kademlia find_node against it. Returns the
    /// peers it knows closest to `target`.
    pub async fn dial_find_node(
        &self,
        addr: SocketAddr,
        target: NodeId,
        count: u16,
    ) -> Result<Vec<KadPeer>, NexxusError> {
        let mut stream = TcpStream::connect(addr)
            .await
            .map_err(|e| NexxusError::Io(e.to_string()))?;
        self.announce_on(&mut stream, 0x0009).await?;
        let query = KadFindNode {
            target_node_id: target.0,
            count,
        };
        self.send_signed_frame(&mut stream, Opcode::KadFindNode, 0x0001, &query)
            .await?;
        let (op, _rid, payload, _sig) = crate::net::frame::recv_frame(&mut stream).await?;
        if op != Opcode::KadNodesFound {
            return Err(NexxusError::Io(format!(
                "expected KadNodesFound, got opcode 0x{:02x}",
                op.to_u8()
            )));
        }
        let nodes = KadNodesFound::decode(&payload)?;
        Ok(nodes
            .peers
            .into_iter()
            .map(|p| KadPeer {
                node_id: p.node_id,
                ip: p.ip,
                port: p.port,
            })
            .collect())
    }

    /// Announce ourselves to a known bootstrap peer (KadFindNode for our own id
    /// so the bootstrap peer learns about us).
    /// Send our NodeAnnounce to a peer and learn their node_id in return.
    pub async fn send_node_announce(&self, addr: SocketAddr) -> Result<NodeId, NexxusError> {
        let mut stream = TcpStream::connect(addr)
            .await
            .map_err(|e| NexxusError::Io(e.to_string()))?;
        let announce = self.our_announce();
        self.send_signed_frame(
            &mut stream,
            Opcode::NodeAnnounce,
            0x0003,
            &announce,
        )
        .await?;
        let (op, _rid, payload, _sig) = crate::net::frame::recv_frame(&mut stream).await?;
        if op != Opcode::NodeAnnounce {
            return Err(NexxusError::Io(format!(
                "expected NodeAnnounce, got opcode 0x{:02x}",
                op.to_u8()
            )));
        }
        let their = NodeAnnounce::decode(&payload)?;
        // Learn the peer's listen address too, so we can route towards it later.
        let their_addr = SocketAddr::new(
            IpAddr::V4(std::net::Ipv4Addr::from(their.ip)),
            their.port,
        );
        self.routing.lock().await.insert(crate::net::routing::Peer {
            node_id: NodeId(their.node_id),
            addr: their_addr,
        });
        self.register_peer(crate::net::routing::Peer {
            node_id: NodeId(their.node_id),
            addr: their_addr,
        }).await;
        Ok(NodeId(their.node_id))
    }

    /// Fetch a chunk from a peer over the wire. Returns the raw chunk bytes.
    pub async fn fetch_chunk_from_peer(
        &self,
        addr: SocketAddr,
        hash: ChunkHash,
    ) -> Result<Vec<u8>, NexxusError> {
        let mut stream = TcpStream::connect(addr)
            .await
            .map_err(|e| NexxusError::Io(e.to_string()))?;
        self.announce_on(&mut stream, 0x0007).await?;
        let fetch = FetchChunk { hash: hash.0 };
        self.send_signed_frame(&mut stream, Opcode::FetchChunk, 0x0004, &fetch)
            .await?;
        let (op, _rid, payload, _sig) = crate::net::frame::recv_frame(&mut stream).await?;
        if op == Opcode::ErrorResponse {
            let err = ErrorResponse::decode(&payload)?;
            return Err(NexxusError::Io(format!(
                "peer error: code={} msg={}",
                err.code, err.message
            )));
        }
        if op != Opcode::FetchChunkResp {
            return Err(NexxusError::Io(format!(
                "expected FetchChunkResp, got opcode 0x{:02x}",
                op.to_u8()
            )));
        }
        let resp = FetchChunkResp::decode(&payload)?;
        // persist locally so future fetches are served from redb
        self.store.put_chunk(&resp.chunk_hash, &resp.data)?;
        Ok(resp.data)
    }

    /// Send an encrypted SMP envelope to a peer.
    pub async fn send_smp_envelope(&self, addr: SocketAddr, env: &SmpEnvelope) -> Result<(), NexxusError> {
        let mut stream = TcpStream::connect(addr)
            .await
            .map_err(|e| NexxusError::Io(e.to_string()))?;
        self.announce_on(&mut stream, 0x000a).await?;
        self.send_signed_frame(&mut stream, Opcode::SmpEnvelope, 0x0005, env)
            .await?;
        let (op, _rid, _payload, _sig) = crate::net::frame::recv_frame(&mut stream).await?;
        if op == Opcode::ErrorResponse {
            let err = ErrorResponse::decode(&_payload)?;
            return Err(NexxusError::Io(format!(
                "peer error: code={} msg={}",
                err.code, err.message
            )));
        }
        Ok(())
    }

    /// Route an SMP envelope towards its recipient via the Kademlia routing
    /// table: try the closest known peers in order until one accepts it.
    pub async fn route_smp_envelope(&self, env: &SmpEnvelope) -> Result<(), NexxusError> {
        let recipient = NodeId(env.recipient_node_id);
        let peers = self.routing.lock().await.find_node(&recipient, 8);
        if peers.is_empty() {
            return Err(NexxusError::Io(format!(
                "no route to recipient {}",
                hex::encode(recipient.0)
            )));
        }
        let mut last_err = NexxusError::Io("no peers tried".into());
        for p in peers {
            match self.send_smp_envelope(p.addr, env).await {
                Ok(()) => return Ok(()),
                Err(e) => last_err = e,
            }
        }
        Err(last_err)
    }

    /// Send an EpochFinalize (committee multi-sig) to a peer.
    pub async fn send_epoch_finalize(
        &self,
        addr: SocketAddr,
        finalize: &nexxus_core::wire::payloads::EpochFinalize,
    ) -> Result<(), NexxusError> {
        let mut stream = TcpStream::connect(addr)
            .await
            .map_err(|e| NexxusError::Io(e.to_string()))?;
        self.announce_on(&mut stream, 0x000b).await?;
        self.send_signed_frame(&mut stream, Opcode::EpochFinalize, 0x0006, finalize)
            .await?;
        let (op, _rid, _payload, _sig) = crate::net::frame::recv_frame(&mut stream).await?;
        if op == Opcode::ErrorResponse {
            let err = ErrorResponse::decode(&_payload)?;
            return Err(NexxusError::Io(format!(
                "peer error: code={} msg={}",
                err.code, err.message
            )));
        }
        Ok(())
    }

    async fn handle_connection(
        &self,
        mut stream: TcpStream,
        mut peer: ConnectedPeer,
    ) -> Result<(), NexxusError> {
        let addr = peer.addr;
        if let Some(api) = self.local_api.lock().await.as_ref() {
            api.register_peer(addr, None, "inbound").await;
        }
        let api_clone = self.local_api.clone();
        let addr_clone = addr;
        let result = (async {
            // Ed25519 pubkey of the peer on this connection, learned from a
            // verified NodeAnnounce. Every later frame must verify against it.
            let mut peer_key: Option<VerifyingKey> = None;
            loop {
                let (opcode, req_id, payload, sig) = match crate::net::frame::recv_frame(&mut stream).await {
                    Ok(f) => f,
                    // clean EOF on idle connection
                    Err(NexxusError::Io(e)) if e.to_string().contains("connection reset")
                        || e.to_string().contains("broken pipe") =>
                    {
                        return Ok(())
                    }
                    Err(e) => return Err(e),
                };
                if payload.len() > MAX_FRAME_LEN {
                    return Err(NexxusError::Io("frame too large".into()));
                }
                if opcode == Opcode::NodeAnnounce {
                    // Self-signed announce: the pubkey travels inside the payload
                    // and is bound to this frame by the frame's own signature.
                    let announce = NodeAnnounce::decode(&payload)?;
                    let vk = VerifyingKey::from_bytes(&announce.pubkey)
                        .map_err(|e| NexxusError::Io(format!("bad announce pubkey: {e}")))?;
                    let msg = v3_signing_bytes(opcode, req_id, &payload, &Self::SESSION_NONCE);
                    if !Identity::verify(&vk, &msg, &sig) {
                        let err = ErrorResponse { code: 0x0008, message: "bad announce signature".into() };
                        self.send_signed_frame(&mut stream, Opcode::ErrorResponse, req_id, &err).await?;
                        return Err(NexxusError::Io("bad announce signature".into()));
                    }
                    peer_key = Some(vk);
                    let their_id = NodeId(announce.node_id);
                    peer.node_id = Some(their_id);
                    if let Some(api) = api_clone.lock().await.as_ref() {
                        api.register_peer(addr_clone, Some(their_id), "inbound").await;
                    }
                    let their_addr = SocketAddr::new(
                        IpAddr::V4(std::net::Ipv4Addr::from(announce.ip)),
                        announce.port,
                    );
                    self.routing.lock().await.insert(crate::net::routing::Peer {
                        node_id: their_id,
                        addr: their_addr,
                    });
                    if let Some(api) = self.local_api.lock().await.as_ref() {
                        api.register_peer(addr, Some(their_id), "inbound").await;
                    }
                    let our_announce = self.our_announce();
                    self.send_signed_frame(&mut stream, Opcode::NodeAnnounce, req_id, &our_announce).await?;
                    continue;
                }
                // All non-announce frames require a verified announce first and
                // a valid signature from the announced key.
                let vk = match peer_key {
                    Some(vk) => vk,
                    None => {
                        let err = ErrorResponse {
                            code: 0x0006,
                            message: "unknown peer: send NodeAnnounce first".into(),
                        };
                        self.send_signed_frame(&mut stream, Opcode::ErrorResponse, req_id, &err).await?;
                        continue;
                    }
                };
                let msg = v3_signing_bytes(opcode, req_id, &payload, &Self::SESSION_NONCE);
                if !Identity::verify(&vk, &msg, &sig) {
                    let err = ErrorResponse { code: 0x0008, message: "bad frame signature".into() };
                    self.send_signed_frame(&mut stream, Opcode::ErrorResponse, req_id, &err).await?;
                    return Err(NexxusError::Io("bad frame signature".into()));
                }
                self.handle_opcode(&mut stream, opcode, req_id, &payload).await?;
            }
        }).await;
        if let Some(api) = api_clone.lock().await.as_ref() {
            api.unregister_peer(&addr_clone).await;
        }
        result
    }

    async fn handle_opcode(
        &self,
        stream: &mut TcpStream,
        opcode: Opcode,
        request_id: u32,
        payload: &[u8],
    ) -> Result<(), NexxusError> {
        // Pause gate: while paused every frame gets an immediate 0x0007 error
        // and is not dispatched (makes node_pause/node_resume real).
        if self.is_paused() {
            let err = ErrorResponse { code: 0x0007, message: "node paused".into() };
            self.send_signed_frame(stream, Opcode::ErrorResponse, request_id, &err).await?;
            return Ok(());
        }
        match opcode {
            Opcode::Ping => {
                let _ping = nexxus_core::wire::payloads::Ping::decode(payload)?;
                let pong = nexxus_core::wire::payloads::Pong;
                self.send_signed_frame(stream, Opcode::Pong, request_id, &pong).await?;
            }
            Opcode::Pong => {
                // unsolicited pong: nothing to do
            }
            Opcode::NodeAnnounce => {
                // Verified and handled in handle_connection before dispatch;
                // a repeated announce on an open connection is just ignored.
            }
            Opcode::StoreChunk => {
                let chunk = StoreChunk::decode(payload)?;
                self.store.put_chunk(&chunk.chunk_hash, &chunk.data)?;
                let ack = StoreChunkAck { hash: chunk.chunk_hash.0 };
                self.send_signed_frame(stream, Opcode::StoreChunkAck, request_id, &ack).await?;
            }
            Opcode::StoreChunkAck => {
                // inbound ack handled by request originator in Phase 8
            }
            Opcode::FetchChunk => {
                let fetch = FetchChunk::decode(payload)?;
                let hash = ChunkHash(fetch.hash);
                if let Some(data) = self.store.get_chunk(&hash)? {
                    let resp = FetchChunkResp {
                        chunk_hash: hash,
                        data,
                    };
                    self.send_signed_frame(stream, Opcode::FetchChunkResp, request_id, &resp).await?;
                } else {
                    let err = ErrorResponse {
                        code: 0x0002,
                        message: "chunk not found".into(),
                    };
                    self.send_signed_frame(stream, Opcode::ErrorResponse, request_id, &err).await?;
                }
            }
            Opcode::FetchChunkResp => {
                // inbound response handled by request originator in Phase 8
            }
            Opcode::PorChallenge => {
                let challenge = PorChallenge::decode(payload)?;
                // Per spec §4.3: challenge.seed — это epoch seed (вход для HMAC),
                // НЕ chunk hash. Нужно детерминированно выбрать чанк из хранилища
                // на основе seed, чтобы проверка была воспроизводимой.
                let hashes = self.store.list_chunk_hashes()?;
                if hashes.is_empty() {
                    let err = ErrorResponse {
                        code: 0x0003,
                        message: "no chunks stored for PoR".into(),
                    };
                    self.send_signed_frame(stream, Opcode::ErrorResponse, request_id, &err)
                        .await?;
                } else {
                    // Детерминированный выбор: индекс = первые 4 байта seed modulo количество чанков.
                    // Это обеспечивает воспроизводимый выбор того же чанка при том же seed.
                    let seed_index = u32::from_be_bytes(challenge.seed[0..4].try_into().unwrap_or([0; 4]))
                        as usize % hashes.len();
                    let hash = hashes[seed_index];
                    if let Some(data) = self.store.get_chunk(&hash)? {
                        // response = SHA-256(chunk_data || seed)
                        let mut h = sha2::Sha256::new();
                        h.update(&data);
                        h.update(challenge.seed);
                        let response: [u8; 32] = h.finalize().into();
                        let resp = PorResponse {
                            chunk_hash: hash,
                            response,
                        };
                        self.send_signed_frame(stream, Opcode::PorResponse, request_id, &resp)
                            .await?;
                    } else {
                        let err = ErrorResponse {
                            code: 0x0003,
                            message: "chunk not found for PoR".into(),
                        };
                        self.send_signed_frame(stream, Opcode::ErrorResponse, request_id, &err)
                            .await?;
                    }
                }
            }
            Opcode::PorResponse => {
                // inbound response handled by request originator in Phase 8
                let _resp = PorResponse::decode(payload)?;
            }
            Opcode::KadFindNode => {
                let find = KadFindNode::decode(payload)?;
                let rt = self.routing.lock().await;
                let target = NodeId(find.target_node_id);
                let peers = rt.find_node(&target, find.count as usize);
                let kad_peers: Vec<KadPeer> = peers
                    .into_iter()
                    .map(|p| socket_addr_to_kad_peer(&p))
                    .collect();
                let nodes = KadNodesFound { peers: kad_peers };
                self.send_signed_frame(stream, Opcode::KadNodesFound, request_id, &nodes).await?;
            }
            Opcode::KadNodesFound => {
                // inbound nodes found handled by request originator in Phase 8
            }
            Opcode::SmpEnvelope => {
                let env = SmpEnvelope::decode(payload)?;
                match env.open(&self.x25519_secret()) {
                    Ok(plaintext) => {
                        // Deliver the decrypted envelope to the upper layer
                        // (LocalApi records it in smp_history via this channel).
                        let msg = InboundSmp {
                            sender_node_id: env.sender_node_id,
                            recipient_node_id: env.recipient_node_id,
                            plaintext,
                        };
                        if let Some(tx) = self.smp_inbox.lock().await.as_ref() {
                            let _ = tx.send(msg);
                        }
                        let pong = nexxus_core::wire::payloads::Pong;
                        self.send_signed_frame(stream, Opcode::Pong, request_id, &pong).await?;
                    }
                    Err(_) => {
                        let err = ErrorResponse {
                            code: 0x0004,
                            message: "smp envelope decrypt failed".into(),
                        };
                        self.send_signed_frame(stream, Opcode::ErrorResponse, request_id, &err).await?;
                    }
                }
            }
            Opcode::EpochFinalize => {
                let finalize = nexxus_core::wire::payloads::EpochFinalize::decode(payload)?;
                // Verify committee multi-sig against registered auditors (M-of-N).
                let result = verify_epoch_finalize(&finalize, &self.auditors, self.threshold);
                // Always surface verification stats to the local API (node_epoch).
                if let Ok(vr) = &result {
                    if let Some(api) = self.local_api.lock().await.as_ref() {
                        api.set_epoch_info(crate::local_api::EpochInfo {
                            epoch_number: finalize.epoch_number,
                            merkle_root: hex::encode(finalize.merkle_root),
                            total_bytes: finalize.total_bytes,
                            signature_count: vr.signatures_valid,
                            threshold: self.threshold,
                            quorum_met: vr.quorum_met,
                        })
                        .await;
                    }
                }
                match result {
                    Ok(vr) if vr.quorum_met => {
                        // Quorum reached: persist the finalized epoch in the store.
                        let record = format!(
                            "{{\"epoch_number\":{},\"merkle_root\":\"{}\",\"total_bytes\":{},\"signatures\":{}}}",
                            finalize.epoch_number,
                            hex::encode(finalize.merkle_root),
                            finalize.total_bytes,
                            vr.signatures_valid
                        );
                        let _ = self.store.put_meta("last_epoch", record.as_bytes());
                        let pong = nexxus_core::wire::payloads::Pong;
                        self.send_signed_frame(stream, Opcode::Pong, request_id, &pong).await?;
                    }
                    _ => {
                        let err = ErrorResponse {
                            code: 0x0005,
                            message: "epoch finalize multi-sig verification failed".into(),
                        };
                        self.send_signed_frame(stream, Opcode::ErrorResponse, request_id, &err)
                            .await?;
                    }
                }
            }
            Opcode::ErrorResponse => {
                // upstream logs the error; nothing to do here
            }
        }
        Ok(())
    }

    /// Our Ed25519 verifying key (hex) — used to register this node in committees.
    pub fn identity_pubkey(&self) -> [u8; 32] {
        self.identity.verifying_key.to_bytes()
    }

    /// Our node id.
    pub fn our_id(&self) -> NodeId {
        self.our_id
    }

    /// Our X25519 secret (used to derive the vault AEAD key, domain-separated).
    pub fn x25519_secret(&self) -> [u8; 32] {
        self.x25519_secret
    }

    /// Shared chunk store.
    pub fn store(&self) -> &Arc<ChunkStore> {
        &self.store
    }

    /// Round-trip Ping/Pong to a peer; returns the RTT.
    pub async fn ping(&self, addr: SocketAddr) -> Result<std::time::Duration, NexxusError> {
        let start = std::time::Instant::now();
        let mut stream = TcpStream::connect(addr)
            .await
            .map_err(|e| NexxusError::Io(e.to_string()))?;
        self.announce_on(&mut stream, 0x0001).await?;
        self.send_signed_frame(&mut stream, Opcode::Ping, 0x0002, &nexxus_core::wire::payloads::Ping)
            .await?;
        let (op, _rid, _payload, _sig) = crate::net::frame::recv_frame(&mut stream).await?;
        if op != Opcode::Pong {
            return Err(NexxusError::Io(format!(
                "expected Pong, got opcode 0x{:02x}",
                op.to_u8()
            )));
        }
        Ok(start.elapsed())
    }

    /// Push a chunk to a peer: announce-handshake + StoreChunk, expect StoreChunkAck.
    pub async fn send_store_chunk(
        &self,
        addr: SocketAddr,
        chunk: &nexxus_core::wire::payloads::StoreChunk,
    ) -> Result<ChunkHash, NexxusError> {
        let mut stream = TcpStream::connect(addr)
            .await
            .map_err(|e| NexxusError::Io(e.to_string()))?;
        self.announce_on(&mut stream, 0x0004).await?;
        self.send_signed_frame(&mut stream, Opcode::StoreChunk, 0x0003, chunk)
            .await?;
        let (op, _rid, payload, _sig) = crate::net::frame::recv_frame(&mut stream).await?;
        match op {
            Opcode::StoreChunkAck => {
                let ack = nexxus_core::wire::payloads::StoreChunkAck::decode(&payload)?;
                Ok(ChunkHash(ack.hash))
            }
            Opcode::ErrorResponse => {
                let e = nexxus_core::wire::payloads::ErrorResponse::decode(&payload)?;
                Err(NexxusError::Io(format!(
                    "peer rejected StoreChunk: {} (0x{:04x})",
                    e.message, e.code
                )))
            }
            other => Err(NexxusError::Io(format!(
                "expected StoreChunkAck, got opcode 0x{:02x}",
                other.to_u8()
            ))),
        }
    }

    /// Snapshot of current routing table peers.
    pub async fn known_peers(&self) -> Vec<crate::net::routing::Peer> {
        self.routing.lock().await.peers()
    }

    /// Insert a discovered peer into the routing table (used after handshake).
    pub async fn register_peer(&self, peer: crate::net::routing::Peer) {
        self.routing.lock().await.insert(peer);
    }
}

/// Convert a tracked Peer to a wire KadPeer (IPv4 only in Phase 7).
fn socket_addr_to_kad_peer(peer: &crate::net::routing::Peer) -> KadPeer {
    let ip = match peer.addr.ip() {
        IpAddr::V4(v4) => u32::from_be_bytes(v4.octets()),
        IpAddr::V6(_) => 0,
    };
    KadPeer {
        node_id: peer.node_id.0,
        ip,
        port: peer.addr.port(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use nexxus_core::epoch::epoch_signing_bytes;
    use nexxus_core::types::ChunkHash;
    use nexxus_core::wire::payloads::{CommitteeSig, EpochFinalize};
    use std::net::Ipv4Addr;
    use tempfile::tempdir;
    use crate::net::routing::Peer;

    #[tokio::test]
    async fn store_then_fetch_over_network() {
        let dir = tempdir().unwrap();
        let store = Arc::new(ChunkStore::open(dir.path().join("store.redb")).unwrap());
        let our_id = NodeId([0x42u8; 32]);
        let net = Arc::new(P2pNetwork::new(our_id, "127.0.0.1:0".parse().unwrap(), store));

        let net_clone = Arc::clone(&net);
        let server = tokio::spawn(async move { net_clone.run().await });

        // wait until the listener is bound, then connect to the real port
        let mut bound = None;
        for _ in 0..100 {
            bound = net.bound_addr().await;
            if bound.is_some() {
                break;
            }
            tokio::time::sleep(std::time::Duration::from_millis(10)).await;
        }
        let listener_addr = bound.expect("listener failed to bind");

        // connect a client, announce, then StoreChunk -> FetchChunk
        let mut stream = TcpStream::connect(listener_addr).await.unwrap();
        net.announce_on(&mut stream, 0x0009).await.unwrap();
        let hash = ChunkHash([0x24u8; 32]);
        let data: Vec<u8> = (0..500).map(|i| (i % 251) as u8).collect();
        let chunk = StoreChunk {
            chunk_hash: hash,
            file_id: 1,
            chunk_index: 0,
            data: data.clone(),
        };
        net.send_signed_frame(&mut stream, Opcode::StoreChunk, 0x0001, &chunk).await.unwrap();
        let (op, rid, _payload, _sig) = crate::net::frame::recv_frame(&mut stream).await.unwrap();
        assert_eq!(op, Opcode::StoreChunkAck);
        assert_eq!(rid, 0x0001);

        let fetch = FetchChunk { hash: hash.0 };
        net.send_signed_frame(&mut stream, Opcode::FetchChunk, 0x0002, &fetch).await.unwrap();
        let (op2, rid2, payload2, _sig2) = crate::net::frame::recv_frame(&mut stream).await.unwrap();
        assert_eq!(op2, Opcode::FetchChunkResp);
        assert_eq!(rid2, 0x0002);
        let resp = FetchChunkResp::decode(&payload2).unwrap();
        assert_eq!(resp.data, data);

        server.abort();
    }

    #[tokio::test]
    async fn node_announce_roundtrip_over_wire() {
        let dir = tempdir().unwrap();
        let store = Arc::new(ChunkStore::open(dir.path().join("store.redb")).unwrap());
        let our_id = NodeId([0x43u8; 32]);
        let net = Arc::new(P2pNetwork::new(our_id, "127.0.0.1:0".parse().unwrap(), store));

        let net_clone = Arc::clone(&net);
        let server = tokio::spawn(async move { net_clone.run().await });

        let mut bound = None;
        for _ in 0..100 {
            bound = net.bound_addr().await;
            if bound.is_some() {
                break;
            }
            tokio::time::sleep(std::time::Duration::from_millis(10)).await;
        }
        let listener_addr = bound.expect("listener failed to bind");

        // client announces, server responds with its own NodeAnnounce
        let their_id = net.send_node_announce(listener_addr).await.unwrap();
        assert_eq!(their_id, our_id);

        server.abort();
    }

    #[tokio::test]
    async fn smp_envelope_over_wire() {
        let dir = tempdir().unwrap();
        let store = Arc::new(ChunkStore::open(dir.path().join("store.redb")).unwrap());
        let our_id = NodeId([0x44u8; 32]);
        let net = Arc::new(P2pNetwork::new(our_id, "127.0.0.1:0".parse().unwrap(), store));

        let net_clone = Arc::clone(&net);
        let server = tokio::spawn(async move { net_clone.run().await });

        let mut bound = None;
        for _ in 0..100 {
            bound = net.bound_addr().await;
            if bound.is_some() {
                break;
            }
            tokio::time::sleep(std::time::Duration::from_millis(10)).await;
        }
        let listener_addr = bound.expect("listener failed to bind");

        // client seals an SMP envelope to our X25519 pubkey and sends it
        let payload = b"SMP over wire test";
        let (ephemeral_pub, env) = SmpEnvelope::seal(
            [0x55u8; 32],
            our_id.0, // recipient = our node_id (used as recipient_node_id)
            &net.x25519_pub(),
            payload,
        );
        assert_eq!(&env.ciphertext[..32], &ephemeral_pub);

        net.send_smp_envelope(listener_addr, &env).await.unwrap();

        server.abort();
    }

    #[test]
    fn socket_addr_to_kad_peer_ipv4() {
        let p = Peer {
            node_id: NodeId([9u8; 32]),
            addr: SocketAddr::new(
                IpAddr::V4(Ipv4Addr::new(10, 0, 0, 1)),
                4001,
            ),
        };
        let k = socket_addr_to_kad_peer(&p);
        assert_eq!(k.node_id, [9u8; 32]);
        assert_eq!(k.ip, 0x0a000001);
        assert_eq!(k.port, 4001);
    }

    #[tokio::test]
    async fn por_challenge_response_over_wire() {
        let dir = tempdir().unwrap();
        let store = Arc::new(ChunkStore::open(dir.path().join("store.redb")).unwrap());
        let our_id = NodeId([0x45u8; 32]);
        let net = Arc::new(P2pNetwork::new(our_id, "127.0.0.1:0".parse().unwrap(), store));

        let net_clone = Arc::clone(&net);
        let server = tokio::spawn(async move { net_clone.run().await });

        let mut bound = None;
        for _ in 0..100 {
            bound = net.bound_addr().await;
            if bound.is_some() {
                break;
            }
            tokio::time::sleep(std::time::Duration::from_millis(10)).await;
        }
        let listener_addr = bound.expect("listener failed to bind");

        // server stores a chunk first
        let hash = ChunkHash([0x25u8; 32]);
        let data: Vec<u8> = (0..256).map(|i| i as u8).collect();
        net.store
            .put_chunk(&hash, &data)
            .expect("store chunk");

        // client announces, then sends PorChallenge with seed = chunk hash
        let mut stream = TcpStream::connect(listener_addr).await.unwrap();
        net.announce_on(&mut stream, 0x0009).await.unwrap();
        let challenge = PorChallenge {
            seed: hash.0,
            count: 1,
            deadline_ms: 5000,
        };
        net.send_signed_frame(
            &mut stream,
            Opcode::PorChallenge,
            0x0007,
            &challenge,
        )
        .await
        .unwrap();
        let (op, _rid, payload, _sig) = crate::net::frame::recv_frame(&mut stream).await.unwrap();
        assert_eq!(op, Opcode::PorResponse);
        let resp = PorResponse::decode(&payload).unwrap();
        assert_eq!(resp.chunk_hash, hash);

        // verify response = SHA-256(chunk_data || seed)
        let mut h = sha2::Sha256::new();
        h.update(&data);
        h.update(hash.0);
        let expected: [u8; 32] = h.finalize().into();
        assert_eq!(resp.response, expected);

        server.abort();
    }

    #[tokio::test]
    async fn epoch_finalize_over_wire() {
        let dir = tempdir().unwrap();
        let store = Arc::new(ChunkStore::open(dir.path().join("store.redb")).unwrap());
        let our_id = NodeId([0x46u8; 32]);
        // Signer must be in the auditor registry with threshold 1 (deny-by-default).
        let signer = nexxus_core::keys::identity::Identity::generate();
        let net = Arc::new(P2pNetwork::with_auditors(
            our_id,
            "127.0.0.1:0".parse().unwrap(),
            store,
            vec![signer.verifying_key],
            1,
        ));

        let net_clone = Arc::clone(&net);
        let server = tokio::spawn(async move { net_clone.run().await });

        let mut bound = None;
        for _ in 0..100 {
            bound = net.bound_addr().await;
            if bound.is_some() {
                break;
            }
            tokio::time::sleep(std::time::Duration::from_millis(10)).await;
        }
        let listener_addr = bound.expect("listener failed to bind");

        // client builds a valid EpochFinalize signed by the registered auditor
        let id = signer;
        let epoch_number: u64 = 7;
        let merkle_root = [0x33u8; 32];
        let total_bytes: u64 = 1_000_000;

        let mut msg = Vec::new();
        msg.extend_from_slice(&epoch_number.to_be_bytes());
        msg.extend_from_slice(&merkle_root);
        msg.extend_from_slice(&total_bytes.to_be_bytes());
        let sig = id.sign(&msg);

        let finalize = nexxus_core::wire::payloads::EpochFinalize {
            epoch_number,
            merkle_root,
            total_bytes,
            signatures: vec![nexxus_core::wire::payloads::CommitteeSig {
                pubkey: id.verifying_key.to_bytes(),
                signature: sig,
            }],
        };

        let mut stream = TcpStream::connect(listener_addr).await.unwrap();
        net.announce_on(&mut stream, 0x0009).await.unwrap();
        net.send_signed_frame(&mut stream, Opcode::EpochFinalize, 0x0008, &finalize)
            .await
            .unwrap();
        let (op, _rid, _payload, _sig) = crate::net::frame::recv_frame(&mut stream).await.unwrap();
        assert_eq!(op, Opcode::Pong); // valid multi-sig -> Pong

        server.abort();
    }

    #[tokio::test]
    async fn epoch_finalize_denied_without_committee_over_wire() {
        // Deny-by-default: empty auditor registry -> even a well-formed,
        // correctly signed EpochFinalize is rejected with ErrorResponse.
        let dir = tempdir().unwrap();
        let store = Arc::new(ChunkStore::open(dir.path().join("store.redb")).unwrap());
        let our_id = NodeId([0x47u8; 32]);
        let net = Arc::new(P2pNetwork::new(our_id, "127.0.0.1:0".parse().unwrap(), store));

        let net_clone = Arc::clone(&net);
        let server = tokio::spawn(async move { net_clone.run().await });

        let mut bound = None;
        for _ in 0..100 {
            bound = net.bound_addr().await;
            if bound.is_some() {
                break;
            }
            tokio::time::sleep(std::time::Duration::from_millis(10)).await;
        }
        let listener_addr = bound.expect("listener failed to bind");

        let id = nexxus_core::keys::identity::Identity::generate();
        let epoch_number: u64 = 7;
        let merkle_root = [0x33u8; 32];
        let total_bytes: u64 = 1_000_000;
        let mut msg = Vec::new();
        msg.extend_from_slice(&epoch_number.to_be_bytes());
        msg.extend_from_slice(&merkle_root);
        msg.extend_from_slice(&total_bytes.to_be_bytes());
        let sig = id.sign(&msg);
        let finalize = nexxus_core::wire::payloads::EpochFinalize {
            epoch_number,
            merkle_root,
            total_bytes,
            signatures: vec![nexxus_core::wire::payloads::CommitteeSig {
                pubkey: id.verifying_key.to_bytes(),
                signature: sig,
            }],
        };

        let mut stream = TcpStream::connect(listener_addr).await.unwrap();
        net.announce_on(&mut stream, 0x0009).await.unwrap();
        net.send_signed_frame(&mut stream, Opcode::EpochFinalize, 0x0008, &finalize)
            .await
            .unwrap();
        let (op, _rid, _payload, _sig) = crate::net::frame::recv_frame(&mut stream).await.unwrap();
        assert_eq!(op, Opcode::ErrorResponse); // no committee -> denied

        server.abort();
    }

    #[tokio::test]
    async fn kad_find_node_over_wire() {
        let dir = tempdir().unwrap();
        let store = Arc::new(ChunkStore::open(dir.path().join("store.redb")).unwrap());
        let our_id = NodeId([0x47u8; 32]);
        let net = Arc::new(P2pNetwork::new(our_id, "127.0.0.1:0".parse().unwrap(), store));

        // register a known peer in the server routing table
        let peer = crate::net::routing::Peer {
            node_id: NodeId([0x48u8; 32]),
            addr: "127.0.0.1:4002".parse().unwrap(),
        };
        net.register_peer(peer).await;

        let net_clone = Arc::clone(&net);
        let server = tokio::spawn(async move { net_clone.run().await });

        let mut bound = None;
        for _ in 0..100 {
            bound = net.bound_addr().await;
            if bound.is_some() {
                break;
            }
            tokio::time::sleep(std::time::Duration::from_millis(10)).await;
        }
        let listener_addr = bound.expect("listener failed to bind");

        // client dials KadFindNode -> expects KadNodesFound with the registered peer
        let target = NodeId([0x99u8; 32]);
        let found = net.dial_find_node(listener_addr, target, 5).await.unwrap();
        assert_eq!(found.len(), 1);
        assert_eq!(found[0].node_id, [0x48u8; 32]);
        assert_eq!(found[0].port, 4002);

        server.abort();
    }

    #[tokio::test]
    async fn two_daemon_end_to_end() {
        // Daemon A
        let dir_a = tempdir().unwrap();
        let store_a = Arc::new(ChunkStore::open(dir_a.path().join("store.redb")).unwrap());
        let id_a = NodeId([0x61u8; 32]);
        let net_a = Arc::new(P2pNetwork::new(id_a, "127.0.0.1:0".parse().unwrap(), store_a));
        let net_a_clone = Arc::clone(&net_a);
        let server_a = tokio::spawn(async move { net_a_clone.run().await });

        // Daemon B
        let dir_b = tempdir().unwrap();
        let store_b = Arc::new(ChunkStore::open(dir_b.path().join("store.redb")).unwrap());
        let id_b = NodeId([0x62u8; 32]);
        // B's committee: the test signer is the sole auditor, threshold 1.
        let signer_b = nexxus_core::keys::identity::Identity::generate();
        let net_b = Arc::new(P2pNetwork::with_auditors(
            id_b,
            "127.0.0.1:0".parse().unwrap(),
            store_b,
            vec![signer_b.verifying_key],
            1,
        ));
        let net_b_clone = Arc::clone(&net_b);
        let server_b = tokio::spawn(async move { net_b_clone.run().await });

        // Wait for both to bind
        let mut bound_a = None;
        for _ in 0..100 {
            bound_a = net_a.bound_addr().await;
            if bound_a.is_some() {
                break;
            }
            tokio::time::sleep(std::time::Duration::from_millis(10)).await;
        }
        let addr_a = bound_a.expect("daemon A failed to bind");

        let mut bound_b = None;
        for _ in 0..100 {
            bound_b = net_b.bound_addr().await;
            if bound_b.is_some() {
                break;
            }
            tokio::time::sleep(std::time::Duration::from_millis(10)).await;
        }
        let addr_b = bound_b.expect("daemon B failed to bind");

        // A announces to B -> B learns A's node_id
        let learned_a = net_b.send_node_announce(addr_a).await.unwrap();
        assert_eq!(learned_a, id_a);

        // B announces to A -> A learns B's node_id
        let learned_b = net_a.send_node_announce(addr_b).await.unwrap();
        assert_eq!(learned_b, id_b);

        // B stores a chunk
        let hash = ChunkHash([0x77u8; 32]);
        let data: Vec<u8> = (0..100).map(|i| i as u8).collect();
        net_b.store.put_chunk(&hash, &data).expect("store chunk");

        // A fetches the chunk from B
        let fetched = net_a.fetch_chunk_from_peer(addr_b, hash).await.unwrap();
        assert_eq!(fetched, data);
        // A now has it locally too
        let local = net_a.store.get_chunk(&hash).unwrap().unwrap();
        assert_eq!(local, data);

        // A sends an SMP envelope to B
        let payload = b"E2E SMP test";
        let (ephemeral, env) = SmpEnvelope::seal(
            id_a.0,
            id_b.0,
            &net_b.x25519_pub(),
            payload,
        );
        assert_eq!(&env.ciphertext[..32], &ephemeral);
        net_a.send_smp_envelope(addr_b, &env).await.unwrap();

        // A sends EpochFinalize to B — B verifies it against its committee
        // (signer_b registered with threshold 1) and accepts with Pong.
        let id_signer = signer_b;
        let epoch_number: u64 = 1;
        let merkle_root = [0x55u8; 32];
        let total_bytes: u64 = 42;
        let msg = epoch_signing_bytes(epoch_number, &merkle_root, total_bytes);
        let sig = id_signer.sign(&msg);
        let finalize = EpochFinalize {
            epoch_number,
            merkle_root,
            total_bytes,
            signatures: vec![CommitteeSig {
                pubkey: id_signer.verifying_key.to_bytes(),
                signature: sig,
            }],
        };
        let result = net_a.send_epoch_finalize(addr_b, &finalize).await;
        assert!(result.is_ok());

        server_a.abort();
        server_b.abort();
    }

    async fn spawn_bound(our_id_byte: u8) -> (Arc<P2pNetwork>, SocketAddr, tokio::task::JoinHandle<Result<(), NexxusError>>) {
        let dir = tempdir().unwrap();
        let store = Arc::new(ChunkStore::open(dir.path().join("store.redb")).unwrap());
        let our_id = NodeId([our_id_byte; 32]);
        let net = Arc::new(P2pNetwork::new(our_id, "127.0.0.1:0".parse().unwrap(), store));
        let net_clone = Arc::clone(&net);
        let server = tokio::spawn(async move { net_clone.run().await });
        let mut bound = None;
        for _ in 0..100 {
            bound = net.bound_addr().await;
            if bound.is_some() {
                break;
            }
            tokio::time::sleep(std::time::Duration::from_millis(10)).await;
        }
        let listener_addr = bound.expect("listener failed to bind");
        (net, listener_addr, server)
    }

    #[tokio::test]
    async fn unannounced_frame_is_rejected() {
        let (net, listener_addr, server) = spawn_bound(0x51).await;
        // Ping without prior NodeAnnounce must be rejected with 0x0006
        let mut stream = TcpStream::connect(listener_addr).await.unwrap();
        net.send_signed_frame(&mut stream, Opcode::Ping, 0x0001, &nexxus_core::wire::payloads::Ping)
            .await
            .unwrap();
        let (op, _rid, payload, _sig) = crate::net::frame::recv_frame(&mut stream).await.unwrap();
        assert_eq!(op, Opcode::ErrorResponse);
        let err = ErrorResponse::decode(&payload).unwrap();
        assert_eq!(err.code, 0x0006);
        server.abort();
    }

    #[tokio::test]
    async fn tampered_frame_signature_is_rejected() {
        let (net, listener_addr, server) = spawn_bound(0x52).await;
        let mut stream = TcpStream::connect(listener_addr).await.unwrap();
        // valid announce first, so the connection has a peer key
        net.announce_on(&mut stream, 0x0001).await.unwrap();
        // well-formed frame after the announce, but the 64-byte signature is
        // garbage: must be rejected with 0x0008 and never dispatched
        send_frame(
            &mut stream,
            Opcode::Ping,
            0x0002,
            &nexxus_core::wire::payloads::Ping,
            &[0x42u8; 64],
        )
        .await
        .unwrap();
        let (op, _rid, payload, _sig) = crate::net::frame::recv_frame(&mut stream).await.unwrap();
        assert_eq!(op, Opcode::ErrorResponse);
        let err = ErrorResponse::decode(&payload).unwrap();
        assert_eq!(err.code, 0x0008);
        server.abort();
    }

    #[tokio::test]
    async fn pause_blocks_frames_and_resume_restores() {
        let (net, listener_addr, server) = spawn_bound(0x53).await;
        let mut stream = TcpStream::connect(listener_addr).await.unwrap();
        net.announce_on(&mut stream, 0x0001).await.unwrap();
        let ping = nexxus_core::wire::payloads::Ping;
        // normal ping -> pong
        net.send_signed_frame(&mut stream, Opcode::Ping, 0x0002, &ping).await.unwrap();
        let (op, _, _, _) = crate::net::frame::recv_frame(&mut stream).await.unwrap();
        assert_eq!(op, Opcode::Pong);
        // pause -> ping rejected with 0x0007
        net.set_paused(true);
        assert!(net.is_paused());
        net.send_signed_frame(&mut stream, Opcode::Ping, 0x0003, &ping).await.unwrap();
        let (op, _, payload, _) = crate::net::frame::recv_frame(&mut stream).await.unwrap();
        assert_eq!(op, Opcode::ErrorResponse);
        assert_eq!(ErrorResponse::decode(&payload).unwrap().code, 0x0007);
        // resume -> pong again
        net.set_paused(false);
        assert!(!net.is_paused());
        net.send_signed_frame(&mut stream, Opcode::Ping, 0x0004, &ping).await.unwrap();
        let (op, _, _, _) = crate::net::frame::recv_frame(&mut stream).await.unwrap();
        assert_eq!(op, Opcode::Pong);
        server.abort();
    }

    #[tokio::test]
    async fn smp_envelope_routed_and_delivered_to_inbox() {
        // Two nodes A and B. A learns B via announce, then routes an SMP
        // envelope to B; B must receive the decrypted plaintext in its inbox.
        let (net_a, addr_a, server_a) = spawn_bound(0x61).await;
        let (net_b, addr_b, server_b) = spawn_bound(0x62).await;
        let _ = addr_a;

        let (tx, mut rx) = mpsc::unbounded_channel();
        net_b.set_smp_inbox(tx).await;

        // A announces to B -> both routing tables learn each other
        let their = net_a.send_node_announce(addr_b).await.unwrap();
        assert_eq!(their, net_b.node_id());

        let id_a = net_a.node_id();
        let id_b = net_b.node_id();
        let payload = b"hello smp over routing";
        let (_eph, env) = SmpEnvelope::seal(id_a.0, id_b.0, &net_b.x25519_pub(), payload);

        // route via A's Kademlia table (must find B and deliver)
        net_a.route_smp_envelope(&env).await.unwrap();

        let msg = tokio::time::timeout(std::time::Duration::from_secs(5), rx.recv())
            .await
            .expect("timeout waiting for inbound smp")
            .expect("inbox closed");
        assert_eq!(msg.plaintext, payload);
        assert_eq!(msg.sender_node_id, id_a.0);
        assert_eq!(msg.recipient_node_id, id_b.0);

        // no route case: unknown recipient -> error, not a panic
        let (_eph2, env2) = SmpEnvelope::seal(id_a.0, [0x77u8; 32], &net_b.x25519_pub(), b"x");
        let (net_c, _addr_c, server_c) = spawn_bound(0x63).await;
        let err = net_c.route_smp_envelope(&env2).await.unwrap_err();
        assert!(err.to_string().contains("no route"));

        server_a.abort();
        server_b.abort();
        server_c.abort();
    }
}
