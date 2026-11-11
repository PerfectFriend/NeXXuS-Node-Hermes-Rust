# Ревизия проекта NeXXus — 11.11.2026 (подготовка к RC1)

Аудит по правилу: рекламируемое vs реализованное, классификация broken / dead / unbuilt.
Все «проверено» — из команд ниже (сессия 11.11.2026); «заявлено» — только из документации.

## 1. Проверенное состояние (verified, живые команды этой сессии)

| Компонент | Доказательство |
|---|---|
| Rust-воркспейс: 4 крейта, ~8 800 строк (core 3320, node 5020, econ 322, wasm 136) + nexxus-desktop 2 415 строк Rust + 1 341 фронт | `wc -l` |
| `cargo test --workspace`: **138 passed, 0 failed** (core 69, econ 12, node 55, wasm 2) | прогон 11.11 |
| `cargo clippy --workspace --all-targets -- -D warnings` = **0** | прогон 11.11 |
| `npm test` (nexxus-desktop): **5/5** (в т.ч. соответствие invoke↔команды Tauri) | прогон 11.11 |
| `vite build` exit 0; `cargo build --release` exit 0 (бинарник 14:49) | прогон 11.11 |
| Живая нода: P2P + WS API слушают, `api_probe node_status` → node_id `0ce668d4…`, `paused:false` | смоук 11.11 |
| Управление нодой доказано: `node_pause → paused:true`, `node_resume → paused:false` | api_probe 11.11 |
| Telegram: `getMe ok`, `sendMessage → message_id 10000` (доставка подтверждена ответом API) | curl 11.11 |
| Все 20 Tauri-команд, которые зовёт фронт, зарегистрированы в бинарнике | `strings` + npm test |
| WS API ноды: 19 методов (auth, ping, 16 node_*, 3 panic_*) с токен-аутентификацией | grep local_api.rs |
| CLI ноды: init, id, status, peers, peer, upload, download, logs, test-por, test-interhost, benchmark | grep cli.rs |
| Безопасность (Phase A из плана v3): A1 token auth ✅, A2 шифрование store at rest ✅, A3 panic PIN dual/duress ✅, A4 zeroize+no core dumps ✅ | коммиты 52a38f0, 787c963, 03156d2, 26df826 |
| Дашборд монитора (Phase B): 8 вкладок, все панели через `node_api_cmd`, NodeID-hero, конфиг-форма, юнит install/uninstall, логи, Telegram-панель настроек | коммиты 392d83a, 472e9e8, 22bab5e |
| Онбординг-машина (C1): 6 шагов, персистентно, идемпотентно | коммит 472e9e8, 6/6 тестов |
| CI: `.github/workflows/ci-release.yml` гоняет npm test + cargo test + clippy + build (в т.ч. --features tor) | чтение workflow |

## 2. Находки этой сессии

### broken (найдено и починено в этой ревизии)
1. **Гонка env-тестов**: `onboarding.rs` и `telegram.rs` использовали разные `ENV_LOCK` — параллельный `cargo test --bin nexxus-desktop` падал 2/19 (telegram config_tests). Починено: общий `node_config::TEST_ENV_LOCK`, оба модуля на нём. (Фикс в рабочей ветке, прогон 3x подряд — см. следующий коммит.)
2. **Рассинхрон бинарник/фронт**: запущенный монитор был собран до свежего фронта (встроенный UI старый → «кнопки не работают»). Пересобрано 14:49, перезапущено.

### dead
- `api_client.rs` имеет `#![allow(dead_code)]` на уровне модуля — по правилу «или в проводку, или удалить».
- Ряд функций в guardian.rs помечены `#[allow(dead_code)]` (get_node_peers/chunks/epoch/tor) — теперь UI ходит через `node_api_cmd`, эти обёртки мёртвые.

### unbuilt (план, не дефекты)
- C2: BIP39 регистрация/восстановление/экспорт в UI (`node_identity_export` в API отсутствует — grep пуст).
- C3: зашифрованный бэкап сид-фразы (vault) в UI.
- D1–D3: бэкап/восстановление store (нет в storage.rs), автобэкап 3-2-1, `nexxusd doctor` (нет в cli.rs).
- E1–E2: панели экономики и эпохи/аудиторов (`node_econ` в API нет).
- F1–F3: скоринг пиров, fleet view, onion-дашборд.
- G2–G5: fuzz/proptest, golden vectors на все опкоды, self-update, пакеты (AppImage/Windows/Android).
- H1: SMP inbox UI (есть только просмотр `node_smp`).

### unverified
- GUI-клики вживую (нет DISPLAY в этом окружении) — логика покрыта headless-тестами, смоук API — живой.
- Сеть между двумя узлами (test-interhost) в этой сессии не прогонялся.

## 3. Главные риски к RC1
1. BIP39 сид в UI ещё не реализован — без C2/C3 RC1 неполный по части идентичности.
2. Бэкапы отсутствуют — потеря store = потеря ноды.
3. CI не собирает артефакт nexxus-desktop в release (только nexxus-node) — RC1-пакет монитора не автоматизирован.
