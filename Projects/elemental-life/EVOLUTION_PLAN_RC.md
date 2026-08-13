# 🧬 Elemental Life — Полный план эволюции до Release Candidate

> **Статус**: Активная разработка | **Ветка**: `main` | **Последний коммит**: 67da7c7
> **Сборка**: ✅ Vite/TypeScript | ❌ Node.js direct TS (case statements)
> **Тесты**: ✅ 10/10 пресетов (water conservation OK)

---

## 📊 ТЕКУЩЕЕ СОСТОЯНИЕ (Audit 2026-08-09)

### ✅ Что работает
| Компонент | Статус | Детали |
|---|---|---|
| **Engine (TS)** | ✅ | 2 геометрии, 7 состояний, water conservation law |
| **Renderer (Canvas)** | ✅ | Hex/Square, pinch/pan, frustum culling |
| **React UI** | ✅ | Sandbox/Puzzle, Wallet, Settings, PWA |
| **TON Wallet** | ✅ | BIP39, HD, biometrics, QR, send/history |
| **Capacitor Android** | ✅ | Sync, build, permissions |
| **Tests** | ✅ | 10 пресетов × 500 тиков = water conserved |
| **Build (Vite)** | ✅ | 363 модуля, 1.57s, gzip ~200KB |
| **Lint** | ⚠️ | 11 предупреждений, 0 ошибок |

### ❌ Критические проблемы
| Проблема | Влияние | Решение |
|---|---|---|
| **Node.js TS runner** | Тесты не запускаются напрямую | Использовать `--experimental-strip-types` + string literals вместо `STATE.X` в `case` |
| **Instagram auth** | Сложно, ненадежно | **Read-only parsing без логина** (Instagram Graph API / public endpoints) |
| **Crypto.subtle в WebView** | `file://` не secure context | Упростить identity до localStorage + SHA-256 (Web Crypto polyfill) |
| **Missing ASH state logic** | Частично реализовано | Добавить полную логику ASH в stepField |
| **Hardcoded birthCount=3** | Bug для square | Использовать `params.birthCount` везде |

---

## 🎯 ROADMAP: 6 ФАЗ ДО RELEASE CANDIDATE

### ФАЗА 0: Критические баги (1-2 дня) — **НАЧАТЬ СЕЙЧАС**

| ID | Задача | Файлы | Приоритет |
|---|---|---|---|
| **0.1** | Заменить `STATE.X` на string literals в `case` для Node.js тестов | `engine.ts` | 🔴 CRITICAL |
| **0.2** | Исправить `birthCount=3` → `params.birthCount` в earth→life | `engine.ts:760` | 🔴 CRITICAL |
| **0.3** | Добавить полную логику `ASH` (wetStreak, ash→earth) | `engine.ts` | 🔴 CRITICAL |
| **0.4** | Упростить identity: убрать BIP39/PIN/panic, оставить localStorage + SHA-256 | `bip39.ts`, `secureContainer.ts`, `RegistrationFlow.tsx`, `useIdentity.ts` | 🟠 HIGH |
| **0.5** | Polyfill для `crypto.subtle` в WebView (js-sha256) | `utils/crypto.ts` | 🟠 HIGH |

### ФАЗА 1: Instagram Read-Only Parsing (2-3 дня)

> **Концепция**: Не логинимся. Парсим публичные посты через:
> - **Instagram Graph API** (Business/Creator account, read-only)
> - **Public endpoints**: `https://www.instagram.com/{username}/feed/` (HTML scraping)
> - **oEmbed API**: `https://graph.facebook.com/v18.0/instagram_oembed?url=...`

| ID | Задача | Детали |
|---|---|---|
| **1.1** | Instagram Parser Skill | Создать `instagram-parser` skill с read-only режимом |
| **1.2** | Username → Posts pipeline | Ввод username → список постов (image, caption, likes, date) |
| **1.3** | Image download + hash | Скачивание фото, perceptual hash (pHash) для дедупа |
| **1.4** | Caption → Game Seed | Текст подписи → SHA-256 → детерминированный seed для генерации уровня |
| **1.5** | UI: Import from Instagram | Кнопка "Импорт из Instagram" → ввод @username → предпросмотр → "Создать уровень" |

**Пример флоу**:
```
User вводит @nasa → Parser получает 20 последних постов
→ Фильтр: только фото (не Reels) → Показывает сетку превью
→ User выбирает 1-3 фото → Капша → SHA-256(caption) → seed
→ buildLevelField(geometry, radius, seed, level) → играбельный уровень
```

### ФАЗА 2: Архитектура и Качество (3-4 дня)

