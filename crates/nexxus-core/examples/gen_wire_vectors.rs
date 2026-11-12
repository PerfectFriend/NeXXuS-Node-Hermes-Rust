//! Generates `nexxus-vectors/06_wire_frames_v2_v3.json` — golden vectors for
//! every opcode (0x01..=0x0D) in both v2 and v3 frame formats.
//!
//! Run from the repo root:
//!   cargo run -p nexxus-core --example gen_wire_vectors
//!
//! v2 frames carry a real SHA-256 checksum; v3 frames add a fixed 64-byte
//! signature placeholder (signature *verification* is the caller's job —
//! parse is structural only, see wire::header docs).

use nexxus_core::wire::header::{encode_v2, encode_v3, SIG_LEN};
use nexxus_core::wire::opcode::Opcode;
use nexxus_core::wire::payloads::{
    ErrorResponse, NodeAnnounce, Payload, Ping, StoreChunk,
};
use nexxus_core::types::ChunkHash;
use serde_json::json;

fn payload_for(op: Opcode) -> Vec<u8> {
    match op {
        Opcode::Ping | Opcode::Pong => Ping.encode(),
        Opcode::NodeAnnounce => NodeAnnounce {
            node_id: [0x11u8; 32],
            pubkey: [0x22u8; 32],
            ip: u32::from_be_bytes([192, 0, 2, 1]),
            port: 4001,
            session_nonce: [0xABu8; 32],
        }
        .encode(),
        Opcode::StoreChunk => StoreChunk {
            chunk_hash: ChunkHash([0x42u8; 32]),
            file_id: 7,
            chunk_index: 3,
            data: b"golden-chunk".to_vec(),
        }
        .encode(),
        Opcode::ErrorResponse => ErrorResponse {
            code: 0x0009,
            message: "peer table full".to_string(),
        }
        .encode(),
        _ => {
            // deterministic filler payload for the remaining opcodes
            let mut v = Vec::new();
            for i in 0..32u8 {
                v.push(op.to_u8().wrapping_add(i));
            }
            v
        }
    }
}

fn main() {
    let ops = [
        Opcode::Ping,
        Opcode::Pong,
        Opcode::NodeAnnounce,
        Opcode::StoreChunk,
        Opcode::StoreChunkAck,
        Opcode::FetchChunk,
        Opcode::FetchChunkResp,
        Opcode::PorChallenge,
        Opcode::PorResponse,
        Opcode::KadFindNode,
        Opcode::KadNodesFound,
        Opcode::EpochFinalize,
        Opcode::SmpEnvelope,
        Opcode::ErrorResponse,
    ];
    let sig = [0xEFu8; SIG_LEN];
    let mut cases = Vec::new();
    for op in ops {
        let payload = payload_for(op);
        let req = 0xDEADBEEFu32;
        cases.push(json!({
            "opcode": format!("0x{:02X}", op.to_u8()),
            "request_id": req,
            "payload_hex": hex::encode(&payload),
            "v2_frame_hex": hex::encode(encode_v2(op, req, &payload)),
            "v3_frame_hex": hex::encode(encode_v3(op, req, &payload, &sig)),
            "v3_signature_hex": hex::encode(sig),
        }));
    }
    let doc = json!({
        "vector_id": "wire_frames_v2_v3_all_opcodes",
        "specification": "PROTOCOL_WIRE_SPEC.md §2-3 (ADR-0001): v2 = 46-byte header + payload; v3 = v2 + 64-byte Ed25519 sig at [46..110]",
        "note": "v3 signature bytes are a fixed placeholder — parse is structural; verification needs peer key+nonce from handshake",
        "cases": cases,
    });
    let out = concat!(env!("CARGO_MANIFEST_DIR"), "/../../nexxus-vectors/06_wire_frames_v2_v3.json");
    std::fs::write(out, serde_json::to_string_pretty(&doc).unwrap()).unwrap();
    println!("wrote {out} ({} opcodes)", cases.len());
}
