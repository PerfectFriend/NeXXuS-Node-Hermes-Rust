//! wasm-bindgen surface for the browser panel: real bindings over nexxus-core
//! (chunking, Reed-Solomon, Merkle, identity from mnemonic). Pure functions —
//! no I/O, no network.

use wasm_bindgen::prelude::*;

use nexxus_core::keys::identity::Identity;
use nexxus_core::keys::seed::IdentitySeed;
use nexxus_core::keys::slip10::DerivedKey;
use nexxus_core::{chunk, merkle, rs};
use sha2::{Digest, Sha256};

fn sha256(data: &[u8]) -> [u8; 32] {
    Sha256::digest(data).into()
}

/// Crate version.
#[wasm_bindgen]
pub fn version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

/// Generate a fresh BIP-39 mnemonic (shown once — the caller must persist it).
#[wasm_bindgen]
pub fn generate_mnemonic() -> Result<String, JsError> {
    let seed = IdentitySeed::generate().map_err(|e| JsError::new(&e.to_string()))?;
    Ok(seed.mnemonic.clone())
}

/// Derive the node id (hex of Ed25519 pubkey) from a BIP-39 mnemonic,
/// via SLIP-0010 m/44'/999'/0'/0/0 — same path as the node's identity store.
#[wasm_bindgen]
pub fn node_id_from_mnemonic(phrase: &str) -> Result<String, JsError> {
    let seed = IdentitySeed::validate(phrase).map_err(|e| JsError::new(&e.to_string()))?;
    let derived = DerivedKey::from_seed(seed.seed_bytes()).map_err(|e| JsError::new(&e.to_string()))?;
    let identity = Identity::from_secret(&derived.private_key).map_err(|e| JsError::new(&e.to_string()))?;
    Ok(hex_encode(&identity.node_id().0))
}

/// Number of 16 KiB chunks a file of `data_len` bytes splits into.
#[wasm_bindgen]
pub fn chunk_count(data_len: u32) -> u32 {
    chunk::slice(&vec![0u8; data_len as usize]).len() as u32
}

/// Slice a file into 16 KiB chunks and return them concatenated
/// (last chunk zero-padded to CHUNK_SIZE).
#[wasm_bindgen]
pub fn chunk_data(data: &[u8]) -> Vec<u8> {
    let chunks = chunk::slice(data);
    let mut out = Vec::with_capacity(chunks.len() * chunk::CHUNK_SIZE);
    for mut c in chunks {
        c.resize(chunk::CHUNK_SIZE, 0);
        out.extend_from_slice(&c);
    }
    out
}

/// Reed-Solomon encode one chunk: returns 6 shards (4 data + 2 parity)
/// concatenated, each `ceil(chunk_len/4)` bytes.
#[wasm_bindgen]
pub fn rs_encode_chunk(data: &[u8]) -> Vec<u8> {
    let shards = rs::encode(data);
    let shard_len = shards[0].len();
    let mut out = Vec::with_capacity(shard_len * rs::TOTAL_SHARDS);
    for s in &shards {
        out.extend_from_slice(s);
    }
    out
}

/// Recover the original chunk from the first 4 shards of a flat
/// `rs_encode_chunk` output. `original_len` is the pre-encode length.
#[wasm_bindgen]
pub fn rs_decode_shards(shards_flat: &[u8], original_len: u32) -> Result<Vec<u8>, JsError> {
    let shard_len = shards_flat.len() / rs::TOTAL_SHARDS;
    if shard_len * rs::TOTAL_SHARDS != shards_flat.len() {
        return Err(JsError::new("shard buffer not a multiple of 6 shards"));
    }
    let surviving: Vec<(&[u8], usize)> = (0..rs::DATA_SHARDS)
        .map(|i| (&shards_flat[i * shard_len..(i + 1) * shard_len], i))
        .collect();
    rs::decode(&surviving, original_len as usize).map_err(|e| JsError::new(&e.to_string()))
}

/// Merkle root (SHA-256 leaves over 16 KiB zero-padded chunks) of a file,
/// as 32 raw bytes.
#[wasm_bindgen]
pub fn merkle_root_of_file(data: &[u8]) -> Vec<u8> {
    let chunks = chunk::slice(data);
    let leaves: Vec<[u8; 32]> = chunks
        .iter()
        .map(|c| {
            let mut padded = c.clone();
            padded.resize(chunk::CHUNK_SIZE, 0);
            sha256(&padded)
        })
        .collect();
    merkle::merkle_root(&leaves).to_vec()
}

fn hex_encode(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn wasm_surface_roundtrip() {
        let data: Vec<u8> = (0..40_000u32).map(|i| (i % 251) as u8).collect();
        let n = chunk_count(data.len() as u32);
        assert_eq!(n, 3); // 40000 / 16384 = 2.44 -> 3
        let flat = chunk_data(&data);
        assert_eq!(flat.len(), 3 * chunk::CHUNK_SIZE);

        let chunk0 = &flat[..chunk::CHUNK_SIZE];
        let shards = rs_encode_chunk(chunk0);
        assert_eq!(shards.len(), 6 * (chunk::CHUNK_SIZE / 4));
        let back = rs_decode_shards(&shards, chunk::CHUNK_SIZE as u32).unwrap();
        assert_eq!(back, chunk0);

        let root = merkle_root_of_file(&data);
        assert_eq!(root.len(), 32);
    }

    #[test]
    fn mnemonic_to_stable_node_id() {
        let m = generate_mnemonic().unwrap();
        let id1 = node_id_from_mnemonic(&m).unwrap();
        let id2 = node_id_from_mnemonic(&m).unwrap();
        assert_eq!(id1, id2);
        assert_eq!(id1.len(), 64);
    }
}
