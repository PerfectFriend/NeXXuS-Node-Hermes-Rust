//! Binary payload structs per PROTOCOL_WIRE_SPEC.md §4 (ADR-0001/0002).
//! All fields Big-Endian; no JSON, no self-describing framing.

use crate::error::NexxusError;
use crate::types::ChunkHash;
use crate::wire::reader::{Reader, Writer};

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
}
