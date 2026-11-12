//! Golden vectors: every wire opcode (0x01..=0x0D) in v2 and v3 frame formats.
//! Source of truth: `nexxus-vectors/06_wire_frames_v2_v3.json` (regenerate with
//! `cargo run -p nexxus-core --example gen_wire_vectors`).
//! The Rust test and any cross-implementation suite (TS) read the same JSON.

use nexxus_core::wire::header::{parse_v2, parse_v3, HEADER_V2_LEN, HEADER_V3_LEN};
use nexxus_core::wire::opcode::Opcode;

#[test]
fn golden_wire_vectors_all_opcodes() {
    let path = concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../nexxus-vectors/06_wire_frames_v2_v3.json"
    );
    let doc: serde_json::Value =
        serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
    let cases = doc["cases"].as_array().unwrap();
    assert_eq!(cases.len(), 14, "one vector per opcode 0x01..=0x0D");

    let mut seen = std::collections::HashSet::new();
    for case in cases {
        let opcode_byte = u8::from_str_radix(case["opcode"].as_str().unwrap().trim_start_matches("0x"), 16).unwrap();
        let op = Opcode::from_u8(opcode_byte).expect("vector opcode must be known");
        assert!(seen.insert(opcode_byte), "duplicate opcode {opcode_byte:#x}");
        let req = case["request_id"].as_u64().unwrap() as u32;
        let payload = hex::decode(case["payload_hex"].as_str().unwrap()).unwrap();

        // v2: parse must succeed, fields must match the vector
        let v2 = hex::decode(case["v2_frame_hex"].as_str().unwrap()).unwrap();
        assert_eq!(v2.len(), HEADER_V2_LEN + payload.len());
        let f = parse_v2(&v2).expect("v2 golden frame must parse");
        assert_eq!(f.opcode, op);
        assert_eq!(f.request_id, req);
        assert_eq!(f.payload, payload);

        // v3: structural parse (signature is a placeholder, not verified here)
        let v3 = hex::decode(case["v3_frame_hex"].as_str().unwrap()).unwrap();
        assert_eq!(v3.len(), HEADER_V3_LEN + payload.len());
        let sig: [u8; 64] = hex::decode(case["v3_signature_hex"].as_str().unwrap())
            .unwrap()
            .try_into()
            .unwrap();
        let f3 = parse_v3(&v3).expect("v3 golden frame must parse");
        assert_eq!(f3.opcode, op);
        assert_eq!(f3.request_id, req);
        assert_eq!(f3.payload, payload);
        assert_eq!(f3.signature, sig);
    }
    assert_eq!(seen.len(), 14);
}