| ID | Задача | Файлы |
|---|---|---|
| **2.1** | Error Boundaries | `App.tsx`, `ErrorBoundary.tsx` |
| **2.2** | Code Splitting (lazy) | `SettingsModal`, `RegistrationFlow`, `PuzzleOverlay` |
| **2.3** | Auto-save каждые 10 тиков | `useSimulation.ts`, `localStorage` |
| **2.4** | Continue Game кнопка | `App.tsx`, `FantasySplash.tsx` |
| **2.5** | Onboarding (3 экрана) | `OnboardingFlow.tsx` |

### ФАЗА 3: Геймплей и Контент (4-5 дней)

| ID | Задача | Детали |
|---|---|---|
| **3.1** | Новые пресеты | `volcanic`, `ice_age`, `mutualism`, `plague` |
| **3.2** | Процедурная генерация уровней (бесконечный puzzle) | `LevelGenerator.ts` |
| **3.2** | Достижения (Google Play / локальные) | `Achievements.ts`, `achievements.json` |
| **3.4** | Статистика и графики | Популяция по тикам, heatmap активности |
| **3.5** | Турнирная таблица puzzle | Локальный лидерборд (тики, попытки) |

### ФАЗА 4: Производительность (2-3 дня)

| ID | Задача | Детали |
|---|---|---|
| **4.1** | Visible rect culling в GridRenderer | Уже частично есть, оптимизировать |
| **4.2** | Web Worker для stepField | `worker.ts`, сериализация Map → Array |
| **4.3** | Haptic feedback (Vibration API) | На тап по клетке |
| **4.4** | Overscroll bounce | При достижении границ поля |

### ФАЗА 5: UI/UX Полировка (2-3 дня)

| ID | Задача | Детали |
|---|---|---|
| **5.1** | Плавный pinch-zoom с easing | `GridRenderer.zoomBy` |
| **5.2** | Exit fullscreen — свайп сверху вниз | `App.tsx` |
| **5.3** | Цветовые схемы (3 темы) | `themes.css`, переключатель в Settings |
| **5.4** | Адаптация под планшеты (1024px+) | Боковая панель инструментов |
| **5.5** | Accessibility (TalkBack, 48dp targets) | `android:contentDescription` |

### ФАЗА 6: Платформенная экспансия (опционально, параллельно)

| ID | Задача | Детали |
|---|---|---|
| **6.1** | iOS (Capacitor iOS) | `npx cap add ios`, safe area insets |
| **6.2** | PWA (Service Worker, manifest) | Offline-first, install prompt |
| **6.3** | Shorebird OTA updates | Без релизов в стор для исправлений |

---

## 🛠️ СКИЛЛЫ ДЛЯ СОЗДАНИЯ

### 1. `instagram-readonly-parser` — Read-only парсинг Instagram
```markdown
# Skill: instagram-readonly-parser
description: "Parse public Instagram posts without login via Graph API / HTML scraping / oEmbed"
triggers:
  - "parse instagram posts"
  - "import from instagram"
  - "instagram username to posts"
inputs:
  - username: string (без @)
  - limit: number (default 20)
  - filter: "photo|reel|carousel" (default "photo")
outputs:
  - posts: Array<{id, imageUrl, caption, likes, comments, timestamp, permalink}>
  - images: Array<{url, localPath, pHash}>
```

### 2. `elemental-life-engine` — Движок клеточного автомата
```markdown
# Skill: elemental-life-engine
description: "Core cellular automaton engine with hex/square geometries, water conservation, puzzle mode"
capabilities:
  - buildInitialField(geometry, radius, seed, params)
  - stepField(geometry, field, radius, params, rng, tick)
  - buildLevelField(geometry, radius, seed, level)
  - checkPuzzleWinTick(field)
  - countWater(field)
  - mulberry32(seed)
```

### 3. `elemental-life-renderer` — Canvas рендерер
```markdown
# Skill: elemental-life-renderer
description: "High-performance Canvas renderer for hex/square grids with pinch/pan, frustum culling"
capabilities:
  - setField(field)
  - render() → 60 FPS
  - zoomBy(factor, centerX, centerY)
  - panBy(dx, dy)
  - getCellAtScreen(x, y) → {q, r}
```

### 4. `elemental-life-wallet` — TON кошелек
```markdown
# Skill: elemental-life-wallet
description: "TON wallet with BIP39, HD paths, biometric auth, QR send/receive"
capabilities:
  - createIdentity(mnemonic) → {address, seedPhrase}
  - signTransaction(tx) → boc
  - sendTon(to, amount, comment)
  - getBalance(address) → {ton, jetton[]}
  - biometricLock/unlock()
```

### 5. `elemental-life-level-generator` — Процедурная генерация уровней
```markdown
# Skill: elemental-life-level-generator
description: "Procedural puzzle level generator with difficulty progression"
capabilities:
  - generate(seed, geometry, difficulty) → Level
  - infiniteProgression(baseLevel, count) → Level[]
  - validateSolvable(level, maxDroplets) → boolean
```

