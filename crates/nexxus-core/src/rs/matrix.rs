//! Matrix operations over GF(2⁸) for Reed-Solomon erasure coding.
//! Gauss-Jordan inversion with a cache of all C(6,4)=15 inverse matrices
//! for the 4-of-6 shard recovery combinations.

#![allow(clippy::needless_range_loop)]

use crate::error::NexxusError;
use crate::rs::gf256::{gf_inv, gf_mul};

const N: usize = 6; // total shards
const K: usize = 4; // data shards

/// Generator matrix G (K x N): [I_K | P] where P rows are Vandermonde coefficients.
/// Row i (data shard i): [1,0,0,0 | 1, 2^i, 4^i, 8^i] style.
pub fn generator_matrix() -> [[u8; N]; K] {
    let mut g = [[0u8; N]; K];
    for i in 0..K {
        for j in 0..N {
            if j < K {
                g[i][j] = if i == j { 1 } else { 0 };
            } else {
                let p = j - K; // 0 -> P1, 1 -> P2
                g[i][j] = if p == 0 {
                    1 // P1 = XOR of all data shards
                } else {
                    gf_pow(2, i) // P2 = Vandermonde [1, 2, 4, 8]
                };
            }
        }
    }
    g
}

fn gf_pow(base: u8, exp: usize) -> u8 {
    if exp == 0 {
        return 1;
    }
    let mut r = 1u8;
    for _ in 0..exp {
        r = gf_mul(r, base);
    }
    r
}

/// Gauss-Jordan inversion of a square matrix over GF(2⁸).
fn invert_matrix(m: &[[u8; 4]; 4]) -> Result<[[u8; 4]; 4], NexxusError> {
    let mut aug = [[0u8; 8]; 4];
    for i in 0..4 {
        for j in 0..4 {
            aug[i][j] = m[i][j];
            aug[i][4 + j] = if i == j { 1 } else { 0 };
        }
    }
    for col in 0..4 {
        // find pivot
        let mut pivot = None;
        for row in col..4 {
            if aug[row][col] != 0 {
                pivot = Some(row);
                break;
            }
        }
        let pivot = pivot.ok_or(NexxusError::SingularMatrix)?;
        aug.swap(col, pivot);
        let inv = gf_inv(aug[col][col]);
        for j in 0..8 {
            aug[col][j] = gf_mul(aug[col][j], inv);
        }
        for row in 0..4 {
            if row != col && aug[row][col] != 0 {
                let factor = aug[row][col];
                for j in 0..8 {
                    aug[row][j] ^= gf_mul(factor, aug[col][j]);
                }
            }
        }
    }
    let mut inv = [[0u8; 4]; 4];
    for i in 0..4 {
        for j in 0..4 {
            inv[i][j] = aug[i][4 + j];
        }
    }
    Ok(inv)
}

/// Cache of inverse matrices for every 4-of-6 shard combination.
/// Key: bitmask of which 4 shards survived (6 bits, exactly 4 set).
static INVERSE_CACHE: once_cell::sync::Lazy<[Option<[[u8; 4]; 4]>; 64]> =
    once_cell::sync::Lazy::new(|| {
        let mut cache = [None; 64];
        for mask in 0u8..64 {
            if mask.count_ones() != 4 {
                continue;
            }
            // indices of surviving shards (0..6)
            let mut idx = [0usize; 4];
            let mut n = 0;
            for i in 0..6 {
                if mask & (1 << i) != 0 {
                    idx[n] = i;
                    n += 1;
                }
            }
            // Build 4x4 matrix M where M[r][c] = G[c][idx[r]] (rows = surviving shards, cols = data coeffs)
            let g = generator_matrix();
            let mut m = [[0u8; 4]; 4];
            for r in 0..4 {
                for c in 0..4 {
                    m[r][c] = g[c][idx[r]];
                }
            }
            cache[mask as usize] = invert_matrix(&m).ok();
        }
        cache
    });

/// Get the inverse matrix for a set of surviving shard indices.
pub fn inverse_for_shards(surviving: &[usize]) -> Result<[[u8; 4]; 4], NexxusError> {
    if surviving.len() != 4 {
        return Err(NexxusError::InsufficientShards {
            need: 4,
            got: surviving.len(),
        });
    }
    let mut mask = 0u8;
    for &i in surviving {
        if i >= 6 {
            return Err(NexxusError::Io(format!("shard index {i} out of range")));
        }
        mask |= 1 << i;
    }
    INVERSE_CACHE[mask as usize]
        .ok_or(NexxusError::SingularMatrix)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn generator_matrix_is_systematic() {
        let g = generator_matrix();
        // first 4 columns form identity
        for i in 0..4 {
            for j in 0..4 {
                assert_eq!(g[i][j], if i == j { 1 } else { 0 });
            }
        }
    }

    #[test]
    fn all_inverses_exist_and_are_correct() {
        let g = generator_matrix();
        for mask in 0u8..64 {
            if mask.count_ones() != 4 {
                continue;
            }
            let mut idx = [0usize; 4];
            let mut n = 0;
            for i in 0..6 {
                if mask & (1 << i) != 0 {
                    idx[n] = i;
                    n += 1;
                }
            }
            let inv = inverse_for_shards(&idx).unwrap();
            // M * inv = I where M[r][c] = g[c][idx[r]]
            let mut m = [[0u8; 4]; 4];
            for r in 0..4 {
                for c in 0..4 {
                    m[r][c] = g[c][idx[r]];
                }
            }
            for r in 0..4 {
                for c in 0..4 {
                    let mut s = 0u8;
                    for k in 0..4 {
                        s ^= gf_mul(m[r][k], inv[k][c]);
                    }
                    assert_eq!(s, if r == c { 1 } else { 0 });
                }
            }
        }
    }
}
