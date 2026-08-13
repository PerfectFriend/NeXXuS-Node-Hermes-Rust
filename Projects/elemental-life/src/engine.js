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
 *   ash    — пепел / опалённая пустота (ждёт воду 2 итерации, чтобы стать землёй)
 *
 * ЗАКОН СОХРАНЕНИЯ ВОДЫ (инвариант, проверенный headless-тестами):
 *   total(water) + total(steam) = const на протяжении всей симуляции,
 *   независимо от выбранной геометрии. Вода не создаётся и не
 *   уничтожается — только меняет агрегатное состояние (water -> steam
 *   при тушении огня жизнью) или физически перемещается (перелив воды
 *   в пустоту/пепел, или розлив игроком в puzzle-режиме).
 *
 * РЕЖИМ ГОЛОВОЛОМКИ ("Полив пустоты"):
 *   Игрок заливает клетки empty/ash водой (мгновенно, тратит "каплю" из лимита).
 *   Мир продолжает тикать сам по себе. Победа — когда пустота/пепел не
 *   задерживаются на поле дольше WIN_MAX_AGE тиков подряд, и это держится
 *   стабильно WIN_STABLE_TICKS тиков (экосистема "сама себя исцеляет").
 */

// ---------- Геометрии сетки: гекс (6 соседей) и квадрат (8 соседей) ----------

const HEX_DIRS = [
  [+1, 0], [+1, -1], [0, -1],
  [-1, 0], [-1, +1], [0, +1],
];

const SQUARE_DIRS = [
  [+1, 0], [+1, +1], [0, +1], [-1, +1],
  [-1, 0], [-1, -1], [0, -1], [+1, -1],
];

function makeHexagonalGrid(radius) {
  // Большой шестиугольник из малых гекс-клеток в осевых координатах.
  // radius = (сторона - 1); условие принадлежности гексагону: max(|q|,|r|,|q+r|) <= radius.
  const cells = [];
  for (let q = -radius; q <= radius; q++) {
    const rMin = Math.max(-radius, -q - radius);
    const rMax = Math.min(radius, -q + radius);
    for (let r = rMin; r <= rMax; r++) {
      cells.push({ q, r });
    }
  }
  return cells;
}

function hexGridCellCount(side) {
  const R = side - 1;
  return 3 * R * (R + 1) + 1;
}

function makeSquareGrid(radius) {
  // Квадратное поле side x side малых клеток, side = 2*radius + 1.
  const cells = [];
  for (let q = -radius; q <= radius; q++) {
    for (let r = -radius; r <= radius; r++) {
      cells.push({ q, r });
    }
  }
  return cells;
}

function squareGridCellCount(side) {
  return side * side;
}

// Единая точка выбора геометрии. UI передаёт geometryKey ("hex" | "square")
// во все функции движка, которым нужно знать структуру соседства.
const GEOMETRIES = {
  hex: {
    dirs: HEX_DIRS,
    fullNeighborCount: 6,
    makeGrid: makeHexagonalGrid,
    cellCount: hexGridCellCount,
    radiusFromSide: (side) => side - 1,
  },
  square: {
    dirs: SQUARE_DIRS,
    fullNeighborCount: 8,
    makeGrid: makeSquareGrid,
    cellCount: squareGridCellCount,
    radiusFromSide: (side) => Math.floor((side - 1) / 2),
  },
};

function neighborsOf(geometryKey, q, r) {
  const dirs = GEOMETRIES[geometryKey].dirs;
  return dirs.map(([dq, dr]) => [q + dq, r + dr]);
}

function makeGrid(geometryKey, radius) {
  return GEOMETRIES[geometryKey].makeGrid(radius);
}

function gridCellCount(geometryKey, side) {
  return GEOMETRIES[geometryKey].cellCount(side);
}

function fullNeighborCount(geometryKey) {
  return GEOMETRIES[geometryKey].fullNeighborCount;
}

function key(q, r) {
  return `${q},${r}`;
}

// ---------- Стихии: визуальные и логические константы ----------

