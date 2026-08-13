import { stepField, buildInitialField, countWater, GEOMETRY_PRESETS, mulberry32 } from '../src/engine/engine.ts';

function profile(geom, radius, side, label) {
  const params = GEOMETRY_PRESETS[geom].classic_balanced.params;
  let field = buildInitialField(geom, radius, 42);
  const rng = mulberry32(999);

  // Warmup 10 ticks
  for (let i = 0; i < 10; i++) {
    field = stepField(geom, field, radius, params, rng);
  }

  // Benchmark 50 ticks
  const start = performance.now();
  for (let i = 0; i < 50; i++) {
    field = stepField(geom, field, radius, params, rng);
  }
  const elapsed = performance.now() - start;
  const perTick = elapsed / 50;
  const cells = field.size;

  console.log(`${label}: ${cells} cells, ${perTick.toFixed(2)}ms/tick (${elapsed.toFixed(1)}ms for 50 ticks)`);
}

profile('hex', 29, 30, 'Hex sandbox');
profile('square', 14, 29, 'Square sandbox');
profile('hex', 7, 14, 'Hex puzzle');
profile('square', 6, 13, 'Square puzzle');
