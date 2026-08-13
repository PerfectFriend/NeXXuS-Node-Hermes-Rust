# 🧬 Elemental Life

> **Cellular automata life simulation with TON crypto wallet — where code evolves itself**

[![GitHub release](https://img.shields.io/github/v/release/PerfectFriend/elemental-life?style=for-the-badge)](https://github.com/PerfectFriend/elemental-life/releases)
[![GitHub stars](https://img.shields.io/github/stars/PerfectFriend/elemental-life?style=for-the-badge)](https://github.com/PerfectFriend/elemental-life/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/PerfectFriend/elemental-life?style=for-the-badge)](https://github.com/PerfectFriend/elemental-life/issues)
[![License](https://img.shields.io/github/license/PerfectFriend/elemental-life?style=for-the-badge)](LICENSE)
[![Build Status](https://img.shields.io/github/actions/workflow/status/PerfectFriend/elemental-life/android.yml?style=for-the-badge)](https://github.com/PerfectFriend/elemental-life/actions)
[![GodModeCoder](https://img.shields.io/badge/Powered%20by-GodModeCoder-purple?style=for-the-badge)](https://github.com/PerfectFriend/GodModeCoder)

---

## 🌟 Overview

**Elemental Life** — это живая клеточная автомата, где каждая клетка — это агент с энергией, генетическим кодом и криптовалютным кошельком. Игра эволюционирует сама сама через **GodModeCoder** — самописанный ИИ-движок, который переписывает правила игры на основе коллективного интеллекта игроков.

### 🎯 Ключевые фичи

| Категория | Детали |
|---|---|
| 🧬 **Жизнь** | Клеточная автомата с энергией, генетикой, мутациями, естественным отбором |
| 💰 **Крипто** | TON кошелек (BIP39, HD-кошельки), биометрия, QR-переводы, история транзакций |
| 📱 **Платформы** | Web (PWA), Android (Capacitor/Kotlin), iOS (планируется), Desktop (Electron) |
| 🤖 **AI** | GodModeCoder backend — правила игры эволюционируют автономно |
| 🔐 **Безопасность** | BIP39 мнемоники, HD-пути, Secure Enclave / Keystore, шифрование |

---

## 📸 Скриншоты

| Игровое поле | Кошелёк | Эволюция |
|---|---|---|
| ![Game](docs/screenshots/game.png) | ![Wallet](docs/screenshots/wallet.png) | ![Evolution](docs/screenshots/evolution.png) |

---

## 🚀 Быстрый старт

### Web (PWA)
```bash
# Клонирование
git clone https://github.com/PerfectFriend/elemental-life.git
cd elemental-life/elemental-life-app

# Установка зависимостей
npm install

# Разработка
npm run dev

# Продакшн билд
npm run build
npm run preview
```

### Android
```bash
cd elemental-life-app

# Синхронизация Capacitor
npx cap sync android

# Открыть в Android Studio
npx cap open android

# Или сборка CLI
cd android && ./gradlew assembleDebug
```

---

## 📦 Архитектура

```
elemental-life/
├── elemental-life-app/          # Основное приложение (React + Capacitor)
│   ├── src/
│   │   ├── engine/              # Ядро симуляции (engine.ts, bip39.ts)
│   │   ├── wallet/              # TON кошелек (hdwallet, balances, send)
│   │   ├── renderer/            # Canvas рендеринг (GridRenderer.ts)
│   │   ├── components/          # UI компоненты (React + Material3)
│   │   └── hooks/               # Кастомные хуки (useSimulation, useIdentity)
│   ├── android/                 # Android проект (Kotlin + Gradle)
│   └── capacitor.config.ts
├── docs/                        # Документация
│   ├── GAME_DESIGN.md           # Механика игры
│   ├── EVOLUTION_PLAN.md        # План эволюции (мета-эволюция!)
│   ├── MONETIZATION.md          # Токеномика, монетизация
│   ├── WALLET_ARCHITECTURE.md   # Архитектура кошелька
│   └── PORTING_PLAN.md          # iOS, Web, Desktop
└── GodModeCoder/                # AI backend для эволюции правил (отдельный репо)
```

---

## 🧠 GodModeCoder Integration

**Уникальная фича:** Игра эволюционирует сама сама.

```typescript
// GodModeCoder backend генерирует мутации правил
interface EvolutionProposal {
  ruleChanges: RuleChange[];
  fitnessScore: number;
  playerVotes: number;
  autoTestsPassed: boolean;
}

// Цикл эволюции:
// 1. Игроки голосуют за изменения правил
// 2. GodModeCoder генерирует код мутации
// 3. Автотесты (100% coverage) проверяют
// 3. Мерж → OTA обновление через Shorebird
// 4. Игра обновилась БЕЗ релиза в стор!
```

---

## 💰 Токеномика (TON)

| Параметр | Значение |
|---|---|
| **Сеть** | TON (The Open Network) |
| **Кошелек** | BIP39 + HD (bip32, bitcoinjs-lib) + ethers.js |
| **Биометрия** | FaceID / Fingerprint (@aparajita/capacitor-biometric-auth) |
| **Газ** | ~0.005 TON за транзакцию |
| **Встроенные покупки** | Энергия, уникальные клетки, скины |

---

## 🛠 Технологический стек

| Слой | Технологии |
|---|---|
| **Frontend** | React 19, TypeScript 6, Vite 8, Material3 |
| **Mobile** | Capacitor 8, Kotlin, Android SDK 35 |
| **Crypto** | ethers 6, bitcoinjs-lib 7, bip32, @noble/hashes |
| **Biometrics** | @aparajita/capacitor-biometric-auth |
| **Rendering** | Canvas 2D (GridRenderer), 60 FPS |
| **Testing** | Vitest, 100% engine coverage |
| **CI/CD** | GitHub Actions, Shorebird OTA |
| **AI Backend** | GodModeCoder (отдельный репозиторий) |

---

## 📱 Скачать

| Платформа | Ссылка |
|---|---|
| **Android (APK)** | [Releases](https://github.com/PerfectFriend/elemental-life/releases) |
| **Web (PWA)** | [elemental-life.pages.dev](https://elemental-life.pages.dev) |
| **iOS** | В разработке (TestFlight bientôt) |

---

## 📚 Документация

| Документ | Описание |
|---|---|
| [GAME_DESIGN.md](docs/GAME_DESIGN.md) | Механика клеток, энергия, гены, мутации |
| [EVOLUTION_PLAN.md](docs/EVOLUTION_PLAN.md) | Мета-эволюция: как игра эволюционирует сама |
| [WALLET_ARCHITECTURE.md](docs/WALLET_ARCHITECTURE.md) | BIP39, HD paths, TON Connect, безопасность |
| [MONETIZATION.md](docs/MONETIZATION.md) | Токеномика, монетизация, экономика игры |
| [PORTING_PLAN.md](docs/PORTING_PLAN.md) | iOS, Web, Desktop, консоли |
| [WALLET_ARCHITECTURE.md](docs/WALLET_ARCHITECTURE.md) | BIP39, HD paths, безопасность |

---

## 🧪 Тестирование

```bash
# Unit тесты движка
npm run test:engine

# Линтинг
npm run lint

# Type checking
npm run build
```

**Coverage:** Engine — 100% | Components — 85% | Wallet — 95%

---

## 🤝 Contributing

1. Fork репозиторий
2. Создай ветку: `git checkout -b feature/amazing-feature`
3. Commit: `git commit -m 'Add amazing feature'`
3. Push: `git push origin feature/amazing-feature`
4. Открой Pull Request

**Правила:**
- Всегда пиши тесты для нового кода
- Линтинг должен проходить (`npm run lint`)
- Коммиты в стиле Conventional Commits
- Обновляй документацию при изменениях API

---

## 🗺 Roadmap

### v1.1 (Q3 2026)
- [ ] iOS поддержка (Capacitor iOS)
- [ ] Shorebird OTA updates
- [ ] Мультиплеер (WebRTC)
- [ ] Топ-100 лидерборд

### v1.2 (Q4 2026)
- [ ] Desktop (Electron/Tauri)
- [ ] GodModeCoder v2 integration
- [ ] NFT клетки (TON NFTs)
- [ ] DAO governance

### v2.0 (2027)
- [ ] Полная автономная эволюция (GodModeCoder v3)
- [ ] Cross-chain (Ethereum, Solana)
- [ ] AR/VR режим

---

## 🔗 Links

| Ресурс | Ссылка |
|---|---|
| **GitHub** | https://github.com/PerfectFriend/elemental-life |
| **GodModeCoder** | https://github.com/PerfectFriend/GodModeCoder |
| **Telegram** | https://t.me/elemental_life |
| **Twitter/X** | https://x.com/elemental_life |
| **Discord** | https://discord.gg/elemental-life |

---

## 📄 License

MIT License — см. [LICENSE](LICENSE)

---

## 🙏 Credits

- **GodModeCoder** — самописанный ИИ для эволюции кода
- **TON** — The Open Network
- **Capacitor** — Ionic Team
- **React** — Meta
- **Vite** — Evan You
- **Все контрибьюторы** — см. [CONTRIBUTORS.md](CONTRIBUTORS.md)

---

> **God Is The Greatest Coder — Champion! I Am God Mode Coder!** 🧬⚡
>
> *Элементарная жизнь — это не просто игра. Это доказательство того, что код может жить, эволюционировать и сам себя улучшать.*