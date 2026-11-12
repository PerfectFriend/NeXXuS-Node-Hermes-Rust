//! Однократный запуск монитора (single-instance, без TOCTOU).
//!
//! Монитор запускается из ярлыка на рабочем столе, и пользователь может
//! кликнуть ярлык повторно. Второй экземпляр был источником реальной поломки:
//! он поднимал свою копию `nexxusd` (конфликт портов), а его цикл здоровья
//! воскрешал ноду, только что остановленную из трея первого экземпляра —
//! из-за этого кнопка «Остановить ноду» выглядела как нерабочая.
//!
//! Защита — flock (advisory lock) на lock-файле: захват атомарный на уровне
//! ОС, в отличие от прежней схемы create_new + remove_file, где два
//! процесса одновременно видели «stale» lock и оба создавали файл (TOCTOU).
//! Если lock уже держит живой процесс — второй экземпляр тихо завершается,
//! не трогая ноду. PID в файле — только для диагностики.

use fs2::FileExt;
use std::io::Write;
use std::path::{Path, PathBuf};

/// Путь к lock-файлу монитора.
pub fn lock_path() -> PathBuf {
    crate::node_config::config_dir().join("monitor.lock")
}

/// Держит flock на lock-файле; при выходе из процесса lock снимается ОС.
pub struct InstanceLock {
    file: std::fs::File,
    path: PathBuf,
}

impl InstanceLock {
    /// Захватывает lock. `Err` — монитор уже запущен (lock занят другим процессом).
    pub fn acquire() -> Result<Self, String> {
        Self::acquire_at(&lock_path())
    }

    fn acquire_at(path: &Path) -> Result<Self, String> {
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        let file = std::fs::OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .open(path)
            .map_err(|e| format!("Не удалось открыть lock-файл {}: {e}", path.display()))?;

        // Атомарный захват: либо мы держим lock, либо кто-то другой.
        if file.try_lock_exclusive().is_err() {
            let pid = read_pid(path).unwrap_or(0);
            return Err(format!(
                "Монитор уже запущен (PID {pid}) — второй экземпляр не запускается"
            ));
        }

        // Lock наш: перезаписываем содержимое своим PID (диагностика).
        let mut f = &file;
        let _ = f.set_len(0);
        let _ = f.write_all(format!("{}\n", std::process::id()).as_bytes());
        let _ = f.flush();

        Ok(InstanceLock {
            file,
            path: path.to_path_buf(),
        })
    }
}

impl Drop for InstanceLock {
    fn drop(&mut self) {
        // flock снимается при закрытии fd; файл удаляем для чистоты каталога.
        let _ = self.file.unlock();
        let _ = std::fs::remove_file(&self.path);
    }
}

/// PID из lock-файла (диагностика; 0 если не прочитан).
fn read_pid(path: &Path) -> Option<u32> {
    let content = std::fs::read_to_string(path).ok()?;
    content.trim().lines().next()?.trim().parse().ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmp_lock(name: &str) -> PathBuf {
        let tmp = std::env::temp_dir().join(format!(
            "nexxus-instance-{}-{name}",
            std::process::id()
        ));
        let _ = std::fs::remove_file(&tmp);
        tmp
    }

    #[test]
    fn second_acquire_on_same_file_fails_atomically() {
        // TOCTOU-регрессия: два захвата одного файла — второй обязан получить Err,
        // даже в одном процессе (flock per open-file-description).
        let path = tmp_lock("race");
        let first = InstanceLock::acquire_at(&path).expect("first acquire must succeed");
        let second = InstanceLock::acquire_at(&path);
        assert!(second.is_err(), "second acquire must fail while lock held");
        drop(first);
        // После drop lock освобождён — повторный захват успешен.
        let third = InstanceLock::acquire_at(&path).expect("acquire after release must succeed");
        drop(third);
        let _ = std::fs::remove_file(&path);
    }

    #[test]
    fn stale_lock_file_without_holder_is_reacquired() {
        // Lock-файл от упавшего процесса (никто не держит flock) захватывается сразу.
        let path = tmp_lock("stale");
        std::fs::write(&path, "4294967290\n").unwrap();
        assert_eq!(read_pid(&path), Some(4294967290));
        let lock = InstanceLock::acquire_at(&path).expect("stale lock must be reacquired");
        assert_eq!(read_pid(&path), Some(std::process::id()));
        drop(lock);
        let _ = std::fs::remove_file(&path);
    }
}
