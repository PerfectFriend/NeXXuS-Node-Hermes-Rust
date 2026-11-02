//! Binary wire protocol — ADR-0001/0002. Big-Endian everywhere, no JSON on the wire.

pub mod header;
pub mod opcode;
pub mod payloads;
pub mod reader;
