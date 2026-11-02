//! Reed-Solomon erasure coding — ADR-0003.
//! Own GF(2⁸) implementation over polynomial 0x11D to match golden vector 03.
//! Layout: 4 data shards + 2 parity shards (P1 = XOR, P2 = Vandermonde [1,2,4,8]).

#![allow(clippy::needless_range_loop, clippy::manual_memcpy, clippy::manual_div_ceil)]

/// GF(2⁸) field polynomial: x⁸ + x⁴ + x³ + x + 1 = 0x11D.
const PRIMITIVE_POLY: u16 = 0x11D;

/// Precomputed exponent and logarithm tables for GF(2⁸).
struct Gf256 {
    exp: [u8; 512], // exp[i] = generator^i, doubled for wrap-around
    log: [u8; 256], // log[value] = i such that generator^i = value; log[0] = 0 (unused)
}

static GF256: once_cell::sync::Lazy<Gf256> = once_cell::sync::Lazy::new(|| {
    let mut exp = [0u8; 512];
    let mut log = [0u8; 256];
    let mut x: u8 = 1;
    for i in 0..255 {
        exp[i as usize] = x;
        log[x as usize] = i as u8;
        x = gf_mul_raw(x, 2);
    }
    for i in 255..512 {
        exp[i as usize] = exp[(i - 255) as usize];
    }
    log[0] = 0;
    Gf256 { exp, log }
});

fn gf_mul_raw(a: u8, b: u8) -> u8 {
    if a == 0 || b == 0 {
        return 0;
    }
    let mut aa = a as u16;
    let mut bb = b as u16;
    let mut p = 0u16;
    for _ in 0..8 {
        if bb & 1 == 1 {
            p ^= aa;
        }
        bb >>= 1;
        aa <<= 1;
        if aa & 0x100 != 0 {
            aa ^= PRIMITIVE_POLY;
        }
    }
    p as u8
}

fn gf_div_raw(a: u8, b: u8) -> u8 {
    if a == 0 {
        return 0;
    }
    if b == 0 {
        panic!("gf_div by zero");
    }
    let gf = &GF256;
    gf.exp[(gf.log[a as usize] as usize + 255 - gf.log[b as usize] as usize) % 255]
}

fn gf_inv_raw(a: u8) -> u8 {
    if a == 0 {
        panic!("gf_inv of zero");
    }
    let gf = &GF256;
    gf.exp[(255 - gf.log[a as usize] as usize) % 255]
}

/// Multiply two elements in GF(2⁸).
pub fn gf_mul(a: u8, b: u8) -> u8 {
    gf_mul_raw(a, b)
}

/// Divide a by b in GF(2⁸).
pub fn gf_div(a: u8, b: u8) -> u8 {
    gf_div_raw(a, b)
}

/// Multiplicative inverse of a in GF(2⁸).
pub fn gf_inv(a: u8) -> u8 {
    gf_inv_raw(a)
}

/// Multiply a GF(2⁸) polynomial (coeffs low-to-high) by a scalar.
pub fn gf_poly_scale(poly: &[u8], scalar: u8) -> Vec<u8> {
    poly.iter().map(|&c| gf_mul(c, scalar)).collect()
}

/// Add (XOR) two GF(2⁸) polynomials element-wise.
pub fn gf_poly_add(poly1: &[u8], poly2: &[u8]) -> Vec<u8> {
    let n = poly1.len().max(poly2.len());
    let mut r = vec![0u8; n];
    for (i, (a, b)) in poly1.iter().zip(poly2.iter()).enumerate() {
        r[i] = a ^ b;
    }
    // if poly1 longer, remaining are just poly1 values (XOR with 0)
    let mut offset = poly1.len();
    if poly2.len() > poly1.len() {
        for i in poly1.len()..poly2.len() {
            r[i] = poly2[i];
        }
        offset = poly2.len();
    }
    for i in poly1.len()..offset {
        r[i] = poly1[i];
    }
    r
}

/// Multiply two GF(2⁸) polynomials.
pub fn gf_poly_mul(poly1: &[u8], poly2: &[u8]) -> Vec<u8> {
    let mut r = vec![0u8; poly1.len() + poly2.len() - 1];
    for (i, &a) in poly1.iter().enumerate() {
        for (j, &b) in poly2.iter().enumerate() {
            r[i + j] ^= gf_mul(a, b);
        }
    }
    r
}

/// Evaluate a GF(2⁸) polynomial at x (Horner's method, coeffs low-to-high).
pub fn gf_poly_eval(poly: &[u8], x: u8) -> u8 {
    if x == 0 {
        return poly[0];
    }
    let y = poly[poly.len() - 1];
    let mut result = y;
    for i in (0..poly.len() - 1).rev() {
        result = gf_mul(result, x) ^ poly[i];
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gf_mul_is_commutative_and_invertible() {
        for a in 1..255 {
            for b in 1..255 {
                assert_eq!(gf_mul(a, b), gf_mul(b, a));
                assert_eq!(gf_div(gf_mul(a, b), b), a);
            }
        }
    }

    #[test]
    fn gf_inv_is_correct() {
        for a in 1..255 {
            assert_eq!(gf_mul(a, gf_inv(a)), 1);
        }
    }

    #[test]
    fn gf_tables_match_known_values() {
        // generator = 2: 2^8 = 0x1d (reduce by 0x11d)
        let gf = &GF256;
        assert_eq!(gf.exp[8], 0x1d);
        assert_eq!(gf.log[0x1d], 8);
    }
}
