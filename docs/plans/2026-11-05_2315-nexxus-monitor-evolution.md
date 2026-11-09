# NeXXus Node Monitor — Полная эволюция (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Превратить NeXXus Node Monitor из «сторожевого панно» в полноценный центр управления нодой: установка монитора → онбординг ноды (BIP39-регистрация/восстановление сид-фразой) → полный контроль всех настроек, сети, данных, экономики, журналов, бэкапов и уведомлений.

**Architecture:** Монитор (Tauri 2 + Rust-guardian + vanilla-JS/Vite фронтенд) — единственная точка управления нодой. Rust-слой guardian говорит с нодой по локальному WebSocket JSON-RPC (`ws://127.0.0.1:4010`, 16 методов) и напрямую управляет процессом `nexxusd`, его unit-файлом и конфигом. Фронтенд разбивается на вкладки-панели, каждая — тонкий слой над Tauri-командами. Установка ноды выполняется **из дашборда**: монитор ставится первым, нода — через мастер онбординга.

**Tech Stack:** Rust 2021, Tauri 2 (`tray-icon`, `custom-protocol`), tokio, tokio-tungstenite, serde_json, redb, arti-client (Tor v3), Vite 5, vanilla ES-модули, systemd --user, Telegram Bot API.

**Spec:** этот документ (спека и отдельного design-doc в проекте нет).

---

## Global Constraints

- Сборка Rust только с изолированным target: `CARGO_TARGET_DIR=/home/thomas/build/cache/cargo-target-nexxus` — общий `cargo-target` делить с W420 нельзя (уже теряли `nexxusd`).
- В `nexxus-desktop/Cargo.toml` обязан остаться feature `custom-protocol` — без него tauri-build ставит `cfg(dev)` даже в release, и webview грузит `http://localhost:1420` → «Connection refused» + белый экран.
- Секреты (токен Telegram, seed-фраза) никогда не пишутся в логи, отчёты, git и файлы репозитория. Токен читается из `NEXXUS_TG_BOT_TOKEN`, иначе из `~/.hermes/secrets/cathedral_bot_token` (600, вне git). Seed-фраза показывается ровно один раз и только по явному действию пользователя.
- Пути ноды: store `~/.nexxus/store.redb`, лог `~/.nexxus/nexxusd.log` (переопределяется `NEXXUS_LOG`), Tor-каталог `~/.nexxus/tor`.
- Дефолты ноды: P2P `127.0.0.1:4001` (`NEXXUS_LISTEN`), API `127.0.0.1:4010` (`NEXXUS_API_ADDR`), epoch 300 c (`NEXXUS_EPOCH_SECS`), комитет deny-by-default (`NEXXUS_AUDITORS` + `NEXXUS_THRESHOLD`), Tor включён (`NEXXUS_TOR=0` выключает).
- Все env-параметры ноды: `NEXXUS_LISTEN`, `NEXXUS_API_ADDR`, `NEXXUS_AUDITORS`, `NEXXUS_THRESHOLD`, `NEXXUS_EPOCH_SECS`, `NEXXUS_TOR`, `NEXXUS_LOG`, `NEXXUS_SPECIFICATION_V`.
- CLI-контракт ноды не ломаем: `nexxusd serve|init|id|status|peers|peer add|peer dial-onion|upload|download|test-por|test-interhost|logs|benchmark`.
- WS-контракт ноды не ломаем: `node_status, node_peers, node_chunks, node_smp, node_epoch, node_tor, node_pause, node_resume, node_connect, node_dial_onion, node_upload, node_download, node_por, node_test_interhost, node_id`.
- Верификация каждой фазы: `cargo test --workspace` (0 failed), `cargo clippy --workspace --all-targets` (0 warnings), `cargo build --release`, `npm run build` в `nexxus-desktop`, живой смоук через `test-api-client`.
- Коммиты делаются в `~/Projects/NeXXus-Node` (ветка `main`, origin `PerfectFriend/NeXXuS-Node-Hermes-Rust`), пуш — ребейзом, по прямой просьбе владельца.
- Rust-код и JS — на русском в комментариях и UI, английский в именах символов.

