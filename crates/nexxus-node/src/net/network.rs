//! P2pNetwork: bind/listen, dial, routing table, opcode dispatcher.
//! Integrates with ChunkStore (redb) for StoreChunk/FetchChunk.
//! Phase 8: full protocol — NodeAnnounce, SmpEnvelope, EpochFinalize,
//! PorChallenge/Response, StoreChunkAck, FetchChunkResp.
#![allow(dead_code)]
#![allow(unused_imports)]

use std::net::{IpAddr, SocketAddr};
use std::sync::Arc;

use curve25519_dalek::MontgomeryPoint;
use ed25519_dalek::{Signer, Verifier, VerifyingKey};
use nexxus_core::{
    error::NexxusError,
    keys::identity::Identity,
    types::{ChunkHash, NodeId},
    wire::opcode::Opcode,
    wire::payloads::{
        ErrorResponse, FetchChunk, FetchChunkResp, KadFindNode, KadNodesFound, KadPeer, NodeAnnounce,
        Payload, PorChallenge, PorResponse, SmpEnvelope, StoreChunk, StoreChunkAck,
    },
    wire::payloads::X25519_BASEPOINT,
};
use crate::net::frame::MAX_FRAME_LEN;
use crate::storage::ChunkStore;
use rand::rngs::OsRng;
use rand::Rng;
use sha2::{Digest, Sha256};
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::Mutex;
use tokio::task;

/// Connected peer tracked for the lifetime of a stream.
struct ConnectedPeer {
    node_id: Option<NodeId>,
    addr: SocketAddr,
}

/// P2P network node. Holds identity (Ed25519 + X25519), routing table +
/// chunk store, accepts inbound connections and dials outbound peers.
#[allow(dead_code)]
pub struct P2pNetwork {
    our_id: NodeId,
    identity: Identity,
    x25519_secret: [u8; 32],
    x25519_pub: MontgomeryPoint,
    listen_addr: SocketAddr,
    bound_addr: Arc<Mutex<Option<SocketAddr>>>,
    routing: Arc<Mutex<crate::net::routing::RoutingTable>>,
    store: Arc<ChunkStore>,
}

