# Полная ревизия проекта NeXXus v2.0 — 09.11.2026

Аудит по скиллу capability-gap-audit: рекламируемое vs реализованное, классификация broken / dead / unbuilt. Всё «проверено» — из команд ниже или актуальных прогонов этой сессии; «заявлено» — только из документации.

## 1. Что это за проект

NeXXus v2.0 — суверенный P2P-узел: децентрализованное хранилище (чанки 16 КБ, RS(4+2), Merkle, PoR), onion-маршрутизация (Tor v3 через arti), SMP-ретранслятор сообщений, экономика storer'ов (секции, вестинг 56 дней, анти-луп инвариант), локальный WS JSON-RPC API, десктоп-монитор (Tauri) и параллельное TS-веб-приложение (src/). Документы-намерения: NEXXUS_SPECIFICATION_V2.md, ADR 0000–0008, contracts/*.fc (FunC).

## 2. Проверенное состояние (verified)

| Компонент | Доказательство |
|---|---|
| Rust-воркспейс: 5 крейтов, ~9 000 строк | `wc -l` по `crates/*/src` + `nexxus-desktop/src-tauri` |
| Тесты: 59 core + 12 econ + 13 node + 2 wasm + 9 desktop = 95 `#[test]` | grep по исходникам; прогон: workspace 100 passed (сессия), desktop 9/9 passed, clippy `-D warnings` = 0, `cargo build --release` exit 0 |
| nexxusd слушает P2P 4001 + API 4010 сразу, Tor бутстрапится фоном | живой смоук (коммит c07fd99) |
| Локальный API: 14 методов (node_status/peers/chunks/upload/download/por/epoch/tor/smp/pause/resume/connect/dial_onion/test_interhost + send_smp_envelope) | grep `local_api.rs` |
| CLI: init, id, status, peers, peer, upload, download, logs, benchmark | grep `cli.rs` |
| Wire: 13 опкодов (0x01–0x0D + 0xFF) | `wire/opcode.rs` |
| Крипто: BIP39/SLIP-10 seed, ed25519 identity, X25519, ChaCha20-Poly1305, GF(256) RS, Merkle/PoR, verify_epoch_finalize | структура `nexxus-core/src` + golden vectors 01–05 |
| Экономика: VestingSchedule (56 дн), split_into_sections, anti_loop_invariant_holds (1.30 > 1.25), degradation/health, PoR reset | `nexxus-econ/src/*.rs` + тесты |
| Монитор: трей-иконка по ТЗ (красная N в синем семиугольнике, верифицировано vision), меню 8 пунктов, single-instance lock, `--shutdown`-файл, Telegram с таймаутами 5/10 с, node.conf (0600), WS-handshake до API | смоук-тесты этой сессии + коммиты 918ddaa, be537b0 |
| Запуск с рабочего стола: `~/.local/share/applications/NeXXus-Node-Monitor.desktop` + launcher, `desktop-file-validate` чист | проверка этой сессии |
| CI (.github/workflows/ci-release.yml) гоняет только TS-тесты (113 проверок), esbuild-бандл и .deb | чтение workflow |

## 3. Находки

### broken (регрессии) — на сейчас не обнаружено
Все найденные ранее регрессии починены и закоммичены: «Handshake not finished»-спам (настоящий WS-handshake в `api_is_reachable`), смерть монитора под systemd (prevent_exit), потеря логов ноды (→ `~/.nexxus/nexxusd.log`), KillMode убивал ноду (→ KillMode=process), гонка тестов env (→ явные пути `load_from`/`save_to`), неработающие кнопки трея (4 корня, см. коммит 918ddaa).

