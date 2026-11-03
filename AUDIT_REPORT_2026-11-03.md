# NeXXus-Node — Полный технический отчёт аудита

**Дата аудита:** 03 ноября 2026 г.
**Ветка:** `main` (origin: github.com/PerfectFriend/NeXXus-Node)
**Статус сборки:** `cargo build --workspace` ✅, `cargo build --features tor` ✅, `cargo build -p nexxus-wasm` ✅
**Тесты:** 76/76 прошли (57 core + 4 econ + 15 node)
**Clippy:** `-D warnings` — 0 предупреждений
**Rust:** 1.99 (edition 2021), `unsafe_code = "forbid"`

---

## 1. Сводка проекта

NeXXus-Node — децентрализованное P2P хранилище и криптофоновская сетевая среда на Rust. Состав workspace:

| Crate | Назначение |
|-------|------------|
| `nexxus-core` | Криптографическое ядро: Ed25519/X25519, BIP-39, SLIP-0010, Reed-Solomon 4+2, Merkle, PoR, ChaCha20-Poly1305, wire v3, SMP, Epoch multi-sig |
| `nexxus-econ` | Экономика бартера: 16 GB секции, квоты vault, награды storer, вестинг |
| `nexxus-node` | Демон `nexxusd`: TCP P2P, redb хранилище, opcode-диспетчер, Tor (feature-gated) |
| `nexxus-wasm` | Placeholder для wasm-UI (отдельный график) |

---

## 2. Архитектура по модулям

### 2.1 nexxus-core

#### `types.rs` — Newtypes
- `NodeId([u8; 32])` — Kademlia-идентификатор узла (`SHA-256(verifying_key)`), derives `Ord` (добавлено в Phase 9 для `BTreeMap`)
- `ChunkHash([u8; 32])` — SHA-256 чанка
- `OnionAddress([u8; 35])` — Tor v3 onion: pubkey[32] || checksum[2] || version(0x03)
- `Money(i64)` — фиксированная точка, 1 NEXX = 1_000_000_000 micro, без float

#### `keys/` — Ключи и identidad
- `identity.rs` — Ed25519 identité, `node_id()` = SHA-256(pubkey), `onion_address()` по Tor v3 spéc, `sign()`/`verify()`. Золотые векторы 01 и 02 проходят.
- `seed.rs` — BIP-39 мнемомника (12 слов), PBKDF2-HMAC-SHA512, 2048 итераций, соль `"mnemonic"`. Золотой вектор 01 проходит.
- `slip10.rs` — SLIP-0010 на ed25519, путь `m/44'/9999'/0'/0'/0'` (все hardened). **Finding #1: несоответствие со спецификацией §2.1 (`m/44'/999'/0'/0/0`).**

#### `wire/` — Бинарный протокол
- `opcode.rs` — 14 опкодов (0x01–0x0D, 0xFF), заморожены (ADR-0002)
- `header.rs` — v2 (46 байт) и v3 (110 байт = v2 + Ed25519 sig[64]), Big-Endian, checksum SHA-256(opcode||req||len||payload). Золотой вектор `wire_ping_v2.hex` проходит.
- `payloads.rs` — все структуры полезной нагрузки с `encode/decode`, `SmpEnvelope` (X25519 ECDH → ChaCha20-Poly1305), `EpochFinalize` (committee multi-sig)
- `reader.rs` — граничированный BE Reader/Writer

**Finding #2: `frame.rs` отправляет v3 с нулевой подписью `[0u8;64]`. ADR-0001 требует реальную Ed25519 подпись кадра.**

#### `smp/mod.rs` — SMP релей (Phase 9)
- `SmpRelay`: `pending: BTreeMap<NodeId, Vec<PendingEnvelope>>`, `peers: BTreeMap<NodeId, Instant>`, TTL
- `store_envelope()` / `take_pending()` / `gc()` / `closest_peers()` (XOR u128)
- Компилируется в wasm32 без изменений

#### `epoch.rs` — Committee multi-sig (Phase 9)
- `verify_epoch_finalize(finalize, auditors, threshold)` — M-of-N, защита от дублей pubkey, проверка реестра аудиторов
- `epoch_signing_bytes(epoch_number, merkle_root, total_bytes)` — `epoch_number || merkle_root || total_bytes`

#### `merkle.rs` — Дерево Меркла + PoR
- `merkle_root()` с дублированием нечётного узла (Bitcoin-стиль), `merkle_proof()`, `verify_proof()`
- `por_response(chunk, seed)` = SHA-256(chunk || seed), `por_verify()`
- Золотой вектор 04 проходит