## Review Focus

- Токен Telegram попадает в лог/отчёт/буфер обмена при ошибке отправки — пользователь ожидает, что секрет не покинет `~/.hermes/secrets/`.
- Seed-фраза BIP39 показывается повторно после рестарта или в дашборде без явного действия — пользователь ожидает «показать один раз», как в `nexxusd init`.
- Юнит systemd для ноды перезапускает ноду при падении, но монитор уже запущен — пользователь ожидает, что монитор не создаёт второй процесс ноды.
- Восстановление из seed-фразы на существующем сторе должно быть refuse-по-умолчанию (иначе node_id молча меняется) — пользователь ожичает явного подтверждения с показом старого и нового node_id.
- Бэкап > 2 ГБ или занятый store-локом во время копирования — пользователь ожидает, что бэкап либо создаётся целиком, либо явно падает без повреждения источника.

---

## File Structure

**Монитор (новые/изменяемые):**
- `nexxus-desktop/src-tauri/guardian.rs` — процесс-менеджмент, health-loop, конфиг ноды, бэкапы (расширяется).
- `nexxus-desktop/src-tauri/commands.rs` — все Tauri-команды монитора (сейчас пустой, команды в `main.rs` — переносим сюда).
- `nexxus-desktop/src-tauri/main.rs` — точка входа, трей, регистрация команд.
- `nexxus-desktop/src-tauri/telegram.rs` — уведомления (расширяется: события онбординга, бэкапа, конфига).
- `nexxus-desktop/src-tauri/api_client.rs` — WS-клиент к ноде.
- `nexxus-desktop/src-tauri/onboarding.rs` — **новый**: машина состояний первичной настройки.
- `nexxus-desktop/src-tauri/backup.rs` — **новый**: бэкап/восстановление store+конфига.
- `nexxus-desktop/src-tauri/node_config.rs` — **новый**: чтение/запись конфига ноды (`~/.nexxus/node.conf`), env-маппинг.
- `nexxus-desktop/src/main.js` — **новый**: шина вкладок, роутер панелей, авто-обновление.
- `nexxus-desktop/src/views/*.js` — **новые**: по панели на файл (`overview.js`, `onboarding.js`, `network.js`, `storage.js`, `epoch.js`, `tor.js`, `logs.js`, `settings.js`, `backup.js`, `security.js`).
- `nexxus-desktop/src/index.html` — каркас с вкладками.
- `nexxus-desktop/src/style.css` — тема и сетка.
- `deploy/nexxus-monitor.service` — **новый**: unit для ноды (монитор управляет им).
- `deploy/desktop/NeXXus-Node-Monitor.desktop` + `deploy/desktop/nexxus-desktop-launch` — запуск монитора из ярлыка рабочего стола (по новому условию: без автозагрузки/systemd, однократный запуск через lock-файл, действие Quit шлёт `--shutdown`).

**Нода (изменяемые):**
- `crates/nexxus-node/src/local_api.rs` — добавить методы `node_config`, `node_log_tail`, `node_identity_export` (seed по явному флагу), `node_backups`.
- `crates/nexxus-node/src/identity_store.rs` — экспорт seed по требованию.
- `crates/nexxus-node/src/storage.rs` — бэкап/целостность стора.

---

## Phase 0 — Фундамент: команды и конфиг (Task 1–2)

### Task 1: Вынести все Tauri-команды в `commands.rs` и добавить слой конфига ноды

**Files:**
- Create: `nexxus-desktop/src-tauri/commands.rs` (перенести 7 команд из `main.rs`)
- Create: `nexxus-desktop/src-tauri/node_config.rs`
- Modify: `nexxus-desktop/src-tauri/main.rs`
- Test: `nexxus-desktop/src-tauri/node_config.rs` (модульные тесты `#[cfg(test)]`)

