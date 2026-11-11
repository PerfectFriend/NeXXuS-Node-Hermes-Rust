//! Store backups + health checks — RC1 task R3.
//!
//! Backup = file-level copy of the redb store (safe while the node is running:
//! redb is copy-on-write with a single writer, so the file is always
//! consistent) + a `manifest.json` next to it with sha256, size, chunk count,
//! merkle root of chunk hashes, and the store encryption flag.
//!
//! Restore never overwrites a live store: it verifies the manifest and writes
//! a `*.restore-candidate.redb` next to the store; swapping is done by
//! `nexxusd restore <name>` while the daemon is stopped.

use crate::at_rest::STORE_ENCRYPTION_META;
use crate::identity_store;
use crate::storage::ChunkStore;
use nexxus_core::error::NexxusError;
use nexxus_core::merkle::merkle_root;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};

/// Directory with backups: `<store_dir>/backups/`.
pub fn backups_dir(store: &ChunkStore) -> PathBuf {
    store
        .path()
        .parent()
        .unwrap_or_else(|| Path::new("."))
        .join("backups")
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BackupManifest {
    pub name: String,
    pub created_at: u64,
    pub store_file: String,
    pub sha256: String,
    pub size_bytes: u64,
    pub chunk_count: usize,
    pub merkle_root: String,
    pub encrypted_at_rest: bool,
    pub nexxus_version: String,
}

fn sha256_file(path: &Path) -> Result<String, NexxusError> {
    let data = std::fs::read(path).map_err(|e| NexxusError::Io(format!("read {}: {e}", path.display())))?;
    Ok(hex::encode(Sha256::digest(&data)))
}

fn now_secs() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

fn now_millis() -> u128 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0)
}

/// Create a backup of the store into `<store_dir>/backups/<ts>/`.
/// Returns the manifest. Safe to call on a running node (CoW file copy).
pub fn backup_store(store: &ChunkStore) -> Result<BackupManifest, NexxusError> {
    let ts = now_secs();
    // Millis in the name: two backups within the same second must not
    // overwrite each other's directory (that corrupts the manifest).
    let name = format!("backup-{ts}-{}", now_millis() % 1000);
    let dir = backups_dir(store).join(&name);
    std::fs::create_dir_all(&dir).map_err(|e| NexxusError::Io(format!("mkdir {}: {e}", dir.display())))?;

    let src = store.path();
    let dst = dir.join("store.redb");
    std::fs::copy(src, &dst).map_err(|e| NexxusError::Io(format!("copy store: {e}")))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = std::fs::set_permissions(&dst, std::fs::Permissions::from_mode(0o600));
    }

    let hashes = store.list_chunk_hashes()?;
    let leaves: Vec<[u8; 32]> = hashes.iter().map(|h| h.0).collect();
    let root = merkle_root(&leaves);
    let encrypted = store.get_meta(STORE_ENCRYPTION_META)?.is_some();
    let meta = std::fs::metadata(&dst).map_err(|e| NexxusError::Io(e.to_string()))?;

    let manifest = BackupManifest {
        name: name.clone(),
        created_at: ts,
        store_file: "store.redb".into(),
        sha256: sha256_file(&dst)?,
        size_bytes: meta.len(),
        chunk_count: hashes.len(),
        merkle_root: hex::encode(root),
        encrypted_at_rest: encrypted,
        nexxus_version: env!("CARGO_PKG_VERSION").into(),
    };
    let mpath = dir.join("manifest.json");
    let tmp = dir.join("manifest.json.tmp");
    std::fs::write(&tmp, serde_json::to_string_pretty(&manifest).unwrap().as_bytes())
        .map_err(|e| NexxusError::Io(e.to_string()))?;
    std::fs::rename(&tmp, &mpath).map_err(|e| NexxusError::Io(e.to_string()))?;
    Ok(manifest)
}

