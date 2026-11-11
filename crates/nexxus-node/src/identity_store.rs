//! Persistent node identity (plan phase 2).
//!
//! The BIP-39 mnemonic lives in the redb `meta` table (`identity_mnemonic`).
//! Keys are derived deterministically: Ed25519 via SLIP-0010
//! (m/44'/999'/0'/0/0), X25519 via domain-separated SHA-256 of the seed.
//! NodeId = SHA-256(verifying_key), so it is stable across restarts on the
//! same store (previously a fresh random NodeId was generated every run).

use nexxus_core::error::NexxusError;
use nexxus_core::keys::identity::Identity;
use nexxus_core::keys::seed::{x25519_secret_from_seed, IdentitySeed};
use nexxus_core::keys::slip10::DerivedKey;
use nexxus_core::types::NodeId;

use crate::storage::ChunkStore;

pub const META_IDENTITY_MNEMONIC: &str = "identity_mnemonic";

/// Keys derived from the persisted seed.
pub struct NodeIdentity {
    pub identity: Identity,
    pub node_id: NodeId,
    /// X25519 secret — zeroize при drop.
    pub x25519_secret: zeroize::Zeroizing<[u8; 32]>,
    /// BIP-39 seed (64 байта) — zeroize при drop; из него выводится ключ стора.
    pub seed: zeroize::Zeroizing<[u8; 64]>,
}

/// Load the identity from the store, or generate a new mnemonic, persist it
/// and derive keys. The second return value is `Some(mnemonic)` only when the
/// identity was freshly created — the caller may print it exactly once.
pub fn load_or_create_identity(
    store: &ChunkStore,
) -> Result<(NodeIdentity, Option<String>), NexxusError> {
    if let Some(phrase_bytes) = store.get_meta(META_IDENTITY_MNEMONIC)? {
        let phrase = String::from_utf8(phrase_bytes)
            .map_err(|_| NexxusError::Io("identity mnemonic is not valid utf-8".into()))?;
        let seed = IdentitySeed::validate(&phrase)?;
        return Ok((derive_identity(&seed), None));
    }
    let seed = IdentitySeed::generate()?;
    let phrase = seed.mnemonic.clone();
    store.put_meta(META_IDENTITY_MNEMONIC, phrase.as_bytes())?;
    Ok((derive_identity(&seed), Some(phrase)))
}

/// Initialize (or verify) the identity, optionally from a given mnemonic.
/// Used by `nexxusd init --mnemonic "..."`.
pub fn init_identity(
    store: &ChunkStore,
    mnemonic: Option<&str>,
) -> Result<(NodeIdentity, Option<String>), NexxusError> {
    match mnemonic {
        Some(phrase) => {
            let seed = IdentitySeed::validate(phrase)?;
            if let Some(existing) = store.get_meta(META_IDENTITY_MNEMONIC)? {
                if existing != phrase.as_bytes() {
                    return Err(NexxusError::Io(
                        "store already initialized with a different mnemonic".into(),
                    ));
                }
                return Ok((derive_identity(&seed), None));
            }
            store.put_meta(META_IDENTITY_MNEMONIC, phrase.as_bytes())?;
            Ok((derive_identity(&seed), None))
        }
        None => load_or_create_identity(store),
    }
}

/// X25519 public key for a secret (for display in `id`/`init`).
pub fn x25519_pub(secret: &[u8; 32]) -> [u8; 32] {
    nexxus_core::wire::payloads::X25519_BASEPOINT
        .mul_clamped(*secret)
        .to_bytes()
}

/// Read the persisted BIP-39 mnemonic. Used ONLY by the one-time
/// `node_identity_export` API call (with explicit confirmation) — the caller
/// must never log it. Returns None if the store has no identity yet.
pub fn read_mnemonic(store: &ChunkStore) -> Result<Option<String>, NexxusError> {
    match store.get_meta(META_IDENTITY_MNEMONIC)? {
        Some(bytes) => String::from_utf8(bytes)
            .map(Some)
            .map_err(|_| NexxusError::Io("identity mnemonic is not valid utf-8".into())),
        None => Ok(None),
    }
}

/// Status of the persisted identity for the local API.
pub fn identity_status(store: &ChunkStore) -> Result<(bool, Option<usize>), NexxusError> {
    match read_mnemonic(store)? {
        Some(phrase) => Ok((true, Some(phrase.split_whitespace().count()))),
        None => Ok((false, None)),
    }
}

/// Import a mnemonic into a store that has NO identity yet.
/// Refuses if the store is already initialized with a different seed —
/// the store encryption key is derived from this seed, so swapping the
/// identity on a live store would make all chunks undecryptable.
/// Returns (node_id, status): "imported" | "already".
pub fn import_mnemonic(store: &ChunkStore, phrase: &str) -> Result<(NodeId, &'static str), NexxusError> {
    let seed = IdentitySeed::validate(phrase)?;
    if let Some(existing) = store.get_meta(META_IDENTITY_MNEMONIC)? {
        let existing_seed = IdentitySeed::validate(
            &String::from_utf8(existing)
                .map_err(|_| NexxusError::Io("identity mnemonic is not valid utf-8".into()))?,
        )?;
        if existing_seed.seed_bytes() != seed.seed_bytes() {
            return Err(NexxusError::Io(
                "store already initialized with a different mnemonic".into(),
            ));
        }
        return Ok((derive_identity(&seed).node_id, "already"));
    }
    store.put_meta(META_IDENTITY_MNEMONIC, seed.mnemonic.as_bytes())?;
    Ok((derive_identity(&seed).node_id, "imported"))
}

