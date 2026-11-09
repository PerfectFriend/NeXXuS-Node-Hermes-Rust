# NeXXus v3 — план эволюции (после полной ревизии 09.11.2026)

> Основан на аудите: `docs/audits/2026-11-09-full-project-review.md`. Старый план (`2026-11-05_2315-nexxus-monitor-evolution.md`) частично выполнен (Task 1–2) и пересмотрен: автозагрузка/демон отложены по условию владельца — запуск монитора только из .desktop-ярлыка, single-instance через lock-файл.

**Goal:** из рабочего ядра + надёжного монитора сделать законченный продукт: безопасный локальный API, шифрование at rest, панельный дашборд, онбординг/бэкапы, видимость экономики, релизы под все платформы.

**Architecture:** монитор (Tauri, трей) остаётся единой точкой управления; нода — дочерний процесс (systemd-юнит — опция). Все новые поверхности добавляются как панели дашборда поверх существующих WS-команд; новый функционал ноды — новые методы `local_api.rs`, никогда mutation напрямую из UI. Безопасность идёт первой фазой, т.к. закрывает реальные дыры (API без токена, стор в открытом виде).

**Tech Stack:** Rust 2021 (workspace: core/node/econ/wasm + nexxus-desktop Tauri 2), tokio, tokio-tungstenite, redb, arti-client, serde_json; фронт монитора — vanilla ES-модули + Vite; TS-приложение в `src/` — отдельная поверхность; FunC-контракты в `contracts/`.

**Spec:** `NEXXUS_SPECIFICATION_V2.md` (ТЗ), `docs/adr/0000–0008`, ревизия `docs/audits/2026-11-09-full-project-review.md`.

## Global Constraints

- Секреты (токены, chat id, сид-фразы) — никогда в репозиторий/логи/ps; только `~/.hermes/secrets/*` (0600) и env. В UI сид показывается один раз с подтверждением, в буфер обмена — по явной кнопке.
- Сборка: `source ~/build/env.sh`, `CARGO_TARGET_DIR=/home/thomas/build/cache/cargo-target-nexxus` (у каждого Rust-проекта свой target-dir).
- Ворота каждой задачи: `cargo test` (все зелёные), `cargo clippy --workspace --all-targets -- -D warnings` = 0, `cargo build --release` = 0, живой смоук где применимо; фронт: `node --test` для чистых функций + `npm run build`.
- Классификация находок: broken / dead / unbuilt — unbuilt не считается дефектом. `#[allow(dead_code)]` не является решением — или в проводку, или удалить.
- Коммиты частые, по задаче; пуш в `origin/main` (PerfectFriend/NeXXuS-Node-Hermes-Rust).
- Русский язык в UI и документации.

## Review Focus (что чаще всего ломается)

1. Секрет в ps/логе при передаче сид-фразы — передавать через env/file, не аргумент.
2. ГонкиParallel-тестов на общем env/файле — явные пути в тестах.
3. Повторный запуск монитора из ярлыка — single-instance lock (уже есть, тесты должны покрывать).
4. API без токена после рефакторинга — негативный тест: запрос без токена → отказ.
5. «Панель нарисована, команда не вызывается» — тест-соответствие: все `invoke('..._cmd')` из фронта ∈ зарегистрированные команды Tauri.

---

## Phase A — Безопасность узла и API (фундамент, закрывает реальные дыры)

### Task A1: Токен-аутентификация локального WS API
- **Files:** Modify `crates/nexxus-node/src/local_api.rs`, `crates/nexxus-node/src/main.rs`; Create `crates/nexxus-node/src/api_auth.rs`; Modify `nexxus-desktop/src-tauri/api_client.rs`.
- **Interfaces:** `api_auth::Token::generate() -> String` (32 байта CSPRNG, hex), хранение в `~/.nexxus/api.token` (0600, создаётся при первом старте); handshake: клиент шлёт `{"method":"auth","token":...}` первой рамкой, до успеха — только `auth` и `ping`; `LocalApi::set_token(...)`.
- **Steps:** тест `ws_call_without_token_rejected` (подключиться, вызвать node_status без токена → ErrorResponse/close) → FAIL → реализация → PASS; негативный тест с неверным токеном; монитор читает токен из файла и передаёт в handshake; `cargo test -p nexxus-node`, clippy, смоук `test-api-client` с токеном → 200/ok. Commit `feat(node): token auth for local WS API`.

