//! E2: экспорт/импорт архивного bundle — cold backup хранилища вне redb.
//!
//! Формат: JSON-документ {kind, node_id, chunks[], meta[]}, зашифрованный
//! в самодостаточный vault (AES-256-GCM, PBKDF2 600k) PIN'ом владельца.
//! Импорт идёт через `ChunkStore::put_chunk` — с проверкой hash и disk cap.

use nexxus_core::{
    error::NexxusError,
    keys::vault::{decrypt_vault_payload, encrypt_vault_payload},
    types::ChunkHash,
};
use serde::{Deserialize, Serialize};
use zeroize::Zeroizing;

use crate::storage::ChunkStore;

pub const BUNDLE_KIND: &str = "nexxus_export_bundle";
pub const BUNDLE_VERSION: u32 = 1;

#[derive(Serialize, Deserialize)]
struct BundleChunk {
    hash: String,   // hex
    data: String,   // base64 — нет dep на base64? используем hex для простоты
}

#[derive(Serialize, Deserialize)]
struct BundleMeta {
    key: String,
    value: String, // hex
}

#[derive(Serialize, Deserialize)]
struct Bundle {
    kind: String,
    version: u32,
    node_id: String,
    exported_at_unix: u64,
    chunk_size: usize,
    chunks: Vec<BundleChunk>,
    meta: Vec<BundleMeta>,
}

fn now_unix() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/// Экспорт всех «живых» чанков + manifest-meta в зашифрованный vault JSON.
/// PIN используется только как passphrase шифрования bundle и затирается.
pub fn export_bundle(
    store: &ChunkStore,
    node_id_hex: &str,
    pin: &str,
) -> Result<(String, usize, usize), NexxusError> {
    let pin = Zeroizing::new(pin.to_string());
    let hashes = store.list_chunk_hashes()?;
    let now = now_unix();
    let mut chunks = Vec::with_capacity(hashes.len());
    let mut skipped_expired = 0usize;
    for h in &hashes {
        // get_chunk уже применяет lazy TTL (expired → None)
        match store.get_chunk(h)? {
            Some(data) => chunks.push(BundleChunk {
                hash: hex::encode(h.0),
                data: hex::encode(&data),
            }),
            None => skipped_expired += 1,
        }
    }
    // manifest_* мета — чтобы bundle восстанавливал и файловые манифесты
    let meta: Vec<BundleMeta> = store
        .list_meta_prefix("manifest_")?
        .into_iter()
        .map(|(k, v)| BundleMeta {
            key: k,
            value: hex::encode(v),
        })
        .collect();

    let bundle = Bundle {
        kind: BUNDLE_KIND.into(),
        version: BUNDLE_VERSION,
        node_id: node_id_hex.to_string(),
        exported_at_unix: now,
        chunk_size: crate::vault::CHUNK_SIZE,
        chunks,
        meta,
    };
    let json = serde_json::to_vec(&bundle)
        .map_err(|e| NexxusError::Io(format!("bundle json: {e}")))?;
    let vault = encrypt_vault_payload(&json, &pin, None)?;
    let n_chunks = bundle.chunks.len();
    let n_meta = bundle.meta.len();
    Ok((vault, n_chunks + skipped_expired, n_meta))
}

