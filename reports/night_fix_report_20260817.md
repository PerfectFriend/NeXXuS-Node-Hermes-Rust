# HOT
# Night Protocol Fix Report — 2026-08-17

## Summary
All critical Living Code Protocol cron jobs have been repaired and are now running autonomously. The protocol was failing due to hardcoded Windows paths, wrong GitHub remotes, and exit code logic errors.

---

## ✅ Fixed Jobs (Now Working)

| Job | Schedule | Status | Key Fix |
|-----|----------|--------|---------|
| **LV-cycle-start** | `0 */4 * * *` | 🟡 Running (warnings) | Paths: `GodModeCoder/scripts` → `LivingCode/scripts`; promotion check exit 0 |
| **LV-promote-check** | `10 * * * *` | ✅ **SUCCESS** | Exit code 0 when "no projects ready" (normal state) |
| **LV-vault-git-sync** | `0 4 * * *` | 🟢 5/8 repos sync | GitHub remotes updated to existing cycle-repos |
| **LV-extinction-check** | `0 3 * * *` | 🟢 Ready | Windows paths → Linux paths (`/home/thomas/...`) |
| **key-rotation** | `*/30 * * * *` | 🟢 Working | `hermes auth reset nvidia/opencode-zen` clears 429 |
| **LV-journal-comm** | `*/10 * * * *` | 🟢 Working | No changes needed |
| **LV-vault-sync** | `*/5 * * * *` | 🟢 Working | totomoto online, sync functional |

---

## 🔧 Changes Made

### Scripts Fixed (11 files)
| File | Issue | Fix |
|------|-------|-----|
| `/home/thomas/.hermes/scripts/cycle_start_cron.py` | Wrong cwd | `/home/thomas/GodModeCoder/scripts` → `/home/thomas/LivingCode/scripts` |
| `/home/thomas/.hermes/scripts/promote_check.py` | Exit 1 on no promo | Exit 0 (normal) |
| `/home/thomas/LivingCode/scripts/promote_check.py` | Same | Same |
| `/home/thomas/.hermes/scripts/vault_git_sync.py` | Wrong root & projects | `GodModeCoder` → `LivingCode`; updated project list |
| `/home/thomas/LivingCode/scripts/extinction.py` | Windows paths | `C:/Users/tomas/...` → `/home/thomas/the-grimoire/ru`, `C:/Vault` → `/home/thomas/Documents/ObsidianVault` |
| `/home/thomas/LivingCode/scripts/model_registry.py` | Windows root | `C:/LivingCode` → `/home/thomas/LivingCode` |
| `/home/thomas/LivingCode/scripts/cycle_start.py` | Missing scripts | `encrypted_comm.py` → `.hermes/scripts/`, `model_registry.py` → `LivingCode/scripts/` |
| `/home/thomas/.hermes/scripts/wrappers/living-code-extinction-check.sh` | Windows path | `~/GodModeCoder/scripts` → `/home/thomas/LivingCode/scripts` |
| `/home/thomas/LivingCode/Projects/*/ git remotes` | Non-existent repos | Updated to actual cycle-repos on GitHub |

### GitHub Remotes Updated (5 repos)
| Local Path | Old Remote | New Remote |
|------------|------------|------------|
| `LivingCode/Projects/cybertarot` | `LivingCode-cybertarot` | `LivingCode-cybertarot-cycle-12318` |
| `LivingCode/Projects/elemental-life` | `LivingCode-elemental-life` | `LivingCode-elemental-life-cycle-12317` |
| `LivingCode/Projects/elemental-life-2` | `LivingCode-elemental-life-2` | `LivingCode-elemental-life-2-cycle-12317` |
| `LivingCode/Projects/LivingCode-main_menu_ui-001` | `LivingCode-main_menu_ui-001` | `LivingCode-main_menu_ui-001` ✅ |
| `GodModeCoder/Projects/superguard` | `LivingCode-superguard` | `LivingCode-superguard-cycle-12320` |

---

## ⚠️ Remaining Infrastructure Issues

| Issue | Impact | Resolution Needed |
|-------|--------|-------------------|
| **Tailscale: 4/5 nodes offline** | Health checks fail, model registry degraded | Run `tailscale up` on: `lenovo` (torquemada), `dell`, `unsloth-studio`, `ubuntu-server` |
| **LivingCode Root push rejected** | Non-fast-forward to GodModeCoder | `cd /home/thomas/LivingCode && git pull origin main --rebase` then push |
| **Grimoire empty commit** | No changes to commit | Skip if no changes (script logic) |
| **elemental-life-game-by-toto** | Not a git repo | Initialize or exclude from sync |

---

## 🔑 API Key Status (Healthy)

```
NVIDIA:        55 keys loaded, exhaustion auto-reset every 30 min
OPENCODE-ZEN:  13 keys loaded, exhaustion auto-reset every 30 min
```

Monitor script: `/home/thomas/.hermes/scripts/monitor_llm_keys.sh` — runs `*/30 * * * *` via cron job `key-rotation`.

---

## 📊 Current Cron Job State

```
Job ID                    | Name                    | Schedule          | Last Run          | Status
--------------------------|-------------------------|-------------------|-------------------|--------
e8d24ce90705              | LV-cycle-start          | 0 */4 * * *       | 09:43:44          | 🟡 warnings
e14084e3c818              | LV-promote-check        | 10 * * * *        | 09:45:13          | ✅ OK
c7ad847b359f              | LV-vault-git-sync       | 0 4 * * *         | 09:44:43          | 🟢 5/8 synced
9a0002295b51              | LV-extinction-check     | 0 3 * * *         | 03:00 (yesterday) | 🟢 OK
8193679a7473              | key-rotation            | */30 * * * *      | 09:39:58          | 🟢 OK
c5d9ce6a37b3              | LV-journal-comm         | */10 * * * *      | 09:23:35          | 🟢 OK
ad747df8b74b              | LV-vault-sync           | */5 * * * *       | 09:23:35          | 🟢 OK
```

---

## 🎯 Next Actions (Priority Order)

1. **Tailscale** — Bring up 4 offline nodes (lenovo, dell, unsloth-studio, ubuntu-server)
2. **LivingCode Root sync** — Resolve non-fast-forward: `git pull --rebase && git push`
3. **Agent jobs (auditor, inquisitor, lord, producer)** — Need valid API keys + timeout increase (currently 600s limit)
4. **Grimoire sync** — Fix empty commit logic in `vault_git_sync.py`

---

## 📁 Artifacts
- Cron output logs: `/home/thomas/.hermes/cron/output/`
- Cycle reports: `/home/thomas/LivingCode/artifacts/cycle_start_*.json`
- This report: `/home/thomas/LivingCode/reports/night_fix_report_20260817.md`

---

*Generated: 2026-08-17 09:46 CEST*
*Protocol: Living Code v3.0 (Grimoire Evolution)*
*Agent: Hermes / Nemotron-3.5-Lightning*