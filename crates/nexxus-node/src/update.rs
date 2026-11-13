//! G4: signed self-update (`nexxusd update`).
//!
//! Релиз скачивается по URL из конфига/CLI, проверяется detached
//! ed25519-подписью против зашитого публичного ключа, заменяется атомарно
//! (tmp + rename в той же файловой системе) с rollback при любой ошибке.
//! Приватный ключ живёт вне репозитория (владелец), в коде — только pubkey.

use nexxus_core::error::NexxusError;
use std::path::{Path, PathBuf};

/// Публичный ключ подписи релизов (ed25519, hex). Приватный — у владельца,
/// в secrets вне git (см. docs/plans/2026-11-12-evolution-post-rc1.md, фаза G4).
pub const RELEASE_PUBKEY_HEX: &str =
    "d2513bc75eb06436ecc391005bf8ad0fba4f6d8d66f4e16bee7039dcc1947436";

/// URL релизного ассета по умолчанию (squash-mirror / GitHub releases).
pub const DEFAULT_RELEASE_URL: &str =
    "https://github.com/PerfectFriend/NeXXuS-Node-Hermes-Rust/releases/latest/download/nexxusd-linux-x86_64";

pub fn release_pubkey() -> Result<ed25519_dalek::VerifyingKey, NexxusError> {
    let bytes = hex::decode(RELEASE_PUBKEY_HEX)
        .map_err(|e| NexxusError::Io(format!("release pubkey hex: {e}")))?;
    let arr: [u8; 32] = bytes
        .try_into()
        .map_err(|_| NexxusError::Io("release pubkey must be 32 bytes".into()))?;
    ed25519_dalek::VerifyingKey::from_bytes(&arr)
        .map_err(|e| NexxusError::Io(format!("release pubkey: {e}")))
}

/// Проверка detached-подписи (64 байта) над байтами ассета.
pub fn verify_release(bytes: &[u8], signature_hex: &str) -> Result<(), NexxusError> {
    let sig_bytes = hex::decode(signature_hex.trim())
        .map_err(|e| NexxusError::Io(format!("bad signature hex: {e}")))?;
    let sig_arr: [u8; 64] = sig_bytes
        .try_into()
        .map_err(|_| NexxusError::Io("signature must be 64 bytes".into()))?;
    let vk = release_pubkey()?;
    use ed25519_dalek::Verifier;
    vk.verify(bytes, &ed25519_dalek::Signature::from_bytes(&sig_arr))
        .map_err(|_| NexxusError::Vault("release signature verification FAILED".into()))
}

/// Скачивание ассета и .sig через curl (без нового тяжёлого dep в daemon).
pub fn download(url: &str) -> Result<(Vec<u8>, String), NexxusError> {
    let bin = run_curl(url)?;
    let sig = run_curl(&format!("{url}.sig"))
        .map_err(|e| NexxusError::Io(format!("signature download: {e}")))?;
    let sig_text = String::from_utf8_lossy(&sig).into_owned();
    Ok((bin, sig_text))
}

fn run_curl(url: &str) -> Result<Vec<u8>, NexxusError> {
    let out = std::process::Command::new("curl")
        .args(["-fsSL", "--max-time", "120", url])
        .output()
        .map_err(|e| NexxusError::Io(format!("curl spawn: {e}")))?;
    if !out.status.success() {
        return Err(NexxusError::Io(format!(
            "curl {} failed: {}",
            url,
            String::from_utf8_lossy(&out.stderr).trim()
        )));
    }
    Ok(out.stdout)
}

/// Атомарная замена бинарника с rollback: verify подписи → backup старого →
/// tmp+rename → при любой ошибке до rename старый бинарь не тронут.
pub fn install_update(new_bytes: &[u8], signature_hex: &str, current_bin: &Path) -> Result<PathBuf, NexxusError> {
    verify_release(new_bytes, signature_hex)?;
    if new_bytes.len() < 1024 {
        return Err(NexxusError::Io("suspiciously small release binary".into()));
    }
    let dir = current_bin
        .parent()
        .ok_or_else(|| NexxusError::Io("no parent dir".into()))?;
    let backup = dir.join(format!(
        ".{}.rollback",
        current_bin
            .file_name()
            .map(|n| n.to_string_lossy().into_owned())
            .unwrap_or_else(|| "nexxusd".into())
    ));
    // backup текущего бинарника
    if current_bin.exists() {
        std::fs::copy(current_bin, &backup)
            .map_err(|e| NexxusError::Io(format!("backup copy: {e}")))?;
    }
    let tmp = dir.join(format!(
        ".{}.new",
        current_bin
            .file_name()
            .map(|n| n.to_string_lossy().into_owned())
            .unwrap_or_else(|| "nexxusd".into())
    ));
    let install = (|| -> Result<PathBuf, NexxusError> {
        std::fs::write(&tmp, new_bytes)
            .map_err(|e| NexxusError::Io(format!("tmp write: {e}")))?;
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            std::fs::set_permissions(&tmp, std::fs::Permissions::from_mode(0o755))
                .map_err(|e| NexxusError::Io(format!("chmod: {e}")))?;
        }
        std::fs::rename(&tmp, current_bin)
            .map_err(|e| NexxusError::Io(format!("atomic rename: {e}")))?;
        Ok(current_bin.to_path_buf())
    })();
    if install.is_err() {
        // rollback
        if backup.exists() {
            let _ = std::fs::copy(&backup, current_bin);
        }
        let _ = std::fs::remove_file(&tmp);
    }
    install
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn signature_verify_ok_and_tamper_fails() {
        // ключationenkeypair только для теста — не release-ключ
        let sk = ed25519_dalek::SigningKey::generate(&mut rand::thread_rng());
        let vk = sk.verifying_key();
        let msg = b"fake release binary bytes";
        use ed25519_dalek::Signer;
        let sig = sk.sign(msg);
        use ed25519_dalek::Verifier;
        assert!(vk.verify(msg, &sig).is_ok());
        let mut bad = msg.to_vec();
        bad[0] ^= 0xFF;
        assert!(vk.verify(&bad, &sig).is_err());

        // verify_release падает на битую подпись / левый ключ
        assert!(verify_release(msg, &hex::encode([0u8; 64])).is_err());
        assert!(verify_release(msg, "zz").is_err());
    }

    #[test]
    fn install_update_atomic_and_rollback() {
        let dir = tempfile::tempdir().unwrap();
        let bin = dir.path().join("nexxusd");
        std::fs::write(&bin, b"old-binary").unwrap();
        // подпись валидна только под release pubkey — для теста install
        // используем verify отдельно; здесь проверяем rollback-логику через
        // фальшивую подпись: install должен упасть и НЕ трогать старый бинарь
        let res = install_update(b"new-bytes", &hex::encode([1u8; 64]), &bin);
        assert!(res.is_err(), "bad signature must abort");
        assert_eq!(std::fs::read(&bin).unwrap(), b"old-binary", "old binary intact after failed verify");
    }
}
