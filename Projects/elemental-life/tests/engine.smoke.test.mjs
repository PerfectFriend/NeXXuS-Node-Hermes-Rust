// Smoke-тест игрового движка. Запуск: node tests/engine.smoke.test.mjs
// Проверяет, что модуль engine.js работает изолированно (без React/UI)
// и что закон сохранения воды держится на всех пресетах ОБЕИХ геометрий
// (гекс — 6 соседей, квадрат — 8 соседей/Мур).
import {
  STATE, GEOMETRY_PRESETS, GEOMETRY_LEVELS, buildInitialField, stepField,
  countWater, mulberry32, gridCellCount,
} from '../src/engine.js';

console.log('STATE keys:', Object.keys(STATE));
console.log('Geometries:', Object.keys(GEOMETRY_PRESETS));
console.log('hex cellCount(30):', gridCellCount('hex', 30));
console.log('square cellCount(30):', gridCellCount('square', 30));

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
    const finalWater = countWater(f).total;
    const ok = initWater === finalWater;
    allOk = allOk && ok;
    console.log(`[${geometryKey}/${name}] water conservation over 500 ticks: ${initWater} -> ${finalWater} (${ok ? 'OK' : 'FAILED'})`);
  }
}

console.log(`\nLevels per geometry: hex=${GEOMETRY_LEVELS.hex.length}, square=${GEOMETRY_LEVELS.square.length}`);

if (!allOk) {
  console.error('\nSMOKE TEST FAILED: water conservation law violated.');
  process.exit(1);
}
console.log('\nAll smoke tests passed.');

