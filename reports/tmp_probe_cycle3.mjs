// Пробник цикла 3: мёртвый код после return в useSimulation.ts (строки 416-449).
import { readFileSync } from 'node:fs';

const SRC = '/home/thomas/LivingCode/Projects/elemental-life/elemental-life-app/src/hooks/useSimulation.ts';
const src = readFileSync(SRC, 'utf8');
const lines = src.split('\n');

console.log('=== 1. Структура функции useSimulation ===');
const retIdx = lines.findIndex((l) => /^\s{2}return \{\s*$/.test(l));
console.log(`  return хука на строке: ${retIdx + 1}`);
let after = 0;
for (let i = retIdx + 1; i < lines.length; i++) {
  const l = lines[i];
  if (/^\s{4}useEffect\(/.test(l) || /^\s{2}\}\)/.test(l)) { after = i + 1; break; }
}
console.log(`  Код ПОСЛЕ return (строки ${retIdx + 2}..${after - 1}), всего ${after - retIdx - 2} строк:`);
lines.slice(retIdx + 1, after).forEach((l, i) => console.log(`    ${retIdx + 2 + i}| ${l}`));

console.log('\n=== 2. Что реально теряется ===');
const savesKey = /localStorage\.setItem\('elemental-life-state'/.test(lines.slice(retIdx).join('\n'));
console.log(`  localStorage.setItem('elemental-life-state', ...) находится ПОСЛЕ return: ${savesKey}`);
console.log('  => useEffect сохранения состояния НИКОГДА не регистрируется.');
console.log('  => прогресс игрока не сохраняется: перезапуск приложения = потеря поля.');

console.log('\n=== 3. Второй дефект в том же блоке: rngState продвигает генератор ===');
const rngCall = lines.slice(retIdx).join('\n').match(/rngState:\s*state\.rng\s*\?\s*\(state\.rng\(\)/);
console.log(`  ${rngCall ? 'НАЙДЕНО' : 'нет'}: rngState: state.rng ? (state.rng() as number) : undefined`);
console.log('  state.rng — это функция ГЕНЕРАТОРА (mulberry32), а не состояние.');
console.log('  Вызов state.rng() ПРОДВИГАЕТ ГПСЧ на один шаг и возвращает число.');
console.log('  => serializeState тихо сдвигает последовательность случайных чисел.');

// Проверяем семантику mulberry32 из движка
console.log('\n=== 4. Доказательство побочного эффекта на реальном mulberry32 ===');
const engine = readFileSync('/home/thomas/LivingCode/Projects/elemental-life/elemental-life-app/src/engine/engine.ts', 'utf8');
const mm = engine.match(/export function mulberry32\([^)]*\)\s*\{[\s\S]*?\n\}/);
if (!mm) { console.log('  mulberry32 не найден'); } else {
  const mulberry32 = new Function('a', mm[0].replace(/export function mulberry32/, 'return function').replace(/\n\}$/, '\n}'));
  const seed = 12345 + 999;
  const a = mulberry32(seed);
  const b = mulberry32(seed);
  const seqA = [a(), a(), a()];
  const seqB = [b(), b(), b()];
  // Сценарий «как в коде»: кто-то сериализует состояние (вызывает rng()) и потом продолжает считать.
  const c = mulberry32(seed);
  c(); // <- «сохранение состояния» съело первый элемент последовательности
  const seqAfterSave = [c(), c(), c()];
  console.log(`  нормальная последовательность:   ${seqA.map((n) => n.toFixed(6)).join(', ')}`);
  console.log(`  после «сохранения» (1 вызов):     ${seqAfterSave.map((n) => n.toFixed(6)).join(', ')}`);
  console.log(`  совпали: ${seqA[0] === seqAfterSave[0] ? 'ДА (тогда дефекта нет)' : 'НЕТ — последовательность сдвинута'}`);
  console.log(`  серии равны сами себе: ${seqB[0] === seqA[0] ? 'да (детерминизм в порядке)' : 'нет'}`);
}

console.log('\n=== ВЫВОД ===');
console.log('  ДЕФЕКТ 1 [СР]: сохранение состояния мертво — код после return в хуке.');
console.log('  ДЕФЕКТ 2 [СР, латентный]: rngState продвигает ГПСЧ при каждом сохранении.');
console.log('  Сейчас оба не наблюдаемы — код недостижим. Но любой рефакторинг');
console.log('  (например, перенос return в конец файла) включит оба сразу.');