**Interfaces:**
- Produces: `node_config::NodeConfig { listen: String, api: String, auditors: Vec<String>, threshold: usize, epoch_secs: u64, tor: bool, spec_version: String, log_path: String }`
- Produces: `node_config::load() -> NodeConfig` (дефолты + `~/.nexxus/node.conf`, TOML-подобный `key=value`)
- Produces: `node_config::save(&NodeConfig) -> Result<(), String>` (атомарно: temp + rename, режим 0600)
- Produces: `node_config::to_env(&NodeConfig) -> Vec<(String, String)>` — env для запуска `nexxusd`
- Produces: Tauri-команды `node_config_get_cmd`, `node_config_set_cmd`

- [ ] **Step 1: Написать падающие тесты** в `node_config.rs`:
  `default_config_has_loopback_ports` (listen `127.0.0.1:4001`, api `127.0.0.1:4010`), `save_then_load_roundtrip`, `to_env_emits_auditors_and_threshold`, `invalid_threshold_rejected`.
- [ ] **Step 2:** `cd ~/Projects/NeXXus-Node/nexxus-desktop && source ~/build/env.sh && CARGO_TARGET_DIR=/home/thomas/build/cache/cargo-target-nexxus cargo test --manifest-path Cargo.toml node_config` → FAIL (модуля нет).
- [ ] **Step 3:** Реализовать `node_config.rs` (без новых зависимостей; парсер `key=value` вручную), перенести команды в `commands.rs`, в `main.rs` подключить `mod commands; mod node_config;` и зарегистрировать новые команды в `generate_handler!`.
- [ ] **Step 4:** Тот же `cargo test` → PASS; `cargo clippy --manifest-path Cargo.toml --all-targets -- -D warnings` → 0 предупреждений.
- [ ] **Step 5: Commit** `feat(desktop): конфиг ноды и слой Tauri-команд`.

### Task 2: Монитор управляет запуском ноды через конфиг и unit-файл

**Files:**
- Create: `deploy/nexxus-monitor-node.service`
- Modify: `nexxus-desktop/src-tauri/guardian.rs`
- Modify: `nexxus-desktop/src-tauri/commands.rs`

**Interfaces:**
- Consumes: `node_config::to_env`, `node_config::load`
- Produces: `guardian::spawn_node_with(cfg: &NodeConfig) -> Result<(), String>` — запуск `nexxusd` с env из конфига
- Produces: `guardian::install_node_unit(paths: &NodePaths) -> Result<(), String>` — пишет `~/.config/systemd/user/nexxus-node.service` и делает `systemctl --user daemon-reload`
- Produces: Tauri-команды `node_install_cmd`, `node_uninstall_cmd`

- [ ] **Step 1:** Тест в `guardian.rs`: `unit_file_contains_env_and_exec` — сгенерированный unit содержит `ExecStart=<nexxusd>`, `Environment=NEXXUS_LISTEN=...`, `Restart=on-failure`.
- [ ] **Step 2:** Запустить тест → FAIL.
- [ ] **Step 3:** Реализовать: генерация unit-текста, запись в `~/.config/systemd/user/`, `daemon-reload`, `enable --now`; `spawn_node_with` заменяет текущий `start_nexxusd` (совместимость: старый вызов сохраняется как обёртка с дефолтным конфигом).
- [ ] **Step 4:** Тест → PASS; clippy → 0.
- [ ] **Step 5: Commit** `feat(desktop): монитор ставит и запускает ноду через systemd-unit`.

---

## Phase 1 — Онбординг и BIP39 (Task 3–4)

### Task 3: Онбординг-машина состояний в Rust

**Files:**
- Create: `nexxus-desktop/src-tauri/onboarding.rs`
- Modify: `nexxus-desktop/src-tauri/commands.rs`

