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
 * гекс-параметров на квадрат даёт совсем другой (более "цветущий") баланс.
 *
 * СОСТОЯНИЯ КЛЕТКИ:
 *   empty  — пустота
 *   life   — живая клетка
 *   fire   — огонь (хранит счётчик "возраста" 0..1, гаснет на 2-й итерации)
 *   water  — вода
 *   earth  — земля / берег
 *   steam  — пар (испарившаяся вода, через 1 итерацию выпадает дождём)
 *   ash    — пепел (выгоревшая клетка)
 *
 * ЗАКОН СОХРАНЕНИЯ ВОДЫ (инвариант, проверенный headless-тестами):
 *   total(water) + total(steam) = const на протяжении всей симуляции,
 *   независимо от выбранной геометрии. Вода не создаётся и не
 *   уничтожается — только меняет агрегатное состояние (water -> steam
 *   при тушении огня жизнью) или физически перемещается (перелив воды
 *   в пустоту, или розлив игроком в puzzle-режиме).
 *
 *  РЕЖИМ ГОЛОВОЛОМКИ ("Полив пустоты"):
 *   Игрок заливает клетки empty водой (мгновенно, тратит "каплю" из лимита).
 *   Мир продолжает тикать сам по себе. Победа — когда пустота не
 *   задерживается на поле дольше WIN_MAX_AGE тиков подряд, и это держится
 *   стабильно WIN_STABLE_TICKS тиков (экосистема "сама себя исцеляет").
 */

// ---------- Геометрии сетки: гекс (6 соседей) и квадрат (8 соседей) ----------

export type GeometryKey = 'hex' | 'square';
export type StateKey = 'empty' | 'life' | 'fire' | 'water' | 'earth' | 'steam' | 'ash';
export type PresetKey = 'classic_balanced' | 'fire_storm' | 'water_world' | 'desert_drought' | 'chaos';

export interface CellData {
  state: StateKey;
  age: number;
  wetStreak?: number;
  flowTicks?: number;
}

export interface Params {
  fireSpreadChance: number;
  overpopulationIgniteTicks: number;
  lightningChance: number;
  survMin: number;
  birthCount: number;
  lifeOverpopulation: number;
  earthDryoutChance: number;
  earthDryoutMinAge: number;
  steamRainTicks: number;
  waterOverflowEnabled: boolean;
}

export interface Preset {
  label: string;
  description: string;
  params: Params;
}

export interface Level {
  id: number;
  label: string;
  waterDensity: number;
  lifeDensity: number;
  earthDensity: number;
  droplets: number;
}

export interface WaterStats {
  water: number;
  steam: number;
  total: number;
}

const HEX_DIRS: [number, number][] = [
  [+1, 0], [+1, -1], [0, -1],
  [-1, 0], [-1, +1], [0, +1],
];

const SQUARE_DIRS: [number, number][] = [
  [+1, 0], [+1, +1], [0, +1], [-1, +1],
  [-1, 0], [-1, -1], [0, -1], [+1, -1],
];

function makeHexagonalGridImpl(radius: number): { q: number; r: number }[] {
  const cells: { q: number; r: number }[] = [];
  for (let q = -radius; q <= radius; q++) {
    const rMin = Math.max(-radius, -q - radius);
    const rMax = Math.min(radius, -q + radius);
    for (let r = rMin; r <= rMax; r++) {
      cells.push({ q, r });
    }
  }
  return cells;
}

function makeSquareGridImpl(radius: number): { q: number; r: number }[] {
  const cells: { q: number; r: number }[] = [];
  for (let q = -radius; q <= radius; q++) {
    for (let r = -radius; r <= radius; r++) {
      cells.push({ q, r });
    }
  }
  return cells;
}

function hexGridCellCountImpl(side: number): number {
  const R = side - 1;
  return 3 * R * (R + 1) + 1;
}

function squareGridCellCountImpl(side: number): number {
  return side * side;
}

