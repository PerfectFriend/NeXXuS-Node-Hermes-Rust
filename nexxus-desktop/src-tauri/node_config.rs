//! Конфигурация ноды NeXXus, управляемая монитором.
//!
//! Файл `~/.nexxus/node.conf` — простой формат `key=value` (по строке на
//! параметр). Монитор читает его при старте, применяет значения к окружению
//! запускаемого `nexxusd` и позволяет менять их из дашборда.
//!
//! Все значения сериализуются в переменные окружения ноды:
//! NEXXUS_LISTEN, NEXXUS_API_ADDR, NEXXUS_AUDITORS, NEXXUS_THRESHOLD,
//! NEXXUS_EPOCH_SECS, NEXXUS_TOR, NEXXUS_LOG, NEXXUS_SPECIFICATION_V.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;

/// Дефолтные значения совпадают с дефолтами ноды (crates/nexxus-node/src/main.rs).
pub const DEFAULT_LISTEN: &str = "127.0.0.1:4001";
pub const DEFAULT_API: &str = "127.0.0.1:4010";
pub const DEFAULT_EPOCH_SECS: u64 = 300;
pub const DEFAULT_SPEC_VERSION: &str = "v2";

fn default_auto_backup_hours() -> u64 {
    24
}
fn default_auto_backup_keep() -> usize {
    5
}
fn default_por_interval_hours() -> u64 {
    24
}

/// Конфигурация ноды.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct NodeConfig {
    /// Адрес P2P-слушателя (NEXXUS_LISTEN).
    pub listen: String,
    /// Адрес локального WebSocket API (NEXXUS_API_ADDR).
    pub api: String,
    /// Комитет аудиторов — hex ed25519-ключи через запятую (NEXXUS_AUDITORS).
    pub auditors: Vec<String>,
    /// Порог кворума M-of-N (NEXXUS_THRESHOLD).
    pub threshold: usize,
    /// Длительность эпохи в секундах (NEXXUS_EPOCH_SECS).
    pub epoch_secs: u64,
    /// Включён ли Tor (NEXXUS_TOR=0 выключает).
    pub tor: bool,
    /// Автобэкап: интервал в часах (0 = выключен, по умолчанию 24).
    #[serde(default = "default_auto_backup_hours")]
    pub auto_backup_hours: u64,
    /// Автобэкап: сколько последних бэкапов хранить (ротация, по умолчанию 5).
    #[serde(default = "default_auto_backup_keep")]
    pub auto_backup_keep: usize,
    /// E2: плановый PoR (proof-of-retrievability) каждые N часов (0 = выкл, дефолт 24).
    #[serde(default = "default_por_interval_hours")]
    pub por_interval_hours: u64,
    /// Версия спецификации протокола (NEXXUS_SPECIFICATION_V).
    pub spec_version: String,
    /// Путь файла лога ноды (NEXXUS_LOG).
    pub log_path: String,
}

impl Default for NodeConfig {
    fn default() -> Self {
        Self {
            listen: DEFAULT_LISTEN.to_string(),
            api: DEFAULT_API.to_string(),
            auditors: Vec::new(),
            threshold: 0,
            epoch_secs: DEFAULT_EPOCH_SECS,
            tor: true,
            auto_backup_hours: default_auto_backup_hours(),
            auto_backup_keep: default_auto_backup_keep(),
            por_interval_hours: default_por_interval_hours(),
            spec_version: DEFAULT_SPEC_VERSION.to_string(),
            log_path: default_log_path().to_string_lossy().into_owned(),
        }
    }
}

/// Каталог конфигурации ноды ( overridable через NEXXUS_CONFIG_DIR — для тестов).
pub fn config_dir() -> PathBuf {
    if let Ok(dir) = std::env::var("NEXXUS_CONFIG_DIR") {
        if !dir.is_empty() {
            return PathBuf::from(dir);
        }
    }
    let home = std::env::var("HOME").unwrap_or_else(|_| ".".to_string());
    PathBuf::from(home).join(".nexxus")
}

/// Путь файла конфигурации.
pub fn config_path() -> PathBuf {
    config_dir().join("node.conf")
}

/// Каталог fleet-конфигов: `<config_dir>/nodes/<name>.conf` (F2).
pub fn nodes_dir() -> PathBuf {
    config_dir().join("nodes")
}

/// Описание узла fleet: имя + адрес API + файл токена.
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct FleetNode {
    pub name: String,
    pub conf_path: String,
    pub api: String,
    pub token_file: String,
}

