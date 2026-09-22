# HOT
# CyberTarot — План эволюции до RC (Release Candidate)
**Дата:** 2026-08-12  
**Автор:** Hermes Agent (GodModeCoder)  
**Проект:** `C:\Projects\cybertarot`

---

## Текущее состояние (после рефакторинга + ManaWell)

| Компонент | Статус |
|-----------|--------|
| Vite + React + TS | ✅ Настроен |
| Tailwind CSS | ✅ Настроен |
| 78 карт из JSON | ✅ Загружаются |
| 10 локалей | ✅ В игре |
| localStorage persistence | ✅ Работает (balance, collection, locale, refCode, well) |
| Монолит разбит на компоненты | ✅ 6 компонентов + hook + 2 сервиса |
| **ManaWell: колодец маны** | ✅ 1→+1/6ч, пересыхание, статистика, уведомления |
| Interpretation service | ⚠️ Mock (готов к замене на AI) |
| Тесты | ❌ Нет |
| Backend | ❌ Нет |
| TON интеграция | ❌ Нет |
| AI engine | ❌ Mock |
| **Limited Edition Series** | ❌ Не начато |
| **Push-уведомления** | ❌ Нет |

---

## Фаза 1: MVP — рабочий web-клиент (готов)

### 1.1 Базовый функционал ✅
- [x] Vite + React + TypeScript scaffold
- [x] 78 карт (22 мажорных + 56 минорных) из tarot-deck.json
- [x] 10 локалей, переключатель языка, RTL для арабского
- [x] Oracle: 1 или 3 карты, тасование полной колоды 78
- [x] Mint: 3 тиры (rare/epic/legendary) + weighted random 70/25/5
- [x] Collection: просмотр заминченных карт
- [x] Market: sell карт за 60% стоимости
- [x] Balance + referral (clipboard copy)
- [x] localStorage persistence

### 1.2 ManaWell ✅
- [x] Колодец: первая мана = 1
- [x] Каждые 6 часов: +1 мана (нарастающее вознаграждение)
- [x] Пересыхание если не собран за 6 часов после наполнения
- [x] Сброс до 1 маны после пересыхания
- [x] UI: таймер до наполнения, таймер до пересыхания, risk bar
- [x] Stats: total harvests, total mana, total dry-outs
- [x] Notification banners: "Колодец наполнен" / "Колодец пересох"
- [x] Quick indicator в header bar (🪻 N)
- [x] Зелёная точка на табе Well когда мана готова
- [x] Rules explanation для игрока

### 1.3 UI/UX доработка
- [ ] Responsive: mobile-first, media queries
- [ ] Карточный дизайн: SVG-арт для Старших Арканов (Gen 1)
- [ ] Анимации: draw (flip), mint (glow), harvest (liquid), sell (fade)
- [ ] Loading state для interpretation
- [ ] Error boundary
- [ ] Toast уведомления ("+1 Magic", "Minted: The Fool [Rare]")
- [ ] Sound effects (ambient + interaction)

### 1.4 Тесты
- [ ] Unit: `shuffleDeck` возвращает правильное кол-во
- [ ] Unit: `rollRarity` распределяет ~70/25/5
- [ ] Unit: `mint` списывает баланс, добавляет в коллекцию
- [ ] Unit: `sellCard` добавляет 60%, удаляет из коллекции
- [ ] Unit: `interpret` возвращает корректный JSON
- [ ] Unit: `tickWell` — fill/dry логика
- [ ] Unit: `harvestWell` — списание + статистика
- [ ] Unit: `tickWell` — пересыхание сбрасывает pending
- [ ] Integration: draw → interpretation → mint → sell цикл
- [ ] Integration: harvest → mint → sell цикл
- [ ] Component: ManaWellTab рендерит таймеры
- [ ] Component: CardFace рендерит карту с правильной ориентацией

---

## Фаза 2: Limited Edition Series — коллекционная жажда (неделя 2)

### 2.1 Series Data Model
- [ ] `Series` type: id, name, description, banner, cards[], rarities[], mintCap, mintStart, mintEnd, burnUnsold
- [ ] `series.json` — каталог всех выпущенных серий
- [ ] Backend: выпуск серии = создание записи + mint window
- [ ] Каждая серия имеет уникальный визуальный стиль (cyberpunk/neon/retro/organic)

