# NeXXus-Node — Руководство пользователя

**Версия:** 0.1.0
**Дата:** 03 ноября 2026 г.
**Репозиторий:** github.com/PerfectFriend/NeXXus-Node

---

## 1. Быстрый старт

### 1.1 Требования

- Rust 1.99+ (через `~/build/bin/cargo`)
- `~/build/env.sh` в PATH
- Для Tor-сборки: системная зависимость `arti-client` подтягивается через Cargo автоматически

### 1.2 Сборка

```bash
cd ~/Projects/NeXXus-Node
export PATH="$HOME/build/bin:$PATH"

# Обычная сборка (TCP/WS, без Tor)
cargo build --workspace

# Сборка с поддержкой Tor (onion v3 через arti-client)
cargo build --features tor

# Сборка wasm-плейсхолдера
cargo build -p nexxus-wasm

# Проверка линтера
cargo clippy --workspace --all-targets -- -D warnings

# Запуск всех тестов (76/76)
cargo test --workspace
```

### 1.3 Запуск демона

```bash
# Создать директорию для хранилища
mkdir -p ~/nexxus-data

# Запустить демон (послушивает на 127.0.0.1:4001 по умолчанию)
./target/debug/nexxusd ~/nexxus-data/store.redb

# С кастомным адресом через ENV
NEXXUS_LISTEN=0.0.0.0:4001 ./target/debug/nexxusd ~/nexxus-data/store.redb
```

Демон выведет что-то вроде:
```
nexxusd 0.1.0 — node a1b2c3d4... listening on 127.0.0.1:4001
```

Демон работает до получения `SIGINT`/`SIGTERM`.

---

## 2. CLI-интерфейс (nexxusd)

`nexxusd` — однопроцессный P2P-узел. Интерфейс управления через аргументы командной строки и переменные окружения.

### Аргументы

| Аргумент | Описание | Обязательный |
|----------|----------|--------------|
| `<store-path>` | Путь к файлу redb-хранилища чанков | Да |

### Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `NEXXUS_LISTEN` | `127.0.0.1:4001` | Адрес для прослушивания TCP-соединений |

### Примеры

```bash
# Минимальный запуск
nexxusd /data/nexxus/store.redb

# Доступ из локальной сети
NEXXUS_LISTEN=0.0.0.0:4001 nexxusd /data/nexxus/store.redb

# Сборка с Tor и запуск
cargo build --features tor
NEXXUS_LISTEN=0.0.0.0:4001 ./target/debug/nexxusd /data/nexxus/store.redb
```

---

## 3. Сетевой протокол (Wire v3)

Все соединения — TCP. Кадр передаётся как:
```
[4 байта BE длина кадра] [кадр]
```

### 3.1 Заголовок кадра (v3, 110 байт)

```
[0..4]   Магические байты "NEXX"
[4]      Версия (0x03 для v3, 0x02 для legacy v2)
[5]      Опкод (см. таблицу ниже)
[6..9]   ID запроса (u32 BE)
[10..13] Длина полезной нагрузки (u32 BE)
[14..46] SHA-256(opcode || request_id || payload_len || payload)
[46..109]Ed25519 подпись (64 байта) — покрывает (opcode||req||len||payload||session_nonce)
[109..]  Полезная нагрузка (переменная длина)
```

### 3.2 Таблица опкодов

