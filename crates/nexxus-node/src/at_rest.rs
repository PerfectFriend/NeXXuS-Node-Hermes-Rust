//! Шифрование чанков at rest (Phase A2 плана эволюции).
//!
//! Ключ стора выводится из BIP-39 seed ноды через HKDF-SHA256
//! (salt = "nexxus-store-v1", info = "nexxus-store-key"). Каждый чанк
//! шифруется XChaCha20-Poly1305 с nonce = первые 24 байта chunk_hash:
//! ChunkHash = SHA-256(payload), поэтому одинаковый nonce возможен только
//! у одинакового контента — утечки нет (равенство и так видно по ключу).
//! В redb хранится только ciphertext+tag; флаг формата — в meta.

use chacha20poly1305::aead::{Aead, KeyInit};
use chacha20poly1305::{Key, XChaCha20Poly1305, XNonce};
use hmac::{Hmac, Mac};
use nexxus_core::error::NexxusError;
use nexxus_core::types::ChunkHash;
use sha2::Sha256;

/// Ключ в meta, помечающий, что стор зашифрован.
pub const STORE_ENCRYPTION_META: &str = "store_encryption";
/// Значение флага для XChaCha20-Poly1305 (v1).
pub const STORE_ENCRYPTION_V1: &str = "xchacha20poly1305-v1";

const HKDF_SALT: &[u8] = b"nexxus-store-v1";
const HKDF_INFO: &[u8] = b"nexxus-store-key";

/// 256-битный ключ шифрования стора, выведенный из seed.
#[derive(Clone)]
pub struct StoreKey(pub [u8; 32]);

impl StoreKey {
    /// HKDF-SHA256 (extract+expand, RFC 5869) от seed ноды.
    pub fn derive(seed: &[u8]) -> Self {
        type HmacSha256 = Hmac<Sha256>;
        // extract
        let mut extract = <HmacSha256 as Mac>::new_from_slice(HKDF_SALT).expect("HMAC accepts any key len");
        extract.update(seed);
        let prk = extract.finalize().into_bytes();
        // expand (нам нужен ровно один блок по 32 байта)
        let mut expand = <HmacSha256 as Mac>::new_from_slice(&prk).expect("HMAC accepts any key len");
        expand.update(HKDF_INFO);
        expand.update(&[0x01]);
        let okm = expand.finalize().into_bytes();
        let mut key = [0u8; 32];
        key.copy_from_slice(&okm[..32]);
        StoreKey(key)
    }
}

fn cipher(key: &StoreKey) -> XChaCha20Poly1305 {
    XChaCha20Poly1305::new(Key::from_slice(&key.0))
}

/// Nonce чанка: первые 24 байта его хеша (детерминированно, см. шапку модуля).
fn nonce_for(hash: &ChunkHash) -> XNonce {
    XNonce::clone_from_slice(&hash.0[..24])
}

/// Шифрует чанк: на выходе ciphertext || tag (16 байта), nonce не хранится.
pub fn encrypt_chunk(key: &StoreKey, hash: &ChunkHash, plaintext: &[u8]) -> Vec<u8> {
    cipher(key)
        .encrypt(&nonce_for(hash), plaintext)
        .expect("XChaCha20-Poly1305 encryption of in-memory buffer cannot fail")
}

/// Дешифрует чанк; ошибка = неверный ключ или повреждённые данные.
pub fn decrypt_chunk(key: &StoreKey, hash: &ChunkHash, ciphertext: &[u8]) -> Result<Vec<u8>, NexxusError> {
    cipher(key)
        .decrypt(&nonce_for(hash), ciphertext)
        .map_err(|_| NexxusError::Io("chunk decrypt failed: wrong store key or corrupted data".into()))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_key() -> StoreKey {
        StoreKey::derive(&[0xABu8; 64])
    }

    #[test]
    fn encrypt_decrypt_roundtrip() {
        let key = test_key();
        let hash = ChunkHash([0x11u8; 32]);
        let plaintext = b"hello nexxus chunk payload";
        let ct = encrypt_chunk(&key, &hash, plaintext);
        assert_ne!(&ct[..plaintext.len()], &plaintext[..], "ciphertext must not contain plaintext");
        assert_eq!(decrypt_chunk(&key, &hash, &ct).unwrap(), plaintext);
    }

    #[test]
    fn wrong_key_fails() {
        let hash = ChunkHash([0x22u8; 32]);
        let ct = encrypt_chunk(&test_key(), &hash, b"secret");
        let other = StoreKey::derive(&[0xCDu8; 64]);
        assert!(decrypt_chunk(&other, &hash, &ct).is_err());
    }

    #[test]
    fn tampered_ciphertext_fails() {
        let key = test_key();
        let hash = ChunkHash([0x33u8; 32]);
        let mut ct = encrypt_chunk(&key, &hash, b"secret");
        let last = ct.len() - 1;
        ct[last] ^= 0x01;
        assert!(decrypt_chunk(&key, &hash, &ct).is_err());
    }

    #[test]
    fn different_chunks_get_different_ciphertexts() {
        let key = test_key();
        let a = encrypt_chunk(&key, &ChunkHash([1u8; 32]), b"same");
        let b = encrypt_chunk(&key, &ChunkHash([2u8; 32]), b"same");
        assert_ne!(a, b, "nonce различается по chunk hash");
    }

    #[test]
    fn hkdf_is_deterministic_and_seed_sensitive() {
        let k1 = StoreKey::derive(&[7u8; 64]);
        let k2 = StoreKey::derive(&[7u8; 64]);
        let k3 = StoreKey::derive(&[8u8; 64]);
        assert_eq!(k1.0, k2.0);
        assert_ne!(k1.0, k3.0);
    }
}
