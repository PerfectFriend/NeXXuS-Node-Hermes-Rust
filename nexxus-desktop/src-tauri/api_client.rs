//! WebSocket JSON-RPC клиент для локального API nexxusd (порт 4010).
#![allow(dead_code)]

use futures_util::{SinkExt, StreamExt};
use serde_json::{json, Value};
use tokio_tungstenite::connect_async;
use url::Url;

/// Проверяет, доступен ли TCP порт API.
pub async fn api_port_open() -> bool {
    tokio::net::TcpStream::connect("127.0.0.1:4010").await.is_ok()
}

/// Выполняет JSON-RPC запрос к локальному API.
pub async fn api_call(method: &str, params: Option<Value>) -> Result<Value, String> {
    let url = Url::parse(crate::guardian::API_URL).map_err(|e| format!("Неверный URL API: {e}"))?;
    let (ws_stream, _) = connect_async(url).await.map_err(|e| format!("WebSocket connect failed: {e}"))?;
    let (mut sender, mut receiver) = ws_stream.split();

    let request = json!({
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    });

    sender.send(request.to_string().into()).await.map_err(|e| format!("WebSocket send failed: {e}"))?;

    match tokio::time::timeout(std::time::Duration::from_secs(5), receiver.next()).await {
        Ok(Some(Ok(msg))) => {
            let _ = sender.close().await;
            let text = msg.to_text().map_err(|e| format!("WebSocket text error: {e}"))?;
            let resp: Value = serde_json::from_str(text).map_err(|e| format!("JSON parse error: {e}"))?;
            Ok(resp)
        }
        Ok(Some(Err(e))) => Err(format!("WebSocket receive error: {e}")),
        Ok(None) => Err("WebSocket connection closed".into()),
        Err(_) => Err("WebSocket timeout".into()),
    }
}
