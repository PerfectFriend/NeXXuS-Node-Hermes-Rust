//! P2pNetwork: bind/listen, dial, routing table, opcode dispatcher.
//! Integrates with ChunkStore (redb) for StoreChunk/FetchChunk.
#![allow(dead_code)]
#![allow(unused_imports)]

use std::net::{IpAddr, SocketAddr};
use std::sync::Arc;

use nexxus_core::{
    error::NexxusError,
    types::NodeId,
    wire::opcode::Opcode,
    wire::payloads::{
        ErrorResponse, FetchChunk, FetchChunkResp, KadFindNode, KadNodesFound, KadPeer, Payload,
        StoreChunk, StoreChunkAck,
    },
};
use crate::storage::ChunkStore;
use tokio::net::{TcpListener, TcpStream};
use tokio::sync::Mutex;
use tokio::task;

use crate::net::frame::MAX_FRAME_LEN;

/// Connected peer tracked for the lifetime of a stream.
struct ConnectedPeer {
    node_id: Option<NodeId>,
    addr: SocketAddr,
}

/// P2P network node. Holds routing table + chunk store, accepts inbound
/// connections and dials outbound peers.
#[allow(dead_code)]
pub struct P2pNetwork {
    our_id: NodeId,
    listen_addr: SocketAddr,
    bound_addr: Arc<Mutex<Option<SocketAddr>>>,
    routing: Arc<Mutex<crate::net::routing::RoutingTable>>,
    store: Arc<ChunkStore>,
}

impl P2pNetwork {
    pub fn new(our_id: NodeId, listen_addr: SocketAddr, store: Arc<ChunkStore>) -> Self {
        Self {
            our_id,
            listen_addr,
            bound_addr: Arc::new(Mutex::new(None)),
            routing: Arc::new(Mutex::new(crate::net::routing::RoutingTable::new(our_id))),
            store,
        }
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
                // Phase 8: node-id + address registration
                let _err = ErrorResponse {
                    code: 0x0001,
                    message: "NodeAnnounce not implemented in Phase 7".into(),
                };
                crate::net::frame::send_frame(stream, Opcode::ErrorResponse, request_id, &_err).await?;
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
                let hash = nexxus_core::types::ChunkHash(fetch.hash);
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
            Opcode::PorChallenge | Opcode::PorResponse => {
                // PoR handled by verifier in Phase 8
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
                // also insert announcing peer into routing table (we don't know
                // its node id yet without handshake, skip in Phase 7)
            }
            Opcode::EpochFinalize | Opcode::SmpEnvelope => {
                // relay/verify handled by upper layers in Phase 8
                let err = ErrorResponse {
                    code: 0x0003,
                    message: "opcode not handled by Phase 7 dispatcher".into(),
                };
                crate::net::frame::send_frame(stream, Opcode::ErrorResponse, request_id, &err).await?;
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
}
