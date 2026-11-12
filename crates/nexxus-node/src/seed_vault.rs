//! Encrypted backup of the BIP-39 seed — RC1 task R2.
//!
//! The mnemonic from the store `meta` table is encrypted with
//! `nexxus_core::keys::vault` (AES-256-GCM, PBKDF2 600k, SDK-compatible JSON)
//! and written to `<store-name>.seed.vault` next to the store with 0600 perms.
//! A duress-PIN can be set at backup time: entering it at restore time is
//! reported as `Duress` and the real seed is NEVER imported.

use crate::identity_store::{import_mnemonic, read_mnemonic};
use crate::storage::ChunkStore;
use nexxus_core::error::NexxusError;
use nexxus_core::keys::vault::{
    check_pin, decrypt_vault_payload, encrypt_vault_payload, EncryptedVault, PinCheck,
};
use nexxus_core::types::NodeId;
use std::path::PathBuf;

/// `<store-name>.seed.vault` next to the store file.
pub fn seed_vault_path(store: &ChunkStore) -> PathBuf {
    let p = store.path();
    let mut name = p
        .file_name()
        .map(|n| n.to_string_lossy().into_owned())
        .unwrap_or_else(|| "store.redb".into());
    if let Some(stripped) = name.strip_suffix(".redb") {
        name = stripped.to_string();
    }
    p.with_file_name(format!("{name}.seed.vault"))
}

/// Encrypt the persisted mnemonic into the seed vault file (atomic tmp+rename, 0600).
/// Returns the vault path. The plaintext mnemonic is zeroized on drop by the caller scope.
pub fn backup_seed(
    store: &ChunkStore,
    pin: &str,
    duress_pin: Option<&str>,
) -> Result<PathBuf, NexxusError> {
    if pin.len() < 4 {
        return Err(NexxusError::Vault("PIN must be at least 4 chars".into()));
    }
    if let Some(dp) = duress_pin {
        if dp == pin {
            return Err(NexxusError::Vault("duress PIN must differ from the primary PIN".into()));
        }
    }
    let phrase = read_mnemonic(store)?.ok_or_else(|| NexxusError::Io("identity not initialized".into()))?;
    let vault_json = encrypt_vault_payload(phrase.as_bytes(), pin, duress_pin)?;
    let path = seed_vault_path(store);
    let tmp = path.with_extension("vault.tmp");
    std::fs::write(&tmp, vault_json.as_bytes())
        .map_err(|e| NexxusError::Io(format!("write vault tmp: {e}")))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(&tmp, std::fs::Permissions::from_mode(0o600))
            .map_err(|e| NexxusError::Io(format!("chmod vault: {e}")))?;
    }
    std::fs::rename(&tmp, &path).map_err(|e| NexxusError::Io(format!("rename vault: {e}")))?;
    Ok(path)
}

/// Metadata about the seed vault — no decryption, no secrets.
pub struct SeedVaultStatus {
    pub path: PathBuf,
    pub created_at: u64,
    pub has_duress_pin: bool,
    pub kdf_rounds: u32,
}

pub fn seed_vault_status(store: &ChunkStore) -> Result<Option<SeedVaultStatus>, NexxusError> {
    let path = seed_vault_path(store);
    match std::fs::read_to_string(&path) {
        Ok(json) => {
            let v: EncryptedVault = serde_json::from_str(&json)
                .map_err(|e| NexxusError::Vault(format!("невалидный seed vault: {e}")))?;
            Ok(Some(SeedVaultStatus {
                path,
                created_at: v.created_at,
                has_duress_pin: v.duress_hash_hex.is_some(),
                kdf_rounds: v.kdf_rounds,
            }))
        }
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
        Err(e) => Err(NexxusError::Io(format!("read seed vault: {e}"))),
    }
}

/// Outcome of a restore attempt.
#[derive(Debug)]
pub enum RestoreOutcome {
    /// Seed imported into an empty store; node_id of the restored identity.
    Imported(NodeId),
    /// Store already had this exact seed.
    Already(NodeId),
    /// Duress-PIN was entered: the real seed is NOT imported, the caller
    /// must raise an alert (Telegram/log) instead of a success message.
    Duress,
    /// Wrong PIN.
    WrongPin,
}