**Interfaces:**
- Produces: `onboarding::Step { Id, State }` с `Id`: `CheckEnv, InstallBinary, InitStore, ChooseIdentity, Network, Storage, Tor, Start, Verify`
- Produces: `onboarding::state() -> Value` (текущий шаг, пройденные, пропущенные)
- Produces: `onboarding::advance(step: StepId, payload: Value) -> Result<Value, String>` — идемпотентно, проверяет предусловия
- Produces: Tauri-команда `onboarding_state_cmd`, `onboarding_advance_cmd`

- [ ] **Step 1:** Тесты: `first_run_requires_identity`, `advance_rejects_out_of_order_step`, `advance_init_store_creates_store_file`, `advance_is_idempotent`.
- [ ] **Step 2:** Тест → FAIL.
- [ ] **Step 3:** Реализовать: `StepId` enum + `Step` struct, `advance` с match по шагам, каждый шаг вызывает guardian/node_config; состояние переживает рестарт (файл `~/.nexxus/onboarding.json`).
- [ ] **Step 4:** Тест → PASS; clippy → 0.
- [ ] **Step 5: Commit** `feat(desktop): машина онбординга первичной настройки`.

### Task 4: BIP39-регистрация и восстановление сид-фразой

**Files:**
- Modify: `crates/nexxus-node/src/identity_store.rs` (экспорт seed по явному флагу + `node_identity_export`)
- Modify: `crates/nexxus-node/src/local_api.rs` (методы `node_identity_export`, `node_identity_status`)
- Modify: `nexxus-desktop/src-tauri/guardian.rs` (вызов `nexxusd init --mnemonic`, разбор вывода)
- Modify: `nexxus-desktop/src-tauri/commands.rs`

**Interfaces:**
- Produces WS: `node_identity_status {} -> {node_id, ed25519_pub, x25519_pub, has_seed: bool}`
- Produces WS: `node_identity_export {confirm: bool} -> {mnemonic: String}` — **только** при `confirm=true`, иначе ошибка
- Produces: `guardian::init_identity_with_seed(mnemonic: &str) -> Result<String, String>` — вызывает `nexxusd init --mnemonic "<...>" <store>`, возвращает node_id; **никогда** не пишет мнемонику в лог
- Produces: Tauri-команды `identity_status_cmd`, `identity_init_cmd`, `identity_export_cmd`

- [ ] **Step 1:** Тест в `identity_store.rs`: `export_requires_confirm` (без флага — ошибка), `import_rejects_foreign_phrase_on_existing_store`, `import_roundtrip_keeps_node_id`.
- [ ] **Step 2:** `cd ~/Projects/NeXXus-Node && cargo test -p nexxus-node identity` → FAIL.
- [ ] **Step 3:** Реализовать в `identity_store.rs` (`pub fn export_mnemonic(store, confirm) -> Result<String, NexxusError>`), пробросить в `local_api.rs`, в guardian — запуск CLI с мнемоникой через stdin-аргумент **без** попадания в `ps` (иначе секрет утечёт в список процессов): передавать через `NEXXUS_INIT_MNEMONIC` env.
- [ ] **Step 4:** Тест → PASS; clippy workspace → 0.
- [ ] **Step 5: Commit** `feat(node): экспорт/импорт BIP39-сида по явному подтверждению`.

---

## Phase 2 — Панели управления нодой (Task 5–9)

### Task 5: Обзор — единая панель состояния

**Files:**
- Create: `nexxus-desktop/src/views/overview.js`
- Modify: `nexxus-desktop/src/index.html`, `src/main.js`, `src/style.css`

**Interfaces:**
- Consumes: `guardian_status_cmd`, `node_status`, `node_chunks`, `node_epoch`, `node_tor`, `node_peers`
- Produces: DOM-секция `#view-overview` с плитками: node_id (с копированием), версия, аптайм, статус (Running/Paused/Offline), пиры, чанки/занято/свободно, epoch+quorum, Tor (onion-адрес + копирование), версия спецификации