### Task A2: Шифрование store.redb at rest
- **Files:** Modify `crates/nexxus-node/src/storage.rs`, `vault.rs`; Create `crates/nexxus-node/src/at_rest.rs`.
- **Interfaces:** ключ стора выводится из seed (HKDF-SHA256, info="nexxus-store-v1"); значение чанка шифруется XChaCha20-Poly1305 с nonce = chunk_hash; redb хранит только ciphertext+tag; миграция: при открытии существующего открытого стора — один проход re-encrypt (прогресс в лог), флаг в метаданных стора.
- **Steps:** тест `store_roundtrip_encrypted_on_disk` (записать чанк, прочитать сырой файл redb — не содержит plaintext; прочитать через API — Ok) → FAIL → реализация → PASS; тест миграции на фиктивном сторе; clippy; смоук upload/download поверх зашифрованного стора. Commit `feat(node): encrypted-at-rest chunk store`.

### Task A3: Panic PIN (dual-PIN, экспоненциальный кулдаун) по спецификации §5
- **База уже вендорена**: `crates/nexxus-core/src/keys/vault.rs` — AES-256-GCM vault с duress-PIN, формат JSON совместим с `BIP39-ABOARD-SDK` (PerfectFriend/BIP39-Onboarding-pipeline, Apache-2.0, наш репо): поле `kdf_rounds` — новые vault пишем 600k (OWASP 2023), старые vault SDK без поля читаем со 100k (тест `sdk_vault_without_kdf_rounds_opens_with_100k`). `check_pin` → `PinCheck::{Ok,Duress,Wrong}`.
- **Files:** Create `crates/nexxus-node/src/panic.rs`; Modify `local_api.rs` (методы `panic_arm`, `panic_enter`, `panic_status`), `identity_store.rs` (duress-wipe: затирание seed + store, необратимо); UI позже (Phase B).
- **Interfaces:** кулдаун удваивается при каждой ошибке (1 мин → 2 → 4 … cap 24 ч), сброс только верным PIN; duress-PIN → wipe + ложный успех. Состояние кулдауна — в `~/.nexxus/panic.state` (не в vault).
- **Steps:** тесты кулдауна и wipe (на копии стора во временной dir); API-тест: 3 неверных PIN подряд → кулдаун растёт; clippy; commit `feat(node): panic PIN with exponential cooldown and duress wipe`.

### Task A4: Hygiene памяти и процессов
- `zeroize` для seed/keys в памяти (добавить dep `zeroize`), запрет дампа core (`setrlimit` через libc уже в дереве зависимостей tokio — добавить прямой dep), сид не в аргументах CLI (уже env), логи не содержат секретов (тест-скан логов). Commit `chore(node): zeroize secrets, no core dumps`.

## Phase B — Дашборд монитора v2 (оживляет 8 мёртвых команд + панели)

### Task B1: Каркас вкладок и роутер панелей
- **Files:** Modify `nexxus-desktop/src/index.html`, `main.js`, `style.css`; Create `src/views/*.js`, `src/format.js`; Create `nexxus-desktop/tests/format.test.mjs` (`node --test`).
- **Interfaces:** чистые функции в `format.js` (formatUptime/formatBytes/statusClass), каждая панель — модуль с `render(el, state)`; авто-обновление 5 с; тест-соответствие: `grep invoke` из всех view == команды в `generate_handler!` (скрипт-проверка в тесте).
- **Steps:** JS-тесты format → FAIL → PASS; панель Overview (статус, аптайм, тор, пиры) поверх `guardian_status_cmd`; `npm run build` = 0; commit `feat(ui): tab shell + overview panel`.

### Task B2: Панель «Нода и конфиг» — оживляет node_config_* и node_install_*
- Панели: форма конфига (listen/api/tor/auditors/threshold/epoch) с валидацией через `node_config_validate_cmd` и сохранением `node_config_set_cmd` + рестарт ноды; статус установки юнита (`node_install_status_cmd`) и кнопки install/uninstall (`node_install_cmd`/`node_uninstall_cmd`); кнопка «Полное отключение» в UI дублирует `guardian_shutdown_cmd`.
- Тест: мок `window.__TAURI__.invoke` — рендер вызывает ожидаемые команды; commit `feat(ui): node config + install panel (wires dead commands)`.

