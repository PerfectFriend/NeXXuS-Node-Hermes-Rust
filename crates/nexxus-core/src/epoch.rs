//! Epoch finalize — committee multi-sig Ed25519 (ADR-0008).
//! Aggregates M-of-N signatures over `epoch_number || merkle_root || total_bytes`.
//! Pure logic — no I/O, compiles to wasm32 unchanged.

use crate::error::NexxusError;
use crate::keys::identity::Identity;
use crate::wire::payloads::EpochFinalize;
use ed25519_dalek::VerifyingKey;
use std::collections::BTreeSet;

/// Result of epoch finalize verification.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct EpochVerifyResult {
    pub valid: bool,
    pub signatures_checked: usize,
    pub signatures_valid: usize,
    pub quorum_met: bool,
}

/// Verify an EpochFinalize against a registry of auditor pubkeys.
/// Requires at least `threshold` valid signatures from distinct registered pubkeys.
pub fn verify_epoch_finalize(
    finalize: &EpochFinalize,
    auditors: &[VerifyingKey],
    threshold: usize,
) -> Result<EpochVerifyResult, NexxusError> {
    let auditor_set: BTreeSet<[u8; 32]> = auditors
        .iter()
        .map(|vk| vk.to_bytes())
        .collect();

    let mut msg = Vec::new();
    msg.extend_from_slice(&finalize.epoch_number.to_be_bytes());
    msg.extend_from_slice(&finalize.merkle_root);
    msg.extend_from_slice(&finalize.total_bytes.to_be_bytes());

    let mut seen_pubkeys: BTreeSet<[u8; 32]> = BTreeSet::new();
    let mut valid_count = 0usize;

    for sig in &finalize.signatures {
        // Skip duplicate pubkeys (double-signing doesn't count twice)
        if !seen_pubkeys.insert(sig.pubkey) {
            continue;
        }

        // Pubkey must be a registered auditor
        if !auditor_set.contains(&sig.pubkey) {
            continue;
        }

        let vk = match VerifyingKey::from_bytes(&sig.pubkey) {
            Ok(vk) => vk,
            Err(_) => continue,
        };

        if Identity::verify(&vk, &msg, &sig.signature) {
            valid_count += 1;
        }
    }

    // Deny-by-default: quorum requires a non-empty auditor registry AND a
    // positive threshold. Previously `0 >= 0` made every EpochFinalize pass
    // with an empty registry and threshold=0.
    let quorum_met = !auditors.is_empty() && threshold > 0 && valid_count >= threshold;
    Ok(EpochVerifyResult {
        valid: quorum_met,
        signatures_checked: finalize.signatures.len(),
        signatures_valid: valid_count,
        quorum_met,
    })
}

