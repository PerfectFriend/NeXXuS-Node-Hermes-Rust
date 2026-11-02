//! NeXXUs protocol core: crypto primitives, wire codec, Reed-Solomon, Merkle/PoR, Kademlia.
//! Pure logic — no I/O, compiles to wasm32 unchanged. See docs/adr/*.md for decisions.

pub mod error;
pub mod types;