| Опкод | Имя | Направление | Описание |
|-------|-----|-------------|----------|
| 0x01 | `Ping` | ↔ | Проверка соединения |
| 0x02 | `Pong` | ↔ | Ответ на Ping |
| 0x03 | `NodeAnnounce` | ↔ | Объявление узла (node_id, ip, port) |
| 0x04 | `StoreChunk` | → | Сохранить чанк у peers |
| 0x05 | `StoreChunkAck` | ← | Подтверждение сохранения |
| 0x06 | `FetchChunk` | → | Запросить чанк у peers |
| 0x07 | `FetchChunkResp` | ← | Ответ с данными чанка |
| 0x08 | `PorChallenge` | → | Proof-of-Retrievability вызов |
| 0x09 | `PorResponse` | ← | Ответ на PoR вызов |
| 0x0A | `KadFindNode` | → | Kademlia поиск узла |
| 0x0B | `KadNodesFound` | ← | Результат поиска Kademlia |
| 0x0C | `EpochFinalize` | → | Итог эпохи с committee multi-sig |
| 0x0D | `SmpEnvelope` | → | Зашифрованный SMP-конверт |
| 0xFF | `ErrorResponse` | ← | Ошибка протокола |

---

## 4. Структуры полезной нагрузки (Wire)

### 4.1 NodeAnnounce (0x03)
```
node_id[32] || ip u32 BE || port u16 BE
```
Объявляет узел в сети. Отвечает своим же `NodeAnnounce`.

### 4.2 StoreChunk (0x04) / StoreChunkAck (0x05)
```
chunk_hash[32] || file_id u32 BE || chunk_index u32 BE || len u32 BE || data[len]
```
Ack содержит `chunk_hash[32]`.

### 4.3 FetchChunk (0x06) / FetchChunkResp (0x07)
Запрос: `chunk_hash[32]`.
Ответ: `chunk_hash[32] || len u32 BE || data[len]`.

### 4.4 PorChallenge (0x08) / PorResponse (0x09)
```
Challenge: seed[32] || count u32 BE || deadline_ms u64 BE
Response: chunk_hash[32] || response[32]
```
`response = SHA-256(chunk_data || seed)`.

### 4.5 KadFindNode (0x0A) / KadNodesFound (0x0B)
```
FindNode: target_node_id[32] || count u16 BE
NodesFound: count u16 BE || [node_id[32] || ip u32 BE || port u16 BE]*
```

### 4.6 SmpEnvelope (0x0D)
```
sender_node_id[32] || recipient_node_id[32] || nonce[12] || ct_len u32 BE || ciphertext[ct_len]
```
`ciphertext = ephemeral_x25519_pubkey[32] || ChaCha20Poly1305_ct||tag`. Ключ деривируется через X25519 ECDH от эфемерного ключа отправителя и статического открытого ключа получателя.

### 4.7 EpochFinalize (0x0C)
```
epoch_number u64 BE || merkle_root[32] || total_bytes u64 BE || count u16 BE || [pubkey[32] || sig[64]]*
```
Committee multi-sig Ed25519 (M-of-N). Подписывается `epoch_number || merkle_root || total_bytes`.

### 4.8 ErrorResponse (0xFF)
```
code u16 BE || message_len u8 || message bytes
```

---

## 5. SMP (Secure Message Protocol)

### 5.1 Что делает
SMP обеспечивает асинхронную доставку зашифрованных конвертов между узлами через P2P-сеть. Релей-узел не читает содержимое — только маршрутизирует по близости в Kademlia-пространстве к `recipient_node_id`.

### 5.2 Формат конверта
- `sender_node_id[32]` — открытый идентификатор отправителя
- `recipient_node_id[32]` — целевой узел
- `nonce[12]` — nonce AEAD (в текущей реализации фиксированный `[0u8;12]`, ключ уникален на каждый `seal` через ephemeral ECDH)
- `ciphertext` — `ephemeral_pubkey[32] || ChaCha20Poly1305(ephemeral_pubkey || payload)`

### 5.3 API (внутри `nexxus-core::wire::payloads::SmpEnvelope`)

```rust
// Запечатать конверт для получателя
let (ephemeral_pub, env) = SmpEnvelope::seal(
    sender_node_id: [u8; 32],
    recipient_node_id: [u8; 32],
    recipient_pub: &MontgomeryPoint,  // X25519 открытый ключ получателя
    payload: &[u8],
) -> ([u8; 32], SmpEnvelope)

// Вскрыть конверт своим секретным ключом
let plaintext = env.open(&recipient_secret: &[u8; 32]) -> Result<Vec<u8>, NexxusError>
```