const GEOMETRIES: Record<GeometryKey, {
  dirs: [number, number][];
  fullNeighborCount: number;
  makeGrid: (radius: number) => { q: number; r: number }[];
  cellCount: (side: number) => number;
  radiusFromSide: (side: number) => number;
}> = {
  hex: {
    dirs: HEX_DIRS,
    fullNeighborCount: 6,
    makeGrid: makeHexagonalGridImpl,
    cellCount: hexGridCellCountImpl,
    radiusFromSide: (side: number) => side - 1,
  },
  square: {
    dirs: SQUARE_DIRS,
    fullNeighborCount: 8,
    makeGrid: makeSquareGridImpl,
    cellCount: squareGridCellCountImpl,
    radiusFromSide: (side: number) => Math.floor((side - 1) / 2),
  },
};

function neighborsOf(geometryKey: GeometryKey, q: number, r: number): [number, number][] {
  const dirs = GEOMETRIES[geometryKey].dirs;
  return dirs.map(([dq, dr]) => [q + dq, r + dr]);
}

function makeGrid(geometryKey: GeometryKey, radius: number): { q: number; r: number }[] {
  return GEOMETRIES[geometryKey].makeGrid(radius);
}

function gridCellCount(geometryKey: GeometryKey, side: number): number {
  return GEOMETRIES[geometryKey].cellCount(side);
}

function key(q: number, r: number): string {
  return `${q},${r}`;
}

// ---------- Стихии: визуальные и логические константы ----------

// String literal constants for case statements (Node.js test compatibility)
const S_EMPTY = 'empty' as StateKey;
const S_LIFE = 'life' as StateKey;
const S_FIRE = 'fire' as StateKey;
const S_WATER = 'water' as StateKey;
const S_EARTH = 'earth' as StateKey;
const S_STEAM = 'steam' as StateKey;
const S_ASH = 'ash' as StateKey;

const STATE = {
  EMPTY: S_EMPTY,
  LIFE: S_LIFE,
  FIRE: S_FIRE,
  WATER: S_WATER,
  EARTH: S_EARTH,
  STEAM: S_STEAM,
  ASH: S_ASH,
};

const COLORS: Record<StateKey, string> = {
  empty: '#0a0e14',
  life: '#4ade80',
  fire: '#ef4444',
  water: '#38bdf8',
  earth: '#a16207',
  steam: '#94a3b8',
  ash: '#1e293b',
};

const STATE_LABELS: Record<StateKey, string> = {
  empty: 'Пустота',
  life: 'Жизнь',
  fire: 'Огонь',
  water: 'Вода',
  earth: 'Земля',
  steam: 'Пар',
  ash: 'Пепел',
};

// ---------- Пресеты параметров ----------