fn derive_identity(seed: &IdentitySeed) -> NodeIdentity {
    let derived = DerivedKey::from_seed(seed.seed_bytes()).expect("SLIP-0010 derivation");
    let identity = Identity::from_secret(&derived.private_key).expect("ed25519 from secret");
    let node_id = identity.node_id();
    let x25519_secret = x25519_secret_from_seed(seed.seed_bytes());
    NodeIdentity {
        identity,
        node_id,
        x25519_secret: zeroize::Zeroizing::new(x25519_secret),
        seed: zeroize::Zeroizing::new(*seed.seed_bytes()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::tempdir;

    #[test]
    fn identity_is_stable_across_reopen() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("store.redb");
        let (id1, created1) = {
            let store = ChunkStore::open(&path).unwrap();
            load_or_create_identity(&store).unwrap()
        };
        assert!(created1.is_some(), "first open must create the identity");
        let (id2, created2) = {
            let store = ChunkStore::open(&path).unwrap();
            load_or_create_identity(&store).unwrap()
        };
        assert!(created2.is_none(), "second open must reuse the identity");
        assert_eq!(id1.node_id, id2.node_id);
        assert_eq!(id1.identity.verifying_key, id2.identity.verifying_key);
        assert_eq!(id1.x25519_secret, id2.x25519_secret);
    }

    #[test]
    fn distinct_stores_get_distinct_identities() {
        let d1 = tempdir().unwrap();
        let d2 = tempdir().unwrap();
        let s1 = ChunkStore::open(d1.path().join("a.redb")).unwrap();
        let s2 = ChunkStore::open(d2.path().join("b.redb")).unwrap();
        let (i1, _) = load_or_create_identity(&s1).unwrap();
        let (i2, _) = load_or_create_identity(&s2).unwrap();
        assert_ne!(i1.node_id, i2.node_id);
    }

    #[test]
    fn node_id_is_sha256_of_pubkey() {
        let dir = tempdir().unwrap();
        let store = ChunkStore::open(dir.path().join("s.redb")).unwrap();
        let (id, _) = load_or_create_identity(&store).unwrap();
        assert_eq!(id.node_id, id.identity.node_id());
    }

    #[test]
    fn mnemonic_persisted_in_meta() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("store.redb");
        let phrase = {
            let store = ChunkStore::open(&path).unwrap();
            let (_, _created) = load_or_create_identity(&store).unwrap();
            let stored = store.get_meta(META_IDENTITY_MNEMONIC).unwrap();
            assert!(stored.is_some());
            String::from_utf8(stored.unwrap()).unwrap()
        };
        assert_eq!(Some(phrase.as_str()), {
            let store = ChunkStore::open(&path).unwrap();
            let (_, created) = load_or_create_identity(&store).unwrap();
            assert!(created.is_none());
            store
                .get_meta(META_IDENTITY_MNEMONIC)
                .unwrap()
                .map(|b| String::from_utf8(b).unwrap())
                .as_deref()
        });
        assert_eq!(phrase.split_whitespace().count(), 12);
    }

    #[test]
    fn read_mnemonic_and_status_roundtrip() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("store.redb");
        let store = ChunkStore::open(&path).unwrap();
        // Пустой стор: идентичности нет.
        assert_eq!(identity_status(&store).unwrap(), (false, None));
        assert!(read_mnemonic(&store).unwrap().is_none());
        let (_, created) = load_or_create_identity(&store).unwrap();
        let phrase = created.unwrap();
        assert_eq!(read_mnemonic(&store).unwrap().as_deref(), Some(phrase.as_str()));
        assert_eq!(identity_status(&store).unwrap(), (true, Some(12)));
    }

    #[test]
    fn import_mnemonic_into_empty_store_then_same_is_already() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("store.redb");
        let store = ChunkStore::open(&path).unwrap();
        let seed = IdentitySeed::generate().unwrap();
        let (node_id, status) = import_mnemonic(&store, &seed.mnemonic).unwrap();
        assert_eq!(status, "imported");
        // Тот же сид поверх — "already", тот же node_id.
        let (node_id2, status2) = import_mnemonic(&store, &seed.mnemonic).unwrap();
        assert_eq!(status2, "already");
        assert_eq!(node_id, node_id2);
        // И node_id совпадает с load_or_create.
        let (id, created) = load_or_create_identity(&store).unwrap();
        assert!(created.is_none());
        assert_eq!(id.node_id, node_id);
    }

    #[test]
    fn import_mnemonic_refuses_different_seed_on_initialized_store() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("store.redb");
        let store = ChunkStore::open(&path).unwrap();
        let _ = load_or_create_identity(&store).unwrap();
        let other = IdentitySeed::generate().unwrap();
        let err = import_mnemonic(&store, &other.mnemonic).unwrap_err();
        assert!(err.to_string().contains("different mnemonic"));
    }

    #[test]
    fn import_mnemonic_rejects_invalid_bip39() {
        let dir = tempdir().unwrap();
        let store = ChunkStore::open(dir.path().join("s.redb")).unwrap();
        let err = import_mnemonic(&store, "not a valid phrase at all really no").unwrap_err();
        assert!(!err.to_string().is_empty());
    }
}