### dead (написано, но недостижимо)
1. **8 Tauri-команд зарегистрированы, но UI их не вызывает**: `node_config_get/set/validate_cmd`, `node_install/uninstall/status_cmd`, `guardian_shutdown_cmd`. `main.js` зовёт только 7 команд (`guardian_*` + `tg_send_test_cmd`). Конфиг ноды и установка юнита сейчас недоступны из дашборда — мёртвая поверхность (capability-gap: backend dispatch есть, surface нет).
2. `allow(dead_code)`-островки: `guardian.rs` (поле `nexxusd_pid` + 4 функции около строк 294–312), `telegram.rs:158`, `api_client.rs` (модульный `#![allow(dead_code)]`). По правилу «стаб ≠ allow»: либо подключить к реальному вызову, либо удалить.
3. `deploy/systemd/nexxus-monitor.service` — установлен но `disabled` (по новому условию пользователя: запуск только из ярлыка).

### unbuilt (задумано, не сделано) — не дефекты, это план
- Панели дашборда монитора (overview/network/storage/epoch/tor/logs/settings/backup/security) — старый план Task 5–12.
- Онбординг-машина состояний + BIP39 регистрация/восстановление/экспорт сида (Task 3–4).
- Бэкап/восстановление store+конфига (Task 8-ish).
- **Аутентификация локального API**: WS на 127.0.0.1:4010 **без токена** — любой локальный процесс может читать/писать хранилище и управлять нодой. Loopback спасает от сети, но не от другого локального процесса. (проверено: grep auth/token в `local_api.rs` пуст)
- **Шифрование store.redb at rest**: `storage.rs` не содержит шифрования — чанки лежат в redb открыто. AEAD есть только в транспортном слое (`ChunkAead`).
- Panic PIN / dual-PIN с экспоненциальным кулдауном (спецификация §5) — в Rust-узле нет; есть только `securityPin.ts` в TS-приложении.
- Мультисиг кворум аудиторов (ADR 0008) и интеграция с FunC-контрактами (contracts/*.fc) — узел только локально верифицирует epoch finalize.
- SMP-«почтовый ящик» с TTL и UI; QR/deep-link обмен контактами (спецификация §7).
- Prometheus-метрики узла; self-update с верификацией подписи; cargo в CI; Windows/Android порты (docs/ROADMAP_WINDOWS_ANDROID.md, фазы W2–W5, A2–A5).
- Старый `linux-node/` (Node.js-демон) — легаси-реализация рядом с Rust.

### не проверено (unverified)
- Живая работа GUI монитора (в этом окружении нет дисплея — проверены только CLI-пути: lock, --shutdown).
- Работа по реальной сети между двумя узлами (test-pair.mjs / node_test_interhost) в этой сессии не прогонялся.
- Соответствие TS- и Rust-реализаций протокола — golden vectors покрывают 5 областей (01–05), не все опкоды.

## 4. Что работает «на самом деле» (главное)

Ядро протокола (wire/RS/Merkle/keys/epoch-verify) — зрелое, с тестами и golden vectors. Сетевой слой слушает порты сразу, Tor не блокирует. Экономика полностью покрыта тестами включая анти-луп инвариант. Монитор после фиксов этой сессии: single-instance, надёжные stop/shutdown, ярлык на рабочем столе, Telegram-отчёты с таймаутами.

## 5. Главные риски

1. Локальный API без аутентификации + стор без шифрования at rest — любой локальный процесс (или малварь) читает всё. Приоритет №1.
2. Мёртвая поверхность монитора (8 команд без UI) — пользователь не видит конфиг/установку ноды.
3. CI не гоняет Rust — регрессии в крейтах не ловятся автоматически.
4. Две параллельные реализации (Rust + TS + legacy JS linux-node) — риск рассинхрона протокола.

## 6. Вердикт

Проект в активной, честной разработке: ядро зрелое и протестированное, монитор доведён до рабочего состояния (запуск из ярлыка, надёжный трей), но «мясо» пользовательского опыта (дашборд-панели, онбординг, бэкапы, безопасность at rest) — unbuilt. Новый план: `docs/plans/2026-11-09-nexxus-evolution-v3.md`.
