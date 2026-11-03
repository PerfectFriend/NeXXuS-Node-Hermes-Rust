//! Binary payload structs per PROTOCOL_WIRE_SPEC.md §4 (ADR-0001/0002).
//! All fields Big-Endian; no JSON, no self-describing framing.

use crate::error::NexxusError;
use crate::types::ChunkHash;
use crate::wire::reader::{Reader, Writer};
use chacha20poly1305::{aead::Aead, ChaCha20Poly1305, KeyInit, Nonce};
use curve25519_dalek::MontgomeryPoint;
use rand::{rngs::OsRng, Rng};
use sha2::{Digest, Sha256};

/// X25519 basepoint (u = 9) over Montgomery curve.
pub const X25519_BASEPOINT: MontgomeryPoint = MontgomeryPoint([9u8, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]);

pub trait Payload: Sized {
    fn encode(&self) -> Vec<u8>;
    fn decode(payload: &[u8]) -> Result<Self, NexxusError>;
}

/// Fixed-size payload: encode/decode a [u8; N] buffer.
macro_rules! fixed_payload {
    ($ty:ident, $n:expr, $field:ident) => {
        impl Payload for $ty {
            fn encode(&self) -> Vec<u8> {
                self.$field.to_vec()
            }

            fn decode(payload: &[u8]) -> Result<Self, NexxusError> {
                if payload.len() != $n {
                    return Err(NexxusError::Io(format!(
                        "{} expects {} bytes, got {}",
                        stringify!($ty),
                        $n,
                        payload.len()
                    )));
                }
                let mut f = [0u8; $n];
                f.copy_from_slice(payload);
                Ok($ty { $field: f })
            }
        }
    };
}

/// Ping — zero-length payload (encode as empty).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Ping;

impl Payload for Ping {
    fn encode(&self) -> Vec<u8> {
        Vec::new()
    }
    fn decode(_payload: &[u8]) -> Result<Self, NexxusError> {
        Ok(Ping)
    }
}

/// Pong — echoes the request id in the header; payload empty.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Pong;

impl Payload for Pong {
    fn encode(&self) -> Vec<u8> {
        Vec::new()
    }
    fn decode(_payload: &[u8]) -> Result<Self, NexxusError> {
        Ok(Pong)
    }
}

/// StoreChunk: chunk_hash[32] || file_id u32 || chunk_index u32 || len u32 || data[len]
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StoreChunk {
    pub chunk_hash: ChunkHash,
    pub file_id: u32,
    pub chunk_index: u32,
    pub data: Vec<u8>,
}

impl Payload for StoreChunk {
    fn encode(&self) -> Vec<u8> {
        let mut w = Writer::new();
        w.fixed(&self.chunk_hash.0)
            .u32_be(self.file_id)
            .u32_be(self.chunk_index)
            .u32_be(self.data.len() as u32)
            .bytes(&self.data);
        w.buf
    }

    fn decode(payload: &[u8]) -> Result<Self, NexxusError> {
        let mut r = Reader::new(payload);
        let chunk_hash = ChunkHash(r.fixed::<32>()?);
        let file_id = r.u32_be()?;
        let chunk_index = r.u32_be()?;
        let len = r.u32_be()? as usize;
        if r.remaining() < len {
            return Err(NexxusError::WireTruncated {
                offset: r.pos(),
                need: len,
            });
        }
        let data = r.bytes(len)?.to_vec();
        Ok(StoreChunk {
            chunk_hash,
            file_id,
            chunk_index,
            data,
        })
    }
}

fixed_payload!(StoreChunkAck, 32, hash);
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StoreChunkAck {
    pub hash: [u8; 32],
}

fixed_payload!(FetchChunk, 32, hash);
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FetchChunk {
    pub hash: [u8; 32],
}

/// FetchChunkResp: chunk_hash[32] || len u32 || data[len]
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FetchChunkResp {
    pub chunk_hash: ChunkHash,
    pub data: Vec<u8>,
}

