// Пробник цикла 5: i18n и NewGameDialog.
import { readFileSync } from 'node:fs';
const S = '/home/thomas/LivingCode/Projects/elemental-life/elemental-life-app/src/';

console.log('=== 1. detectSystemLocale: достижим ли цикл по full locale? ===');
{
  const supported = ['en', 'ru', 'es', 'de', 'zh', 'ja'];
  const detect = (lang) => {
    const primaryLang = lang.split('-')[0];
    if (supported.includes(primaryLang)) return primaryLang;
    for (const key of supported) if (lang.startsWith(key)) return key;
    return 'en';
  };
  for (const lang of ['ru-RU', 'zh-Hans-CN', 'de-AT', 'ja-JP', 'pt-BR', 'fr', 'es-419']) {
    console.log(`  navigator.language='${lang}' -> '${detect(lang)}'`);
  }
  console.log('  Цикл startsWith достижим? Проверяем: для любого lang, где');
  console.log('  lang.split("-")[0] не в списке, может ли lang.startsWith(key) быть true?');
  let reachable = [];
  // Полный перебор разумного пространства имён языков из ISO-639-1
  const iso = ['aa','ab','ae','af','ak','am','an','ar','as','av','ay','az','ba','be','bg','bh','bi','bm','bn','bo','br','bs','ca','ce','ch','co','cr','cs','cu','cv','cy','da','de','dv','dz','ee','el','en','eo','es','et','eu','fa','ff','fi','fj','fo','fr','fy','ga','gd','gl','gn','gu','gv','ha','he','hi','ho','hr','ht','hu','hy','hz','ia','id','ie','ig','ii','ik','io','is','it','iu','ja','jv','ka','kg','ki','kj','kk','kl','km','kn','ko','kr','ks','ku','kv','kw','ky','la','lb','lg','li','ln','lo','lt','lu','lv','mg','mh','mi','mk','ml','mn','mr','ms','mt','my','na','nb','nd','ne','ng','nl','nn','no','nr','nv','ny','oc','oj','om','or','os','pa','pi','pl','ps','pt','qu','rm','rn','ro','ru','rw','sa','sc','sd','se','sg','si','sk','sl','sm','sn','so','sq','sr','ss','st','su','sv','sw','ta','te','tg','th','ti','tk','tl','tn','to','tr','ts','tt','tw','ty','ug','uk','ur','uz','ve','vi','vo','wa','wo','xh','yi','yo','za','zh','zu'];
  for (const l of iso) {
    // primaryLang = l (без дефиса) -> если l не в supported, идём в цикл
    if (supported.includes(l)) continue;
    for (const key of supported) {
      if (l.startsWith(key)) reachable.push(`${l} startsWith '${key}' -> '${key}'`);
    }
  }
  console.log(`  Найдено языков, где цикл даёт не-'en': ${reachable.length} ${JSON.stringify(reachable.slice(0,10))}`);
  console.log(reachable.length === 0
    ? '  ВЫВОД: цикл НИКОГДА не меняет результат — мёртвый код (первый if всегда покрывает).'
    : '  ВЫВОД: цикл достижим.');
}

console.log('\n=== 2. setLocale: неизвестная локаль проглатывается молча ===');
{
  const src = readFileSync(S + 'i18n.ts', 'utf8');
  const setLocaleBody = src.slice(src.indexOf('export function setLocale'), src.indexOf('export function detectSystemLocale'));
  console.log(setLocaleBody.split('\n').map((l) => '  ' + l).join('\n'));
  console.log('  => setLocale("fr") не меняет локаль и НЕ сообщает об ошибке.');
  console.log('  => UI-переключатель языка откатился бы на прошлый язык без объяснения.');
}

console.log('\n=== 3. setLocale(\'RU\') — регистр ===');
{
  // detectSystemLocale отдаёт lowerCase, но ручной вызов setLocale из UI?
  const src = readFileSync(S + 'i18n.ts', 'utf8');
  const supported = ['en', 'ru', 'es', 'de', 'zh', 'ja'];
  console.log(`  translations['RU'] существует? ${supported.includes('RU')} -> setLocale('RU') проглотит молча`);
}

console.log('\n=== 4. NewGameDialog: состояние диалога ===');
{
  const src = readFileSync(S + 'components/NewGameDialog.tsx', 'utf8');
  const useState = [...src.matchAll(/useState<([^>]+)>\(([^)]*)\)/g)].map((m) => `${m[1]} = ${m[2]}`);
  console.log(`  useState: ${useState.join(' | ')}`);
  const hasReset = /setGeometry\('hex'\)|reset.*useState|\/\/ reset/i.test(src);
  console.log(`  есть сброс состояния при закрытии/открытии диалога: ${hasReset}`);
}

console.log('\n=== 5. PuzzleOverlay: счётчик капель ===');
{
  const src = readFileSync(S + 'components/PuzzleOverlay.tsx', 'utf8');
  console.log('  --- файл ---');
  console.log(src.split('\n').map((l) => '  ' + l).join('\n').slice(0, 2200));
}