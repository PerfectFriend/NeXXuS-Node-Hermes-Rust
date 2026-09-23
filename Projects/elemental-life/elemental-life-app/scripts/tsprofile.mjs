/* Профилирование портированного движка (engine.ts) на полном поле. */
import { readFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import ts from 'typescript';
const __dirname = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(__dirname, '..', 'src', 'engine', 'engine.ts'), 'utf8');
const js = ts.transpileModule(src, { compilerOptions: { module: 99, target: 99 } }).outputText;
const engine = await import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'));
const { GEOMETRY_PRESETS, buildInitialField, stepField, gridCellCount } = engine;
for (const g of ['hex', 'square']) {
  const radius = g === 'hex' ? 30 : 14;
  const preset = GEOMETRY_PRESETS[g]['classic_balanced'];
  let f = buildInitialField(g, radius, 42);
  const params = preset.params;
  const st = Date.now();
  for (let t = 0; t < 500; t++) f = stepField(g, f, radius, params, () => Math.random());
  const ms = Date.now() - st;
  console.log(`TS [${g}] radius=${radius} cells=${gridCellCount(g, radius)} 500ticks=${ms}ms avg=${(ms / 500).toFixed(3)}ms/tick`);
}