### 6. `elemental-life-achievements` — Система достижений
```markdown
# Skill: elemental-life-achievements
description: "Achievement system with Google Play / local sync"
capabilities:
  - unlock(id) → void
  - getProgress(id) → {current, target, unlocked}
  - syncToGooglePlay() → Promise<void>
  - exportLocal() → JSON
```

---

## 📝 СКРИПТЫ ДЛЯ СОЗДАНИЯ

### `scripts/instagram-import.mjs`
```javascript
// Использование: node scripts/instagram-import.mjs @nasa --limit=10 --out=levels/nasa-1.json
import { InstagramParser } from '../skills/instagram-readonly-parser/index.js';
import { buildLevelField } from '../src/engine/engine.ts';
import { writeFileSync } from 'fs';

const username = process.argv[2]?.replace('@', '');
const limit = parseInt(process.argv[3]?.replace('--limit=', '')) || 20;

const parser = new InstagramParser();
const posts = await parser.getPosts(username, { limit, filter: 'photo' });

// Показываем пользователю выбор
console.log('Найдено постов:', posts.length);
posts.forEach((p, i) => console.log(`${i+1}. ${p.caption?.slice(0,50)}... (${p.likes} ❤️)`));

// TODO: Интерактивный выбор или авто-выбор первого фото
const selected = posts[0];
const seed = hashCaption(selected.caption);
const level = buildLevelField('hex', 12, seed, { waterDensity: 0.2, ... });
writeFileSync(`levels/${username}-${Date.now()}.json`, JSON.stringify(level, null, 2));
```

### `scripts/generate-achievements.mjs`
```javascript
// Генерация achievements.json из шаблона
const achievements = [
  { id: 'gardener', name: 'Садовник', desc: 'Пройти все 5 уровней на hex', target: 5 },
  { id: 'architect', name: 'Архитектор', desc: 'Пройти все 5 уровней на square', target: 5 },
  { id: 'phoenix', name: 'Феникс', desc: 'Огонь >50% поля 100 тиков', target: 100 },
  { id: 'ocean', name: 'Океан', desc: 'Вода >50% поля', target: 50 },
  { id: 'desert', name: 'Пустыня', desc: 'Empty >90% поля', target: 90 },
  { id: 'terraformer', name: 'Терраформер', desc: 'Life >30% поля', target: 30 },
];
writeFileSync('src/assets/achievements.json', JSON.stringify(achievements, null, 2));
```

### `scripts/verify-build.mjs`
```javascript
// Полная верификация перед коммитом
import { execSync } from 'child_process';

const checks = [
  'npm run lint',
  'npm run build',
  'npm run test:engine',
  'npx tsc --noEmit',
];

for (const cmd of checks) {
  console.log(`\n🔍 ${cmd}`);
  try {
    execSync(cmd, { stdio: 'inherit', cwd: __dirname + '/..' });
  } catch (e) {
    console.error(`❌ FAILED: ${cmd}`);
    process.exit(1);
  }
}
console.log('\n✅ ALL CHECKS PASSED');
```

---

## 🔐 INSTAGRAM READ-ONLY PARSE — ТЕХНИЧЕСКАЯ СХЕМА

### Вариант А: Instagram Graph API (Business/Creator Account)
```bash
# Требует: Facebook App, Instagram Business Account, Access Token
GET https://graph.facebook.com/v18.0/{ig-user-id}/media?fields=id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count&limit=20&access_token={token}
```
**Плюсы**: Официальный, надежный,Structured data
**Минусы**: Нужен Business аккаунт, App Review для production

