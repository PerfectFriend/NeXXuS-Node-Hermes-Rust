//! Ed25519 identity + Tor v3 onion address.
//! node_id = SHA-256(verifying_key)
//! onion = base32(pubkey[32] || SHA-256(".onion checksum" || pubkey || 0x03)[..2] || 0x03)

use crate::error::NexxusError;
use crate::types::{NodeId, OnionAddress};
use ed25519_dalek::{Signer, SigningKey, Verifier, VerifyingKey};
use rand::rngs::OsRng;
use sha2::{Digest, Sha256};

#[cfg(test)]
use data_encoding::BASE32_NOPAD;

/// Full signing identity: secret key + derived public key.
#[derive(Debug, Clone)]
pub struct Identity {
    pub signing_key: SigningKey,
    pub verifying_key: VerifyingKey,
}

impl Identity {
    /// Generate a fresh random identity.
    pub fn generate() -> Self {
        let signing_key = SigningKey::generate(&mut OsRng);
        let verifying_key = signing_key.verifying_key();
        Self {
            signing_key,
            verifying_key,
        }
    }

    /// Reconstruct from raw secret key bytes.
    pub fn from_secret(secret: &[u8; 32]) -> Result<Self, NexxusError> {
        let signing_key = SigningKey::from_bytes(secret);
        let verifying_key = signing_key.verifying_key();
        Ok(Self {
            signing_key,
            verifying_key,
        })
    }

    /// Node identifier used in Kademlia space: SHA-256(verifying_key bytes).
    pub fn node_id(&self) -> NodeId {
        let mut h = Sha256::new();
        h.update(self.verifying_key.as_bytes());
        NodeId(h.finalize().into())
    }

    /// Tor v3 onion address bytes.
    pub fn onion_address(&self) -> OnionAddress {
        let pk = self.verifying_key.as_bytes();
        let mut check = Sha256::new();
        check.update(b".onion checksum");
        check.update(pk);
        check.update([0x03]);
        let checksum = check.finalize();
        let mut raw = [0u8; 35];
        raw[..32].copy_from_slice(pk);
        raw[32..34].copy_from_slice(&checksum[..2]);
        raw[34] = 0x03;
        OnionAddress(raw)
    }

    /// Sign arbitrary data; signature is 64 bytes.
    pub fn sign(&self, message: &[u8]) -> [u8; 64] {
        self.signing_key.sign(message).to_bytes()
    }

    /// Verify a signature with another identity's public key.
    pub fn verify(pubkey: &VerifyingKey, message: &[u8], signature: &[u8; 64]) -> bool {
        pubkey.verify(message, &ed25519_dalek::Signature::from_bytes(signature)).is_ok()
    }
}

impl From<&Identity> for NodeId {
    fn from(id: &Identity) -> Self {
        id.node_id()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn generate_and_sign_verify() {
        let id = Identity::generate();
        let msg = b"hello nexxus";
        let sig = id.sign(msg);
        assert!(Identity::verify(&id.verifying_key, msg, &sig));
        assert!(!Identity::verify(&id.verifying_key, b"tampered", &sig));
    }

    /// Cross-check against Tor v3 golden vector (vector 02).
    #[test]
    fn onion_matches_golden_vector() {
        let pk_hex = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a";
        let pk = hex::decode(pk_hex).unwrap();
        let mut arr = [0u8; 32];
        arr.copy_from_slice(&pk);
        let verifying = VerifyingKey::from_bytes(&arr).expect("valid ed25519 pubkey");
        let secret = [0u8; 32];
        let signing_key = SigningKey::from_bytes(&secret);
        let id = Identity {
            signing_key,
            verifying_key: verifying,
        };
        let onion = id.onion_address();
        let addr = BASE32_NOPAD.encode(&onion.0).to_lowercase();
        assert_eq!(addr, "25njqamcweflpvkl73j4szahhihoc4xt3ktcgjnpaingr5yhkenjpzad");
        assert_eq!(addr.len(), 56); // 35 bytes -> 56 base32 chars (no padding)
    }

    #[test]
    fn onion_second_golden_vector() {
        let pk_hex = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";
        let pk = hex::decode(pk_hex).unwrap();
        let mut arr = [0u8; 32];
        arr.copy_from_slice(&pk);
        let verifying = VerifyingKey::from_bytes(&arr).expect("valid ed25519 pubkey");
        let secret = [0u8; 32];
        let signing_key = SigningKey::from_bytes(&secret);
        let id = Identity {
            signing_key,
            verifying_key: verifying,
        };
        let addr = BASE32_NOPAD.encode(&id.onion_address().0).to_lowercase();
        assert_eq!(addr, "aerukz4jvpg66ajdivtytk6n54asgrlhrgv433ybencwpcnlzxxunhad");
    }

    #[test]
    fn node_id_is_sha256_of_pubkey() {
        let id = Identity::generate();
        let mut h = Sha256::new();
        h.update(id.verifying_key.as_bytes());
        let digest: [u8; 32] = h.finalize().into();
        assert_eq!(id.node_id().0, digest);
    }
}
