// Тесты чистых функций форматирования + консистентность invoke() vs generate_handler!.
// Запуск: npm test  (node --test tests/)
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { formatUptime, formatBytes, statusClass } from '../src/format.js';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

test('formatUptime: секунды/минуты/часы/дни', () => {
  assert.equal(formatUptime(0), '0 с');
  assert.equal(formatUptime(45_000), '45 с');
  assert.equal(formatUptime(90_000), '1 мин 30 с');
  assert.equal(formatUptime(3_600_000), '1 ч 0 мин');
  assert.equal(formatUptime(90_000_000), '1 д 1 ч');
  assert.equal(formatUptime(null), '—');
  assert.equal(formatUptime(-5), '—');
});

test('formatBytes: единицы и границы', () => {
  assert.equal(formatBytes(0), '0 Б');
  assert.equal(formatBytes(512), '512 Б');
  assert.equal(formatBytes(2048), '2.0 КБ');
  assert.equal(formatBytes(5 * 1024 * 1024), '5.0 МБ');
  assert.equal(formatBytes(3 * 1024 ** 3), '3.0 ГБ');
  assert.equal(formatBytes(null), '—');
});

test('statusClass: известные статусы', () => {
  assert.equal(statusClass('Running'), 'status-running');
  assert.equal(statusClass('Unhealthy'), 'status-unhealthy');
  assert.equal(statusClass('Starting'), 'status-starting');
  assert.equal(statusClass('Restarting'), 'status-starting');
  assert.equal(statusClass('Stopped'), 'status-stopped');
  assert.equal(statusClass('whatever'), 'status-stopped');
});

test('каждый invoke() в src/ зарегистрирован в generate_handler! (src-tauri/main.rs)', () => {
  const mainRs = readFileSync(path.join(root, 'src-tauri/main.rs'), 'utf8');
  const m = mainRs.match(/generate_handler!\[([\s\S]*?)\]/);
  assert.ok(m, 'generate_handler! не найден в main.rs');
  const registered = new Set([...m[1].matchAll(/(\w+)/g)].map((x) => x[1]));

  const viewFiles = readdirSync(path.join(root, 'src/views'))
    .filter((f) => f.endsWith('.js'))
    .map((f) => path.join('src/views', f));
  const sources = [path.join('src', 'main.js'), ...viewFiles];

  for (const rel of sources) {
    const src = readFileSync(path.join(root, rel), 'utf8');
    for (const im of src.matchAll(/invoke\(\s*['"]([\w-]+)['"]/g)) {
      assert.ok(
        registered.has(im[1]),
        `${rel}: invoke('${im[1]}') не зарегистрирован в generate_handler!`,
      );
    }
  }
});

test('все вкладки из main.js имеют pane в index.html', () => {
  const mainJs = readFileSync(path.join(root, 'src/main.js'), 'utf8');
  const html = readFileSync(path.join(root, 'src/index.html'), 'utf8');
  const tabs = [...mainJs.matchAll(/TABS = \[([\s\S]*?)\]/g)][0][1].matchAll(/['"](\w+)['"]/g);
  for (const t of tabs) {
    assert.ok(html.includes(`id="pane-${t[1]}"`), `нет pane-${t[1]} в index.html`);
    assert.ok(html.includes(`data-tab="${t[1]}"`), `нет tab-btn ${t[1]} в index.html`);
  }
});
