# 🏛️ CATHEDRAL — Autonomous Code Machine

> **Autonomous full-cycle development system** — from brief to release and automatic evolution.  
> Living Code Protocol + GodModeCoder integration. 4 projects, 5 evolution phases, Self-HPO cycle, auto-release.

[![Living Code Protocol](https://img.shields.io/badge/Protocol-Living%20Code-purple)](https://github.com/PerfectFriend/NeXXus-Node)
[![Evolution v4](https://img.shields.io/badge/Evolution-v4-blue)](docs/CATHEDRAL_AUTONOMOUS_CODE_MACHINE.en.md)
[![Technical Documentation](https://img.shields.io/badge/Documentation-CATHEDRAL-green)](docs/CATHEDRAL_AUTONOMOUS_CODE_MACHINE.en.md)
[![User Guide](https://img.shields.io/badge/User%20Guide-orange)](docs/USER_GUIDE.en.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## 📖 About

**CATHEDRAL — Autonomous Code Machine** is an autonomous development system based on the Living Code Protocol (ЖК) with GodModeCoder integration. The system enables 4 agent roles (coder, artist/musician, producer, release) to autonomously evolve 4 projects through 5 evolution phases, with automatic Self-HPO cycle and release shipping.

### 🎯 Key Features

| Component | Description |
|-----------|-------------|
| **Living Code Protocol** | 4 project coders + Lord + Producer + Artist + Musician |
| **Evolution v4** | 5 phases: 0-Foundation → 1-Self-HPO → 2-A-Evolve → 3-Release → 4-UI/Media → 5-Publication |
| **Self-HPO Cycle** | H-step (harness optimization) ↔ P-step (execution) with transition gate |
| **A-Evolve (3 layers)** | Task-harness → Evolver → Meta-evolver (evolution of evolution code) |
| **Auto-release** | Lord verdict → Checklist → Tag vX.Y.Z → APK → Report to topic 252 |
| **UI/Media** | v2-artist, v2-musician, v2-producer contracts with MEDIA reports |
| **News search** | X.com (no login), Reddit (via search), GitHub (via search) |

---

## 🚀 Quick Start

### Requirements

- Ubuntu 24.04 LTS or Windows 10/11
- Python 3.9+, Go, Rust, Node.js, JDK 21, Flutter SDK
- Docker (optional)
- Cathedral Telegram bot token (`CATHEDRAL_BOT_TOKEN`)

### Installation

```bash
# Clone the repository
git clone https://github.com/PerfectFriend/NeXXus-Node.git
cd NeXXus-Node

# Install dependencies
source ~/build/env.sh
pip install -r requirements.txt

# Verify configuration
python3 orchestration/scripts/check_roster.py --update

# Run verification
bash orchestration/bin/verify.sh
```

### First Evolution Phase

```bash
# Run Super-Supervisor (post-verification + auto-release)
bash orchestration/scripts/wrappers/wrapper_super_supervisor.sh

# Run Self-HPO harness cycle
python3 orchestration/scripts/meta_evolver.py

# Run auto-release for a project
python3 orchestration/scripts/release_project.py superguard

# Generate MEDIA report
python3 orchestration/scripts/media_contract.py superguard
```

---

## 📊 System Architecture

```
CATHEDRAL — Autonomous Code Machine
├── 🏗️ Living Code Protocol (ЖК)
│   ├── LV-coder-superguard      — SuperGuard project coder
│   ├── LV-coder-elemental-life  — Elemental Life project coder
│   ├── LV-coder-cybertarot      — CyberTarot project coder
│   ├── LV-coder-elemental-life-2 — Elemental Life 2 project coder
│   ├── LV-lord-of-code          — Lord (verdicts HOT/COLD/RETURN)
│   ├── LV-producer              — Producer (auto-release)
│   ├── LV-artist                — Artist (illustrations, assets)
│   └── LV-dj-musician           — Musician (tracks, voiceover)
├── 🔄 Evolution v4 (5 phases)
│   ├── Phase 0 — Foundation and hardening
│   ├── Phase 1 — Self-HPO harness cycle (H-step ↔ P-step)
│   ├── Phase 2 — A-Evolve (3-layer protocol evolution)
│   ├── Phase 3 — Code → Release pipeline
│   ├── Phase 4 — UI/Media contracts
│   └── Phase 5 — Publication (repository, localization)
├── 📡 News search
│   ├── X.com (no login via Jina Reader)
│   ├── Reddit (via web search + extraction)
│   └── GitHub (via web search)
└── 📦 Export
    └── ~/apkexport/ — Release APK files
```

---

## 📚 Documentation

| Document | Russian | English | Spanish |
|----------|---------|---------|---------|
| CATHEDRAL Technical Docs | [ru](docs/CATHEDRAL_AUTONOMOUS_CODE_MACHINE.ru.md) | [en](docs/CATHEDRAL_AUTONOMOUS_CODE_MACHINE.en.md) | [es](docs/CATHEDRAL_AUTONOMOUS_CODE_MACHINE.es.md) |
| User Guide | [ru](docs/USER_GUIDE.ru.md) | [en](docs/USER_GUIDE.en.md) | [es](docs/USER_GUIDE.es.md) |
| Evolution Phase Reports | [reports/](reports/) | | |
| Grok Prompts (illustrations) | [prompts/grok/](prompts/grok/) | | |

---

## 🎨 Grok Prompts (illustrations)

Prompts for generating project illustrations via Grok (xAI), adapted from GodModeCoder repository samples for the Living Code Protocol.

- [Main banner (16:9)](prompts/grok/illustration-prompts.en.md) — cyberpunk, Van Gogh, Gaudi, neon typography
- [Footer banner (16:9)](prompts/grok/illustration-prompts.en.md) — digital void, bioluminescence, quantum portals
- [Evolution phase illustrations](prompts/grok/illustration-prompts.en.md) — each phase with its own style

---

## 🤝 Contributing

The project is under active development. Each evolution phase is documented in a repository report and delivered to Telegram topic 252.

1. Fork the repository
2. Create a branch for your phase
3. Make changes with detailed comments
4. Submit a Pull Request describing changes

---

## 📄 License

MIT License — see [LICENSE](LICENSE)

---

## 🙏 Acknowledgments

- **GodModeCoder** — sample illustration prompts and Cathedral concept
- **Living Code Protocol** — base for autonomous project evolution
- **xAI Grok** — illustration generation for the repository

---

<div align="center">

**Made with ❤️ and the power of the Universe**  
_May the Great Force of the Universe be with you!_

</div>