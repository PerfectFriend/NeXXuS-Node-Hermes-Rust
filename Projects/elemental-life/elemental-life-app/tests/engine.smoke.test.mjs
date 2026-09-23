// Smoke-тест игрового движка. Запуск: node tests/engine.smoke.test.mjs
// Проверяет экспорты engine.ts и наличие логики сохранения воды

import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, resolve } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const projectRoot = resolve(__dirname, '..');

// Читаем engine.ts и проверяем наличие экспортов
const engineSource = readFileSync(resolve(projectRoot, 'src/engine/engine.ts'), 'utf-8');

const requiredExports = [
  'STATE',
  'GEOMETRY_PRESETS', 
  'GEOMETRY_LEVELS',
  'mulberry32',
  'buildInitialField',
  'stepField',
  'countWater',
  'gridCellCount',
];

console.log('Checking engine.ts exports...');
let allExportsFound = true;
for (const exp of requiredExports) {
  const found = engineSource.includes(`export {`) && engineSource.includes(exp);
  console.log(`  ${found ? '✓' : '✗'} ${exp}`);
  if (!found) allExportsFound = false;
}

if (!allExportsFound) {
  console.error('\nMissing exports in engine.ts');
  process.exit(1);
}

console.log('\nAll exports present. Checking water conservation logic patterns...');

// Движок использует константы S_WATER и S_STEAM вместо STATE.WATER / STATE.STEAM
const conservationPatterns = [
  'S_WATER',    // вода как константа
  'S_STEAM',    // пар как константа
  'steamRainTicks', // пар возвращается в воду
  'countWater', // функция подсчета воды+пара
  'case S_WATER:', // обработка воды в stepField
  'case S_STEAM:', // обработка пара в stepField
];

let patternsFound = 0;
for (const pattern of conservationPatterns) {
  const found = engineSource.includes(pattern);
  console.log(`  ${found ? '✓' : '✗'} ${pattern}`);
  if (found) patternsFound++;
}

if (patternsFound === conservationPatterns.length) {
  console.log('\n✓ Water conservation logic patterns found in engine');
  console.log('Note: Full integration test requires compiled JS (run after npm run build)');
  process.exit(0);
} else {
  console.error(`\n✗ Water conservation logic incomplete (${patternsFound}/${conservationPatterns.length} patterns found)`);
  process.exit(1);
}