// Пробник: повторная награда за уровень (App.tsx:264-270).
// Гипотеза: useEffect зависит от [puzzleWon, geometry, levelIndex, profile, ...].
// При победе он вызывает rewardLevelCompletion. Если puzzleWon остаётся true,
// а ЛЮБАЯ другая зависимость изменится — награда начисляется ПОВТОРНО.
console.log('=== Модель useEffect из App.tsx:264-270 ===');
{
  let ledger = { balance: 0, totalMined: 0 };
  const reward = (levelIndex) => {
    const r = 10 + levelIndex * 5;
    ledger.balance += r;
    ledger.totalMined += r;
  };

  // Сценарий 1: обычная победа — эффект отрабатывает один раз.
  let puzzleWon = false;
  let geometry = 'hex', levelIndex = 0, profile = { id: 1 };

  const runEffect = () => {
    if (puzzleWon) reward(levelIndex);
  };

  puzzleWon = true;
  runEffect();
  console.log(`  1. победа на уровне 0: balance=${ledger.balance}, totalMined=${ledger.totalMined}`);

  // Сценарий 2: профиль обновился (например, пересоздан/синхронизирован),
  // puzzleWon всё ещё true -> эффект с зависимостью 'profile' перезапускается.
  profile = { id: 2 };
  runEffect();
  console.log(`  2. profile обновился: balance=${ledger.balance}, totalMined=${ledger.totalMined}  <-- ПОВТОР?`);

  // Сценарий 3: переключение геометрии при том же puzzleWon.
  geometry = 'square';
  runEffect();
  console.log(`  3. смена геометрии:   balance=${ledger.balance}, totalMined=${ledger.totalMined}  <-- ПОВТОР?`);

  // Сценарий 4: игрок перезапускает тот же уровень (levelIndex 0 -> 1 -> 0).
  levelIndex = 1; runEffect();
  levelIndex = 0; runEffect();
  console.log(`  4. переигрывание:     balance=${ledger.balance}, totalMined=${ledger.totalMined}`);

  const expected = 10; // уровень 0 = 10
  console.log(`\n  Ожидалось за одну победу на уровне 0: ${expected}`);
  console.log(`  Фактически начислено: ${ledger.totalMined}`);
  console.log(`  ВЫВОД: ${ledger.totalMined > expected ? 'ДЕФЕКТ — награда начисляется повторно' : 'ок'}`);
}

// Проверка: есть ли защита от повторной награды где-либо ещё?
console.log('\n=== Есть ли idempotency-guard? ===');
{
  const { readFileSync } = await import('node:fs');
  const src = readFileSync('/home/thomas/LivingCode/Projects/elemental-life/elemental-life-app/src/wallet/elemental.ts', 'utf8');
  const hasGuard = /levelIndex\s*===|alreadyRewarded|rewarded|seen|completed/i.test(src);
  console.log(`  rewardLevelCompletion содержит защиту от повторной выдачи: ${hasGuard ? 'да' : 'НЕТ'}`);
}