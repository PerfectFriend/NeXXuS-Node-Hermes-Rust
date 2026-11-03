//! Kademlia routing table: k-buckets over NodeId XOR distance.
//! Pure logic — no I/O, deterministic, fully unit-testable.
#![allow(dead_code)]

use std::array;
use std::collections::VecDeque;
use std::net::SocketAddr;

use nexxus_core::types::NodeId;

/// Max peers per k-bucket.
const K: usize = 20;
/// Number of k-buckets (32 bytes × 8 bits).
const BUCKETS: usize = 256;

/// Known peer: node id + socket address.
#[derive(Clone, Debug)]
pub struct Peer {
    pub node_id: NodeId,
    pub addr: SocketAddr,
}

/// Kademlia routing table keyed by XOR distance from our NodeId.
#[derive(Clone, Debug)]
pub struct RoutingTable {
    buckets: [VecDeque<Peer>; BUCKETS],
    our_id: NodeId,
}

impl RoutingTable {
    pub fn new(our_id: NodeId) -> Self {
        Self {
            buckets: array::from_fn(|_| VecDeque::new()),
            our_id,
        }
    }

    pub fn our_id(&self) -> NodeId {
        self.our_id
    }

    /// Bucket index = position of the most significant differing bit between
    /// `peer_id` and `our_id` (255 = closest possible, 0 = farthest).
    pub fn bucket_index(peer_id: &NodeId, our_id: &NodeId) -> usize {
        let mut idx: usize = 0;
        for i in 0..32 {
            let x = peer_id.0[i] ^ our_id.0[i];
            if x != 0 {
                idx = i * 8 + (8 - x.leading_zeros() as usize);
                break;
            }
        }
        idx.min(BUCKETS - 1)
    }

    /// Insert or refresh a peer. Existing peer is moved to the front (most
    /// recently seen). Full buckets drop the new peer (replacement cache
    /// omitted in Phase 7).
    pub fn insert(&mut self, peer: Peer) {
        if peer.node_id == self.our_id {
            return;
        }
        let idx = Self::bucket_index(&peer.node_id, &self.our_id);
        let bucket = &mut self.buckets[idx];
        if let Some(pos) = bucket.iter().position(|p| p.node_id == peer.node_id) {
            bucket.remove(pos);
            bucket.push_front(peer);
            return;
        }
        if bucket.len() < K {
            bucket.push_front(peer);
        }
        // bucket full: silently drop (replacement cache in Phase 8)
    }

    /// `count` closest peers to `target`, ordered by XOR distance (closest first).
    pub fn find_node(&self, target: &NodeId, count: usize) -> Vec<Peer> {
        let mut scored: Vec<(u128, Peer)> = self
            .buckets
            .iter()
            .flat_map(|b| b.iter().cloned())
            .map(|p| (xor_distance(&p.node_id, target), p))
            .collect();
        scored.sort_by_key(|(d, _)| *d);
        scored
            .into_iter()
            .take(count)
            .map(|(_, p)| p)
            .collect()
    }

    /// All known peers (most-recent-first within each bucket).
    pub fn peers(&self) -> Vec<Peer> {
        self.buckets.iter().flat_map(|b| b.iter().cloned()).collect()
    }

    pub fn bucket_len(&self, idx: usize) -> usize {
        self.buckets[idx].len()
    }
}

/// XOR distance folded to u128 for ordering (full 256-bit XOR, consistent with smp/mod.rs).
fn xor_distance(a: &NodeId, b: &NodeId) -> u128 {
    let mut acc: u128 = 0;
    for i in 0..32 {
        acc = (acc << 8) | (a.0[i] ^ b.0[i]) as u128;
    }
    acc
}

#[cfg(test)]
mod tests {
    use super::*;

    use std::net::{IpAddr, Ipv4Addr};

    fn nid(b: u8) -> NodeId {
        let mut a = [0u8; 32];
        a[31] = b;
        NodeId(a)
    }

    fn addr(port: u16) -> SocketAddr {
        SocketAddr::new(IpAddr::V4(Ipv4Addr::new(127, 0, 0, 1)), port)
    }

    #[test]
    fn insert_and_find_closest() {
        let mut rt = RoutingTable::new(nid(0x00));
        for i in 1..=40u8 {
            rt.insert(Peer {
                node_id: nid(i),
                addr: addr(i as u16),
            });
        }
        let closest = rt.find_node(&nid(0x00), 5);
        assert!(!closest.is_empty());
        assert!(closest.len() <= 5);
        // closest to 0x00 is lowest id
        assert_eq!(closest[0].node_id, nid(1));
    }

    #[test]
    fn insert_moves_to_front() {
        let mut rt = RoutingTable::new(nid(0x00));
        rt.insert(Peer {
            node_id: nid(5),
            addr: addr(5),
        });
        rt.insert(Peer {
            node_id: nid(6),
            addr: addr(6),
        });
        rt.insert(Peer {
            node_id: nid(5),
            addr: addr(55),
        });
        let peers = rt.peers();
        assert_eq!(peers[0].node_id, nid(5));
        assert_eq!(peers[0].addr, addr(55));
        assert_eq!(peers[1].node_id, nid(6));
    }

    #[test]
    fn bucket_capacity_k() {
        let mut rt = RoutingTable::new(nid(0xff));
        for i in 0..(K as u8 + 5) {
            rt.insert(Peer {
                node_id: nid(i),
                addr: addr(i as u16),
            });
        }
        let idx = RoutingTable::bucket_index(&nid(0), &nid(0xff));
        assert!(rt.bucket_len(idx) <= K);
    }

    #[test]
    fn bucket_index_spread() {
        // nid(0x01) vs our nid(0x00): XOR=1 -> MSB at bit 6 of last byte -> idx 249
        assert_eq!(
            RoutingTable::bucket_index(&nid(0x01), &nid(0x00)),
            31 * 8 + 1
        );
        // nid(0x80) vs our nid(0x00): XOR=0x80 -> MSB at bit 7 -> idx 255 (clamped)
        assert_eq!(
            RoutingTable::bucket_index(&nid(0x80), &nid(0x00)),
            255
        );
        // identical ids -> idx 0 (no differing bit)
        assert_eq!(RoutingTable::bucket_index(&nid(0x00), &nid(0x00)), 0);
    }
}
