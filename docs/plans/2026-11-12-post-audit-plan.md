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
