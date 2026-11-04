//! Bounded Big-Endian reader/writer. Every read past the end fails instead of panicking.

use crate::error::NexxusError;

pub struct Reader<'a> {
    buf: &'a [u8],
    pos: usize,
}

impl<'a> Reader<'a> {
    pub fn new(buf: &'a [u8]) -> Self {
        Reader { buf, pos: 0 }
    }

    pub const fn pos(&self) -> usize {
        self.pos
    }

    pub fn remaining(&self) -> usize {
        self.buf.len() - self.pos
    }

    pub fn is_empty(&self) -> bool {
        self.remaining() == 0
    }

    fn take(&mut self, n: usize) -> Result<&'a [u8], NexxusError> {
        if self.remaining() < n {
            return Err(NexxusError::WireTruncated {
                offset: self.pos,
                need: n,
            });
        }
        let s = &self.buf[self.pos..self.pos + n];
        self.pos += n;
        Ok(s)
    }

    pub fn u8(&mut self) -> Result<u8, NexxusError> {
        Ok(self.take(1)?[0])
    }

    pub fn u16_be(&mut self) -> Result<u16, NexxusError> {
        Ok(u16::from_be_bytes(self.fixed::<2>()?))
    }

    pub fn u32_be(&mut self) -> Result<u32, NexxusError> {
        Ok(u32::from_be_bytes(self.fixed::<4>()?))
    }

    pub fn u64_be(&mut self) -> Result<u64, NexxusError> {
        Ok(u64::from_be_bytes(self.fixed::<8>()?))
    }

    pub fn bytes(&mut self, n: usize) -> Result<&'a [u8], NexxusError> {
        self.take(n)
    }

    pub fn fixed<const N: usize>(&mut self) -> Result<[u8; N], NexxusError> {
        let s = self.take(N)?;
        // N is const-generic and take(N) guarantees length; unwrap is unreachable.
        Ok(s.try_into().expect("take(N) returns exactly N bytes"))
    }

    pub fn rest(&mut self) -> &'a [u8] {
        let s = &self.buf[self.pos..];
        self.pos = self.buf.len();
        s
    }
}

pub struct Writer {
    pub buf: Vec<u8>,
}

impl Default for Writer {
    fn default() -> Self {
        Self::new()
    }
}

impl Writer {
    pub fn new() -> Self {
        Writer { buf: Vec::new() }
    }

    pub fn with_capacity(cap: usize) -> Self {
        Writer {
            buf: Vec::with_capacity(cap),
        }
    }

    pub fn u8(&mut self, v: u8) -> &mut Self {
        self.buf.push(v);
        self
    }

    pub fn u16_be(&mut self, v: u16) -> &mut Self {
        self.buf.extend_from_slice(&v.to_be_bytes());
        self
    }

    pub fn u32_be(&mut self, v: u32) -> &mut Self {
        self.buf.extend_from_slice(&v.to_be_bytes());
        self
    }

    pub fn u64_be(&mut self, v: u64) -> &mut Self {
        self.buf.extend_from_slice(&v.to_be_bytes());
        self
    }

    pub fn bytes(&mut self, b: &[u8]) -> &mut Self {
        self.buf.extend_from_slice(b);
        self
    }

    pub fn fixed<const N: usize>(&mut self, b: &[u8; N]) -> &mut Self {
        self.buf.extend_from_slice(b);
        self
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn writer_is_big_endian() {
        let mut w = Writer::new();
        w.u16_be(0x1234).u32_be(0xdeadbeef).u64_be(1);
        assert_eq!(
            w.buf,
            vec![0x12, 0x34, 0xde, 0xad, 0xbe, 0xef, 0, 0, 0, 0, 0, 0, 0, 1]
        );
    }

    #[test]
    fn reader_rejects_truncated() {
        let mut r = Reader::new(&[0x01, 0x02]);
        assert!(r.u32_be().is_err());
        assert_eq!(r.pos(), 0); // failed read must not advance
        let mut r = Reader::new(&[0x01]);
        assert!(r.fixed::<4>().is_err());
    }

    #[test]
    fn reader_roundtrip() {
        let mut w = Writer::new();
        w.u8(7).u16_be(0x0203).fixed(&[9u8; 3]).bytes(b"ab");
        let mut r = Reader::new(&w.buf);
        assert_eq!(r.u8().unwrap(), 7);
        assert_eq!(r.u16_be().unwrap(), 0x0203);
        assert_eq!(r.fixed::<3>().unwrap(), [9, 9, 9]);
        assert_eq!(r.rest(), b"ab");
        assert!(r.is_empty());
    }
}