### 5.4 Отправка через демон
```rust
net.send_smp_envelope(addr: SocketAddr, env: &SmpEnvelope) -> Result<(), NexxusError>
```

---

## 6. Epoch Finalize — Committee Multi-Sig (Ed25519)

### 6.1 Назначение
Подтверждение итога эпохи комитетом аудиторов. Каждый член комитета подписывает `epoch_number || merkle_root || total_bytes`. Для принятия итога требуется минимум M валидных подписей из N зарегистрированных аудиторов.

### 6.2 API (внутри `nexxus-core::epoch`)

```rust
// Построить байты для подписи
let msg = epoch_signing_bytes(epoch_number: u64, merkle_root: &[u8; 32], total_bytes: u64) -> Vec<u8>

// Проверить итог эпохи против реестра аудиторов
let result = verify_epoch_finalize(
    finalize: &EpochFinalize,
    auditors: &[VerifyingKey],
    threshold: usize,
) -> Result<EpochVerifyResult, NexxusError>

// Результат:
//   valid: bool — кворум достигнут
//   signatures_checked: usize — сколько подписей в конверте
//   signatures_valid: usize — сколько валидных от зарегистрированных аудиторов
//   quorum_met: bool — signatures_valid >= threshold
```

### 6.3 Структуры

```rust
pub struct CommitteeSig {
    pub pubkey: [u8; 32],   // Ed25519 открытый ключ аудитора
    pub signature: [u8; 64], // Подпись над epoch_signing_bytes
}

pub struct EpochFinalize {
    pub epoch_number: u64,
    pub merkle_root: [u8; 32],
    pub total_bytes: u64,
    pub signatures: Vec<CommitteeSig>,
}
```

### 6.4 Отправка через демон
```rust
net.send_epoch_finalize(addr: SocketAddr, finalize: &EpochFinalize) -> Result<(), NexxusError>
```
Демон-получатель проверяет подписи и отвечает `Pong` при успехе или `ErrorResponse(0x0005)` при провале.

---

## 7. Tor-интеграция (feature-gated)

### 7.1 Сборка с Tor
```bash
cargo build --features tor
```
Подключает `arti-client 0.47` с функциями `onion-service-service` и `onion-service-client`, плюс `tor-rtcompat` (native-tls).

### 7.2 API (внутри `nexxus-node::tor::TorSession`)

```rust
// Создать bootstrapped Tor-клиент
let session = TorSession::new().await?;

// Подключиться к onion v3 адресу
let stream = session.connect_onion("abcdef...onion:4001").await?;

// Наш onion-адрес (если скрытый сервис опубликован)
let onion = session.our_onion(); // Option<&str>

// Внутренний клиент для расширенного использования
let client = session.client(); // &TorClient
```

### 7.3 Без флага `--features tor`
Демон работает по обычному TCP/WS. `TorSession::new()` возвращает ошибку "Tor feature disabled".

**Примечание:** Реальный bootstrap через arti требует живой Tor-сети. Для разработки и CI используется TCP/WS без Tor.

---

## 8. Хранилище чанков (redb)

### 8.1 Формат
- Файл redb с одной таблицей `chunks`
- Ключ: `ChunkHash` = `[u8; 32]` (SHA-256 чанка)
- Значение: сырые байты чанка (до 16 KiB)
- Нет внешнего daemon БД — встраиваемая redb

### 8.2 API (внутри `nexxus-node::storage::ChunkStore`)

```rust
// Открыть/создать хранилище
let store = ChunkStore::open(path: &Path) -> Result<ChunkStore, NexxusError>

// Сохранить чанк
store.put_chunk(&hash: &ChunkHash, data: &[u8]) -> Result<(), NexxusError>

// Прочитать чанк
let data: Option<Vec<u8>> = store.get_chunk(&hash: &ChunkHash)? -> Result<Option<Vec<u8>>, NexxusError>
```

