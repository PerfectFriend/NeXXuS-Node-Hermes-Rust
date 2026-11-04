//! BIP-39 mnemonic + seed derivation (ADR-0003/keys).
//! PBKDF2-HMAC-SHA512, 2048 rounds, salt "mnemonic" + optional passphrase.

use crate::error::NexxusError;
use bip39::{Language, Mnemonic};
use pbkdf2::pbkdf2_hmac_array;
use sha2::{Digest, Sha256, Sha512};
use zeroize::Zeroizing;

/// BIP-39 mnemonic phrase + derived 64-byte seed.
#[derive(Debug, Clone)]
pub struct IdentitySeed {
    pub mnemonic: String,
    pub seed: Zeroizing<[u8; 64]>,
}

impl IdentitySeed {
    /// Generate a new 12-word mnemonic (128-bit entropy) and its BIP-39 seed.
    pub fn generate() -> Result<Self, NexxusError> {
        let mnemonic = Mnemonic::generate_in(Language::English, 12)
            .map_err(|e| NexxusError::Io(format!("mnemonic gen failed: {e}")))?;
        let phrase = mnemonic.to_string();
        let seed = Self::phrase_to_seed(&phrase)?;
        Ok(Self {
            mnemonic: phrase,
            seed: Zeroizing::new(seed),
        })
    }

    /// Validate an existing mnemonic phrase against the BIP-39 wordlist + checksum.
    pub fn validate(phrase: &str) -> Result<Self, NexxusError> {
        let _mnemonic: Mnemonic = phrase
            .parse()
            .map_err(|_| NexxusError::Io("invalid mnemonic".into()))?;
        let seed = Self::phrase_to_seed(phrase)?;
        Ok(Self {
            mnemonic: phrase.to_string(),
            seed: Zeroizing::new(seed),
        })
    }

    /// PBKDF2-HMAC-SHA512, 2048 rounds, salt = "mnemonic" + passphrase (empty).
    fn phrase_to_seed(phrase: &str) -> Result<[u8; 64], NexxusError> {
        let salt = format!("mnemonic{}", String::new()); // passphrase is empty by default
        Ok(pbkdf2_hmac_array::<Sha512, 64>(
            phrase.as_bytes(),
            salt.as_bytes(),
            2048,
        ))
    }

    pub fn seed_bytes(&self) -> &[u8; 64] {
        &self.seed
    }
}

/// Deterministic X25519 secret derived from the BIP-39 seed with a domain
/// separator (so it is independent of the SLIP-0010 Ed25519 key).
pub fn x25519_secret_from_seed(seed: &[u8; 64]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(b"nexxus-x25519-secret");
    h.update(seed);
    h.finalize().into()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn generate_and_validate() {
        let s = IdentitySeed::generate().unwrap();
        IdentitySeed::validate(&s.mnemonic).unwrap();
        assert_eq!(s.mnemonic.split_whitespace().count(), 12);
        assert!(s.seed.iter().any(|&b| b != 0));
    }

    /// Cross-check against BIP-39 golden vector: abandon...about -> known seed.
    #[test]
    fn matches_bip39_golden_vector() {
        let phrase = "abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon abandon about";
        let s = IdentitySeed::validate(phrase).unwrap();
        let expected = hex::decode("5eb00bbddcf069084889a8ab9155568165f5c453ccb85e70811aaed6f6da5fc19a5ac40b389cd370d086206dec8aa6c43daea6690f20ad3d8d48b2d2ce9e38e4").unwrap();
        assert_eq!(&s.seed[..], expected.as_slice());
    }

    #[test]
    fn invalid_mnemonic_rejected() {
        assert!(IdentitySeed::validate("not a valid phrase at all").is_err());
    }
}
