//! Reed-Solomon erasure coding — ADR-0003.
//! Own GF(2⁸) over polynomial 0x11D, 4 data + 2 parity shards, matches golden vector 03.

#![allow(clippy::needless_range_loop, clippy::manual_div_ceil)]

use crate::error::NexxusError;

pub mod gf256;
pub mod matrix;

pub use gf256::{gf_div, gf_inv, gf_mul};
pub use matrix::{generator_matrix, inverse_for_shards};

pub const DATA_SHARDS: usize = 4;
pub const PARITY_SHARDS: usize = 2;
pub const TOTAL_SHARDS: usize = 6;

pub type Shard = Vec<u8>;

/// Encode `data` into 6 shards (4 data + 2 parity). Each shard = ceil(len/4) bytes,
/// last data shard zero-padded; caller stores original length separately.
pub fn encode(data: &[u8]) -> [Shard; TOTAL_SHARDS] {
    let shard_len = (data.len() + DATA_SHARDS - 1) / DATA_SHARDS;
    let mut chunks: [Vec<u8>; DATA_SHARDS] = [
        vec![0u8; shard_len],
        vec![0u8; shard_len],
        vec![0u8; shard_len],
        vec![0u8; shard_len],
    ];
    for (i, &b) in data.iter().enumerate() {
        chunks[i / shard_len][i % shard_len] = b;
    }

    let g = generator_matrix();
    let mut shards: [Shard; TOTAL_SHARDS] = [
        chunks[0].clone(),
        chunks[1].clone(),
        chunks[2].clone(),
        chunks[3].clone(),
        vec![0u8; shard_len],
        vec![0u8; shard_len],
    ];
    for byte in 0..shard_len {
        for p in 0..PARITY_SHARDS {
            let mut acc = 0u8;
            for d in 0..DATA_SHARDS {
                acc ^= gf_mul(g[d][DATA_SHARDS + p], chunks[d][byte]);
            }
            shards[DATA_SHARDS + p][byte] = acc;
        }
    }
    shards
}

/// Decode from any >=4 surviving shards back to original `original_len` bytes.
pub fn decode(shards: &[(&[u8], usize)], original_len: usize) -> Result<Vec<u8>, NexxusError> {
    if shards.len() < DATA_SHARDS {
        return Err(NexxusError::InsufficientShards {
            need: DATA_SHARDS,
            got: shards.len(),
        });
    }
    let shard_len = shards[0].0.len();
    for (s, _) in shards.iter().skip(1) {
        if s.len() != shard_len {
            return Err(NexxusError::Io("shard length mismatch".into()));
        }
    }

    let indices: Vec<usize> = shards.iter().take(4).map(|(_, idx)| *idx).collect();
    let inv = inverse_for_shards(&indices)?;

    let mut data = vec![0u8; original_len];
    for byte in 0..shard_len {
        let mut y = [0u8; 4];
        for (r, (s, _)) in shards.iter().take(4).enumerate() {
            y[r] = s[byte];
        }
        for c in 0..4 {
            let mut acc = 0u8;
            for r in 0..4 {
                acc ^= gf_mul(inv[c][r], y[r]);
            }
            let pos = c * shard_len + byte;
            if pos < original_len {
                data[pos] = acc;
            }
        }
    }
    Ok(data)
}

