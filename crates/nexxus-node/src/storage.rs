//! Persistent chunk index on redb (ADR-0005).
//! Key = ChunkHash (32 bytes), value = raw chunk bytes. No external DB daemon.

use nexxus_core::{error::NexxusError, types::ChunkHash};
use redb::{Database, TableDefinition};

const CHUNKS: TableDefinition<[u8; 32], &[u8]> = TableDefinition::new("chunks");

pub struct ChunkStore {
    #[allow(dead_code)]
    db: Database,
}

impl ChunkStore {
    #[allow(dead_code)]
    pub fn open<P: AsRef<std::path::Path>>(path: P) -> Result<Self, NexxusError> {
        let db = Database::create(path).map_err(|e| NexxusError::Io(format!("redb create: {e}")))?;
        Ok(Self { db })
    }

    #[allow(dead_code)]
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

    #[allow(dead_code)]
    pub fn get_chunk(&self, hash: &ChunkHash) -> Result<Option<Vec<u8>>, NexxusError> {
        let rtx = self
            .db
            .begin_read()
            .map_err(|e| NexxusError::Io(format!("redb read tx: {e}")))?;
        let table = rtx
            .open_table(CHUNKS)
            .map_err(|e| NexxusError::Io(format!("redb table: {e}")))?;
        let res = table
            .get(hash.0)
            .map_err(|e| NexxusError::Io(format!("redb get: {e}")))?;
        Ok(res.map(|v| v.value().to_vec()))
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
}
