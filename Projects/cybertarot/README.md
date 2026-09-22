# Cybertarot

## Статус (публикация 2026-09-20)

- **Состояние:** Стабильно. Код холодный, PLAN.md закрыт (10/10 пунктов).
- **Тесты:** 37/37 vitest passed (было 32). tsc чист по файлам проекта, git clean.
- **Исправлено:** локале-зависимые единицы формата времени `formatTimeLeft`; честный Fisher-Yates вместо смещённого `sort(Math.random()-0.5)` в `shuffleDeck`.
- **Известно на аудит:** дрейф deps vitest (package.json `^2.0.3` vs node_modules v4.1.10) роняет `tsc -b` в `npm run build` (TS1128 в tinyrainbow). Кода не касается — рекомендовано `npm ci` по lock или `skipLibCheck`.

## Коммиты вехи

- `e22ca5b` — formatTimeLeft локали
- `3649a47` — Fisher-Yates shuffle
- `42c7b71` — план закрыт