### Task B3: Панели Network / Storage / Logs / Tor / Epoch
- Network: пиры (`node_peers`), dial onion, connect, pause/resume (`node_pause`/`node_resume`); Storage: chunks, upload/download с прогрессом, PoR (`node_por`), benchmark; Logs: tail `~/.nexxus/nexxusd.log` (новая команда `node_log_tail` в local_api); Tor: статус/onion (`node_tor`, `node_dial_onion`); Epoch: текущая эпоха, merkle root, `node_epoch`, история finalize.
- Каждая панель: свой view + команда; тесты валидации ввода (адрес пира, onion) как в старом плане; commit по панели.

## Phase C — Онбординг и идентичность

### Task C1: Машина состояний онбординга (персистентная)
- `nexxus-desktop/src-tauri/onboarding.rs`: `StepId` (Welcome → Identity → Store → Network → Notifications → Done), состояние в `~/.nexxus/onboarding.json`, `advance` идемпотентен и отклоняет пропуски; тесты как в старом плане Task 3. Commit `feat(desktop): onboarding state machine`.

### Task C2: BIP39 регистрация/восстановление/экспорт в UI
- В `identity_store.rs`: `export_mnemonic(confirm: bool)`, `import_mnemonic` (отказ на чужую фразу поверх существующего стора); проброс в API (`node_identity_export` с подтверждением, сид — только в ответе один раз, не в лог); UI: генерация 12/24 слов, ввод при восстановлении, QR-код сида (qrcode в dev-deps фронта), чекбокс «я записал».
- **Вендорено из нашего репо BIP39-Onboarding-pipeline**: `crates/nexxus-core/src/keys/verification.rs` — `generate_verification_challenges` (3 вопроса «какое слово под номером N», 4 дистрактора из wordlist, retry с другими позициями) + `check_challenge`; UI онбординга использует их вместо своей логики.
- Тесты: roundtrip node_id, отказ без confirm, challenges: 3 позиции/5 вариантов, retry исключает прежние. Commit `feat: BIP39 register/restore/export + verification challenges`.

### Task C3: Зашифрованный бэкап сид-фразы
- Используем вендоренный `keys::vault`: `encrypt_vault_payload(seed_json, pin, Some(duress_pin))` → `seed.vault` рядом со стором (AES-256-GCM, PBKDF2 600k, формат совместим с BIP39-ABOARD-SDK); восстановление — `decrypt_vault_payload`, duress → ложный успех + сигнал в лог/Telegram. Тесты roundtrip + отказ при неверном PIN + tamper → AeadAuthFailed. Commit `feat(desktop): encrypted seed vault backup (SDK-compatible)`.

## Phase D — Бэкапы, восстановление, self-heal

### Task D1: Снапшоты store + конфига с проверкой целостности
- Новая команда API `node_backup` (redb snapshot → tar.zst? без новых тяжёлых dep: redb online backup API + gzip через flate2 если уже в дереве, иначе plain copy с quiesce), манифест с merkle root стора; восстановление `node_restore` с верификацией манифеста. Тесты: бэкап → порча файла → restore отказывает; бэкап → restore на чистый стор → node_id совпадает. Commit `feat(node): verified store backups/restore`.

### Task D2: Автобэкап в мониторе + 3-2-1
- Планировщик в guardian: раз в N часов (конфиг), ротация (хранить K последних), копия на внешний носитель если примонтирован (`/run/media/...`), отчёт в Telegram. Тесты планировщика на фиктивных часах. Commit `feat(desktop): scheduled encrypted backups with rotation`.

### Task D3: `nexxusd doctor` — самодиагностика
- CLI-команда: проверка портов, прав на файлы, целостности стора, Tor, диска, памяти; вывод отчётом; монитор показывает результат в панели здоровья. Commit `feat(cli): nexxusd doctor self-check`.

## Phase E — Экономика и эпохи: видимость

### Task E1: Панель экономики
- API: `node_econ` — vesting progress (vested/unvested, дней до полной), секции (split_into_sections), health/degradation (offline hours → Health), анти-луп инвариант (anti_loop_invariant_holds) как индикатор; UI: прогресс-бар вестинга, карточки секций, health-meter. Тесты уже в econ; нужен только проброс + UI-тесты. Commit `feat(ui): economics panel (vesting, sections, health)`.