pub fn list_backups(store: &ChunkStore) -> Result<Vec<BackupManifest>, NexxusError> {
    let dir = backups_dir(store);
    let mut out = Vec::new();
    let rd = match std::fs::read_dir(&dir) {
        Ok(r) => r,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(out),
        Err(e) => return Err(NexxusError::Io(e.to_string())),
    };
    for entry in rd.flatten() {
        let mpath = entry.path().join("manifest.json");
        if let Ok(json) = std::fs::read_to_string(&mpath) {
            if let Ok(m) = serde_json::from_str::<BackupManifest>(&json) {
                out.push(m);
            }
        }
    }
    out.sort_by_key(|b| std::cmp::Reverse(b.created_at));
    Ok(out)
}

/// Verify a backup: manifest sha256 matches the file, and the copy opens as a
/// valid redb with the same chunk count. Returns (manifest, ok, detail).
pub fn verify_backup(store: &ChunkStore, name: &str) -> Result<(BackupManifest, bool, String), NexxusError> {
    if name.contains('/') || name.contains("..") {
        return Err(NexxusError::Io("bad backup name".into()));
    }
    let dir = backups_dir(store).join(name);
    let mpath = dir.join("manifest.json");
    let json = std::fs::read_to_string(&mpath)
        .map_err(|e| NexxusError::Io(format!("read manifest {name}: {e}")))?;
    let m: BackupManifest = serde_json::from_str(&json)
        .map_err(|e| NexxusError::Vault(format!("невалидный manifest: {e}")))?;
    let file = dir.join(&m.store_file);
    let actual = sha256_file(&file)?;
    if actual != m.sha256 {
        let detail = format!("sha256 mismatch: manifest {} vs file {actual}", m.sha256);
        return Ok((m, false, detail));
    }
    // Chunk count проверяем на ВРЕМЕННОЙ копии: redb при open (read-write)
    // может repair-нуть файл и изменить его — оригинал бэкапа не трогаем.
    let tmp = std::env::temp_dir().join(format!(
        "nexxus-verify-{}-{}.redb",
        std::process::id(),
        name.replace(['/', '\\'], "_")
    ));
    std::fs::copy(&file, &tmp).map_err(|e| NexxusError::Io(format!("copy for verify: {e}")))?;
    let n = ChunkStore::open(&tmp).and_then(|c| c.list_chunk_hashes()).map(|v| v.len());
    let _ = std::fs::remove_file(&tmp);
    let n = match n {
        Ok(n) => n,
        Err(e) => return Ok((m, false, format!("backup copy does not open: {e}"))),
    };
    if n != m.chunk_count {
        let detail = format!("chunk count mismatch: manifest {} vs file {n}", m.chunk_count);
        return Ok((m, false, detail));
    }
    Ok((m, true, "ok".into()))
}

/// "Restore" = verify + write a candidate file next to the live store.
/// The live store is NEVER overwritten by the API. Swapping is done by
/// `nexxusd restore <name>` with the daemon stopped.
pub fn restore_candidate(store: &ChunkStore, name: &str) -> Result<PathBuf, NexxusError> {
    let (m, ok, detail) = verify_backup(store, name)?;
    if !ok {
        return Err(NexxusError::Vault(format!("backup {name} failed verification: {detail}")));
    }
    let dir = backups_dir(store).join(name);
    let src = dir.join(&m.store_file);
    let dst = store
        .path()
        .with_file_name(format!("{}.restore-candidate.redb", store.path().file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_else(|| "store".into())));
    std::fs::copy(&src, &dst).map_err(|e| NexxusError::Io(format!("copy candidate: {e}")))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = std::fs::set_permissions(&dst, std::fs::Permissions::from_mode(0o600));
    }
    Ok(dst)
}

