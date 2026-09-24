// Тест «жадного игрока» для режима головоломки «Полив пустоты» (Point 8, Протокол Живого Кода).
//
// Проверяет НАСТОЯЩИЙ движок (engine.ts, как в engine.functional.test.mjs:
// transpile через ts.transpileModule → data:URL ESM): все 10 уровней
// (2 геометрии × 5) ПРОХОДИМЫ по механике UI (useSimulation):
//   - поле строится buildLevelField(geometry, PUZZLE_RADIUS[g], seed, level);
//   - симуляция бежит на params = classic_balanced ТЕКУЩЕЙ геометрии
//     (prev.params — так делает UI в puzzle-режиме);
//   - rng = mulberry32(seed + 999) — как startLevel/switchMode в useSimulation;
//   - клик игрока = вода в ПУСТУЮ клетку, тратит 1 каплю;
//   - поражение = dropletsLeft == 0 и прошло > 80 тиков после этого;
//   - победа = checkPuzzleWinTick(field) == true WIN_STABLE_TICKS (15) раз подряд.
//
// «Жадный игрок» (greedy): каждый тик поливает старейшие пустые клетки.
// Это минимально-разумная стратегия (не оптимальная — просто честный жадный
// обход), доказывающая УРОВНИ ПРОХОДИМЫ, а не «слишком тугие» (Point 8:
// "ensure limits feel appropriate, not too tight or too easy").
//
// Запуск: node tests/engine.puzzle.test.mjs

import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import ts from 'typescript';

const __dirname = dirname(fileURLToPath(import.meta.url));
const enginePath = join(__dirname, '..', 'src', 'engine', 'engine.ts');
const engineSrc = readFileSync(enginePath, 'utf8');

const js = ts.transpileModule(engineSrc, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: enginePath,
}).outputText;

const blob = `data:text/javascript;base64,${Buffer.from(js).toString('base64')}`;
const engine = await import(blob);

const {
  STATE, GEOMETRY_PRESETS, GEOMETRY_LEVELS, PUZZLE_RADIUS,
  WIN_STABLE_TICKS, WATER, mulberry32, buildLevelField, checkPuzzleWinTick,
  stepField,
} = engine;

const paramsFor = (g) => GEOMETRY_PRESETS[g].classic_balanced.params;
const MAX_TICKS = 4000;      // жёсткий потолок на длину игры
const MAX_CLICKS_PER_TICK = 6; // столько капель игрок может капнуть за один тик

let failures = 0;
let totalDropletsUsed = 0;
const results = [];

for (const g of ['hex', 'square']) {
  const levels = GEOMETRY_LEVELS[g];
  console.log(`\n--- Геометрия: ${g} (${levels.length} уровней) ---`);
  for (const level of levels) {
    // Зеркалим UI: seed фиксирован для воспроизводимости, rng для stepField — mulberry32(seed+999)
    const seed = 1000 + level.id * 17;
    const radius = PUZZLE_RADIUS[g];
    let field = buildLevelField(g, radius, seed, level);
    const rng = mulberry32(seed + 999);
    const params = paramsFor(g);

    let droplets = level.droplets;
    let winStreak = 0;
    let puzzleWon = false;
    let dropletsRanOutTick = Infinity;
    let puzzleFailed = false;
    let tick = 0;

    while (!puzzleWon && !puzzleFailed && tick < MAX_TICKS) {
      // --- Ход игрока: жадный полив старейших пустых клеток ---
      let clicks = 0;
      while (clicks < MAX_CLICKS_PER_TICK && droplets > 0) {
        // Ищем старейшую пустую клетку (последнюю по возрасту); tile count 469/441 —
        // линейный скан на каждый клик терпим в тесте (469*6 сканов/тик).
        let oldest = null;
        for (const [k, cell] of field) {
          if (cell.state === STATE.EMPTY && (oldest === null || (cell.age || 0) > (oldest.cell.age || 0))) {
            oldest = { k, cell };
          }
        }
        if (oldest === null) break; // пустых нет — полить нечего
        const next = new Map(field);
        next.set(oldest.k, { state: WATER, age: 0 });
        field = next;
        droplets -= 1;
        clicks += 1;
      }

      // --- Тик симуляции (как doStep в useSimulation) ---
      field = stepField(g, field, radius, params, rng);
      tick += 1;

      // --- Проверки состояния (как doStep) ---
      if (!puzzleWon && checkPuzzleWinTick(field)) {
        winStreak += 1;
        if (winStreak >= WIN_STABLE_TICKS) puzzleWon = true;
      } else {
        winStreak = 0;
      }

      if (!puzzleWon && droplets <= 0 && dropletsRanOutTick === Infinity) {
        dropletsRanOutTick = tick;
      }
      if (!puzzleWon && droplets > 0) dropletsRanOutTick = Infinity;
      if (!puzzleWon && droplets <= 0 && dropletsRanOutTick !== Infinity &&
          tick - dropletsRanOutTick > 80) {
        puzzleFailed = true;
      }
    }

    const dropletsUsed = level.droplets - droplets;
    totalDropletsUsed += dropletsUsed;
    const ok = puzzleWon && !puzzleFailed;
    if (!ok) failures += 1;
    const verdict = puzzleWon ? 'WON' : puzzleFailed ? 'FAILED' : 'TIMEOUT';
    console.log(`[${g}/Уровень ${level.id}] ${verdict} за ${tick} тиков, капель потрачено: ${dropletsUsed}/${level.droplets} ${ok ? '(OK)' : '(FAIL)'}`);
    results.push({ g, levelId: level.id, tick, dropletsUsed, dropletsTotal: level.droplets, verdict });
  }
}

// --- Итоговая сводка ---
console.log('\n=== Сводка ===');
console.log(`Уровней пройдено: ${results.filter(r => r.verdict === 'WON').length}/${results.length}`);
console.log(`Капель потрачено суммарно: ${totalDropletsUsed}`);

if (failures > 0) {
  console.error(`\n✗ Point 8 FAILED: ${failures} уровень(ей) непроходимы для жадного игрока`);
  process.exit(1);
}
console.log('\n✓ Point 8 PASSED: все 10 уровней (2 геометрии × 5) проходимы жадным игроком.');
process.exit(0);