/// Verify PIN and, if correct, import the decrypted mnemonic.
/// Duress-PIN never imports anything — it returns `RestoreOutcome::Duress`.
pub fn restore_seed(store: &ChunkStore, pin: &str) -> Result<RestoreOutcome, NexxusError> {
    let path = seed_vault_path(store);
    let json = std::fs::read_to_string(&path)
        .map_err(|e| NexxusError::Io(format!("seed vault not found/readable: {e}")))?;
    match check_pin(&json, pin)? {
        PinCheck::Duress => return Ok(RestoreOutcome::Duress),
        PinCheck::Wrong => return Ok(RestoreOutcome::WrongPin),
        PinCheck::Ok => {}
    }
    let dec = decrypt_vault_payload(&json, pin)?;
    if dec.is_duress {
        return Ok(RestoreOutcome::Duress);
    }
    let phrase = zeroize::Zeroizing::new(
        String::from_utf8(dec.decrypted_bytes)
            .map_err(|_| NexxusError::Vault("decrypted seed is not valid utf-8".into()))?,
    );
    let (node_id, status) = import_mnemonic(store, &phrase)?;
    Ok(if status == "imported" {
        RestoreOutcome::Imported(node_id)
    } else {
        RestoreOutcome::Already(node_id)
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::identity_store::load_or_create_identity;
    use tempfile::tempdir;

    fn store_with_identity() -> (tempfile::TempDir, ChunkStore) {
        let dir = tempdir().unwrap();
        let path = dir.path().join("store.redb");
        let store = ChunkStore::open(&path).unwrap();
        let _ = load_or_create_identity(&store).unwrap();
        (dir, store)
    }

    #[test]
    fn backup_creates_0600_vault_and_status_reads_it() {
        let (_d, store) = store_with_identity();
        let path = backup_seed(&store, "1234", Some("9999")).unwrap();
        assert!(path.exists());
        assert!(path.to_string_lossy().ends_with("store.seed.vault"));
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mode = std::fs::metadata(&path).unwrap().permissions().mode() & 0o777;
            assert_eq!(mode, 0o600);
        }
        let st = seed_vault_status(&store).unwrap().unwrap();
        assert!(st.has_duress_pin);
        assert!(st.created_at > 0);
        // Содержимое файла — JSON, без сид-фразы в открытом виде.
        let raw = std::fs::read_to_string(&path).unwrap();
        let phrase = read_mnemonic(&store).unwrap().unwrap();
        assert!(!raw.contains(phrase.as_str()));
    }

    #[test]
    fn restore_with_correct_pin_gives_already_on_same_store() {
        let (_d, store) = store_with_identity();
        backup_seed(&store, "1234", None).unwrap();
        match restore_seed(&store, "1234").unwrap() {
            RestoreOutcome::Already(id) => {
                let (id2, _) = load_or_create_identity(&store).unwrap();
                assert_eq!(id, id2.node_id);
            }
            other => panic!("expected Already, got {other:?}"),
        }
    }

    #[test]
    fn restore_into_empty_store_imports_and_restores_node_id() {
        let (d1, store1) = store_with_identity();
        let (id1, _) = load_or_create_identity(&store1).unwrap();
        backup_seed(&store1, "1234", None).unwrap();
        // Копируем vault рядом с новым (пустым) стором.
        let d2 = tempdir().unwrap();
        let store2 = ChunkStore::open(d2.path().join("store.redb")).unwrap();
        let vault_src = seed_vault_path(&store1);
        let vault_dst = seed_vault_path(&store2);
        std::fs::copy(&vault_src, &vault_dst).unwrap();
        let _ = d1; // держим tempdir живым
        match restore_seed(&store2, "1234").unwrap() {
            RestoreOutcome::Imported(id) => assert_eq!(id, id1.node_id),
            other => panic!("expected Imported, got {other:?}"),
        }
        // И load_or_create на новом сторе видит ту же идентичность.
        let (id2, created) = load_or_create_identity(&store2).unwrap();
        assert!(created.is_none());
        assert_eq!(id2.node_id, id1.node_id);
    }

    #[test]
    fn restore_wrong_pin_and_duress() {
        let (_d, store) = store_with_identity();
        backup_seed(&store, "1234", Some("9999")).unwrap();
        assert!(matches!(restore_seed(&store, "0000").unwrap(), RestoreOutcome::WrongPin));
        // Duress: реальный сид НЕ импортируется — стор не тронут.
        assert!(matches!(restore_seed(&store, "9999").unwrap(), RestoreOutcome::Duress));
    }

    #[test]
    fn backup_rejects_short_pin_and_same_duress() {
        let (_d, store) = store_with_identity();
        assert!(backup_seed(&store, "12", None).is_err());
        assert!(backup_seed(&store, "1234", Some("1234")).is_err());
    }

    #[test]
    fn status_none_when_no_vault() {
        let (_d, store) = store_with_identity();
        assert!(seed_vault_status(&store).unwrap().is_none());
    }
}
