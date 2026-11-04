//! SMP (Secure Message Protocol) relay — ADR-0007.
//! Kademlia-based routing of encrypted envelopes to the closest peers to
//! `recipient_node_id`, with pending-envelope storage and TTL.
//! Pure logic — no I/O, compiles to wasm32 unchanged.

use crate::error::NexxusError;
use crate::types::NodeId;
use crate::wire::payloads::SmpEnvelope;
use std::collections::BTreeMap;
use std::time::{Duration, Instant};

/// A pending (undelivered) SMP envelope with expiry.
#[derive(Debug, Clone)]
struct PendingEnvelope {
    env: SmpEnvelope,
    expires_at: Instant,
}

/// XOR distance between two NodeIds (closer = smaller).
fn xor_distance(a: &NodeId, b: &NodeId) -> u128 {
    let mut d = 0u128;
    for i in 0..32 {
        d = (d << 8) | (a.0[i] as u128 ^ b.0[i] as u128);
    }
    d
}

/// SMP relay table: maps recipient node_id -> pending envelopes.
/// Peers are tracked by their NodeId; routing picks the closest known peer
/// to the target recipient.
#[derive(Debug, Clone, Default)]
pub struct SmpRelay {
    /// recipient_node_id -> pending envelopes (ordered by expiry)
    pending: BTreeMap<NodeId, Vec<PendingEnvelope>>,
    /// known peers: node_id -> last seen
    peers: BTreeMap<NodeId, Instant>,
    ttl: Duration,
}

impl SmpRelay {
    pub fn new(ttl: Duration) -> Self {
        Self {
            pending: BTreeMap::new(),
            peers: BTreeMap::new(),
            ttl,
        }
    }

    /// Register that we know about a peer (used for routing decisions).
    pub fn register_peer(&mut self, node_id: NodeId) {
        self.peers.insert(node_id, Instant::now());
    }

    /// Store an envelope for later delivery to `recipient_node_id`.
    /// Returns error if the envelope is too large.
    pub fn store_envelope(&mut self, env: SmpEnvelope) -> Result<(), NexxusError> {
        if env.ciphertext.len() > (1 << 20) {
            return Err(NexxusError::Io("smp envelope too large".into()));
        }
        let recipient = NodeId(env.recipient_node_id);
        let pending = PendingEnvelope {
            env,
            expires_at: Instant::now() + self.ttl,
        };
        self.pending.entry(recipient).or_default().push(pending);
        Ok(())
    }

    /// Retrieve and remove all non-expired envelopes for a recipient.
    /// Expired envelopes are dropped.
    pub fn take_pending(&mut self, recipient: NodeId) -> Vec<SmpEnvelope> {
        let now = Instant::now();
        let mut result = Vec::new();
        if let Some(envs) = self.pending.get_mut(&recipient) {
            envs.retain(|p| p.expires_at > now);
            result.extend(envs.drain(..).map(|p| p.env));
            if envs.is_empty() {
                self.pending.remove(&recipient);
            }
        }
        result
    }

    /// Return the `count` closest known peers to `target` (Kademlia lookup).
    pub fn closest_peers(&self, target: &NodeId, count: usize) -> Vec<NodeId> {
        let mut peers: Vec<(NodeId, u128)> = self
            .peers
            .keys()
            .filter(|pid| **pid != *target)
            .map(|pid| (*pid, xor_distance(pid, target)))
            .collect();
        peers.sort_by_key(|(_, d)| *d);
        peers.into_iter().take(count).map(|(pid, _)| pid).collect()
    }

    /// Purge all expired envelopes (call periodically).
    pub fn gc(&mut self) {
        let now = Instant::now();
        self.pending.retain(|_, envs| {
            envs.retain(|p| p.expires_at > now);
            !envs.is_empty()
        });
    }

    /// Number of pending envelopes across all recipients.
    pub fn pending_count(&self) -> usize {
        self.pending.values().map(|v| v.len()).sum()
    }

    /// Number of known peers.
    pub fn peer_count(&self) -> usize {
        self.peers.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::wire::payloads::{NodeAnnounce, Payload};
    use std::time::Duration;

    #[test]
    fn store_and_take_pending() {
        let mut relay = SmpRelay::new(Duration::from_secs(60));
        let payload = b"hello smp";
        let mut secret = [0u8; 32];
        use rand::rngs::OsRng;
        use rand::Rng;
        OsRng.fill(&mut secret);
        let pub_point = crate::wire::payloads::X25519_BASEPOINT.mul_clamped(secret);
        let (_ephemeral, env) = SmpEnvelope::seal(
            [1u8; 32],
            [2u8; 32],
            &pub_point,
            payload,
        );

        relay.store_envelope(env.clone()).unwrap();
        assert_eq!(relay.pending_count(), 1);

        let taken = relay.take_pending(NodeId([2u8; 32]));
        assert_eq!(taken.len(), 1);
        assert_eq!(taken[0].ciphertext, env.ciphertext);
        assert_eq!(relay.pending_count(), 0);
    }

    #[test]
    fn expired_envelopes_dropped() {
        let mut relay = SmpRelay::new(Duration::from_nanos(1));
        let payload = b"expires immediately";
        let mut secret = [0u8; 32];
        use rand::rngs::OsRng;
        use rand::Rng;
        OsRng.fill(&mut secret);
        let pub_point = crate::wire::payloads::X25519_BASEPOINT.mul_clamped(secret);
        let (_ephemeral, env) = SmpEnvelope::seal(
            [1u8; 32],
            [2u8; 32],
            &pub_point,
            payload,
        );
        relay.store_envelope(env).unwrap();
        // force expiry by sleeping a tiny bit
        std::thread::sleep(Duration::from_nanos(10));
        let taken = relay.take_pending(NodeId([2u8; 32]));
        assert_eq!(taken.len(), 0); // expired
        assert_eq!(relay.pending_count(), 0);
    }

    #[test]
    fn closest_peers_by_xor() {
        let mut relay = SmpRelay::new(Duration::from_secs(60));
        let target = NodeId([0x00u8; 32]);
        relay.register_peer(NodeId([0xFFu8; 32])); // far
        relay.register_peer(NodeId([0x01u8; 32])); // close
        relay.register_peer(NodeId([0x80u8; 32])); // medium
        let closest = relay.closest_peers(&target, 2);
        assert_eq!(closest.len(), 2);
        assert_eq!(closest[0], NodeId([0x01u8; 32]));
        assert_eq!(closest[1], NodeId([0x80u8; 32]));
    }

    #[test]
    fn closest_peers_excludes_target() {
        let mut relay = SmpRelay::new(Duration::from_secs(60));
        let me = NodeId([0x42u8; 32]);
        relay.register_peer(me);
        let closest = relay.closest_peers(&me, 5);
        assert_eq!(closest.len(), 0); // self excluded
    }

    #[test]
    fn node_announce_roundtrip_in_smp() {
        let announce = NodeAnnounce {
            node_id: [0x42u8; 32],
            pubkey: [0x99u8; 32],
            ip: 0x0a000001,
            port: 4001,
        };
        let dec = NodeAnnounce::decode(&announce.encode()).unwrap();
        assert_eq!(dec, announce);
    }
}