/// Список узлов fleet из `<config_dir>/nodes/*.conf`.
/// Токен узла — `<nodes_dir>/<name>.token` (или NEXXUS_API_TOKEN_FILE для дефолта).
pub fn list_fleet_nodes() -> Vec<FleetNode> {
    list_fleet_nodes_in(&nodes_dir())
}

/// То же для произвольного каталога (явный путь — дружелюбно к параллельным тестам).
pub fn list_fleet_nodes_in(dir: &std::path::Path) -> Vec<FleetNode> {
    let mut out = Vec::new();
    if let Ok(rd) = std::fs::read_dir(dir) {
        for e in rd.flatten() {
            let p = e.path();
            if p.extension().and_then(|x| x.to_str()) != Some("conf") {
                continue;
            }
            let Some(name) = p.file_stem().and_then(|s| s.to_str()).map(|s| s.to_string()) else {
                continue;
            };
            if name.is_empty() || name.contains(['/', '\\', '.']) {
                continue;
            }
            let cfg = load_from(&p);
            let token_file = dir
                .join(format!("{name}.token"))
                .to_string_lossy()
                .into_owned();
            out.push(FleetNode {
                name,
                conf_path: p.to_string_lossy().into_owned(),
                api: cfg.api,
                token_file,
            });
        }
    }
    out.sort_by(|a, b| a.name.cmp(&b.name));
    out
}

/// Стандартный путь лога ноды.
pub fn default_log_path() -> PathBuf {
    config_dir().join("nexxusd.log")
}

/// Проверка корректности конфигурации.
/// Кворум имеет смысл только вместе с реестром аудиторов: при пустом
/// реестре порог обязан быть нулевым, иначе нода не сможет закрыть эпоху.
pub fn validate(cfg: &NodeConfig) -> Result<(), String> {
    if cfg.listen.trim().is_empty() {
        return Err("Адрес P2P-слушателя не может быть пустым".into());
    }
    if !cfg.listen.contains(':') {
        return Err(format!("Адрес P2P-слушателя '{}' должен содержать порт", cfg.listen));
    }
    if cfg.api.trim().is_empty() {
        return Err("Адрес API не может быть пустым".into());
    }
    if !cfg.api.contains(':') {
        return Err(format!("Адрес API '{}' должен содержать порт", cfg.api));
    }
    if cfg.epoch_secs == 0 {
        return Err("Длительность эпохи должна быть больше нуля".into());
    }
    if cfg.auditors.is_empty() {
        if cfg.threshold != 0 {
            return Err("Порог кворума задан без реестра аудиторов".into());
        }
    } else {
        if cfg.threshold == 0 {
            return Err("Порог кворума должен быть больше нуля, если есть аудиторы".into());
        }
        if cfg.threshold > cfg.auditors.len() {
            return Err(format!(
                "Порог кворума {} больше числа аудиторов {}",
                cfg.threshold,
                cfg.auditors.len()
            ));
        }
    }
    Ok(())
}

/// Читает конфигурацию из файла; отсутствующий/битый файл → дефолты.
pub fn load() -> NodeConfig {
    load_from(&config_path())
}

/// Читает конфигурацию из произвольного пути.
///
/// Явный путь вместо глобального env-переопределения: тесты в Rust
/// выполняются параллельно в одном процессе, и общий `NEXXUS_CONFIG_DIR`
/// приводил к гонке между тестами.
pub fn load_from(path: &std::path::Path) -> NodeConfig {
    let Ok(content) = std::fs::read_to_string(path) else {
        return NodeConfig::default();
    };
    let mut cfg = NodeConfig::default();
    for line in content.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let Some((key, value)) = line.split_once('=') else {
            continue;
        };
        let key = key.trim();
        let value = value.trim();
        match key {
            "listen" => cfg.listen = value.to_string(),
            "api" => cfg.api = value.to_string(),
            "auditors" => {
                cfg.auditors = value
                    .split(',')
                    .map(|s| s.trim().to_string())
                    .filter(|s| !s.is_empty())
                    .collect();
            }
            "threshold" => cfg.threshold = value.parse().unwrap_or(cfg.threshold),
            "epoch_secs" => cfg.epoch_secs = value.parse().unwrap_or(cfg.epoch_secs),
            "tor" => cfg.tor = !matches!(value.to_ascii_lowercase().as_str(), "0" | "false" | "no"),
            "auto_backup_hours" => cfg.auto_backup_hours = value.parse().unwrap_or(cfg.auto_backup_hours),
            "auto_backup_keep" => cfg.auto_backup_keep = value.parse().unwrap_or(cfg.auto_backup_keep),
            "por_interval_hours" => cfg.por_interval_hours = value.parse().unwrap_or(cfg.por_interval_hours),
            "spec_version" => cfg.spec_version = value.to_string(),
            "log_path" => cfg.log_path = value.to_string(),
            _ => {}
        }
    }
    cfg
}

