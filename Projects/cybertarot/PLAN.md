# COLD
# CyberTarot — Execution Plan (10 Items)

> **FREEZE (Lord of Code 2026-09-20):** цикл заморожен COLD. Аудит 02:33 чист (дефектов/уязвимостей нет), vitest 37/37 PASS, git clean. Коммиты e22ca5b (formatTimeLeft i18n), 3649a47 (Fisher-Yates shuffle) верифицированы. Outstanding (не код, инфраструктура): дрейф vitest-package.json ^2.0.3 vs node_modules v4.1.10 бьёт tsc -b в npm run build (TS1128) — решить npm ci/skipLibCheck оператору.

> @Аудитор — статус 2026-09-19, Агент-Кодер "Инквизитор Бездны":
> Все 10 пунктов реализованы; 37 vitest-тестов зелёные (5 файлов).
> Дополнительно в этом цикле исправлено 2 реальных бага:
>  1. formatTimeLeft писал единицы «ч/м/с» при всех локалях (дефолт en страдал); теперь локаль-зависимые (e22ca5b).
>  2. shuffleDeck использовал смещённый sort(Math.random()-0.5); заменён на честный Fisher-Yates (3649a47).
> ⚠️ Предсуществующая проблема окружения, НЕ внесена кодом:
>   `npm run build` (шаг tsc -b) падает на парсинге node_modules/vitest/node_modules/tinyrainbow/*.d.ts (TS1128).
>   package.json: vitest ^2.0.3, а в node_modules v4.1.10 — дрейф зависимостей.
>   tsc по моим файлам чист (npx tsc -b = exit 0); все тесты зелёные.

## Item 1: Initialize TDD test suite [DONE — vitest config ест, 37 тестов]
## Item 2: shuffleDeck full 78-card deck [DONE + Fisher-Yates, без повторов]
## Item 3: rollRarity 70/25/5 [DONE — never common]
## Item 4: ManaWell tickWell fill/dry cycle [DONE + formatTimeLeft i18n fix]
## Item 5: localStorage persistence tests [DONE]
## Item 6: card orientation [DONE]
## Item 7: interpretation service tests [DONE]
## Item 8: mint cost deduction [DONE]
## Item 9: collection/sellCard [DONE]
## Item 10: full suite green [DONE]
- **Goal**: Create vitest config and write first failing test for shuffleDeck
- **RED**: Watch test fail because no test infrastructure yet
- **GREEN**: Minimal code to pass test
- **REFACTOR**: Clean up after passing

## Item 2: Fix shuffleDeck to use full 78-card deck
- **Goal**: Ensure shuffleDeck draws from all 78 cards, not just 22 majors (per EVOLUTION_PLAN.md section 1.4 Unit tests)
- Current issue: DECK imported from tarot-deck.json may have issues
- **RED**: Write test that fails — should see >22 unique cards in 100 draws
- **GREEN**: Fix shuffleDeck implementation

## Item 3: Fix rollRarity rarity distribution
- **Goal**: Ensure rollRarity distributes ~70/25/5 (rare:epic:legendary) per EVOLUTION_PLAN.md
- Current: Common has weight 0 but still possible
- **RED**: Test fails — common appears in rollRarity results
- **GREEN**: Fix weight distribution logic

## Item 4: Fix ManaWell tickWell dry/fill cycle
- **Goal**: Ensure ManaWell tickWell correctly handles fill/dry/refill cycle per spec (6h fill, 6h dry)
- Current: Complex state transitions in magicWell.ts
- **RED**: Write test that fails — observe incorrect tickWell behavior
- **GREEN**: Fix tickWell logic

## Item 5: Add localStorage persistence tests
- **Goal**: Test that useTarot hook persists and restores state from localStorage
- **RED**: Test fails — persistence not verified
- **GREEN**: Fix save/load state in useTarot.ts

## Item 6: Fix card orientation property
- **Goal**: Ensure every drawn card has orientation property (upright/reversed)
- **RED**: Test fails — missing orientation
- **GREEN**: Fix shuffleDeck mapping

## Item 7: Add interpretation service tests
- **Goal**: Test mockInterpret returns valid JSON structure
- **RED**: Test fails — mock not working
- **GREEN**: Fix mock or integrate Ollama

## Item 8: Fix mint cost deduction
- **Goal**: Ensure mint deducts correct balance based on rarity cost
- **RED**: Test fails — balance not updated correctly
- **GREEN**: Fix mint callback in useTarot.ts

## Item 9: Add collection management tests
- **Goal**: Test sellCard removes card and adds 60% cost to balance
- **RED**: Test fails — collection/sell not working
- **GREEN**: Fix sellCard callback

## Item 10: Full test suite passes with no regressions
- **Goal**: Run all vitest tests, ensure 100% pass
- **RED**: Some tests failing
- **GREEN**: `vitest run --config vitest.config.ts` — all green