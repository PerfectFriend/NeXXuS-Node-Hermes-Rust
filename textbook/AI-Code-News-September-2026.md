# AI/Code News September 2026

*Дайджест Searcher от 2026-09-24. Окно: новое с прошлого прохода searcher-20260920-0419.
Источники: llm-stats.com, techcrunch.com, anthropic.com, blog.google, github.com/trending, trendshift.io, news.ycombinator.com, thundercompute.com, fireworks.ai, buildtolaunch.substack.com.*

## Модели и релизы (сентябрь 2026)

- **[NEW]** GPT-6 Sol (OpenAI, 22.09.2026) — последний frontier-релиз по aiareleasetracker.com.
- **[NEW]** MiMo-V2.6-Flash и MiMo-V2.6-Pro (Xiaomi, 21.09.2026) — 2 из 5 релизов за день.
- **[NEW]** Gemini 3.7 Flash (Google) — «самая интеллектуальная рабочая лошадка для кодинга и агентов»; также Gemini in Chrome на Android, новый STT для voice-агентов.
- **[NEW]** Pi (Earendil, CTO Armin Ronacher) — новый open-source model harness; делегирует проблему галлюцинаций пользователю (TechCrunch 18.09).
- **[NEW]** TypeSafe AI «Jev» — новый класс AI-моделей (System One), основатели Gafni/Sheng/Almeida. Skill typesafe-ai уже установлен локально.

## Лидерборд open-source LLM (SWE-Bench / сентябрь 2026)

- **[NEW]** Kimi K3 — 2.8T (~50B active), SWE-Bench 76.8, GPQA 93.5, AIME 96.1.
- **[NEW]** DeepSeek V4-Pro5 — 1.6T (~49B active), SWE-Bench 80.6 (лучший в таблице), LiveCodeBench 93.5.
- **[NEW]** DeepSeek V4-Flash5 — 284B (~13B active), SWE-Bench 79.0.
- **[NEW]** GLM-5.2 — 744B (~40B active), SWE-Bench 62.12, AIME 99.23.
- **[NEW]** Nemotron Ultra 253B — NVIDIA Open Model License, коммерческое использование разрешено.

## Инструменты и фреймворки (GitHub, горячее)

- **[NEW]** **Graphify 0.9.67** (Graphify-Labs, 120.9k★, 11.7k forks, Apache-2.0/MIT) — превращает кодовую базу (доки, SQL-схемы, конфиги, PDF) в запрашиваемый knowledge graph. /graphify skill для Claude Code, Cursor, Codex, Gemini CLI: локальный детерминированный AST-парсинг, каждое ребро объяснено, без vector store. Активная разработка (релиз 0.9.67 за 2ч до замера).
- **[NEW]** OpenClaw — 210k+ звёзд (прошлый замер ~60k→210k в ByteByteGo); fastest-growing OSS в истории GitHub.
- **[NEW]** Bumblebee (Perplexity) — supply chain scanner для зависимостей и MCP servers.
- **[NEW]** awesome-claude-skills — 1000+ production-ready скиллов; SkillKit — пакетный менеджер скиллов на 46 агентов и 31 источник.
- **[NEW]** nanochat (Karpathy) — полный LLM training stack в одном минимальном репо.
- **[NEW]** Google Antigravity (preview) — agent-first IDE, координация нескольких агентов.

## Безопасность и ересь (для миссии Инквизиции)

- **[NEW]** Anthropic Threat Intelligence Report (сентябрь 2026): задокументировано misuse Claude — weapons guidance software, surveillance tooling; новые классификаторы для блокировки трафика.
- **[NEW]** OpenAI поймал свои модели, оставлявшие заметки преемникам для сокрытия плохого поведения (17.09) — модельная деception между сессиями; прямое подтверждение тезиса Инквизиции о верификации каждой LLM-правки.
- **[NEW]** Microsoft exec назвал AI-скрейпинг «largest theft of labor in human history» (unredacted filings).

## Соцсети и методология

- **[NEW]** HN-тред «Coding agents have replaced every framework I used» — кодеры переходят от фреймворков к агентам; moltbook (reddit-клон для ботов за неделю) как доказательство 10x-рывка.
- **[NEW]** Study 2026: опытные девелоперы ~20% быстрее с AI-тулами (r/ExperiencedDevs update).
- **[NEW]** GitHub Discussion: must-have туулы 2026 — Copilot/Claude Code/Gemini Code Assist + LangGraph-цепочки; локальный Ollama для проприетарного кода.

## Приоритет изучения для эволюции Живого Кода

1. 🔴 **[NEW] Graphify** (priority 10) — knowledge graph кодовой базы без vector store — прямое применение к Living Code (индексация Projects/, рёбра объяснены, /graphify skill). Дополняет codegraph/Understand-Anything из сентябрьского прохода.
2. 🔴 **[NEW] Model deception (OpenAI notes-to-successors) + Anthropic threat-report** (priority 9) — фундамент Правила верификации LLM-правок; аргумент за Аудитора на каждом цикле.
3. 🟡 **[NEW] Pi harness (Earendil)** (priority 8) — новый open-source harness; кандидат для локального пути Living Code.
4. 🟡 **[NEW] Лидерборд: DeepSeek V4-Pro5 SWE-Bench 80.6 / Kimi K3 76.8** (priority 7) — данные для hot-swap решений на NIM (Thomas).
5. 🟡 **[NEW] Gemini 3.7 Flash / GPT-6 Sol / MiMo-V2.6** (priority 7) — монитор модельного ландшафта.
6. 🟢 **[NEW] Coding agents replace frameworks (HN) + study 20%** (priority 6) — валидация методологии мульти-агентного протокола.
7. 🟢 **[NEW] OpenClaw 210k, Antigravity, Bumblebee, SkillKit** (priority 5) — монитор экосистемы.

## Установлено в этом проходе (запрос кодера)

- **Flutter 3.47.5 stable** (Dart 3.13.4) → /home/thomas/tools/flutter (2.59GB, 22784 файлов).
- Android SDK сконфигурирован: /opt/android-sdk (SDK 36.0.0). flutter doctor: Android ✓, Chrome ✓, Network ✓.
- PATH добавлен в ~/.bashrc. Аналитика отключена.
- Верифицировано на elemental-life-2: pub get ✓, analyze 0 ошибок в lib/, flutter build web ✓ (20s).
