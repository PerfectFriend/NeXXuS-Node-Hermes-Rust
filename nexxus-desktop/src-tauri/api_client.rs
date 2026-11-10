//! WebSocket JSON-RPC клиент для локального API nexxusd (порт 4010).
//!
//! API требует токен-аутентификации: первый запрос на соединении —
//! `auth` с токеном из `~/.nexxus/api.token` (или `NEXXUS_API_TOKEN_FILE`),
//! затем на том же соединении — сам метод. Без токена доступен только `ping`.
#![allow(dead_code)]

use futures_util::{SinkExt, StreamExt};
use serde_json::{json, Value};
use tokio_tungstenite::connect_async;
use url::Url;

/// Путь к файлу токена API ноды.
pub fn api_token_path() -> std::path::PathBuf {
    if let Ok(p) = std::env::var("NEXXUS_API_TOKEN_FILE") {
        if !p.is_empty() {
            return std::path::PathBuf::from(p);
        }
    }
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
    std::path::PathBuf::from(home).join(".nexxus").join("api.token")
}

/// Читает токен API ноды. `None`, если файла нет или он пуст.
pub fn read_api_token() -> Option<String> {
    let content = std::fs::read_to_string(api_token_path()).ok()?;
    let token = content.trim().to_string();
    if token.is_empty() {
        None
    } else {
        Some(token)
    }
}

/// Проверяет, доступен ли TCP порт API (адрес из node.conf).
pub async fn api_port_open() -> bool {
    tokio::net::TcpStream::connect(crate::guardian::api_addr())
        .await
        .is_ok()
}

/// Отправляет один JSON-RPC фрейм и читает один ответ (с таймаутом).
async fn send_and_recv(
    sender: &mut futures_util::stream::SplitSink<
        tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>,
        tokio_tungstenite::tungstenite::Message,
    >,
    receiver: &mut futures_util::stream::SplitStream<
        tokio_tungstenite::WebSocketStream<tokio_tungstenite::MaybeTlsStream<tokio::net::TcpStream>>,
    >,
    request: Value,
) -> Result<Value, String> {
    sender
        .send(request.to_string().into())
        .await
        .map_err(|e| format!("WebSocket send failed: {e}"))?;
    match tokio::time::timeout(std::time::Duration::from_secs(5), receiver.next()).await {
        Ok(Some(Ok(msg))) => {
            let text = msg.to_text().map_err(|e| format!("WebSocket text error: {e}"))?;
            serde_json::from_str(text).map_err(|e| format!("JSON parse error: {e}"))
        }
        Ok(Some(Err(e))) => Err(format!("WebSocket receive error: {e}")),
        Ok(None) => Err("WebSocket connection closed".into()),
        Err(_) => Err("WebSocket timeout".into()),
    }
}

/// Выполняет JSON-RPC запрос к локальному API: сначала `auth`, затем метод.
/// Возвращает ответ метода (объект с `result` или `error`) — как раньше.
pub async fn api_call(method: &str, params: Option<Value>) -> Result<Value, String> {
    let url = Url::parse(&crate::guardian::api_url()).map_err(|e| format!("Неверный URL API: {e}"))?;
    let (ws_stream, _) = connect_async(url).await.map_err(|e| format!("WebSocket connect failed: {e}"))?;
    let (mut sender, mut receiver) = ws_stream.split();

    // --- auth handshake ---
    let token = read_api_token()
        .ok_or_else(|| "API token file missing/empty — restart nexxusd to create ~/.nexxus/api.token".to_string())?;
    let auth_resp = send_and_recv(
        &mut sender,
        &mut receiver,
        json!({"jsonrpc": "2.0", "method": "auth", "params": {"token": token}, "id": 1}),
    )
    .await?;
    if let Some(err) = auth_resp.get("error") {
        if !err.is_null() {
            let _ = sender.close().await;
            return Err(format!("API auth failed: {err}"));
        }
    }

    // --- сам запрос на том же соединении ---
    let resp = send_and_recv(
        &mut sender,
        &mut receiver,
        json!({"jsonrpc": "2.0", "method": method, "params": params, "id": 2}),
    )
    .await;
    let _ = sender.close().await;
    resp
}