- [ ] **Step 1:** Тест-логика в JS: `formatUptime(65000) === "1 м 5 с"`, `formatBytes(1536) === "1.5 КБ"`, `statusClass("Paused") === "warn"` (чистые функции в `src/format.js`, тест через `node --test`).
- [ ] **Step 2:** `cd nexxus-desktop && node --test tests/format.test.mjs` → FAIL (файла нет).
- [ ] **Step 3:** Реализовать `src/format.js`, `src/views/overview.js`, вкладку в `index.html`, авто-обновление раз в 5 c в `src/main.js`.
- [ ] **Step 4:** Тест → PASS; `npm run build` → exit 0.
- [ ] **Step 5: Commit** `feat(ui): панель обзора состояния ноды`.

### Task 6: Сеть — пиры, подключения, Tor

**Files:**
- Create: `nexxus-desktop/src/views/network.js`
- Modify: `nexxus-desktop/src-tauri/commands.rs` (`node_peers_cmd`, `node_connect_cmd`, `node_dial_onion_cmd`, `node_tor_cmd`, `node_pause_cmd`, `node_resume_cmd`)

**Interfaces:**
- Produces Tauri: `node_peers_cmd`, `node_connect_cmd {addr}`, `node_dial_onion_cmd {addr}`, `node_pause_cmd`, `node_resume_cmd`, `node_tor_cmd`
- UI: таблица пиров (node_id, addr, направление, время подключения), форма «добавить IP:PORT», форма «dial onion:PORT», кнопки пауза/резюм, карточка Tor с onion-адресом

- [ ] **Step 1:** JS-тест: `validatePeerAddr("1.2.3.4:4001") === true`, `validatePeerAddr("bad") === false`, `validateOnionAddr("abc.onion:4001") === true`.
- [ ] **Step 2:** Тест → FAIL.
- [ ] **Step 3:** Реализовать валидаторы + панель + Tauri-команды поверх `api_call`.
- [ ] **Step 4:** Тест → PASS; `npm run build` → 0.
- [ ] **Step 5: Commit** `feat(ui): панель сети (пиры, onion, пауза)`.

### Task 7: Хранилище — чанки, upload/download, PoR, бенчмарк

**Files:**
- Create: `nexxus-desktop/src/views/storage.js`
- Modify: `nexxus-desktop/src-tauri/commands.rs` (`node_chunks_cmd`, `node_upload_cmd {path}`, `node_download_cmd {root, out}`, `node_por_cmd`, `node_test_interhost_cmd {addr}`, `node_benchmark_cmd`)

**Interfaces:**
- Produces Tauri: перечисленные команды; `node_benchmark_cmd` запускает `nexxusd benchmark` и парсит JSON (write_mbps, read_mbps, merkle_4096_leaves_ms)
- UI: статистика чанков, таблица, форма загрузки файла (путь), форма скачивания по root-hex, кнопки PoR / interhost-тест / бенчмарк с выводом результата

- [ ] **Step 1:** JS-тест: `parseBenchmark('{"write_mbps":1}')` возвращает объект; битый JSON → `null`, без исключения.
- [ ] **Step 2:** Тест → FAIL.
- [ ] **Step 3:** Реализовать команду + панель; вывод бенчмарка и PoR — в `<pre id="tool-output">` с копированием.
- [ ] **Step 4:** Тест → PASS; clippy → 0; `npm run build` → 0.
- [ ] **Step 5: Commit** `feat(ui): панель хранилища, PoR, бенчмарк`.

### Task 8: Epoch, комитет аудиторов и экономика

**Files:**
- Create: `nexxus-desktop/src/views/epoch.js`, `nexxus-desktop/src/views/economy.js`
- Modify: `nexxus-desktop/src-tauri/commands.rs` (`node_epoch_cmd`, `node_econ_cmd`)

