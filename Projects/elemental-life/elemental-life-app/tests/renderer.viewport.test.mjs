// Юнит-тест viewport-математики GridRenderer (Point 9, Protocol of Living Code).
//
// Тестирует НАСТОЯЩИЙ src/renderer/GridRenderer.ts: файл компилируется tsc
// в scratch-каталог и подключается через require(). DOM-зависимости шимятся.
//
// Проверяемое:
//  1. Инвариант якоря зума: world-точка под курсором остаётся под курсором
//     при zoomBy (модель viewport — CSS-пиксели, см. заголовок GridRenderer.ts).
//  2. Регресс-кейс dpr-бага: передача device-пикселей (CSS * dpr) в zoomBy
//     смещает якорь зума при dpr>1 — причина «jitter or lost position»
//     на HiDPI-устройствах (Android). Баг был в pinch/wheel до фикса 2026-09-24.
//  3. Реальный wheel-обработчик (через dispatch события) держит якорь в CSS px.
//  4. panBy добавляет CSS-пиксели к viewport.x/y.
//  5. Clamp зума 0.15..4; centerGrid; getViewport возвращает копию.

import { execFileSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const require = createRequire(import.meta.url);

// ---------- Шимы DOM (до подключения скомпилированного модуля) ----------
globalThis.window = {
  devicePixelRatio: 2.0, // HiDPI — как реальный Android
  addEventListener: () => {},
  removeEventListener: () => {},
};
globalThis.document = { addEventListener: () => {}, removeEventListener: () => {} };
globalThis.ResizeObserver = class {
  constructor(cb) { this.cb = cb; }
  observe() {} disconnect() {} unobserve() {}
};

// ---------- Компиляция реального GridRenderer.ts через tsc ----------
// tsc с file-аргументами конфликтует с корневым tsconfig.json (TS5112),
// поэтому компилируем в scratch-копии: cp src → scratch/src, компилируем там,
// забираем out/renderer/GridRenderer.js. Кэшируем результат рядом с тестом,
// чтобы не пересобирать при каждом запуске ( инвалидация по mtime GridRenderer.ts).
import { statSync, existsSync, mkdirSync, cpSync } from 'node:fs';

const SRC_TS = join(ROOT, 'src/renderer/GridRenderer.ts');
const CACHE_DIR = join(__dirname, '.tsc-cache');
const CACHED_JS = join(CACHE_DIR, 'renderer', 'GridRenderer.js');
const CACHED_ENGINE_JS = join(CACHE_DIR, 'engine', 'engine.js');
const srcMtime = statSync(SRC_TS).mtimeMs;
const cacheValid = existsSync(CACHED_JS) && existsSync(CACHED_ENGINE_JS) &&
  existsSync(join(CACHE_DIR, 'package.json')) &&
  statSync(CACHED_JS).mtimeMs >= srcMtime;

if (!cacheValid) {
  const scratch = mkdtempSync(join(tmpdir(), 'gr-viewport-'));
  try {
    mkdirSync(join(scratch, 'src'), { recursive: true });
    cpSync(join(ROOT, 'src'), join(scratch, 'src'), { recursive: true });
    let tscOut = '';
    try {
      tscOut = execFileSync('node', [
        join(ROOT, 'node_modules/typescript/bin/tsc'),
        'src/renderer/GridRenderer.ts',
        '--target', 'es2020',
        '--module', 'commonjs',
        '--lib', 'es2020,dom',
        '--skipLibCheck',
        '--outDir', join(scratch, 'out'),
      ], { cwd: scratch, timeout: 120000 });
    } catch (e) {
      console.error('tsc failed:\n' + (e.stdout ? String(e.stdout) : '') + (e.stderr ? String(e.stderr) : '') + (e.message || ''));
      throw e;
    }
    rmSync(CACHE_DIR, { recursive: true, force: true });
    // Скомпилированный CJS-код живёт в дереве с "type": "module" — без этого
    // маркера Node трактует .js как ESM и падает на `exports`.
    mkdirSync(CACHE_DIR, { recursive: true });
    writeFileSync(join(CACHE_DIR, 'package.json'), '{"type":"commonjs"}');
    mkdirSync(join(CACHE_DIR, 'renderer'), { recursive: true });
    mkdirSync(join(CACHE_DIR, 'engine'), { recursive: true });
    cpSync(join(scratch, 'out/renderer'), join(CACHE_DIR, 'renderer'), { recursive: true });
    cpSync(join(scratch, 'out/engine'), join(CACHE_DIR, 'engine'), { recursive: true });
  } finally {
    try { rmSync(scratch, { recursive: true, force: true }); } catch {}
  }
}

// Тест запускается из CJS require(); engine.ts не импортирует ничего внешнего,
// поэтому CJS-путь require работает напрямую.
const GridRenderer = require(CACHED_JS);

// ---------- Fake canvas ----------
function makeFakeCanvas(cssSize = { width: 800, height: 600 }) {
  const listeners = {};
  const ctxStub = new Proxy({}, { get: () => () => {} });
  const fakeCanvas = {
    width: 0, height: 0, style: {},
    getContext: () => ctxStub,
    addEventListener: (n, f) => { (listeners[n] = listeners[n] || []).push(f); },
    removeEventListener: () => {},
    setPointerCapture: () => {},
    releasePointerCapture: () => {},
    parentElement: { getBoundingClientRect: () => ({ width: cssSize.width, height: cssSize.height, left: 0, top: 0 }) },
    getBoundingClientRect: () => ({ left: 0, top: 0, width: cssSize.width, height: cssSize.height }),
  };
  return { fakeCanvas, listeners };
}

// ---------- Мини-раннер ----------
let passed = 0, failed = 0;
const failures = [];
function assert(cond, msg) {
  if (cond) { passed++; }
  else { failed++; failures.push(msg); console.error(`FAIL: ${msg}`); }
}
function near(a, b, eps = 1e-9) { return Math.abs(a - b) < eps; }

const { GridRenderer: GR } = GridRenderer;

// 1. Конструкция + setViewport/getViewport
{
  const { fakeCanvas } = makeFakeCanvas();
  const r = new GR(fakeCanvas, 'hex', 12, 22);
  r.setViewport({ x: 100, y: 80, zoom: 1.5, width: 800, height: 600 });
  const vp = r.getViewport();
  assert(vp.x === 100 && vp.y === 80 && vp.zoom === 1.5,
    `construction + setViewport/getViewport, got ${JSON.stringify(vp)}`);
}

// 2. Инвариант якоря зума (CSS px): world под курсором неподвижен
{
  const { fakeCanvas } = makeFakeCanvas();
  const r = new GR(fakeCanvas, 'hex', 2, 22);
  r.setViewport({ x: 400, y: 300, zoom: 1, width: 800, height: 600 });
  const cx = 200, cy = 150;
  const wxBefore = (cx - 400) / 1, wyBefore = (cy - 300) / 1;
  r.zoomBy(1.5, cx, cy);
  const vp = r.getViewport();
  const wxAfter = (cx - vp.x) / vp.zoom, wyAfter = (cy - vp.y) / vp.zoom;
  assert(near(wxAfter, wxBefore) && near(wyAfter, wyBefore),
    `zoom anchor invariant: before=(${wxBefore},${wyBefore}) after=(${wxAfter},${wyAfter})`);
}

// 3. Регресс-кейс dpr-бага: device-px (CSS*dpr) в zoomBy смещает якорь
{
  const { fakeCanvas } = makeFakeCanvas();
  const r = new GR(fakeCanvas, 'hex', 2, 22);
  r.setViewport({ x: 400, y: 300, zoom: 1, width: 800, height: 600 });
  const cssX = 200, cssY = 150;
  const wxBefore = (cssX - 400) / 1, wyBefore = (cssY - 300) / 1;
  // Старое (багованное) поведение pinch/wheel: умножение на dpr (=2)
  r.zoomBy(1.5, cssX * 2, cssY * 2);
  const vp = r.getViewport();
  const wxAfter = (cssX - vp.x) / vp.zoom, wyAfter = (cssY - vp.y) / vp.zoom;
  assert(!(near(wxAfter, wxBefore) && near(wyAfter, wyBefore)),
    `REGRESSION: device-px anchor shifts world under cursor (dpr=2): before=(${wxBefore},${wyBefore}) after=(${wxAfter},${wyAfter})`);
  // И величина смещения существенна (не численный шум)
  const shift = Math.hypot(wxAfter - wxBefore, wyAfter - wyBefore);
  assert(shift > 50, `device-px anchor shift is significant: ${shift.toFixed(1)} world px at zoom ${vp.zoom}`);
}

// 4. Реальный wheel-обработчик: dispatch события держит якорь в CSS px
{
  const { fakeCanvas, listeners } = makeFakeCanvas();
  const r = new GR(fakeCanvas, 'hex', 2, 22);
  r.setViewport({ x: 400, y: 300, zoom: 1, width: 800, height: 600 });
  const wheel = (listeners['wheel'] || [])[0];
  assert(typeof wheel === 'function', 'wheel listener bound to canvas');
  const cssX = 200, cssY = 150;
  const wxBefore = (cssX - 400) / 1, wyBefore = (cssY - 300) / 1;
  wheel({ preventDefault: () => {}, clientX: cssX, clientY: cssY, deltaY: -100 }); // zoom in 1.15
  const vp = r.getViewport();
  const wxAfter = (cssX - vp.x) / vp.zoom, wyAfter = (cssY - vp.y) / vp.zoom;
  assert(near(wxAfter, wxBefore, 1e-6) && near(wyAfter, wyBefore, 1e-6),
    `wheel handler keeps CSS-px anchor: before=(${wxBefore},${wyBefore}) after=(${wxAfter},${wyAfter})`);
  // dpr не должен участвовать: viewport.zoom изменился, якорь цел
  assert(near(vp.zoom, 1.15, 1e-9), `wheel zoom factor applied: zoom=${vp.zoom}`);
}

// 5. panBy добавляет CSS-пиксели
{
  const { fakeCanvas } = makeFakeCanvas();
  const r = new GR(fakeCanvas, 'hex', 2, 22);
  r.setViewport({ x: 100, y: 100, zoom: 2, width: 800, height: 600 });
  r.panBy(50, 0);
  const vp = r.getViewport();
  assert(near(vp.x, 150) && near(vp.y, 100), `panBy adds CSS px: got (${vp.x},${vp.y})`);
}

// 6. Clamp зума 0.15..4
{
  const { fakeCanvas } = makeFakeCanvas();
  const r = new GR(fakeCanvas, 'hex', 2, 22);
  r.setViewport({ x: 400, y: 300, zoom: 3.9, width: 800, height: 600 });
  r.zoomBy(2, 400, 300);
  assert(near(r.getViewport().zoom, 4), `zoom clamped to max 4: got ${r.getViewport().zoom}`);
  r.setViewport({ x: 400, y: 300, zoom: 0.2, width: 800, height: 600 });
  r.zoomBy(0.125, 400, 300);
  assert(near(r.getViewport().zoom, 0.15), `zoom clamped to min 0.15: got ${r.getViewport().zoom}`);
}

// 7. centerGrid ставит world(0,0) в центр (CSS px)
{
  const { fakeCanvas } = makeFakeCanvas();
  const r = new GR(fakeCanvas, 'hex', 2, 22);
  r.setViewport({ x: 10, y: 20, zoom: 1.5, width: 800, height: 600 });
  r.centerGrid();
  const vp = r.getViewport();
  assert(near(vp.x, 400) && near(vp.y, 300), `centerGrid: got (${vp.x},${vp.y})`);
  assert(near(vp.zoom, 1.5), `centerGrid keeps zoom: got ${vp.zoom}`);
}

// 8. resetView центрирует и вписывает поле
{
  const { fakeCanvas } = makeFakeCanvas();
  const r = new GR(fakeCanvas, 'hex', 2, 22);
  r.setViewport({ x: 10, y: 20, zoom: 4, width: 800, height: 600 });
  r.resetView();
  const vp = r.getViewport();
  assert(near(vp.x, 400) && near(vp.y, 300), `resetView centers: got (${vp.x},${vp.y})`);
  assert(vp.zoom >= 0.15 && vp.zoom <= 4, `resetView zoom in clamp: got ${vp.zoom}`);
}

// 9. getViewport возвращает копию (изоляция внутреннего состояния)
{
  const { fakeCanvas } = makeFakeCanvas();
  const r = new GR(fakeCanvas, 'hex', 2, 22);
  r.setViewport({ x: 400, y: 300, zoom: 1, width: 800, height: 600 });
  const vp1 = r.getViewport();
  vp1.x = -999;
  const vp2 = r.getViewport();
  assert(vp2.x === 400, `getViewport returns a copy: got x=${vp2.x}`);
}

// ---------- Итог ----------
console.log(`\nviewport math tests: ${passed} passed, ${failed} failed`);
if (failed > 0) {
  console.error('FAILURES:\n' + failures.map(f => '  - ' + f).join('\n'));
  process.exit(1);
}
