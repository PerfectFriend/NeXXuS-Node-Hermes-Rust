// Функциональный smoke-тест ПОРТИРОВАННОГО движка (engine.ts).
//
// В отличие от engine.smoke.test.mjs (статические проверки строк),
// этот тест ДЕЙСТВИТЕЛЬНО ВЫПОЛНЯЕТ симуляцию, оттранспилировав
// engine.ts в чистый JS через установленный пакет typescript.
// Он повторяет функциональный тест JS-движка (src/engine.js в корне):
// закон сохранения воды (water+steam = const) на ВСЕХ пресетах ОБЕИХ
// геометрий за 500 тиков — это критическое требование намерения из PLAN.md.
//
// Запуск: node tests/engine.functional.test.mjs

import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import ts from 'typescript';

const __dirname = dirname(fileURLToPath(import.meta.url));
const enginePath = join(__dirname, '..', 'src', 'engine', 'engine.ts');
const engineSrc = readFileSync(enginePath, 'utf8');

// 1) Транспилируем engine.ts (erasableSyntaxOnly, нет импортов — беспроблемно).
const js = ts.transpileModule(engineSrc, {
  compilerOptions: {
    module: ts.ModuleKind.ES2022,
    target: ts.ScriptTarget.ES2022,
  },
  fileName: enginePath,
}).outputText;

// 2) Выполняем в изолированном модуле.
const blob = `data:text/javascript;base64,${Buffer.from(js).toString('base64')}`;
const engine = await import(blob);

const { STATE, GEOMETRY_PRESETS, GEOMETRY_LEVELS, buildInitialField, stepField,
        countWater, mulberry32, gridCellCount } = engine;

console.log('engine.ts transpiled OK. STATE keys:', Object.keys(STATE).join(','));
console.log('Geometries:', Object.keys(GEOMETRY_PRESETS).join(', '));

let allOk = true;

for (const geometryKey of ['hex', 'square']) {
  const presets = GEOMETRY_PRESETS[geometryKey];
  console.log(`\n--- Геометрия: ${geometryKey} (${Object.keys(presets).length} пресетов) ---`);
  for (const [name, preset] of Object.entries(presets)) {
    const radius = geometryKey === 'hex' ? 10 : 7;
    const field = buildInitialField(geometryKey, radius, 42);
    const rng = mulberry32(123);
    const initWater = countWater(field).total;
    let f = field;
    for (let t = 0; t < 500; t++) {
      f = stepField(geometryKey, f, radius, preset.params, rng);
    }
    const finalTotal = countWater(f).total;
    const ok = finalTotal === initWater;
    if (!ok) allOk = false;
    console.log(`[${geometryKey}/${name}] water conservation over 500 ticks: ${initWater} -> ${finalTotal} ${ok ? '(OK)' : '(FAIL)'}`);
  }
}

console.log('\nLevels per geometry:', Object.fromEntries(
  Object.entries(GEOMETRY_LEVELS).map(([k, v]) => [k, typeof v === 'number' ? v : (v && v.length) || Object.keys(v).length])
));

// Информационно: размер сетки вычисляется самим движком.
console.log('gridCellCount hex(10):', gridCellCount('hex', 10));
console.log('gridCellCount square(7):', gridCellCount('square', 7));

if (!allOk) {
  console.error('\n✗ Engine port FAILED functional water-conservation check');
  process.exit(1);
}
console.log('\n✓ Engine port passed functional smoke test (all presets conserve water over 500 ticks).');
process.exit(0);