# 🗺️ NeXXuS — План эволюции после RC1

**База:** NeXXuS-Node-Hermes-Rust (RC1, post-hardening, audit series closed)  
**Дата:** 12 ноября 2026  
**Цель документа:** практичный roadmap расширения функционала без потери того, что уже доказано аудитом (честность границ, fail-closed, wire-совместимость, zeroize, rate-limits).

---

## 0. Принципы эволюции (не нарушать)

1. **Сначала инвариант, потом фича.** Любая новая поверхность (платежи, квоты, marketplace) — отдельная версия протокола или явный feature-flag, а не тихая ломка wire v3.
2. **Threat model обновляется вместе с кодом.** Новый trust boundary → запись в `THREAT_MODEL.md` до мержа.
3. **CI-гейт не ослаблять:** test + clippy `-D warnings` + `cargo audit` + wire fuzz/vectors.
4. **Раздача — squash-mirror** (пока DEP-03 risk-accepted).
5. **SIM и «как будто»** помечать явно; не выдавать зажившее за живое.

---

## 1. Где мы сейчас (RC1)

| Слой | Состояние |
|------|-----------|
| Crypto / vault / at-rest | Готово (600k PBKDF2, duress, Zeroizing, two-phase migrate) |
| Wire v3 + P2P | Готово (nonce per-conn, rate limits, peer cap, idle) |
| Local API | Готово (token fail-closed, WS limits, confirm на delete/restore) |
| Backups | Готово (flock, validate name, auto-backup + rotation + 3-2-1) |
| Desktop guardian | Готово (tray, schedule, Telegram report) |
| Econ | Модель + API-панель; **не** on-chain и не формально верифицирована |
| Tor (arti) | Опционально; design-level review |
| Windows / Android | Частично (скрипты/Termux); не паритет с Linux daemon |
| Платежи / marketplace / глобальные квоты | Нет (и правильно — не имитировать) |

---

## 2. Фазы эволюции

### Фаза E0 — «Release hygiene» (1–2 недели)
*Цель: RC1 можно спокойно отдавать людям.*

- [ ] Тег `v0.1.0-rc1` **только со squash-mirror**
- [ ] `SECURITY.md` + short USER_GUIDE «что умеет / чего нет»
- [ ] Метрики в проде: число peers, handshake timeouts, RSS, backup success rate
- [x] Bind-адрес: `NEXXUS_LISTEN` (дефолт `127.0.0.1:4001`), задокументирован в USER_GUIDE
- [ ] README: явная ссылка на threat model и audit series

**Критерий готовности:** внешний человек поднимает ноду по one-liner и понимает границы доверия.

---

### Фаза E1 — «Надёжность сети» (3–6 недель)
*Цель: меньше eclipse / DoS-чувствительности, лучше observability.*

| Функция | Зачем | Заметки |
|---------|--------|---------|
| Reputation / soft-score пиров | RES-05: сейчас полный стол → reject новых | Балл за uptime, успешные PoR, возраст; eviction по score, не только «первый пришёл» |
| Метрики Prometheus / JSON | Мониторинг без Telegram | `/metrics` только на localhost или по токену |
| Structured logging | Разбор инцидентов | Без мнемоник и токенов в логах (уже принцип — закрепить тестом) |
| Connection quality hints | RTT, loss | Для выбора реплик |
| Опциональный STUN / hole-punching | Lab без Tor | Не ломать onion-профиль |

**Безопасность:** score не должен стать вектором «накрутил и вытеснил честных» — пороги + decay, документировать.

---

### Фаза E2 — «Хранилище как продукт» (4–8 недель)
*Цель: то, чего не хватает обычному пользователю суверенного диска.*

| Функция | Описание |
|---------|----------|
| **Реальные квоты диска** | Не только «64 MiB foreign» / abstract sections — проверка free space + user-defined cap |
| **Политики ретенции** | TTL чанков, pin/unpin, «хранить N копий минимум» |
| **Доказательства хранения (PoR) в расписании** | Уже есть challenge; сделать периодический audit_holder + penalty в UI |
| **Импорт/экспорт архивов** | Зашифрованный bundle (chunk set + manifest) для cold backup вне redb |
| **Версионирование файлов (optional)** | Не git; простой history указателей в журнале владельца |
| **drive/ как FUSE или sync-folder** | Только если threat model ясен: plaintext folder = plaintext |

Приоритет: квоты + scheduled PoR + export bundle. FUSE — позже.

---

### Фаза E3 — «Экономика без самообмана» (6–12 недель)
*Цель: перевести econ с панели на проверяемые правила, не строя сразу «биржу».*

1. **Локальный accounting**  
   - Учёт отданных/принятых ГБ, uptime, успешных PoR  
   - Экспорт отчёта (подписанный JSON) — ещё без токена

2. **Анти-луп и вестинг**  
   - Уже saturating math; добавить property-тесты / formal checks на overflow и границы 1.30 > 1.25