/// Reconstruct a missing shard at `index` from >=4 surviving shards.
pub fn reconstruct(index: usize, surviving: &[(&[u8], usize)]) -> Result<Shard, NexxusError> {
    if surviving.len() < DATA_SHARDS {
        return Err(NexxusError::InsufficientShards {
            need: DATA_SHARDS,
            got: surviving.len(),
        });
    }
    if index >= TOTAL_SHARDS {
        return Err(NexxusError::Io(format!("shard index {index} out of range")));
    }
    let indices: Vec<usize> = surviving.iter().take(4).map(|(_, idx)| *idx).collect();
    let inv = inverse_for_shards(&indices)?;
    let g = generator_matrix();
    let shard_len = surviving[0].0.len();

    let mut shard = vec![0u8; shard_len];
    for byte in 0..shard_len {
        let mut y = [0u8; 4];
        for (r, (s, _)) in surviving.iter().take(4).enumerate() {
            y[r] = s[byte];
        }
        let mut x = [0u8; 4];
        for c in 0..4 {
            let mut acc = 0u8;
            for r in 0..4 {
                acc ^= gf_mul(inv[c][r], y[r]);
            }
            x[c] = acc;
        }
        let mut acc = 0u8;
        for c in 0..4 {
            acc ^= gf_mul(g[c][index], x[c]);
        }
        shard[byte] = acc;
    }
    Ok(shard)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn encode_roundtrip_all_15_combinations() {
        let data: Vec<u8> = (0..16).map(|i| i as u8).collect();
        let shards = encode(&data);
        let shard_refs: [(&[u8], usize); 6] = [
            (&shards[0], 0),
            (&shards[1], 1),
            (&shards[2], 2),
            (&shards[3], 3),
            (&shards[4], 4),
            (&shards[5], 5),
        ];
        for mask in 0u8..64 {
            if mask.count_ones() != 4 {
                continue;
            }
            let mut picked = Vec::new();
            for i in 0..6 {
                if mask & (1 << i) != 0 {
                    picked.push(shard_refs[i]);
                }
            }
            let recovered = decode(&picked, data.len()).unwrap();
            assert_eq!(recovered, data, "combination {mask:b} failed");
        }
    }

    #[test]
    fn decode_rejects_fewer_than_4() {
        let shards = encode(&[1, 2, 3, 4]);
        let picked: [(&[u8], usize); 3] = [(&shards[0], 0), (&shards[1], 1), (&shards[2], 2)];
        assert!(decode(&picked, 4).is_err());
    }

    #[test]
    fn reconstruct_missing_shard() {
        let data: Vec<u8> = (0..32).map(|i| i as u8).collect();
        let shards = encode(&data);
        let surviving: [(&[u8], usize); 5] = [
            (&shards[0], 0),
            (&shards[1], 1),
            (&shards[3], 3),
            (&shards[4], 4),
            (&shards[5], 5),
        ];
        let rec = reconstruct(2, &surviving).unwrap();
        assert_eq!(rec, shards[2]);
    }

    #[test]
    fn parity_p1_is_xor() {
        // chunks: [de,ad] [be,ef] [01,23] [45,67]; P1 byte0 = de^be^01^45 = 0x24
        let data: Vec<u8> = vec![0xde, 0xad, 0xbe, 0xef, 0x01, 0x23, 0x45, 0x67];
        let shards = encode(&data);
        assert_eq!(shards[4][0], 0xde ^ 0xbe ^ 0x01 ^ 0x45);
        assert_eq!(shards[4][1], 0xad ^ 0xef ^ 0x23 ^ 0x67);
    }

    /// Cross-check encode/decode against golden vector 03 byte-for-byte.
    #[test]
    fn matches_golden_vector_03() {
        use sha2::{Digest, Sha256};
        const LEN: usize = 16384;
        let mut input = vec![0u8; LEN];
        for i in 0..LEN {
            input[i] = ((i as u32 * 37 + 11) & 0xff) as u8;
        }
        let hash = Sha256::digest(&input);
        assert_eq!(
            hex::encode(hash),
            "ce61cc72a84bd3526a8f955235c5f4f67439820d6ffb910b5ab07e54741262b8"
        );

        let shards = encode(&input);
        let expected = [
            ("4e441a3533bb2c10cd5649981d395744213e09a336746b5a3458fee4057205ec", 0),
            ("4e441a3533bb2c10cd5649981d395744213e09a336746b5a3458fee4057205ec", 1),
            ("4e441a3533bb2c10cd5649981d395744213e09a336746b5a3458fee4057205ec", 2),
            ("4e441a3533bb2c10cd5649981d395744213e09a336746b5a3458fee4057205ec", 3),
            ("ad7facb2586fc6e966c004d7d1d16b024f5805ff7cb47c7a85dabd8b48892ca7", 4),
            ("a73f90de170493bc22031a85d37f7fb9d86e6d518214b98cbd9f4585784ebf5c", 5),
        ];
        for (exp_hash, idx) in expected {
            let h = Sha256::digest(&shards[idx]);
            assert_eq!(
                hex::encode(h),
                exp_hash,
                "shard {} hash mismatch",
                idx
            );
        }
        // first 16 bytes of shard 0
        assert_eq!(
            hex::encode(&shards[0][..16]),
            "0b30557a9fc4e90e33587da2c7ec1136"
        );
        // roundtrip from all 6
        let refs: [(&[u8], usize); 6] = shards.iter().enumerate().map(|(i, s)| (s.as_slice(), i)).collect::<Vec<_>>().try_into().unwrap();
        let recovered = decode(&refs, LEN).unwrap();
        assert_eq!(recovered, input);
    }
}
