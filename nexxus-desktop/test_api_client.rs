// Тест NexxusApiClient — прямое подключение к локальному API nexxusd
// Проверяет, что WebSocket JSON-RPC клиент реально получает данные от nexxusd

use serde_json::Value;
use std::time::Duration;
use futures_util::{SinkExt, StreamExt};
use tokio_tungstenite::connect_async;
use tungstenite::Message;
use url::Url;

struct NexxusApiClient {
    url: String,
}

impl NexxusApiClient {
    fn new(url: &str) -> Self {
        Self { url: url.into() }
    }

    /// Токен API из ~/.nexxus/api.token (или NEXXUS_API_TOKEN_FILE).
    fn read_token() -> Result<String, String> {
        let path = std::env::var("NEXXUS_API_TOKEN_FILE").ok().filter(|p| !p.is_empty())
            .map(std::path::PathBuf::from)
            .unwrap_or_else(|| {
                let home = std::env::var("HOME").unwrap_or_else(|_| ".".into());
                std::path::PathBuf::from(home).join(".nexxus").join("api.token")
            });
        let content = std::fs::read_to_string(&path)
            .map_err(|e| format!("read {}: {e}", path.display()))?;
        let token = content.trim().to_string();
        if token.is_empty() {
            Err("API token file is empty".into())
        } else {
            Ok(token)
        }
    }

    async fn request(&self, method: &str, params: Value) -> Result<Value, String> {
        let url = Url::parse(&self.url).map_err(|e| e.to_string())?;
        let (ws_stream, _) = connect_async(url)
            .await
            .map_err(|e| format!("WebSocket connect failed: {e}"))?;

        let (mut sender, mut receiver) = ws_stream.split();

        // --- auth handshake: первый фрейм на соединении ---
        let token = Self::read_token()?;
        let auth = serde_json::json!({
            "jsonrpc": "2.0",
            "method": "auth",
            "params": {"token": token},
            "id": 1u64,
        });
        sender
            .send(Message::Text(auth.to_string()))
            .await
            .map_err(|e| format!("WebSocket send auth failed: {e}"))?;
        let msg = tokio::time::timeout(Duration::from_secs(5), receiver.next())
            .await
            .map_err(|_| "Auth response timeout".to_string())?
            .ok_or("WebSocket stream ended during auth")?
            .map_err(|e| format!("WebSocket auth receive failed: {e}"))?;
        if let Message::Text(text) = msg {
            let v: Value = serde_json::from_str(&text).map_err(|e| format!("Invalid auth JSON: {e}"))?;
            if let Some(error) = v.get("error") {
                if !error.is_null() {
                    return Err(format!("auth failed: {error}"));
                }
            }
        }

        let id = 2u64;
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

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    println!("=== Тест NexxusApiClient ===");
    println!("Подключение к ws://127.0.0.1:4010 ...");

    let client = NexxusApiClient::new("ws://127.0.0.1:4010");

    // Тест 1: node_status
    println!("\n1. node_status...");
    let result = client.request("node_status", serde_json::json!({})).await;
    match result {
        Ok(v) => {
            let node_id = v.get("node_id").and_then(|v| v.as_str()).unwrap_or("?");
            let uptime = v.get("uptime_ms").and_then(|v| v.as_u64()).unwrap_or(0);
            let peers = v.get("peer_count").and_then(|v| v.as_u64()).unwrap_or(0);
            let bound = v.get("bound_addr").and_then(|v| v.as_str()).unwrap_or("?");
            println!("   ✅ OK: node_id={} uptime={}ms peers={} bound={}", &node_id[..16.min(node_id.len())], uptime, peers, bound);
        }
        Err(e) => println!("   ❌ Ошибка: {e}"),
    }

    // Тест 2: node_peers
    println!("\n2. node_peers...");
    let result = client.request("node_peers", serde_json::json!({})).await;
    match result {
        Ok(v) => {
            let peers = v.get("peers").and_then(|v| v.as_array()).map(|a| a.len()).unwrap_or(0);
            println!("   ✅ OK: {peers} пиров");
        }
        Err(e) => println!("   ❌ Ошибка: {e}"),
    }

    // Тест 3: node_chunks
    println!("\n3. node_chunks...");
    let result = client.request("node_chunks", serde_json::json!({})).await;
    match result {
        Ok(v) => println!("   ✅ OK: {v}"),
        Err(e) => println!("   ⚠️  (ожидаемо для пустого хранилища): {e}"),
    }

    // Тест 4: node_epoch
    println!("\n4. node_epoch...");
    let result = client.request("node_epoch", serde_json::json!({})).await;
    match result {
        Ok(v) => println!("   ✅ OK: {v}"),
        Err(e) => println!("   ⚠️ : {e}"),
    }

    // Тест 5: node_tor
    println!("\n5. node_tor...");
    let result = client.request("node_tor", serde_json::json!({})).await;
    match result {
        Ok(v) => println!("   ✅ OK: {v}"),
        Err(e) => println!("   ⚠️ : {e}"),
    }

    println!("\n=== Тест завершён ===");
    Ok(())
}
