// Пробник кандидатов цикла 2 (вне дерева проекта).
// Проверяет гипотезы ДО правки кода. Каждый кандидат = конкретное наблюдение.
import { readFileSync } from 'node:fs';

const ROOT = '/home/thomas/LivingCode/Projects/elemental-life/elemental-life-app/src';

// --- Кандидат A: sendElemental с отрицательным amount ----------------------
console.log('=== A: sendElemental(amount = -50) ===');
{
  // Изолированная копия тела функции (без localStorage) — логика 1-в-1.
  let balance = 100;
  const send = (to, amount) => {
    if (balance < amount) return false;
    balance -= amount;
    return true;
  };
  const ok = send('attacker', -50);
  console.log(`  вернула ${ok}, баланс 100 -> ${balance}`);
  console.log(`  ВЫВОД: ${balance > 100 ? 'ДЕФЕКТ — отрицательная отправка НАЧИСЛЯЕТ токены' : 'ок'}`);
}

// --- Кандидат B: receiveElemental с отрицательным amount -------------------
console.log('\n=== B: receiveElemental(amount = -30) ===');
{
  let balance = 100, totalReceived = 0;
  const receive = (from, amount) => { balance += amount; totalReceived += amount; };
  receive('x', -30);
  console.log(`  баланс 100 -> ${balance}, totalReceived -> ${totalReceived}`);
  console.log(`  ВЫВОД: ${balance < 100 && totalReceived < 0 ? 'ДЕФЕКТ — отрицательное получение ОТРИЦАТЕЛЬНО в статистике' : 'ок'}`);
}

// --- Кандидат C: loadLedger на испорченном/неполном JSON -------------------
console.log('\n=== C: loadLedger на разных payload ===');
for (const [name, raw] of [
  ['массив вместо объекта', '[1,2,3]'],
  ['balance строкой', '{"balance":"100"}'],
  ['пустой объект', '{}'],
  ['balance:null', '{"balance":null}'],
]) {
  let parsed;
  try { parsed = JSON.parse(raw); } catch (e) { parsed = null; }
  const ledger = parsed;
  // Что делает реальный код: ledger.balance += 10
  const before = ledger.balance;
  ledger.balance += 10;
  console.log(`  ${name.padEnd(22)} balance ${JSON.stringify(before)} -> ${JSON.stringify(ledger.balance)}`);
}

// --- Кандидат D: history.ts loadHistory на не-массиве -----------------------
console.log('\n=== D: history.loadHistory на не-массиве ===');
{
  const raw = '{"hash":"0xabc"}';
  const txs = JSON.parse(raw);
  try {
    txs.unshift({ hash: '0xdef' });
    console.log('  unshift отработал, история:', JSON.stringify(txs));
  } catch (e) {
    console.log(`  ДЕФЕКТ — unshift бросает: ${e.constructor.name}: ${e.message}`);
    console.log('  Причина: loadHistory возвращает JSON.parse без проверки Array.isArray');
  }
}

// --- Кандидат E: rewardLevelCompletion с отрицательным индексом -------------
console.log('\n=== E: rewardLevelCompletion(levelIndex = -5) ===');
{
  let balance = 100;
  const reward = 10 + (-5) * 5;
  balance += reward;
  console.log(`  reward = ${reward}, баланс 100 -> ${balance}`);
  console.log(`  ВЫВОД: ${reward < 0 ? 'ДЕФЕКТ — отрицательная награда СНИЖАЕТ баланс' : 'ок'}`);
}

// --- Кандидат F: scan реальных исходников на эти паттерны -----------------
console.log('\n=== F: где вызываются эти функции (живой код) ===');
{
  const callers = ['components/WalletScreen.tsx', 'components/PuzzleOverlay.tsx',
                   'components/GameToolbar.tsx', 'App.tsx', 'components/WalletTxHistory.tsx'];
  for (const rel of callers) {
    let src;
    try { src = readFileSync(`${ROOT}/${rel}`, 'utf8'); } catch { continue; }
    const hits = ['sendElemental(', 'receiveElemental(', 'rewardLevelCompletion(', 'addTx(', 'updateTxStatus(']
      .filter((fn) => src.includes(fn));
    if (hits.length) console.log(`  ${rel}: ${hits.join(', ')}`);
  }
}