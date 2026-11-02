//! Canonical wire header — ADR-0001.
//!
//! v2 (legacy TS-compatible): 46 bytes.
//!   [0..3] magic "NEXX" | [4] version | [5] opcode | [6..9] req_id u32_be
//!   [10..13] payload_len u32_be | [14..45] sha256(opcode||req||len||payload)
//! v3 (canonical): 110 bytes = v2 header fields (version=0x03) + [46..109] Ed25519 sig.
//!   Signature is over (opcode||req||len||payload||session_nonce); verification is
//!   the caller's job (needs the peer pubkey + nonce from handshake).

use sha2::{Digest, Sha256};

use super::opcode::Opcode;
use super::reader::{Reader, Writer};
use crate::error::NexxusError;

pub const MAGIC: &[u8; 4] = b"NEXX";
pub const VERSION_V2: u8 = 0x02;
pub const VERSION_V3: u8 = 0x03;
pub const HEADER_V2_LEN: usize = 46;
pub const SIG_LEN: usize = 64;
pub const HEADER_V3_LEN: usize = HEADER_V2_LEN + SIG_LEN; // 110

/// SHA-256 over opcode || request_id_be || payload_len_be || payload.
pub fn frame_checksum(opcode: u8, request_id: u32, payload_len: u32, payload: &[u8]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update([opcode]);
    h.update(request_id.to_be_bytes());
    h.update(payload_len.to_be_bytes());
    h.update(payload);
    h.finalize().into()
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FrameV2 {
    pub opcode: Opcode,
    pub request_id: u32,
    pub payload: Vec<u8>,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FrameV3 {
    pub opcode: Opcode,
    pub request_id: u32,
    pub payload: Vec<u8>,
    pub signature: [u8; SIG_LEN],
}

pub fn encode_v2(opcode: Opcode, request_id: u32, payload: &[u8]) -> Vec<u8> {
    let mut w = Writer::with_capacity(HEADER_V2_LEN + payload.len());
    w.fixed(MAGIC)
        .u8(VERSION_V2)
        .u8(opcode.to_u8())
        .u32_be(request_id)
        .u32_be(payload.len() as u32)
        .fixed(&frame_checksum(
            opcode.to_u8(),
            request_id,
            payload.len() as u32,
            payload,
        ))
        .bytes(payload);
    w.buf
}

pub fn parse_v2(raw: &[u8]) -> Result<FrameV2, NexxusError> {
    if raw.len() < HEADER_V2_LEN {
        return Err(NexxusError::WireTruncated {
            offset: 0,
            need: HEADER_V2_LEN,
        });
    }
    if &raw[0..4] != MAGIC {
        return Err(NexxusError::WireMagic);
    }
    let version = raw[4];
    if version != VERSION_V2 {
        return Err(NexxusError::VersionMismatch(version));
    }
    let opcode = Opcode::from_u8(raw[5]).ok_or(NexxusError::UnknownOpcode(raw[5]))?;
    let mut r = Reader::new(&raw[6..]);
    let request_id = r.u32_be()?;
    let payload_len = r.u32_be()? as usize;
    if raw.len() < HEADER_V2_LEN + payload_len {
        return Err(NexxusError::WireTruncated {
            offset: HEADER_V2_LEN,
            need: payload_len,
        });
    }
    let checksum: [u8; 32] = raw[14..46].try_into().expect("slice len 32");
    let payload = &raw[HEADER_V2_LEN..HEADER_V2_LEN + payload_len];
    let expect = frame_checksum(opcode.to_u8(), request_id, payload_len as u32, payload);
    if checksum != expect {
        return Err(NexxusError::WireChecksum);
    }
    Ok(FrameV2 {
        opcode,
        request_id,
        payload: payload.to_vec(),
    })
}

/// v3 frame: same layout, version=0x03, plus 64-byte Ed25519 signature at [46..109].
pub fn encode_v3(opcode: Opcode, request_id: u32, payload: &[u8], signature: &[u8; SIG_LEN]) -> Vec<u8> {
    let mut w = Writer::with_capacity(HEADER_V3_LEN + payload.len());
    w.fixed(MAGIC)
        .u8(VERSION_V3)
        .u8(opcode.to_u8())
        .u32_be(request_id)
        .u32_be(payload.len() as u32)
        .fixed(&frame_checksum(
            opcode.to_u8(),
            request_id,
            payload.len() as u32,
            payload,
        ))
        .fixed(signature)
        .bytes(payload);
    w.buf
}

pub fn parse_v3(raw: &[u8]) -> Result<FrameV3, NexxusError> {
    if raw.len() < HEADER_V3_LEN {
        return Err(NexxusError::WireTruncated {
            offset: 0,
            need: HEADER_V3_LEN,
        });
    }
    if &raw[0..4] != MAGIC {
        return Err(NexxusError::WireMagic);
    }
    let version = raw[4];
    if version != VERSION_V3 {
        return Err(NexxusError::VersionMismatch(version));
    }
    let opcode = Opcode::from_u8(raw[5]).ok_or(NexxusError::UnknownOpcode(raw[5]))?;
    let mut r = Reader::new(&raw[6..]);
    let request_id = r.u32_be()?;
    let payload_len = r.u32_be()? as usize;
    if raw.len() < HEADER_V3_LEN + payload_len {
        return Err(NexxusError::WireTruncated {
            offset: HEADER_V3_LEN,
            need: payload_len,
        });
    }
    let checksum: [u8; 32] = raw[14..46].try_into().expect("slice len 32");
    let signature: [u8; SIG_LEN] = raw[46..HEADER_V3_LEN].try_into().expect("slice len 64");
    let payload = &raw[HEADER_V3_LEN..HEADER_V3_LEN + payload_len];
    let expect = frame_checksum(opcode.to_u8(), request_id, payload_len as u32, payload);
    if checksum != expect {
        return Err(NexxusError::WireChecksum);
    }
    Ok(FrameV3 {
        opcode,
        request_id,
        payload: payload.to_vec(),
        signature,
    })
}

/// Message to sign for a v3 frame: opcode||req||len||payload||session_nonce.
pub fn v3_signing_bytes(opcode: Opcode, request_id: u32, payload: &[u8], session_nonce: &[u8; 32]) -> Vec<u8> {
    let mut w = Writer::with_capacity(9 + payload.len() + 32);
    w.u8(opcode.to_u8())
        .u32_be(request_id)
        .u32_be(payload.len() as u32)
        .bytes(payload)
        .fixed(session_nonce);
    w.buf
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn v2_roundtrip() {
        let payload = [0u8, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 42];
        let frame = encode_v2(Opcode::Ping, 0xdeadbeef, &payload);
        assert_eq!(frame.len(), HEADER_V2_LEN + 12);
        let f = parse_v2(&frame).unwrap();
        assert_eq!(f.opcode, Opcode::Ping);
        assert_eq!(f.request_id, 0xdeadbeef);
        assert_eq!(f.payload, payload);
        // re-encode is byte-identical
        assert_eq!(encode_v2(f.opcode, f.request_id, &f.payload), frame);
    }

    /// Cross-check against the legacy TypeScript implementation (fixture generated by tsx).
    #[test]
    fn v2_matches_ts_fixture() {
        let hex = include_str!("../../tests/fixtures/wire_ping_v2.hex").trim();
        let raw = hex::decode(hex).unwrap();
        let f = parse_v2(&raw).unwrap();
        assert_eq!(f.opcode, Opcode::Ping);
        assert_eq!(f.request_id, 0xdeadbeef);
        assert_eq!(f.payload, vec![0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 42]);
        assert_eq!(encode_v2(f.opcode, f.request_id, &f.payload), raw);
    }

    #[test]
    fn v2_rejects_bad_magic_and_checksum() {
        let mut frame = encode_v2(Opcode::Ping, 1, b"hi");
        frame[0] = b'X';
        assert!(matches!(parse_v2(&frame), Err(NexxusError::WireMagic)));

        let mut frame = encode_v2(Opcode::Ping, 1, b"hi");
        frame[20] ^= 0xff;
        assert!(matches!(parse_v2(&frame), Err(NexxusError::WireChecksum)));
    }

    #[test]
    fn v2_rejects_wrong_version_and_truncation() {
        let mut frame = encode_v2(Opcode::Ping, 1, b"");
        frame[4] = 0x09;
        assert!(matches!(parse_v2(&frame), Err(NexxusError::VersionMismatch(0x09))));
        assert!(matches!(
            parse_v2(&frame[..20]),
            Err(NexxusError::WireTruncated { .. })
        ));
    }

    #[test]
    fn v2_rejects_unknown_opcode() {
        let mut frame = encode_v2(Opcode::Ping, 1, b"");
        frame[5] = 0x77;
        // checksum now invalid too, but opcode check fires first
        assert!(matches!(parse_v2(&frame), Err(NexxusError::UnknownOpcode(0x77))));
    }

    #[test]
    fn v3_roundtrip_and_tamper() {
        let sig = [0xabu8; SIG_LEN];
        let payload = b"chunk-data";
        let frame = encode_v3(Opcode::StoreChunk, 42, payload, &sig);
        assert_eq!(frame.len(), HEADER_V3_LEN + payload.len());
        let f = parse_v3(&frame).unwrap();
        assert_eq!(f.opcode, Opcode::StoreChunk);
        assert_eq!(f.request_id, 42);
        assert_eq!(f.payload, payload);
        assert_eq!(f.signature, sig);

        let mut bad = frame.clone();
        bad[HEADER_V3_LEN] ^= 1; // flip payload bit
        assert!(matches!(parse_v3(&bad), Err(NexxusError::WireChecksum)));

        // v2 parser must refuse a v3 frame
        assert!(matches!(parse_v2(&frame), Err(NexxusError::VersionMismatch(0x03))));
    }

    #[test]
    fn v3_signing_bytes_layout() {
        let nonce = [7u8; 32];
        let b = v3_signing_bytes(Opcode::Pong, 5, b"xy", &nonce);
        assert_eq!(&b[0..1], &[0x02]);
        assert_eq!(&b[1..5], &5u32.to_be_bytes());
        assert_eq!(&b[5..9], &2u32.to_be_bytes());
        assert_eq!(&b[9..11], b"xy");
        assert_eq!(&b[11..43], &nonce);
    }
}
