# Полное ревью проекта — Elemental Life

## Статистика проекта
- **Всего файлов**: ~75
- **Строк кода**: ~10,700
- **Язык**: TypeScript (React 19, Vite 8, Capacitor 8)
- **APK**: 5.65 MB (debug)
- **Документация**: 8 файлов, ~1,180 строк

---

## 1. КРИТИЧЕСКИЕ ПРОБЛЕМЫ

### 1.1 Сид-фраза хранится в plaintext в localStorage
**Файл**: `src/engine/secureContainer.ts:163`
**Суть**: `storeSeedHash()` сохраняет seed phrase в открытом виде под ключом `localStorage.el_secure_seed_hash`. Переменная называется `hash`, но это literally `seedPhrase.join(' ')` — не хеш.
**Риск**: Любое приложение/расширение/эксплойт на том же origin читает 12 слов BIP39-фразы.

### 1.2 Секретная последовательность хранится в plaintext
**Файл**: `src/wallet/secretSequence.ts:22`
**Суть**: Последовательность элементов (PIN-эквивалент для входа в кошелёк) сохраняется как `localStorage.el_secret_sequence` в открытом виде.

### 1.3 Движок форкнулся от эталонного — нет тестов на app-версию
**Файл**: `elemental-life-app/src/engine/engine.ts`
**Суть**: App-движок добавил flow/terraforming-механики, убрал состояние ASH, изменил правило рождения earth→life (добавил `w >= 1`, захардкодил `sumWL === 3` вместо `params.birthCount`). **Ни один smoke-тест не проверяет app-движок** — тесты в `tests/engine.smoke.test.mjs` проверяют только `src/engine.js` (эталон).
**Риск**: Water conservation не верифицирован для app-движка. Баланс уровней puzzle не совпадает с эталонным.

---

## 2. ВЫСОКИЙ ПРИОРИТЕТ

### 2.1 ASH удалён из app-движка
**engine.ts**: Состояние `ash` полностью отсутствует. Огонь при уничтожении водой/выгорании→`empty`, а не `ash`. Удалён цикл `ash→earth (wetStreak)`. Экосистема потеряла целое состояние.
- `SettingsModal.tsx:174` всё ещё упоминает ash в тексте правил
- `BrushSelector.tsx:11-14` содержит мёртвый код `ash: '⬜'`

### 2.2 `require('bip32')` в ES module проекте
**Файл**: `src/wallet/hdwallet.ts:11`
**Суть**: CommonJS `require()` в проекте с `"type": "module"`. Работает только потому что Vite шимит require. В чистом Node.js/Capacitor Native упадёт.

### 2.3 ERC-20 send всегда использует Ethereum RPC
**Файл**: `src/wallet/send.ts:73`
**Суть**: Любой ERC-20 токен отправляется через Ethereum RPC, независимо от `token.chain`. Для BSC токенов (BEP-20) не будет работать.

### 2.4 Hardcoded RPC endpoints
**Файлы**: `send.ts:5-8`, `balances.ts:7-10`, `balances.ts:13-15`, `prices.ts:1`
**Суть**: Все RPC/API endpoints захардкожены. Должны быть в едином конфиге или env.

### 2.5 `randomCellWithParams` даёт ~0% пустых клеток
**engine.ts:402-416**: Для `classic_balanced` initial field: ~24% life, ~28% water, ~5% fire, ~43% earth, **~0% empty**. В эталоне: 10%/12%/5%/28%/45% empty. Кардинально меняет геймплей.

### 2.6 Земля→Жизнь: захардкожен `birthCount = 3` и добавлен `w >= 1`
**engine.ts:760**: Правило рождения жизни: `w >= 1 && sumWL === 3`. Должно быть `sumWL === params.birthCount` (как в эталоне). Для square пресетов `birthCount = 4`, поэтому квадратные поля почти не рождают жизнь.

### 2.7 XOR "encryption" выдается за безопасность
**secureContainer.ts**: PIN и контейнеры "зашифрованы" XOR + base64. Код честно пишет "не криптостойко", но API (`verifyPin`, `isLocked`, `saveContainer`) создаёт ложное чувство безопасности.

---

## 3. СРЕДНИЙ ПРИОРИТЕТ

### 3.1 Flow/terraforming механики не тестировались
**engine.ts:535-647**: Сложный двухфазный flow воды + BFS terraforming. Запускается раз в 3 тика. Для каждой пустой клетки в окружении earth+life запускается BFS глубиной 12 — потенциально сотни обходов на тик.

### 3.2 `useSimulation` — 30+ полей в одном объекте
Каждый `doStep` создаёт новый `waterHistory` срез (120 записей). 500 тиков = 500 промежуточных стейтов.