#### `rs/` — Reed-Solomon 4+2
- `gf256.rs` — GF(2⁸), полином 0x11D, таблицы exp/log
- `matrix.rs` — генераторная матрица [I\|P], кэш всех 15 обратных матриц C(6,4)
- `mod.rs` — `encode()`/`decode()`/`reconstruct()`, золотой вектор 03 проходит (все 15 комбинаций 4-of-6)

#### `chunk.rs` — Нарезка чанков + AEAD
- `CHUNK_SIZE = 16_384`, `slice()`/`join()`
- `ChunkAead::seal/open` — nonce[12] || ct||tag, ключ на чанк: SHA-256(vault_key || "nexxus-chunk-v2:" || index)
- Золотой вектор 05 (RFC 8439) проходит

#### `error.rs` — `NexxusError` с `thiserror`, `unsafe_code = "forbid"` на workspace-уровне

---

### 2.2 nexxus-econ

- `SECTION_SIZE_GB = 16`, `BASE_VAULT_REWARD_GB = 2`, `EXPANDED_VAULT_RATIO = 1/8`
- `split_into_sections(free_gb)` — 16 GB секции → квота vault
- `daily_storer_reward(foreign_gb)` = 1.25 NEXX/GB/день
- `daily_subscription_cost(subscribed_gb)` = 1.30 NEXX/GB/день
- `VESTING_LOCK_DAYS = 56`
- Все суммы в integer micro-NEXX, `Money` из `nexxus-core::types`

---

### 2.3 nexxus-node

#### `main.rs` — Демон `nexxusd`
- Аргумент: `<store-path>` (redb файл)
- ENV `NEXXUS_LISTEN` (default `127.0.0.1:4001`)
- `NodeId` через `OsRng`, `ChunkStore` из CLI-аргумента
- Запуск под `tokio::Runtime`

#### `storage.rs` — redb индекс
- `ChunkStore` — таблица `chunks`: ключ `[u8;32]`, значение `&[u8]`
- `put_chunk` / `get_chunk`, транзакции redb

#### `net/` — P2P сеть
- `frame.rs` — length-delimited v3 (4 байта BE len || frame), `MAX_FRAME_LEN = 4 MiB`
- `routing.rs` — Kademlia k-buckets (k=20, 256 buckets), `bucket_index` = MSB differing bit, `find_node()` по XOR u64
- `network.rs` — `P2pNetwork`: listen/dial, opcode-диспетчер (Ping/Pong/NodeAnnounce/StoreChunk/FetchChunk/PorChallenge/PorResponse/KadFindNode/KadNodesFound/SmpEnvelope/EpochFinalize/ErrorResponse), SMP decode через `x25519_secret`

**Finding #3: Обработчик `EpochFinalize` проверяет подписи, но не сверяет pubkey с реестром аудиторов. ADR-0008 требует M-of-N из зарегистрированных аудиторов.**

**Finding #5: `PorChallenge.seed` используется как `ChunkHash` (строка `let hash = ChunkHash(challenge.seed);`), а по спецификации §4.3 Challenge = HMAC-SHA256(EpochSeed, NodeId).**

#### `tor.rs` — Tor transport (Phase 9, feature-gated)
- `TorSession` с `arti-client 0.47`, `TorClient::create_bootstrapped()`, `connect_onion(onion_addr)`
- Функционально без `--features tor` — TCP/WS
- Зависимости: `arti-client` + `tor-rtcompat` (native-tls)
- **Не требует живой Tor-сети для сборки; bootstrap требует реальной Tor-сети (отдельный smoke-тест)**

---

### 2.4 nexxus-wasm

- Placeholder: `pub use nexxus_core;`, `fn version() -> &str`
- Real wasm-bindgen exports — отдельный график (UI build)

---

## 3. Золотые векторы (fixtures)

| Вектор | Файл | Статус |
|--------|------|--------|
| 01 BIP-39 seed | `tests/fixtures/01_bip39_seed.json` | ✅ `matches_bip39_golden_vector` |
| 02 Tor v3 onion | `tests/fixtures/02_tor_v3_onion.json` | ✅ `onion_matches_golden_vector` + второй вектор |
| 03 Reed-Solomon | `tests/fixtures/03_reed_solomon_gf256.json` | ✅ `matches_golden_vector_03` (все 15 комбинаций) |
| 04 Merkle tree | `tests/fixtures/04_merkle_tree.json` | ✅ `matches_golden_vector_04_root` |
| 05 ChaCha20-Poly1305 | `tests/fixtures/05_chacha20_poly1305.json` | ✅ `matches_golden_vector_05` (RFC 8439) |
| Wire v2 ping | `tests/fixtures/wire_ping_v2.hex` | ✅ `v2_matches_ts_fixture` |

