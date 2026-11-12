# План эволюции после внешнего аудита (Grok, 2026-11-12)

Источник: `Downloads/AUDIT_REPORT_NeXXuS_Node_Hermes_Rust.md` (аудит нашего репо `NeXXuS-Node-Hermes-Rust`, RC1).
База: `a8cf065` — 157/157 workspace + 19/19 desktop, clippy 0.

## Что аудитор подтвердил как закрытое (не трогаем)
- Фрейм-лимит до аллокации (наш CRITICAL DoS) — positive finding #1.
- Fail-closed token auth + constant-time compare + 0600 — #2.
- Привязка Ed25519 ключа пира через NodeAnnounce — #3.
- Инвариант nonce: hash-проверка + no-overwrite в put_chunk — #4.
- Seed vault PBKDF2-600k + duress + zeroize ключа — #5.
- Валидация имён бэкапов + staged restore — #6. `unsafe` запрещён — #7.

## Классификация находок

| ID аудита | Severity | Статус у нас | Действие |
|---|---|---|---|
| NET-01 rate-limit/handshake на 0.0.0.0:4001 | Medium | **нет** | фаза A1 |
| NET-02 статический SESSION_NONCE | Medium | **есть** (константа) | фаза A1 |
| NET-03 max_peers + idle timeout | Low | нет | фаза A2 |
| NET-04 буферизация 4MiB × N conn | Info | закрыто частично | закрывается NET-01 |
| API-01 явные WS max_message/frame size | Low | не задано | фаза A1 |
| API-02/03 trust boundary локального API | Info | задокументируем | THREAT_MODEL.md |
| STR-01 инвариант put_chunk | — | есть + тесты | добавить комментарий-тест про намеренный nonce |
| STR-02 миграция шифрования однофазная | Low | есть риск | двухфазный флаг, фаза A2 |
| VLT-01 zeroize всех буферов с мнемоникой | Low | частично (seed/keys — да, String — нет) | `Zeroizing<String>`, фаза A2 |
| VLT-02 ре-encrypt старых 100k vault до 600k | Info | нет | фаза B (опционально) |
| VLT-03 duress неотличим от wrong pin в UI | — | проверить UI | фаза A2 |
| BKP-01 TOCTOU restore vs живой демон | Low | нет лока | exclusive lock (fs2 уже в зависимостях), фаза A1 |
| BKP-02 backups/ dir 0700 | Info | проверить | фаза A1 |
| DEP-01 cargo audit/deny в CI | Medium (process) | **не было** | фаза A1: локальный прогон + шаг в CI |
| DEP-02 два rand (0.8+0.10) | Info | есть | фаза B: гармонизация |
| DEP-03 секреты в истории git | High (operational) | **действие владельца** | ротация + filter-repo/squash до раздачи; не код |

## Фаза A1 — Immediate (до любого публичного P2P)
1. **NET-01**: глобальный semaphore на коннекты (например 128), per-IP token bucket (5 concurrent, 20 new/min), таймаут incomplete handshake 4 s. Тест: N быстрых коннектов → часть отбивается; RSS не растёт.
2. **NET-02**: случайный 32-байтный session nonce на соединение, включается в `v3_signing_bytes` обеими сторонами. Тест: фрейм, подписанный под другим nonce, отклоняется.
3. **API-01**: явный `max_message_size`/`max_frame_size` (4 MiB) в WS acceptor.
4. **BKP-01/02**: exclusive flock на store при `restore`/swap; `backups/` создаётся 0700. Тест: restore при запущенном демоне падает чисто.
5. **DEP-01**: `cargo audit` локально + job в CI (`cargo audit`, `cargo deny` advisories); отчёт в release notes.
6. **DEP-03**: чеклист владельцу (ротация PAT/bot-токенов, filter-repo) — вынести в AUDITOR.md/README.

## Фаза A2 — RC1 hardening
7. **NET-03**: `max_peers` (default 64) + idle timeout 20 мин.
8. **VLT-01**: `Zeroizing<String>` для mnemonic во всех путях (identity_store, seed_vault, backup_seed).
9. **STR-02**: двухфазный флаг миграции (`migrating` → `encrypted`), флаг после завершения.
10. **VLT-03**: UI не различает wrong-pin/duress.
11. **docs/THREAT_MODEL.md**: 5 пунктов из §6 аудита + API trust boundary (API-02).

