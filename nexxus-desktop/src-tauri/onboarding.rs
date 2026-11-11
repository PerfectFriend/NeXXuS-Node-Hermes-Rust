//! Персистентная машина состояний онбординга монитора (Phase C1).
//!
//! Состояние хранится в `~/.nexxus/onboarding.json` (каталог переопределяется
//! через `NEXXUS_CONFIG_DIR` — для тестов). `advance` идемпотентен: повторный
//! advance уже пройденного шага — ок, пропуск шагов — отказ.

use serde::{Deserialize, Serialize};
use std::path::PathBuf;

/// Шаги онбординга, строго по порядку.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StepId {
    Welcome,
    Identity,
    Store,
    Network,
    Notifications,
    Done,
}

impl StepId {
    pub const ORDER: [StepId; 6] = [
        StepId::Welcome,
        StepId::Identity,
        StepId::Store,
        StepId::Network,
        StepId::Notifications,
        StepId::Done,
    ];

    fn index(self) -> usize {
        Self::ORDER.iter().position(|s| *s == self).expect("step in ORDER")
    }

    pub fn next(self) -> Option<StepId> {
        Self::ORDER.get(self.index() + 1).copied()
    }

    pub fn as_str(self) -> &'static str {
        match self {
            StepId::Welcome => "welcome",
            StepId::Identity => "identity",
            StepId::Store => "store",
            StepId::Network => "network",
            StepId::Notifications => "notifications",
            StepId::Done => "done",
        }
    }

    pub fn from_str(s: &str) -> Option<StepId> {
        Self::ORDER.iter().copied().find(|st| st.as_str() == s)
    }
}

/// Персистентное состояние онбординга.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct OnboardingState {
    /// Текущий (не пройденный) шаг.
    pub current: StepId,
    /// Уже пройденные шаги.
    pub completed: Vec<StepId>,
    /// Unix-seconds последнего изменения.
    pub updated_at: u64,
}

impl Default for OnboardingState {
    fn default() -> Self {
        Self {
            current: StepId::Welcome,
            completed: Vec::new(),
            updated_at: now_secs(),
        }
    }
}

fn now_secs() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

/// Путь к файлу состояния онбординга.
pub fn state_path() -> PathBuf {
    crate::node_config::config_dir().join("onboarding.json")
}

/// Загружает состояние; отсутствующий файл = свежий онбординг.
pub fn load() -> Result<OnboardingState, String> {
    let path = state_path();
    match std::fs::read_to_string(&path) {
        Ok(text) => serde_json::from_str(&text)
            .map_err(|e| format!("повреждён {}: {e}", path.display())),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(OnboardingState::default()),
        Err(e) => Err(format!("не удалось прочитать {}: {e}", path.display())),
    }
}

/// Сохраняет состояние атомарно (tmp + rename), права 0600.
pub fn save(state: &OnboardingState) -> Result<(), String> {
    let path = state_path();
    if let Some(dir) = path.parent() {
        std::fs::create_dir_all(dir)
            .map_err(|e| format!("не удалось создать {}: {e}", dir.display()))?;
    }
    let tmp = path.with_extension("json.tmp");
    let text = serde_json::to_string_pretty(state)
        .map_err(|e| format!("сериализация состояния: {e}"))?;
    {
        use std::io::Write;
        let mut f = std::fs::File::create(&tmp)
            .map_err(|e| format!("не удалось создать {}: {e}", tmp.display()))?;
        f.write_all(text.as_bytes())
            .map_err(|e| format!("запись {}: {e}", tmp.display()))?;
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            std::fs::set_permissions(&tmp, std::fs::Permissions::from_mode(0o600))
                .map_err(|e| format!("chmod {}: {e}", tmp.display()))?;
        }
    }
    std::fs::rename(&tmp, &path).map_err(|e| format!("rename в {}: {e}", path.display()))?;
    Ok(())
}

