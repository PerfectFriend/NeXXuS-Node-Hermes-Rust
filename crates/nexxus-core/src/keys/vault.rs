//! Зашифрованный vault для seed/конфигов с PIN и duress-PIN.
//!
//! Вендорено из `crates/bip39-auth-rs/src/storage.rs` репозитория
//! PerfectFriend/BIP39-Onboarding-pipeline (Apache-2.0) — формат
//! `EncryptedVault` JSON идентичен, чтобы существующие vault'ы SDK
//! открывались и здесь. Изменения относительно оригинала:
//! - ошибка через `NexxusError::Vault` вместо String;
//! - `check_pin` возвращает `PinCheck` (нужен для экспоненциального
//!   кулдауна в panic-модуле, спецификация §5), decrypt по-прежнему
//!   сам детектит duress;
//! - PBKDF2 поднят до 600 000 итераций (OWASP 2023 для HMAC-SHA256),
//!   формат vault от этого не меняется — меняется только стоимость подбора.

use aes_gcm::aead::{Aead, KeyInit};
use aes_gcm::{Aes256Gcm, Nonce};
use pbkdf2::pbkdf2_hmac;
use rand::Rng;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use zeroize::Zeroize;

use crate::error::NexxusError;

/// Итерации PBKDF2 для НОВЫХ vault (OWASP 2023 для HMAC-SHA256).
pub const PBKDF2_ROUNDS: u32 = 600_000;
/// Итерации для чтения vault без поля `kdf_rounds` — как в BIP39-ABOARD-SDK.
pub const PBKDF2_ROUNDS_SDK_DEFAULT: u32 = 100_000;
const SALT_LEN: usize = 16;
const NONCE_LEN: usize = 12;

/// Самодостаточный JSON-vault: формат совместим с BIP39-ABOARD-SDK.
///
/// Поле `kdf_rounds` добавлено нами: в нём пишем 600 000 для новых
/// vault; если поле отсутствует (vault создан SDK) — читаем со 100 000,
/// иначе старые vault'ы SDK не открылись бы.
#[derive(Debug, Serialize, Deserialize)]
pub struct EncryptedVault {
    pub ciphertext_hex: String,
    pub iv_hex: String,
    pub salt_hex: String,
    pub pin_hash_hex: String,
    pub duress_hash_hex: Option<String>,
    pub created_at: u64,
    #[serde(default = "default_kdf_rounds")]
    pub kdf_rounds: u32,
}

fn default_kdf_rounds() -> u32 {
    PBKDF2_ROUNDS_SDK_DEFAULT
}

/// Результат проверки PIN без попытки расшифровки.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PinCheck {
    /// Основной PIN верен.
    Ok,
    /// Введён duress-PIN: паника, содержимое не выдаётся.
    Duress,
    /// Неверный PIN.
    Wrong,
}

/// Результат расшифровки vault.
#[derive(Debug)]
pub struct DecryptResult {
    pub decrypted_bytes: Vec<u8>,
    pub is_duress: bool,
}

/// SHA-256(PIN || salt) в hex — формат хеша как в SDK.
pub fn hash_pin(pin: &str, salt: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(pin.as_bytes());
    hasher.update(salt);
    hex::encode(hasher.finalize())
}

/// 256-битный ключ из PIN через PBKDF2-HMAC-SHA256 с заданным числом раундов.
fn derive_key(pin: &str, salt: &[u8], rounds: u32) -> [u8; 32] {
    let mut key = [0u8; 32];
    pbkdf2_hmac::<Sha256>(pin.as_bytes(), salt, rounds, &mut key);
    key
}

/// Шифрует payload в самодостаточный JSON vault (с duress-PIN опционально).
pub fn encrypt_vault_payload(
    payload: &[u8],
    primary_pin: &str,
    duress_pin: Option<&str>,
) -> Result<String, NexxusError> {
    encrypt_vault_payload_rounds(payload, primary_pin, duress_pin, PBKDF2_ROUNDS)
}

