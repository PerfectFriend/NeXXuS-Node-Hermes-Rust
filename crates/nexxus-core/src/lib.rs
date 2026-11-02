//! NeXXUs protocol core: crypto primitives, wire codec, Reed-Solomon, Merkle/PoR, Kademlia.
//! Pure logic — no I/O, compiles to wasm32 unchanged. See docs/adr/*.md for decisions.

pub mod chunk;
pub mod error;
pub mod keys;
pub mod merkle;
pub mod rs;
pub mod types;
pub mod wire;