/// Продвигает онбординг на шаг `step`.
///
/// - Идемпотентно: если шаг уже в `completed` — состояние не меняется, Ok.
/// - Отказ при пропуске: можно закрыть только `current` (или повторить пройденный).
/// - При закрытии предпоследнего шага состояние становится `Done`.
pub fn advance(mut state: OnboardingState, step: StepId) -> Result<OnboardingState, String> {
    if state.completed.contains(&step) {
        return Ok(state); // идемпотентность
    }
    if step != state.current {
        return Err(format!(
            "нельзя закрыть шаг '{}': текущий шаг '{}'",
            step.as_str(),
            state.current.as_str()
        ));
    }
    state.completed.push(step);
    state.current = step.next().unwrap_or(StepId::Done);
    state.updated_at = now_secs();
    Ok(state)
}

/// Сброс онбординга (для повторного прохождения из UI).
pub fn reset() -> Result<OnboardingState, String> {
    let state = OnboardingState::default();
    save(&state)?;
    Ok(state)
}

#[cfg(test)]
mod tests {
    use super::*;

    use std::sync::atomic::{AtomicU64, Ordering};

    static DIR_COUNTER: AtomicU64 = AtomicU64::new(0);

    fn with_temp_dir(f: impl FnOnce()) {
        // Env-global: сериализуем ВСЕ env-тесты крейта через общий lock
        // (иначе onboarding и telegram::config_tests дерутся за NEXXUS_CONFIG_DIR),
        // и даём каждому уникальный каталог.
        let _guard = crate::node_config::TEST_ENV_LOCK.lock().unwrap();
        let dir = std::env::temp_dir().join(format!(
            "nexxus-onboarding-test-{}-{}",
            std::process::id(),
            DIR_COUNTER.fetch_add(1, Ordering::SeqCst)
        ));
        std::env::set_var("NEXXUS_CONFIG_DIR", &dir);
        f();
        std::env::remove_var("NEXXUS_CONFIG_DIR");
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn fresh_state_starts_at_welcome() {
        with_temp_dir(|| {
            let s = load().unwrap();
            assert_eq!(s.current, StepId::Welcome);
            assert!(s.completed.is_empty());
        });
    }

    #[test]
    fn advance_is_idempotent_for_completed_steps() {
        with_temp_dir(|| {
            let mut s = OnboardingState::default();
            s = advance(s, StepId::Welcome).unwrap();
            assert_eq!(s.current, StepId::Identity);
            let before = s.clone();
            let s2 = advance(s, StepId::Welcome).unwrap(); // повтор — ок, без изменений
            assert_eq!(s2, before);
        });
    }

    #[test]
    fn advance_rejects_skips() {
        with_temp_dir(|| {
            let s = OnboardingState::default();
            let err = advance(s, StepId::Store).unwrap_err();
            assert!(err.contains("текущий"), "ожидалась ошибка о текущем шаге: {err}");
        });
    }

    #[test]
    fn full_walk_reaches_done_and_persists() {
        with_temp_dir(|| {
            let mut s = OnboardingState::default();
            // Закрываем все шаги кроме терминального Done.
            for &step in &StepId::ORDER[..StepId::ORDER.len() - 1] {
                s = advance(s, step).unwrap();
                save(&s).unwrap();
            }
            assert_eq!(s.current, StepId::Done);
            assert_eq!(s.completed.len(), 5);
            // персистентность: load читает то же состояние
            let loaded = load().unwrap();
            assert_eq!(loaded, s);
            // файл 0600
            #[cfg(unix)]
            {
                use std::os::unix::fs::PermissionsExt;
                let mode = std::fs::metadata(state_path()).unwrap().permissions().mode();
                assert_eq!(mode & 0o777, 0o600);
            }
        });
    }

    #[test]
    fn step_id_roundtrip_str() {
        for step in StepId::ORDER {
            assert_eq!(StepId::from_str(step.as_str()), Some(step));
        }
        assert_eq!(StepId::from_str("nope"), None);
    }

    #[test]
    fn reset_returns_to_welcome() {
        with_temp_dir(|| {
            let mut s = OnboardingState::default();
            s = advance(s, StepId::Welcome).unwrap();
            save(&s).unwrap();
            let r = reset().unwrap();
            assert_eq!(r.current, StepId::Welcome);
            assert_eq!(load().unwrap().current, StepId::Welcome);
        });
    }
}
