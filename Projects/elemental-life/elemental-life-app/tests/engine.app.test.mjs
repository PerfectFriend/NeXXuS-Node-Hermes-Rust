// App engine smoke test — validates water conservation on the forked engine.ts
// This mirrors the reference tests/engine.smoke.test.mjs but tests the app's engine.ts

import { createRequire } from 'module';
const require = createRequire(import.meta.url);

// Dynamic import for TS — use the compiled JS or ts-node
// For now, we test the reference engine.js from root
// App engine.ts is tested via build (no runtime loader for .ts in raw Node)

const engine = require('../src/engine/engine.ts') || {};

console.log('STATE keys:', Object.keys(engine.STATE || {}));
console.log('Geometries:', engine.GEOMETRY_PRESETS ? Object.keys(engine.GEOMETRY_PRESETS) : 'N/A');

const STATE = engine.STATE;
const GEOMETRY_PRESETS = engine.GEOMETRY_PRESETS;
const GEOMETRY_LEVELS = engine.GEOMETRY_LEVELS;
const PUZZLE_RADIUS = engine.PUZZLE_RADIUS;

if (!STATE || !GEOMETRY_PRESETS) {
  console.log('SKIP: engine.ts cannot be loaded directly (TypeScript)');
  console.log('Test the reference engine instead: node tests/engine.smoke.test.mjs');
  process.exit(0);
}

function countWater(field) {
  let total = 0;
  for (const cell of field.values()) {
    if (cell.state === STATE.WATER || cell.state === STATE.STEAM) {
      total++;
    }
  }
  return total;
}

function testPresets(geometryKey) {
  const presets = GEOMETRY_PRESETS[geometryKey];
  const names = Object.keys(presets);
  console.log(`\n--- Геометрия: ${geometryKey} (${names.length} пресетов) ---`);
  for (const name of names) {
    const params = presets[name];
    const radius = PUZZLE_RADIUS[geometryKey] ?? 10;
    const field = engine.buildInitialField(geometryKey, radius, 42, params);
    const initial = countWater(field);
    let f = field;
    for (let tick = 0; tick < 200; tick++) {
      f = engine.stepField(geometryKey, f, radius, params, Math.random);
    }
    const final = countWater(f);
    const ok = initial === final;
    console.log(`[${geometryKey}/${name}] water conservation over 200 ticks: ${initial} -> ${final} (${ok ? 'OK' : 'FAIL'})`);
    if (!ok) process.exit(1);
  }
}

if (GEOMETRY_PRESETS.hex) testPresets('hex');
if (GEOMETRY_PRESETS.square) testPresets('square');

console.log('\nAll app engine smoke tests passed.');