/// Swap a verified backup over the store file. ONLY safe with the daemon
/// stopped — used by `nexxusd restore <name>`.
pub fn swap_backup(store_path: &Path, name: &str) -> Result<PathBuf, NexxusError> {
    let store = ChunkStore::open(store_path)?;
    let (m, ok, detail) = verify_backup(&store, name)?;
    drop(store);
    if !ok {
        return Err(NexxusError::Vault(format!("backup {name} failed verification: {detail}")));
    }
    let src = backups_dir(&ChunkStore::open(store_path)?).join(name).join(&m.store_file);
    std::fs::copy(&src, store_path).map_err(|e| NexxusError::Io(format!("swap: {e}")))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = std::fs::set_permissions(store_path, std::fs::Permissions::from_mode(0o600));
    }
    Ok(store_path.to_path_buf())
}

// ---------- doctor ----------

#[derive(Debug, Clone, Serialize)]
pub struct DoctorReport {
    pub store_path: String,
    pub store_perms_ok: bool,
    pub store_opens: bool,
    pub chunk_count: usize,
    pub merkle_root: String,
    pub encrypted_at_rest: bool,
    pub identity_initialized: bool,
    pub seed_vault_exists: bool,
    pub backups: usize,
    pub problems: Vec<String>,
}

pub fn doctor(store: &ChunkStore) -> DoctorReport {
    let mut problems = Vec::new();
    let path = store.path();

    #[cfg(unix)]
    let perms_ok = {
        use std::os::unix::fs::PermissionsExt;
        match std::fs::metadata(path) {
            Ok(md) => {
                let mode = md.permissions().mode() & 0o777;
                if mode != 0o600 {
                    problems.push(format!("store perms {mode:o} != 600"));
                }
                mode == 0o600
            }
            Err(_) => {
                problems.push("store file metadata unreadable".into());
                false
            }
        }
    };
    #[cfg(not(unix))]
    let perms_ok = true;

    let chunk_count = store.list_chunk_hashes().map(|h| h.len()).unwrap_or_else(|e| {
        problems.push(format!("list chunks: {e}"));
        0
    });
    let leaves: Vec<[u8; 32]> = store
        .list_chunk_hashes()
        .unwrap_or_default()
        .iter()
        .map(|h| h.0)
        .collect();
    let root = hex::encode(merkle_root(&leaves));
    let encrypted = store.get_meta(STORE_ENCRYPTION_META).ok().flatten().is_some();
    if !encrypted {
        problems.push("store encryption at rest is NOT enabled".into());
    }
    let identity = identity_store::identity_status(store).ok().map(|(i, _)| i).unwrap_or(false);
    if !identity {
        problems.push("identity (BIP39) not initialized".into());
    }
    let vault = crate::seed_vault::seed_vault_status(store).ok().flatten().is_some();
    if !vault {
        problems.push("no encrypted seed vault (run a seed backup)".into());
    }
    let backups = list_backups(store).map(|b| b.len()).unwrap_or(0);

    DoctorReport {
        store_path: path.to_string_lossy().into(),
        store_perms_ok: perms_ok,
        store_opens: true,
        chunk_count,
        merkle_root: root,
        encrypted_at_rest: encrypted,
        identity_initialized: identity,
        seed_vault_exists: vault,
        backups,
        problems,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::identity_store::load_or_create_identity;
    use nexxus_core::types::ChunkHash;
    use sha2::Digest;
    use tempfile::tempdir;

    /// Real SHA-256 of the payload — put_chunk now verifies hash == SHA-256(data).
    fn h(data: &[u8]) -> ChunkHash {
        ChunkHash(sha2::Sha256::digest(data).into())
    }

    fn store_with_data() -> (tempfile::TempDir, ChunkStore) {
        let dir = tempdir().unwrap();
        let store = ChunkStore::open(dir.path().join("store.redb")).unwrap();
        let _ = load_or_create_identity(&store).unwrap();
        store.put_chunk(&h(b"hello"), b"hello").unwrap();
        store.put_chunk(&h(b"world"), b"world").unwrap();
        (dir, store)
    }

    #[test]
    fn backup_list_verify_roundtrip() {
        let (_d, store) = store_with_data();
        let m = backup_store(&store).unwrap();
        assert_eq!(m.chunk_count, 2);
        assert!(!m.merkle_root.is_empty());
        let list = list_backups(&store).unwrap();
        assert_eq!(list.len(), 1);
        assert_eq!(list[0].name, m.name);
        let (m2, ok, detail) = verify_backup(&store, &m.name).unwrap();
        assert!(ok, "verify failed: {detail}");
        assert_eq!(m2.sha256, m.sha256);
    }

    #[test]
    fn verify_detects_tampered_file() {
        let (_d, store) = store_with_data();
        let m = backup_store(&store).unwrap();
        let f = backups_dir(&store).join(&m.name).join("store.redb");
        let mut data = std::fs::read(&f).unwrap();
        data[10] ^= 0xff;
        std::fs::write(&f, data).unwrap();
        let (_, ok, detail) = verify_backup(&store, &m.name).unwrap();
        assert!(!ok);
        assert!(detail.contains("sha256 mismatch"));
    }

    #[test]
    fn verify_rejects_bad_name() {
        let (_d, store) = store_with_data();
        assert!(verify_backup(&store, "../etc").is_err());
    }

    #[test]
    fn verify_is_idempotent_and_does_not_modify_backup_file() {
        // Регрессия: verify открывал оригинал read-write — redb мог его
        // repair-нуть, и второй verify падал по sha256. Теперь проверка
        // chunk count идёт на временной копии.
        let (_d, store) = store_with_data();
        let m = backup_store(&store).unwrap();
        let f = backups_dir(&store).join(&m.name).join("store.redb");
        let before = std::fs::read(&f).unwrap();
        for _ in 0..2 {
            let (_, ok, detail) = verify_backup(&store, &m.name).unwrap();
            assert!(ok, "verify failed: {detail}");
        }
        let after = std::fs::read(&f).unwrap();
        assert_eq!(before, after, "verify must not modify the backup file");
    }

    #[test]
    fn restore_candidate_writes_file_and_never_touches_live_store() {
        let (d, store) = store_with_data();
        let live_before = std::fs::read(store.path()).unwrap();
        let m = backup_store(&store).unwrap();
        let cand = restore_candidate(&store, &m.name).unwrap();
        assert!(cand.exists());
        assert!(cand.to_string_lossy().contains("restore-candidate"));
        let live_after = std::fs::read(store.path()).unwrap();
        assert_eq!(live_before, live_after, "live store must be untouched");
        // Кандидат открывается и содержит те же чанки.
        let copy = ChunkStore::open(&cand).unwrap();
        assert_eq!(copy.list_chunk_hashes().unwrap().len(), 2);
        drop(copy);
        let _ = d;
    }

    #[test]
    fn swap_backup_replaces_store_file() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("store.redb");
        let store = ChunkStore::open(&path).unwrap();
        let _ = load_or_create_identity(&store).unwrap();
        store.put_chunk(&h(b"v1"), b"v1").unwrap();
        drop(store);
        let m = backup_store(&ChunkStore::open(&path).unwrap()).unwrap();
        // «Повреждаем» живой стор после бэкапа.
        let store = ChunkStore::open(&path).unwrap();
        store.put_chunk(&h(b"v2-extra"), b"v2-extra").unwrap();
        drop(store);
        swap_backup(&path, &m.name).unwrap();
        let store = ChunkStore::open(&path).unwrap();
        assert_eq!(store.list_chunk_hashes().unwrap().len(), 1, "swap must restore the backup state");
    }

    #[test]
    fn doctor_reports_identity_and_vault_and_backup_count() {
        let (_d, store) = store_with_data();
        let _ = crate::seed_vault::backup_seed(&store, "1234", None).unwrap();
        let _ = backup_store(&store).unwrap();
        let r = doctor(&store);
        assert!(r.store_opens);
        assert!(r.identity_initialized);
        assert!(r.seed_vault_exists);
        assert_eq!(r.backups, 1);
        assert_eq!(r.chunk_count, 2);
        assert!(r.store_perms_ok, "problems: {:?}", r.problems);
        assert!(r.encrypted_at_rest || r.problems.iter().any(|p| p.contains("encryption")));
    }
}