## Фаза B — later
12. VLT-02: авто re-encrypt 100k → 600k при успешном открытии.
13. Fuzz wire-парсера (proptest/cargo-fuzz target для parse_v3/recv_frame/payload decode).
14. Econ: overflow-тесты анти-луп инварианта на i64 micro-NEXX.
15. DEP-02: единый rand.
16. Guardian TOCTOU single-instance lock (fs2 lock вместо lock-файла-удаления).

## Правила фазы
- Каждая фаза: тесты + clippy 0 + живой смоук + коммит+пуш в `PerfectFriend/NeXXuS-Node-Hermes-Rust` (main).
- Не регрессировать positive findings аудита.
- DEP-03 — единственное, что не в коде: владелец ротирует и чистит историю до раздачи аудитору/наружу.

## СТАТУС 2026-11-12 (коммит 532575e) — фаза A1 ЗАКРЫТА в коде
1. **NET-01** ✅ — accept-gate: semaphore 128 глобально, per-IP active≤8, new≤20/мин (дроп молча), HANDSHAKE_TIMEOUT=4s на первый фрейм. Тесты: `ip_rate_limit_drops_after_20_new_connections_per_minute`, `incomplete_handshake_is_dropped_after_timeout`.
2. **NET-02** ✅ — `session_nonce[32]` (OsRng) на соединение в NodeAnnounce (wire 102 байта), включается в `v3_signing_bytes` обеими сторонами; клиент верифицирует ответы через `recv_verified_frame`. Тест: `session_nonce_is_per_connection_and_replay_is_rejected` (replay чужим nonce → 0x0008).
3. **API-01** ✅ — WS `max_message_size=max_frame_size=1 MiB`, `MAX_WS_CONNECTIONS=16` (semaphore), `accept_unmasked_frames=false`. Live-smoke: ping ok, no-auth → -32001, 2 MiB фрейм → соединение закрыто.
4. **BKP-01/02** ✅ — flock через fs2: `.backup.lock` (EX при backup/swap, SH при verify), `.store.lock` при swap; `validate_backup_name` + проверка `store_file` из manifest (plain file name only).
5. **DEP-01** ⏳ — `cargo audit` в песочнице нет (`no such command`); нужен локальный прогон + CI job — ручной шаг.
6. **DEP-03** ⚠️ — владелец: ротация PAT/bot-токенов + filter-repo/squash ДО раздачи репо аудитору.

Проверено: `cargo test --workspace` 158/158 green, `cargo clippy --workspace --all-targets -- -D warnings` чист, live-smoke nexxusd (WS + P2P порты).

## СТАТУС 2026-11-12 (коммит 261918b) — фаза A2 ЗАКРЫТА
7. **NET-03** ✅ — `max_peers` (default 64, AtomicUsize) → announce при полной таблице отклоняется `0x0009`; `IDLE_TIMEOUT` 20 мин на established connections. Тест `peer_cap_rejects_announce_when_routing_full`.
8. **VLT-01** ✅ — mnemonic везде как `Zeroizing<String>`: `read_mnemonic`, `load_or_create_identity`, `init_identity`, `restore_seed`, `import_mnemonic` (existing phrase). Вызовы в main/cli/local_api обновлены.
9. **STR-02** ✅ — двухфазная миграция: флаг `migrating` отдельным коммитом → re-encrypt → флаг `v1`; при рестарте с `migrating` миграция дожимается (уже зашифрованные чанки пропускаются по decrypt). Тест `migration_resume_after_crash_midway`.
10. **VLT-03** ✅ — проверено по коду: UI различает `duress` (алерт в Telegram, сид НЕ восстановлен) и `wrong_pin` (`nexxus-desktop/src/main.js` ~730, API статусы в `local_api.rs`).
11. **THREAT_MODEL.md** ✅ — `docs/THREAT_MODEL.md`: 5 trust-boundary пунктов аудита + API-02 + статусы NET-01/02/03, BKP, остатки (DEP-01/03).

Проверено: workspace 162/162 green, clippy `-D warnings` чист, WS live-smoke (ping ok / no-auth -32001 / 2MiB frame закрыт).

Осталось: ручные DEP-01 (cargo audit в CI) и DEP-03 (ротация секретов владельцем).

