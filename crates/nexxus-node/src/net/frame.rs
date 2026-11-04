//! TCP/onion frame codec: length-delimited wire v3 frames.
//! 4-byte BE length || frame (HEADER_V3_LEN + payload).
//! Generic over any AsyncRead+AsyncWrite stream (TcpStream, arti DataStream).

use nexxus_core::{
    error::NexxusError,
    wire::header::{encode_v3, parse_v3},
    wire::opcode::Opcode,
    wire::payloads::Payload,
};
use tokio::io::{AsyncRead, AsyncReadExt, AsyncWrite, AsyncWriteExt};

const LEN_LEN: usize = 4;

/// Send a payload as a v3 frame. `signature` is the Ed25519 signature over
/// `v3_signing_bytes(opcode, request_id, payload, session_nonce)`; computed
/// by the caller (see `P2pNetwork::send_signed_frame`).
pub async fn send_frame<T: Payload, S: AsyncRead + AsyncWrite + Unpin + Send>(
    stream: &mut S,
    opcode: Opcode,
    request_id: u32,
    payload: &T,
    signature: &[u8; 64],
) -> Result<(), NexxusError> {
    let frame = encode_v3(opcode, request_id, &payload.encode(), signature);
    let mut len_buf = [0u8; LEN_LEN];
    len_buf.copy_from_slice(&(frame.len() as u32).to_be_bytes());
    stream
        .write_all(&len_buf)
        .await
        .map_err(|e| NexxusError::Io(e.to_string()))?;
    stream
        .write_all(&frame)
        .await
        .map_err(|e| NexxusError::Io(e.to_string()))?;
    Ok(())
}

/// Receive one v3 frame. Returns (opcode, request_id, payload_bytes, signature).
pub async fn recv_frame<S: AsyncRead + AsyncWrite + Unpin + Send>(
    stream: &mut S,
) -> Result<(Opcode, u32, Vec<u8>, [u8; 64]), NexxusError> {
    let mut len_buf = [0u8; LEN_LEN];
    stream
        .read_exact(&mut len_buf)
        .await
        .map_err(|e| NexxusError::Io(e.to_string()))?;
    let len = u32::from_be_bytes(len_buf) as usize;
    let mut frame = vec![0u8; len];
    stream
        .read_exact(&mut frame)
        .await
        .map_err(|e| NexxusError::Io(e.to_string()))?;
    let f = parse_v3(&frame).map_err(|e| NexxusError::Io(format!("frame parse: {e}")))?;
    Ok((f.opcode, f.request_id, f.payload, f.signature))
}

/// Sanity: frame must not exceed a reasonable size to bound memory.
pub const MAX_FRAME_LEN: usize = 1 << 22; // 4 MiB

#[cfg(test)]
mod tests {
    use super::*;

    use nexxus_core::wire::payloads::{Ping, Pong};

    #[tokio::test]
    async fn send_recv_roundtrip_loopback() {
        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
        let addr = listener.local_addr().unwrap();

        let handle = tokio::spawn(async move {
            let (mut stream, _) = listener.accept().await.unwrap();
            let (op, rid, payload, sig) = recv_frame(&mut stream).await.unwrap();
            assert_eq!(op, Opcode::Ping);
            assert_eq!(rid, 0xdeadbeef);
            assert_eq!(sig, [0x42u8; 64]);
            let decoded = Ping::decode(&payload).unwrap();
            let _ = decoded;
            let pong = Pong;
            send_frame(&mut stream, Opcode::Pong, rid, &pong, &[0u8; 64]).await.unwrap();
        });

        let mut stream = tokio::net::TcpStream::connect(addr).await.unwrap();
        send_frame(&mut stream, Opcode::Ping, 0xdeadbeef, &Ping, &[0x42u8; 64]).await.unwrap();
        let (op, rid, payload, _sig) = recv_frame(&mut stream).await.unwrap();
        assert_eq!(op, Opcode::Pong);
        assert_eq!(rid, 0xdeadbeef);
        let _ = Pong::decode(&payload).unwrap();
        handle.await.unwrap();
    }
}
