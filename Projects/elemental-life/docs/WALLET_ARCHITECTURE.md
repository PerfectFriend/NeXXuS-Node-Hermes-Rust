// HOT
# Wallet Architecture — Элементарная жизнь как cover для криптокошелька

## Что есть сейчас и что сломано

- `src/engine/bip39.ts`: полный протокол BIP39 (энтропия → 12 слов → seed) — работает через `crypto.subtle`
- **Критический баг**: `crypto.subtle` недоступен на Android WebView (`file://` — не secure context). `digest()`, `importKey()`, `deriveBits()` бросают TypeError.
- `src/engine/secureContainer.ts`: PIN/backup/panic с XOR-"шифрованием" + localStorage — симуляция, не криптостойко
- `src/hooks/useIdentity.ts`: профиль пользователя (seed, прогресс) в localStorage
- `src/components/RegistrationFlow.tsx`: 5-шаговый мастер (слова → BIP39 → verify → disclaimer → PINs)
- `src/components/PinEntryScreen.tsx`: 8-цифр PIN при входе

## Фазы имплементации

### Фаза 0: Fix crypto.subtle (сейчас)

Заменить `crypto.subtle` на `@noble/hashes` — pure JS, работает везде:

| Web Crypto | Замена |
|---|---|
| `crypto.subtle.digest('SHA-256', data)` | `sha256(data)` из `@noble/hashes/sha256` |
| `crypto.subtle.importKey('raw', key, 'PBKDF2', ...)` | не нужен |
| `crypto.subtle.deriveBits({name:'PBKDF2'}, key, 4096)` | `pbkdf2(sha256, password, salt, {c:2048, dkLen:64})` из `@noble/hashes/pbkdf2` |

**Файлы для изменения:**
- `src/engine/bip39.ts`: строки 230, 271, 332-337

После фикса: `node tests/engine.smoke.test.mjs` должен проходить. BIP39 работает в любом окружении.

### Фаза 1: Онбординг как у криптокошелька

Текущий флоу идентичен кошельку (seed phrase + PIN) — нужно переписать UI, убрать game-контекст, усилить tone.

**Изменения RegistrationFlow.tsx:**
- Убрать анимацию игрового гексагона из финального шага
- Текст: не "создать персонажа", а "создать защищённый профиль"
- Seed phrase показывать с номерами в 3 колонки (как Ledger/Trezor)
- Кнопка "Я записал(а) фразу" только после 30-секундной задержки
- Верификация: выбор 3 слов из 12 (по номеру), а не ввод с клавиатуры (безопаснее)

**Изменения PinEntryScreen.tsx:**
- Дизайн как экран банковского приложения
- Анимация при неправильном PIN (вибрация поля)
- Счётчик попыток визуально (3 из 5)

### Фаза 2: Секретный вход в кошелёк

**Механизм:** последовательность тапов клеток в правильном порядке стихий.

```
Последовательность: fire → water → earth → empty → fire → water
```

**Имплементация:**

```ts
const SECRET_SEQUENCE: StateKey[] = ['fire', 'water', 'earth', 'empty', 'fire', 'water'];
```

- `useHiddenEntrance()` хук: хранит `seq: StateKey[]`, на каждый `handleCellClick` проверяет совпадение
- При полном совпадении: показывает анимацию разблокировки (свечение, короткая вибрация)
- Затем появляется кнопка/иконка "🔓 Wallet" в углу экрана
- Тап по иконке → WalletScreen