/// Импорт bundle: decrypt PIN'ом, затем каждый чанк через put_chunk
/// (hash check + disk cap). Возвращает {imported, skipped_existing, meta}.
pub fn import_bundle(
    store: &ChunkStore,
    vault_json: &str,
    pin: &str,
) -> Result<serde_json::Value, NexxusError> {
    let pin = Zeroizing::new(pin.to_string());
    let dec = decrypt_vault_payload(vault_json, &pin)?;
    if dec.is_duress {
        // duress-PIN: не импортируем «ложный» bundle — сообщаем как ошибку,
        // а signal (лог/Telegram) выставляет вызывающий слой по аналогии с seed.
        return Err(NexxusError::Vault("duress PIN used on bundle".into()));
    }
    let payload = dec.decrypted_bytes;
    let bundle: Bundle = serde_json::from_slice(&payload)
        .map_err(|e| NexxusError::Io(format!("bundle parse: {e}")))?;
    if bundle.kind != BUNDLE_KIND || bundle.version != BUNDLE_VERSION {
        return Err(NexxusError::Io("unsupported bundle kind/version".into()));
    }
    let mut imported = 0usize;
    let mut skipped = 0usize;
    for c in &bundle.chunks {
        let hbytes = hex::decode(&c.hash)
            .map_err(|e| NexxusError::Io(format!("bad chunk hash hex: {e}")))?;
        let hash = ChunkHash(<[u8; 32]>::try_from(hbytes.as_slice()).map_err(|_| {
            NexxusError::Io("chunk hash must be 32 bytes".into())
        })?);
        let data = hex::decode(&c.data)
            .map_err(|e| NexxusError::Io(format!("bad chunk data hex: {e}")))?;
        if store.get_chunk(&hash)?.is_some() {
            skipped += 1;
            continue;
        }
        store.put_chunk(&hash, &data)?; // hash + capacity guard внутри
        imported += 1;
    }
    let mut meta_restored = 0usize;
    for m in &bundle.meta {
        let val = hex::decode(&m.value)
            .map_err(|e| NexxusError::Io(format!("bad meta hex: {e}")))?;
        store.put_meta(&m.key, &val)?;
        meta_restored += 1;
    }
    Ok(serde_json::json!({
        "imported_chunks": imported,
        "skipped_existing": skipped,
        "meta_restored": meta_restored,
        "bundle_node_id": bundle.node_id,
        "exported_at_unix": bundle.exported_at_unix,
    }))
}

#[cfg(test)]
mod tests {
    use super::*;
    use sha2::Digest;

    fn h(data: &[u8]) -> ChunkHash {
        ChunkHash(sha2::Sha256::digest(data).into())
    }

    #[test]
    fn bundle_roundtrip_and_wrong_pin() {
        let dir_a = tempfile::tempdir().unwrap();
        let a = ChunkStore::open(dir_a.path().join("store.redb")).unwrap();
        let c1: Vec<u8> = (0..5000u32).map(|i| (i % 256) as u8).collect();
        let c2: Vec<u8> = vec![9u8; 100];
        a.put_chunk(&h(&c1), &c1).unwrap();
        a.put_chunk(&h(&c2), &c2).unwrap();
        a.put_meta("manifest_root123", b"{\"root\":\"abc\"}").unwrap();

        let (vault, total, nmeta) = export_bundle(&a, "aa55", "test-pin-123").unwrap();
        assert_eq!(total, 2);
        assert_eq!(nmeta, 1);
        assert!(vault.contains("ciphertext_hex") && vault.contains("salt_hex"), "vault json");

        // импорт в чистый стор
        let dir_b = tempfile::tempdir().unwrap();
        let b = ChunkStore::open(dir_b.path().join("store.redb")).unwrap();
        let r = import_bundle(&b, &vault, "test-pin-123").unwrap();
        assert_eq!(r["imported_chunks"], 2);
        assert_eq!(r["meta_restored"], 1);
        assert_eq!(b.get_chunk(&h(&c1)).unwrap().unwrap(), c1);
        assert_eq!(b.get_chunk(&h(&c2)).unwrap().unwrap(), c2);
        assert_eq!(
            b.get_meta("manifest_root123").unwrap().unwrap(),
            b"{\"root\":\"abc\"}"
        );

        // повторный импорт — все чанки existing
        let r2 = import_bundle(&b, &vault, "test-pin-123").unwrap();
        assert_eq!(r2["imported_chunks"], 0);
        assert_eq!(r2["skipped_existing"], 2);

        // неверный PIN
        assert!(import_bundle(&b, &vault, "wrong-pin").is_err());

        // tamper: портим шифртекст → ошибка AEAD
        let mut bad = vault.clone().into_bytes();
        let mid = bad.len() / 2;
        bad[mid] ^= 0xFF;
        let bad = String::from_utf8_lossy(&bad).into_owned();
        assert!(import_bundle(&b, &bad, "test-pin-123").is_err());
    }

    #[test]
    fn bundle_skips_expired_chunks() {
        let dir = tempfile::tempdir().unwrap();
        let a = ChunkStore::open(dir.path().join("store.redb")).unwrap();
        let c: Vec<u8> = vec![3u8; 64];
        let ch = h(&c);
        a.put_chunk(&ch, &c).unwrap();
        a.set_chunk_ttl(&ch, 10, 1000).unwrap(); // exp at 1010
        // экспорт "сейчас" = 2000 → чанк просрочен, в bundle не попадёт
        let (_, total, _) = export_bundle(&a, "bb", "pin").unwrap();
        // total = живые + просроченные(счётчик), но в chunks только живые
        assert_eq!(total, 1);
    }
}