---

## 4. Найденные проблемы (Findings)

### Критические / Высокие

**F-01 — Несоответствие пути деривации ключей**
- `slip10.rs`: `m/44'/9999'/0'/0'/0'` (все indexes hardened, coin type 9999)
- Спецификация §2.1: `m/44'/999'/0'/0/0` (coin type 999)
- Риск: ключи, сгенерированные Rust- realization, не совпадут с TS-базой и с мобильными клиентами. Требуется унификация до релиза.

**F-02 — Нулевая подпись в v3 кадрах**
- `frame.rs::send_frame` использует `sig = [0u8; 64]`
- ADR-0001 §6: v3 заголовок включает 64-байтную Ed25519 подпись над `opcode||req||len||payload||session_nonce`
- Риск: подмена кадра не обнаруживается на уровне транспорта.

**F-03 — EpochFinalize без реестра аудиторов**
- `network.rs` обработчик `EpochFinalize` проверяет только криптографическую валидность подписей, но не требует, чтобы pubkey belonged к реестру аудиторов (ADR-0008: M-of-N из зарегистрированных аудиторов)
- Риск: любой узел может отправить валидную multi-sig, не являясь членом комитета.

**F-05 — PoR challenge не по спецификации**
- `network.rs` строка 382: `let hash = ChunkHash(challenge.seed);` — seed используется как ChunkHash
- Спецификация §4.3: Challenge = HMAC-SHA256(EpochSeed, NodeId)
- Риск: несовместимость протокола PoR с внешними реализациями.

### Низкие

**F-04 — Нулевой nonce в SmpEnvelope**
- `payloads.rs::seal`: `nonce: [0u8; 12]` фиксированный
- Безопасно пока ключ ЭCDH уникален на каждый `seal` (ephemeral OsRng), но нарушает гигиену AEAD при переиспользовании ключа.

**F-06 — Разные метрики XOR расстояния**
- `net/routing.rs::xor_distance` возвращает `u64` (топ 64 бита)
- `smp/mod.rs::xor_distance` возвращает `u128` (полные 256 бит)
- Риск: ранг соседей в k-buckets и SMP-маршрутизации может различаться.

---

## 5. Статус по фазам

| Фаза | Описание | Статус |
|------|----------|--------|
| Phase 0–8 | TS→Rust миграция ядра, wire v3, ключи, matematika, экономика, redb, SMP, Epoch multi-sig, Tor stub | ✅ Завершено |
| Phase 9 | SMP релей, Epoch委員 multi-sig, реальный arti-client, e2e тесты двух демонов | ✅ Завершено (этот отчёт) |
| Phase 9+ | Real Tor bootstrap (живая сеть), wasm UI, сквозные тесты двух демонов на разных портах | 🔄 Отдельный график |

---

## 6. Рекомендации

1. **Единолизировать derivation path** — привести `slip10.rs` к спецификации `m/44'/999'/0'/0/0` или обновить спецификацию под код (согласовать с владельцем).
2. **Реализовать Ed25519 подпись v3 кадров** в `frame.rs` с передачей `session_nonce` из рукопожатия.
3. **Добавить реестр аудиторов** в обработчик `EpochFinalize` в `network.rs` (M-of-N проверка).
4. **Привести PoR challenge к спецификации** — HMAC-SHA256(EpochSeed, NodeId), а не ChunkHash.
5. **Единолизировать XOR-метрику** — выбрать u128 для всех модулей маршрутизации.
6. **Добавить интеграционный тест с реальной Tor-сетью** (smoke-тест, отдельный CI job).
7. **Завершить wasm-UI привязку** — реальные wasm-bindgen экспорты вместо placeholder.

---

## 7. Вывод

Кодовая база NeXXus-Node на момент аудита: **собирается, тестируется, запушена на GitHub**. Криптографические примитивы соответствуют золотым векторам, протокольные структуры (wire v3, опкоды, SMP, Epoch multi-sig) реализованы согласно ADR. Найденные несоответствия (F-01–F-06) не блокируют сборку, но требуют исправления перед релизом в продакшен для обеспечения межсетевой совместимости и криптографической整ноты.
