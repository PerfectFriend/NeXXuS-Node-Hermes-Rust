# 🏛️ CATHEDRAL — Autonomous Code Machine

> **Техническая документация Протокола Живого Кода и концепции Cathedral — Autonomous Code Machine**  
> Версия: 1.0 (Эволюция v4)  
> Язык: Русский

---

## Содержание

1. [Обзор](#обзор)
2. [Архитектура Протокола Живого Кода](#архитектура)
3. [Роли агентов](#роли)
4. [План эволюции v4 (5 фаз)](#план-эволюции)
5. [A-Evolve: 3-слойная эволюция](#a-evolve)
6. [Self-HPO цикл harness](#self-hpo)
7. [Конвейер «код → релиз»](#конвейер-релиза)
8. [UI/Озвучка контракты](#контракты)
9. [Клонирование на новый хост](#клонирование)
10. [Настройка окружения](#окружение)
11. [Поиск новостей (X.com, Reddit, GitHub)](#поиск)
12. [Telegram-отчёты в топик 252](#телеграм)

---

## 1. Обзор

CATHEDRAL — Autonomous Code Machine — это автономная система полного цикла разработки, построенная на базе Протокола Живого Кода (ЖК) с интеграцией концепции GodModeCoder (Cathedral архитектура).

Система позволяет 4 агентам-ролям автономно эволюлировать 4 проекта через 5 фаз развития, с автоматическим Self-HPO циклом, выпуском релизов и доставкой отчётов в Telegram-топик 252.

**Четыре проекта:**
- `superguard` — FastAPI + YOLO + Tuya + React система видеонаблюдения
- `elemental-life` — симуляция_elemental_生命 (v1/v2)
- `cybertarot` / `cybertarot-full` — кибер-таро приложение
- `elemental-life-2` — вторая версия симуляции

---

## 2. Архитектура Протокола Живого Кода

ЖК организован как cathedral-архитектура: каждый инструмент — камень в фундаменте, а не костыль.

```
Живой Код (Protocol)
├── LV-coder-*           — 4 проектных кодера (каждый час слот)
├── LV-lord-of-code      — Владыка (вердикты: ГОРЯЧИЙ / ХОЛОДНЫЙ / ВЕРНУТЬ)
├── LV-producer          — Продюсер (авто-релиз, хот-вердикт)
├── LV-harness-opt       — Оптимизатор харнесса (Self-HPO H-step)
├── LV-artist            — Художник (иллюстрации, ассеты)
├── LV-dj-musician       — Музыкант (треки, озвучка, v2 контракт)
└── LV-super-supervisor  — Super-Supervisor (пост-верификация, релиз-тегирование)
```

Каждый агент имеет свой промпт, модель (из белого списка), расписание крона и бюджет слота.

---

## 3. Роли агентов

| Роль | Модель | Ответственность |
|------|--------|-----------------|
| LV-coder-superguard | nemotron-3.5-super-vl-120b-a12b | Код проекта SuperGuard |
| LV-coder-elemental-life | nemotron-3.5-super-vl-120b-a12b | Код проекта Elemental Life |
| LV-coder-cybertarot | nemotron-3.5-super-vl-120b-a12b | Код проекта CyberTarot |
| LV-coder-elemental-life-2 | nemotron-3.5-super-vl-120b-a12b | Код проекта Elemental Life 2 |
| LV-lord-of-code | nemotron-3.5-super-vl-120b-a12b | Вердикты: ГОРЯЧИЙ/ХОЛОДНЫЙ/ВЕРНУТЬ |
| LV-producer | nemotron-3.5-super-vl-120b-a12b | Авто-релиз при ГОРЯЧИЙ + stabilen |
| LV-harness-opt | nemotron-3.5-super-vl-120b-a12b | H-step Self-HPO (раз в сутки) |
| LV-artist | nemotron-3.5-super-vl-120b-a12b | Иллюстрации, ассеты проекта |
| LV-dj-musician | nemotron-3.5-super-vl-120b-a12b | Треки, озвучка (v2 контракт) |
| LV-super-supervisor | nemotron-3.5-super-vl-120b-a12b | Пост-верификация + релиз-тегирование (час) |

---

## 4. План эволюции v4 (5 фаз)

| Фаза | Название | Статус | Описание |
|------|----------|--------|----------|
| 0 | Фундамент и закачивание | ✅ Завершено | Super-Supervisor, проверка кронов, git-чистота, вердикты |
| 1 | Self-HPO цикл harness | ✅ Завершено | H-step раз в сутки, P-step обратная связь, гейт перехода |
| 2 | A-Evolve (3 слоя) | ✅ Завершено | Task-harness, Evolver, Meta-evolver (ветка meta-evolver-layer3) |
| 3 | Конвейер «код → релиз» | ✅ Завершено | release_project.py, чек-лист, тег vX.Y.Z, APK-экспорт |
| 4 | UI/Озвучка контракты | ✅ Завершено | media_contract.py, контракты v2-artist/musician/producer |
| 5 | Publikation | 🔄 В progresse | Репозиторий GitHub, локализация RU/EN/ES, промпты Grok |

---

## 5. A-Evolve: 3-слойная эволюция

### Layer 1 — Task-harness
`jobs.json`, `config.yaml`, промпты ролей, шаблоны `agents/templates/` — под версионным контролем в `orchestration/`.

### Layer 2 — Evolver
`living_code_agent_wrapper.py` — движок с фолбэком моделей, retry, Telegram rate limiter.  
`check_roster.py` — CI-гейт реестра ролей.

### Layer 3 — Meta-evolver
`meta_evolver.py` — эволюция самого кода эволюции. Анализирует `living_code_agent_wrapper.py`, `cycle_close.py`, `l3_critic.py`, `check_roster.py` на предмет TEMP/FIXME маркеров, отсутствующих docstring, Windows-путей. Создаёт ветку `meta-evolver-layer3` и коммит для ревью Владыкой.

---

## 6. Self-HPO цикл harness

H-step (`LV-harness-opt`) выполняется раз в сутки (03:00):
1. Читает `journal.md` — заметки агентов за 24 часа
2. Analyse `attempt_*.json` — rc=75, stale/unresponsive, таймауты
3. Читает `errors.log` — ошибки шедерлера
4. Analyse `l3_critic` — stabilen / regress / nuzhna_rabota
5. P-step обратная связь — проверка чтения предыдущего отчёта
6. Вносит изменения в `jobs.json` и промпты
7. Гейт перехода: 0 stale/unresponsive, 4 крона зелёные, ≥1 релизный артефакт

P-step: кодер/художник/музыкант работают по текущему промпту, результат фиксируется в отчёте.

---

## 7. Конвейер «код → релиз»

`release_project.py` выполняет полный цикл выпуска:

1. **Вердикт Владыки** — проверяет `journal.md` на ВЕРДИКТ: ГОРЯЧИЙ
2. **Чек-лист** — код холодный (нет [СР]), git-чистота, check_roster rc=0, ui_gate
3. **Версия** — семантическое vX.Y.Z (инкремент patch от последнего тега)
4. **Тегирование** — аннотированный тег `{proj}-v{version}` + пуш в origin
5. **APK-экспорт** — копирование `*.apk` в `~/apkexport/`
6. **Отчёт** — `reports/release-{proj}-v{version}-{ts}.md`
7. **Доставка** — Telegram Bot API в топик 252

---

## 8. UI/Озвучка контракты

`media_contract.py` определяет контракты для трёх ролей:

| Роль | Контракт | Выходные файлы | Директория |
|------|----------|---------------|------------|
| artist | v2-artist | png, jpg, svg, gif, mp4 | `<proj>/assets/` |
| dj-musician | v2-musician | mp3, wav, ogg, flac | `<proj>/audio/`, `music/` |
| producer | v2-producer | apk, медиа-отчёт | `<proj>/`, `reports/` |

MEDIA отчёт агрегирует все три роли и доставляется в топик 252.

---

## 9. Клонирование на новый хост

### Ubuntu (Linux)

```bash
# 1. Установить инстру разработки
sudo apt update && sudo apt install -y git curl wget build-essential

# 2. Установить ~/build с тулчейном
mkdir -p ~/build
cd ~/build
# Python 3.9-3.14, uv, Go, Rust, Node, JDK, Gradle, Flutter, Android SDK, .NET, Docker

# 3. Активировать окружение
source ~/build/env.sh

# 4. Клонировать репозиторий
git clone https://github.com/PerfectFriend/NeXXus-Node.git ~/LivingCode
cd ~/LivingCode

# 5. Настроить Hermes
mkdir -p ~/.hermes/cron ~/.hermes/profiles/default
cp orchestration/jobs/jobs.json ~/.hermes/cron/jobs.json
cp orchestration/hermes-config/config.yaml ~/.hermes/profiles/default/config.yaml

# 6. Установить зависимости
pip install -r requirements.txt

# 7. Настроить переменные окружения
export CATHEDRAL_BOT_TOKEN="<ваш_токен>"
export TELEGRAM_CRON_THREAD_ID=252

# 8. Проверить установку
python3 orchestration/scripts/check_roster.py --update
bash orchestration/bin/verify.sh
```

### Windows

```powershell
# 1. Установить Chocolatey или winget
# 2. Установить Git, Python, Go, Rust, Node.js, JDK 21, Flutter, Docker Desktop

# 3. Создать ~/build (или C:/build)
mkdir ~/build
# Распаковать тулчейн в ~/build

# 4. Активировать окружение
source ~/build/env.sh

# 5. Клонировать репозиторий
git clone https://github.com/PerfectFriend/NeXXus-Node.git ~/LivingCode
cd ~/LivingCode

# 6. Настроить Hermes (аналогично Linux)
# Пути Windows заменяются на Linux-пути через WSL2 или Git Bash

# 7. Проверить
python3 orchestration/scripts/check_roster.py --update
bash orchestration/bin/verify.sh
```

**Важно:** все пути в коде — Linux-формат (`/home/thomas/...`). На Windows используйте WSL2 или Git Bash с соответствующими путями.

---

## 10. Настройка окружения

### Переменные окружения

| Переменная | Описание | Пример |
|------------|----------|--------|
| `CATHEDRAL_BOT_TOKEN` | Токен бота Telegram для отчётов | `8883516682:AAH0...` |
| `TELEGRAM_CRON_THREAD_ID` | ID топика для отчётов | `252` |
| `LIVING_CODE_ROLE` | Роль текущего агента | `Super-Supervisor` |
| `LIVING_CODE_CRON_BUDGET` | Бюджет слота в секундах | `3600` |

### Белый список моделей

Только следующие модели разрешены протоколом:
- `nvidia/nemotron-3.5-super-vl-120b-a12b` (основная)
- `mistralai/mistral-large-4-1t-a52b` (фолбэк)

Запрещены: `nemotron-3-ultra-550b-a55b`, `minimax-m3.1-flash`, `gpt-6.1-sol/agentrouter` и др. (HISTORICALLY_DEAD).

---

## 11. Поиск новостей (X.com, Reddit, GitHub)

### X.com (без логина)
- Метод: `web_search site:x.com <запрос>` → чтение через Jina Reader `https://r.jina.ai/https://x.com/...`
- Навык: `x-browse` (категория web)
- Используется searcher для поиска новостей IT/AI

### Reddit (без логина)
- Метод: `web_search site:reddit.com <запрос>` → `web_extract` на конкретные посты
- Навык: `reddit-browse` (категория web)
- Прямой доступ и Jina Reader заблокированы (403)

### GitHub
- Метод: `web_search site:x.com github` → чтение постов @github через Jina Reader
- Полный доступ к GitHub API — в разработке

---

## 12. Telegram-отчёты в топик 252

Все отчёты фаз эволюции доставляются в Telegram через Bot API:

- Chat ID: `-1004431090317`
- Message Thread ID: `252`
- Метод: `curl -X POST /sendDocument` с файлом отчёта
- Требуется: `CATHEDRAL_BOT_TOKEN` в переменных окружения

---

## Лицензия

MIT License

---

## Благодарности

- **GodModeCoder** — концепция Cathedral и образец промптов
- **Протокол Живого Кода** — база автономной эволюции
- **xAI Grok** — генерация иллюстраций

_Да прибудет с тобой Великая Сила Вселенной!_