impl Payload for FetchChunkResp {
    fn encode(&self) -> Vec<u8> {
        let mut w = Writer::new();
        w.fixed(&self.chunk_hash.0)
            .u32_be(self.data.len() as u32)
            .bytes(&self.data);
        w.buf
    }

    fn decode(payload: &[u8]) -> Result<Self, NexxusError> {
        let mut r = Reader::new(payload);
        let chunk_hash = ChunkHash(r.fixed::<32>()?);
        let len = r.u32_be()? as usize;
        if r.remaining() < len {
            return Err(NexxusError::WireTruncated {
                offset: r.pos(),
                need: len,
            });
        }
        let data = r.bytes(len)?.to_vec();
        Ok(FetchChunkResp { chunk_hash, data })
    }
}

/// PorChallenge: seed[32] || count u32 || deadline_ms u64
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PorChallenge {
    pub seed: [u8; 32],
    pub count: u32,
    pub deadline_ms: u64,
}

impl Payload for PorChallenge {
    fn encode(&self) -> Vec<u8> {
        let mut w = Writer::new();
        w.fixed(&self.seed)
            .u32_be(self.count)
            .u64_be(self.deadline_ms);
        w.buf
    }

    fn decode(payload: &[u8]) -> Result<Self, NexxusError> {
        let mut r = Reader::new(payload);
        Ok(PorChallenge {
            seed: r.fixed::<32>()?,
            count: r.u32_be()?,
            deadline_ms: r.u64_be()?,
        })
    }
}

/// PorResponse: chunk_hash[32] || response[32]
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PorResponse {
    pub chunk_hash: ChunkHash,
    pub response: [u8; 32],
}

impl Payload for PorResponse {
    fn encode(&self) -> Vec<u8> {
        let mut w = Writer::new();
        w.fixed(&self.chunk_hash.0).fixed(&self.response);
        w.buf
    }

    fn decode(payload: &[u8]) -> Result<Self, NexxusError> {
        let mut r = Reader::new(payload);
        Ok(PorResponse {
            chunk_hash: ChunkHash(r.fixed::<32>()?),
            response: r.fixed::<32>()?,
        })
    }
}

/// KadFindNode: target_node_id[32] || count u16
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct KadFindNode {
    pub target_node_id: [u8; 32],
    pub count: u16,
}

impl Payload for KadFindNode {
    fn encode(&self) -> Vec<u8> {
        let mut w = Writer::new();
        w.fixed(&self.target_node_id).u16_be(self.count);
        w.buf
    }

    fn decode(payload: &[u8]) -> Result<Self, NexxusError> {
        let mut r = Reader::new(payload);
        Ok(KadFindNode {
            target_node_id: r.fixed::<32>()?,
            count: r.u16_be()?,
        })
    }
}