/// Build the signing message for an epoch (same bytes the committee signs).
pub fn epoch_signing_bytes(epoch_number: u64, merkle_root: &[u8; 32], total_bytes: u64) -> Vec<u8> {
    let mut msg = Vec::new();
    msg.extend_from_slice(&epoch_number.to_be_bytes());
    msg.extend_from_slice(merkle_root);
    msg.extend_from_slice(&total_bytes.to_be_bytes());
    msg
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::keys::identity::Identity;
    use crate::wire::payloads::CommitteeSig;

    #[test]
    fn verify_valid_multi_sig() {
        let id1 = Identity::generate();
        let id2 = Identity::generate();
        let auditors = vec![id1.verifying_key, id2.verifying_key];

        let epoch_number: u64 = 3;
        let merkle_root = [0x11u8; 32];
        let total_bytes: u64 = 1_000_000;
        let msg = epoch_signing_bytes(epoch_number, &merkle_root, total_bytes);

        let sig1 = id1.sign(&msg);
        let sig2 = id2.sign(&msg);

        let finalize = EpochFinalize {
            epoch_number,
            merkle_root,
            total_bytes,
            signatures: vec![
                CommitteeSig {
                    pubkey: id1.verifying_key.to_bytes(),
                    signature: sig1,
                },
                CommitteeSig {
                    pubkey: id2.verifying_key.to_bytes(),
                    signature: sig2,
                },
            ],
        };

        let result = verify_epoch_finalize(&finalize, &auditors, 2).unwrap();
        assert!(result.valid);
        assert!(result.quorum_met);
        assert_eq!(result.signatures_valid, 2);
    }

    #[test]
    fn verify_threshold_not_met() {
        let id1 = Identity::generate();
        let id2 = Identity::generate();
        let auditors = vec![id1.verifying_key, id2.verifying_key];

        let epoch_number: u64 = 3;
        let merkle_root = [0x11u8; 32];
        let total_bytes: u64 = 1_000_000;
        let msg = epoch_signing_bytes(epoch_number, &merkle_root, total_bytes);

        let sig1 = id1.sign(&msg);

        let finalize = EpochFinalize {
            epoch_number,
            merkle_root,
            total_bytes,
            signatures: vec![CommitteeSig {
                pubkey: id1.verifying_key.to_bytes(),
                signature: sig1,
            }],
        };

        let result = verify_epoch_finalize(&finalize, &auditors, 2).unwrap();
        assert!(!result.valid);
        assert!(!result.quorum_met);
        assert_eq!(result.signatures_valid, 1);
    }

    #[test]
    fn empty_registry_denies_even_with_zero_threshold() {
        // Regression: previously 0 >= 0 made this pass.
        let finalize = EpochFinalize {
            epoch_number: 1,
            merkle_root: [0x22u8; 32],
            total_bytes: 1,
            signatures: vec![],
        };
        let result = verify_epoch_finalize(&finalize, &[], 0).unwrap();
        assert!(!result.quorum_met);
        assert!(!result.valid);
    }

    #[test]
    fn zero_threshold_with_registry_still_denies() {
        let id1 = Identity::generate();
        let auditors = vec![id1.verifying_key];
        let msg = epoch_signing_bytes(1, &[0x22u8; 32], 1);
        let sig = id1.sign(&msg);
        let finalize = EpochFinalize {
            epoch_number: 1,
            merkle_root: [0x22u8; 32],
            total_bytes: 1,
            signatures: vec![CommitteeSig {
                pubkey: id1.verifying_key.to_bytes(),
                signature: sig,
            }],
        };
        let result = verify_epoch_finalize(&finalize, &auditors, 0).unwrap();
        assert!(!result.quorum_met);
        assert!(!result.valid);
    }

    #[test]
    fn verify_unregistered_auditor_rejected() {
        let id1 = Identity::generate();
        let id_unreg = Identity::generate();
        let auditors = vec![id1.verifying_key]; // id_unreg not registered

        let epoch_number: u64 = 3;
        let merkle_root = [0x11u8; 32];
        let total_bytes: u64 = 1_000_000;
        let msg = epoch_signing_bytes(epoch_number, &merkle_root, total_bytes);

        let sig1 = id1.sign(&msg);
        let sig_unreg = id_unreg.sign(&msg);

        let finalize = EpochFinalize {
            epoch_number,
            merkle_root,
            total_bytes,
            signatures: vec![
                CommitteeSig {
                    pubkey: id1.verifying_key.to_bytes(),
                    signature: sig1,
                },
                CommitteeSig {
                    pubkey: id_unreg.verifying_key.to_bytes(),
                    signature: sig_unreg,
                },
            ],
        };

        let result = verify_epoch_finalize(&finalize, &auditors, 2).unwrap();
        assert!(!result.valid); // only 1 valid from registered auditor, need 2
        assert_eq!(result.signatures_valid, 1);
    }

    #[test]
    fn verify_duplicate_pubkey_counted_once() {
        let id1 = Identity::generate();
        let auditors = vec![id1.verifying_key];

        let epoch_number: u64 = 3;
        let merkle_root = [0x11u8; 32];
        let total_bytes: u64 = 1_000_000;
        let msg = epoch_signing_bytes(epoch_number, &merkle_root, total_bytes);

        let sig1 = id1.sign(&msg);

        // Two signatures from same pubkey — counts as one
        let finalize = EpochFinalize {
            epoch_number,
            merkle_root,
            total_bytes,
            signatures: vec![
                CommitteeSig {
                    pubkey: id1.verifying_key.to_bytes(),
                    signature: sig1,
                },
                CommitteeSig {
                    pubkey: id1.verifying_key.to_bytes(),
                    signature: sig1,
                },
            ],
        };

        let result = verify_epoch_finalize(&finalize, &auditors, 2).unwrap();
        assert!(!result.valid); // only 1 unique valid signature
        assert_eq!(result.signatures_valid, 1);
    }
}
