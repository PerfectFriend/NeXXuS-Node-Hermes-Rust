// Пробник цикла 5: useHiddenEntrance и WalletTxHistory.
console.log('=== 1. useHiddenEntrance: пустая целевая последовательность ===');
{
  // getStoredSequence() берёт из localStorage. Если там '[]' или ключа нет,
  // targetRef.current = [] и seqLen = 0.
  const target = [];               // нет сохранённой последовательности
  const seqLen = target.length;    // 0
  let seq = [];

  const recordTap = (element) => {
    seq = [...seq, element].slice(-seqLen);   // .slice(-0) === .slice(0) — НЕ пусто!
    const matched = seq.length === seqLen && seq.every((s, i) => s === target[i]);
    return { seq: [...seq], matched };
  };

  const r1 = recordTap('fire');
  console.log(`  1-й тап: seq=${JSON.stringify(r1.seq)} (len ${r1.seq.length}), target len ${seqLen}, matched=${r1.matched}`);
  if (r1.matched) console.log('  ДЕФЕКТ: разблокировка сработала при пустой цели — секретная дверь открыта без ввода кода');
  else console.log('  ок');
}

console.log('\n=== 2. useHiddenEntrance: getStoredSequence без проверки массива ===');
{
  for (const [name, raw] of [
    ['объект', '{"0":"FIRE"}'],
    ['строка', '"пожар"'],
    ['null', 'null'],
    ['число', '42'],
  ]) {
    const parsed = JSON.parse(raw);
    const mapped = (Array.isArray(parsed) ? parsed : []).map?.(s => s) ?? 'CRASH: .map is not a function';
    console.log(`  localStorage='${raw}' -> ${typeof mapped === 'string' ? mapped : JSON.stringify(mapped)}`);
  }
  console.log('  getStoredSequence возвращает СЫРОЙ JSON.parse; stored.map(...) на объекте бросает TypeError.');
}

console.log('\n=== 3. useHiddenEntrance: setTimeout(setShowHint(false)) без отмены ===');
{
  let unmounted = false;
  const handle = setTimeout(() => { console.log('    сработал таймер подсказки'); }, 10);
  // reset() не отменяет таймер; после reset() он всё равно вызовет setShowHint(false)
  console.log('  reset() очищает seqRef/unlocked/showHint/firedRef, но НЕ clearTimeout(handle)');
  console.log(`  handle жив: ${!unmounted}; в React это setState на размонтированном компоненте (React 18+ — no-op, React 17 — warning)`);
  clearTimeout(handle);
}

console.log('\n=== 4. WalletTxHistory: getElementalHistory отдаёт ЖИВУЮ ссылку ===');
{
  const ledger = { history: [{ to: 'self', amount: 10, reason: 'r', ts: 1 }] };
  const txs1 = ledger.history;            // как в getElementalHistory()
  const txs2 = ledger.history;
  console.log(`  два вызова возвращают один и тот же объект: ${txs1 === txs2}`);
  console.log('  => Снапшота нет: если кто-то мутирует результат, он мутирует ledger.');
}

console.log('\n=== 5. WalletTxHistory: key={i} по индексу ===');
{
  const items = [{ amount: 1 }, { amount: 2 }, { amount: 3 }];
  console.log('  key={i} при [{...txs}.reverse()] — после разворота и смены данных');
  console.log('  React переиспользует DOM-узлы по позиции: у одинаковых по структуре строк');
  console.log('  состояние узла (если появится) переедет на другую транзакцию.');
  console.log(`  Транзакций без стабильного id: ${items.filter(x => !x.hash).length}/${items.length}`);
}