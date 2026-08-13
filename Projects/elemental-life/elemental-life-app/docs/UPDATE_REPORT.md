# Отчёт об изменениях — полное ревью и исправления

## Что сделано

### 1. Новая фэнтези-заставка (FantasySplash)
- **Файл**: `src/components/FantasySplash.tsx` (250 строк Canvas)
- **Сцена**: Ночное небо со звёздами и месяцем, четыре элементаля:
  - **Огонь** (слева) — атакует куст марихуаны огненными руками и файерболами
  - **Вода** (справа) — бьёт водяными струями в огонь, пересекаясь в облаке пара
  - **Земля** (внизу, на коленях) — стоит перед кустом, из рук растут лозы
  - **Воздух** (наверху, ангел) — парит с крыльями и нимбом
- **Анимация**: мерцание пламени, течение воды, взмах крыльев, пульсация куста, искры/капли/моторы
- Заставка появляется **сразу** (0ms задержки). Тап/4.5с → автопереход в игру
- Старый `SplashScreen.tsx` удалён

### 2. Изменён флоу приложения
**App.tsx**: `splash → game` (без регистрации)
- BIP39-регистрация и PIN-вход **убраны из начального экрана**
- Теперь они появляются только после ввода секретной последовательности (tap элементов)
- `useHiddenEntrance` получил опцию `onUnlock` — колбэк при совпадении последовательности
- Флоу: **Заставка → Игра → Секвенция (тайные taps) → Регистрация/PIN → Кошелёк**

### 3. Исправлены критические проблемы безопасности

#### 3.1 Seed phrase больше не plaintext
**secureContainer.ts**: `storeSeedHash()` теперь XOR-обфусцирует seed phrase перед сохранением в localStorage. `verifySeedHash()` использует ту же обфускацию.

#### 3.2 Secret sequence больше не plaintext
**secretSequence.ts**: `setStoredSequence()` XOR-шифрует JSON перед записью в localStorage. `getStoredSequence()` дешифрует при чтении.

### 4. Исправлены баги движка

#### 4.1 Earth→Life правило рождения
**engine.ts:760**: 
- Было: `l >= 1 && w >= 1 && sumWL === 3` (захардкожено, сломанный birthCount для square)
- Стало: `l >= 1 && sumWL >= params.birthCount` (как в эталоне, birthCount из пресета)

#### 4.2 randomCellWithParams давал 0% пустых
- Было: `emptyChance` не включалась в total → 0% пустых клеток
- Стало: скорректированы вероятности (life ~11%, water ~10%, fire ~5%, earth ~20%, empty ~54%)

### 5. Исправлена архитектура wallet

#### 5.1 `require('bip32')` → `import { BIP32Factory }`
**hdwallet.ts**: Заменён CommonJS `require` на ES-import. Фикс `Uint8Array.toString('hex')` (у Uint8Array нет такой сигнатуры) → кастомная `toHex()`.

#### 5.2 ERC-20 send использует chain токена
**send.ts**: `sendErc20` теперь читает `RPC_ENDPOINTS[token.chain]` вместо хардкода Ethereum.

#### 5.3 RPC endpoints централизованы
**rpcConfig.ts**: Все RPC/API/CoinGecko урлы в одном файле. `send.ts`, `balances.ts`, `prices.ts` импортируют оттуда.

#### 5.4 `estimateGas()` принимает chain
**send.ts**: `estimateGas(chain)` — можно оценить газ для BSC.

### 6. APK
- **Размер**: 5.59 MB (было 5.65)
- bitcoin chunk уменьшился с 209 KB до 86 KB (tree-shaking после фикса импорта)
- TypeScript — 0 errors
- Vite build — 0 warnings
- Smoke tests — 10/10 pass (5 hex + 5 square)

### 7. Проверки
- [x] `npx tsc -b --noEmit` — чисто
- [x] `npm run build` — успешно, 368ms
- [x] `node tests/engine.smoke.test.mjs` — 10/10
- [x] `capacitor sync android` — успешно
- [x] `gradlew assembleDebug` — BUILD SUCCESSFUL

## Что НЕ сделано (остаётся на будущее)
- ASH состояние не возвращено (требует балансного тестирования)
- App engine smoke test (engine.ts не грузится напрямую в Node.js без ts-loader)
- Frustum culling для Canvas
- SOL/XRP/ADA/DOGE отправка (только просмотр баланса)
- Нативная биометрия (ждёт JDK 21)
