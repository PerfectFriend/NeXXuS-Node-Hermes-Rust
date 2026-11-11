# NeXXus-Node — подготовка к внешнему аудиту (2026-11-11)

Репозиторий: `PerfectFriend/NeXXuS-Node-Hermes-Rust` (private), ветка `main`, HEAD на момент аудита см. в git.
Язык: Rust (workspace: `nexxus-core`, `nexxus-econ`, `nexxus-node`, `nexxus-wasm`) + Tauri desktop (`nexxus-desktop`). ~15k строк. `unsafe` = 0.

## Как поднять и проверить (5 минут)
```bash
git clone <repo> && cd NeXXus-Node
source ~/build/env.sh            # toolchain (или свой: rust 1.8x, node 24)
CARGO_TARGET_DIR=$PWD/target cargo test --workspace        # 157 тестов
CARGO_TARGET_DIR=$PWD/target cargo clippy --workspace --all-targets -- -D warnings   # 0
cd nexxus-desktop && npm test && npm run build              # 5/5
CARGO_TARGET_DIR=$PWD/target cargo build --release --bin nexxusd
NEXXUS_TOR=0 ./target/release/nexxusd /tmp/test-store.redb  # P2P :4001 (0.0.0.0), WS API 127.0.0.1:4010
# токен API: ~/.nexxus/api.token (0600); первый WS-кадр обязан быть {"method":"auth","params":{"token":...}}
```

## Карта поверхности атаки
| Поверхность | Где | Защита |
|---|---|---|
| P2P TCP (wire v3, length-delimited) | `crates/nexxus-node/src/net/` | Ed25519 подпись каждого фрейма после верифицированного NodeAnnounce; лимит фрейма 4 MiB **до** аллокации (фикс ниже); pause-gate |
| Local WS API 127.0.0.1:4010 | `local_api.rs`, `api_auth.rs` | fail-closed token auth (create_new 0600), constant-time compare (фикс ниже), только `ping` без auth |
| Store (redb) at rest | `at_rest.rs`, `storage.rs` | XChaCha20-Poly1305, ключ из seed; nonce = SHA-256(payload)[..24] — инвариант: put_chunk верифицирует hash и никогда не перезаписывает (фикс ниже) |
| Seed vault | `seed_vault.rs`, `core/keys/vault.rs` | AES-256-GCM, PBKDF2-HMAC-SHA256 600k, random salt+nonce, duress-PIN, zeroize, 0600 |
| Бэкапы стора | `backup.rs` | manifest sha256+merkle, verify на tmp-копии, staged restore, имя валидируется (`/`, `..` запрещены) |
| Desktop/guardian (Tauri) | `nexxus-desktop/src-tauri/` | single-instance lock, pgrep/pkill по regex `(^|/)nexxusd( |$)`, WS к ноде с токеном |
| CI | `.github/workflows/ci-release.yml` | tests+clippy на 2 фичах (tor on/off), deb-артефакты, релиз по тегу v* |

## Найдено и исправлено в этой сессии аудита (с доказательствами)
1. **CRITICAL (было): remote memory-exhaustion** — `recv_frame` аллоцировал `vec![0; len]` до проверки `MAX_FRAME_LEN`. Доказано живьём: `len=0xFFFFFFFF` → VSZ процесса 5.3 GB. Фикс: проверка до аллокации + юнит-тест. Ретест: 10 соединений × 4 GiB → VSZ не изменился, API живо.
2. **CRITICAL (было): нет верификации chunk hash + перезапись по hash** — пир мог записать чужой hash с другим plaintext; при nonce=hash[..24] это nonce reuse с разным plaintext (крах AEAD). Фикс: `put_chunk` проверяет SHA-256(data)==hash и дедуплицирует (no-overwrite); тесты `put_chunk_rejects_hash_mismatch`, `put_chunk_never_overwrites_existing_hash`.
3. **MEDIUM: timing-leak при сравнении API токена** — `==` на строках → constant-time через `subtle::ConstantTimeEq`.
4. **LOW: guardian match-паттерн** не ловил `/usr/bin/nexxusd` → regex `(^|/)nexxusd( |$)`.

