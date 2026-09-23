/**
 * ЭЛЕМЕНТАРНАЯ ЖИЗНЬ — игровое ядро (platform-agnostic engine)
 *
 * Этот файл НЕ зависит от React, DOM, Canvas или какого-либо UI фреймворка.
 * Он содержит только чистую логику клеточного автомата и может быть
 * использован как есть в любой среде, которая поддерживает ES-модули
 * (React Native, Capacitor/WebView, Node.js для тестов, Web Worker, и т.д.)
 *
 * Клеточный автомат на основе "Жизни" Конвея, расширенный четырьмя
 * стихиями: огонь, вода, воздух (пар), земля. Поддерживает ДВЕ геометрии
 * сетки, выбираемые при старте новой игры:
 *   - "hex"    — гексагональная сетка, 6 равноправных соседей
 *   - "square" — квадратная сетка, 8 соседей (окружение Мура, с диагоналями)
 * Правила переходов одни и те же (общий код в stepField), но числовые
 * пороги (birthCount, lifeOverpopulation и т.д.) откалиброваны раздельно
 * под каждую геометрию — см. GEOMETRY_PRESETS ниже. Калибровка нужна,
 * потому что при 8 соседях те же правила статистически срабатывают
 * иначе, чем при 6 — это было проверено headless-тестами, прямой перенос
 * гекс-параметров на квадрат даёт совсем другой (более \"цветущий\") баланс.
 *
 * СОСТОЯНИЯ КЛЕТКИ:
 *   empty  — пустота
 *   life   — живая клетка
 *   fire   — огонь (хранит счётчик \"возраста\" 0..1, гаснет на 2-й итерации)
 *   water  — вода
 *   earth  — земля / берег
 *   steam  — пар (испарившаяся вода, через 1 итерацию выпадает дождём)
 *   ash    — пепел / опалённая пустота (ждёт воду 2 итерации, чтобы стать землёй)
 *
 * ЗАКОН СОХРАНЕНИЯ ВОДЫ (инвариант, проверенный headless-тестами):
 *   total(water) + total(steam) = const на протяжении всей симуляции,
 *   независимо от выбранной геометрии. Вода не создаётся и не
 *   уничтожается — только меняет агрегатное состояние (water -> steam
 *   при тушении огня жизнью) или физически перемещается (перелив воды
 *   в пустоту/пепел, или розлив игроком в puzzle-режиме).
 *
 * РЕЖИМ ГОЛОВОЛОМКИ (\"Полив пустоты\"):
 *   Игрок заливает клетки empty/ash водой (мгновенно, тратит \"каплю\" из лимита).
 *   Мир продолжает тикать сам по себе. Победа — когда пустота/пепел не
 *   задерживаются на поле дольше WIN_MAX_AGE тиков подряд, и это держится
 *   стабильно WIN_STABLE_TICKS тиков (экосистема \"сама себя исцеляет\).
 */

import { buildInitialField, stepField, GEOMETRY_PRESETS } from './src/engine.js';

const geometryKey = 'hex';
const presetKey = 'classic_balanced';
const radius = 30; // for hex, side=30 -> radius=29? Actually, in the engine, radius = side - 1 for hex.
// But the preset doesn't specify radius. We use the same as in the smoke test: 30 for hex gives 2611 cells.
const seed = 12345;
const params = GEOMETRY_PRESETS[geometryKey][presetKey].params;

const field = buildInitialField(geometryKey, radius, seed);

console.log(`Profiling ${geometryKey}/${presetKey} with field size: ${radius*2+1} (approx) ...`);

const start = Date.now();
let current = field;
for (let i = 0; i < 500; i++) {
  current = stepField(geometryKey, current, radius, params, () => Math.random());
}
const end = Date.now();

console.log(`Time for 500 ticks: ${end - start} ms`);
console.log(`Average per tick: ${(end - start) / 500} ms`);