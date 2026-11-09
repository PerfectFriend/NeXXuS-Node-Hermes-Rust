//! Однократный запуск монитора.
//!
//! Монитор запускается из ярлыка на рабочем столе, и пользователь может
//! кликнуть ярлык повторно. Второй экземпляр был источником реальной поломки:
//! он поднимал свою копию `nexxusd` (конфликт портов), а его цикл здоровья
//! воскрешал ноду, только что остановленную из трея первого экземпляра —
//! из-за этого кнопка «Остановить ноду» выглядела как нерабочая.
//!
//! Защита — lock-файл с PID: если живой процесс уже держит lock, второй
//! экземпляр тихо завершается, не трогая ноду.

use std::io::Write;
use std::path::PathBuf;

/// Путь к lock-файлу монитора.
pub fn lock_path() -> PathBuf {
    crate::node_config::config_dir().join("monitor.lock")
}

/// Держит lock-файл; при выходе из процесса файл снимается.
pub struct InstanceLock {
    path: PathBuf,
}

impl InstanceLock {
    /// Захватывает lock. `Err` — монитор уже запущен (или lock занят).
    pub fn acquire() -> Result<Self, String> {
        let path = lock_path();
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }

        for attempt in 0..2 {
            match std::fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(&path)
            {
                Ok(mut file) => {
                    let _ = writeln!(file, "{}", std::process::id());
                    let _ = file.flush();
                    return Ok(InstanceLock { path });
                }
                Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => {
                    if let Some(pid) = read_pid(&path) {
                        if process_alive(pid) {
                            return Err(format!(
                                "Монитор уже запущен (PID {pid}) — второй экземпляр не запускается"
                            ));
                        }
                    }
                    // Lock остался от упавшего процесса — снимаем и пробуем снова.
                    let _ = std::fs::remove_file(&path);
                    if attempt == 1 {
                        return Err(format!(
                            "Не удалось захватить lock-файл {}: занят",
                            path.display()
                        ));
                    }
                }
                Err(e) => {
                    return Err(format!(
                        "Не удалось создать lock-файл {}: {e}",
                        path.display()
                    ))
                }
            }
        }

        Err(format!("Не удалось захватить lock-файл {}", path.display()))
    }
}

impl Drop for InstanceLock {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(&self.path);
    }
}

/// PID из lock-файла.
fn read_pid(path: &PathBuf) -> Option<u32> {
    let content = std::fs::read_to_string(path).ok()?;
    content.trim().lines().next()?.trim().parse().ok()
}

/// Жив ли процесс: есть /proc/<pid> и его cmdline похож на наш монитор.
fn process_alive(pid: u32) -> bool {
    let proc_dir = PathBuf::from("/proc").join(pid.to_string());
    if !proc_dir.exists() {
        return false;
    }
    // Если cmdline читается — проверяем, что это действительно монитор:
    // PID мог быть переиспользован другим процессом. Имя тестового бинаря
    // cargo — `nexxus_desktop-<hash>` (подчёркивание), у release-бинаря —
    // `nexxus-desktop`, поэтому принимаем оба варианта.
    match std::fs::read_to_string(proc_dir.join("cmdline")) {
        Ok(cmdline) => {
            cmdline.contains("nexxus-desktop") || cmdline.contains("nexxus_desktop")
        }
        Err(_) => true,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn lock_acquire_and_release() {
        let tmp = std::env::temp_dir().join(format!("nexxus-instance-test-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&tmp);
        std::fs::create_dir_all(&tmp).unwrap();

        let path = tmp.join("monitor.lock");
        std::fs::write(&path, format!("{}\n", std::process::id())).unwrap();
        assert_eq!(read_pid(&path), Some(std::process::id()));
        assert!(process_alive(std::process::id()));
        assert!(!process_alive(u32::MAX - 1));

        let _ = std::fs::remove_dir_all(&tmp);
    }

    #[test]
    fn stale_lock_pid_is_not_alive() {
        let tmp = std::env::temp_dir().join(format!("nexxus-instance-stale-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&tmp);
        std::fs::create_dir_all(&tmp).unwrap();

        let path = tmp.join("monitor.lock");
        std::fs::write(&path, "4294967290\n").unwrap();
        assert_eq!(read_pid(&path), Some(4294967290));
        assert!(!process_alive(4294967290));

        let _ = std::fs::remove_dir_all(&tmp);
    }
}
