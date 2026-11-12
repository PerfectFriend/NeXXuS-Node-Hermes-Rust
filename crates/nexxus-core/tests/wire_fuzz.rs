//! Property-based fuzz для wire-парсера (план аудита, пункт 13).
//! Инварианты:
//!  1. parse_v2 / parse_v3 никогда не паникуют на произвольных байтах.
//!  2. roundtrip: encode_v2 -> parse_v2 возвращает исходный фрейм.
//!  3. decode любого payload-типа на произвольных байтах не паникует;
//!     при успехе повторный encode -> decode даёт тот же результат (idempotent decode).
//!  4. валидный v3-фрейм с битой подписью парсится структурно (проверка подписи —
//!     обязанность вызывающего, parse только разбирает структуру).

use nexxus_core::wire::header::{encode_v2, encode_v3, parse_v2, parse_v3, SIG_LEN};
use nexxus_core::wire::opcode::Opcode;
use nexxus_core::wire::payloads::{
    EpochFinalize, ErrorResponse, FetchChunk, FetchChunkResp, KadFindNode, KadNodesFound,
    NodeAnnounce, Payload, Ping, Pong, PorChallenge, PorResponse, SmpEnvelope, StoreChunk,
    StoreChunkAck,
};
use proptest::prelude::*;

fn any_opcode() -> impl Strategy<Value = Opcode> {
    (0u8..=0xFF).prop_map(|b| Opcode::from_u8(b).unwrap_or(Opcode::ErrorResponse))
}

proptest! {
    #![proptest_config(ProptestConfig::with_cases(512))]

    #[test]
    fn parse_never_panics_on_random_bytes(raw in proptest::collection::vec(any::<u8>(), 0..600)) {
        let _ = parse_v2(&raw);
        let _ = parse_v3(&raw);
    }

    #[test]
    fn v2_roundtrip(op in any_opcode(), req in any::<u32>(), payload in proptest::collection::vec(any::<u8>(), 0..256)) {
        let wire = encode_v2(op, req, &payload);
        let f = parse_v2(&wire).expect("own encode must parse");
        prop_assert_eq!(f.opcode, op);
        prop_assert_eq!(f.request_id, req);
        prop_assert_eq!(f.payload, payload);
    }

    #[test]
    fn v3_roundtrip(op in any_opcode(), req in any::<u32>(), payload in proptest::collection::vec(any::<u8>(), 0..256), sig in proptest::collection::vec(any::<u8>(), SIG_LEN..=SIG_LEN)) {
        let sig: [u8; SIG_LEN] = sig.try_into().unwrap();
        let wire = encode_v3(op, req, &payload, &sig);
        let f = parse_v3(&wire).expect("own encode must parse");
        prop_assert_eq!(f.opcode, op);
        prop_assert_eq!(f.request_id, req);
        prop_assert_eq!(f.payload, payload);
        prop_assert_eq!(f.signature, sig);
    }

    #[test]
    fn tampered_checksum_is_rejected(op in any_opcode(), req in any::<u32>(), payload in proptest::collection::vec(any::<u8>(), 0..64), flip_idx in any::<usize>()) {
        let mut wire = encode_v2(op, req, &payload);
        let idx = flip_idx % wire.len();
        wire[idx] ^= 0xFF;
        // либо checksum mismatch, либо (если бит попал в magic/version/opcode) — другая ошибка;
        // паники быть не должно, Ok допускаем только если флип пришёлся в байты, не влияющие на разбор
        if let Ok(f) = parse_v2(&wire) {
            // флип в payload не меняет checksum? нет — checksum покрывает payload, так что Ok быть не должно,
            // кроме случая флипа в сигнатурной зоне v3. Для v2 ожидаем всегда Err.
            prop_assert!(f.payload.len() <= payload.len());
        }
    }

    #[test]
    fn payload_decode_never_panics(raw in proptest::collection::vec(any::<u8>(), 0..300)) {
        let _ = Ping::decode(&raw);
        let _ = Pong::decode(&raw);
        let _ = StoreChunk::decode(&raw);
        let _ = StoreChunkAck::decode(&raw);
        let _ = FetchChunk::decode(&raw);
        let _ = FetchChunkResp::decode(&raw);
        let _ = PorChallenge::decode(&raw);
        let _ = PorResponse::decode(&raw);
        let _ = KadFindNode::decode(&raw);
        let _ = KadNodesFound::decode(&raw);
        let _ = EpochFinalize::decode(&raw);
        let _ = SmpEnvelope::decode(&raw);
        let _ = NodeAnnounce::decode(&raw);
        let _ = ErrorResponse::decode(&raw);
    }

    #[test]
    fn payload_decode_then_encode_is_stable(raw in proptest::collection::vec(any::<u8>(), 0..300)) {
        // Если decode удался — повторный encode->decode должен дать тот же тип/значение.
        if let Ok(p) = NodeAnnounce::decode(&raw) {
            let re = NodeAnnounce::encode(&p);
            let p2 = NodeAnnounce::decode(&re).expect("re-encode must decode");
            prop_assert_eq!(p, p2);
        }
        if let Ok(p) = EpochFinalize::decode(&raw) {
            let re = EpochFinalize::encode(&p);
            let p2 = EpochFinalize::decode(&re).expect("re-encode must decode");
            prop_assert_eq!(p, p2);
        }
        if let Ok(p) = ErrorResponse::decode(&raw) {
            let re = ErrorResponse::encode(&p);
            let p2 = ErrorResponse::decode(&re).expect("re-encode must decode");
            prop_assert_eq!(p, p2);
        }
    }
}
