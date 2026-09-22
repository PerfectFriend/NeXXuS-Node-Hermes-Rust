# HOT
# CyberTarot — Полный технический аудит
**Дата:** 2026-08-12  
**Аудитор:** Hermes Agent (GodModeCoder)  
**Источник:** `D:\projects\Tarot 3` → `C:\Projects\cybertarot`

---

## 1. Состав проекта

| Файл | Размер | Назначение |
|------|--------|------------|
| `CyberTarot.jsx` | 21 KB, 364 строки | React-компонент — весь UI + логика в одном файле |
| `data/tarot-deck.json` | 51 KB, 1701 строка | Полные 78 карт (22 Major + 56 Minor), EN+RU, keywords |
| `build_data.py` | 14 KB, 193 строки | Генератор tarot-deck.json (Python, запуск на Linux) |
| `localization/i18n-keys.json` | 1 KB, 21 строка | Перечень i18n ключей + статус локалей |
| `docs/architecture.md` | 4 KB | Спека архитектуры: client → backend → AI → TON |
| `docs/ai-rules-package.md` | 5 KB | System prompt для Qwen3 (3 задачи: интерпретация, минт, модерация) |
| `docs/tokenomics-ton-spec.md` | 3 KB | Токеномика: Magic Jetton, NFT тиры, gacha 70/25/5, anti-farm |
| `contracts/magic-jetton.tact` | 2 KB | TON Jetton — скелет (master + wallet) |
| `contracts/cybertarot-nft.tact` | 3 KB | TON NFT TIP-4 — скелет (collection + item, soulbound base) |
| `contracts/auction-exchange.tact` | 3 KB | Скелет (instant sell pool + peer auction escrow) |

**Нет:** package.json, vite.config, tsconfig, .gitignore, тестов, CI/CD, backend, README.

---

## 2. Что РЕАЛЬНО работает (не симуляция)

### ✅ tarot-deck.json — ПОЛНЫЙ и КОРРЕКТНЫЙ
- **78 карт**: 22 Major + 56 Minor (4 масти × 10 номеров + 4 двора)
- **2 локали**: EN + RU — обе заполнены для всех 78 карт
- Структура: `id`, `arcana`, `number`, `name{en,ru}`, `keywords{upright,reversed}{en,ru}`, `default_rarity`
- Данные проверены assertion'ом в build_data.py: `assert len(all_cards) == 78`
- **Вердикт:** production-ready данные

### ✅ i18n-keys.json — КОРРЕКТНЫЙ перечь ключей
- 19 ключей: nav, oracle, wallet, mint, referral, card tags, spread positions
- Статус: en/ru/es/pt/fr/de = complete; zh/hi/ar/ja = stub_en_fallback
- **Вердикт:** годится как спецификация, нужна реализация

### ✅ docs/ — КАЧЕСТВЕННЫЕ спецификации
- `architecture.md` — чёткая архитектура: client → backend (source of truth) → AI (Qwen3) → TON
- `ai-rules-package.md` — 3 системных промпта (интерпретация, минт-арбитраж, модерация) с hard rules
- `tokenomics-ton-spec.md` — токеномика с anti-farm, compliance flags, referral decay
- **Вердикт:** это не затычки — это продуманные спецификации уровня production

### ✅ contracts/*.tact — СТРУКТУРНЫЕ СКЕЛЕТЫ
- `magic-jetton.tact` — Jetton master + wallet, mint authority, circuit breaker
- `cybertarot-nft.tact` — NFT collection + item, soulbound base deck, transfer для rare+
- `auction-exchange.tact` — instant sell pool (70% floor), peer auction escrow, anti-wash notes
- **Не скомпилированы, не тестированы** — но логика верная, comments грамотные
- **Вердикт:** годятся как spec для Tact-разработчика, не как production код

---

## 3. Что является ЗАТЫЧКАМИ и СИМУЛЯЦИЯМИ

### 🔴 CyberTarot.jsx — ВСЁ состояние in-memory

| Функция | Что делает | Что должна делать |
|---------|-----------|-------------------|
| `draw()` (L114-121) | `Math.random()` shuffle 22 карт | Тасовать 78 карт из tarot-deck.json |
| `interpretation()` (L123-132) | Конкатенация keywords в строку | Вызов AI engine (Qwen3/Ollama) по ai-rules-package.md |
| `mint(rarity)` (L134-143) | `Math.random()` выбор карты, in-memory коллекция | Backend: deduct Magic, roll rarity server-side, mint NFT on TON |
| `rollRarity()` (L57-62) | `Math.random()` 70/25/5 | Backend deterministic roll, NOT client-side |
| `mintRandom()` (L145-147) | `mint(rollRarity())` | То же — должно быть на сервере |
| `earnMagic()` (L149-151) | `+12 Magic` по клику | Backend: daily streak check, cap, reason=login |
| `copyRef()` (L153-156) | `setCopied(true)` 1.5s timeout | Clipboard API + referral linkgeneration на сервере |
| Market sell (L347-355) | `balance + cost*0.6`, remove from array | TON: Smart contract sell-to-pool, NFT transfer |