const GEOMETRY_PRESETS: Record<GeometryKey, Record<PresetKey, Preset>> = {
  hex: {
    classic_balanced: {
      label: 'Классика стихий (стабильный)',
      description: 'Сбалансированный цикл воды и жизни — выходит на устойчивое плато.',
      params: {
        fireSpreadChance: 0.0,
        overpopulationIgniteTicks: 4,
        lightningChance: 0.002,
        survMin: 0,
        birthCount: 3,
        lifeOverpopulation: 6,
        earthDryoutChance: 0.0015,
        earthDryoutMinAge: 16,
        steamRainTicks: 1,
        waterOverflowEnabled: true,
      },
    },
    fire_storm: {
      label: 'Огненный шторм',
      description: 'Огонь агрессивно расползается. Вода — единственная защита.',
      params: {
        fireSpreadChance: 0.25,
        overpopulationIgniteTicks: 3,
        lightningChance: 0.004,
        survMin: 0,
        birthCount: 3,
        lifeOverpopulation: 6,
        earthDryoutChance: 0.0015,
        earthDryoutMinAge: 14,
        steamRainTicks: 1,
        waterOverflowEnabled: true,
      },
    },
    water_world: {
      label: 'Мир воды',
      description: 'Много воды, земля медленно отступает, жизнь буйно колонизирует берега.',
      params: {
        fireSpreadChance: 0.05,
        overpopulationIgniteTicks: 5,
        lightningChance: 0.0008,
        survMin: 0,
        birthCount: 3,
        lifeOverpopulation: 7,
        earthDryoutChance: 0.0008,
        earthDryoutMinAge: 20,
        steamRainTicks: 1,
        waterOverflowEnabled: true,
      },
    },
    desert_drought: {
      label: 'Засуха',
      description: 'Воды мало, земля сохнет быстро, жизнь выживает с трудом.',
      params: {
        fireSpreadChance: 0.15,
        overpopulationIgniteTicks: 3,
        lightningChance: 0.0025,
        survMin: 0,
        birthCount: 3,
        lifeOverpopulation: 5,
        earthDryoutChance: 0.02,
        earthDryoutMinAge: 4,
        steamRainTicks: 1,
        waterOverflowEnabled: false,
      },
    },
    chaos: {
      label: 'Хаос',
      description: 'Высокая турбулентность: молнии, пожары и засуха борются за территорию.',
      params: {
        fireSpreadChance: 0.25,
        overpopulationIgniteTicks: 3,
        lightningChance: 0.005,
        survMin: 0,
        birthCount: 3,
        lifeOverpopulation: 6,
        earthDryoutChance: 0.015,
        earthDryoutMinAge: 6,
        steamRainTicks: 1,
        waterOverflowEnabled: true,
      },
    },
  },

  square: {
    classic_balanced: {
      label: 'Классика стихий (стабильный)',
      description: 'Сбалансированный цикл воды и жизни — выходит на устойчивое плато.',
      params: {
        fireSpreadChance: 0.0,
        overpopulationIgniteTicks: 4,
        lightningChance: 0.002,
        survMin: 0,
        birthCount: 4,
        lifeOverpopulation: 7,
        earthDryoutChance: 0.0015,
        earthDryoutMinAge: 16,
        steamRainTicks: 1,
        waterOverflowEnabled: true,
      },
    },
    fire_storm: {
      label: 'Огненный шторм',
      description: 'Огонь агрессивно расползается. Вода — единственная защита.',
      params: {
        fireSpreadChance: 0.25,
        overpopulationIgniteTicks: 3,
        lightningChance: 0.004,
        survMin: 0,
        birthCount: 4,
        lifeOverpopulation: 7,
        earthDryoutChance: 0.0015,
        earthDryoutMinAge: 14,
        steamRainTicks: 1,
        waterOverflowEnabled: true,
      },
    },
    water_world: {
      label: 'Мир воды',
      description: 'Много воды, земля медленно отступает, жизнь буйно колонизирует берега.',
      params: {
        fireSpreadChance: 0.05,
        overpopulationIgniteTicks: 5,
        lightningChance: 0.0008,
        survMin: 0,
        birthCount: 4,
        lifeOverpopulation: 8,
        earthDryoutChance: 0.0008,
        earthDryoutMinAge: 20,
        steamRainTicks: 1,
        waterOverflowEnabled: true,
      },
    },
    desert_drought: {
      label: 'Засуха',
      description: 'Воды мало, земля сохнет быстро, жизнь выживает с трудом.',
      params: {
        fireSpreadChance: 0.15,
        overpopulationIgniteTicks: 3,
        lightningChance: 0.0025,
        survMin: 1,
        birthCount: 4,
        lifeOverpopulation: 5,
        earthDryoutChance: 0.02,
        earthDryoutMinAge: 4,
        steamRainTicks: 1,
        waterOverflowEnabled: false,
      },
    },
    chaos: {
      label: 'Хаос',
      description: 'Высокая турбулентность: молнии, пожары и засуха борются за территорию.',
      params: {
        fireSpreadChance: 0.25,
        overpopulationIgniteTicks: 3,
        lightningChance: 0.005,
        survMin: 0,
        birthCount: 4,
        lifeOverpopulation: 7,
        earthDryoutChance: 0.015,
        earthDryoutMinAge: 6,
        steamRainTicks: 1,
        waterOverflowEnabled: true,
      },
    },
  },
};