## Живые security-пробы (все зелёные, против живой ноды)
- `node_status` без auth → `-32001 requires auth` + соединение закрыто (fail-closed).
- `auth` с неверным токеном → `-32001` + close.
- `node_backup_verify {name:"../../etc"}` и `".."`, `"a/b"` → `bad backup name`.
- `node_identity_export` без `confirm:true` → отказ; `node_seed_restore` с неверным PIN → `wrong_pin`.
- Неизвестный метод → `-32601`.
- API слушает только 127.0.0.1; P2P 0.0.0.0:4001 (по замыслу, входящие пиры).

## ⚠️ Секреты в истории git — требует решения владельца
`git log --all -S` находит в истории: GitHub PAT (`ghp_…`, коммиты `26f817f`, `50b925c` и др.), упоминания `BOT_TOKEN` (~270), `sk-` (~381), `BEGIN RSA` (2). HEAD чистый (скан 0 находок), но история — нет.
**Действия: (а) ревокировать все найденные токены у провайдеров; (б) очистить историю (`git filter-repo` / BFG) перед любым внешним доступом, либо дать аудитору read-only доступ к свежему squash-репо.** Значения здесь не печатаем.

## Список вопросов к аудитору (куда смотреть в первую очередь)
1. **Крипто**: nonce = hash-derived в at_rest — инвариант держится за счёт верификации hash + no-overwrite в put_chunk. Есть ли путь записать чанк в обход put_chunk (миграция re-encrypt, restore/swap, legacy-импорт)? Проверьте `enable_encryption` миграцию: перешифровка существующих чанков использует тот же nonce — это ок (тот же plaintext), но подтвердите.
2. **Wire v3**: `parse_v3` — валидация opcode, request_id, длины payload против opcode; что происходит с `Opcode::StoreChunk` больше 4 MiB после лимита; rate limiting / лимит соединений с одного IP на 4001 (сейчас нет — DoS-вектор по CPU на верификацию подписей).
3. **Auth API**: replay/lingeр после auth на одном соединении — ок ли, что соединение остаётся открытым после успешного auth; нет ли лимита попыток auth на соединение (сейчас 1 — ок); WS message size limit в tokio-tungstenite (max_frame_size default 16 MiB? проверьте, что не 64 MiB+).
4. **Seed vault**: kdf_rounds миграция (старый vault с меньшим числом итераций — принимается ли? `kdf_rounds` в метаданных); duress-PIN — что именно происходит (алерт + отказ); zeroize покрытия (PIN в String?).
5. **Бэкапы**: TOCTOU между verify и swap (`nexxusd restore` при остановленном демоне — кто гарантирует остановку?); права на `backups/` dir; merkle в manifest — покрывает ли store_file целиком.
6. **Econ**: анти-луп инвариант 1.30>1.25 — целочисленная арифметика в micro-NEXX, нет ли overflow при больших объёмах; вестинг 56д — что с烧录ом при offline >28 дней.
7. **Guardian (desktop)**: lock-файл single-instance — race при старте двух копий; Telegram-токен хранится в `~/.nexxus/telegram.json` 0600 — подтвердите, нигде не логируется; команды в systemd unit — инъекция через конфиг?
8. **Tor (arti)**: onion service key хранение, `NEXXUS_TOR=0` действительно отключает; bootstrap узлы захардкожены?
9. **Зависимости**: `cargo audit` не прогонялся в этой сессии (инструмент не установлен) — прогоните; ручная сверка: aes-gcm 0.10.3, chacha20poly1305 0.10.1, ed25519-dalek 2.2.0, redb 2.6.4, tokio 1.54.1, openssl 0.10.82, два rand (0.8.8 + 0.10.3 — зачем два?).
10. **Память/секреты в памяти**: mnemonic в String без zeroize в некоторых путях? (проверьте identity_store/seed_vault на Zeroize у временных буферов).

## Что НЕ проверено (честно)
- cargo audit / cargo deny (нет инструмента локально) — см. вопрос 9.
- Fuzz wire-парсера (proptest/fuzz не настроен).
- Двухнодовый sync под реальной нагрузкой — только loopback тесты.
- Windows-сборка (CI только ubuntu).
- Istoriya git на секреты — см. выше, требует rotation.

## Известные ограничения дизайна (не баги)
- Local API на localhost без TLS — защита токеном; любой локальный процесс с доступом к `~/.nexxus/api.token` (0600) имеет полный доступ. Это осознанный trust boundary: user-level.
- P2P порт открыт наружу (0.0.0.0:4001) — по дизайну; защита — подписи Ed25519.
