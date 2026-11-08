//! systemd-юнит ноды, которым управляет монитор.
//!
//! Монитор ставится первым и сам создаёт юнит ноды: нода запускается
//! системой как отдельная служба (а не дочерним процессом монитора), поэтому
//! переживает перезапуск монитора и стартует при загрузке ОС.

use crate::node_config::NodeConfig;
use std::path::{Path, PathBuf};
use std::process::Command;

/// Имя юнита ноды.
pub const NODE_UNIT_NAME: &str = "nexxus-node.service";
/// Имя юнита монитора (в нём живёт нода по умолчанию, см. fallback).
pub const MONITOR_UNIT_NAME: &str = "nexxus-monitor.service";

/// Путь к user-юниту ноды.
pub fn node_unit_path() -> PathBuf {
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
    PathBuf::from(home)
        .join(".config")
        .join("systemd")
        .join("user")
        .join(NODE_UNIT_NAME)
}

/// Путь к исполняемому файлу ноды.
pub fn node_binary_path() -> PathBuf {
    PathBuf::from("/home/thomas/build/cache/cargo-target-nexxus/release/nexxusd")
}

/// Путь к хранилищу ноды.
pub fn node_store_path() -> PathBuf {
    PathBuf::from("/home/thomas/.nexxus/store.redb")
}

/// Собирает текст user-юнита ноды из конфигурации.
pub fn render_unit(cfg: &NodeConfig, bin: &Path, store: &Path) -> String {
    let env_lines: String = crate::node_config::to_env(cfg)
        .iter()
        .map(|(k, v)| format!("Environment=\"{k}={v}\"\n"))
        .collect();

    format!(
        "[Unit]\n\
         Description=NeXXus Storage Node (daemon nexxusd)\n\
         After=network-online.target\n\
         Wants=network-online.target\n\
         \n\
         [Service]\n\
         Type=simple\n\
         WorkingDirectory={dir}\n\
         {env_lines}\
         ExecStart={bin} {store}\n\
         Restart=on-failure\n\
         RestartSec=5\n\
         \n\
         [Install]\n\
         WantedBy=default.target\n",
        dir = store
            .parent()
            .map(|p| p.to_string_lossy().into_owned())
            .unwrap_or_else(|| ".".to_string()),
        env_lines = env_lines,
        bin = bin.display(),
        store = store.display(),
    )
}

/// Устанавливает (создаёт/обновляет) user-юнит ноды и перечитывает
/// конфигурацию systemd. Возвращает путь к записанному файлу.
pub fn install_unit(cfg: &NodeConfig) -> Result<PathBuf, String> {
    let path = node_unit_path();
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("Не удалось создать {}: {e}", parent.display()))?;
    }
    let content = render_unit(cfg, &node_binary_path(), &node_store_path());
    std::fs::write(&path, content).map_err(|e| format!("Не удалось записать {}: {e}", path.display()))?;
    daemon_reload()?;
    Ok(path)
}

/// `systemctl --user daemon-reload`.
pub fn daemon_reload() -> Result<(), String> {
    let status = Command::new("systemctl")
        .args(["--user", "daemon-reload"])
        .status()
        .map_err(|e| format!("Не удалось выполнить systemctl: {e}"))?;
    if status.success() {
        Ok(())
    } else {
        Err(format!("systemctl daemon-reload завершился с кодом {}", status.code().unwrap_or(-1)))
    }
}

/// Включает и запускает юнит ноды (`systemctl --user enable --now`).
pub fn enable_and_start() -> Result<(), String> {
    let status = Command::new("systemctl")
        .args(["--user", "enable", "--now", NODE_UNIT_NAME])
        .status()
        .map_err(|e| format!("Не удалось выполнить systemctl: {e}"))?;
    if status.success() {
        Ok(())
    } else {
        Err(format!("systemctl enable --now {} завершился с кодом {}", NODE_UNIT_NAME, status.code().unwrap_or(-1)))
    }
}

/// Останавливает и выключает юнит ноды (`systemctl --user disable --now`).
pub fn disable_and_stop() -> Result<(), String> {
    let status = Command::new("systemctl")
        .args(["--user", "disable", "--now", NODE_UNIT_NAME])
        .status()
        .map_err(|e| format!("Не удалось выполнить systemctl: {e}"))?;
    if status.success() {
        Ok(())
    } else {
        Err(format!("systemctl disable --now {} завершился с кодом {}", NODE_UNIT_NAME, status.code().unwrap_or(-1)))
    }
}

/// Состояние юнита ноды: active / inactive / failed / not-found.
pub fn unit_state() -> String {
    let Ok(out) = Command::new("systemctl")
        .args(["--user", "is-active", NODE_UNIT_NAME])
        .output()
    else {
        return "unknown".into();
    };
    let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
    if text.is_empty() {
        "unknown".into()
    } else {
        text
    }
}

/// Установлен ли юнит ноды.
pub fn is_installed() -> bool {
    node_unit_path().exists()
}

/// Состояние юнита монитора: active / inactive / not-found.
///
/// Нужно, чтобы «полное отключение» понимало: если монитор под systemd,
/// его корректно останавливать через `systemctl --user stop`, а не просто
/// завершать процесс.
pub fn monitor_unit_state() -> String {
    let Ok(out) = Command::new("systemctl")
        .args(["--user", "is-active", MONITOR_UNIT_NAME])
        .output()
    else {
        return "unknown".into();
    };
    let text = String::from_utf8_lossy(&out.stdout).trim().to_string();
    if text.is_empty() {
        "unknown".into()
    } else {
        text
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unit_file_contains_env_and_exec() {
        let cfg = NodeConfig {
            listen: "127.0.0.1:4001".into(),
            api: "127.0.0.1:4010".into(),
            auditors: vec!["aa".into(), "bb".into()],
            threshold: 1,
            tor: false,
            ..NodeConfig::default()
        };
        let unit = render_unit(&cfg, &node_binary_path(), &node_store_path());

        assert!(unit.contains("ExecStart=/home/thomas/build/cache/cargo-target-nexxus/release/nexxusd /home/thomas/.nexxus/store.redb"));
        assert!(unit.contains("Environment=\"NEXXUS_LISTEN=127.0.0.1:4001\""));
        assert!(unit.contains("Environment=\"NEXXUS_API_ADDR=127.0.0.1:4010\""));
        assert!(unit.contains("Environment=\"NEXXUS_AUDITORS=aa,bb\""));
        assert!(unit.contains("Environment=\"NEXXUS_THRESHOLD=1\""));
        assert!(unit.contains("Environment=\"NEXXUS_TOR=0\""));
        assert!(unit.contains("Restart=on-failure"));
        assert!(unit.contains("WantedBy=default.target"));
    }

    #[test]
    fn unit_contains_every_node_env_var() {
        let unit = render_unit(&NodeConfig::default(), &node_binary_path(), &node_store_path());
        for key in [
            "NEXXUS_LISTEN",
            "NEXXUS_API_ADDR",
            "NEXXUS_AUDITORS",
            "NEXXUS_THRESHOLD",
            "NEXXUS_EPOCH_SECS",
            "NEXXUS_TOR",
            "NEXXUS_LOG",
            "NEXXUS_SPECIFICATION_V",
        ] {
            assert!(unit.contains(&format!("Environment=\"{key}=")), "нет {key} в юните");
        }
    }
}
