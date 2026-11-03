// Пробник цикла 7 (Кодер, вторая попытка полосы): согласованность счётчика клеток
// gridCellCount() с реальным полем makeGrid()/buildInitialField() и с вызовами в UI.
import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, cpSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const ROOT = '/home/thomas/LivingCode/Projects/elemental-life/elemental-life-app';
const require = createRequire(import.meta.url);
const scratch = mkdtempSync(join(tmpdir(), 'el-eng-'));
mkdirSync(join(scratch, 'src'), { recursive: true });
cpSync(join(ROOT, 'src'), join(scratch, 'src'), { recursive: true });
execFileSync('node', [join(ROOT, 'node_modules/typescript/bin/tsc'),
  'src/engine/engine.ts', '--target', 'es2022', '--module', 'commonjs',
  '--lib', 'es2022,dom', '--skipLibCheck'], { cwd: scratch, stdio: 'pipe' });
const E = require(join(scratch, 'src/engine/engine.js'));

console.log('=== 1. Что делает gridCellCount и какой радиус реально строит поле ===');
console.log('gridCellCount =', E.gridCellCount.toString().split('\n').slice(0, 24).join('\n'));
console.log('\nradiusFromSide =', typeof E.radiusFromSide === 'function' ? E.radiusFromSide.toString() : 'НЕТ В ЭКСПОРТЕ');
void E;

console.log('\n=== 2. Квадрат: заявленное число клеток vs фактическое поле ===');
for (const side of [10, 21, 29, 30]) {
  const shown = E.gridCellCount('square', side);
  const r = Math.floor((side - 1) / 2);
  const field = E.buildInitialField('square', r, 42, E.GEOMETRY_PRESETS.square.classic_balanced.params);
  console.log(`  side=${String(side).padStart(2)} радиус=${String(r).padStart(2)}: заявлено ${String(shown).padStart(4)}, фактически ${String(field.size).padStart(4)} ${field.size === shown ? 'OK' : '<-- РАСХОЖДЕНИЕ x' + (field.size / shown).toFixed(2)}`);
}

console.log('\n=== 3. Гекс: заявленное vs фактическое ===');
for (const side of [10, 21, 30, 31]) {
  const shown = E.gridCellCount('hex', side);
  const r = side - 1;
  const field = E.buildInitialField('hex', r, 42, E.GEOMETRY_PRESETS.hex.classic_balanced.params);
  console.log(`  side=${String(side).padStart(2)} радиус=${String(r).padStart(2)}: заявлено ${String(shown).padStart(5)}, фактически ${String(field.size).padStart(5)} ${field.size === shown ? 'OK' : '<-- РАСХОЖДЕНИЕ x' + (field.size / shown).toFixed(2)}`);
}

console.log('\n=== 4. Вызовы gridCellCount в исходниках UI ===');
for (const f of ['components/NewGameDialog.tsx', 'components/SettingsModal.tsx', 'hooks/useSimulation.ts', 'components/GameHeader.tsx', 'App.tsx']) {
  let src = '';
  try { src = readFileSync(ROOT + '/src/' + f, 'utf8'); } catch { continue; }
  const hits = [...src.matchAll(/.{0,60}gridCellCount\([\s\S]{0,80}?\)/g)].map((m) => m[0].replace(/\s+/g, ' '));
  if (hits.length) hits.forEach((h) => console.log(`  ${f}: …${h}…`));
}
console.log('\n=== 5. Комментарий в движке про квадрат ===');
const eng = readFileSync(ROOT + '/src/engine/engine.ts', 'utf8');
const line = eng.split('\n').findIndex((l) => l.includes('gridCellCount'));
console.log(eng.split('\n').slice(Math.max(0, line - 12), line + 14).map((l, i) => `  ${line - 12 + i + 1}| ${l}`).join('\n'));