/// VLT-02: то же, что `encrypt_vault_payload`, но с явным числом раундов KDF.
/// Используется для миграции старых (SDK, 100k) vault на 600k и в тестах —
/// в обычном коде всегда вызывайте `encrypt_vault_payload`.
pub fn encrypt_vault_payload_rounds(
    payload: &[u8],
    primary_pin: &str,
    duress_pin: Option<&str>,
    rounds: u32,
) -> Result<String, NexxusError> {
    let mut rng = rand::thread_rng();

    let mut salt = [0u8; SALT_LEN];
    let mut nonce_bytes = [0u8; NONCE_LEN];
    rng.fill(&mut salt[..]);
    rng.fill(&mut nonce_bytes[..]);

    let mut key = derive_key(primary_pin, &salt, rounds);
    let cipher = Aes256Gcm::new_from_slice(&key)
        .map_err(|e| NexxusError::Vault(format!("инициализация шифра: {e}")))?;

    let nonce = Nonce::from_slice(&nonce_bytes);
    let ciphertext = cipher
        .encrypt(nonce, payload)
        .map_err(|e| NexxusError::Vault(format!("шифрование: {e}")))?;
    key.zeroize();

    let vault = EncryptedVault {
        ciphertext_hex: hex::encode(ciphertext),
        iv_hex: hex::encode(nonce_bytes),
        salt_hex: hex::encode(salt),
        pin_hash_hex: hash_pin(primary_pin, &salt),
        duress_hash_hex: duress_pin.map(|dp| hash_pin(dp, &salt)),
        created_at: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_secs(),
        kdf_rounds: rounds,
    };

    serde_json::to_string(&vault).map_err(|e| NexxusError::Vault(format!("сериализация: {e}")))
}

/// Проверяет PIN без расшифровки (для кулдауна и duress-детекта).
pub fn check_pin(vault_json: &str, entered_pin: &str) -> Result<PinCheck, NexxusError> {
    let vault: EncryptedVault = serde_json::from_str(vault_json)
        .map_err(|e| NexxusError::Vault(format!("невалидный JSON vault: {e}")))?;
    let salt = hex::decode(&vault.salt_hex)
        .map_err(|e| NexxusError::Vault(format!("невалидный salt: {e}")))?;
    let entered_hash = hash_pin(entered_pin, &salt);

    if let Some(ref duress_hash) = vault.duress_hash_hex {
        if &entered_hash == duress_hash {
            return Ok(PinCheck::Duress);
        }
    }
    if entered_hash == vault.pin_hash_hex {
        Ok(PinCheck::Ok)
    } else {
        Ok(PinCheck::Wrong)
    }
}