### 2.2 Series Mint UI
- [ ] "Limited Series" блок в Mint tab
- [ ] Countdown: до конца минта (FOMO timer)
- [ ] Minted counter: "342/1000 minted" (прогресс бар)
- [ ] Preview карт серии (blur для неизвестных)
- [ ] Batch mint: "Mint 5 from series" (со скидкой)
- [ ] Series detail modal: lore, art preview, rarity odds

### 2.3 Burn Mechanics
- [ ] После mintEnd: непроданные карты сжигаются (burn transaction)
- [ ] Supply уменьшается → remaining Karten становятся ценнее
- [ ] "This series is now rare! Only 342 exist." badge
- [ ] Ember эффект при сжигании (анимация)

### 2.4 Collection Sorting & Filters
- [ ] Filter: by series, by rarity, by arcana
- [ ] Sort: newest, oldest, rarity, name
- [ ] Search by card name
- [ ] "Series completion" badge: 78/78 collected

---

## Фаза 3: AI Engine — живые расклады (неделя 3)

### 3.1 Local AI (Ollama / Qwen3)
- [ ] Настроить Ollama на Windows (CPU mode для AMD 780M)
- [ ] Реализовать `POST /api/interpret` endpoint
- [ ] System prompt из `docs/ai-rules-package.md`
- [ ] JSON schema validation ответа
- [ ] Rate limiting: 1 запрос / 30 сек на пользователя
- [ ] Fallback: если AI недоступен → keyword mock

### 3.2 Push-уведомления (ManaWell)
- [ ] Request Notification permission при первом harvest
- [ ] Service Worker для background notifications
- [ ] "🪻 Колодец наполнен! Забери N маны" push
- [ ] "⚠️ Колодец пересохнет через 1 час!" warning push (за час до дедлайна)
- [ ] "🔥 Новая лимитированная серия: 'Neon Oracle'!" push при выпуске серии

### 3.3 Локализация трактовок
- [ ] AI получает `locale` → отвечает на нужном языке
- [ ] 6 полных локалей: en, ru, es, pt, fr, de
- [ ] 4 stub локали: zh, hi, ar, ja (machine translation fallback)

---

## Фаза 4: TON интеграция (неделя 4-5)

### 4.1 TON Connect
- [ ] Интегрировать `@tonconnect/web-sdk`
- [ ] Wallet auth: подключение кошелька → адрес как ID
- [ ] Disconnect flow
- [ ] QR код для mobile wallet

### 4.2 Magic Jetton
- [ ] Компилировать `magic-jetton.tact` → TON testnet
- [ ] Backend: `MintMagic` message подписан mintAuthority
- [ ] Balance query: чтение jetton wallet balance
- [ ] Transfer: отправка Magic между кошельками
- [ ] ManaWell: on-chain verification (опционально, для anti-cheat)

### 4.3 NFT коллекция
- [ ] Компилировать `cybertarot-nft.tact` → TON testnet
- [ ] Backend: `MintCard` message → deploy item contract
- [ ] Soulbound: base deck (common) non-transferable
- [ ] Transfer: rare+ карты переносимы между кошельками
- [ ] Metadata: IPFS/pinned JSON для каждой NFT
- [ ] Series NFT: серия = коллекция контрактов на TON

### 4.4 Marketplace
- [ ] Instant sell pool: sell за 70% Magic
- [ ] Peer auction: English auction escrow contract
- [ ] Anti-wash-trade: backend denylist (device/IP fingerprint)
- [ ] Series marketplace: фильтр по сериям, rarity badges

---

## Фаза 5: Backend (неделя 4-6, параллельно с TON)

### 5.1 API сервер (Node.js + TypeScript)
- [ ] Express/Fastify REST API
- [ ] PostgreSQL: users, balances, collection, referrals, audit log, series
- [ ] Endpoints:
  - `POST /api/interpret` → AI engine
  - `POST /api/mint` → deduct Magic, roll rarity, signature for TON
  - `GET /api/balance/:address` → jetton + NFT balance
  - `POST /api/earn` → mana well harvest (server-side timer verification)
  - `POST /api/referral` → referral link generation
  - `GET /api/collection/:address` → NFT inventory
  - `POST /api/series/create` → admin: create new limited series
  - `GET /api/series/active` → list active series + countdown
  - `POST /api/series/mint` → mint from limited series
  - `POST /api/series/burn` → burn unsold after mintEnd