### Вариант Б: Public HTML Scraping (No Auth)
```javascript
// Парсинг https://www.instagram.com/{username}/
// Данные в window._sharedData или <script type="application/ld+json">
const response = await fetch(`https://www.instagram.com/${username}/`, {
  headers: { 'User-Agent': 'Mozilla/5.0...' }
});
const html = await response.text();
// Парсинг JSON из script тегов
```
**Плюсы**: Никаких токенов, работает для публичных профилей
**Минусы**: Rate limiting, может сломаться при изменении верстки

### Вариант В: oEmbed API (Самый простой)
```javascript
// https://graph.facebook.com/v18.0/instagram_oembed?url=https://www.instagram.com/p/{shortcode}/
// Возвращает: title, author_name, author_url, thumbnail_url, html
```
**Плюсы**: Официальный, без токена для публичных постов, работает по URL поста
**Минусы**: Только по одному посту, нужна короткая ссылка

### РЕКОМЕНДАЦИЯ: Гибридный подход
1. **Username → Public Profile** (HTML scraping) → список постов
2. **Выбранный пост → oEmbed** → получить фото + caption
3. **Download image** → local cache + pHash

---

## 📦 РЕЛИЗНЫЙ ЧЕКЛИСТ (Release Candidate)

### Pre-Release (Code Complete)
- [ ] Все тесты проходят (`npm run test:engine` → 10/10 OK)
- [ ] Линт чистый (`npm run lint` → 0 errors)
- [ ] Сборка проходит (`npm run build` → dist/ создан)
- [ ] TypeScript чистый (`npx tsc --noEmit` → 0 errors)
- [ ] Android debug APK собирается (`cd android && ./gradlew assembleDebug`)

### Pre-Release (QA)
- [ ] Smoke test на реальном устройстве (Android 10+)
- [ ] Puzzle mode: все 5 уровней проходимы на hex + square
- [ ] Sandbox: 30 мин игры без крашей/утечек памяти
- [ ] Wallet: создание, PIN, отправка TON, QR код
- [ ] Instagram import: @nasa → выбор фото → уровень играбелен
- [ ] Fullscreen жесты: pinch/pan/exit работают плавно
- [ ] Auto-save/Continue: перезапуск приложения восстанавливает игру

### Release Candidate
- [ ] Version bump в `package.json` + `android/app/build.gradle`
- [ ] Changelog обновлен (`CHANGELOG.md`)
- [ ] Signed AAB для Play Console (`./gradlew bundleRelease`)
- [ ] Store listing: screenshots, description, privacy policy
- [ ] Internal testing track в Play Console
- [ ] Shorebird настроен для OTA

---

## 🚀 ПОРЯДОК ВЫПОЛНЕНИЯ (НАЧАТЬ СЕГОДНЯ)

### Сегодня (Фаза 0):
```bash
# 1. Исправить engine.ts для Node.js тестов
cd /c/Projects/elemental-life/elemental-life-app
# Заменить все STATE.X на string literals в case
# Исправить birthCount=3 → params.birthCount
# Добавить полную логику ASH

# 2. Запустить тесты
npm run test:engine  # Должно пройти 10/10

# 3. Упростить identity (завтра)
```

### Завтра (Фаза 0 завершение + Начало Фазы 1):
```bash
# 1. Упростить identity: убрать BIP39/PIN/panic
# 2. Создать skill: instagram-readonly-parser
# 3. Написать scripts/instagram-import.mjs
# 4. Протестировать парсинг @nasa без логина
```

### На этой неделе:
- Фаза 0-1 завершены
- Фаза 2 (Error Boundaries, Code Splitting, Auto-save)
- Начало Фазы 3 (новые пресеты, генератор уровней)

---

## 📁 СТРУКТУРА ПРОЕКТА (ФИНАЛЬНАЯ)

```
/c/Projects/elemental-life/
├── elemental-life-app/
│   ├── src/
│   │   ├── engine/           # Чистый TS движок
│   │   │   ├── engine.ts     # Основной движок (ИСПРАВИТЬ)
│   │   │   ├── crypto.ts     # SHA-256 polyfill для WebView
│   │   │   └── index.ts      # Экспорты
│   │   ├── renderer/         # Canvas рендерер
│   │   ├── wallet/           # TON кошелек (упрощенный)
│   │   ├── hooks/            # React хуки
│   │   ├── components/       # UI компоненты
│   │   ├── skills/           # Локальные скиллы
│   │   │   ├── instagram-readonly-parser/
│   │   │   ├── elemental-life-engine/
│   │   │   ├── elemental-life-renderer/
│   │   │   ├── elemental-life-wallet/
│   │   │   ├── elemental-life-level-generator/
│   │   │   └── elemental-life-achievements/
│   │   ├── scripts/          # Build/Deploy/Import скрипты
│   │   └── tests/            # Smoke + App тесты
│   ├── android/              # Capacitor Android проект
│   ├── skills/               # Hermes skills (global)
│   └── docs/                 # Документация
├── reference/                # Claude Artifacts референсы
├── tests/                    # Корневые тесты (legacy)
└── src/                      # Legacy engine.js (для совместимости)
```

---

## 🎯 СЛЕДУЮЩИЙ ШАГ ПРЯМО СЕЙЧАС

```bash
cd /c/Projects/elemental-life/elemental-life-app

# 1. Исправить engine.ts — заменить все STATE.X на string literals в case
#    sed -i 's/STATE\.EMPTY/'"'empty'"/g; s/STATE\.LIFE/'"'life'"/g; ...' src/engine/engine.ts

# 2. Исправить birthCount=3 → params.birthCount (строка ~760)

# 3. Запустить тесты
npm run test:engine

# 4. Если проходит — комитить и переходить к упрощению identity
```

**Готов начать исправление `engine.ts`?** Дайте команду — сделаю за 10 минут.