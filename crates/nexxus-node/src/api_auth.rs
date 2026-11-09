//! Token-аутентификация локального WebSocket API.
//!
//! До этой фазы любой локальный процесс мог подключиться к
//! ws://127.0.0.1:4010 и читать/писать хранилище. Теперь первый
//! запрос на соединении обязан быть `auth` с токеном из
//! `~/.nexxus/api.token` (0600); без успешного auth доступен только
//! `ping`. Fail-closed: если токен не удалось загрузить/создать —
//! API не стартует.

use rand::RngCore;
use std::fs;
use std::io;
use std::path::PathBuf;

/// Путь к файлу токена: env `NEXXUS_API_TOKEN_FILE` или `~/.nexxus/api.token`.
pub fn token_file_path() -> PathBuf {
    if let Ok(p) = std::env::var("NEXXUS_API_TOKEN_FILE") {
        if !p.is_empty() {
            return PathBuf::from(p);
        }
    }
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
    PathBuf::from(home).join(".nexxus").join("api.token")
}

/// Генерирует новый токен: 32 случайных байта в hex (64 символа).
pub fn generate_token() -> String {
    let mut bytes = [0u8; 32];
    rand::thread_rng().fill_bytes(&mut bytes);
    hex::encode(bytes)
}

/// Токен валиден: 64 hex-символа.
pub fn is_valid_token(token: &str) -> bool {
    token.len() == 64 && token.bytes().all(|b| b.is_ascii_hexdigit())
}

/// Читает токен из файла; `Ok(None)` если файла нет.
pub fn load_token(path: &PathBuf) -> io::Result<Option<String>> {
    match fs::read_to_string(path) {
        Ok(content) => {
            let token = content.trim().to_string();
            if token.is_empty() {
                Ok(None)
            } else if is_valid_token(&token) {
                Ok(Some(token))
            } else {
                Err(io::Error::new(
                    io::ErrorKind::InvalidData,
                    format!("файл токена {} повреждён (ожидалось 64 hex-символа)", path.display()),
                ))
            }
        }
        Err(e) if e.kind() == io::ErrorKind::NotFound => Ok(None),
        Err(e) => Err(e),
    }
}

/// Записывает токен с правами 0600 (только владелец).
fn write_token_private(path: &PathBuf, token: &str) -> io::Result<()> {
    use std::os::unix::fs::OpenOptionsExt;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let mut file = fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .mode(0o600)
        .open(path)?;
    use std::io::Write;
    file.write_all(token.as_bytes())?;
    file.write_all(b"\n")?;
    Ok(())
}

/// Загружает существующий токен или создаёт новый (и сохраняет 0600).
pub fn load_or_create_token(path: &PathBuf) -> io::Result<String> {
    if let Some(token) = load_token(path)? {
        return Ok(token);
    }
    let token = generate_token();
    write_token_private(path, &token)?;
    Ok(token)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmp_path(tag: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("nexxus-api-auth-test-{tag}-{}", std::process::id()));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir.join("api.token")
    }

    #[test]
    fn generate_token_is_64_hex_and_unique() {
        let a = generate_token();
        let b = generate_token();
        assert!(is_valid_token(&a));
        assert!(is_valid_token(&b));
        assert_ne!(a, b);
        assert!(!is_valid_token("xyz"));
        assert!(!is_valid_token(&"ab".repeat(33)));
    }

    #[test]
    fn load_or_create_is_idempotent_and_private() {
        let path = tmp_path("idem");
        let t1 = load_or_create_token(&path).unwrap();
        let t2 = load_or_create_token(&path).unwrap();
        assert_eq!(t1, t2);
        assert_eq!(load_token(&path).unwrap(), Some(t1.clone()));

        // Права файла — только владелец.
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mode = fs::metadata(&path).unwrap().permissions().mode() & 0o777;
            assert_eq!(mode, 0o600, "токен должен лежать с правами 0600, а не {mode:o}");
        }

        let _ = fs::remove_dir_all(path.parent().unwrap());
    }

    #[test]
    fn missing_file_yields_none() {
        let path = tmp_path("missing");
        assert_eq!(load_token(&path).unwrap(), None);
    }

    #[test]
    fn corrupt_token_is_an_error_not_silent_overwrite() {
        let path = tmp_path("corrupt");
        fs::write(&path, "not-a-token").unwrap();
        assert!(load_token(&path).is_err());
        let _ = fs::remove_dir_all(path.parent().unwrap());
    }
}
