//! Клиент локального WebSocket API nexxusd.
//! Общается с nexxusd через JSON-RPC 2.0 на ws://127.0.0.1:4010.

use serde_json::Value;
use std::time::Duration;
use futures_util::{SinkExt, StreamExt};
use tokio_tungstenite::connect_async;
use tungstenite::Message;
use url::Url;

/// Клиент для взаимодействия с локальным API nexxusd.
pub struct NexxusApiClient {
    url: String,
}

impl NexxusApiClient {
    pub fn new(url: &str) -> Self {
        Self { url: url.into() }
    }

    /// Выполнить JSON-RPC запрос к nexxusd.
    /// Открывает новое WebSocket соединение на каждый запрос (простая модель для MVP).
    pub async fn request(&self, method: &str, params: Value) -> Result<Value, String> {
        let url = Url::parse(&self.url).map_err(|e| e.to_string())?;
        let (ws_stream, _) = connect_async(url)
            .await
            .map_err(|e| format!("WebSocket connect failed: {e}"))?;

        let (mut sender, mut receiver) = ws_stream.split();

        let id = 1u64;
        let request = serde_json::json!({
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": id,
        });

        sender
            .send(Message::Text(request.to_string()))
            .await
            .map_err(|e| format!("WebSocket send failed: {e}"))?;

        // Ждём ответ с таймаутом 5 секунд
        let msg = tokio::time::timeout(Duration::from_secs(5), receiver.next())
            .await
            .map_err(|_| "WebSocket response timeout".to_string())?
            .ok_or("WebSocket stream ended")?
            .map_err(|e| format!("WebSocket receive failed: {e}"))?;

        match msg {
            Message::Text(text) => {
                let response: Value = serde_json::from_str(&text)
                    .map_err(|e| format!("Invalid JSON response: {e}"))?;
                if let Some(error) = response.get("error") {
                    Err(format!("API error: {error}"))
                } else {
                    Ok(response
                        .get("result")
                        .cloned()
                        .unwrap_or(serde_json::Value::Null))
                }
            }
            _ => Err("Unexpected WebSocket message type".to_string()),
        }
    }
}

impl Default for NexxusApiClient {
    fn default() -> Self {
        Self::new("ws://127.0.0.1:4010")
    }
}