// ---------- Инициализация случайного поля ----------

function randomCell(rng: () => number): CellData {
  const v = rng();
  if (v < 0.10) return { state: S_LIFE, age: 0 };
  if (v < 0.22) return { state: S_WATER, age: 0 };
  if (v < 0.27) return { state: S_FIRE, age: 0 };
  if (v < 0.55) return { state: S_EARTH, age: 0 };
  return { state: S_EMPTY, age: 0 };
}

// Preset-aware random cell — uses params to tune density
function randomCellWithParams(rng: () => number, params: Params): CellData {
  const v = rng();
  const lifeChance = 0.08 + params.birthCount * 0.01;
  const waterChance = 0.10 + (params.waterOverflowEnabled ? 0.03 : 0.0);
  const fireChance = params.fireSpreadChance * 0.08 + params.lightningChance * 2;
  const earthChance = 0.24;
  let acc = 0;
  acc += lifeChance; if (v < acc) return { state: S_LIFE, age: 0 };
  acc += waterChance; if (v < acc) return { state: S_WATER, age: 0 };
  acc += fireChance; if (v < acc) return { state: S_FIRE, age: 0 };
  acc += earthChance; if (v < acc) return { state: S_EARTH, age: 0 };
  return { state: S_EMPTY, age: 0 };
}