**Interfaces:**
- Produces WS (новое, в `crates/nexxus-node/src/local_api.rs`): `node_econ {} -> {sections: {foreign_gb, subscribed_gb}, daily_storer_reward, daily_subscription_cost, anti_loop_ok, vesting_days}` — считается через `nexxus-econ` (`sections.rs`, `vesting.rs`, `degradation.rs`)
- UI: epoch-панель (номер, merkle-root, байты, подписи/threshold, quorum-индикатор), панель экономики (секции, доход/расход, инвариант анти-лупа, вестинг 56 дней, деградация по офлайну)

- [ ] **Step 1:** Тест в `crates/nexxus-econ/src/sections.rs` уже есть (`anti_loop_invariant_holds`); новый тест в `nexxus-node`: `node_econ_reports_anti_loop_true`.
- [ ] **Step 2:** `cargo test -p nexxus-node node_econ` → FAIL.
- [ ] **Step 3:** Реализовать `handle_node_econ` в `local_api.rs` (используя `nexxus_econ::{sections, vesting, degradation}`), команды и панели.
- [ ] **Step 4:** Тест → PASS; clippy workspace → 0.
- [ ] **Step 5: Commit** `feat(node,ui): панели epoch и экономики`.

### Task 9: Логи и живая диагностика

**Files:**
- Create: `nexxus-desktop/src/views/logs.js`
- Modify: `crates/nexxus-node/src/local_api.rs` (`node_log_tail {lines}`)
- Modify: `nexxus-desktop/src-tauri/commands.rs` (`node_logs_cmd {lines}`, `node_logs_path_cmd`)

**Interfaces:**
- Produces WS: `node_log_tail {lines: usize} -> {lines: [String], path: String}` — хвост `~/.nexxus/nexxusd.log` (или `NEXXUS_LOG`)
- UI: просмотр последних N строк, авто-обновление, копирование, открыть папку, очистить (с подтверждением)

- [ ] **Step 1:** Тест в `local_api.rs`: `log_tail_returns_last_lines`, `log_tail_handles_missing_file` (пустой массив, без ошибки).
- [ ] **Step 2:** Тест → FAIL.
- [ ] **Step 3:** Реализовать метод + команду + панель.
- [ ] **Step 4:** Тест → PASS; clippy → 0.
- [ ] **Step 5: Commit** `feat(node,ui): просмотр логов ноды в дашборде`.

---

## Phase 3 — Конфиг, бэкап, безопасность, уведомления (Task 10–12)

### Task 10: Редактор конфига ноды

**Files:**
- Create: `nexxus-desktop/src/views/settings.js`
- Modify: `nexxus-desktop/src-tauri/commands.rs` (`node_config_apply_cmd`)

**Interfaces:**
- Produces: `guardian::apply_config(cfg: &NodeConfig) -> Result<(), String>` — сохранить конфиг → перезапуск ноды → дождаться API → вернуть новый статус
- UI: форма всех полей (`listen`, `api`, `auditors` textarea, `threshold`, `epoch_secs`, `tor` switch, `spec_version`, `log_path`) + кнопки «Применить и перезапустить», «Проверить», сброс к дефолтам, предупреждение о смене `node_id` при смене портов

- [ ] **Step 1:** JS-тест: `validateThreshold("0") === false`, `validateThreshold("3") === true`, `validateListen("127.0.0.1:4001") === true`.
- [ ] **Step 2:** Тест → FAIL.
- [ ] **Step 3:** Реализовать валидаторы, форму, команду apply с рестартом.
- [ ] **Step 4:** Тест → PASS; `npm run build` → 0.
- [ ] **Step 5: Commit** `feat(ui): редактор конфигурации ноды`.

### Task 11: Бэкап, восстановление и целостность