- [ ] Auth: TON Connect signature verification
- [ ] Rate limiting per endpoint
- [ ] Server-side ManaWell timer (anti-cheat: клиент не может придумать сколько маны)

### 5.2 Indexer
- [ ] TON event indexer (tonapi.io или self-hosted)
- [ ] Listen: MintMagic, MintCard, Transfer, Burn events
- [ ] Sync on-chain state → database
- [ ] Audit log: append-only record всех mint/transfer/sell/burn

### 5.3 Admin Dashboard
- [ ] Создание новых серий (upload art, set rarities, mint window)
- [ ] Мониторинг: активные игроки, mint объёмы, burn статистика
- [ ] Push notification sender: анонс новой серии всем игрокам
- [ ] Anti-fraud: suspicious pattern alerts

---

## Фаза 6: Polish && RC (неделя 7)

### 6.1 Performance
- [ ] Lazy load tarot-deck.json (78 карт × 10 языков)
- [ ] Code splitting: vendor + app + data bundles
- [ ] Image lazy load для карт
- [ ] Service worker (PWA offline)
- [ ] Background sync для ManaWell (работает даже когда вкладка закрыта)

### 6.2 Accessibility
- [ ] Keyboard navigation (tab/enter/escape)
- [ ] Screen reader labels (aria-label для карт)
- [ ] Color contrast WCAG AA минимум
- [ ] Reduced motion media query

### 6.3 Compliance
- [ ] Вероятности mint: раскрыть 70/25/5 в UI
- [ ] Loot box warning для юрисдикций (Belgium, Netherlands)
- [ ] Privacy policy
- [ ] ToS с разделом про крипто-активы
- [ ] Responsible gaming: таймер сессии + мягкий cooldown

### 6.4 Deployment
- [ ] Vercel/Netlify для web-клиента
- [ ] Hetzner VPS для backend + Ollama
- [ ] TON testnet → mainnet migration
- [ ] Domain + HTTPS
- [ ] CDN для card art assets

### 6.5 RC Checklist
- [ ] Все unit + integration тесты зелёные
- [ ] E2E: полный цикл wallet → draw → harvest → mint → sell
- [ ] E2E: series mint → burn unsold → remaining cards ценнее
- [ ] TON testnet: 10 успешных mint транзакций
- [ ] AI engine: 50 интерпретаций без hallucination
- [ ] ManaWell: 72 часа теста (fill → harvest → fill → forget → dry → restart)
- [ ] Performance: LCP < 2.5s, TTI < 3.5s
- [ ] 6 локалей проверены носителями
- [ ] Security audit: no private keys in client, SQL injection, XSS
- [ ] Push notifications: delivery rate > 90%

---

## Risks & Mitigation

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| TON contract компиляция (Tact молод) | Средняя | Начать с testnet, иметь fallback на EVM (Polygon) |
| Qwen3 на CPU медленный | Высокая | Streaming ответ, fallback на Mistral Small |
| Loot box regulation | Высокая | Прямые продажи mini-sets (без gacha), раскрытие odds |
| AI hallucination в трактовках | Средняя | JSON schema validation, hard rules в system prompt |
| Anti-wash-trade | Средняя | Backend device fingerprint + IP clustering |
| ManaWell client-side cheating | Высокая | Server-side timer verification (Phase 5) |
| Series art pipeline (нужен художник) | Высокая | Start with AI-generated art (Stable Diffusion / Midjourney) |
| Push notification permissions denied | Средняя | In-app fallback + email notifications |

---

## Ключевые метрики RC

| Метрика | Цель |
|---------|------|
| DAU (Daily Active Users) | 100+ |
| D1 retention | >40% |
| D7 retention | >25% |
| Average session length | >5 min |
| ManaWell harvest rate | >70% (не пересыхает) |
| Series mint participation | >30% active users |
| Average cards per user | >5 |
| Push notification opt-in | >50% |
