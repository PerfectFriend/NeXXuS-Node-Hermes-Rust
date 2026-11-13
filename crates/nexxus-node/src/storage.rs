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
    /// E2 quick win: user-defined disk cap for the store, bytes. 0 = unlimited.
    max_store_bytes: std::sync::atomic::AtomicU64,
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
            max_store_bytes: std::sync::atomic::AtomicU64::new(0),
        })
    }

    /// E2: лимит размера стора в байтах (0 = без лимита). Задаётся из
    /// `NEXXUS_MAX_STORE_BYTES` или конфига монитора.
    pub fn set_max_store_bytes(&self, bytes: u64) {
        self.max_store_bytes
            .store(bytes, std::sync::atomic::Ordering::Relaxed);
    }

    pub fn max_store_bytes(&self) -> u64 {
        self.max_store_bytes.load(std::sync::atomic::Ordering::Relaxed)
    }

    /// Свободное место на файловой системе стора (fs2/statvfs), байт.
    pub fn available_space(&self) -> Result<u64, NexxusError> {
        // statvfs требует существующий путь: поднимаемся к первому
        // существующему предку (тесты дропают tempdir, пока redb держит fd).
        let mut probe = self.path.clone();
        while !probe.exists() {
            match probe.parent() {
                Some(p) if p != probe.as_os_str() => probe = p.to_path_buf(),
                _ => break,
            }
        }
        fs2::available_space(&probe)
            .map_err(|e| NexxusError::Io(format!("statvfs {}: {e}", probe.display())))
    }

    /// Текущий размер файла стора, байт.
    pub fn store_size(&self) -> Result<u64, NexxusError> {
        std::fs::metadata(&self.path)
            .map(|m| m.len())
            .map_err(|e| NexxusError::Io(format!("stat {}: {e}", self.path.display())))
    }

    /// E2 guard: вызывается перед записью foreign/own чанка. Ошибка, если
    /// (a) store size + chunk > max_store_bytes (когда cap > 0), или
    /// (b) на диске свободно меньше 2x размера чанка (headroom под redb).
    fn check_capacity(&self, incoming: u64) -> Result<(), NexxusError> {
        let cap = self.max_store_bytes();
        if cap > 0 {
            let used = self.store_size()?;
            if used.saturating_add(incoming) > cap {
                return Err(NexxusError::Io(format!(
                    "store cap exceeded: used {used} + incoming {incoming} > cap {cap} bytes"
                )));
            }
        }
        let avail = self.available_space()?;
        if avail < incoming.saturating_mul(2) {
            return Err(NexxusError::Io(format!(
                "insufficient disk space: available {avail} < 2x incoming {incoming} bytes"
            )));
        }
        Ok(())
    }

    /// Включает шифрование at rest ключом, выведенным из seed (at_rest::StoreKey).
    ///
    /// STR-02 двухфазная миграция: сначала meta-флаг `migrating`, затем
    /// re-encrypt всех чанков, затем финальный флаг `v1` — каждая фаза
    /// отдельным коммитом. При падении между фазами рестарт видит
    /// `migrating` и дожимает миграцию (уже зашифрованные чанки
    /// распознаются по успешному decrypt и пропускаются).
    ///
    /// Если стор уже помечен как зашифрованный (v1) — ключ просто
    /// устанавливается (с проверкой дешифрования первого чанка).
    /// Возвращает число мигрированных чанков.
    pub fn enable_encryption(&self, key: crate::at_rest::StoreKey) -> Result<usize, NexxusError> {
        use crate::at_rest::{
            decrypt_chunk, STORE_ENCRYPTION_META, STORE_ENCRYPTION_MIGRATING,
            STORE_ENCRYPTION_V1,
        };
        match self.get_meta(STORE_ENCRYPTION_META)? {
            Some(flag) if flag == STORE_ENCRYPTION_V1.as_bytes() => {
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
            Some(flag) if flag == STORE_ENCRYPTION_MIGRATING.as_bytes() => {
                // STR-02: resume после краша — дожимаем миграцию.
                let n = self.migrate_chunks(&key, true)?;
                self.set_encryption_flag(STORE_ENCRYPTION_V1)?;
                *self.crypto.lock().unwrap() = Some(key);
                Ok(n)
            }
            Some(flag) => Err(NexxusError::Io(format!(
                "unsupported store encryption format: {}",
                String::from_utf8_lossy(&flag)
            ))),
            None => {
                // Фаза 1: помечаем "migrating" отдельным коммитом ДО re-encrypt.
                self.set_encryption_flag(STORE_ENCRYPTION_MIGRATING)?;
                // Фаза 2: re-encrypt + финальный флаг.
                let n = self.migrate_chunks(&key, false)?;
                self.set_encryption_flag(STORE_ENCRYPTION_V1)?;
                *self.crypto.lock().unwrap() = Some(key);
                eprintln!("nexxusd: store re-encrypt done, {n} chunks");
                Ok(n)
            }
        }
    }

    /// Write the encryption meta flag in its own transaction (migration phase marker).
    fn set_encryption_flag(&self, flag: &str) -> Result<(), NexxusError> {
        use crate::at_rest::STORE_ENCRYPTION_META;
        let wtx = self
            .db
            .begin_write()
            .map_err(|e| NexxusError::Io(format!("redb write tx: {e}")))?;
        {
            let mut meta = wtx
                .open_table(META)
                .map_err(|e| NexxusError::Io(format!("redb table: {e}")))?;
            meta.insert(STORE_ENCRYPTION_META, flag.as_bytes())
                .map_err(|e| NexxusError::Io(format!("redb insert: {e}")))?;
        }
        wtx.commit()
            .map_err(|e| NexxusError::Io(format!("redb commit: {e}")))?;
        Ok(())
    }

    /// Re-encrypt all plaintext chunks in one write transaction.
    /// If `resume` is true, chunks that already decrypt with `key` are skipped
    /// (crash-resume path). Returns the number of chunks (re-)encrypted.
    fn migrate_chunks(&self, key: &crate::at_rest::StoreKey, resume: bool) -> Result<usize, NexxusError> {
        use crate::at_rest::{decrypt_chunk, encrypt_chunk};
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
        let mut done = 0usize;
        let wtx = self
            .db
            .begin_write()
            .map_err(|e| NexxusError::Io(format!("redb write tx: {e}")))?;
        {
            let mut chunks = wtx
                .open_table(CHUNKS)
                .map_err(|e| NexxusError::Io(format!("redb table: {e}")))?;
            for (i, (hash, raw)) in pairs.into_iter().enumerate() {
                if resume && decrypt_chunk(key, &hash, &raw).is_ok() {
                    continue; // already encrypted before the crash
                }
                let ct = encrypt_chunk(key, &hash, &raw);
                chunks
                    .insert(hash.0, ct.as_slice())
                    .map_err(|e| NexxusError::Io(format!("redb insert: {e}")))?;
                done += 1;
                if i % 1000 == 0 {
                    eprintln!("nexxusd: store re-encrypt progress {}/{total}", i + 1);
                }
            }
        }
        wtx.commit()
            .map_err(|e| NexxusError::Io(format!("redb commit: {e}")))?;
        Ok(done)
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
        // Integrity: the claimed hash MUST be SHA-256(data). Without this a peer
        // could store arbitrary bytes under someone else's hash — and with the
        // at-rest nonce derived from the hash that would be a nonce reuse with a
        // different plaintext (fatal for XChaCha20-Poly1305).
        use sha2::Digest;
        let actual = sha2::Sha256::digest(data);
        if actual.as_slice() != hash.0 {
            return Err(NexxusError::Io(format!(
                "chunk hash mismatch: claimed {}, actual {}",
                hex::encode(hash.0),
                hex::encode(actual)
            )));
        }
        // E2: disk cap + free-space guard before any write.
        self.check_capacity(data.len() as u64)?;
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
            // Dedup: never overwrite an existing hash. The at-rest nonce is
            // hash-derived, so a second write under the same hash with different
            // bytes would reuse the nonce. (Hash is verified above, so the same
            // hash implies the same plaintext — overwriting would be a no-op
            // anyway; refusing it makes the invariant explicit.)
            if table.get(hash.0).map_err(|e| NexxusError::Io(format!("redb get: {e}")))?.is_some() {
                return Ok(());
            }
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
        // E2: expired unpinned chunk reads as gone (lazy TTL).
        if raw.is_some() {
            let now = std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .map(|d| d.as_secs())
                .unwrap_or(0);
            if self.is_expired(hash, now)? {
                return Ok(None);
            }
        }
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

    // --- E2 retention: pin / TTL / GC (meta keys, chunk rows untouched) ---

    fn pin_key(hash: &ChunkHash) -> String {
        format!("pin_{}", hex::encode(hash.0))
    }
    fn ttl_key(hash: &ChunkHash) -> String {
        format!("ttl_exp_{}", hex::encode(hash.0))
    }

    /// Pin a chunk: pinned chunks are never GC'd and ignore TTL expiry.
    pub fn pin_chunk(&self, hash: &ChunkHash) -> Result<(), NexxusError> {
        self.put_meta(&Self::pin_key(hash), b"1")
    }

    pub fn unpin_chunk(&self, hash: &ChunkHash) -> Result<(), NexxusError> {
        self.delete_meta(&Self::pin_key(hash))
    }

    pub fn is_pinned(&self, hash: &ChunkHash) -> Result<bool, NexxusError> {
        Ok(self.get_meta(&Self::pin_key(hash))?.is_some())
    }

    /// Set TTL in seconds from `now`; 0 clears the TTL. Returns expiry unix ts
    /// (None when cleared).
    pub fn set_chunk_ttl(
        &self,
        hash: &ChunkHash,
        ttl_secs: u64,
        now: u64,
    ) -> Result<Option<u64>, NexxusError> {
        if ttl_secs == 0 {
            self.delete_meta(&Self::ttl_key(hash))?;
            return Ok(None);
        }
        let exp = now.saturating_add(ttl_secs);
        self.put_meta(&Self::ttl_key(hash), exp.to_string().as_bytes())?;
        Ok(Some(exp))
    }

    pub fn chunk_expiry(&self, hash: &ChunkHash) -> Result<Option<u64>, NexxusError> {
        match self.get_meta(&Self::ttl_key(hash))? {
            Some(b) => Ok(String::from_utf8_lossy(&b).parse::<u64>().ok()),
            None => Ok(None),
        }
    }

    /// Expired = TTL set, now past expiry, and not pinned.
    pub fn is_expired(&self, hash: &ChunkHash, now: u64) -> Result<bool, NexxusError> {
        if self.is_pinned(hash)? {
            return Ok(false);
        }
        Ok(matches!(self.chunk_expiry(hash)?, Some(exp) if now > exp))
    }

    /// Delete a chunk row (explicit; allowed even when pinned — pin only
    /// protects against GC/TTL, not against an explicit delete).
    pub fn delete_chunk(&self, hash: &ChunkHash) -> Result<bool, NexxusError> {
        let wtx = self
            .db
            .begin_write()
            .map_err(|e| NexxusError::Io(format!("redb write tx: {e}")))?;
        let existed = {
            let mut table = wtx
                .open_table(CHUNKS)
                .map_err(|e| NexxusError::Io(format!("redb table: {e}")))?;
            let removed = table
                .remove(hash.0)
                .map_err(|e| NexxusError::Io(format!("redb remove: {e}")))?;
            removed.is_some()
        };
        wtx.commit()
            .map_err(|e| NexxusError::Io(format!("redb commit: {e}")))?;
        Ok(existed)
    }

    /// GC: delete all expired, unpinned chunks. Returns count deleted.
    pub fn gc_expired(&self, now: u64) -> Result<usize, NexxusError> {
        let hashes = self.list_chunk_hashes()?;
        let mut deleted = 0;
        for h in hashes {
            if self.is_expired(&h, now)? && self.delete_chunk(&h)? {
                deleted += 1;
            }
        }
        Ok(deleted)
    }

    fn delete_meta(&self, key: &str) -> Result<(), NexxusError> {
        let wtx = self
            .db
            .begin_write()
            .map_err(|e| NexxusError::Io(format!("redb write tx: {e}")))?;
        {
            let mut table = wtx
                .open_table(META)
                .map_err(|e| NexxusError::Io(format!("redb table: {e}")))?;
            table
                .remove(key)
                .map_err(|e| NexxusError::Io(format!("redb remove meta: {e}")))?;
        }
        wtx.commit()
            .map_err(|e| NexxusError::Io(format!("redb commit: {e}")))?;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sha2::Digest;

    /// Real SHA-256 of the payload — put_chunk verifies hash == SHA-256(data).
    fn h(data: &[u8]) -> ChunkHash {
        ChunkHash(sha2::Sha256::digest(data).into())
    }

    #[test]
    fn put_get_roundtrip() {
        use sha2::Digest;
        let dir = tempfile::tempdir().unwrap();
        let store = ChunkStore::open(dir.path().join("store.redb")).unwrap();
        let chunk: Vec<u8> = (0..1000).map(|i| (i % 251) as u8).collect();
        let hash = ChunkHash(sha2::Sha256::digest(&chunk).into());
        store.put_chunk(&hash, &chunk).unwrap();
        let got = store.get_chunk(&hash).unwrap().unwrap();
        assert_eq!(got, chunk);
        assert!(store.get_chunk(&ChunkHash([1u8; 32])).unwrap().is_none());
    }

    #[test]
    fn disk_cap_rejects_oversized_write_and_reports_capacity() {
        // E2 quick win: user-defined cap + free-space guard in put_chunk.
        let dir = tempfile::tempdir().unwrap();
        let store = ChunkStore::open(dir.path().join("store.redb")).unwrap();
        assert_eq!(store.max_store_bytes(), 0, "default = unlimited");
        let chunk: Vec<u8> = vec![7u8; 4096];
        let hash = h(&chunk);

        store.set_max_store_bytes(1024);
        let err = store.put_chunk(&hash, &chunk).unwrap_err();
        assert!(err.to_string().contains("store cap exceeded"), "got: {err}");
        assert!(store.get_chunk(&hash).unwrap().is_none(), "rejected write must not persist");

        store.set_max_store_bytes(0);
        store.put_chunk(&hash, &chunk).unwrap();
        assert_eq!(store.get_chunk(&hash).unwrap().unwrap(), chunk);

        // visibility for node_metrics
        assert!(store.store_size().unwrap() > 0);
        assert!(store.available_space().unwrap() > 0);
    }

    #[test]
    fn ttl_pin_gc_retention_policy() {
        // E2: TTL expiry (lazy read + GC), pin protects from both.
        let dir = tempfile::tempdir().unwrap();
        let store = ChunkStore::open(dir.path().join("store.redb")).unwrap();
        let a: Vec<u8> = vec![1u8; 64];
        let b: Vec<u8> = vec![2u8; 64];
        let ha = h(&a);
        let hb = h(&b);
        store.put_chunk(&ha, &a).unwrap();
        store.put_chunk(&hb, &b).unwrap();

        // TTL on A (expires at 1000), pin B with TTL too — pin must win.
        assert_eq!(store.set_chunk_ttl(&ha, 100, 900).unwrap(), Some(1000));
        assert_eq!(store.set_chunk_ttl(&hb, 100, 900).unwrap(), Some(1000));
        store.pin_chunk(&hb).unwrap();

        assert!(!store.is_expired(&ha, 999).unwrap());
        assert!(store.is_expired(&ha, 1001).unwrap());
        assert!(!store.is_expired(&hb, 1001).unwrap(), "pinned ignores TTL");

        // lazy: get_chunk on expired unpinned reads as gone, row still there
        assert!(store.get_chunk(&ha).unwrap().is_none());
        assert_eq!(store.list_chunk_hashes().unwrap().len(), 2);

        // GC deletes only expired+unpinned
        assert_eq!(store.gc_expired(1001).unwrap(), 1);
        assert!(store.get_chunk(&ha).unwrap().is_none());
        assert_eq!(store.get_chunk(&hb).unwrap().unwrap(), b, "pinned survives GC");

        // unpin + clear TTL
        store.unpin_chunk(&hb).unwrap();
        assert!(!store.is_pinned(&hb).unwrap());
        assert_eq!(store.set_chunk_ttl(&hb, 0, 1001).unwrap(), None, "0 clears TTL");
        assert!(!store.is_expired(&hb, 99999).unwrap());
        assert_eq!(store.gc_expired(99999).unwrap(), 0);
    }

    #[test]
    fn put_chunk_rejects_hash_mismatch() {
        // A peer claiming a hash that is not SHA-256(data) must be refused:
        // with the at-rest nonce derived from the hash this would be a nonce
        // reuse with a different plaintext (fatal for XChaCha20-Poly1305).
        let dir = tempfile::tempdir().unwrap();
        let store = ChunkStore::open(dir.path().join("store.redb")).unwrap();
        let fake = ChunkHash([0x42u8; 32]);
        let err = store.put_chunk(&fake, b"not matching the hash").unwrap_err();
        assert!(err.to_string().contains("hash mismatch"), "got: {err}");
        assert!(store.get_chunk(&fake).unwrap().is_none());
    }

    #[test]
    fn put_chunk_never_overwrites_existing_hash() {
        use sha2::Digest;
        let dir = tempfile::tempdir().unwrap();
        let store = ChunkStore::open(dir.path().join("store.redb")).unwrap();
        let first = b"first".to_vec();
        let hash = ChunkHash(sha2::Sha256::digest(&first).into());
        store.put_chunk(&hash, &first).unwrap();
        // Same hash, same bytes (hash verified) -> dedup no-op, still first.
        store.put_chunk(&hash, &first).unwrap();
        assert_eq!(store.get_chunk(&hash).unwrap().unwrap(), first);
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
        store.put_chunk(&h(b"data"), b"data").unwrap();
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
        let hash = h(&chunk);
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
            store.put_chunk(&h(b"plain-one"), b"plain-one").unwrap();
            store.put_chunk(&h(b"plain-two"), b"plain-two").unwrap();
        }
        let raw_before = disk_bytes(&path);
        assert!(raw_before.windows(9).any(|w| w == b"plain-one"), "precondition: plaintext on disk before migration");

        // Открываем и включаем шифрование — миграция.
        let store = ChunkStore::open(&path).unwrap();
        assert_eq!(store.enable_encryption(key.clone()).unwrap(), 2);
        assert_eq!(store.get_chunk(&h(b"plain-one")).unwrap().unwrap(), b"plain-one");
        drop(store);

        let raw_after = disk_bytes(&path);
        assert!(!raw_after.windows(9).any(|w| w == b"plain-one"), "plaintext still on disk after migration");
        assert!(!raw_after.windows(9).any(|w| w == b"plain-two"));

        // Повторное открытие: флаг уже есть, миграции нет, ключ валидируется.
        let store = ChunkStore::open(&path).unwrap();
        assert_eq!(store.enable_encryption(key).unwrap(), 0);
        assert_eq!(store.get_chunk(&h(b"plain-two")).unwrap().unwrap(), b"plain-two");
    }

    #[test]
    fn migration_resume_after_crash_midway() {
        // STR-02: краш между фазами — флаг "migrating", часть чанков уже
        // зашифрована. Повторный enable_encryption дожимает остальное и
        // ставит финальный флаг v1; все чанки читаются.
        use crate::at_rest::{encrypt_chunk, STORE_ENCRYPTION_META, STORE_ENCRYPTION_MIGRATING, STORE_ENCRYPTION_V1};
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("store.redb");
        let key = crate::at_rest::StoreKey::derive(&[0x7Cu8; 64]);

        let h1 = h(b"chunk-one");
        let h2 = h(b"chunk-two");
        {
            let store = ChunkStore::open(&path).unwrap();
            store.put_chunk(&h1, b"chunk-one").unwrap();
            store.put_chunk(&h2, b"chunk-two").unwrap();
            // Симулируем краш после фазы 1: флаг migrating + один чанк уже зашифрован.
            store.put_meta(STORE_ENCRYPTION_META, STORE_ENCRYPTION_MIGRATING.as_bytes()).unwrap();
            let ct = encrypt_chunk(&key, &h1, b"chunk-one");
            let wtx = store.db.begin_write().unwrap();
            let mut t = wtx.open_table(CHUNKS).unwrap();
            t.insert(h1.0, ct.as_slice()).unwrap();
            drop(t);
            wtx.commit().unwrap();
        }

        let store = ChunkStore::open(&path).unwrap();
        // Resume: дожимается только незашифрованный чанк.
        assert_eq!(store.enable_encryption(key.clone()).unwrap(), 1);
        assert_eq!(
            store.get_meta(STORE_ENCRYPTION_META).unwrap().unwrap(),
            STORE_ENCRYPTION_V1.as_bytes()
        );
        assert_eq!(store.get_chunk(&h1).unwrap().unwrap(), b"chunk-one");
        assert_eq!(store.get_chunk(&h2).unwrap().unwrap(), b"chunk-two");
        // Повторный вызов — уже v1, миграции нет.
        assert_eq!(store.enable_encryption(key).unwrap(), 0);
    }

    #[test]
    fn wrong_key_rejected_on_encrypted_store() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("store.redb");
        let store = ChunkStore::open(&path).unwrap();
        store
            .enable_encryption(crate::at_rest::StoreKey::derive(&[0x01u8; 64]))
            .unwrap();
        store.put_chunk(&h(b"secret"), b"secret").unwrap();
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