**Files:**
- Create: `nexxus-desktop/src-tauri/backup.rs`
- Modify: `crates/nexxus-node/src/storage.rs` (проверка целостности стора)
- Create: `nexxus-desktop/src/views/backup.js`
- Modify: `nexxus-desktop/src-tauri/commands.rs` (`backup_create_cmd`, `backup_list_cmd`, `backup_restore_cmd`, `backup_verify_cmd`)

**Interfaces:**
- Produces: `backup::create(store_path: &Path, dest_dir: &Path, label: &str) -> Result<BackupInfo, String>` — копия store+конфига+`node.conf` в `~/.nexxus/backups/<ts>-<label>/` + `manifest.json` с sha256
- Produces: `backup::list(dir) -> Vec<BackupInfo>`, `backup::restore(info, store_path) -> Result<(), String>` (атомарно: бэкап текущего → подмена), `backup::verify(info) -> bool`
- Produces: `storage::verify_store(path) -> Result<u64, String>` — открыть redb и пересчитать список чанков
- UI: список бэкапов, создать, проверить, восстановить (двойное подтверждение), экспорт в файл

- [ ] **Step 1:** Тесты в `backup.rs`: `create_then_list_contains_new`, `restore_replaces_store_content`, `verify_detects_corrupted_file` (порча байта в манифесте).
- [ ] **Step 2:** Тест → FAIL.
- [ ] **Step 3:** Реализовать (копирование файлов + `sha256sum` через `sha2` из workspace), панель и команды.
- [ ] **Step 4:** Тест → PASS; clippy → 0.
- [ ] **Step 5: Commit** `feat(desktop): бэкап, восстановление и проверка целостности стора`.

### Task 12: Уведомления Telegram и безопасность

**Files:**
- Modify: `nexxus-desktop/src-tauri/telegram.rs`
- Modify: `nexxus-desktop/src-tauri/commands.rs` (`tg_settings_cmd`, `tg_test_cmd`)
- Create: `nexxus-desktop/src/views/security.js`

**Interfaces:**
- Produces: `telegram::settings() -> Value {token_present: bool, token_source: "env"|"file"|"none", chat_id: String}` — **значение токена не возвращается никогда**
- Produces: `telegram::notify_event(kind: &str, detail: &str)` — события: `onboarding_step`, `identity_created`, `identity_restored`, `config_applied`, `backup_created`, `backup_restored`, `node_started`, `node_stopped`, `node_unreachable`, `node_recovered`, `benchmark_done`
- UI (security): карточка состояния токена, проверка чата, список включённых событий, предупреждение о seed-фразе

- [ ] **Step 1:** Тест в `telegram.rs`: `settings_never_exposes_token` (в JSON нет подстроки токена), `settings_reports_token_source_file`.
- [ ] **Step 2:** Тест → FAIL.
- [ ] **Step 3:** Реализовать `settings()`, событийные уведомления (переиспользовать существующий `TelegramBot`), панель.
- [ ] **Step 4:** Тест → PASS; clippy → 0.
- [ ] **Step 5: Commit** `feat(desktop): настройки уведомлений и панель безопасности`.

---

## Phase 4 — Первичная установка монитора и поставка (Task 13–14)

### Task 13: Монитор первичен — установка монитора до ноды

**Files:**
- Create: `deploy/desktop/install-monitor.sh`
- Create: `deploy/desktop/nexxus-monitor-autostart.desktop`
- Modify: `deploy/desktop/NeXXus-Node-Monitor.desktop` (точка входа на установленный бинарь)
- Modify: `nexxus-desktop/src-tauri/main.rs` (команда `self_install_cmd`)

**Interfaces:**
- Produces: скрипт `install-monitor.sh` — копирует бинарь в `~/.local/bin/nexxus-desktop`, ставит `.desktop` в `~/.local/share/applications`, иконки в `~/.local/share/icons/hicolor/`, unit `nexxus-monitor.service` в `~/.config/systemd/user/`, выполняет `systemctl --user enable --now nexxus-monitor.service`
- Produces: `self_install_cmd` — вызывает тот же скрипт из дашборда и возвращает отчёт по шагам
- UI: вкладка «Обзор» при первом запуске показывает карточку «Установить ноду» (кнопка ведёт в онбординг)