### Task E2: Эпоха и аудиторы
- `node_epoch` расширить: номер, merkle root, total_bytes, список auditor-подписей (verify_epoch_finalize → EpochVerifyResult), история последних N эпох из стора; UI таймлайн. Multisig (ADR 0008): статус кворума (сколько из auditorов подписали), без ончейн-интеграции пока. Commit `feat: epoch timeline + auditor quorum status`.

## Phase F — Сеть и парк узлов

### Task F1: Качество пиров и лимиты
- Скоринг пиров (успешные fetch/Por, latency из `node_test_interhost`), чёрный/белый списки, лимит скорости (token bucket) в конфиге; UI: таблица пиров со скорингом. Commit `feat(node): peer scoring + bandwidth caps`.

### Task F2: Fleet view — несколько узлов из одного монитора
- Монитор управляет N узлами: конфиги `~/.nexxus/nodes/<name>.conf`, переключение в UI, агрегированный статус; удалённый узел по onion (`node_dial_onion` + API поверх onion через arti). Commit `feat(desktop): multi-node fleet view`.

### Task F3: Удалённый доступ к дашборду через onion (опционально, с токеном)
- Монитор поднимает скрытый сервис (arti) для своего HTTP, доступ только с api-token; предупреждение в UI о риске. Commit `feat(desktop): optional onion-exposed dashboard (token-gated)`.

## Phase G — Качество, CI, релизы

### Task G1: Rust в CI
- `.github/workflows/ci-release.yml`: добавить job `cargo test --workspace`, `cargo clippy --workspace --all-targets -- -D warnings`, `cargo build --release --workspace`, `cargo build -p nexxus-desktop --release`; артефакты (nexxusd, nexxus-desktop) в release. Commit `ci: run cargo test/clippy/build`.

### Task G2: Fuzz + proptest
- proptest для RS encode/decode (любые k из n восстанавливают), merkle proof verify, wire parser (любой байтовый ввод не падает); cargo-fuzz цель для `wire::reader` (offline-локально, без CI-fuzz пока). Commit `test: property + fuzz tests for wire/rs/merkle`.

### Task G3: Golden vectors на все опкоды + кросс-импл паритет
- Расширить `nexxus-vectors/` векторами на каждый опкод (0x01–0x0D); тест в Rust читает те же JSON, что и TS (`test/golden-vectors.test.ts`) — один источник правды. Commit `test: golden vectors for all wire opcodes, shared Rust/TS`.

### Task G4: Self-update с верификацией подписи
- `nexxusd update`: скачать релиз с GitHub, проверить ed25519-подпись (публичный ключ в коде), atomic replace (rename), rollback при падении после апдейта. Commit `feat(node): signed self-update with rollback`.

### Task G5: Пакеты и платформы
- .deb уже в CI; добавить AppImage/Flatpak (Linux), MSI/InnoSetup (Windows, фазы W3–W4 roadmap), Windows tray companion (W5), Android APK (A2–A4). Каждая — отдельная задача с smoke на целевой платформе. Commit по платформе.

## Phase H — Мессенджер (SMP) как продукт

### Task H1: Inbox и контакты
- API: `smp_inbox` (pending envelopes из SmpRelay), `smp_send`; UI: список контактов (node_id + label), QR-обмен контактами (спецификация §7: `nexxus://add/<node_id>?sig=...`), отправка envelope, TTL-индикатор, read receipts. Commit `feat: SMP inbox UI + QR contact exchange`.

---

## Что изменилось относительно старого плана (записано, чтобы не наследовать ошибки)

1. Task 2 старого плана (нода как systemd-юнит по умолчанию) — **отложено владельцем**: запуск из .desktop-ярлыка, single-instance lock обязателен (обнаружено: без него «Остановить» не работала). Юнит остаётся опцией в UI.
2. Telegram-клиент без таймаута ломал «Полное отключение» — теперь таймауты 5/10 с + жёсткий timeout 15 с вокруг shutdown.
3. Тесты с общим env (`NEXXUS_CONFIG_DIR`) падали в parallel — явные пути `load_from`/`save_to`.
4. Stop ноды по шаблону `nexxusd.*store.redb` промахивался — теперь матч по пути бинаря + `systemctl stop` для юнит-варианта.

## Порядок выполнения

A1 → A2 → A3 → A4 → B1 → B2 → B3 → C1 → C2 → C3 → D1 → D2 → D3 → E1 → E2 → F1 → F2 → F3 → G1 → G2 → G3 → G4 → G5 → H1. Phase A обязателен первой: она закрывает реальные дыры безопасности до наращивания UI.