/// KadNodesFound: count u16 || [node_id[32] || ip u32 || port u16]*
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct KadPeer {
    pub node_id: [u8; 32],
    pub ip: u32,
    pub port: u16,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct KadNodesFound {
    pub peers: Vec<KadPeer>,
}

impl Payload for KadNodesFound {
    fn encode(&self) -> Vec<u8> {
        let mut w = Writer::new();
        w.u16_be(self.peers.len() as u16);
        for p in &self.peers {
            w.fixed(&p.node_id).u32_be(p.ip).u16_be(p.port);
        }
        w.buf
    }

    fn decode(payload: &[u8]) -> Result<Self, NexxusError> {
        let mut r = Reader::new(payload);
        let count = r.u16_be()? as usize;
        let mut peers = Vec::with_capacity(count);
        for _ in 0..count {
            peers.push(KadPeer {
                node_id: r.fixed::<32>()?,
                ip: r.u32_be()?,
                port: r.u16_be()?,
            });
        }
        Ok(KadNodesFound { peers })
    }
}

/// EpochFinalize (0x0C): epoch_number u64 || merkle_root[32] || total_bytes u64
///   || count u16 || [pubkey[32] || sig[64]]*  (committee multi-sig Ed25519, ADR-0008)
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct CommitteeSig {
    pub pubkey: [u8; 32],
    pub signature: [u8; 64],
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EpochFinalize {
    pub epoch_number: u64,
    pub merkle_root: [u8; 32],
    pub total_bytes: u64,
    pub signatures: Vec<CommitteeSig>,
}

impl Payload for EpochFinalize {
    fn encode(&self) -> Vec<u8> {
        let mut w = Writer::new();
        w.u64_be(self.epoch_number)
            .fixed(&self.merkle_root)
            .u64_be(self.total_bytes)
            .u16_be(self.signatures.len() as u16);
        for s in &self.signatures {
            w.fixed(&s.pubkey).fixed(&s.signature);
        }
        w.buf
    }

    fn decode(payload: &[u8]) -> Result<Self, NexxusError> {
        let mut r = Reader::new(payload);
        let epoch_number = r.u64_be()?;
        let merkle_root = r.fixed::<32>()?;
        let total_bytes = r.u64_be()?;
        let count = r.u16_be()? as usize;
        let mut signatures = Vec::with_capacity(count);
        for _ in 0..count {
            signatures.push(CommitteeSig {
                pubkey: r.fixed::<32>()?,
                signature: r.fixed::<64>()?,
            });
        }
        Ok(EpochFinalize {
            epoch_number,
            merkle_root,
            total_bytes,
            signatures,
        })
    }
}

/// SmpEnvelope (0x0D): sender[32] || recipient[32] || nonce[12] || ct_len u32 || ct+tag
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SmpEnvelope {
    pub sender_node_id: [u8; 32],
    pub recipient_node_id: [u8; 32],
    pub nonce: [u8; 12],
    pub ciphertext: Vec<u8>,
}

impl Payload for SmpEnvelope {
    fn encode(&self) -> Vec<u8> {
        let mut w = Writer::new();
        w.fixed(&self.sender_node_id)
            .fixed(&self.recipient_node_id)
            .fixed(&self.nonce)
            .u32_be(self.ciphertext.len() as u32)
            .bytes(&self.ciphertext);
        w.buf
    }

    fn decode(payload: &[u8]) -> Result<Self, NexxusError> {
        let mut r = Reader::new(payload);
        let sender_node_id = r.fixed::<32>()?;
        let recipient_node_id = r.fixed::<32>()?;
        let nonce = r.fixed::<12>()?;
        let ct_len = r.u32_be()? as usize;
        if r.remaining() < ct_len {
            return Err(NexxusError::WireTruncated {
                offset: r.pos(),
                need: ct_len,
            });
        }
        let ciphertext = r.bytes(ct_len)?.to_vec();
        Ok(SmpEnvelope {
            sender_node_id,
            recipient_node_id,
            nonce,
            ciphertext,
        })
    }
}

/// X25519 + ChaCha20-Poly1305 envelope (ADR-0007).
/// ciphertext = ephemeral_x25519_pubkey[32] || ChaCha20Poly1305(nonce, ephemeral_pubkey || payload).
/// Recipient opens with their static X25519 secret; sender authenticity comes from the
/// wire-v3 frame Ed25519 signature covering this envelope.
impl SmpEnvelope {
    pub fn seal(
        sender_node_id: [u8; 32],
        recipient_node_id: [u8; 32],
        recipient_pub: &MontgomeryPoint,
        payload: &[u8],
    ) -> ([u8; 32], Self) {
        let mut ephemeral_secret = [0u8; 32];
        OsRng.fill(&mut ephemeral_secret);
        let ephemeral_pub = X25519_BASEPOINT.mul_clamped(ephemeral_secret);
        let shared = recipient_pub.mul_clamped(ephemeral_secret);
        let mut h = Sha256::new();
        h.update(shared.0);
        let key: [u8; 32] = h.finalize().into();
        let aead = ChaCha20Poly1305::new_from_slice(&key[..]).expect("chacha20 key length");
        // Random per-envelope nonce (key is ephemeral per seal, so nonce reuse is not an issue,
        // but random nonce improves AEAD hygiene).
        let mut nonce_bytes = [0u8; 12];
        OsRng.fill(&mut nonce_bytes);
        let nonce_box = Nonce::from_slice(&nonce_bytes);
        let inner = payload.to_vec();
        let ct = aead
            .encrypt(nonce_box, &inner[..])
            .expect("chacha20 encrypt");
        // ciphertext = ephemeral pubkey (cleartext, 32 bytes) || ChaCha20Poly1305 ciphertext
        let mut ciphertext = ephemeral_pub.0.to_vec();
        ciphertext.extend_from_slice(&ct);
        (
            ephemeral_pub.0,
            Self {
                sender_node_id,
                recipient_node_id,
                nonce: nonce_bytes,
                ciphertext,
            },
        )
    }

    pub fn open(&self, recipient_secret: &[u8; 32]) -> Result<Vec<u8>, NexxusError> {
        if self.ciphertext.len() < 32 {
            return Err(NexxusError::Io("smp envelope too short".into()));
        }
        let ephemeral_pub = MontgomeryPoint(
            self.ciphertext[..32]
                .try_into()
                .map_err(|_| NexxusError::Io("bad ephemeral pubkey".into()))?,
        );
        let shared = ephemeral_pub.mul_clamped(*recipient_secret);
        let mut h = Sha256::new();
        h.update(shared.0);
        let key: [u8; 32] = h.finalize().into();
        let aead = ChaCha20Poly1305::new_from_slice(&key[..]).map_err(|_| NexxusError::Io("bad key".into()))?;
        let nonce_box = Nonce::from_slice(&self.nonce[..]);
        let payload = aead
            .decrypt(nonce_box, &self.ciphertext[32..])
            .map_err(|_| NexxusError::AeadAuthFailed)?;
        Ok(payload)
    }
}

/// NodeAnnounce: node_id[32] || ip u32 || port u16 — peer announces itself
/// so the listener can register it in the routing table.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct NodeAnnounce {
    pub node_id: [u8; 32],
    pub ip: u32,
    pub port: u16,
}

impl Payload for NodeAnnounce {
    fn encode(&self) -> Vec<u8> {
        let mut w = Writer::new();
        w.fixed(&self.node_id).u32_be(self.ip).u16_be(self.port);
        w.buf
    }

    fn decode(payload: &[u8]) -> Result<Self, NexxusError> {
        let mut r = Reader::new(payload);
        Ok(NodeAnnounce {
            node_id: r.fixed::<32>()?,
            ip: r.u32_be()?,
            port: r.u16_be()?,
        })
    }
}

/// ErrorResponse: code u16 || message_len u8 || message bytes
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ErrorResponse {
    pub code: u16,
    pub message: String,
}

impl Payload for ErrorResponse {
    fn encode(&self) -> Vec<u8> {
        let mut w = Writer::new();
        w.u16_be(self.code);
        let msg = self.message.as_bytes();
        w.u8(msg.len() as u8).bytes(msg);
        w.buf
    }

    fn decode(payload: &[u8]) -> Result<Self, NexxusError> {
        let mut r = Reader::new(payload);
        let code = r.u16_be()?;
        let msg_len = r.u8()? as usize;
        let msg_bytes = r.bytes(msg_len)?;
        Ok(ErrorResponse {
            code,
            message: String::from_utf8_lossy(msg_bytes).into_owned(),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn store_chunk_roundtrip() {
        let hash = ChunkHash([1u8; 32]);
        let orig = StoreChunk {
            chunk_hash: hash,
            file_id: 9,
            chunk_index: 3,
            data: vec![0xde, 0xad, 0xbe, 0xef],
        };
        let enc = orig.encode();
        let dec = StoreChunk::decode(&enc).unwrap();
        assert_eq!(dec, orig);
    }

    #[test]
    fn por_challenge_roundtrip() {
        let orig = PorChallenge {
            seed: [2u8; 32],
            count: 7,
            deadline_ms: 3000,
        };
        let dec = PorChallenge::decode(&orig.encode()).unwrap();
        assert_eq!(dec, orig);
    }

    #[test]
    fn kad_nodes_found_variable_length() {
        let orig = KadNodesFound {
            peers: vec![
                KadPeer {
                    node_id: [3u8; 32],
                    ip: 0x0a000001,
                    port: 4001,
                },
                KadPeer {
                    node_id: [4u8; 32],
                    ip: 0x0a000002,
                    port: 4002,
                },
            ],
        };
        let dec = KadNodesFound::decode(&orig.encode()).unwrap();
        assert_eq!(dec, orig);
    }

    #[test]
    fn epoch_finalize_multi_sig_roundtrip() {
        let orig = EpochFinalize {
            epoch_number: 42,
            merkle_root: [5u8; 32],
            total_bytes: 1 << 24,
            signatures: vec![
                CommitteeSig {
                    pubkey: [6u8; 32],
                    signature: [7u8; 64],
                },
                CommitteeSig {
                    pubkey: [8u8; 32],
                    signature: [9u8; 64],
                },
            ],
        };
        let dec = EpochFinalize::decode(&orig.encode()).unwrap();
        assert_eq!(dec, orig);
    }

    #[test]
    fn smp_envelope_roundtrip() {
        let orig = SmpEnvelope {
            sender_node_id: [10u8; 32],
            recipient_node_id: [11u8; 32],
            nonce: [12u8; 12],
            ciphertext: vec![0xaa, 0xbb, 0xcc],
        };
        let dec = SmpEnvelope::decode(&orig.encode()).unwrap();
        assert_eq!(dec, orig);
    }

    #[test]
    fn error_response_roundtrip() {
        let orig = ErrorResponse {
            code: 0x0007,
            message: "ERR_UNAUTHORIZED".into(),
        };
        let dec = ErrorResponse::decode(&orig.encode()).unwrap();
        assert_eq!(dec.code, 0x0007);
        assert_eq!(dec.message, "ERR_UNAUTHORIZED");
    }

    #[test]
    fn decode_rejects_truncated() {
        assert!(StoreChunk::decode(&[0u8; 10]).is_err());
        assert!(PorResponse::decode(&[0u8; 31]).is_err());
        assert!(EpochFinalize::decode(&[0u8; 20]).is_err());
    }

    #[test]
    fn node_announce_roundtrip() {
        let orig = NodeAnnounce {
            node_id: [0x42u8; 32],
            ip: 0x0a000001,
            port: 4001,
        };
        let dec = NodeAnnounce::decode(&orig.encode()).unwrap();
        assert_eq!(dec, orig);
    }

    #[test]
    fn smp_seal_open_roundtrip() {
        let payload = b"SMP test payload: P2P relay request";
        let mut bob_secret = [0u8; 32];
        OsRng.fill(&mut bob_secret);
        let bob_pub = X25519_BASEPOINT.mul_clamped(bob_secret);

        let (ephemeral_pub, env) = SmpEnvelope::seal([1u8; 32], [2u8; 32], &bob_pub, payload);
        assert_eq!(env.sender_node_id, [1u8; 32]);
        assert_eq!(env.recipient_node_id, [2u8; 32]);
        // nonce is random per seal (not all zeros)
        assert_ne!(env.nonce, [0u8; 12]);

        // ephemeral pubkey is embedded in ciphertext
        assert_eq!(&env.ciphertext[..32], &ephemeral_pub);

        let opened = env.open(&bob_secret).unwrap();
        assert_eq!(&opened, payload);

        // wrong secret key fails
        let mut wrong = [0u8; 32];
        OsRng.fill(&mut wrong);
        assert!(env.open(&wrong).is_err());

        // tampered ciphertext fails
        let mut tampered = env.clone();
        tampered.ciphertext[40] ^= 0xff;
        assert!(tampered.open(&bob_secret).is_err());
    }

    #[test]
    fn smp_encode_decode_roundtrip() {
        let payload = vec![0x42u8; 100];
        let mut alice_secret = [0u8; 32];
        OsRng.fill(&mut alice_secret);
        let alice_pub = X25519_BASEPOINT.mul_clamped(alice_secret);
        let (_, env) = SmpEnvelope::seal([7u8; 32], [8u8; 32], &alice_pub, &payload);
        let dec = SmpEnvelope::decode(&env.encode()).unwrap();
        assert_eq!(dec, env);
    }
}