- [ ] **Step 1:** Тест-скрипт `bash -n deploy/desktop/install-monitor.sh` (синтаксис) + проверка, что скрипт создаёт unit с `Restart=on-failure` и кладёт `.desktop` в правильный путь (dry-run c `INSTALL_ROOT=$(mktemp -d)`).
- [ ] **Step 2:** Тест → FAIL (скрипта нет).
- [ ] **Step 3:** Реализовать скрипт с `INSTALL_ROOT` для тестов, команду `self_install_cmd`, карточку в UI.
- [ ] **Step 4:** Тест → PASS.
- [ ] **Step 5: Commit** `feat(deploy): установка монитора первым, до ноды`.

### Task 14: Финальная интеграция, самотест и документация

**Files:**
- Modify: `nexxus-desktop/src/main.js` (роутер вкладок, порядок: обзор → онбординг → сеть → хранилище → epoch/экономика → логи → настройки → бэкап → безопасность)
- Create: `docs/monitor.md` (руководство: установка монитора, онбординг, BIP39, бэкапы, Telegram)
- Modify: `README.md` (раздел монитора)

**Interfaces:**
- Produces: Tauri-команда `selftest_cmd` — прогон всех 15 WS-методов по очереди с таймаутом 3 c каждый, отчёт `{method, ok, ms, error}`
- Produces: кнопка «Прогнать самотест» в обзоре

- [ ] **Step 1:** Тест в `guardian.rs`: `selftest_reports_every_method` — 15 записей, каждая с `ok: bool`.
- [ ] **Step 2:** Тест → FAIL.
- [ ] **Step 3:** Реализовать `selftest_cmd`, роутер, документацию.
- [ ] **Step 4:** Полная верификация: `cargo test --workspace` (0 failed) → `cargo clippy --workspace --all-targets` (0 warnings) → `cargo build --release` → `npm run build` → живой смоук `test-api-client` (5 методов OK) → ручной прогон `selftest_cmd` через дашборд.
- [ ] **Step 5: Commit** `feat(desktop): самотест, роутер вкладок, документация монитора`.

---

## Порядок и зависимости

```
Task 1 (команды+конфиг) ─┬─> Task 2 (unit) ─┐
                          └─> Task 3 (онбординг) ─> Task 4 (BIP39)
Task 4 ─┬─> Task 5 (обзор) ─> Task 6 (сеть) ─> Task 7 (хранилище)
        └─> Task 8 (epoch/экономика)
Task 2 ─> Task 9 (логи) ─> Task 10 (конфиг-UI) ─> Task 11 (бэкап) ─> Task 12 (Telegram)
Task 1 ─> Task 13 (установка монитора) ─> Task 14 (интеграция)
```

Критический путь: 1 → 3 → 4 → 5 → 14.

## Определения готовности (Definition of Done)

- Монитор ставится и запускается **без** установленной ноды; дашборд открывается и предлагает онбординг.
- Онбординг из дашборда: проверка окружения → установка бинаря/юнита → создание стора → BIP39 (создание нового сида **или** восстановление из существующей фразы) → сеть → хранилище → Tor → старт → проверка.
- Все 15 WS-методов ноды доступны из UI; все 12 CLI-команд доступны через дашборд или его подкоманды.
- Все 8 env-параметров ноды редактируются из UI, применяются с рестартом и показывают фактическое значение.
- Бэкап/восстановление стора и конфига работают и проверяются по sha256.
- Seed-фраза и токен Telegram не появляются ни в логах, ни в отчётах, ни в git.
- `cargo test --workspace` — 0 failed; `cargo clippy --workspace --all-targets` — 0 warnings; release-сборка проходит.