function mulberry32(seed: number): () => number {
  let a = seed;
  return function (): number {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function buildInitialField(geometryKey: GeometryKey, radius: number, seed: number, params?: Params): Map<string, CellData> {
  const rng = mulberry32(seed);
  const field = new Map<string, CellData>();
  const gen = params ? (r: () => number) => randomCellWithParams(r, params) : randomCell;
  for (const { q, r } of makeGrid(geometryKey, radius)) {
    field.set(key(q, r), gen(rng));
  }
  return field;
}

// ---------- Режим головоломки "Полив пустоты" ----------

const WIN_MAX_AGE = 3;
const WIN_STABLE_TICKS = 15;

const GEOMETRY_LEVELS: Record<GeometryKey, Level[]> = {
  // Поле головоломки hex: 469 клеток (radius=12). Капли откалиброваны под
  // terraforming + flow, с запасом ~1.5× от reference-минимума для 217 клеток.
  hex: [
    { id: 1, label: 'Уровень 1', waterDensity: 0.18, lifeDensity: 0.10, earthDensity: 0.30, droplets: 80 },
    { id: 2, label: 'Уровень 2', waterDensity: 0.14, lifeDensity: 0.10, earthDensity: 0.30, droplets: 100 },
    { id: 3, label: 'Уровень 3', waterDensity: 0.11, lifeDensity: 0.10, earthDensity: 0.30, droplets: 120 },
    { id: 4, label: 'Уровень 4', waterDensity: 0.08, lifeDensity: 0.10, earthDensity: 0.30, droplets: 150 },
    { id: 5, label: 'Уровень 5', waterDensity: 0.05, lifeDensity: 0.10, earthDensity: 0.30, droplets: 175 },
  ],
  // Поле головоломки square: 441 клеток (21×21, radius=10). Капли с
  // запасом ~1.6× от reference-минимума для 169 клеток.
  square: [
    { id: 1, label: 'Уровень 1', waterDensity: 0.18, lifeDensity: 0.10, earthDensity: 0.30, droplets: 60 },
    { id: 2, label: 'Уровень 2', waterDensity: 0.14, lifeDensity: 0.10, earthDensity: 0.30, droplets: 100 },
    { id: 3, label: 'Уровень 3', waterDensity: 0.11, lifeDensity: 0.10, earthDensity: 0.30, droplets: 110 },
    { id: 4, label: 'Уровень 4', waterDensity: 0.08, lifeDensity: 0.10, earthDensity: 0.30, droplets: 140 },
    { id: 5, label: 'Уровень 5', waterDensity: 0.05, lifeDensity: 0.10, earthDensity: 0.30, droplets: 150 },
  ],
};

const PUZZLE_RADIUS: Record<GeometryKey, number> = { hex: 12, square: 10 };

function levelRandomCell(rng: () => number, level: Level): CellData {
  const v = rng();
  if (v < level.lifeDensity) return { state: S_LIFE, age: 0 };
  if (v < level.lifeDensity + level.earthDensity) return { state: S_EARTH, age: 0 };
  if (v < level.lifeDensity + level.earthDensity + level.waterDensity) {
    return { state: S_WATER, age: 0 };
  }
  return { state: S_EMPTY, age: 0 };
}

function buildLevelField(geometryKey: GeometryKey, radius: number, seed: number, level: Level): Map<string, CellData> {
  const rng = mulberry32(seed);
  const field = new Map<string, CellData>();
  for (const { q, r } of makeGrid(geometryKey, radius)) {
    field.set(key(q, r), levelRandomCell(rng, level));
  }
  return field;
}

function checkPuzzleWinTick(field: Map<string, CellData>): boolean {
  for (const cell of field.values()) {
    if (cell.state === S_EMPTY && (cell.age || 0) >= WIN_MAX_AGE) {
      return false;
    }
  }
  return true;
}

// ---------- Подсчёт воды для контроля закона сохранения ----------

function countWater(field: Map<string, CellData>): WaterStats {
  let water = 0, steam = 0;
  for (const cell of field.values()) {
    if (cell.state === S_WATER) water++;
    if (cell.state === S_STEAM) steam++;
  }
  return { water, steam, total: water + steam };
}

// ---------- Основной шаг симуляции ----------

function stepField(
  geometryKey: GeometryKey,
  field: Map<string, CellData>,
  radius: number,
  params: Params,
  rng: () => number,
  tick?: number
): Map<string, CellData> {
  const next = new Map<string, CellData>();
  const requiredFull = GEOMETRIES[geometryKey].fullNeighborCount;

  const getCell = (q: number, r: number): CellData | null => field.get(key(q, r)) || null;

  function neighborCounts(q: number, r: number) {
    const counts: Record<StateKey, number> = {
      empty: 0, life: 0, fire: 0,
      water: 0, earth: 0, steam: 0, ash: 0,
    };
    const list: { q: number; r: number; cell: CellData }[] = [];
    for (const [nq, nr] of neighborsOf(geometryKey, q, r)) {
      const c = getCell(nq, nr);
      if (c) {
        counts[c.state]++;
        list.push({ q: nq, r: nr, cell: c });
      }
    }
    return { counts, list };
  }

  const overflowTargets = new Map<string, string>();
  const overflowSources = new Set<string>();

  // === Rule 1: Water flow — вода→пустота за 2 тика ===
  const flowTargets = new Map<string, string>();   // targetKey → sourceKey
  const flowReverse = new Map<string, string>();   // sourceKey → targetKey
  const flowSources = new Set<string>();

  for (const { q, r } of makeGrid(geometryKey, radius)) {
    const cell = getCell(q, r);
    if (!cell || cell.state !== S_WATER) continue;

    let emptyNeighbor: string | null = null;
    for (const [nq, nr] of neighborsOf(geometryKey, q, r)) {
      const n = getCell(nq, nr);
      if (n && n.state === S_EMPTY) {
        emptyNeighbor = key(nq, nr);
        break;
      }
    }
    if (emptyNeighbor === null) continue;

    const prevFlow = cell.flowTicks || 0;
    if (prevFlow >= 1) {
      // Skip if this water source will be consumed by fire
      let willBeConsumed = false;
      for (const [nq, nr] of neighborsOf(geometryKey, q, r)) {
        const n = getCell(nq, nr);
        if (!n) continue;
        if (n.state === S_FIRE) { willBeConsumed = true; break; }
        if (n.state === S_LIFE) {
          const { counts: lifeNeighborCounts } = neighborCounts(nq, nr);
          if (lifeNeighborCounts.fire > 0) { willBeConsumed = true; break; }
        }
      }
      if (willBeConsumed) continue;

      const sKey = key(q, r);
      if (!flowTargets.has(emptyNeighbor)) {
        flowTargets.set(emptyNeighbor, sKey);
        flowReverse.set(sKey, emptyNeighbor);
        flowSources.add(sKey);
      }
    }
  }

  // === Rule 2: Terraforming — пустота, окружённая E+L, забирает ближайшую воду ===
  // BFS throttled: full scan only every 3 ticks to save CPU
  const skipTerraforming = tick !== undefined && tick % 3 !== 0;
  if (!skipTerraforming) {
    const fullN = GEOMETRIES[geometryKey].fullNeighborCount;
    for (const { q, r } of makeGrid(geometryKey, radius)) {
      const cell = getCell(q, r);
      if (!cell || cell.state !== S_EMPTY) continue;
      if (flowTargets.has(key(q, r))) continue;

      const { counts } = neighborCounts(q, r);
      const e = counts.earth;
      const l = counts.life;
      const ePlusL = e + l;
      if (ePlusL !== fullN) continue;

      let terraformable = false;
      if (geometryKey === 'hex') {
        terraformable = (e === 2 && l === 4) || (e === 3 && l === 3) || (e === 4 && l === 2);
      } else {
        terraformable = (e === 3 && l === 5) || (e === 4 && l === 4) || (e === 5 && l === 3);
      }
      if (!terraformable) continue;

      const visited = new Set<string>();
      const queue: { q: number; r: number; dist: number }[] = [{ q, r, dist: 0 }];
      visited.add(key(q, r));

      let foundWater: string | null = null;
      let head = 0;
      while (head < queue.length && foundWater === null) {
        const cur = queue[head++];
        if (cur.dist > 12) break;
        for (const [nq, nr] of neighborsOf(geometryKey, cur.q, cur.r)) {
          const nk = key(nq, nr);
          if (visited.has(nk)) continue;
          visited.add(nk);
          const n = getCell(nq, nr);
          if (!n) continue;
          if (n.state === S_WATER && !flowSources.has(nk)) {
            // Skip if this water will be consumed by fire
            let willBeConsumed = false;
            for (const [nq2, nr2] of neighborsOf(geometryKey, nq, nr)) {
              const n2 = getCell(nq2, nr2);
              if (!n2) continue;
              if (n2.state === S_FIRE) { willBeConsumed = true; break; }
              if (n2.state === S_LIFE) {
                const { counts: lifeNeighborCounts } = neighborCounts(nq2, nr2);
                if (lifeNeighborCounts.fire > 0) { willBeConsumed = true; break; }
              }
            }
            if (willBeConsumed) {
              queue.push({ q: nq, r: nr, dist: cur.dist + 1 });
              continue;
            }

            foundWater = nk;
            flowSources.add(nk);
            break;
          }
          queue.push({ q: nq, r: nr, dist: cur.dist + 1 });
        }
      }

      if (foundWater !== null && !flowTargets.has(key(q, r))) {
        flowTargets.set(key(q, r), foundWater);
        flowReverse.set(foundWater, key(q, r));
      }
    }
  }

  // Water overflow — throttled to every 3 ticks
  if (params.waterOverflowEnabled && (tick === undefined || tick % 3 === 0)) {
    for (const { q, r } of makeGrid(geometryKey, radius)) {
      const cell = getCell(q, r);
      if (!cell || cell.state !== S_WATER) continue;
      const { counts, list } = neighborCounts(q, r);
      if (counts.water !== requiredFull) continue;
      for (const n of list) {
        const { list: nList } = neighborCounts(n.q, n.r);
        const targetEmpty = nList.find((m) => {
          if (m.cell.state !== S_EMPTY) return false;
          const { counts: mCounts } = neighborCounts(m.q, m.r);
          const willBeFarmed = mCounts.water > 0 && mCounts.life > 0;
          return !willBeFarmed;
        });
        if (targetEmpty) {
          const tKey = key(targetEmpty.q, targetEmpty.r);
          const sKey = key(q, r);
          if (!flowTargets.has(tKey) && !flowSources.has(sKey) && !overflowTargets.has(tKey) && !overflowSources.has(sKey)) {
            overflowTargets.set(tKey, sKey);
            overflowSources.add(sKey);
          }
          break;
        }
      }
    }
  }

  for (const { q, r } of makeGrid(geometryKey, radius)) {
    const k = key(q, r);
    const cell = getCell(q, r)!;
    const { counts } = neighborCounts(q, r);
    let result: CellData = { state: cell.state, age: (cell.age || 0) + 1 };

    switch (cell.state) {
      case S_LIFE: {
        const hasWater = counts.water > 0;
        const isOverpopulated = counts.life >= params.lifeOverpopulation;

        if (counts.fire > 0) {
          if (hasWater) {
            result = { state: S_LIFE, age: 0 };
          } else {
            result = { state: S_FIRE, age: 0 };
          }
        } else if (isOverpopulated && !hasWater) {
          const heat = (cell.age || 0) + 1;
          if (heat >= params.overpopulationIgniteTicks) {
            result = { state: S_FIRE, age: 0 };
          } else {
            result = { state: S_LIFE, age: heat };
          }
        } else if (params.lightningChance > 0 && rng() < params.lightningChance) {
          result = { state: S_FIRE, age: 0 };
        } else {
          if (isOverpopulated) {
            // Water "cools" overpopulation
            result = { state: S_LIFE, age: 0 };
          } else if (counts.life < params.survMin) {
            result = { state: S_EARTH, age: 0 };
          } else {
            result = { state: S_LIFE, age: 0 };
          }
        }
        break;
      }

      case S_FIRE: {
        if (counts.water > 0) {
          result = { state: S_ASH, age: 0 };
        } else if ((cell.age || 0) >= 1) {
          result = { state: S_ASH, age: 0 };
        } else {
          result = { state: S_FIRE, age: cell.age + 1 };
        }
        break;
      }

      case S_WATER: {
        let consumed = false;
        for (const [nq, nr] of neighborsOf(geometryKey, q, r)) {
          const n = getCell(nq, nr);
          if (!n) continue;
          if (n.state === S_FIRE) { consumed = true; break; }
          if (n.state === S_LIFE) {
            const { counts: lifeNeighborCounts } = neighborCounts(nq, nr);
            if (lifeNeighborCounts.fire > 0) { consumed = true; break; }
          }
        }
        const hasEmpty = counts.empty > 0;
        const newFlow = hasEmpty ? (cell.flowTicks || 0) + 1 : 0;
        if (consumed) {
          const rev = flowReverse.get(k);
          if (rev) flowTargets.delete(rev);
          result = { state: S_STEAM, age: 0 };
        } else if (flowSources.has(k)) {
          result = { state: S_EARTH, age: 0 };
        } else if (params.waterOverflowEnabled && overflowSources.has(k)) {
          result = { state: S_EARTH, age: 0 };
        } else {
          result = { state: S_WATER, age: cell.age + 1, flowTicks: newFlow || undefined };
        }
        break;
      }

      case S_EARTH: {
        const w = counts.water;
        const l = counts.life;
        const sumWL = w + l;
        // FIX: Use params.birthCount instead of hardcoded 3
        const canBirth = l >= 1 && sumWL === params.birthCount;
        if (canBirth) {
          result = { state: S_LIFE, age: 0 };
        } else if (
          counts.water === 0 &&
          params.lightningChance > 0 &&
          rng() < params.lightningChance * 0.5
        ) {
          result = { state: S_FIRE, age: 0 };
        } else if (
          params.earthDryoutChance > 0 &&
          counts.water === 0 &&
          (cell.age || 0) >= params.earthDryoutMinAge &&
          rng() < params.earthDryoutChance
        ) {
          result = { state: S_EMPTY, age: 0 };
        } else {
          result = { state: S_EARTH, age: cell.age + 1 };
        }
        break;
      }

      case S_STEAM: {
        if ((cell.age || 0) >= params.steamRainTicks - 1) {
          result = { state: S_WATER, age: 0 };
        } else {
          result = { state: S_STEAM, age: cell.age + 1 };
        }
        break;
      }

      case S_ASH: {
        const hasWater = counts.water > 0;
        const hasLife = counts.life > 0;
        if (hasWater && hasLife) {
          // Ash with both water and life → earth (fertilized)
          result = { state: S_EARTH, age: 0 };
        } else if (hasWater) {
          // Ash gets wet, track wet streak
          const wetStreak = (cell.wetStreak || 0) + 1;
          if (wetStreak >= 3) {
            // After 3 ticks of wetness, ash becomes earth
            result = { state: S_EARTH, age: 0 };
          } else {
            result = { state: S_ASH, age: (cell.age || 0) + 1, wetStreak };
          }
        } else {
          // Dry ash just ages
          result = { state: S_ASH, age: (cell.age || 0) + 1, wetStreak: 0 };
        }
        break;
      }

      case S_EMPTY: {
        const hasWater = counts.water > 0;
        const hasLife = counts.life > 0;
        const gotFlow = flowTargets.has(k);
        const gotOverflow = params.waterOverflowEnabled && overflowTargets.has(k);
        if (gotFlow) {
          result = { state: S_WATER, age: 0 };
        } else if (hasWater && hasLife) {
          result = { state: S_EARTH, age: 0 };
        } else if (gotOverflow) {
          result = { state: S_WATER, age: 0 };
        } else if (counts.fire >= 2 && rng() < params.fireSpreadChance) {
          result = { state: S_FIRE, age: 0 };
        } else {
          result = { state: S_EMPTY, age: (cell.age || 0) + 1 };
        }
        break;
      }

      default:
        result = { state: cell.state, age: (cell.age || 0) + 1 };
    }

    next.set(k, result);
  }

  return next;
}

// ---------- Экспорт публичного API ----------

export {
  STATE,
  COLORS,
  STATE_LABELS,
  GEOMETRIES,
  GEOMETRY_PRESETS,
  GEOMETRY_LEVELS,
  PUZZLE_RADIUS,
  WIN_MAX_AGE,
  WIN_STABLE_TICKS,
  S_EMPTY as EMPTY,
  S_LIFE as LIFE,
  S_FIRE as FIRE,
  S_WATER as WATER,
  S_EARTH as EARTH,
  S_STEAM as STEAM,
  S_ASH as ASH,
  HEX_DIRS,
  SQUARE_DIRS,
  neighborsOf,
  key,
  makeGrid,
  makeHexagonalGridImpl,
    makeSquareGridImpl,
    gridCellCount,
    hexGridCellCountImpl,
    squareGridCellCountImpl,
    mulberry32,
    randomCell,
    buildInitialField,
    levelRandomCell,
    buildLevelField,
    checkPuzzleWinTick,
    countWater,
    stepField,
  };

// Для обратной совместимости
export const PRESETS = GEOMETRY_PRESETS.hex;
export const LEVELS = GEOMETRY_LEVELS.hex;