impl P2pNetwork {
    /// Create a new node with a fresh Ed25519 identity and X25519 key pair.
    pub fn new(our_id: NodeId, listen_addr: SocketAddr, store: Arc<ChunkStore>) -> Self {
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
        }
    }

    /// Create from an existing identity + X25519 keys (for reconnect/restart).
    pub fn with_keys(
        our_id: NodeId,
        identity: Identity,
        x25519_secret: [u8; 32],
        listen_addr: SocketAddr,
        store: Arc<ChunkStore>,
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
        }
    }

    /// Ed25519 verifying key (our node public key).
    pub fn verifying_key(&self) -> VerifyingKey {
        self.identity.verifying_key
    }

    /// Static X25519 public key (for SMP envelope sealing by peers).
    pub fn x25519_pub(&self) -> MontgomeryPoint {
        self.x25519_pub
    }

    /// Actual address the listener is bound to (None until `run()` binds).
    pub async fn bound_addr(&self) -> Option<SocketAddr> {
        *self.bound_addr.lock().await
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
        let query = KadFindNode {
            target_node_id: target.0,
            count,
        };
        crate::net::frame::send_frame(&mut stream, Opcode::KadFindNode, 0x0001, &query)
            .await?;
        let (op, _rid, payload) = crate::net::frame::recv_frame(&mut stream).await?;
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
    pub async fn dial_announce(&self, addr: SocketAddr) -> Result<(), NexxusError> {
        let mut stream = TcpStream::connect(addr)
            .await
            .map_err(|e| NexxusError::Io(e.to_string()))?;
        let query = KadFindNode {
            target_node_id: self.our_id.0,
            count: 1,
        };
        crate::net::frame::send_frame(&mut stream, Opcode::KadFindNode, 0x0002, &query).await?;
        let _ = crate::net::frame::recv_frame(&mut stream).await?;
        Ok(())
    }

    /// Send our NodeAnnounce to a peer and learn their node_id in return.
    pub async fn send_node_announce(&self, addr: SocketAddr) -> Result<NodeId, NexxusError> {
        let mut stream = TcpStream::connect(addr)
            .await
            .map_err(|e| NexxusError::Io(e.to_string()))?;
        let announce = NodeAnnounce {
            node_id: self.our_id.0,
            ip: match self.listen_addr.ip() {
                IpAddr::V4(v4) => u32::from_be_bytes(v4.octets()),
                IpAddr::V6(_) => 0,
            },
            port: self.listen_addr.port(),
        };
        crate::net::frame::send_frame(
            &mut stream,
            Opcode::NodeAnnounce,
            0x0003,
            &announce,
        )
        .await?;
        let (op, _rid, payload) = crate::net::frame::recv_frame(&mut stream).await?;
        if op != Opcode::NodeAnnounce {
            return Err(NexxusError::Io(format!(
                "expected NodeAnnounce, got opcode 0x{:02x}",
                op.to_u8()
            )));
        }
        let their = NodeAnnounce::decode(&payload)?;
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
        let fetch = FetchChunk { hash: hash.0 };
        crate::net::frame::send_frame(&mut stream, Opcode::FetchChunk, 0x0004, &fetch)
            .await?;
        let (op, _rid, payload) = crate::net::frame::recv_frame(&mut stream).await?;
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
        crate::net::frame::send_frame(&mut stream, Opcode::SmpEnvelope, 0x0005, env)
            .await?;
        let (op, _rid, _payload) = crate::net::frame::recv_frame(&mut stream).await?;
        if op == Opcode::ErrorResponse {
            let err = ErrorResponse::decode(&_payload)?;
            return Err(NexxusError::Io(format!(
                "peer error: code={} msg={}",
                err.code, err.message
            )));
        }
        Ok(())
    }

    /// Send an EpochFinalize (committee multi-sig) to a peer.
    pub async fn send_epoch_finalize(&self, addr: SocketAddr, finalize: &nexxus_core::wire::payloads::EpochFinalize) -> Result<(), NexxusError> {
        let mut stream = TcpStream::connect(addr)
            .await
            .map_err(|e| NexxusError::Io(e.to_string()))?;
        crate::net::frame::send_frame(&mut stream, Opcode::EpochFinalize, 0x0006, finalize)
            .await?;
        let (op, _rid, _payload) = crate::net::frame::recv_frame(&mut stream).await?;
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
        _peer: ConnectedPeer,
    ) -> Result<(), NexxusError> {
        loop {
            let (opcode, req_id, payload) = match crate::net::frame::recv_frame(&mut stream).await {
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
            self.handle_opcode(&mut stream, opcode, req_id, &payload).await?;
        }
    }

    async fn handle_opcode(
        &self,
        stream: &mut TcpStream,
        opcode: Opcode,
        request_id: u32,
        payload: &[u8],
    ) -> Result<(), NexxusError> {
        match opcode {
            Opcode::Ping => {
                let _ping = nexxus_core::wire::payloads::Ping::decode(payload)?;
                let pong = nexxus_core::wire::payloads::Pong;
                crate::net::frame::send_frame(stream, Opcode::Pong, request_id, &pong).await?;
            }
            Opcode::Pong => {
                // unsolicited pong: nothing to do
            }
            Opcode::NodeAnnounce => {
                let announce = NodeAnnounce::decode(payload)?;
                let their_id = NodeId(announce.node_id);
                let their_addr = SocketAddr::new(
                    IpAddr::V4(std::net::Ipv4Addr::from(u32::from_be(announce.ip))),
                    announce.port,
                );
                // insert announcing peer into routing table
                let peer = crate::net::routing::Peer {
                    node_id: their_id,
                    addr: their_addr,
                };
                self.routing.lock().await.insert(peer);

                // respond with our own NodeAnnounce
                let our_announce = NodeAnnounce {
                    node_id: self.our_id.0,
                    ip: match self.listen_addr.ip() {
                        IpAddr::V4(v4) => u32::from_be_bytes(v4.octets()),
                        IpAddr::V6(_) => 0,
                    },
                    port: self.listen_addr.port(),
                };
                crate::net::frame::send_frame(stream, Opcode::NodeAnnounce, request_id, &our_announce)
                    .await?;
            }
            Opcode::StoreChunk => {
                let chunk = StoreChunk::decode(payload)?;
                self.store.put_chunk(&chunk.chunk_hash, &chunk.data)?;
                let ack = StoreChunkAck { hash: chunk.chunk_hash.0 };
                crate::net::frame::send_frame(stream, Opcode::StoreChunkAck, request_id, &ack).await?;
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
                    crate::net::frame::send_frame(stream, Opcode::FetchChunkResp, request_id, &resp).await?;
                } else {
                    let err = ErrorResponse {
                        code: 0x0002,
                        message: "chunk not found".into(),
                    };
                    crate::net::frame::send_frame(stream, Opcode::ErrorResponse, request_id, &err).await?;
                }
            }
            Opcode::FetchChunkResp => {
                // inbound response handled by request originator in Phase 8
            }
            Opcode::PorChallenge => {
                let challenge = PorChallenge::decode(payload)?;
                // Find the chunk by hash — challenge.seed is used as chunk hash in Phase 8
                let hash = ChunkHash(challenge.seed);
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
                    crate::net::frame::send_frame(stream, Opcode::PorResponse, request_id, &resp).await?;
                } else {
                    let err = ErrorResponse {
                        code: 0x0003,
                        message: "chunk not found for PoR".into(),
                    };
                    crate::net::frame::send_frame(stream, Opcode::ErrorResponse, request_id, &err).await?;
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
                crate::net::frame::send_frame(stream, Opcode::KadNodesFound, request_id, &nodes).await?;
            }
            Opcode::KadNodesFound => {
                // inbound nodes found handled by request originator in Phase 8
            }
            Opcode::SmpEnvelope => {
                let env = SmpEnvelope::decode(payload)?;
                match env.open(&self.x25519_secret) {
                    Ok(plaintext) => {
                        // deliver plaintext to upper layer (Phase 8: store/deliver)
                        let _ = plaintext;
                        let pong = nexxus_core::wire::payloads::Pong;
                        crate::net::frame::send_frame(stream, Opcode::Pong, request_id, &pong).await?;
                    }
                    Err(_) => {
                        let err = ErrorResponse {
                            code: 0x0004,
                            message: "smp envelope decrypt failed".into(),
                        };
                        crate::net::frame::send_frame(stream, Opcode::ErrorResponse, request_id, &err).await?;
                    }
                }
            }
            Opcode::EpochFinalize => {
                let finalize = nexxus_core::wire::payloads::EpochFinalize::decode(payload)?;
                // Verify each committee signature against its pubkey
                let mut valid = true;
                for sig in &finalize.signatures {
                    let vk = match VerifyingKey::from_bytes(&sig.pubkey) {
                        Ok(vk) => vk,
                        Err(_) => {
                            valid = false;
                            break;
                        }
                    };
                    let mut msg = Vec::new();
                    msg.extend_from_slice(&finalize.epoch_number.to_be_bytes());
                    msg.extend_from_slice(&finalize.merkle_root);
                    msg.extend_from_slice(&finalize.total_bytes.to_be_bytes());
                    if !Identity::verify(&vk, &msg, &sig.signature) {
                        valid = false;
                        break;
                    }
                }
                if valid {
                    let pong = nexxus_core::wire::payloads::Pong;
                    crate::net::frame::send_frame(stream, Opcode::Pong, request_id, &pong).await?;
                } else {
                    let err = ErrorResponse {
                        code: 0x0005,
                        message: "epoch finalize multi-sig verification failed".into(),
                    };
                    crate::net::frame::send_frame(stream, Opcode::ErrorResponse, request_id, &err).await?;
                }
            }
            Opcode::ErrorResponse => {
                // upstream logs the error; nothing to do here
            }
        }
        Ok(())
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

    use nexxus_core::types::ChunkHash;
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

        // connect a client and StoreChunk -> FetchChunk
        let mut stream = TcpStream::connect(listener_addr).await.unwrap();
        let hash = ChunkHash([0x24u8; 32]);
        let data: Vec<u8> = (0..500).map(|i| (i % 251) as u8).collect();
        let chunk = StoreChunk {
            chunk_hash: hash,
            file_id: 1,
            chunk_index: 0,
            data: data.clone(),
        };
        crate::net::frame::send_frame(&mut stream, Opcode::StoreChunk, 0x0001, &chunk).await.unwrap();
        let (op, rid, _payload) = crate::net::frame::recv_frame(&mut stream).await.unwrap();
        assert_eq!(op, Opcode::StoreChunkAck);
        assert_eq!(rid, 0x0001);

        let fetch = FetchChunk { hash: hash.0 };
        crate::net::frame::send_frame(&mut stream, Opcode::FetchChunk, 0x0002, &fetch).await.unwrap();
        let (op2, rid2, payload2) = crate::net::frame::recv_frame(&mut stream).await.unwrap();
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

        // client sends PorChallenge with seed = chunk hash
        let mut stream = TcpStream::connect(listener_addr).await.unwrap();
        let challenge = PorChallenge {
            seed: hash.0,
            count: 1,
            deadline_ms: 5000,
        };
        crate::net::frame::send_frame(
            &mut stream,
            Opcode::PorChallenge,
            0x0007,
            &challenge,
        )
        .await
        .unwrap();
        let (op, _rid, payload) = crate::net::frame::recv_frame(&mut stream).await.unwrap();
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

        // client builds a valid EpochFinalize with one Ed25519 signature
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
        crate::net::frame::send_frame(&mut stream, Opcode::EpochFinalize, 0x0008, &finalize)
            .await
            .unwrap();
        let (op, _rid, _payload) = crate::net::frame::recv_frame(&mut stream).await.unwrap();
        assert_eq!(op, Opcode::Pong); // valid multi-sig -> Pong

        server.abort();
    }
}