const STATE = {
  EMPTY: "empty",
  LIFE: "life",
  FIRE: "fire",
  WATER: "water",
  EARTH: "earth",
  STEAM: "steam",
  ASH: "ash",
};

const COLORS = {
  [STATE.EMPTY]: "#0d1117",
  [STATE.LIFE]: "#2ecc71",
  [STATE.FIRE]: "#ff5a36",
  [STATE.WATER]: "#2196f3",
  [STATE.EARTH]: "#8d6e43",
  [STATE.STEAM]: "#cfd8e3",
  [STATE.ASH]: "#4a4a4a",
};

const STATE_LABELS = {
  [STATE.EMPTY]: "Пустота",
  [STATE.LIFE]: "Жизнь",
  [STATE.FIRE]: "Огонь",
  [STATE.WATER]: "Вода",
  [STATE.EARTH]: "Земля",
  [STATE.STEAM]: "Пар",
  [STATE.ASH]: "Пепел",
};

// ---------- Пресеты параметров ----------

// Пресеты раздельны для каждой геометрии: правила одни и те же (см. stepField),
// но числовые пороги откалиброваны независимо headless-тестами — прямой перенос
// гекс-чисел на квадрат даёт иной (более "цветущий") баланс, см. комментарий
// в шапке файла. Структура присетов идентична по набору и духу (один и тот же
// набор имён/описаний), различаются только params.
const GEOMETRY_PRESETS = {
  hex: {
    classic_balanced: {
      label: "Классика стихий (стабильный)",
      description: "Сбалансированный цикл воды и жизни — выходит на устойчивое плато.",
      params: {
        fireSpreadChance: 0.0,
        overpopulationIgniteTicks: 4,
        lightningChance: 0.002,
        survMin: 0,
        birthCount: 3,
        lifeOverpopulation: 6,
        earthDryoutChance: 0.0015,
        earthDryoutMinAge: 16,
        ashToEarthTicks: 2,
        steamRainTicks: 1,
        waterOverflowEnabled: true,
      },
    },
    fire_storm: {
      label: "Огненный шторм",
      description: "Огонь агрессивно расползается. Вода — единственная защита.",
      params: {
        fireSpreadChance: 0.25,
        overpopulationIgniteTicks: 3,
        lightningChance: 0.004,
        survMin: 0,
        birthCount: 3,
        lifeOverpopulation: 6,
        earthDryoutChance: 0.0015,
        earthDryoutMinAge: 14,
        ashToEarthTicks: 2,
        steamRainTicks: 1,
        waterOverflowEnabled: true,
      },
    },
    water_world: {
      label: "Мир воды",
      description: "Много воды, земля медленно отступает, жизнь буйно колонизирует берега.",
      params: {
        fireSpreadChance: 0.05,
        overpopulationIgniteTicks: 5,
        lightningChance: 0.0008,
        survMin: 0,
        birthCount: 3,
        lifeOverpopulation: 7,
        earthDryoutChance: 0.0008,
        earthDryoutMinAge: 20,
        ashToEarthTicks: 2,
        steamRainTicks: 1,
        waterOverflowEnabled: true,
      },
    },
    desert_drought: {
      label: "Засуха",
      description: "Воды мало, земля сохнет быстро, жизнь выживает с трудом.",
      params: {
        fireSpreadChance: 0.15,
        overpopulationIgniteTicks: 3,
        lightningChance: 0.0025,
        survMin: 0,
        birthCount: 3,
        lifeOverpopulation: 5,
        earthDryoutChance: 0.02,
        earthDryoutMinAge: 4,
        ashToEarthTicks: 3,
        steamRainTicks: 1,
        waterOverflowEnabled: false,
      },
    },
    chaos: {
      label: "Хаос",
      description: "Высокая турбулентность: молнии, пожары и засуха борются за территорию.",
      params: {
        fireSpreadChance: 0.25,
        overpopulationIgniteTicks: 3,
        lightningChance: 0.005,
        survMin: 0,
        birthCount: 3,
        lifeOverpopulation: 6,
        earthDryoutChance: 0.015,
        earthDryoutMinAge: 6,
        ashToEarthTicks: 1,
        steamRainTicks: 1,
        waterOverflowEnabled: true,
      },
    },
  },

  // Квадратная сетка, 8 соседей (Мур). birthCount=4 и lifeOverpopulation
  // подняты относительно гекс-версии — при 8 соседях статистически больше
  // комбинаций дают нужную сумму (вода+жизнь), поэтому birthCount=3 на
  // квадрате даёт ~36% поля жизнью вместо целевых ~15% — перекалибровано
  // headless-тестами на 3000 тиков (см. историю чата при разработке).
  square: {
    classic_balanced: {
      label: "Классика стихий (стабильный)",
      description: "Сбалансированный цикл воды и жизни — выходит на устойчивое плато.",
      params: {
        fireSpreadChance: 0.0,
        overpopulationIgniteTicks: 4,
        lightningChance: 0.002,
        survMin: 0,
        birthCount: 4,
        lifeOverpopulation: 7,
        earthDryoutChance: 0.0015,
        earthDryoutMinAge: 16,
        ashToEarthTicks: 2,
        steamRainTicks: 1,
        waterOverflowEnabled: true,
      },
    },
    fire_storm: {
      label: "Огненный шторм",
      description: "Огонь агрессивно расползается. Вода — единственная защита.",
      params: {
        fireSpreadChance: 0.25,
        overpopulationIgniteTicks: 3,
        lightningChance: 0.004,
        survMin: 0,
        birthCount: 4,
        lifeOverpopulation: 7,
        earthDryoutChance: 0.0015,
        earthDryoutMinAge: 14,
        ashToEarthTicks: 2,
        steamRainTicks: 1,
        waterOverflowEnabled: true,
      },
    },
    water_world: {
      label: "Мир воды",
      description: "Много воды, земля медленно отступает, жизнь буйно колонизирует берега.",
      params: {
        fireSpreadChance: 0.05,
        overpopulationIgniteTicks: 5,
        lightningChance: 0.0008,
        survMin: 0,
        birthCount: 4,
        lifeOverpopulation: 8,
        earthDryoutChance: 0.0008,
        earthDryoutMinAge: 20,
        ashToEarthTicks: 2,
        steamRainTicks: 1,
        waterOverflowEnabled: true,
      },
    },
    desert_drought: {
      label: "Засуха",
      description: "Воды мало, земля сохнет быстро, жизнь выживает с трудом.",
      params: {
        // survMin:1 (а не 0, как у гекса) — именно это, не высыхание земли,
        // даёт реальную "засуху" на квадрате: высыхание земли само по себе
        // парадоксально подпитывало жизнь через пересортировку состояний
        // (empty легче комбинируется в water+life, чем устоявшаяся earth).
        fireSpreadChance: 0.15,
        overpopulationIgniteTicks: 3,
        lightningChance: 0.0025,
        survMin: 1,
        birthCount: 4,
        lifeOverpopulation: 5,
        earthDryoutChance: 0.02,
        earthDryoutMinAge: 4,
        ashToEarthTicks: 3,
        steamRainTicks: 1,
        waterOverflowEnabled: false,
      },
    },
    chaos: {
      label: "Хаос",
      description: "Высокая турбулентность: молнии, пожары и засуха борются за территорию.",
      params: {
        fireSpreadChance: 0.25,
        overpopulationIgniteTicks: 3,
        lightningChance: 0.005,
        survMin: 0,
        birthCount: 4,
        lifeOverpopulation: 7,
        earthDryoutChance: 0.015,
        earthDryoutMinAge: 6,
        ashToEarthTicks: 1,
        steamRainTicks: 1,
        waterOverflowEnabled: true,
      },
    },
  },
};

