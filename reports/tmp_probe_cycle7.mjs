// Пробник цикла 7: расхождение gridCellCount и makeGrid в движке.
import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, cpSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = '/home/thomas/LivingCode/Projects/elemental-life/elemental-life-app';
const require = createRequire(import.meta.url);
const scratch = mkdtempSync(join(tmpdir(), 'el-eng-'));
mkdirSync(join(scratch, 'src'), { recursive: true });
cpSync(join(ROOT, 'src'), join(scratch, 'src'), { recursive: true });
execFileSync('node', [join(ROOT, 'node_modules/typescript/bin/tsc'),
  'src/engine/engine.ts', '--target','es2022','--module','commonjs',
  '--lib','es2022,dom','--skipLibCheck'], { cwd: scratch, stdio: 'pipe' });
const E = require(join(scratch, 'src/engine/engine.js'));

console.log('=== 1. Квадрат: gridCellCount(N) vs реальный makeGrid(radius) ===');
console.log('   N | gridCellCount(square,N) | реально клеток |  соотношение');
for (const N of [10, 21, 29, 30]) {
  const reported = E.gridCellCount('square', N);
  // Радиус, который реально даст makeGrid: radiusFromSide(N)
  const radius = E.GEOMETRIES ? null : Math.floor((N - 1) / 2);
  const actual = E.makeGrid ? null : null;
  void radius; void actual;
  console.log(`  ${String(N).padStart(2)} | ${String(reported).padStart(21)} |`);
}
console.log('\n  Что показывает NewGameDialog: gridCellCount(geometry, side)');
console.log('  Что реально создаёт поле: makeGrid(geometry, radiusFromSide(side))');
console.log('\n   N | radiusFromSide | реально makeGrid | показывается | во сколько раз меньше');
for (const N of [10, 21, 29, 30]) {
  const shown = E.gridCellCount('square', N);
  const r = Math.floor((N - 1) / 2);
  const actual = (2 * r + 1) * (2 * r + 1);
  console.log(`  ${String(N).padStart(2)} | ${String(r).padStart(13)} | ${String(actual).padStart(16)} | ${String(shown).padStart(12)} | ${(actual / shown).toFixed(2)}x`);
}

console.log('\n=== 2. Гекс: проверка на согласованность ===');
console.log('   N | radiusFromSide | makeGrid | gridCellCount | совпадает?');
for (const N of [10, 21, 30, 31]) {
  const shown = E.gridCellCount('hex', N);
  const r = N - 1;
  const field = E.buildInitialField('hex', r, 42, E.GEOMETRY_PRESETS.hex.classic_balanced.params);
  console.log(`  ${String(N).padStart(2)} | ${String(r).padStart(13)} | ${String(field.size).padStart(8)} | ${String(shown).padStart(12)} | ${field.size === shown ? 'ДА' : 'НЕТ (' + ((field.size - shown) / shown * 100).toFixed(1) + '%)'}`);
}

console.log('\n=== 3. Квадрат: реальное поле vs заявленное ===');
for (const N of [10, 21, 29]) {
  const shown = E.gridCellCount('square', N);
  const r = Math.floor((N - 1) / 2);
  const field = E.buildInitialField('square', r, 42, E.GEOMETRY_PRESETS.square.classic_balanced.params);
  const ratio = field.size / shown;
  console.log(`  N=${N}: заявлено ${shown}, реально ${field.size}  -> занижение в ${(1/ratio).toFixed(2)}x ${ratio < 1 ? ' <-- ДЕФЕКТ' : ''}`);
}

console.log('\n=== 4. Где используется gridCellCount в UI ===');
import { readFileSync } from 'node:fs';
const S = ROOT + '/src/';
for (const f of ['components/NewGameDialog.tsx', 'components/SettingsModal.tsx', 'hooks/useSimulation.ts', 'components/GameHeader.tsx']) {
  const src = readFileSync(S + f, 'utf8');
  const hits = [...src.matchAll(/gridCellCount\([^)]*\)/g)].map((m) => m[0]);
  if (hits.length) console.log(`  ${f}: ${hits.join(', ')}`);
}

console.log('\n=== 5. radiusFromSide согласованность ===');
for (const geo of ['hex', 'square']) {
  for (const N of [10, 21, 29, 30]) {
    const r = geo === 'hex' ? N - 1 : Math.floor((N - 1) / 2);
    const shown = E.gridCellCount(geo, N);
    const actual = E.buildInitialField(geo, r, 7, E.GEOMETRY_PRESETS[geo].classic_balanced.params).size;
    const ok = actual === shown;
    console.log(`  ${geo.padEnd(6)} N=${String(N).padStart(2)}: gridCellCount=${String(shown).padStart(5)}, фактически=${String(actual).padStart(5)} ${ok ? 'OK' : '<-- РАСХОЖДЕНИЕ ' + (actual - shown)}`);
  }
}