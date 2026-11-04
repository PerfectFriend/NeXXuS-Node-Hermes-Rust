//! Binary Merkle tree with odd-node duplication (Bitcoin/NeXXUs style).
//! Matches golden vector 04.

use sha2::{Digest, Sha256};

/// Compute the root hash of a Merkle tree over `leaves`.
/// Leaves are pre-hashed 32-byte digests; odd nodes are duplicated up the tree.
pub fn merkle_root(leaves: &[[u8; 32]]) -> [u8; 32] {
    if leaves.is_empty() {
        return Sha256::new().finalize().into();
    }
    let mut level: Vec<[u8; 32]> = leaves.to_vec();
    while level.len() > 1 {
        if level.len() % 2 == 1 {
            // duplicate last node
            let last = *level.last().unwrap();
            level.push(last);
        }
        let mut next = Vec::with_capacity(level.len() / 2);
        for pair in level.chunks(2) {
            let mut h = Sha256::new();
            h.update(pair[0]);
            h.update(pair[1]);
            next.push(h.finalize().into());
        }
        level = next;
    }
    level[0]
}

/// Generate an inclusion proof for `leaf_index`.
pub fn merkle_proof(leaves: &[[u8; 32]], leaf_index: usize) -> Vec<([u8; 32], bool)> {
    // (sibling, is_right_sibling)
    let mut proof = Vec::new();
    if leaves.is_empty() {
        return proof;
    }
    let mut level: Vec<[u8; 32]> = leaves.to_vec();
    let mut pos = leaf_index;
    while level.len() > 1 {
        if level.len() % 2 == 1 {
            let last = *level.last().unwrap();
            level.push(last);
        }
        let is_right = pos % 2 == 1;
        let sibling_idx = if is_right { pos - 1 } else { pos + 1 };
        proof.push((level[sibling_idx], is_right));
        let mut next = Vec::with_capacity(level.len() / 2);
        for pair in level.chunks(2) {
            let mut h = Sha256::new();
            h.update(pair[0]);
            h.update(pair[1]);
            next.push(h.finalize().into());
        }
        level = next;
        pos /= 2;
    }
    proof
}

/// Verify an inclusion proof: recompute the root from leaf + path.
pub fn verify_proof(root: &[u8; 32], leaf: &[u8; 32], _leaf_index: usize, proof: &[([u8; 32], bool)]) -> bool {
    let mut computed = *leaf;
    for (sibling, is_right) in proof {
        let mut h = Sha256::new();
        if *is_right {
            // computed is the right child: parent = H(sibling, computed)
            h.update(*sibling);
            h.update(computed);
        } else {
            // computed is the left child: parent = H(computed, sibling)
            h.update(computed);
            h.update(*sibling);
        }
        computed = h.finalize().into();
    }
    computed == *root
}

/// Proof of Retrievability: challenge → response → verify.
pub struct PorChallenge {
    pub seed: [u8; 32],
    pub chunk_index: usize,
}

pub struct PorResponse {
    pub response: [u8; 32], // SHA-256(chunk || seed)
}

/// Server computes response for a challenged chunk.
pub fn por_response(chunk: &[u8], challenge: &PorChallenge) -> PorResponse {
    let mut h = Sha256::new();
    h.update(chunk);
    h.update(challenge.seed);
    PorResponse {
        response: h.finalize().into(),
    }
}

/// Client verifies response against the chunk hash.
pub fn por_verify(chunk: &[u8], response: &PorResponse, challenge: &PorChallenge) -> bool {
    let expected = por_response(chunk, challenge);
    expected.response == response.response
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn matches_golden_vector_04_root() {
        // 5 leaves from the vector
        let leaves: Vec<[u8; 32]> = [
            "0000000000000000000000000000000000000000000000000000000000000001",
            "0000000000000000000000000000000000000000000000000000000000000002",
            "0000000000000000000000000000000000000000000000000000000000000003",
            "0000000000000000000000000000000000000000000000000000000000000004",
            "0000000000000000000000000000000000000000000000000000000000000005",
        ]
        .iter()
        .map(|h| hex::decode(h).unwrap().try_into().unwrap())
        .collect();
        let root = merkle_root(&leaves);
        assert_eq!(
            hex::encode(root),
            "b3704b0f54c4070b36ace72ae3f4879e91eda3f81cef4cb97653d2a0b8592ce1"
        );
    }

    #[test]
    fn proof_verify_roundtrip() {
        let leaves: Vec<[u8; 32]> = (0..5)
            .map(|i| {
                let mut h = [0u8; 32];
                h[31] = i as u8;
                h
            })
            .collect();
        let root = merkle_root(&leaves);
        for i in 0..leaves.len() {
            let proof = merkle_proof(&leaves, i);
            assert!(
                verify_proof(&root, &leaves[i], i, &proof),
                "proof for leaf {i} failed"
            );
        }
    }

    #[test]
    fn proof_rejects_wrong_leaf() {
        let leaves: Vec<[u8; 32]> = (0..3).map(|i| { let mut h=[0u8;32]; h[31]=i as u8; h }).collect();
        let root = merkle_root(&leaves);
        let proof = merkle_proof(&leaves, 0);
        let other = leaves[1];
        assert!(!verify_proof(&root, &other, 0, &proof));
    }

    #[test]
    fn por_deterministic() {
        let chunk = [0x42u8; 1024];
        let challenge = PorChallenge { seed: [7u8; 32], chunk_index: 3 };
        let r1 = por_response(&chunk, &challenge);
        let r2 = por_response(&chunk, &challenge);
        assert_eq!(r1.response, r2.response);
        assert!(por_verify(&chunk, &r1, &challenge));
        // wrong chunk fails
        let mut other = chunk;
        other[0] ^= 1;
        assert!(!por_verify(&other, &r1, &challenge));
    }
}
