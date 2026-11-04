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
}

impl ChunkStore {
    pub fn open<P: AsRef<std::path::Path>>(path: P) -> Result<Self, NexxusError> {
        let path = path.as_ref().to_path_buf();
        let db = Database::create(&path).map_err(|e| NexxusError::Io(format!("redb create: {e}")))?;
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
        Ok(Self { db, path })
    }

    /// Путь к файлу стора на диске (для метрик свободного места).
    pub fn path(&self) -> &std::path::Path {
        &self.path
    }

    pub fn put_chunk(&self, hash: &ChunkHash, data: &[u8]) -> Result<(), NexxusError> {
        let wtx = self
            .db
            .begin_write()
            .map_err(|e| NexxusError::Io(format!("redb write tx: {e}")))?;
        {
            let mut table = wtx
                .open_table(CHUNKS)
                .map_err(|e| NexxusError::Io(format!("redb table: {e}")))?;
            table
                .insert(hash.0, data)
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
        Ok(res.map(|v| v.value().to_vec()))
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
}