/// Расшифровывает vault; duress-PIN возвращает `is_duress: true` и пустой payload.
pub fn decrypt_vault_payload(vault_json: &str, entered_pin: &str) -> Result<DecryptResult, NexxusError> {
    let vault: EncryptedVault = serde_json::from_str(vault_json)
        .map_err(|e| NexxusError::Vault(format!("невалидный JSON vault: {e}")))?;

    let salt = hex::decode(&vault.salt_hex)
        .map_err(|e| NexxusError::Vault(format!("невалидный salt: {e}")))?;
    let iv_bytes = hex::decode(&vault.iv_hex)
        .map_err(|e| NexxusError::Vault(format!("невалидный IV: {e}")))?;
    let ciphertext = hex::decode(&vault.ciphertext_hex)
        .map_err(|e| NexxusError::Vault(format!("невалидный ciphertext: {e}")))?;

    let entered_hash = hash_pin(entered_pin, &salt);

    if let Some(ref duress_hash) = vault.duress_hash_hex {
        if &entered_hash == duress_hash {
            return Ok(DecryptResult {
                decrypted_bytes: Vec::new(),
                is_duress: true,
            });
        }
    }
    if entered_hash != vault.pin_hash_hex {
        return Err(NexxusError::Vault("неверный PIN".into()));
    }

    let mut key = derive_key(entered_pin, &salt, vault.kdf_rounds);
    let cipher = Aes256Gcm::new_from_slice(&key)
        .map_err(|e| NexxusError::Vault(format!("инициализация шифра: {e}")))?;
    let nonce = Nonce::from_slice(&iv_bytes);
    let plaintext = cipher
        .decrypt(nonce, ciphertext.as_ref())
        .map_err(|_| NexxusError::AeadAuthFailed)?;
    key.zeroize();

    Ok(DecryptResult {
        decrypted_bytes: plaintext,
        is_duress: false,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn vault_roundtrip() {
        let payload = b"nexxus seed phrase secret";
        let vault = encrypt_vault_payload(payload, "1234", Some("9999")).unwrap();
        let res = decrypt_vault_payload(&vault, "1234").unwrap();
        assert!(!res.is_duress);
        assert_eq!(res.decrypted_bytes, payload);
    }

    #[test]
    fn duress_pin_detected_without_decrypt() {
        let vault = encrypt_vault_payload(b"secret", "1111", Some("0000")).unwrap();
        let res = decrypt_vault_payload(&vault, "0000").unwrap();
        assert!(res.is_duress);
        assert!(res.decrypted_bytes.is_empty());
        assert_eq!(check_pin(&vault, "0000").unwrap(), PinCheck::Duress);
    }

    #[test]
    fn wrong_pin_rejected() {
        let vault = encrypt_vault_payload(b"secret", "1111", None).unwrap();
        assert!(decrypt_vault_payload(&vault, "2222").is_err());
        assert_eq!(check_pin(&vault, "2222").unwrap(), PinCheck::Wrong);
        assert_eq!(check_pin(&vault, "1111").unwrap(), PinCheck::Ok);
    }

    #[test]
    fn tampered_ciphertext_fails() {
        let vault = encrypt_vault_payload(b"secret", "1111", None).unwrap();
        let mut v: serde_json::Value = serde_json::from_str(&vault).unwrap();
        let ct = v["ciphertext_hex"].as_str().unwrap().to_string();
        let mut tampered = ct.clone();
        tampered.replace_range(0..2, if &ct[0..2] == "00" { "11" } else { "00" });
        v["ciphertext_hex"] = serde_json::Value::String(tampered);
        let broken = serde_json::to_string(&v).unwrap();
        assert!(decrypt_vault_payload(&broken, "1111").is_err());
    }

    #[test]
    fn sdk_vault_without_kdf_rounds_opens_with_100k() {
        // Имитируем vault, созданный BIP39-ABOARD-SDK: поля те же,
        // kdf_rounds отсутствует, ключ выведен со 100 000 раундов.
        let payload = b"sdk legacy vault";
        let pin = "4321";
        let salt = [7u8; SALT_LEN];
        let nonce_bytes = [9u8; NONCE_LEN];
        let mut key = derive_key(pin, &salt, PBKDF2_ROUNDS_SDK_DEFAULT);
        let cipher = Aes256Gcm::new_from_slice(&key).unwrap();
        let ct = cipher
            .encrypt(Nonce::from_slice(&nonce_bytes), payload.as_ref())
            .unwrap();
        key.zeroize();
        let vault_json = serde_json::json!({
            "ciphertext_hex": hex::encode(ct),
            "iv_hex": hex::encode(nonce_bytes),
            "salt_hex": hex::encode(salt),
            "pin_hash_hex": hash_pin(pin, &salt),
            "duress_hash_hex": null,
            "created_at": 0u64,
        })
        .to_string();
        // Поля kdf_rounds нет — десериализация подставит дефолт 100k.
        let res = decrypt_vault_payload(&vault_json, pin).unwrap();
        assert!(!res.is_duress);
        assert_eq!(res.decrypted_bytes, payload);
    }

    #[test]
    fn vault_format_compatible_with_sdk_fields() {
        // Без duress-PIN поле есть, но null (как в SDK).
        let vault = encrypt_vault_payload(b"x", "1", None).unwrap();
        let v: serde_json::Value = serde_json::from_str(&vault).unwrap();
        for field in ["ciphertext_hex", "iv_hex", "salt_hex", "pin_hash_hex", "created_at"] {
            assert!(v.get(field).is_some(), "нет поля {field}");
        }
        assert!(v["duress_hash_hex"].is_null());

        // С duress-PIN поле заполнено.
        let vault2 = encrypt_vault_payload(b"x", "1", Some("2")).unwrap();
        let v2: serde_json::Value = serde_json::from_str(&vault2).unwrap();
        assert!(v2["duress_hash_hex"].is_string());
    }
}