// Обратная совместимость: PRESETS = гекс-пресеты (старое поведение по умолчанию,
// чтобы код/тесты, написанные до введения мультигеометрии, продолжали работать).
const PRESETS = GEOMETRY_PRESETS.hex;

// ---------- Инициализация случайного поля ----------

function randomCell(rng) {
  const v = rng();
  if (v < 0.10) return { state: STATE.LIFE, age: 0 };
  if (v < 0.22) return { state: STATE.WATER, age: 0 };
  if (v < 0.27) return { state: STATE.FIRE, age: 0 };
  if (v < 0.55) return { state: STATE.EARTH, age: 0 };
  return { state: STATE.EMPTY, age: 0 };
}

function mulberry32(seed) {
  let a = seed;
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function buildInitialField(geometryKey, radius, seed) {
  const rng = mulberry32(seed);
  const field = new Map();
  for (const { q, r } of makeGrid(geometryKey, radius)) {
    field.set(key(q, r), randomCell(rng));
  }
  return field;
}

// ---------- Режим головоломки "Полив пустоты" ----------
//
// Идея: вся пустота и пепел могут быть "оживлены" простой заливкой водой.
// Игроку даётся стартовое поле с ограниченным количеством воды и лимит капель.
// Капля мгновенно превращает клетку empty/ash в воду.
// Симуляция продолжает тикать сама — игрок подливает воду по ходу дела.
// ПОБЕДА: пустота/пепел не задерживаются на поле дольше WIN_MAX_AGE тиков подряд,
// и это держится стабильно WIN_STABLE_TICKS тиков без перерыва — то есть мир
// сам "наводит порядок" даже после редкой молнии. Поле НЕ обязано быть statично:
// огонь/перенаселение/молния могут продолжаться, лишь бы пустота не залипала.
const WIN_MAX_AGE = 3; // пустота/пепел не должны жить дольше этого числа тиков
const WIN_STABLE_TICKS = 15; // сколько тиков подряд критерий должен держаться для победы

// Уровни головоломки откалиброваны раздельно для каждой геометрии —
// проверены симуляцией "жадного игрока" (заливает самые старые empty/ash
// первым делом), с запасом x1.3–1.6 от найденного минимума капель.
const GEOMETRY_LEVELS = {
  hex: [
    { id: 1, label: "Уровень 1", waterDensity: 0.35, lifeDensity: 0.08, earthDensity: 0.25, droplets: 55 },
    { id: 2, label: "Уровень 2", waterDensity: 0.28, lifeDensity: 0.08, earthDensity: 0.25, droplets: 65 },
    { id: 3, label: "Уровень 3", waterDensity: 0.22, lifeDensity: 0.08, earthDensity: 0.25, droplets: 80 },
    { id: 4, label: "Уровень 4", waterDensity: 0.16, lifeDensity: 0.08, earthDensity: 0.25, droplets: 100 },
    { id: 5, label: "Уровень 5", waterDensity: 0.10, lifeDensity: 0.08, earthDensity: 0.25, droplets: 115 },
  ],
  // Поле головоломки на квадрате меньше по радиусу (13x13=169 клеток —
  // сопоставимо с гекс-головоломкой на 217 клетках), бюджеты капель
  // пересчитаны отдельно: на 8 соседях правило birthCount=4 (не 3, как у
  // гекса) даёт другую динамику заливки, прямой перенос гекс-чисел был
  // бы неверным.
  square: [
    { id: 1, label: "Уровень 1", waterDensity: 0.35, lifeDensity: 0.08, earthDensity: 0.25, droplets: 38 },
    { id: 2, label: "Уровень 2", waterDensity: 0.28, lifeDensity: 0.08, earthDensity: 0.25, droplets: 63 },
    { id: 3, label: "Уровень 3", waterDensity: 0.22, lifeDensity: 0.08, earthDensity: 0.25, droplets: 68 },
    { id: 4, label: "Уровень 4", waterDensity: 0.16, lifeDensity: 0.08, earthDensity: 0.25, droplets: 86 },
    { id: 5, label: "Уровень 5", waterDensity: 0.10, lifeDensity: 0.08, earthDensity: 0.25, droplets: 93 },
  ],
};

// Обратная совместимость: LEVELS = гекс-уровни (поведение по умолчанию).
const LEVELS = GEOMETRY_LEVELS.hex;

const PUZZLE_RADIUS = { hex: 8, square: 6 }; // hex: 217 клеток, square: 13x13=169 клеток

function levelRandomCell(rng, level) {
  const v = rng();
  if (v < level.lifeDensity) return { state: STATE.LIFE, age: 0 };
  if (v < level.lifeDensity + level.earthDensity) return { state: STATE.EARTH, age: 0 };
  if (v < level.lifeDensity + level.earthDensity + level.waterDensity) {
    return { state: STATE.WATER, age: 0 };
  }
  return { state: STATE.EMPTY, age: 0 };
}

function buildLevelField(geometryKey, radius, seed, level) {
  const rng = mulberry32(seed);
  const field = new Map();
  for (const { q, r } of makeGrid(geometryKey, radius)) {
    field.set(key(q, r), levelRandomCell(rng, level));
  }
  return field;
}

function checkPuzzleWinTick(field) {
  // Возвращает true, если на данном тике пустота/пепел "молоды" (критерий ещё не нарушен).
  for (const cell of field.values()) {
    if (
      (cell.state === STATE.EMPTY || cell.state === STATE.ASH) &&
      (cell.age || 0) >= WIN_MAX_AGE
    ) {
      return false;
    }
  }
  return true;
}

// ---------- Подсчёт воды для контроля закона сохранения ----------

function countWater(field) {
  let water = 0, steam = 0;
  for (const cell of field.values()) {
    if (cell.state === STATE.WATER) water++;
    if (cell.state === STATE.STEAM) steam++;
  }
  return { water, steam, total: water + steam };
}

// ---------- Основной шаг симуляции ----------

function stepField(geometryKey, field, radius, params, rng) {
  const next = new Map();
  const requiredFull = fullNeighborCount(geometryKey);

  const getCell = (q, r) => field.get(key(q, r)) || null;

  // Предрасчёт соседей по типам для каждой клетки
  function neighborCounts(q, r) {
    const counts = {
      [STATE.EMPTY]: 0, [STATE.LIFE]: 0, [STATE.FIRE]: 0,
      [STATE.WATER]: 0, [STATE.EARTH]: 0, [STATE.STEAM]: 0, [STATE.ASH]: 0,
    };
    const list = [];
    for (const [nq, nr] of neighborsOf(geometryKey, q, r)) {
      const c = getCell(nq, nr);
      if (c) {
        counts[c.state]++;
        list.push({ q: nq, r: nr, cell: c });
      }
    }
    return { counts, list };
  }

  // Для перелива воды нам нужно решить заранее, куда вода "сольётся",
  // чтобы не было гонки записи в одну и ту же клетку дважды.
  const overflowTargets = new Map(); // key(target) -> key(source)
  const overflowSources = new Set();

  if (params.waterOverflowEnabled) {
    for (const { q, r } of makeGrid(geometryKey, radius)) {
      const cell = getCell(q, r);
      if (!cell || cell.state !== STATE.WATER) continue;
      const { counts, list } = neighborCounts(q, r);
      if (counts[STATE.WATER] !== requiredFull) continue; // полностью окружена водой
      // ищем соседа воды, у которого есть сосед-пустота/пепел
      // (но не такую пустоту/пепел, что сама уже распахивается водой+жизнью в этот тик —
      // иначе источник перелива превратится в землю, а цель тоже превратится в землю
      // своим путём, и вода окажется потеряна — нарушится закон сохранения)
      for (const n of list) {
        const { list: nList } = neighborCounts(n.q, n.r);
        const targetEmptyAsh = nList.find((m) => {
          if (m.cell.state !== STATE.EMPTY && m.cell.state !== STATE.ASH) return false;
          const { counts: mCounts } = neighborCounts(m.q, m.r);
          const willBeFarmed = mCounts[STATE.WATER] > 0 && mCounts[STATE.LIFE] > 0;
          return !willBeFarmed;
        });
        if (targetEmptyAsh) {
          const tKey = key(targetEmptyAsh.q, targetEmptyAsh.r);
          const sKey = key(q, r);
          if (!overflowTargets.has(tKey) && !overflowSources.has(sKey)) {
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
    const cell = getCell(q, r);
    const { counts } = neighborCounts(q, r);
    let result = { state: cell.state, age: (cell.age || 0) + 1 };

    switch (cell.state) {
      case STATE.LIFE: {
        const hasWater = counts[STATE.WATER] > 0;
        const isOverpopulated = counts[STATE.LIFE] >= params.lifeOverpopulation;

        // Огонь рядом (от соседней горящей клетки)?
        if (counts[STATE.FIRE] > 0) {
          if (hasWater) {
            // Жизнь спасается водой: вода тратится (испаряется), жизнь выживает.
            // (Само превращение воды->пар и огня->пепел происходит в их собственных клетках.)
            result = { state: STATE.LIFE, age: 0 };
          } else {
            // Нет воды для спасения — огонь обязательно перекидывается на эту жизнь.
            result = { state: STATE.FIRE, age: 0 };
          }
        } else if (isOverpopulated && !hasWater) {
          // Перенаселение без доступа к воде: клетка "копит" перегрев.
          // После N тиков подряд в таком состоянии — самовозгорание (раньше называли "молнией").
          const heat = (cell.age || 0) + 1;
          if (heat >= params.overpopulationIgniteTicks) {
            result = { state: STATE.FIRE, age: 0 };
          } else {
            result = { state: STATE.LIFE, age: heat };
          }
        } else if (params.lightningChance > 0 && rng() < params.lightningChance) {
          // Молния: отдельный редкий случайный источник огня (не связанный с перенаселением).
          result = { state: STATE.FIRE, age: 0 };
        } else {
          // Правила выживания, откалиброванные под 6 соседей гекс-сетки.
          const aliveLike = counts[STATE.LIFE];
          if (isOverpopulated) {
            // Перенаселена, но есть вода рядом — вода "разгружает" клетку, не даёт перегреться.
            result = { state: STATE.LIFE, age: 0 };
          } else if (aliveLike < params.survMin) {
            result = { state: STATE.EARTH, age: 0 }; // изоляция -> земля
          } else {
            result = { state: STATE.LIFE, age: 0 };
          }
        }
        break;
      }

      case STATE.FIRE: {
        if (counts[STATE.WATER] > 0) {
          // Огонь тушится водой (вода в соседней клетке испарится сама в своей ветке).
          result = { state: STATE.ASH, age: 0 };
        } else if ((cell.age || 0) >= 1) {
          // Прожил 2 итерации без тушения — гаснет сам.
          result = { state: STATE.ASH, age: 0 };
        } else {
          result = { state: STATE.FIRE, age: cell.age + 1 };
          // Шанс распространения на соседнюю жизнь обработан в ветке LIFE/EARTH.
        }
        break;
      }

      case STATE.WATER: {
        // Проверяем: эта вода используется для тушения соседнего огня
        // или для спасения соседней жизни? Если рядом fire ИЛИ (life рядом с fire без др. воды)
        let consumed = false;
        for (const [nq, nr] of neighborsOf(geometryKey, q, r)) {
          const n = getCell(nq, nr);
          if (!n) continue;
          if (n.state === STATE.FIRE) { consumed = true; break; }
          if (n.state === STATE.LIFE) {
            const { counts: lifeNeighborCounts } = neighborCounts(nq, nr);
            if (lifeNeighborCounts[STATE.FIRE] > 0) { consumed = true; break; }
          }
        }
        if (consumed) {
          result = { state: STATE.STEAM, age: 0 };
        } else if (params.waterOverflowEnabled && overflowSources.has(k)) {
          // Эта вода перетекла в пустоту/пепел соседа — на её месте остаётся берег.
          result = { state: STATE.EARTH, age: 0 };
        } else {
          result = { state: STATE.WATER, age: cell.age + 1 };
        }
        break;
      }

      case STATE.EARTH: {
        // Оживление земли: ровно N соседей из {вода, жизнь} (по умолчанию 3),
        // и среди них есть хотя бы одна жизнь (земля не оживает от одной воды).
        const w = counts[STATE.WATER];
        const l = counts[STATE.LIFE];
        const sumWL = w + l;
        const canBirth = l >= 1 && sumWL === params.birthCount;
        if (canBirth) {
          result = { state: STATE.LIFE, age: 0 };
        } else if (
          counts[STATE.WATER] === 0 &&
          params.lightningChance > 0 &&
          rng() < params.lightningChance * 0.5
        ) {
          // Молния может поджечь сухую землю (растительность/торф), запуская новый цикл огня.
          result = { state: STATE.FIRE, age: 0 };
        } else if (
          params.earthDryoutChance > 0 &&
          counts[STATE.WATER] === 0 &&
          (cell.age || 0) >= params.earthDryoutMinAge &&
          rng() < params.earthDryoutChance
        ) {
          result = { state: STATE.EMPTY, age: 0 };
        } else {
          result = { state: STATE.EARTH, age: cell.age + 1 };
        }
        break;
      }

      case STATE.STEAM: {
        if ((cell.age || 0) >= params.steamRainTicks - 1) {
          result = { state: STATE.WATER, age: 0 }; // дождь
        } else {
          result = { state: STATE.STEAM, age: cell.age + 1 };
        }
        break;
      }

      case STATE.ASH: {
        const hasWater = counts[STATE.WATER] > 0;
        const hasLife = counts[STATE.LIFE] > 0;
        const gotOverflow = params.waterOverflowEnabled && overflowTargets.has(k);
        const wetStreak = hasWater ? (cell.wetStreak || 0) + 1 : 0;
        if (hasWater && hasLife) {
          // Пепел рядом и с водой, и с жизнью — жизнь "удобряет" пепел, восстановление мгновенное.
          result = { state: STATE.EARTH, age: 0 };
        } else if (gotOverflow) {
          // Перелитая вода долила именно эту клетку пепла — она становится водой, как и пустота.
          result = { state: STATE.WATER, age: 0 };
        } else if (hasWater && wetStreak >= params.ashToEarthTicks) {
          result = { state: STATE.EARTH, age: 0 };
        } else {
          // age растёт всегда, пока клетка остаётся пеплом — это её "возраст пустования"
          // (важно для критерия победы в режиме головоломки). wetStreak — отдельный счётчик
          // "сколько тиков подряд рядом есть вода", используется только для перехода в землю.
          result = { state: STATE.ASH, age: (cell.age || 0) + 1, wetStreak };
        }
        break;
      }

      case STATE.EMPTY: {
        const hasWater = counts[STATE.WATER] > 0;
        const hasLife = counts[STATE.LIFE] > 0;
        if (hasWater && hasLife) {
          // Жизнь с водой под боком распахивает целину — пустота (как и пепел) становится землёй.
          result = { state: STATE.EARTH, age: 0 };
        } else if (params.waterOverflowEnabled && overflowTargets.has(k)) {
          result = { state: STATE.WATER, age: 0 };
        } else if (counts[STATE.FIRE] >= 2 && rng() < params.fireSpreadChance) {
          result = { state: STATE.FIRE, age: 0 };
        } else {
          // age растёт всегда, пока клетка остаётся пустой — нужно для критерия победы
          // в режиме головоломки ("пустота не должна задерживаться дольше N тиков").
          result = { state: STATE.EMPTY, age: (cell.age || 0) + 1 };
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

// ---------- Экспорт публичного API движка ----------
// Этот блок не несёт игровой логики — только делает функции/константы
// выше доступными для импорта из других модулей (UI слой, тесты, воркеры).

export {
  STATE,
  COLORS,
  STATE_LABELS,
  GEOMETRIES,
  GEOMETRY_PRESETS,
  GEOMETRY_LEVELS,
  PRESETS, // = GEOMETRY_PRESETS.hex, для обратной совместимости
  LEVELS,  // = GEOMETRY_LEVELS.hex, для обратной совместимости
  PUZZLE_RADIUS,
  WIN_MAX_AGE,
  WIN_STABLE_TICKS,
  HEX_DIRS,
  SQUARE_DIRS,
  neighborsOf,
  key,
  makeGrid,
  makeHexagonalGrid,
  makeSquareGrid,
  gridCellCount,
  hexGridCellCount,
  squareGridCellCount,
  fullNeighborCount,
  mulberry32,
  randomCell,
  buildInitialField,
  levelRandomCell,
  buildLevelField,
  checkPuzzleWinTick,
  countWater,
  stepField,
};