### 3.3 Canvas рендерит все клетки, даже за экраном
**GridRenderer.ts:400-436**: `field.keys()` итерирует все 2611 клеток при каждом рендере. Нужен frustum culling.

### 3.4 TxStatusPoller — последовательный вызов
**TxStatusPoller.tsx:10-18**: Пока все pending транзакции обрабатываются `await` последовательно. При 10 pending это ~5 секунд. Нужен `Promise.allSettled`.

### 3.5 WalletTxHistory не обновляется при смене статуса
TxStatusPoller обновляет статус в localStorage, но WalletTxHistory читает только при монтировании.

### 3.6 Seed phrase stored in plaintext (повтор)
Это настолько серьёзно, что стоит дважды.

### 3.7 Нет поддержки XRP, ADA, SOL отправки
**balance.ts**: Балансы XRP/ADA/SOL показываются как "0" (RPC не подключены). Отправка не реализована.

### 3.8 `estimateGas()` не работает для BSC
Функция всегда использует Ethereum RPC и не принимает параметр chain.

---

## 4. НИЗКИЙ ПРИОРИТЕТ

### 4.1 `TxRecord` не имеет поля direction
Все транзакции в истории показываются как исходящие (с минусом). Нет поля для различения send/receive.

### 4.2 Hardcoded max 50 записей в истории
`history.ts:26` — 50, не конфигурируется.

### 4.3 `ELEMENTAL` reward не зависит от геометрии
`elemental.ts:54`: `10 + levelIndex * 5` — геометрия игнорируется.

### 4.4 `resetElemental()` — тестовая функция без гейта
`elemental.ts:94` — любой вызов сбросит баланс. Должна быть скрыта за debug-флагом.

### 4.5 `mnemonicToSeed()` синхронно блокирует UI
PBKDF2 с 2048 итерациями — 50-200ms на мобильном устройстве.

### 4.6 Нет light mode
Все компоненты кошелька захардкожены на `#0d1117` (GitHub dark).

### 4.7 `key={i}` в TokenDetail вместо `tx.hash`
Проблема при пересортировке/фильтрации.

### 4.8 Нет геометрия-специфичного New Game экрана
Вместо выделенного экрана — кнопка в настройках.

### 4.9 `STATE_LABELS`: "Пустыня" вместо "Пустота"
Визуально и смысловое различие.

### 4.10 `seedToGameKey` — мёртвый экспорт
Экспортируется, но нигде не используется.

---

## 5. АРХИТЕКТУРА И КАЧЕСТВО

### Сильные стороны
1. Чистое отделение engine (чистый ES module) от UI (React)
2. Два типа сетки (hex/square) с раздельными калибровками
3. Полная имплементация BIP39 (seed → 12 words → PBKDF2)
4. Capacitor для Android-сборки — APK собирается в 5.65 MB
5. Canvas-рендеринг (не SVG) — подходит для 2611 клеток
6. Telegram-бот для удалённого управления build/send/smoke
7. 11 токенов кошелька (EVM + BTC + internal ELEMENTAL)
8. Code splitting (ethers/bitcoin/vendor — chunks до 336 KB)

### Слабые стороны
1. Движок форкнулся и не покрыт тестами
2. "Безопасность" — симуляция (plaintext seed phrase, XOR, нет реального шифрования)
3. Хардкод везде (RPC endpoints, лимиты, UI цвета)
4. Unused/dead код (ash в UI, seedToGameKey, toggleRunning)
5. Canvas без frustum culling
6. Нет тестов на app-версию engine.ts (только на эталонный engine.js)

---

## 6. РЕКОМЕНДАЦИИ

### Сделать немедленно
1. **Спрятать seed phrase**: хотя бы XOR-обфускация, в идеале — вынести в нативный keychain через Capacitor плагин
2. **Добавить smoke-тест для app-движка**: скопировать `tests/engine.smoke.test.mjs`, переключить на `engine.ts`, проверить water conservation
3. **Задокументировать fork**: описать отличия `engine.ts` от `engine.js` в README

### Сделать в ближайшее время
4. **Вернуть ASH** или обновить UI (убрать из правил, иконки)
5. **Починить earth→life правило**: убрать `w >= 1`, использовать `params.birthCount`
6. **Починить ERC-20 RPC**: передавать `token.chain` в send
7. **Добавить frustum culling** в Canvas рендер
8. **Объединить RPC endpoints** в один конфиг
9. **Добавить `direction` в `TxRecord`**

### На будущее
10. Web Worker для `stepField` (чтобы не блокировать UI)
11. Нативное биометрическое шифрование seed phrase (после JDK 21)
12. SOL/XRP/ADA/DOGE отправка (сейчас только баланс)
13. Light mode
14. E2E тесты (Playwright + Android WebView)