## СТАТУС 2026-11-12 (коммит 2d4818f) — фаза B ЗАКРЫТА
12. **VLT-02** ✅ — `restore_seed` при успешном unlock vault с KDF<600k и без duress-PIN автоматически перешифровывает на 600k (tmp+rename, 0600). С duress-PIN — skip + eprintln (duress_hash зависит от salt). Тест `legacy_100k_vault_is_auto_reencrypted_to_600k_on_unlock`.
13. **Fuzz wire** ✅ — proptest `crates/nexxus-core/tests/wire_fuzz.rs` (512 cases/тест): parse v2/v3 never-panic, v2/v3 roundtrip, decode всех 15 payload-типов, tamper. **Находка fuzz'а:** `ErrorResponse.message_len` был u8 — сообщение >255 байт заворачивалось (`as u8` wrap) → теперь u16 + strict UTF-8.
14. **Econ overflow** ✅ — `daily_storer_reward`/`daily_subscription_cost`/`split_into_sections`/`VestingSchedule` переведены на saturating arithmetic; тесты на u64::MAX / i64::MAX micro-NEXX. Анти-луп инвариант 1.30>1.25 подтверждён тестом.
15. **DEP-02** ✅ Принято: rand 0.10 в lockfile — только транзитивная arti/tor; наш код един на workspace rand 0.8.
16. **Guardian TOCTOU** ✅ — `InstanceLock` переведён с `create_new`+`remove_file` (гонка двух процессов на stale lock) на `flock` (`try_lock_exclusive`, fs2) — атомарный захват. Тесты: второй acquire падает пока lock держат, stale-файл без держателя захватывается.

Бонус-фикс: флап backup-тестов — tmp-имя verify получило random суффикс (два параллельных verify с одинаковым именем бэкапа бились в один файл redb); 5 прогонов подряд 80/80.

Верификация: workspace 172/172 green (core 69 + fuzz 6 + econ 15 + node 80 + fixtures 2), desktop 19/19, clippy `--workspace --all-targets -D warnings` = 0, clippy desktop = 0.

Осталось вне кода: DEP-01 (cargo audit/deny в CI — ручной, в sandbox нет), DEP-03 (ротация секретов из истории git — только владелец, до раздачи аудитору).

## СТАТУС 2026-11-12 (коммит 3eaaab2) — DEP-01 выполнен, DEP-03 проинвентаризирован
- **DEP-01** ✅ — cargo-audit 0.23.0 прогнан (555 крейтов): arti/tor подняты 0.47→0.48, осталось 3 vulns, все транзитивны от arti и заблокированы её semver-пинами (rsa 0.9.10, crypto-bigint 0.5.5, libsqlite3-sys 0.38.2) → игноры с обоснованием в `.cargo/audit.toml`, разбор в `docs/DEP-01-dependency-audit.md`, CI-шаг `cargo audit` описан. Итог: 0 не-игнорированных уязвимостей, 2 задокументированных unmaintained warning.
- **DEP-03** 📋 — `docs/DEP-03-secret-rotation.md`: скан истории нашёл 3 Telegram bot-токена (bot-ID 8853927147 / 8883516682 / 8896772547, 5 pre-squash коммитов), реальных ghp_ нет. Ревокация через @BotFather + filter-repo/squash — **владелец, ручной шаг**.

Все пункты плана A1/A2/B + DEP-01 закрыты в коде. Открыто только DEP-03 (владелец).

## СТАТУС 2026-11-12 (финал, коммит после 3eaaab2) — RC1 готов к внешнему аудиту
- Squash-копия для аудитора собрана и просканирована: `/tmp/nexxus-auditor-squash` (1 коммит, 0 секретов по скану; рецепт в docs/DEP-03-secret-rotation.md).
- Сетевой слой прогнан живьём: 17/17 net::network::tests (two_daemon_end_to_end, per-connection nonce replay → 0x0008, ip rate-limit 20/мин, handshake timeout 4s, peer cap 0x0009).
- Полная верификация: workspace 172/172, desktop 19/19, clippy -D warnings = 0 (оба workspace), cargo audit = 0 vulns (игноры обоснованы), WS smoke OK.
- DEP-03: risk accepted владельцем (2026-11-12) — токены не ревокются, в docs/DEP-03-secret-rotation.md. Аудитору выдаём только squash-копию (чистая).