### 8.3 Размер чанка
`CHUNK_SIZE = 16_384` байт (16 KiB). Последний чанк не дополняется нулями.

---

## 9. Reed-Solomon 4+2 (эрasure-кодирование)

### 9.1 Параметры
- Поле: GF(2⁸), полином 0x11D
- 4 data shard + 2 parity shard = 6 всего
- P1 = XOR всех data shard
- P2 = коэффициенты Вандермонда [1, 2, 4, 8]

### 9.2 API (внутри `nexxus-core::rs`)

```rust
// Закодировать данные в 6 шардов
let shards: [Vec<u8>; 6] = encode(data: &[u8]);

// Декодировать из >=4 выживших шардов
let data: Vec<u8> = decode(shards: &[(&[u8], usize)], original_len: usize) -> Result<Vec<u8>, NexxusError>

// Восстановить отсутствующий шард
let shard: Vec<u8> = reconstruct(index: usize, surviving: &[(&[u8], usize)]) -> Result<Vec<u8>, NexxusError>
```

### 9.3 Константы
- `DATA_SHARDS = 4`, `PARITY_SHARDS = 2`, `TOTAL_SHARDS = 6`

---

## 10. Merkle-дерево и Proof-of-Retrievability (PoR)

### 10.1 Merkle
```rust
// Корень дерева (SHA-256, дублирование нечётного узла)
let root: [u8; 32] = merkle_root(leaves: &[[u8; 32]])

// Генерация доказательства включения
let proof: Vec<([u8; 32], bool)> = merkle_proof(leaves: &[[u8; 32]], leaf_index: usize)

// Проверка доказательства
let ok: bool = verify_proof(root: &[u8; 32], leaf: &[u8; 32], leaf_index: usize, proof: &[([u8; 32], bool)])
```

### 10.2 PoR
```rust
// Ответ на вызов
let response = por_response(chunk: &[u8], challenge: &PorChallenge) -> PorResponse
// где PorChallenge { seed: [u8; 32], chunk_index: usize }
// response = SHA-256(chunk || seed)

// Проверка
let ok: bool = por_verify(chunk: &[u8], response: &PorResponse, challenge: &PorChallenge)
```

---

## 11. Экономика (nexxus-econ)

### 11.1 Параметры бартера
| Параметр | Значение | Описание |
|----------|----------|----------|
| `SECTION_SIZE_GB` | 16 | Размер секции хранилища |
| `BASE_VAULT_REWARD_GB` | 2 | Квота за первую секцию |
| `EXPANDED_VAULT_RATIO` | 1/8 | Доп. квота за каждую следующую секцию |
| `VESTING_LOCK_DAYS` | 56 | Блокировка наград (8 недель) |
| `DAILY_NEXX_RATE_PER_GB` | 1.25 NEXX | Награда за 1 GB чужих чанков в день |
| `SUBSCRIPTION_DAILY_COST_PER_GB` | 1.30 NEXX | Стоимость 1 GB подписки в день |

### 11.2 API

```rust
// Разбить свободное место на секции
let split = split_into_sections(free_gb: u64) -> SectionSplit
// SectionSplit { sections_16gb, remainder_gb, vault_quota_gb }

// Дневная награда за хранение
let reward: Money = daily_storer_reward(foreign_gb: u64)

// Дневная стоимость подписки
let cost: Money = daily_subscription_cost(subscribed_gb: u64)
```

Все суммы в `Money` (micro-NEXX, integer, без float).

---

## 12. Ключи и идентификация

### 12.1 Ed25519 identité (`nexxus-core::keys::identity::Identity`)

