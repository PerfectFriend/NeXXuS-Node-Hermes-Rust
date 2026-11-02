//! Canonical opcode table (ADR-0002). Values are frozen; reordering is forbidden.

/// P2P opcodes. `0x0C = EpochFinalize`, `0x0D = SmpEnvelope` per PROTOCOL_WIRE_SPEC.md.
#[repr(u8)]
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Opcode {
    Ping = 0x01,
    Pong = 0x02,
    NodeAnnounce = 0x03,
    StoreChunk = 0x04,
    StoreChunkAck = 0x05,
    FetchChunk = 0x06,
    FetchChunkResp = 0x07,
    PorChallenge = 0x08,
    PorResponse = 0x09,
    KadFindNode = 0x0A,
    KadNodesFound = 0x0B,
    EpochFinalize = 0x0C,
    SmpEnvelope = 0x0D,
    ErrorResponse = 0xFF,
}

impl Opcode {
    pub const fn to_u8(self) -> u8 {
        self as u8
    }

    pub const fn from_u8(b: u8) -> Option<Opcode> {
        match b {
            0x01 => Some(Opcode::Ping),
            0x02 => Some(Opcode::Pong),
            0x03 => Some(Opcode::NodeAnnounce),
            0x04 => Some(Opcode::StoreChunk),
            0x05 => Some(Opcode::StoreChunkAck),
            0x06 => Some(Opcode::FetchChunk),
            0x07 => Some(Opcode::FetchChunkResp),
            0x08 => Some(Opcode::PorChallenge),
            0x09 => Some(Opcode::PorResponse),
            0x0A => Some(Opcode::KadFindNode),
            0x0B => Some(Opcode::KadNodesFound),
            0x0C => Some(Opcode::EpochFinalize),
            0x0D => Some(Opcode::SmpEnvelope),
            0xFF => Some(Opcode::ErrorResponse),
            _ => None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip_all() {
        for b in 0x00u8..=0xFF {
            if let Some(op) = Opcode::from_u8(b) {
                assert_eq!(op.to_u8(), b);
            }
        }
        assert_eq!(Opcode::EpochFinalize.to_u8(), 0x0C);
        assert_eq!(Opcode::SmpEnvelope.to_u8(), 0x0D);
        assert_eq!(Opcode::from_u8(0x77), None);
    }
}