/// Сохраняет конфигурацию атомарно (temp + rename) с правами 0600.
pub fn save(cfg: &NodeConfig) -> Result<(), String> {
    save_to(cfg, &config_path())
}

/// Сохраняет конфигурацию в произвольный путь (атомарно, права 0600).
pub fn save_to(cfg: &NodeConfig, path: &std::path::Path) -> Result<(), String> {
    validate(cfg)?;
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir).map_err(|e| format!("Не удалось создать {}: {e}", dir.display()))?;
    }
    let tmp = path.with_extension("conf.tmp");

    let body = format!(
        "listen={}\napi={}\nauditors={}\nthreshold={}\nepoch_secs={}\ntor={}\nauto_backup_hours={}\nauto_backup_keep={}\npor_interval_hours={}\nspec_version={}\nlog_path={}\n",
        cfg.listen,
        cfg.api,
        cfg.auditors.join(","),
        cfg.threshold,
        cfg.epoch_secs,
        if cfg.tor { "1" } else { "0" },
        cfg.auto_backup_hours,
        cfg.auto_backup_keep,
        cfg.por_interval_hours,
        cfg.spec_version,
        cfg.log_path,
    );

    std::fs::write(&tmp, body).map_err(|e| format!("Не удалось записать {}: {e}", tmp.display()))?;
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let _ = std::fs::set_permissions(&tmp, std::fs::Permissions::from_mode(0o600));
    }
    std::fs::rename(&tmp, path).map_err(|e| format!("Не удалось сохранить {}: {e}", path.display()))?;
    Ok(())
}

/// Переводит конфигурацию в пары переменных окружения для `nexxusd`.
pub fn to_env(cfg: &NodeConfig) -> Vec<(String, String)> {
    vec![
        ("NEXXUS_LISTEN".into(), cfg.listen.clone()),
        ("NEXXUS_API_ADDR".into(), cfg.api.clone()),
        ("NEXXUS_AUDITORS".into(), cfg.auditors.join(",")),
        ("NEXXUS_THRESHOLD".into(), cfg.threshold.to_string()),
        ("NEXXUS_EPOCH_SECS".into(), cfg.epoch_secs.to_string()),
        ("NEXXUS_TOR".into(), if cfg.tor { "1".into() } else { "0".into() }),
        ("NEXXUS_LOG".into(), cfg.log_path.clone()),
        ("NEXXUS_SPECIFICATION_V".into(), cfg.spec_version.clone()),
    ]
}

#[cfg(test)]
pub(crate) static TEST_ENV_LOCK: std::sync::Mutex<()> = std::sync::Mutex::new(());

#[cfg(test)]
mod tests {
    use super::*;

    /// Изолированный каталог конфигурации на время теста.
    ///
    /// Путь передаётся явно в `load_from`/`save_to`, а не через env: тесты
    /// выполняются параллельно, и общий env-переопределитель давал гонку.
    struct TempDir(PathBuf);

    impl TempDir {
        fn new(tag: &str) -> Self {
            let dir = std::env::temp_dir().join(format!(
                "nexxus-config-test-{}-{}",
                tag,
                std::process::id()
            ));
            let _ = std::fs::remove_dir_all(&dir);
            std::fs::create_dir_all(&dir).unwrap();
            Self(dir)
        }

        /// Путь к файлу конфигурации внутри временного каталога.
        fn conf(&self) -> PathBuf {
            self.0.join("node.conf")
        }
    }

    impl Drop for TempDir {
        fn drop(&mut self) {
            let _ = std::fs::remove_dir_all(&self.0);
        }
    }

    #[test]
    fn default_config_has_loopback_ports() {
        let cfg = NodeConfig::default();
        assert_eq!(cfg.listen, "127.0.0.1:4001");
        assert_eq!(cfg.api, "127.0.0.1:4010");
        assert!(cfg.tor, "Tor включён по умолчанию");
        assert_eq!(cfg.epoch_secs, 300);
        assert!(cfg.auditors.is_empty());
        assert_eq!(cfg.threshold, 0);
    }

