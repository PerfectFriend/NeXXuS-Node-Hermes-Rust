//! Persistent chunk index on redb (ADR-0005).
//! Key = ChunkHash (32 bytes), value = raw chunk bytes. No external DB daemon.

use nexxus_core::{error::NexxusError, types::ChunkHash};
use redb::{Database, ReadableTable, TableDefinition};

const CHUNKS: TableDefinition<[u8; 32], &[u8]> = TableDefinition::new("chunks");
/// Key-value metadata table (identity mnemonic, future settings).
const META: TableDefinition<&str, &[u8]> = TableDefinition::new("meta");

pub struct ChunkStore {
    db: Database,
    path: std::path::PathBuf,
    /// Ключ шифрования at rest (Phase A2). None = plaintext-режим (legacy/тесты).
    crypto: std::sync::Mutex<Option<crate::at_rest::StoreKey>>,
}

impl ChunkStore {
    pub fn open<P: AsRef<std::path::Path>>(path: P) -> Result<Self, NexxusError> {
        let path = path.as_ref().to_path_buf();
        let db = Database::create(&path).map_err(|e| NexxusError::Io(format!("redb create: {e}")))?;
        // Файл стора содержит (зашифрованные) данные и meta — только владелец.
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let _ = std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o600));
        }
        // Eagerly ensure the schema: in a write transaction open_table creates
        // the table if it is missing, so legacy stores (written before the
        // Rust daemon, without "chunks") become readable instead of failing
        // every read with TableDoesNotExist.
        {
            let wtx = db
                .begin_write()
                .map_err(|e| NexxusError::Io(format!("redb write tx: {e}")))?;
            {
                let _table = wtx
                    .open_table(CHUNKS)
                    .map_err(|e| NexxusError::Io(format!("redb table: {e}")))?;
            }
            {
                let _table = wtx
                    .open_table(META)
                    .map_err(|e| NexxusError::Io(format!("redb table: {e}")))?;
            }
            wtx.commit()
                .map_err(|e| NexxusError::Io(format!("redb commit: {e}")))?;
        }
        Ok(Self {
            db,
            path,
            crypto: std::sync::Mutex::new(None),
        })
    }

    /// Включает шифрование at rest ключом, выведенным из seed (at_rest::StoreKey).
    ///
    /// Если стор уже помечен как зашифрованный (meta-флаг) — ключ просто
    /// устанавливается (с проверкой дешифрования первого чанка). Если стор
    /// открыт (флага нет) — выполняется миграция: один проход re-encrypt всех
    /// чанков, затем флаг. Возвращает число мигрированных чанков.
    pub fn enable_encryption(&self, key: crate::at_rest::StoreKey) -> Result<usize, NexxusError> {
        use crate::at_rest::{decrypt_chunk, encrypt_chunk, STORE_ENCRYPTION_META, STORE_ENCRYPTION_V1};
        match self.get_meta(STORE_ENCRYPTION_META)? {
            Some(flag) => {
                if flag != STORE_ENCRYPTION_V1.as_bytes() {
                    return Err(NexxusError::Io(format!(
                        "unsupported store encryption format: {}",
                        String::from_utf8_lossy(&flag)
                    )));
                }
                // Уже зашифрован: проверяем ключ на первом чанке.
                let hashes = self.list_chunk_hashes()?;
                if let Some(first) = hashes.first() {
                    let raw = self.get_chunk_raw(first)?.ok_or_else(|| {
                        NexxusError::Io("chunk listed but missing".into())
                    })?;
                    decrypt_chunk(&key, first, &raw)?;
                }
                *self.crypto.lock().unwrap() = Some(key);
                Ok(0)
            }
            None => {
                // Миграция открытого стора: читаем все, шифруем, пишем одной транзакцией.
                let rtx = self
                    .db
                    .begin_read()
                    .map_err(|e| NexxusError::Io(format!("redb read tx: {e}")))?;
                let pairs: Vec<(ChunkHash, Vec<u8>)> = match rtx.open_table(CHUNKS) {
                    Ok(t) => t
                        .iter()
                        .map_err(|e| NexxusError::Io(format!("redb iter: {e}")))?
                        .collect::<Result<Vec<_>, redb::StorageError>>()
                        .map_err(|e| NexxusError::Io(format!("redb iter item: {e}")))?
                        .into_iter()
                        .map(|(k, v)| (ChunkHash(k.value()), v.value().to_vec()))
                        .collect(),
                    Err(redb::TableError::TableDoesNotExist(_)) => Vec::new(),
                    Err(e) => return Err(NexxusError::Io(format!("redb table: {e}"))),
                };
                drop(rtx);
                let total = pairs.len();
                let wtx = self
                    .db
                    .begin_write()
                    .map_err(|e| NexxusError::Io(format!("redb write tx: {e}")))?;
                {
                    let mut chunks = wtx
                        .open_table(CHUNKS)
                        .map_err(|e| NexxusError::Io(format!("redb table: {e}")))?;
                    for (i, (hash, plain)) in pairs.into_iter().enumerate() {
                        let ct = encrypt_chunk(&key, &hash, &plain);
                        chunks
                            .insert(hash.0, ct.as_slice())
                            .map_err(|e| NexxusError::Io(format!("redb insert: {e}")))?;
                        if i % 1000 == 0 {
                            eprintln!("nexxusd: store re-encrypt progress {}/{total}", i + 1);
                        }
                    }
                    let mut meta = wtx
                        .open_table(META)
                        .map_err(|e| NexxusError::Io(format!("redb table: {e}")))?;
                    meta.insert(STORE_ENCRYPTION_META, STORE_ENCRYPTION_V1.as_bytes())
                        .map_err(|e| NexxusError::Io(format!("redb insert: {e}")))?;
                }
                wtx.commit()
                    .map_err(|e| NexxusError::Io(format!("redb commit: {e}")))?;
                *self.crypto.lock().unwrap() = Some(key);
                eprintln!("nexxusd: store re-encrypt done, {total} chunks");
                Ok(total)
            }
        }
    }

    /// Сырое (как лежит в redb) значение чанка — для миграции и тестов.
    fn get_chunk_raw(&self, hash: &ChunkHash) -> Result<Option<Vec<u8>>, NexxusError> {
        let rtx = self
            .db
            .begin_read()
            .map_err(|e| NexxusError::Io(format!("redb read tx: {e}")))?;
        let table = match rtx.open_table(CHUNKS) {
            Ok(t) => t,
            Err(redb::TableError::TableDoesNotExist(_)) => return Ok(None),
            Err(e) => return Err(NexxusError::Io(format!("redb table: {e}"))),
        };
        Ok(table
            .get(hash.0)
            .map_err(|e| NexxusError::Io(format!("redb get: {e}")))?
            .map(|v| v.value().to_vec()))
    }

    /// Путь к файлу стора на диске (для метрик свободного места).
    pub fn path(&self) -> &std::path::Path {
        &self.path
    }

    pub fn put_chunk(&self, hash: &ChunkHash, data: &[u8]) -> Result<(), NexxusError> {
        // При включённом at-rest ключе в redb уходит только ciphertext+tag.
        let stored: Vec<u8> = match &*self.crypto.lock().unwrap() {
            Some(key) => crate::at_rest::encrypt_chunk(key, hash, data),
            None => data.to_vec(),
        };
        let wtx = self
            .db
            .begin_write()
            .map_err(|e| NexxusError::Io(format!("redb write tx: {e}")))?;
        {
            let mut table = wtx
                .open_table(CHUNKS)
                .map_err(|e| NexxusError::Io(format!("redb table: {e}")))?;
            table
                .insert(hash.0, stored.as_slice())
                .map_err(|e| NexxusError::Io(format!("redb insert: {e}")))?;
        }
        wtx.commit()
            .map_err(|e| NexxusError::Io(format!("redb commit: {e}")))?;
        Ok(())
    }

    pub fn get_chunk(&self, hash: &ChunkHash) -> Result<Option<Vec<u8>>, NexxusError> {
        let rtx = self
            .db
            .begin_read()
            .map_err(|e| NexxusError::Io(format!("redb read tx: {e}")))?;
        let table = match rtx.open_table(CHUNKS) {
            Ok(t) => t,
            // Defensive: a store written by an older version may lack the table.
            Err(redb::TableError::TableDoesNotExist(_)) => return Ok(None),
            Err(e) => return Err(NexxusError::Io(format!("redb table: {e}"))),
        };
        let res = table
            .get(hash.0)
            .map_err(|e| NexxusError::Io(format!("redb get: {e}")))?;
        let raw = res.map(|v| v.value().to_vec());
        // При включённом at-rest ключе дешифруем; ошибка = неверный ключ/повреждение.
        match (&*self.crypto.lock().unwrap(), raw) {
            (Some(key), Some(ct)) => Ok(Some(crate::at_rest::decrypt_chunk(key, hash, &ct)?)),
            (_, other) => Ok(other),
        }
    }

    /// List all stored chunk hashes (for PoR challenge selection).
    pub fn list_chunk_hashes(&self) -> Result<Vec<ChunkHash>, NexxusError> {
        let rtx = self
            .db
            .begin_read()
            .map_err(|e| NexxusError::Io(format!("redb read tx: {e}")))?;
        let table = match rtx.open_table(CHUNKS) {
            Ok(t) => t,
            Err(redb::TableError::TableDoesNotExist(_)) => return Ok(Vec::new()),
            Err(e) => return Err(NexxusError::Io(format!("redb table: {e}"))),
        };
        let mut hashes = Vec::new();
        for res in table.iter().map_err(|e| NexxusError::Io(format!("redb iter: {e}")))? {
            let (key, _val) = res.map_err(|e| NexxusError::Io(format!("redb iter item: {e}")))?;
            hashes.push(ChunkHash(key.value()));
        }
        Ok(hashes)
    }

    /// Store a metadata key (e.g. the identity mnemonic).
    pub fn put_meta(&self, key: &str, value: &[u8]) -> Result<(), NexxusError> {
        let wtx = self
            .db
            .begin_write()
            .map_err(|e| NexxusError::Io(format!("redb write tx: {e}")))?;
        {
            let mut table = wtx
                .open_table(META)
                .map_err(|e| NexxusError::Io(format!("redb table: {e}")))?;
            table
                .insert(key, value)
                .map_err(|e| NexxusError::Io(format!("redb insert: {e}")))?;
        }
        wtx.commit()
            .map_err(|e| NexxusError::Io(format!("redb commit: {e}")))?;
        Ok(())
    }

    /// Read a metadata key. Missing table (legacy store) reads as None.
    pub fn get_meta(&self, key: &str) -> Result<Option<Vec<u8>>, NexxusError> {
        let rtx = self
            .db
            .begin_read()
            .map_err(|e| NexxusError::Io(format!("redb read tx: {e}")))?;
        let table = match rtx.open_table(META) {
            Ok(t) => t,
            Err(redb::TableError::TableDoesNotExist(_)) => return Ok(None),
            Err(e) => return Err(NexxusError::Io(format!("redb table: {e}"))),
        };
        match table.get(key).map_err(|e| NexxusError::Io(format!("redb get: {e}")))? {
            Some(v) => Ok(Some(v.value().to_vec())),
            None => Ok(None),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn put_get_roundtrip() {
        let dir = tempfile::tempdir().unwrap();
        let store = ChunkStore::open(dir.path().join("store.redb")).unwrap();
        let chunk: Vec<u8> = (0..1000).map(|i| (i % 251) as u8).collect();
        let hash = ChunkHash([0x42u8; 32]);
        store.put_chunk(&hash, &chunk).unwrap();
        let got = store.get_chunk(&hash).unwrap().unwrap();
        assert_eq!(got, chunk);
        assert!(store.get_chunk(&ChunkHash([1u8; 32])).unwrap().is_none());
    }

    #[test]
    fn overwrite_chunk() {
        let dir = tempfile::tempdir().unwrap();
        let store = ChunkStore::open(dir.path().join("store.redb")).unwrap();
        let hash = ChunkHash([0x43u8; 32]);
        store.put_chunk(&hash, b"first").unwrap();
        store.put_chunk(&hash, b"second").unwrap();
        assert_eq!(store.get_chunk(&hash).unwrap().unwrap(), b"second");
    }

    #[test]
    fn open_legacy_store_without_chunks_table() {
        // Legacy store: redb file with another table but no "chunks" table
        // (like the real ~/.nexxus/store.redb written before the Rust daemon).
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("legacy.redb");
        {
            let db = redb::Database::create(&path).unwrap();
            let wtx = db.begin_write().unwrap();
            let legacy: redb::TableDefinition<u64, u64> = redb::TableDefinition::new("legacy_meta");
            {
                let mut t = wtx.open_table(legacy).unwrap();
                t.insert(1u64, 2u64).unwrap();
            }
            wtx.commit().unwrap();
        }
        let store = ChunkStore::open(&path).unwrap();
        // Regression: used to fail with "Table 'chunks' does not exist" (-32603 over WS)
        assert!(store.list_chunk_hashes().unwrap().is_empty());
        assert!(store.get_chunk(&ChunkHash([0x09u8; 32])).unwrap().is_none());
        // writes still work on the legacy file
        store.put_chunk(&ChunkHash([0x09u8; 32]), b"data").unwrap();
        assert_eq!(store.list_chunk_hashes().unwrap().len(), 1);
    }

    fn disk_bytes(path: &std::path::Path) -> Vec<u8> {
        std::fs::read(path).unwrap()
    }

    #[test]
    fn encrypted_roundtrip_and_plaintext_not_on_disk() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("store.redb");
        let store = ChunkStore::open(&path).unwrap();
        let key = crate::at_rest::StoreKey::derive(&[0x5Au8; 64]);
        assert_eq!(store.enable_encryption(key.clone()).unwrap(), 0);

        let chunk: Vec<u8> = (0..5000).map(|i| (i % 253) as u8).collect();
        let hash = ChunkHash([0x77u8; 32]);
        store.put_chunk(&hash, &chunk).unwrap();
        drop(store);

        // В сыром файле redb не должно быть plaintext чанка.
        let raw = disk_bytes(&path);
        let needle = &chunk[100..200];
        assert!(
            !raw.windows(needle.len()).any(|w| w == needle),
            "plaintext chunk leaked into the redb file"
        );

        // Через API чанк читается обратно.
        let store = ChunkStore::open(&path).unwrap();
        store.enable_encryption(key).unwrap();
        assert_eq!(store.get_chunk(&hash).unwrap().unwrap(), chunk);
    }

    #[test]
    fn migration_reencrypts_existing_plaintext_store() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("store.redb");
        let key = crate::at_rest::StoreKey::derive(&[0x6Bu8; 64]);

        // "Старый" стор: plaintext-чанки, без флага шифрования.
        {
            let store = ChunkStore::open(&path).unwrap();
            store.put_chunk(&ChunkHash([1u8; 32]), b"plain-one").unwrap();
            store.put_chunk(&ChunkHash([2u8; 32]), b"plain-two").unwrap();
        }
        let raw_before = disk_bytes(&path);
        assert!(raw_before.windows(9).any(|w| w == b"plain-one"), "precondition: plaintext on disk before migration");

        // Открываем и включаем шифрование — миграция.
        let store = ChunkStore::open(&path).unwrap();
        assert_eq!(store.enable_encryption(key.clone()).unwrap(), 2);
        assert_eq!(store.get_chunk(&ChunkHash([1u8; 32])).unwrap().unwrap(), b"plain-one");
        drop(store);

        let raw_after = disk_bytes(&path);
        assert!(!raw_after.windows(9).any(|w| w == b"plain-one"), "plaintext still on disk after migration");
        assert!(!raw_after.windows(9).any(|w| w == b"plain-two"));

        // Повторное открытие: флаг уже есть, миграции нет, ключ валидируется.
        let store = ChunkStore::open(&path).unwrap();
        assert_eq!(store.enable_encryption(key).unwrap(), 0);
        assert_eq!(store.get_chunk(&ChunkHash([2u8; 32])).unwrap().unwrap(), b"plain-two");
    }

    #[test]
    fn wrong_key_rejected_on_encrypted_store() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("store.redb");
        let store = ChunkStore::open(&path).unwrap();
        store
            .enable_encryption(crate::at_rest::StoreKey::derive(&[0x01u8; 64]))
            .unwrap();
        store.put_chunk(&ChunkHash([9u8; 32]), b"secret").unwrap();
        drop(store);

        let store = ChunkStore::open(&path).unwrap();
        let wrong = crate::at_rest::StoreKey::derive(&[0x02u8; 64]);
        assert!(store.enable_encryption(wrong).is_err(), "wrong key must be rejected");
    }

    #[test]
    fn store_file_is_private() {
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let dir = tempfile::tempdir().unwrap();
            let path = dir.path().join("store.redb");
            let _store = ChunkStore::open(&path).unwrap();
            let mode = std::fs::metadata(&path).unwrap().permissions().mode() & 0o777;
            assert_eq!(mode, 0o600, "store file must be 0600, got {mode:o}");
        }
    }
}