**Безопасность:** последовательность не хранится в коде в открытом виде, а как SHA256-хеш — проверка по хешу, а не по plaintext. (Но это оверкилл для cover'а — достаточно просто неочевидной последовательности.)

**UX в игре:** никаких подсказок. Игрок должен сам догадаться или узнать из "пасхалки". Можно добавить очень редкий шанс (1/10000) что симуляция сама выстроит правильную последовательность — как easter egg в самой игре.

### Фаза 3: Wallet Core

```
src/wallet/
├── index.ts          # публичный API
├── hdwallet.ts       # BIP32/BIP44 derivation из BIP39 seed
├── chains/
│   ├── evm.ts        # ETH + USDT + USDC + DAI + BNB (EVM-совместимые)
│   ├── bitcoin.ts    # BTC
│   ├── solana.ts     # SOL
│   ├── xrp.ts        # XRP
│   ├── ada.ts        # ADA
│   ├── doge.ts       # DOGE
│   └── elemental.ts  # ELEMENTAL token (internal ledger)
├── rpc.ts            # балансы через публичные RPC
├── send.ts           # построение + подпись + отправка транзакций
└── types.ts          # TokenInfo, Transaction, Balance
```

**Token config:**

| Токен | Chain | Derivation path | Тип |
|---|---|---|---|
| BTC | Bitcoin | `m/44'/0'/0'/0/0` | Native SegWit |
| ETH | Ethereum | `m/44'/60'/0'/0/0` | EOA |
| USDT | Ethereum (ERC-20) | — (на том же адресе что ETH) | ERC-20 |
| USDC | Ethereum (ERC-20) | — | ERC-20 |
| BNB | BSC | `m/44'/60'/0'/0/0` (EVM) | BEP-20 |
| SOL | Solana | `m/44'/501'/0'/0'` | Ed25519 |
| XRP | Ripple | `m/44'/144'/0'/0/0` | secp256k1 |
| ADA | Cardano | `m/44'/1815'/0'/0/0'` | ED25519 |
| DOGE | Dogecoin | `m/44'/3'/0'/0/0` | secp256k1 |
| DAI | Ethereum (ERC-20) | — | ERC-20 |
| ELEMENTAL | Internal | — | Internal ledger |

**Зависимости:**
- `ethers@6` — EVM (ETH, BSC, токены)
- `bitcoinjs-lib@6` + `@bitcoinerlab/secp256k1` — BTC
- `@solana/web3.js` — SOL
- `xrpl` — XRP
- `@emurgo/cardano-serialization-lib` — ADA (тяжёлая зависимость, можно отложить)
- Для DOGE: bitcoinjs-lib с `network = dogecoin`

**ELEMENTAL token:**
- Внутренний токен (не ERC-20 на внешней сети, если нет бюджета на газ)
- Хранится в локальном ledger'е: `Map<address, bigint>`
- Можно "добывать" через игру: достижения в puzzle дают ELEMENTAL
- Можно отправлять между пользователями (p2p через зашифрованный канал — см. ниже)

### Фаза 4: UI кошелька

**Экраны:**

1. **WalletScreen** — портфель:
   - Total balance (USD)
   - Список токенов с балансами + изменение 24h (+X%)
   - Кнопка "Receive" и "Send" для каждого токена
   - Кнопка "History"

2. **ReceiveScreen**:
   - Адрес кошелька в виде QR-кода
   - Адрес текстом (copy)
   - Выбор сети (для EVM: ETH, BSC; отдельно BTC, SOL...)

3. **SendScreen**:
   - Адрес получателя (сканировать QR или ввести)
   - Сумма (в токене и в USD)
   - Оценка газа/комиссии
   - Подтверждение с деталями
   - Отправка с PIN-подтверждением

4. **TransactionHistoryScreen**:
   - Список транзакций (дата, тип, сумма, статус)
   - Для внешних сетей: explorer-ссылка

**Стиль:** тот же тёмный theme что у игры, но без игровых отсылок. Ощущение банковского приложения.

### Фаза 5: Коммуникация (p2p)

Для отправки ELEMENTAL между пользователями нужен канал:
- Encrypted ключом получателя (через их публичный ключ, выведенный из seed phrase)
- Передача через relay server (WebSocket/WebRTC)
- Либо через QR-код (офлайн)

Это самая сложная часть. Для MVP: только receive/send внутри кошелька на одной сети (EVM). ELEMENTAL — локальный.

## Roadmap

```
Неделя 1: Фаза 0 (crypto fix) + Фаза 1 (onboarding)
  День 1: @noble/hashes, переписать bip39.ts, проверить тесты
  День 2: переписать RegistrationFlow (wallet-grade UI)
  День 3: переписать PinEntryScreen (bank-grade UI)
  День 4: hidden entrance механизм

Неделя 2: Фаза 3 (Wallet Core)
  День 5-6: HD wallet derivation (BIP32/BIP44), адреса для ETH, BTC
  День 7: balance fetching (ETH + ERC-20 токены)
  День 8: send ETH + USDT

Неделя 3: Wallet UI + остальные chain'ы
  День 9-10: WalletScreen, ReceiveScreen, SendScreen
  День 11-12: SOL, XRP (балансы + отправка)
  День 13: ELEMENTAL token + добыча через игру
  День 14: тестирование всех flow на Android

Месяц 2: Полировка
  QR-коды, transaction history, p2p ELEMENTAL
  ADA, DOGE
  Безопасность: audit, encrypt container, biometric auth (Capacitor)
```

## Security model

```
Seed phrase (12 words BIP39)
    ↓ (never stored in plaintext)
BIP39 seed (64 bytes)
    ↓
┌─ BIP32 master key ──────────────────────┐
│  m/44'/0'/0'  → BTC private key          │
│  m/44'/60'/0' → ETH private key          │
│  m/44'/501'/0'→ SOL private key          │
│  ...                                      │
└──────────────────────────────────────────┘
    ↓ (encrypted with PIN)
Secure container (localStorage)
```

**Private keys никогда не хранятся в plaintext:**
- При входе по PIN: расшифровываем seed из контейнера → держим в памяти (state, не localStorage)
- При lock/background: зануляем seed в памяти
- Для отправки: подписываем транзакцию в памяти, не сохраняем ключ

**Текущая архитектура already supports this pattern** — `SecureContainer` хранит зашифрованные данные, `mnemonicToSeed` восстанавливает seed. Нужно только заменить XOR на AES-GCM.
