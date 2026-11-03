# 🏛️ CATHEDRAL — Autonomous Code Machine

> **Technical Documentation of Living Code Protocol and Cathedral — Autonomous Code Machine concept**  
> Version: 1.0 (Evolution v4)  
> Language: English

---

## Table of Contents

1. [Overview](#overview)
2. [Living Code Protocol Architecture](#architecture)
3. [Agent Roles](#roles)
4. [Evolution Plan v4 (5 Phases)](#evolution-plan)
5. [A-Evolve: 3-Layer Evolution](#a-evolve)
6. [Self-HPO Harness Cycle](#self-hpo)
7. [Code → Release Pipeline](#release-pipeline)
8. [UI/Media Contracts](#contracts)
9. [Cloning to a New Host](#cloning)
10. [Environment Setup](#environment)
11. [News Search (X.com, Reddit, GitHub)](#news-search)
12. [Telegram Reports in Topic 252](#telegram)

---

## 1. Overview

CATHEDRAL — Autonomous Code Machine is an autonomous full-cycle development system based on the Living Code Protocol (ЖК) with GodModeCoder integration (Cathedral architecture).

The system enables 4 agent roles to autonomously evolve 4 projects through 5 evolution phases, with automatic Self-HPO cycle, release shipping, and report delivery to Telegram topic 252.

**Four projects:**
- `superguard` — FastAPI + YOLO + Tuya + React video surveillance system
- `elemental-life` — elemental life simulation (v1/v2)
- `cybertarot` / `cybertarot-full` — cyber tarot application
- `elemental-life-2` — second version of the simulation

---

## 2. Living Code Protocol Architecture

ЖК is organized as cathedral architecture: every tool is a stone in the foundation, not a crutch.

```
Living Code Protocol
├── LV-coder-*           — 4 project coders (hourly slot each)
├── LV-lord-of-code      — Lord (verdicts: HOT / COLD / RETURN)
├── LV-producer          — Producer (auto-release)
├── LV-harness-opt       — Harness optimizer (Self-HPO H-step)
├── LV-artist            — Artist (illustrations, assets)
├── LV-dj-musician       — Musician (tracks, voiceover, v2 contract)
└── LV-super-supervisor  — Super-Supervisor (post-verification, release tagging)
```

Each agent has its own prompt, model (from whitelist), cron schedule, and slot budget.

---

## 3. Agent Roles

| Role | Model | Responsibility |
|------|-------|----------------|
| LV-coder-superguard | nemotron-3.5-super-vl-120b-a12b | SuperGuard project code |
| LV-coder-elemental-life | nemotron-3.5-super-vl-120b-a12b | Elemental Life project code |
| LV-coder-cybertarot | nemotron-3.5-super-vl-120b-a12b | CyberTarot project code |
| LV-coder-elemental-life-2 | nemotron-3.5-super-vl-120b-a12b | Elemental Life 2 project code |
| LV-lord-of-code | nemotron-3.5-super-vl-120b-a12b | Verdicts: HOT/COLD/RETURN |
| LV-producer | nemotron-3.5-super-vl-120b-a12b | Auto-release on HOT + stabilen |
| LV-harness-opt | nemotron-3.5-super-vl-120b-a12b | H-step Self-HPO (daily) |
| LV-artist | nemotron-3.5-super-vl-120b-a12b | Project illustrations, assets |
| LV-dj-musician | nemotron-3.5-super-vl-120b-a12b | Tracks, voiceover (v2 contract) |
| LV-super-supervisor | nemotron-3.5-super-vl-120b-a12b | Post-verification + release tagging (hourly) |

---

## 4. Evolution Plan v4 (5 Phases)

| Phase | Name | Status | Description |
|-------|------|--------|-------------|
| 0 | Foundation and hardening | ✅ Completed | Super-Supervisor, cron check, git cleanliness, verdicts |
| 1 | Self-HPO harness cycle | ✅ Completed | H-step daily, P-step feedback, transition gate |
| 2 | A-Evolve (3 layers) | ✅ Completed | Task-harness, Evolver, Meta-evolver (branch meta-evolver-layer3) |
| 3 | Code → Release pipeline | ✅ Completed | release_project.py, checklist, tag vX.Y.Z, APK export |
| 4 | UI/Media contracts | ✅ Completed | media_contract.py, contracts v2-artist/musician/producer |
| 5 | Publication | 🔄 In progress | GitHub repository, localization RU/EN/ES, Grok prompts |

---

## 5. A-Evolve: 3-Layer Evolution

### Layer 1 — Task-harness
`jobs.json`, `config.yaml`, role prompts, templates in `agents/templates/` — under version control in `orchestration/`.

### Layer 2 — Evolver
`living_code_agent_wrapper.py` — engine with model fallback, retry, Telegram rate limiter.  
`check_roster.py` — CI gate for role registry.

### Layer 3 — Meta-evolver
`meta_evolver.py` — evolution of the evolution code itself. Analyzes `living_code_agent_wrapper.py`, `cycle_close.py`, `l3_critic.py`, `check_roster.py` for TEMP/FIXME markers, missing docstrings, Windows paths. Creates branch `meta-evolver-layer3` and commit for Lord review.

---

## 6. Self-HPO Harness Cycle

H-step (`LV-harness-opt`) runs once per day (03:00):
1. Reads `journal.md` — agent notes from last 24 hours
2. Analyses `attempt_*.json` — rc=75, stale/unresponsive, timeouts
3. Reads `errors.log` — scheduler errors
4. Analyses `l3_critic` — stabilen / regress / nuzhna_rabota
5. P-step feedback — checks if previous report was read
6. Makes changes to `jobs.json` and prompts
7. Transition gate: 0 stale/unresponsive, 4 cron green, ≥1 release artifact

P-step: coder/artist/musician work by current prompt, result fixed in report.

---

## 7. Code → Release Pipeline

`release_project.py` executes the full release cycle:

1. **Lord verdict** — checks `journal.md` for HOT verdict
2. **Checklist** — code cold (no [СР]), git clean, check_roster rc=0, ui_gate
3. **Version** — semantic vX.Y.Z (patch increment from last tag)
4. **Tagging** — annotated tag `{proj}-v{version}` + push to origin
5. **APK export** — copies `*.apk` to `~/apkexport/`
6. **Report** — `reports/release-{proj}-v{version}-{ts}.md`
7. **Delivery** — Telegram Bot API to topic 252

---

## 8. UI/Media Contracts

`media_contract.py` defines contracts for three roles:

| Role | Contract | Output files | Directory |
|------|----------|--------------|-----------|
| artist | v2-artist | png, jpg, svg, gif, mp4 | `<proj>/assets/` |
| dj-musician | v2-musician | mp3, wav, ogg, flac | `<proj>/audio/`, `music/` |
| producer | v2-producer | apk, media report | `<proj>/`, `reports/` |

MEDIA report aggregates all three roles and delivers to topic 252.

---

## 9. Cloning to a New Host

### Ubuntu (Linux)

```bash
# 1. Install dev tools
sudo apt update && sudo apt install -y git curl wget build-essential

# 2. Install ~/build toolchain
mkdir -p ~/build
cd ~/build
# Python 3.9-3.14, uv, Go, Rust, Node, JDK, Gradle, Flutter, Android SDK, .NET, Docker

# 3. Activate environment
source ~/build/env.sh

# 4. Clone repository
git clone https://github.com/PerfectFriend/NeXXus-Node.git ~/LivingCode
cd ~/LivingCode

# 5. Configure Hermes
mkdir -p ~/.hermes/cron ~/.hermes/profiles/default
cp orchestration/jobs/jobs.json ~/.hermes/cron/jobs.json
cp orchestration/hermes-config/config.yaml ~/.hermes/profiles/default/config.yaml

# 6. Install dependencies
pip install -r requirements.txt

# 7. Set environment variables
export CATHEDRAL_BOT_TOKEN="<your_token>"
export TELEGRAM_CRON_THREAD_ID=252

# 8. Verify installation
python3 orchestration/scripts/check_roster.py --update
bash orchestration/bin/verify.sh
```

### Windows

```powershell
# 1. Install Chocolatey or winget
# 2. Install Git, Python, Go, Rust, Node.js, JDK 21, Flutter, Docker Desktop

# 3. Create ~/build (or C:/build)
mkdir ~/build
# Extract toolchain to ~/build

# 4. Activate environment
source ~/build/env.sh

# 5. Clone repository
git clone https://github.com/PerfectFriend/NeXXus-Node.git ~/LivingCode
cd ~/LivingCode

# 6. Configure Hermes (same as Linux)
# Windows paths are replaced with Linux paths via WSL2 or Git Bash

# 7. Verify
python3 orchestration/scripts/check_roster.py --update
bash orchestration/bin/verify.sh
```

**Important:** All paths in code are Linux format (`/home/thomas/...`). On Windows use WSL2 or Git Bash with corresponding paths.

---

## 10. Environment Setup

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `CATHEDRAL_BOT_TOKEN` | Telegram bot token for reports | `8883516682:AAH0...` |
| `TELEGRAM_CRON_THREAD_ID` | Topic ID for reports | `252` |
| `LIVING_CODE_ROLE` | Current agent role | `Super-Supervisor` |
| `LIVING_CODE_CRON_BUDGET` | Slot budget in seconds | `3600` |

### Model Whitelist

Only the following models are allowed by the protocol:
- `nvidia/nemotron-3.5-super-vl-120b-a12b` (primary)
- `mistralai/mistral-large-4-1t-a52b` (fallback)

Forbidden: `nemotron-3-ultra-550b-a55b`, `minimax-m3.1-flash`, `gpt-6.1-sol/agentrouter` and others (HISTORICALLY_DEAD).

---

## 11. News Search (X.com, Reddit, GitHub)

### X.com (no login)
- Method: `web_search site:x.com <query>` → read via Jina Reader `https://r.jina.ai/https://x.com/...`
- Skill: `x-browse` (category web)
- Used by searcher for IT/AI news search

### Reddit (no login)
- Method: `web_search site:reddit.com <query>` → `web_extract` on specific posts
- Skill: `reddit-browse` (category web)
- Direct access and Jina Reader blocked (403)

### GitHub
- Method: `web_search site:x.com github` → read @github posts via Jina Reader
- Full GitHub API access — in development

---

## 12. Telegram Reports in Topic 252

All evolution phase reports are delivered via Telegram Bot API:

- Chat ID: `-1004431090317`
- Message Thread ID: `252`
- Method: `curl -X POST /sendDocument` with report file
- Required: `CATHEDRAL_BOT_TOKEN` in environment variables

---

## License

MIT License

---

## Acknowledgments

- **GodModeCoder** — Cathedral concept and sample prompts
- **Living Code Protocol** — base for autonomous project evolution
- **xAI Grok** — illustration generation for the repository

_May the Great Force of the Universe be with you!_