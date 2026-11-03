// Пробник цикла 4: i18n, soundSystem, crypto — кандидаты дефектов.
import { readFileSync } from 'node:fs';
const S = '/home/thomas/LivingCode/Projects/elemental-life/elemental-life-app/src/';

console.log('=== 1. crypto.validateWords: регулярка с кириллицей, но длина в UTF-16 ===');
{
  const { validateWords } = await import('data:text/javascript,' +
    encodeURIComponent(`
      export function validateWords(words) {
        if (words.length < 3) return 'Enter at least 3 words';
        if (words.length > 5) return 'Maximum 5 words';
        for (const w of words) {
          if (w.length > 16) return 'Too long: ' + w;
          if (!/^[a-zа-яё]+$/.test(w)) return 'Bad: ' + w;
        }
        return null;
      }`));
  const cases = [
    ['три латинских слова', ['alpha', 'beta', 'gamma']],
    ['три русских слова', ['привет', 'мир', 'тест']],
    ['слово из 9 кириллических букв (18 UTF-16)', ['абракадабра', 'мир', 'тест']],
    ['слово ровно 16 латинских', ['abcdefghijklmnop', 'a', 'b']],
    ['слово ровно 8 кириллических (16 UTF-16)', ['абвгдеёж', 'a', 'b']],
    ['ё в начале', ['ёжик', 'мир', 'тест']],
  ];
  for (const [name, words] of cases) {
    console.log(`  ${name.padEnd(46)} -> ${JSON.stringify(validateWords(words))}`);
  }
}

console.log('\n=== 2. crypto: parseWords не фильтрует, validateWords считает по кодовым точкам ===');
{
  // wordsToEntropy: phrase.join(' ').trim().toLowerCase().replace(/\s+/g,' ')
  // а parseWords НЕ убирает лишние пробелы так же -> разная фраза = другой энтропии?
  const parseWords = (input) => input.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const wordsToEntropy = (words) => words.join(' ').trim().toLowerCase().replace(/\s+/g, ' ');
  console.log(`  parseWords('  A   b  c ') -> ${JSON.stringify(parseWords('  A   b  c '))}`);
  console.log(`  wordsToEntropy(parseWords(...)) -> ${JSON.stringify(wordsToEntropy(parseWords('  A   b  c ')))}`);
  console.log(`  wordsToEntropy(['a','b','c'])     -> ${JSON.stringify(wordsToEntropy(['a', 'b', 'c']))}`);
  console.log(`  совпадают: ${wordsToEntropy(parseWords('  A   b  c ')) === wordsToEntropy(['a','b','c'])}`);
}

console.log('\n=== 3. entropyToGameSeed: старшие биты и распределение ===');
{
  const wte = (phrase) => {
    // sha256 не подключаем — считаем через crypto
    return new Uint8Array(require('node:crypto').createHash('sha256').update(phrase).digest());
  };
  const { createRequire } = await import('node:module');
  const require = createRequire(import.meta.url);
  const entropyToGameSeed = (e) => {
    let v = 0;
    for (let i = 0; i < 4; i++) v = (v << 8) | e[i];
    return (v >>> 0) & 0x7fffffff;
  };
  // Смотрим: значение 0xFFFFFFFF -> & 0x7fffffff = 0x7fffffff, ок.
  // Но сколько бит реально используется? 31 бит из 256.
  const seeds = ['a b c', 'a b d', 'test words here', 'привет мир тест'].map(
    (p) => entropyToGameSeed(wte(p)));
  console.log(`  сиды: ${seeds.join(', ')}`);
  console.log(`  уникальны: ${new Set(seeds).size}/4`);
  // Проверка: 0x80000000 & 0x7fffffff = 0 -> зерно 2147483648 и 0 неразличимы?
  console.log(`  0x80000000 & 0x7fffffff = ${0x80000000 & 0x7fffffff} (старший бит отбрасывается)`);
  console.log(`  0xFFFFFFFF & 0x7fffffff = ${0xffffffff & 0x7fffffff}`);
}

console.log('\n=== 4. soundSystem: незакрытые таймеры / громкость вне [0,1] ===');
{
  const src = readFileSync(S + 'sound/soundSystem.ts', 'utf8');
  const volWrites = [...src.matchAll(/volume\s*=\s*([^;\n]+)/g)].map((m) => m[1].trim());
  console.log(`  присваиваний volume: ${volWrites.length}`);
  const unguarded = volWrites.filter((v) => !/Math\.(min|max|clamp)|Math\.abs/.test(v));
  console.log(`  БЕЗ ограничения диапазона [0,1]: ${unguarded.length}`);
  unguarded.slice(0, 8).forEach((v) => console.log(`    volume = ${v}`));
  const setInterval = (src.match(/setInterval/g) || []).length;
  const clearInterval = (src.match(/clearInterval/g) || []).length;
  console.log(`  setInterval: ${setInterval}, clearInterval: ${clearInterval}`);
  const setTimeout = (src.match(/setTimeout/g) || []).length;
  const clearTimeout = (src.match(/clearTimeout/g) || []).length;
  console.log(`  setTimeout: ${setTimeout}, clearTimeout: ${clearTimeout}`);
}

console.log('\n=== 5. i18n: покрытие ключей ===');
{
  const src = readFileSync(S + 'i18n.ts', 'utf8');
  const langs = [...src.matchAll(/^\s*(ru|en|de|fr|es|zh|ja|ko|pt|it):\s*{/gm)].map((m) => m[1]);
  console.log(`  языков в i18n.ts: ${langs.join(', ') || 'не найдены'}`);
  const tCalls = new Set();
  for (const f of ['App.tsx', 'components/WalletScreen.tsx', 'components/SettingsModal.tsx']) {
    const c = readFileSync(S + f, 'utf8');
    for (const m of c.matchAll(/\bt\(\s*'([a-zA-Z0-9_.]+)'/g)) tCalls.add(m[1]);
  }
  console.log(`  строковых ключей t('...') в 3 файлах: ${tCalls.size}`);
  const missing = [...tCalls].filter((k) => !src.includes(k));
  console.log(`  отсутствуют в i18n.ts: ${missing.length} ${JSON.stringify(missing.slice(0, 10))}`);
}