```rust
// Новая случайná identité
let id = Identity::generate();

// Из секретных байт
let id = Identity::from_secret(&[u8; 32])?;

// NodeId = SHA-256(verifying_key)
let node_id: NodeId = id.node_id();

// Tor v3 onion адрес (сырые 35 байт)
let onion: OnionAddress = id.onion_address();

// Подпись
let sig: [u8; 64] = id.sign(message: &[u8]);

// Верификация чужого ключа
let ok: bool = Identity::verify(&verifying_key, message: &[u8], &[u8; 64])
```

### 12.2 BIP-39 мнемомника (`nexxus-core::keys::seed::IdentitySeed`)

```rust
// Новая 12-словесная мнемомника + seed
let seed = IdentitySeed::generate()?;
// seed.mnemonic — строка из 12 слов
// seed.seed — [u8; 64] (Zeroizing)

// Валидация существующей мнемомники
let seed = IdentitySeed::validate(phrase: &str)?;

// PBKDF2-HMAC-SHA512, 2048 итераций, соль "mnemonic"
```

### 12.3 SLIP-0010 HD-derivation (`nexxus-core::keys::slip10`)

```rust
// Путь: m/44'/9999'/0'/0'/0' (все indexes hardened)
let path = DerivedKey::DERIVATION_PATH; // [44|H, 9999|H, H, H, H]

// Из 64-байтного seed
let derived = DerivedKey::from_seed(&[u8; 64])?;
// derived.private_key — [u8; 32] ed25519 секретный ключ
// derived.chain_code — [u8; 32]
```

**Важно:** Путь деривации в коде (`m/44'/9999'/...`) не совпадает со спецификацией §2.1 (`m/44'/999'/...`). Требуется унификация перед релизом.

---

## 13. Управление и мониторинг

### 13.1 Журнал демона
Демон выводит в stdout/stderr:
- Старт: версия, NodeId (hex), адрес прослушивания
- Ошибки открытия хранилища
- Сетевые ошибки (connection reset, broken pipe — обрабатываются мягко)

### 13.2 Тестирование
```bash
# Все тесты workspace
cargo test --workspace

# Только core
cargo test -p nexxus-core

# Только node
cargo test -p nexxus-node

# Только econ
cargo test -p nexxus-econ
```

### 13.3 Лints
```bash
cargo clippy --workspace --all-targets -- -D warnings
```

---

## 14. Ограничения и известные проблемы

| Ограничение | Описание | Планируемое решение |
|-------------|----------|---------------------|
| Нулевая подпись v3 кадра | `frame.rs` отправляет `[0u8;64]` вместо Ed25519 | Реализовать подпись в `frame.rs` |
| EpochFinalize без реестра аудиторов | Любой может отправить валидную multi-sig | Добавить реестр аудиторов в обработчик |
| PoR challenge ≠ спецификации | Seed используется как ChunkHash, а не HMAC | Привести к HMAC-SHA256(EpochSeed, NodeId) |
| Derivation path mismatch | Код: 9999, спец: 999 | Унифицировать путь |
|ヌлевой nonce SMP | Фиксированный `[0u8;12]` | Безопасно при уникальном ключе, но добавить случайный nonce |
| Real Tor bootstrap | Требует живой Tor-сети | Отдельный smoke-тест, не в CI |
| Wasm UI | Placeholder только | Отдельный график UI-билда |

---

## 15. Безопасность

- `unsafe_code = "forbid"` на уровне workspace — никакого небезопасного кода
- Все ключи в памяти через стандартные типы `ed25519-dalek`/`curve25519-dalek`
- BIP-39 seed хранится в `Zeroizing<[u8; 64]>`
- ChaCha20-Poly1305 AEAD для всех симметричных операций
- SHA-256 для всех хэш-функций протокола
- ed25519-dalek для всех цифровых подписей

---

## 16. Лицензия и контакты

- Лицензия: MIT
- Репозиторий: https://github.com/PerfectFriend/NeXXus-Node
- Ветка: `main`