### 🔴 Hardcoded данные в JSX вместо JSON
- `MAJORS` (L12-35) — **22 Major Arcana захардкожены** в JSX, дублируют tarot-deck.json
- **Minor Arcana (56 карт) отсутствуют в коде** — `draw()` может вытащить только 22 из 78
- `LOCALES` (L37-48) — 10 локалей захардкожены в JSX, дублируют i18n-keys.json
- `RARITY` (L50-55) — конфиг редкостей захардкожен

### 🔴 Отсутствие persistency
- `balance` (L106): `useState(58)` — ** hardcoded стартовый баланс 58 Magic**
- `collection` (L109): `useState([])` — при перезагрузке всё стирается
- `refCode` (L112): `useRef(Math.random())` — новый при каждом монтировании
- Нет localStorage, нет sessionStorage, нет backend API

### 🔴 UI/UX затычки
- Cyberpunk/Neo-Noir стиль — inline styles, **нет CSS-файла, нет Tailwind config**
- `lucide-react` импорт без package.json — не запустится без установки
- Нет роутинга — всё на вкладках (`tab` state)
- Нет responsive — `max-w-2xl mx-auto` без media queries
- Нет loading/error states — API вызовы не предусмотрены
- Нет accessibility (aria, keyboard nav, screen readers)

### 🔴 build_data.py — НЕПРАВИЛЬНЫЙ путь
- L190: `open("/home/claude/cybertarot/data/tarot-deck.json")` — hardcoded Linux путь из Claude environment
- 4 попытки (L46-79) перед финальной (L83-107) — мусорный код с комментариями "fix", "simpler", "avoid confusion"
- **Вердикт:** скрипт одноразовый, нужен rewrite или удаление

---

## 4. Архитектурные проблемы

### 🔴 Монолит 364 строки
- Весь UI + вся логика + все данные в **одном файле** `CyberTarot.jsx`
- Нет разделения: data, logic, presentation, API layer
- React компонент использует `useState` для бизнес-логики (баланс, минт, маркет)
- Нет custom hooks, нет context, нет state management

### 🔴 Нет project scaffolding
- Нет `package.json`, `vite.config`, `tsconfig.json`, `.gitignore`
- Нет `src/` структуры — единственный файл в корне
- Нет dev-сервера, нет build-pipeline
- TypeScript не используется — чистый JSX

### 🔴 Нет тестов
- 0 тестов — ни unit, ни integration, ни e2e
- `build_data.py` имеет assertion `len == 78` — единственная проверка во всём проекте

---

## 5. Резюме аудита

| Компонент | Статус | Оценка |
|-----------|--------|--------|
| **tarot-deck.json** (78 карт) | ✅ Production-ready | 9/10 |
| **docs/** (3 спецификации) | ✅ Качественные | 9/10 |
| **contracts/*.tact** (3 скелета) | ⚠️ Структурные, не скомпилированы | 5/10 |
| **i18n-keys.json** | ✅ Спека годная, реализация stub | 6/10 |
| **CyberTarot.jsx** (main app) | 🔴 In-memory mock, 22/78 карт | **2/10** |
| **build_data.py** | 🔴 Одноразовый, мусорный | 1/10 |
| **Project setup** | 🔴 Отсутствует | 0/10 |
| **Тесты** | 🔴 Нет | 0/10 |

**Итог:** ~30% проекта — качественные спецификации и данные, ~70% — прототип-затычка для демо.

---

## 6. План рефакторинга (что делаем сейчас)

### 6.1 Project scaffolding
- Vite + React + TypeScript
- Tailwind CSS + lucide-react
- Структура: `src/{components,hooks,data,services,types}/`

### 6.2 Разделение монолита
- Вынести данные → `data/` (загрузка из tarot-deck.json)
- Вынести логику → custom hooks (`useDeck`, `useBalance`, `useCollection`)
- Разбить UI → компоненты (`OracleTab`, `CollectionTab`, `MintTab`, `MarketTab`, `CardFace`)

### 6.3 Web-интерпретация
- Заглушка `interpret(cards)` → async функция, сейчас возвращает mock
- Подготовить интерфейс для Qwen3/Ollama API

### 6.4 Persistency
- localStorage для баланса, коллекции, настроек
- Т将来 — backend API

### 6.5 78 карт
- Заменить hardcoded MAJORS (22) на импорт из tarot-deck.json (78)
- `draw()` тасует полную колоду

### 6.6 Чистка
- Удалить build_data.py (ону уже сработала, JSON готов)
- Удалить дублирование LOCALES → использовать i18n-keys.json
