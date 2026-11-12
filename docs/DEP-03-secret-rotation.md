# DEP-03 — ротация секретов из истории git (владелец, ручной шаг)

Статус: **OPEN — только владелец**. До раздачи репозитория внешнему аудитору
обязательно выполнить оба пункта ниже.

Значения секретов здесь НЕ хранятся (правило репо: [REDACTED]).

## Что найдено в истории (инвентарь, 2026-11-12)

Скан `git log --all -p` по паттернам `ghp_…`, `github_pat_…`, Telegram
`ID:token`, `sk-…`, `xox…`:

| Секрет | Где в истории | Действие |
|---|---|---|
| Telegram bot token, bot-ID `8853927147` | 2 вхождения, старые pre-squash коммиты (`50b925c` «test commit», `19f1e1f` «Auto-backup», `2e01dac`, `6404d7a`, `983f6f0` — state/scripts/orchestrator файлы) | Ревокать через @BotFather (`/revoke`) |
| Telegram bot token, bot-ID `8883516682` | 8 вхождений, те же старые коммиты | Ревокать через @BotFather |
| Telegram bot token, bot-ID `8896772547` | 12 вхождений, те же старые коммиты | Ревокать через @BotFather |
| GitHub PAT `ghp_…` | **Не найден** — в истории только placeholder `ghp_xxxx` в документации (`26f817f` и др.) | Для протокола: перепроверить на GitHub → Settings → Developer settings → PATs, что ни один старый токен не активен |

Коммиты-источники: `50b925c`, `19f1e1f`, `2e01dac`, `6404d7a`, `983f6f0`
(pre-squash «Clear repository» ветка — файлы `state/orchestrator_state.json`,
`scripts/*`, `wrappers/*`, `tmp/localllama.json`).

## Порядок закрытия

1. **Ревокация** (сначала!): 3 bot-токена через @BotFather `/revoke`; проверить
   PAT в GitHub settings. Ревокация валидна сразу, до переписывания истории.
2. **Чистка истории**: `git filter-repo` (или squash-копия для аудитора):
   удалить пути `state/`, `scripts/vault_git_sync.py`, `scripts/professor_sync_cron.py`,
   `wrappers/`, `tmp/` из всей истории + вычистить паттерны токенов.
   После filter-repo: force-push всех веток + tags, запросить у GitHub
   «secret scanning cache purge» / invalidate старых push'ей.
3. **Доказательство аудитору**: дать доступ к squash-копии (один коммит,
   без истории) — там секретов нет (проверено сканом выше по текущему дереву).

## Проверка текущего дерева (2026-11-12)

Скан рабочего дерева по тем же паттернам: чисто. Секреты живут только в
`~/.hermes/secrets/` вне репо (mode 600).
