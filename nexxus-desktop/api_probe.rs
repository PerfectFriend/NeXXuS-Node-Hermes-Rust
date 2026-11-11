//! api_probe <method> [params-json]
//!
//! Доказательный прогон: ходит в локальный WS API ноды ровно тем же путём,
//! что и команда монитора `node_api_cmd` (авторизация токеном из
//! ~/.nexxus/api.token, адрес из NEXXUS_API_ADDR или поля `api` в node.conf).
//! Печатает сырой result или ошибку — чтобы было видно, что кнопка реально
//! дошла до ноды и получила настоящий ответ.

use futures_util::{SinkExt, StreamExt};
use serde_json::Value;
use std::time::Duration;
use tokio_tungstenite::connect_async;
use tungstenite::Message;
use url::Url;

fn api_url() -> String {
    if let Ok(addr) = std::env::var("NEXXUS_API_ADDR") {
        if !addr.is_empty() {
            return format!("ws://{addr}");
        }
    }
    // fallback: поле api= из ~/.nexxus/node.conf
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".into());
    let conf = std::path::PathBuf::from(home).join(".nexxus").join("node.conf");
    if let Ok(text) = std::fs::read_to_string(&conf) {
        for line in text.lines() {
            if let Some(v) = line.strip_prefix("api=") {
                return format!("ws://{v}");
            }
        }
    }
    "ws://127.0.0.1:4010".to_string()
}

fn read_token() -> Result<String, String> {
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".into());
    let path = std::path::PathBuf::from(home).join(".nexxus").join("api.token");
    let token = std::fs::read_to_string(&path)
        .map_err(|e| format!("read {}: {e}", path.display()))?
        .trim()
        .to_string();
    if token.is_empty() {
        Err("empty token".into())
    } else {
        Ok(token)
    }
}

async fn request(url: &str, method: &str, params: Value) -> Result<Value, String> {
    let (ws, _) = connect_async(Url::parse(url).map_err(|e| e.to_string())?)
        .await
        .map_err(|e| format!("connect: {e}"))?;
    let (mut tx, mut rx) = ws.split();
    let auth = serde_json::json!({"jsonrpc":"2.0","method":"auth","params":{"token":read_token()?},"id":1});
    tx.send(Message::Text(auth.to_string())).await.map_err(|e| e.to_string())?;
    let m = tokio::time::timeout(Duration::from_secs(5), rx.next())
        .await.map_err(|_| "auth timeout".to_string())?
        .ok_or("eof")? .map_err(|e| e.to_string())?;
    if let Message::Text(t) = m {
        let v: Value = serde_json::from_str(&t).map_err(|e| e.to_string())?;
        if v.get("error").map(|e| !e.is_null()).unwrap_or(false) {
            return Err(format!("auth: {}", v["error"]));
        }
    }
    let req = serde_json::json!({"jsonrpc":"2.0","method":method,"params":params,"id":2});
    tx.send(Message::Text(req.to_string())).await.map_err(|e| e.to_string())?;
    let m = tokio::time::timeout(Duration::from_secs(8), rx.next())
        .await.map_err(|_| "response timeout".to_string())?
        .ok_or("eof")? .map_err(|e| e.to_string())?;
    match m {
        Message::Text(t) => {
            let v: Value = serde_json::from_str(&t).map_err(|e| e.to_string())?;
            if v.get("error").map(|e| !e.is_null()).unwrap_or(false) {
                Err(format!("{}", v["error"]))
            } else {
                Ok(v.get("result").cloned().unwrap_or(Value::Null))
            }
        }
        _ => Err("non-text frame".into()),
    }
}

#[tokio::main]
async fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        eprintln!("usage: api_probe <method> [params-json]");
        std::process::exit(2);
    }
    let method = &args[1];
    let params: Value = match args.get(2) {
        Some(s) => serde_json::from_str(s).unwrap_or_else(|e| {
            eprintln!("bad params json: {e}");
            std::process::exit(2);
        }),
        None => Value::Null,
    };
    let url = api_url();
    match request(&url, method, params).await {
        Ok(v) => println!("OK {}", serde_json::to_string_pretty(&v).unwrap()),
        Err(e) => {
            println!("ERR {e}");
            std::process::exit(1);
        }
    }
}
