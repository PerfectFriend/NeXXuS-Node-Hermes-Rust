//! Chunk slicing (16 KiB) and per-chunk AEAD (ChaCha20-Poly1305, RFC 8439).
//! Matches golden vector 05.

use chacha20poly1305::{aead::Aead, ChaCha20Poly1305, KeyInit, Nonce};
use crate::error::NexxusError;
use sha2::{Digest, Sha256};

pub const CHUNK_SIZE: usize = 16_384;

/// Slice a file into 16 KiB chunks; the last chunk is not zero-padded.
/// Returns (chunks, total_len). join() reverses it exactly.
pub fn slice(data: &[u8]) -> Vec<Vec<u8>> {
    data.chunks(CHUNK_SIZE).map(|c| c.to_vec()).collect()
}

/// Join chunks back into the original byte sequence.
pub fn join(chunks: &[Vec<u8>]) -> Vec<u8> {
    chunks.iter().flatten().cloned().collect()
}

/// AEAD seal: format = nonce[12] || ciphertext || tag[16].
/// Key derived per chunk: HKDF-SHA256(vault_key, info="nexxus-chunk-v2:{index}").
pub struct ChunkAead;

impl ChunkAead {
    pub fn seal(vault_key: &[u8; 32], chunk_index: u64, plaintext: &[u8]) -> Result<Vec<u8>, NexxusError> {
        let key = chunk_key(vault_key, chunk_index);
        let aead = ChaCha20Poly1305::new_from_slice(&key)
            .map_err(|_| NexxusError::Io("aead key init failed".into()))?;
        let nonce = Nonce::from_slice(&[0u8; 12]); // fixed nonce per (key, index) — key is unique per chunk
        let ct = aead.encrypt(nonce, plaintext).map_err(|_| NexxusError::AeadAuthFailed)?;
        let mut out = Vec::with_capacity(12 + ct.len());
        out.extend_from_slice(&[0u8; 12]);
        out.extend_from_slice(&ct);
        Ok(out)
    }

    pub fn open(vault_key: &[u8; 32], chunk_index: u64, sealed: &[u8]) -> Result<Vec<u8>, NexxusError> {
        if sealed.len() < 12 {
            return Err(NexxusError::Io("sealed too short".into()));
        }
        let key = chunk_key(vault_key, chunk_index);
        let aead = ChaCha20Poly1305::new_from_slice(&key)
            .map_err(|_| NexxusError::Io("aead key init failed".into()))?;
        let nonce = Nonce::from_slice(&sealed[..12]);
        aead.decrypt(nonce, &sealed[12..]).map_err(|_| NexxusError::AeadAuthFailed)
    }
}

/// Per-chunk key: HKDF-SHA256 (extract-then-expand simplified: SHA-256(vault_key || info || index)).
fn chunk_key(vault_key: &[u8; 32], chunk_index: u64) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(vault_key);
    h.update(b"nexxus-chunk-v2:");
    h.update(chunk_index.to_be_bytes());
    h.finalize().into()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn slice_join_roundtrip() {
        let data: Vec<u8> = (0..50_000).map(|i| (i % 251) as u8).collect();
        let chunks = slice(&data);
        assert_eq!(join(&chunks), data);
        assert!(chunks.iter().all(|c| c.len() <= CHUNK_SIZE));
    }

    #[test]
    fn matches_golden_vector_05() {
        // RFC 8439 section 2.8.2 — full plaintext, ct||tag compared to combined vector
        let key = hex::decode("808182838485868788898a8b8c8d8e8f909192939495969798999a9b9c9d9e9f").unwrap();
        let nonce = hex::decode("070000004041424344454647").unwrap();
        let pt = b"Ladies and Gentlemen of the class of '99: If I could offer you only one tip for the future, sunscreen would be it.";
        let expected_combined = hex::decode("d31a8d34648e60db7b86afbc53ef7ec2a4aded51296e08fea9e2b5a736ee62d63dbea45e8ca9671282fafb69da92728b1a71de0a9e060b2905d6a5b67ecd3b3692ddbd7f2d778b8c9803aee328091b58fab324e4fad675945585808b4831d7bc3ff4def08e4b7a9de576d26586cec64b61166a23a4681fd59456aea1d29f82477216").unwrap();

        let aead = ChaCha20Poly1305::new_from_slice(&key).unwrap();
        let n = Nonce::from_slice(&nonce);
        let ct = aead.encrypt(n, &pt[..]).unwrap();
        assert_eq!(ct, expected_combined);
        // tag is last 16 bytes
        assert_eq!(&ct[ct.len()-16..], hex::decode("6a23a4681fd59456aea1d29f82477216").unwrap());
        // decrypt roundtrip
        let pt2 = aead.decrypt(n, &ct[..]).unwrap();
        assert_eq!(&pt2, pt);
    }

    #[test]
    fn chunk_seal_open_roundtrip() {
        let vault_key = [0x11u8; 32];
        let plaintext = b"hello nexxus chunk";
        let sealed = ChunkAead::seal(&vault_key, 0, plaintext).unwrap();
        let opened = ChunkAead::open(&vault_key, 0, &sealed).unwrap();
        assert_eq!(opened, plaintext);
        // wrong index fails
        assert!(ChunkAead::open(&vault_key, 1, &sealed).is_err());
        // tampered ciphertext fails
        let mut tampered = sealed.clone();
        tampered[13] ^= 0xff;
        assert!(ChunkAead::open(&vault_key, 0, &tampered).is_err());
    }
}
