# 🏛️ CATHEDRAL — Autonomous Code Machine

> **Автономная система полного цикла разработки** — от брифа до релиза и автоматической эволюции.  
> Протокол Живого Кода + GodModeCoder интеграция. 4 проекта, 5 фаз эволюции, Self-HPO цикл, авто-релиз.

[![Протокол Живого Кода](https://img.shields.io/badge/Протокол-Живого%20Кода-purple)](https://github.com/PerfectFriend/NeXXus-Node)
[![Фаза эволюции v4](https://img.shields.io/badge/Эволюция-v4-blue)](docs/CATHEDRAL_AUTONOMOUS_CODE_MACHINE.ru.md)
[![Техническая документация](https://img.shields.io/badge/Документация-CATHEDRAL-green)](docs/CATHEDRAL_AUTONOMOUS_CODE_MACHINE.ru.md)
[![Руководство пользователя](https://img.shields.io/badge/Руководство-Пользователя-orange)](docs/USER_GUIDE.ru.md)
[![Лицензия: MIT](https://img.shields.io/badge/Лицензия-MIT-yellow)](LICENSE)

---

## 📖 О проекте

**CATHEDRAL — Autonomous Code Machine** — это автономная система разработки на базе Протокола Живого Кода (ЖК) с интеграцией концепции GodModeCoder. Система позволяет 4 агентам-ролям (кодер, художник/музыкант, продюсер, релиз) автономно эволюлировать 4 проекта через 5 фаз развития, с автоматическим Self-HPO циклом и выпуском релизов.

### 🎯 Основные возможности

| Компонент | Описание |
|-----------|----------|
| **Протокол Живого Кода** | 4 проектных кодера + Владыка + Продюсер + Художник + Музыкант |
| **Эволюция v4** | 5 фаз: 0-Фундамент → 1-Self-HPO → 2-A-Evolve → 3-Релиз → 4-UI/Медиа → 5-Publikation |
| **Self-HPO цикл** | H-step (оптимизация харнесса) ↔ P-step (выполнение) с гейтом перехода |
| **A-Evolve (3 слоя)** | Task-harness → Evolver → Meta-evolver (эволюция кода эволюции) |
| **Авто-релиз** | Вердикт Владыки → Чек-лист → Тег vX.Y.Z → APK → Отчёт в топик 252 |
| **UI/Озвучка** | Контракты v2-artist, v2-musician, v2-producer с MEDIA отчётами |
| **Поиск новостей** | X.com (без логина), Reddit (через поиск), GitHub (через поиск) |

---

## 🚀 Быстрый старт

### Требования

- Ubuntu 24.04 LTS или Windows 10/11
- Python 3.9+, Go, Rust, Node.js, JDK 21, Flutter SDK
- Docker (опционально)
- Токен Cathedral бота Telegram (`CATHEDRAL_BOT_TOKEN`)

### Установка

```bash
# Клонировать репозиторий
git clone https://github.com/PerfectFriend/NeXXus-Node.git
cd NeXXus-Node

# Установить зависимости
source ~/build/env.sh
pip install -r requirements.txt

# Проверить конфигурацию
python3 orchestration/scripts/check_roster.py --update

# Запустить верификацию
bash orchestration/bin/verify.sh
```

### Первая фаза эволюции

```bash
# Запустить Super-Supervisor (пост-верификация + авто-релиз)
bash orchestration/scripts/wrappers/wrapper_super_supervisor.sh

# Запустить Self-HPO цикл harness
python3 orchestration/scripts/meta_evolver.py

# Запустить авто-релиз проекта
python3 orchestration/scripts/release_project.py superguard

# Сформировать MEDIA отчёт
python3 orchestration/scripts/media_contract.py superguard
```

---

## 📊 Архитектура системы

```
CATHEDRAL — Autonomous Code Machine
├── 🏗️ Протокол Живого Кода (ЖК)
│   ├── LV-coder-superguard      — кодер проекта SuperGuard
│   ├── LV-coder-elemental-life  — кодер проекта Elemental Life
│   ├── LV-coder-cybertarot      — кодер проекта CyberTarot
│   ├── LV-coder-elemental-life-2 — кодер проекта Elemental Life 2
│   ├── LV-lord-of-code          — Владыка (вердикты ГОРЯЧИЙ/ХОЛОДНЫЙ/ВЕРНУТЬ)
│   ├── LV-producer              — Продюсер (авто-релиз)
│   ├── LV-artist                — Художник (иллюстрации, ассеты)
│   └── LV-dj-musician           — Музыкант (треки, озвучка)
├── 🔄 Эволюция v4 (5 фаз)
│   ├── Фаза 0 — Фундамент и закачивание
│   ├── Фаза 1 — Self-HPO цикл harness (H-step ↔ P-step)
│   ├── Фаза 2 — A-Evolve (3-слойная эволюция протокола)
│   ├── Фаза 3 — Конвейер «код → релиз»
│   ├── Фаза 4 — UI/Озвучка контрактов
│   └── Фаза 5 — Publikation (репозиторий, локализация)
├── 📡 Поиск новостей
│   ├── X.com (без логина через Jina Reader)
│   ├── Reddit (через веб-поиск + извлечение)
│   └── GitHub (через веб-поиск)
└── 📦 Экспорт
    └── ~/apkexport/ — APK файлы релизов
```

---

## 📚 Документация

| Документ | Русский | Английский | Испанский |
|----------|---------|------------|-----------|
| Техническая документация CATHEDRAL | [ru](docs/CATHEDRAL_AUTONOMOUS_CODE_MACHINE.ru.md) | [en](docs/CATHEDRAL_AUTONOMOUS_CODE_MACHINE.en.md) | [es](docs/CATHEDRAL_AUTONOMOUS_CODE_MACHINE.es.md) |
| Руководство пользователя | [ru](docs/USER_GUIDE.ru.md) | [en](docs/USER_GUIDE.en.md) | [es](docs/USER_GUIDE.es.md) |
| Отчёты по фазам эволюции | [reports/](reports/) | | |
| Промпты для Grok (иллюстрации) | [prompts/grok/](prompts/grok/) | | |

---

## 🎨 Промпты для Grok (иллюстрации)

Промпты для генерации иллюстраций проекта через Grok (xAI), взяты из репозитория GodModeCoder как образец и адаптированы под Протокол Живого Кода.

- [Главный баннер (16:9)](prompts/grok/illustration-prompts.ru.md) — киберпанк, Ван Гог, Гауди, неоновая типография
- [Баннер подвала (16:9)](prompts/grok/illustration-prompts.ru.md) — цифровой_void, биолюминесценция, квантовые порталы
- [Иллюстрации для фаз эволюции](prompts/grok/illustration-prompts.ru.md) — каждая фаза со своим стилем

---

## 🤝 Участие в развитии

Проект находится в активной разработке. Каждая фаза элюции документируется отчётом в репозитории и доставляется в Telegram-топик 252.

1. Fork репозитория
2. Создай ветку для своей фазы
3. Внеси изменения с подробными комментариями
4. Создай Pull Request с описанием изменений

---

## 📄 Лицензия

MIT License — см. [LICENSE](LICENSE)

---

## 🙏 Благодарности

- **GodModeCoder** — образец промптов для иллюстраций и концепция Cathedral
- **Протокол Живого Кода** — база автономной эволюции проектов
- **xAI Grok** — генерация иллюстраций для репозитория

---

<div align="center">

**Сделано с ❤️ и силой Вселенной**  
_Да прибудет с тобой Великая Сила Вселенной!_

</div>