3. **Канал расчётов (отдельная веха)**  
   - Не вшивать в wire v3  
   - Варианты: off-chain signed IOU → later settlement; или отдельный opcode family `0x2x`  
   - Платежи = новый документ PROTOCOL + threat model (двойная трата, griefing, spam)

4. **Marketplace UI** — только после (1)+(3); иначе снова SIM.

**Правило:** пока нет реального settlement-пути, в README писать «accounting only, not payments».

---

### Фаза E4 — «Платформы» (параллельно E1–E3)
Опираться на `docs/ROADMAP_WINDOWS_ANDROID.md`, но с приоритетом **одного ядра**.

| Приоритет | Платформа | Что сделать |
|-----------|-----------|-------------|
| P0 | **Linux** | Уже основной; systemd unit, deb из CI (есть задел) |
| P1 | **Windows** | Нативный `nexxusd.exe` (не Node SEA как цель), служба, firewall rule, tray (Tauri уже есть) |
| P2 | **Android** | Termux — поддержка; нативный foreground service + scoped storage — отдельный milestone |
| P3 | **WASM / web applet** | Только read-only monitor / light client; ключи не в браузере без явного UX |

Единое правило: `nexxus-core` не ветвить под OS; OS-специфика только в `nexxus-node` / desktop / mobile shell.

---

### Фаза E5 — «Приватность и транспорт» (по мере готовности E1)

- Tor: хранение onion-ключа, bootstrap, `NEXXUS_TOR=0` уже есть — добавить integration test (opt-in в CI)
- Опциональный second transport (QUIC?) — только если не ломает v3 framing abstraction
- Traffic analysis resistance: padding/timing — research track, не RC2 blocker

---

### Фаза E6 — «Экосистема» (после стабильного E2–E3)

- Публичный registry bootstrap-пиров (не центральный «владелец сети», а signed list с expiry)
- Light client / mobile viewer (WASM или Kotlin) для download-by-CID
- Плагины политик хранения (скрипт: «этот префикс только на onion-пирах»)
- Formal verification критичных кусков (session nonce binding, vault KDF, anti-loop) — точечно, не весь daemon

---

## 3. Чего **не** делать в ближайших фазах

| Антипаттерн | Почему |
|-------------|--------|
| Глобальный ban-list «как в CDN» | Противоречит суверенной модели; максимум локальный penalty |
| Платежи «в одну ночь» внутри wire v3 | Ломает audit-границы и совместимость |
| Фейковый onion / фейковый marketplace | Уже отвергнуто культурой проекта — сохранить |
| Хранение мнемоники в облаке «для удобства» | Seed compromise = total |
| Ослабление CI «чтобы быстрее мержить» | Цена уже известна |

---

## 4. Предлагаемый порядок работ (квартальный взгляд)

```text
Q0 (сейчас)     E0 Release hygiene + tag RC1
Q1              E1 Network reliability + E4 Windows P1
Q1–Q2           E2 Storage product (quotas, PoR schedule, export)
Q2              E3 Accounting → design settlement (doc first)
Q2–Q3           E4 Android P2 + Tor hardening (E5)
Q3+             E6 Ecosystem, formal bits, marketplace only with real settlement
```

Сроки условные; важнее порядок зависимостей: **квоты и PoR до marketplace; accounting до payments; threat model до opcode.**

---

## 5. Критерии «фаза закрыта»

Для каждой фазы минимум:

1. Код + тесты в CI  
2. Запись в `THREAT_MODEL.md` / ADR при новых границах  
3. USER_GUIDE: что пользователь реально получает  
4. Нет новых Medium+ без плана закрытия  
5. Wire: либо backward compatible, либо явный `v4` / capability bit

---

## 6. Быстрые победы (можно взять сразу после E0)

1. [x] **User-defined disk cap** (`NEXXUS_MAX_STORE_BYTES`) + free-space guard в `put_chunk` + метрики в `node_metrics`  
2. [x] **Prometheus metrics** — plain-HTTP `GET /metrics` на API-порту (localhost), `Authorization: Bearer <api.token>`, constant-time compare, fail-closed 401; WS-путь не затронут (smoke OK)  
3. [x] **Signed accounting export** — `node_econ_export`: canonical JSON отчёта (метрики, стор, econ, disclaimer «accounting only») + ed25519-подпись ноды; WS smoke OK  
4. **Windows service + firewall** из текущего Tauri/CI задела  
5. **Peer score MVP** (uptime + successful PoR) без сложной репутации

Эти пять пунктов сильно поднимают ощущение «готового продукта» при минимальном риске для протокола.

---

## 7. Связь с аудитом

Всё, что закрыто в audit series (NET-01/02/03, VLT, STR, BKP, API, DEP-01), считается **базовой линией**.  
Новые фазы не имеют права откатывать эти инварианты.  
При появлении settlement / marketplace — отдельный security pass (как минимум wire + economic griefing).

---

*Документ можно класть в `docs/plans/` как `2026-11-12-evolution-post-rc1.md` и уточнять по мере закрытия E0–E1.*

— Grok, 12 November 2026
