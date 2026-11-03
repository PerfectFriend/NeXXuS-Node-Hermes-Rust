# 📘 CATHEDRAL User Guide

> **How to use Living Code Protocol and Autonomous Code Machine system**  
> Version: 1.0  
> Language: English

---

## Contents

1. [First Launch](#first-launch)
2. [Working with Cron Jobs](#cron-jobs)
3. [Working with Lord Verdicts](#lord-verdicts)
4. [How to Release a Project](#release)
5. [How to Generate MEDIA Report](#media-report)
6. [How to Add a New Coder](#new-coder)
7. [How to Update Role Prompt](#role-prompt)
8. [Common Problems and Solutions](#problems)

---

## 1. First Launch

```bash
# Activate development environment
source ~/build/env.sh

# Check role configuration
python3 ~/LivingCode/orchestration/scripts/check_roster.py --update

# Run verification
bash ~/LivingCode/orchestration/bin/verify.sh

# Make sure it outputs "нет проблем" (no problems)
```

If everything passes, you're ready to work with Living Code Protocol.

---

## 2. Working with Cron Jobs

All tasks are configured in `orchestration/jobs/jobs.json`. Each task has:
- `name` — cron name (e.g., `LV-coder-superguard`)
- `schedule` — cron expression (e.g., `0 * * * *` for every hour)
- `enabled` — whether the task is active
- `model` — LLM model (from whitelist)
- `script` — path to wrapper (if null — agent runs via Hermes)

### Check status of all tasks:
```bash
python3 ~/LivingCode/orchestration/scripts/check_roster.py --update
```

### Enable a task:
Edit `jobs.json`, set `enabled: true`, then copy to `~/.hermes/cron/jobs.json`.

---

## 3. Working with Lord Verdicts

Lord of Code (`LV-lord-of-code`) issues verdicts in `journal.md`:

| Verdict | Meaning | What to do |
|---------|---------|------------|
| HOT | Project ready for release | Run `release_project.py <project>` |
| COLD | Project in development | Continue coder work |
| RETURN | Needs fixes | Coder fixes errors |

### Example record in journal.md:
```
[TRIGGER_LORD] superguard — ВЕРДИКТ: superguard — ГОРЯЧИЙ
```

---

## 4. How to Release a Project

```bash
# Run auto-release for a project
python3 ~/LivingCode/orchestration/scripts/release_project.py superguard

# For other projects:
python3 ~/LivingCode/orchestration/scripts/release_project.py elemental-life
python3 ~/LivingCode/orchestration/scripts/release_project.py cybertarot
python3 ~/LivingCode/orchestration/scripts/release_project.py elemental-life-2
```

The script will:
1. Check Lord verdict (must be HOT)
2. Check release checklist (code cold, no uncommitted, check_roster rc=0)
3. Determine version vX.Y.Z
4. Tag and push to GitHub
5. Export APK to `~/apkexport/`
6. Report in `reports/`
7. Deliver to topic 252 (if CATHEDRAL_BOT_TOKEN configured)

---

## 5. How to Generate MEDIA Report

```bash
# MEDIA report for project (all three roles: artist, musician, producer)
python3 ~/LivingCode/orchestration/scripts/media_contract.py superguard
```

Report is saved in `reports/media-{proj}-{ts}.md` and contains:
- Number of artist assets
- Number of musician audio files
- Number of producer APKs
- Receipt log information

---

## 6. How to Add a New Coder

1. Create project directory in `Projects/<name>/`
2. Add task to `jobs.json` with name `LV-coder-<name>`
3. Create prompt in `scripts/wrappers/prompts/<name>.txt`
4. Run `check_roster.py --update` to verify
5. Run `verify.sh` for verification

---

## 7. How to Update Role Prompt

Role prompts are stored in `scripts/wrappers/prompts/`. To update:
1. Edit the prompt file
2. Add detailed comments (for new coders unfamiliar with project)
3. Save changes
4. Restart the corresponding cron

---

## 8. Common Problems and Solutions

| Problem | Solution |
|---------|----------|
| `CATHEDRAL_BOT_TOKEN` not set | Add token to environment: `export CATHEDRAL_BOT_TOKEN="..."` |
| Reports not delivered to topic 252 | Check `TELEGRAM_CRON_THREAD_ID=252` and bot token |
| Uncommitted changes in projects | Make `git commit` in project directory before release |
| check_roster errors | Fix `jobs.json` and copy to `~/.hermes/cron/jobs.json` |
| Cron jobs paused | Set `enabled: true` in `jobs.json` |
| Windows path error in code | Replace `C:/...` with `/home/thomas/...` |

---

## 9. Getting Help

If something doesn't work:
1. Check logs in `~/.hermes/cron/errors.log`
2. Check reports in `reports/`
3. Check `journal.md` for verdicts and triggers
4. Make sure `verify.sh` outputs "no problems"

---

_May the Great Force of the Universe be with you!_