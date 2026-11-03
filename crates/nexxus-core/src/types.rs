//! Core newtypes: NodeId, ChunkHash, OnionAddress, Money (ADR-0004).

use core::fmt;

/// 256-bit node identifier in the Kademlia space.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Ord, PartialOrd, Debug)]
pub struct NodeId(pub [u8; 32]);

/// SHA-256 digest of a chunk's payload.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct ChunkHash(pub [u8; 32]);

/// Raw Tor v3 onion address bytes: pubkey(32) || checksum(2) || version(1)=0x03.
#[derive(Clone, Copy, PartialEq, Eq, Hash, Debug)]
pub struct OnionAddress(pub [u8; 35]);

/// Fixed-point token amount in micro-NEXX. 1 NEXX = 1_000_000_000. No floats.
#[derive(Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Hash, Default, Debug)]
pub struct Money(pub i64);

impl Money {
    pub const MICRO_PER_NEXX: i64 = 1_000_000_000;

    pub const fn zero() -> Self {
        Money(0)
    }

    pub const fn from_nexx(n: i64) -> Self {
        Money(n * Self::MICRO_PER_NEXX)
    }

    /// Render as decimal string with up to 9 fractional digits, trimming trailing zeros.
    pub fn to_decimal_string(&self) -> String {
        let neg = self.0 < 0;
        let abs = self.0.unsigned_abs();
        let whole = abs / (Self::MICRO_PER_NEXX as u64);
        let frac = abs % (Self::MICRO_PER_NEXX as u64);
        if frac == 0 {
            return format!("{}{}", if neg { "-" } else { "" }, whole);
        }
        let frac_s = format!("{:09}", frac).trim_end_matches('0').to_string();
        format!("{}{}.{}", if neg { "-" } else { "" }, whole, frac_s)
    }
}

impl fmt::Display for Money {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.to_decimal_string())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn money_roundtrip() {
        // "1.25" NEXX -> 1_250_000_000 micro -> back to "1.25"
        let m = Money(1_250_000_000);
        assert_eq!(m.to_decimal_string(), "1.25");
        assert_eq!(Money::from_nexx(1).to_decimal_string(), "1");
        assert_eq!(Money(-1_250_000_000).to_decimal_string(), "-1.25");
        assert_eq!(Money(0).to_decimal_string(), "0");
    }
}
