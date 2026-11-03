// Пробник цикла 6: GridRenderer — жесты (pan/pinch/wheel).
import { execFileSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, cpSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = '/home/thomas/LivingCode/Projects/elemental-life/elemental-life-app';
const require = createRequire(import.meta.url);

globalThis.window = { devicePixelRatio: 2, addEventListener(){}, removeEventListener(){} };
globalThis.document = { addEventListener(){}, removeEventListener(){} };
globalThis.ResizeObserver = class { constructor(cb){this.cb=cb;} observe(){} disconnect(){} unobserve(){} };

// Минимальная шима canvas/DOM
class FakeCtx {
  setTransform(){} clearRect(){} beginPath(){} moveTo(){} lineTo(){} closePath(){} fill(){} fillRect(){}
}
function makeCanvas(rect = { left: 0, top: 0, width: 400, height: 300 }) {
  const listeners = {};
  return {
    width: 0, height: 0, style: {},
    parentElement: { getBoundingClientRect: () => rect },
    getContext: () => new FakeCtx(),
    getBoundingClientRect: () => rect,
    setPointerCapture(){}, releasePointerCapture(){},
    addEventListener: (t, f) => { (listeners[t] ||= []).push(f); },
    removeEventListener: (t, f) => { listeners[t] = (listeners[t]||[]).filter(x => x !== f); },
    fire: (t, ev) => (listeners[t]||[]).forEach(f => f(ev)),
    listeners,
  };
}

const scratch = mkdtempSync(join(tmpdir(), 'el-grid-'));
mkdirSync(join(scratch, 'src'), { recursive: true });
cpSync(join(ROOT, 'src'), join(scratch, 'src'), { recursive: true });
execFileSync('node', [join(ROOT, 'node_modules/typescript/bin/tsc'),
  'src/renderer/GridRenderer.ts', '--target','es2020','--module','commonjs',
  '--lib','es2020,dom','--skipLibCheck'], { cwd: scratch, stdio: 'pipe' });
const { GridRenderer } = require(join(scratch, 'src/renderer/GridRenderer.js'));

const ev = (x, y, id = 1) => ({ clientX: x, clientY: y, pointerId: id, preventDefault(){} });

console.log('=== Дефект A: после пинча одним пальцем НЕЛЬЗЯ панорамировать ===');
{
  const canvas = makeCanvas();
  const r = new GridRenderer(canvas, 'hex', 10, 9);
  r.setViewport({ x: 0, y: 0, zoom: 1, width: 400, height: 300 });
  const before = r.getViewport();

  // Пинч двумя пальцами: вниз, move, один палец отпущен.
  canvas.fire('pointerdown', ev(100, 100, 1));
  canvas.fire('pointerdown', ev(200, 100, 2));
  canvas.fire('pointermove', ev(120, 100, 2));   // растоптали
  const afterPinch = r.getViewport();
  console.log(`  зум после пинча: ${before.zoom.toFixed(4)} -> ${afterPinch.zoom.toFixed(4)}`);
  console.log(`  пан после пинча:  x ${before.x.toFixed(2)} -> ${afterPinch.x.toFixed(2)}`);

  canvas.fire('pointerup', ev(120, 100, 2));    // остался один палец (id=1)

  // Теперь двигаем оставшийся палец на 60px вправо.
  const v0 = r.getViewport();
  canvas.fire('pointermove', ev(160, 100, 1));
  const v1 = r.getViewport();
  const panned = (v1.x - v0.x) !== 0 || (v1.y - v0.y) !== 0;
  console.log(`  движение одним пальцем после пинча: dx=${(v1.x - v0.x).toFixed(3)}`);
  console.log(`  ВЫВОД: ${panned ? 'панорамирование работает' : 'ДЕФЕКТ — палец двигается, поле не едет (isPanning не восстановлен)'}`);
}

console.log('\n=== Дефект B: два пальца -> один -> панорамирование (контроль) ===');
{
  const canvas = makeCanvas();
  const r = new GridRenderer(canvas, 'hex', 10, 9);
  r.setViewport({ x: 0, y: 0, zoom: 1, width: 400, height: 300 });
  canvas.fire('pointerdown', ev(100, 100, 1));
  const v0 = r.getViewport();
  canvas.fire('pointermove', ev(150, 130, 1));
  const v1 = r.getViewport();
  console.log(`  одиночный палец БЕЗ пинча: dx=${(v1.x - v0.x).toFixed(3)} dy=${(v1.y - v0.y).toFixed(3)}`);
  console.log(`  ВЫВОД: ${(v1.x !== v0.x) ? 'панорамирование работает' : 'ДЕФЕКТ'}`);
}

console.log('\n=== Дефект C: три пальца, отпускаем один ===');
{
  const canvas = makeCanvas();
  const r = new GridRenderer(canvas, 'hex', 10, 9);
  r.setViewport({ x: 0, y: 0, zoom: 1, width: 400, height: 300 });
  canvas.fire('pointerdown', ev(100, 100, 1));
  canvas.fire('pointerdown', ev(200, 100, 2));
  canvas.fire('pointerdown', ev(300, 100, 3));
  canvas.fire('pointerup', ev(200, 100, 2));
  canvas.fire('pointerup', ev(300, 100, 3));
  // остался палец 1, isPanning должен стать true
  const v0 = r.getViewport();
  canvas.fire('pointermove', ev(140, 100, 1));
  const v1 = r.getViewport();
  console.log(`  после 3 пальцев и отпускания двух: dx=${(v1.x - v0.x).toFixed(3)}`);
  console.log(`  ВЫВОД: ${v1.x !== v0.x ? 'работает' : 'ДЕФЕКТ — после мультитача одним пальцем поле не едет'}`);
}

console.log('\n=== Дефект D: zoomBy с некорректным factor ===');
{
  const canvas = makeCanvas();
  const r = new GridRenderer(canvas, 'hex', 10, 9);
  r.setViewport({ x: 0, y: 0, zoom: 1, width: 400, height: 300 });
  for (const f of [0, -1, NaN, Infinity, undefined]) {
    const v0 = r.getViewport();
    try {
      r.zoomBy(f, 200, 150);
      const v1 = r.getViewport();
      const bad = !Number.isFinite(v1.zoom) || !Number.isFinite(v1.x) || !Number.isFinite(v1.y);
      console.log(`  zoomBy(${String(f)}): zoom ${v0.zoom} -> ${v1.zoom}, x=${v1.x}, y=${v1.y} ${bad ? ' <-- NaN/Inf!' : ''}`);
    } catch (e) {
      console.log(`  zoomBy(${String(f)}): исключение ${e.constructor.name}`);
    }
  }
}

console.log('\n=== Дефект E: render() при destroy() ===');
{
  const canvas = makeCanvas();
  const r = new GridRenderer(canvas, 'hex', 10, 9);
  r.render();
  r.destroy();
  try {
    r.render();
    console.log('  render() после destroy(): отработал (слушатели сняты, но рендер жив) — наблюдение');
  } catch (e) {
    console.log(`  render() после destroy(): ${e.constructor.name}: ${e.message}`);
  }
  canvas.fire('pointermove', ev(500, 500, 1));
  console.log('  события после destroy(): не должны обрабатываться');
}

console.log('\n=== Дефект F: getViewport возвращает копию? ===');
{
  const canvas = makeCanvas();
  const r = new GridRenderer(canvas, 'hex', 10, 9);
  const v = r.getViewport();
  v.zoom = 999;
  console.log(`  после мутации возвращённого объекта внутренний зум: ${r.getViewport().zoom} (должен быть исходным)`);
}