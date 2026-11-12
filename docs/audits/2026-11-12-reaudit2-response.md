# Ответ на внешний аудит — Re-Audit #2 (Grok, 2026-11-12, HEAD 4af49ad)

Вердикт аудитора: **RC1 complete, approved for controlled release and external
review hand-off.** Новых Critical/High/Medium нет; предыдущие закрытия
подтверждены spot-check'ами без регрессий.

## Статус residual-замечаний re-audit #2

| ID | Замечание | Статус |
|---|---|---|
| RES-01 | Исторические bot-токены в полной истории main | Принято владельцем (risk accepted, `docs/DEP-03-secret-rotation.md`); раздача — только squash-mirror, зафиксировано в `SECURITY.md` |
| RES-02 | P2P на 0.0.0.0 с лимитами | Принято; мониторинг метрик в проде, опциональный строгий bind позже |
| RES-06 | Экономика только design-level | Принято для RC1 |
| AB-01 | Первый mount под /run/media — цель внешней копии | **Задокументировано** в `docs/THREAT_MODEL.md` (копия зашифрована at-rest; доверие к mount-политике хоста) — коммит `7bf93e6` |
| AB-02 | `node_backup_delete` без confirm | **Закрыто**: требует `"confirm": true`, симметрия с restore; guardian шлёт confirm — коммит `7bf93e6` |
| AB-03 | Автобэкап в контексте guardian с токеном пользователя | Info, та же trust boundary, что и весь local API — задокументировано |

## Что проверено аудитором в новом коде

- Golden vectors: 14 опкодов, v2+v3, общий JSON + Rust-тест + генератор.
- CI `.github/workflows/rust-ci.yml`: test / clippy `-D warnings` / release /
  cargo audit / wire fuzz — на каждый PR.
- D2 автобэкап: валидация имён (reject `/`, `\`, `..`), flock, restore только
  staging-кандидатом (live swap — при остановленном демоне через CLI),
  внешняя копия best-effort, `hours=0` выключает.
- Регрессий прошлых фиксов нет: лимиты коннектов, per-connection nonce,
  Zeroizing, двухфазная миграция, проверка длины фрейма до аллокации.

## Пакет для внешнего ревью (раздавать только squash-mirror)

`AUDITOR.md` → `SECURITY.md` → `docs/THREAT_MODEL.md` →
`docs/DEP-01-dependency-audit.md` / `docs/DEP-03-secret-rotation.md` →
`docs/plans/2026-11-12-post-audit-plan.md` → эта заметка + серия отчётов в
`docs/audits/`.

## Метрики на момент закрытия (коммит `7bf93e6`)

- workspace 173/173 green, desktop 19/19
- clippy `--all-targets -D warnings` = 0 (оба воркспейса)
- `cargo audit` = 0 non-ignored advisories (игноры обоснованы в `.cargo/audit.toml`)
- wire fuzz (proptest, 512 кейсов) + golden vectors green
- WS live-smoke: ping ok / no-auth → -32001 / oversize → close
