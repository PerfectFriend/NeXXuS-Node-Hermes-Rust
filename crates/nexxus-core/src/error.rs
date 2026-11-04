//! Crate-wide error type.

use thiserror::Error;

#[derive(Debug, Error)]
pub enum NexxusError {
    #[error("wire: truncated frame at offset {offset} (need {need})")]
    WireTruncated { offset: usize, need: usize },

    #[error("wire: invalid magic bytes")]
    WireMagic,

    #[error("wire: checksum mismatch")]
    WireChecksum,

    #[error("wire: unsupported version 0x{0:02x}")]
    VersionMismatch(u8),

    #[error("wire: unauthorized (bad or missing signature)")]
    Unauthorized,

    #[error("wire: unknown opcode 0x{0:02x}")]
    UnknownOpcode(u8),

    #[error("reed-solomon: insufficient shards (need {need}, got {got})")]
    InsufficientShards { need: usize, got: usize },

    #[error("reed-solomon: singular matrix / erasure pattern unrecoverable")]
    SingularMatrix,

    #[error("aead: authentication tag check failed")]
    AeadAuthFailed,

    #[error("io: {0}")]
    Io(String),
}

impl From<std::io::Error> for NexxusError {
    fn from(e: std::io::Error) -> Self {
        NexxusError::Io(e.to_string())
    }
}