    #[test]
    fn save_then_load_roundtrip() {
        let tmp = TempDir::new("roundtrip");
        let path = tmp.conf();
        let cfg = NodeConfig {
            listen: "0.0.0.0:4001".into(),
            api: "127.0.0.1:5010".into(),
            auditors: vec!["aa".into(), "bb".into()],
            threshold: 1,
            epoch_secs: 600,
            tor: false,
            auto_backup_hours: 12,
            auto_backup_keep: 3,
            por_interval_hours: 6,
            spec_version: "v3".into(),
            log_path: "/tmp/custom.log".into(),
        };
        save_to(&cfg, &path).unwrap();
        let loaded = load_from(&path);
        assert_eq!(loaded, cfg);
    }

    #[test]
    fn to_env_emits_auditors_and_threshold() {
        let cfg = NodeConfig {
            auditors: vec!["aa".into(), "bb".into()],
            threshold: 2,
            tor: false,
            ..NodeConfig::default()
        };
        let env = to_env(&cfg);
        let get = |k: &str| {
            env.iter()
                .find(|(n, _)| n == k)
                .map(|(_, v)| v.clone())
                .unwrap_or_default()
        };
        assert_eq!(get("NEXXUS_AUDITORS"), "aa,bb");
        assert_eq!(get("NEXXUS_THRESHOLD"), "2");
        assert_eq!(get("NEXXUS_TOR"), "0");
        assert_eq!(get("NEXXUS_LISTEN"), "127.0.0.1:4001");
        assert_eq!(get("NEXXUS_EPOCH_SECS"), "300");
    }

    #[test]
    fn invalid_threshold_rejected() {
        let tmp = TempDir::new("invalid");
        let path = tmp.conf();
        // Порог без аудиторов — кворум недостижим.
        let bad = NodeConfig { threshold: 3, ..NodeConfig::default() };
        assert!(save_to(&bad, &path).is_err());
        // Порог больше числа аудиторов — тоже ошибка.
        let bad2 = NodeConfig {
            auditors: vec!["aa".into()],
            threshold: 5,
            ..NodeConfig::default()
        };
        assert!(save_to(&bad2, &path).is_err());
        // Нулевая эпоха — ошибка.
        let bad3 = NodeConfig { epoch_secs: 0, ..NodeConfig::default() };
        assert!(save_to(&bad3, &path).is_err());
        // Некорректный адрес — ошибка.
        let bad4 = NodeConfig { listen: "no-port".into(), ..NodeConfig::default() };
        assert!(save_to(&bad4, &path).is_err());
        // Корректная конфигурация сохраняется.
        let good = NodeConfig {
            auditors: vec!["aa".into(), "bb".into(), "cc".into()],
            threshold: 2,
            ..NodeConfig::default()
        };
        assert!(save_to(&good, &path).is_ok());
    }

    #[test]
    fn missing_file_yields_defaults() {
        let tmp = TempDir::new("missing");
        let cfg = load_from(&tmp.conf());
        assert_eq!(cfg, NodeConfig::default());
    }

    #[test]
    fn fleet_nodes_listed_and_name_validated() {
        let tmp = TempDir::new("fleet");
        let dir = tmp.0.join("nodes");
        std::fs::create_dir_all(&dir).unwrap();
        // валидный узел
        let cfg = NodeConfig { api: "127.0.0.1:4011".into(), ..Default::default() };
        save_to(&cfg, &dir.join("alpha.conf")).unwrap();
        std::fs::write(dir.join("alpha.token"), "tok-alpha").unwrap();
        // опасное имя — пропускается
        save_to(&NodeConfig::default(), &dir.join("../evil.conf")).ok();
        std::fs::write(dir.join("..conf"), "{}").ok();
        // не .conf — игнорируется
        std::fs::write(dir.join("notes.txt"), "hi").unwrap();

        let nodes = list_fleet_nodes_in(&dir);
        assert_eq!(nodes.len(), 1, "только валидный .conf: {nodes:?}");
        assert_eq!(nodes[0].name, "alpha");
        assert_eq!(nodes[0].api, "127.0.0.1:4011");
        assert!(nodes[0].token_file.ends_with("alpha.token"));
    }
}
