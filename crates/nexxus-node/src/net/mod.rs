//! P2P transport over TCP with Kademlia routing (ADR-0001/0002 wire v3).
//! Phase 7: bind/listen, dial, length-delimited frame codec, k-buckets,
//! opcode dispatcher (Ping/Pong, KadFindNode/KadNodesFound, StoreChunk/FetchChunk).

pub mod frame;
pub mod network;
pub mod routing;

pub use network::P2pNetwork;
