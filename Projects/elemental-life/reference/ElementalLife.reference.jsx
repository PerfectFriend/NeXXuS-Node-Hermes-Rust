import React, { useState, useRef, useCallback, useEffect, useMemo } from "react";

/**
 * ЭЛЕМЕНТАРНАЯ ЖИЗНЬ
 * Гексагональный клеточный автомат на основе "Жизни" Конвея,
 * расширенный четырьмя стихиями: огонь, вода, воздух (пар), земля.
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
 * ЗАКОН СОХРАНЕНИЯ ВОДЫ:
 *   total(water) + total(steam) = const на протяжении всей симуляции.
 *   Вода не создаётся и не уничтожается — только меняет агрегатное состояние
 *   (water -> steam при тушении огня жизнью) или физически перемещается
 *   (перелив воды в пустоту/пепел).
 */

// ---------- Геометрия гекс-сетки (axial coordinates, flat-top) ----------

const DIRS = [
  [+1, 0], [+1, -1], [0, -1],
  [-1, 0], [-1, +1], [0, +1],
];

function neighborsOf(q, r) {
  return DIRS.map(([dq, dr]) => [q + dq, r + dr]);
}

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

const PRESETS = {
  classic_balanced: {
    label: "Классика стихий (стабильный)",
    description: "Сбалансированный цикл воды и жизни — выходит на устойчивое плато.",
    params: {
      fireSpreadChance: 0.0,
      overpopulationIgniteTicks: 4, // через сколько тиков перенаселённая жизнь без воды самовоспламеняется
      lightningChance: 0.002,
      survMin: 0, // минимум живых соседей, чтобы клетка life не угасла
      birthCount: 3, // сумма (вода+жизнь) соседей у земли для оживления
      lifeOverpopulation: 6, // от скольких соседей life клетка гибнет/перегревается
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
};

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

function buildInitialField(radius, seed) {
  const rng = mulberry32(seed);
  const field = new Map();
  for (const { q, r } of makeHexagonalGrid(radius)) {
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

const LEVELS = [
  { id: 1, label: "Уровень 1", waterDensity: 0.35, lifeDensity: 0.08, earthDensity: 0.25, droplets: 55 },
  { id: 2, label: "Уровень 2", waterDensity: 0.28, lifeDensity: 0.08, earthDensity: 0.25, droplets: 65 },
  { id: 3, label: "Уровень 3", waterDensity: 0.22, lifeDensity: 0.08, earthDensity: 0.25, droplets: 80 },
  { id: 4, label: "Уровень 4", waterDensity: 0.16, lifeDensity: 0.08, earthDensity: 0.25, droplets: 100 },
  { id: 5, label: "Уровень 5", waterDensity: 0.10, lifeDensity: 0.08, earthDensity: 0.25, droplets: 115 },
];
const PUZZLE_RADIUS = 8; // меньшее поле для головоломки — 217 клеток, удобно для ручного клика

function levelRandomCell(rng, level) {
  const v = rng();
  if (v < level.lifeDensity) return { state: STATE.LIFE, age: 0 };
  if (v < level.lifeDensity + level.earthDensity) return { state: STATE.EARTH, age: 0 };
  if (v < level.lifeDensity + level.earthDensity + level.waterDensity) {
    return { state: STATE.WATER, age: 0 };
  }
  return { state: STATE.EMPTY, age: 0 };
}

function buildLevelField(radius, seed, level) {
  const rng = mulberry32(seed);
  const field = new Map();
  for (const { q, r } of makeHexagonalGrid(radius)) {
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

function stepField(field, radius, params, rng) {
  const next = new Map();

  const getCell = (q, r) => field.get(key(q, r)) || null;

  // Предрасчёт соседей по типам для каждой клетки
  function neighborCounts(q, r) {
    const counts = {
      [STATE.EMPTY]: 0, [STATE.LIFE]: 0, [STATE.FIRE]: 0,
      [STATE.WATER]: 0, [STATE.EARTH]: 0, [STATE.STEAM]: 0, [STATE.ASH]: 0,
    };
    const list = [];
    for (const [nq, nr] of neighborsOf(q, r)) {
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
    for (const { q, r } of makeHexagonalGrid(radius)) {
      const cell = getCell(q, r);
      if (!cell || cell.state !== STATE.WATER) continue;
      const { counts, list } = neighborCounts(q, r);
      if (counts[STATE.WATER] !== 6) continue; // полностью окружена водой
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

  for (const { q, r } of makeHexagonalGrid(radius)) {
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
        for (const [nq, nr] of neighborsOf(q, r)) {
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

// ---------- Геометрия рисования (flat-top hexagons) ----------

function axialToPixel(q, r, size) {
  const x = size * (1.5 * q);
  const y = size * (Math.sqrt(3) * (r + q / 2));
  return [x, y];
}

function hexPoints(cx, cy, size) {
  const pts = [];
  for (let i = 0; i < 6; i++) {
    const angle = (Math.PI / 180) * (60 * i);
    pts.push([cx + size * Math.cos(angle), cy + size * Math.sin(angle)]);
  }
  return pts.map((p) => p.join(",")).join(" ");
}

// ---------- React-компонент ----------

export default function ElementalLife() {
  const [mode, setMode] = useState("sandbox"); // sandbox | puzzle
  const [presetKey, setPresetKey] = useState("classic_balanced");
  const [params, setParams] = useState(PRESETS.classic_balanced.params);
  const [side] = useState(30); // сторона большого гексагона в малых клетках (только для sandbox)

  const [levelIndex, setLevelIndex] = useState(0);
  const [levelSeed, setLevelSeed] = useState(1);
  const [dropletsLeft, setDropletsLeft] = useState(LEVELS[0].droplets);
  const [winStreak, setWinStreak] = useState(0);
  const [puzzleWon, setPuzzleWon] = useState(false);
  const [puzzleFailed, setPuzzleFailed] = useState(false);

  const radius = mode === "puzzle" ? PUZZLE_RADIUS : side - 1;
  const hexSize = mode === "puzzle" ? 22 : 9; // в головоломке клетки крупнее — удобнее кликать
  const width = hexSize * 1.5 * (2 * radius + 1) + hexSize * 4;
  const height = hexSize * Math.sqrt(3) * (2 * radius + 2) + hexSize * 4;

  const currentLevel = LEVELS[levelIndex];

  const [seed, setSeed] = useState(42);
  const [field, setField] = useState(() => buildInitialField(29, 42));
  const [running, setRunning] = useState(false);
  const [speed, setSpeed] = useState(220); // ms per tick
  const [tick, setTick] = useState(0);
  const [brush, setBrush] = useState(STATE.LIFE);
  const [waterHistory, setWaterHistory] = useState([]);
  const [showPanel, setShowPanel] = useState(true);
  const [activeTab, setActiveTab] = useState("presets"); // presets | tuning | chart | rules

  // ---- Полноэкранный режим ----
  const appRef = useRef(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      appRef.current?.requestFullscreen?.().catch(() => {});
    } else {
      document.exitFullscreen?.().catch(() => {});
    }
  }, []);

  useEffect(() => {
    const onChange = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  // ---- Масштаб (зум) и панорамирование поля ----
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const minZoom = 0.15;
  const maxZoom = 4;
  const viewportRef = useRef(null);
  const dragState = useRef(null);
  const pinchState = useRef(null);

  const clampZoom = (z) => Math.min(maxZoom, Math.max(minZoom, z));

  const zoomBy = useCallback((factor, centerX, centerY) => {
    setZoom((prevZoom) => {
      const nextZoom = clampZoom(prevZoom * factor);
      const ratio = nextZoom / prevZoom;
      if (centerX !== undefined && viewportRef.current) {
        setPan((prevPan) => ({
          x: centerX - (centerX - prevPan.x) * ratio,
          y: centerY - (centerY - prevPan.y) * ratio,
        }));
      }
      return nextZoom;
    });
  }, []);

  const handleWheel = useCallback((e) => {
    e.preventDefault();
    const rect = viewportRef.current.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
    zoomBy(factor, cx, cy);
  }, [zoomBy]);

  const handlePointerDown = useCallback((e) => {
    if (e.touches && e.touches.length === 2) {
      const [t1, t2] = e.touches;
      pinchState.current = {
        dist: Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY),
        zoom,
      };
      return;
    }
    const point = e.touches ? e.touches[0] : e;
    dragState.current = {
      startX: point.clientX,
      startY: point.clientY,
      panX: pan.x,
      panY: pan.y,
      moved: false,
    };
  }, [pan, zoom]);

  const handlePointerMove = useCallback((e) => {
    if (e.touches && e.touches.length === 2 && pinchState.current) {
      const [t1, t2] = e.touches;
      const dist = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY);
      const factor = dist / pinchState.current.dist;
      setZoom(clampZoom(pinchState.current.zoom * factor));
      return;
    }
    if (!dragState.current) return;
    const point = e.touches ? e.touches[0] : e;
    const dx = point.clientX - dragState.current.startX;
    const dy = point.clientY - dragState.current.startY;
    if (Math.abs(dx) > 3 || Math.abs(dy) > 3) dragState.current.moved = true;
    setPan({ x: dragState.current.panX + dx, y: dragState.current.panY + dy });
  }, []);

  const handlePointerUp = useCallback(() => {
    dragState.current = null;
    pinchState.current = null;
  }, []);

  const resetView = useCallback(() => {
    if (viewportRef.current) {
      const rect = viewportRef.current.getBoundingClientRect();
      const fitZoom = clampZoom(
        Math.min(rect.width / width, rect.height / height) * 0.94
      );
      setZoom(fitZoom);
      setPan({
        x: (rect.width - width * fitZoom) / 2,
        y: (rect.height - height * fitZoom) / 2,
      });
    } else {
      setZoom(1);
      setPan({ x: 0, y: 0 });
    }
  }, [width, height]);

  useEffect(() => {
    // Подгоняем масштаб под вьюпорт сразу после монтирования.
    const id = requestAnimationFrame(() => resetView());
    return () => cancelAnimationFrame(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    // При входе/выходе из полноэкранного режима размер вьюпорта меняется — пересчитываем вид.
    const id = requestAnimationFrame(() => resetView());
    return () => cancelAnimationFrame(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isFullscreen]);

  useEffect(() => {
    // При смене режима (песочница/головоломка) меняется размер и форма поля — пересчитываем вид.
    const id = requestAnimationFrame(() => resetView());
    return () => cancelAnimationFrame(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, width, height]);

  const rngRef = useRef(mulberry32(seed + 999));
  const intervalRef = useRef(null);
  const initialWaterRef = useRef(null);

  const applyPreset = useCallback((pKey) => {
    setPresetKey(pKey);
    setParams(PRESETS[pKey].params);
  }, []);

  const startLevel = useCallback((index, newSeed) => {
    const lvl = LEVELS[index];
    const s = newSeed ?? Math.floor(Math.random() * 1e9);
    setLevelIndex(index);
    setLevelSeed(s);
    setField(buildLevelField(PUZZLE_RADIUS, s, lvl));
    setDropletsLeft(lvl.droplets);
    setWinStreak(0);
    setPuzzleWon(false);
    setPuzzleFailed(false);
    rngRef.current = mulberry32(s + 999);
    setTick(0);
    setWaterHistory([]);
    setRunning(true);
    initialWaterRef.current = null;
  }, []);

  const goToNextLevel = useCallback(() => {
    const nextIndex = Math.min(levelIndex + 1, LEVELS.length - 1);
    startLevel(nextIndex, Math.floor(Math.random() * 1e9));
  }, [levelIndex, startLevel]);

  const retryLevel = useCallback(() => {
    startLevel(levelIndex, Math.floor(Math.random() * 1e9));
  }, [levelIndex, startLevel]);

  const switchMode = useCallback((nextMode) => {
    setMode(nextMode);
    setRunning(false);
    if (nextMode === "puzzle") {
      startLevel(0, 1);
      setActiveTab((t) => (t === "presets" || t === "tuning" ? "chart" : t));
    } else {
      setField(buildInitialField(side - 1, seed));
      setTick(0);
      setWaterHistory([]);
      initialWaterRef.current = null;
    }
  }, [startLevel, side, seed]);

  const reset = useCallback((newSeed) => {
    const s = newSeed ?? Math.floor(Math.random() * 1e9);
    setSeed(s);
    setField(buildInitialField(radius, s));
    rngRef.current = mulberry32(s + 999);
    setTick(0);
    setWaterHistory([]);
    initialWaterRef.current = null;
  }, [radius]);

  const dropletsRanOutTickRef = useRef(Infinity);
  useEffect(() => {
    if (mode === "puzzle" && dropletsLeft <= 0 && dropletsRanOutTickRef.current === Infinity) {
      dropletsRanOutTickRef.current = tick;
    }
    if (dropletsLeft > 0) {
      dropletsRanOutTickRef.current = Infinity;
    }
  }, [dropletsLeft, mode, tick]);

  const doStep = useCallback(() => {
    setField((prev) => {
      const nextField = stepField(prev, radius, params, rngRef.current);
      const w = countWater(nextField);
      setWaterHistory((h) => [...h.slice(-119), w.total]);

      if (mode === "puzzle" && !puzzleWon) {
        const tickOk = checkPuzzleWinTick(nextField);
        if (tickOk) {
          setWinStreak((s) => {
            const next = s + 1;
            if (next >= WIN_STABLE_TICKS) {
              setPuzzleWon(true);
              setRunning(false);
            }
            return next;
          });
        } else {
          setWinStreak(0);
        }
      }
      return nextField;
    });
    setTick((t) => {
      const nextTick = t + 1;
      if (
        mode === "puzzle" &&
        !puzzleWon &&
        dropletsLeft <= 0 &&
        nextTick - dropletsRanOutTickRef.current > 80
      ) {
        setPuzzleFailed(true);
        setRunning(false);
      }
      return nextTick;
    });
  }, [radius, params, mode, puzzleWon, dropletsLeft]);

  useEffect(() => {
    if (running) {
      intervalRef.current = setInterval(doStep, speed);
      return () => clearInterval(intervalRef.current);
    }
  }, [running, speed, doStep]);

  const waterStats = useMemo(() => countWater(field), [field]);

  useEffect(() => {
    if (initialWaterRef.current === null) {
      initialWaterRef.current = countWater(field).total;
    }
  }, [field]);

  const handleCellClick = useCallback((q, r) => {
    if (mode === "puzzle") {
      if (puzzleWon || dropletsLeft <= 0) return;
      const k = key(q, r);
      const current = field.get(k);
      if (!current || (current.state !== STATE.EMPTY && current.state !== STATE.ASH)) {
        return; // в головоломке капля льётся только на пустоту/пепел
      }
      setField((prev) => {
        const next = new Map(prev);
        next.set(k, { state: STATE.WATER, age: 0 });
        return next;
      });
      setDropletsLeft((d) => Math.max(0, d - 1));
      return;
    }
    setField((prev) => {
      const k = key(q, r);
      const next = new Map(prev);
      next.set(k, { state: brush, age: 0 });
      return next;
    });
  }, [brush, mode, puzzleWon, dropletsLeft, field]);

  const counts = useMemo(() => {
    const c = {
      [STATE.EMPTY]: 0, [STATE.LIFE]: 0, [STATE.FIRE]: 0,
      [STATE.WATER]: 0, [STATE.EARTH]: 0, [STATE.STEAM]: 0, [STATE.ASH]: 0,
    };
    for (const cell of field.values()) c[cell.state]++;
    return c;
  }, [field]);

  const totalCells = useMemo(
    () => (mode === "puzzle" ? hexGridCellCount(PUZZLE_RADIUS + 1) : hexGridCellCount(side)),
    [mode, side]
  );

  const cellsArray = useMemo(() => makeHexagonalGrid(radius), [radius]);

  const waterDrift = waterStats.total - (initialWaterRef.current ?? waterStats.total);

  return (
    <div ref={appRef} style={{ ...styles.app, ...(isFullscreen ? styles.appFullscreen : null) }}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Элементарная жизнь</h1>
          <p style={styles.subtitle}>
            Гексагональное поле со стороной 30 клеток — жизнь, огонь, вода, воздух, земля
          </p>
        </div>
        <div style={styles.headerBtns}>
          <div style={styles.modeSwitch}>
            <button
              style={{ ...styles.modeBtn, ...(mode === "sandbox" ? styles.modeBtnActive : null) }}
              onClick={() => mode !== "sandbox" && switchMode("sandbox")}
            >
              🧪 Песочница
            </button>
            <button
              style={{ ...styles.modeBtn, ...(mode === "puzzle" ? styles.modeBtnActive : null) }}
              onClick={() => mode !== "puzzle" && switchMode("puzzle")}
            >
              💧 Головоломка
            </button>
          </div>
          <button style={styles.panelToggle} onClick={toggleFullscreen} title="Полноэкранный режим">
            {isFullscreen ? "⤓ Выйти" : "⛶ Во весь экран"}
          </button>
          <button style={styles.panelToggle} onClick={() => setShowPanel((s) => !s)}>
            {showPanel ? "Скрыть панель" : "Параметры"}
          </button>
        </div>
      </div>

      <div style={styles.layout}>
        <div style={styles.boardWrap}>
          {mode === "puzzle" ? (
            <div style={styles.puzzleBar}>
              <div style={styles.puzzleLevelBadge}>
                {currentLevel.label} / {LEVELS.length}
              </div>
              <div style={styles.puzzleDroplets}>
                💧 Капель осталось: <b>{dropletsLeft}</b>
              </div>
              <button style={styles.btnPrimary} onClick={() => setRunning((r) => !r)}>
                {running ? "⏸ Пауза" : "▶ Старт"}
              </button>
              <button style={styles.btn} onClick={retryLevel}>⟳ Заново</button>
              <div style={styles.speedControl}>
                <span style={styles.speedLabel}>Скорость</span>
                <input
                  type="range"
                  min={40}
                  max={600}
                  step={20}
                  value={650 - speed}
                  onChange={(e) => setSpeed(650 - Number(e.target.value))}
                  style={{ width: 110 }}
                />
              </div>
              <div style={styles.tickBadge}>тик: {tick}</div>
              <div style={styles.zoomControl}>
                <button style={styles.zoomBtn} onClick={() => zoomBy(1 / 1.25)}>−</button>
                <span style={styles.zoomLabel}>{Math.round(zoom * 100)}%</span>
                <button style={styles.zoomBtn} onClick={() => zoomBy(1.25)}>+</button>
                <button style={styles.zoomResetBtn} onClick={resetView}>⤾</button>
              </div>
            </div>
          ) : (
          <div style={styles.toolbar}>
            <button style={styles.btnPrimary} onClick={() => setRunning((r) => !r)}>
              {running ? "⏸ Пауза" : "▶ Старт"}
            </button>
            <button style={styles.btn} onClick={doStep}>⏭ Шаг</button>
            <button style={styles.btn} onClick={() => reset()}>⟳ Новое поле</button>
            <div style={styles.speedControl}>
              <span style={styles.speedLabel}>Скорость</span>
              <input
                type="range"
                min={40}
                max={600}
                step={20}
                value={650 - speed}
                onChange={(e) => setSpeed(650 - Number(e.target.value))}
                style={{ width: 110 }}
              />
            </div>
            <div style={styles.tickBadge}>тик: {tick}</div>
            <div style={styles.zoomControl}>
              <button style={styles.zoomBtn} onClick={() => zoomBy(1 / 1.25)}>−</button>
              <span style={styles.zoomLabel}>{Math.round(zoom * 100)}%</span>
              <button style={styles.zoomBtn} onClick={() => zoomBy(1.25)}>+</button>
              <button style={styles.zoomResetBtn} onClick={resetView}>⤾</button>
            </div>
          </div>
          )}

          {mode === "puzzle" ? (
            <div style={styles.brushRow}>
              <span style={styles.hint}>💧 кликай по пустоте/пеплу, чтобы залить их водой · колесо мыши / пинч — зум</span>
            </div>
          ) : (
          <div style={styles.brushRow}>
            {Object.values(STATE).map((s) => (
              <button
                key={s}
                onClick={() => setBrush(s)}
                style={{
                  ...styles.brushBtn,
                  borderColor: brush === s ? "#fff" : "transparent",
                  background: COLORS[s],
                }}
                title={STATE_LABELS[s]}
              >
                <span style={styles.brushLabel}>{STATE_LABELS[s]}</span>
              </button>
            ))}
            <span style={styles.hint}>кликай по клеткам, чтобы рисовать стихии · колесо мыши / пинч — зум, перетаскивание — панорама</span>
          </div>
          )}

          <div
            ref={viewportRef}
            style={styles.svgWrap}
            onWheel={handleWheel}
            onMouseDown={handlePointerDown}
            onMouseMove={handlePointerMove}
            onMouseUp={handlePointerUp}
            onMouseLeave={handlePointerUp}
            onTouchStart={handlePointerDown}
            onTouchMove={handlePointerMove}
            onTouchEnd={handlePointerUp}
          >
            <div
              style={{
                transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                transformOrigin: "0 0",
                width: "fit-content",
                cursor: dragState.current?.moved ? "grabbing" : "grab",
              }}
            >
              <svg width={width} height={height} style={styles.svg}>
                {cellsArray.map(({ q, r }) => {
                  const [x, y] = axialToPixel(q, r, hexSize);
                  const cell = field.get(key(q, r));
                  if (!cell) return null;
                  return (
                    <polygon
                      key={key(q, r)}
                      points={hexPoints(x + width / 2, y + height / 2, hexSize - 0.6)}
                      fill={COLORS[cell.state]}
                      stroke="#05070a"
                      strokeWidth={0.5}
                      onClick={() => handleCellClick(q, r)}
                      style={{ cursor: "pointer" }}
                    />
                  );
                })}
              </svg>
            </div>

            {mode === "puzzle" && (puzzleWon || puzzleFailed) && (
              <div style={styles.puzzleOverlay}>
                <div style={styles.puzzleOverlayCard}>
                  {puzzleWon ? (
                    <>
                      <div style={styles.puzzleOverlayTitle}>🌿 Уровень пройден!</div>
                      <div style={styles.puzzleOverlayText}>
                        Экосистема сама исцеляет любую новую пустоту — порядок наведён.
                      </div>
                      {levelIndex < LEVELS.length - 1 ? (
                        <button style={styles.btnPrimary} onClick={goToNextLevel}>
                          Следующий уровень →
                        </button>
                      ) : (
                        <div style={styles.puzzleOverlayText}>Это был последний уровень — ты прошёл всю головоломку!</div>
                      )}
                      <button style={styles.btn} onClick={retryLevel}>Переиграть</button>
                    </>
                  ) : (
                    <>
                      <div style={styles.puzzleOverlayTitle}>💀 Капли закончились</div>
                      <div style={styles.puzzleOverlayText}>
                        Пустота и пепел не зажили достаточно быстро — попробуй другую стратегию полива.
                      </div>
                      <button style={styles.btnPrimary} onClick={retryLevel}>Попробовать снова</button>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>

          {mode === "puzzle" && !puzzleWon && !puzzleFailed && (
            <div style={styles.winProgressBar}>
              <div style={styles.winProgressHeader}>
                <span>Стабильность экосистемы</span>
                <span>{winStreak} / {WIN_STABLE_TICKS} тиков подряд без пустоты</span>
              </div>
              <div style={styles.winProgressTrack}>
                <div
                  style={{
                    ...styles.winProgressFill,
                    width: `${Math.min(100, (winStreak / WIN_STABLE_TICKS) * 100)}%`,
                  }}
                />
              </div>
            </div>
          )}

          <div style={styles.waterBar}>
            <div style={styles.waterBarHeader}>
              <span>Закон сохранения воды</span>
              <span style={{
                color: Math.abs(waterDrift) === 0 ? "#2ecc71" : "#ff5a36",
                fontWeight: 700,
              }}>
                {waterDrift === 0 ? "✓ соблюдён" : `Δ ${waterDrift > 0 ? "+" : ""}${waterDrift}`}
              </span>
            </div>
            <div style={styles.waterBarRow}>
              <span>Вода: {waterStats.water}</span>
              <span>Пар: {waterStats.steam}</span>
              <span>Σ = {waterStats.total} (исходно {initialWaterRef.current})</span>
            </div>
          </div>

          <div style={styles.statsRow}>
            {Object.values(STATE).map((s) => (
              <div key={s} style={styles.statChip}>
                <span style={{ ...styles.statDot, background: COLORS[s] }} />
                <span>{STATE_LABELS[s]}</span>
                <b>{counts[s]}</b>
                <span style={styles.statPct}>
                  {((counts[s] / totalCells) * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>

        {showPanel && (
          <div style={styles.panel}>
            <div style={styles.tabBar}>
              {(mode === "puzzle"
                ? [
                    { id: "chart", label: "График" },
                    { id: "rules", label: "Правила" },
                  ]
                : [
                    { id: "presets", label: "Пресеты" },
                    { id: "tuning", label: "Настройка" },
                    { id: "chart", label: "График" },
                    { id: "rules", label: "Правила" },
                  ]
              ).map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  style={{
                    ...styles.tabBtn,
                    ...(activeTab === tab.id ? styles.tabBtnActive : null),
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div style={styles.tabContent}>
              {activeTab === "presets" && (
                <div style={styles.presetList}>
                  {Object.entries(PRESETS).map(([k, p]) => (
                    <button
                      key={k}
                      onClick={() => applyPreset(k)}
                      style={{
                        ...styles.presetBtn,
                        borderColor: presetKey === k ? "#2ecc71" : "#2a2f3a",
                        background: presetKey === k ? "#163322" : "#161a22",
                      }}
                    >
                      <div style={styles.presetLabel}>{p.label}</div>
                      <div style={styles.presetDesc}>{p.description}</div>
                    </button>
                  ))}
                </div>
              )}

              {activeTab === "tuning" && (
                <>
                  <ParamSlider
                    label="Перенаселение без воды → самовозгорание через N тиков"
                    value={params.overpopulationIgniteTicks}
                    min={1} max={5} step={1}
                    onChange={(v) => setParams((p) => ({ ...p, overpopulationIgniteTicks: v }))}
                  />
                  <ParamSlider
                    label="Молния (шанс случайного возгорания)"
                    value={params.lightningChance}
                    min={0} max={0.02} step={0.0005}
                    onChange={(v) => setParams((p) => ({ ...p, lightningChance: v }))}
                  />
                  <ParamSlider
                    label="Шанс распространения огня в пустоту"
                    value={params.fireSpreadChance}
                    min={0} max={1} step={0.05}
                    onChange={(v) => setParams((p) => ({ ...p, fireSpreadChance: v }))}
                  />
                  <ParamSlider
                    label="Минимум соседей для выживания жизни"
                    value={params.survMin}
                    min={0} max={3} step={1}
                    onChange={(v) => setParams((p) => ({ ...p, survMin: v }))}
                  />
                  <ParamSlider
                    label="Перенаселение жизни (соседей)"
                    value={params.lifeOverpopulation}
                    min={3} max={6} step={1}
                    onChange={(v) => setParams((p) => ({ ...p, lifeOverpopulation: v }))}
                  />
                  <ParamSlider
                    label="Рождение земли: сумма соседей вода+жизнь"
                    value={params.birthCount}
                    min={1} max={6} step={1}
                    onChange={(v) => setParams((p) => ({ ...p, birthCount: v }))}
                  />
                  <ParamSlider
                    label="Шанс высыхания земли"
                    value={params.earthDryoutChance}
                    min={0} max={0.1} step={0.005}
                    onChange={(v) => setParams((p) => ({ ...p, earthDryoutChance: v }))}
                  />
                  <ParamSlider
                    label="Возраст земли для высыхания (тиков)"
                    value={params.earthDryoutMinAge}
                    min={1} max={20} step={1}
                    onChange={(v) => setParams((p) => ({ ...p, earthDryoutMinAge: v }))}
                  />
                  <ParamSlider
                    label="Пепел → земля (тиков с водой рядом)"
                    value={params.ashToEarthTicks}
                    min={1} max={5} step={1}
                    onChange={(v) => setParams((p) => ({ ...p, ashToEarthTicks: v }))}
                  />
                  <label style={styles.checkboxRow}>
                    <input
                      type="checkbox"
                      checked={params.waterOverflowEnabled}
                      onChange={(e) =>
                        setParams((p) => ({ ...p, waterOverflowEnabled: e.target.checked }))
                      }
                    />
                    Перелив воды в пустоты (острова)
                  </label>
                </>
              )}

              {activeTab === "chart" && (
                <>
                  <h3 style={styles.panelTitle}>График воды (последние тики)</h3>
                  <MiniChart history={waterHistory} />
                  <h3 style={styles.panelTitle}>Текущее состояние поля</h3>
                  <div style={styles.statsRowVertical}>
                    {Object.values(STATE).map((s) => (
                      <div key={s} style={styles.statChip}>
                        <span style={{ ...styles.statDot, background: COLORS[s] }} />
                        <span>{STATE_LABELS[s]}</span>
                        <b>{counts[s]}</b>
                        <span style={styles.statPct}>
                          {((counts[s] / totalCells) * 100).toFixed(0)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {activeTab === "rules" && (
                <>
                  {mode === "puzzle" && (
                    <>
                      <h3 style={styles.panelTitle}>Режим головоломки</h3>
                      <ul style={styles.rulesList}>
                        <li>💧 Капля воды мгновенно заливает клетку пустоты или пепла.</li>
                        <li>🌍 Мир продолжает жить сам по себе (огонь, перенаселение, молния) — капли льются "на лету".</li>
                        <li>🏆 Победа: пустота и пепел не задерживаются на поле дольше {WIN_MAX_AGE} тиков подряд, и это держится стабильно {WIN_STABLE_TICKS} тиков — экосистема сама исцеляет редкие пожары.</li>
                        <li>💀 Если капли закончились и порядок долго не наводится — уровень придётся начать заново.</li>
                        <li>📈 С каждым уровнём изначальной воды меньше, но и капель у тебя больше — расставляй их с умом.</li>
                      </ul>
                    </>
                  )}
                  <h3 style={styles.panelTitle}>Правила симуляции</h3>
                  <ul style={styles.rulesList}>
                    <li>🔥🌱 Перенаселение (5-6 соседей-жизни) без воды рядом — клетка перегревается и через несколько тиков самовоспламеняется.</li>
                    <li>🔥➡️🌱 Возникший огонь обязательно перекидывается на соседнюю жизнь, если у неё нет своей воды.</li>
                    <li>💧 Жизнь с водой рядом гасит огонь и спасается: вода испаряется в пар, на её месте остаётся земля.</li>
                    <li>⚡ Молния — отдельный редкий случайный поджиг (не от перенаселения), чтобы цикл стихий не замирал.</li>
                    <li>🔥 Огонь без воды живёт 2 тика, затем гаснет в пепел.</li>
                    <li>☁️ Пар выпадает дождём (водой) через 1 тик.</li>
                    <li>🌾 Пустота или пепел рядом и с водой, и с жизнью одновременно — жизнь распахивает целину, превращая клетку в землю.</li>
                    <li>⬛ Без жизни рядом пепел становится землёй медленнее — после 2 тиков подряд с водой.</li>
                    <li>🌱 Земля оживает, если среди её соседей есть хотя бы 1 жизнь, а сумма (вода+жизнь) соседей равна заданному числу (по умолчанию 3).</li>
                    <li>🌊 Вода в окружении 6 воды перетекает в соседнюю пустоту/пепел, оставляя землю (берег).</li>
                    <li>⚖️ Суммарно (вода + пар) — неизменная величина во всей системе, проверяется счётчиком на экране.</li>
                  </ul>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ParamSlider({ label, value, min, max, step, onChange }) {
  return (
    <div style={styles.sliderRow}>
      <div style={styles.sliderLabelRow}>
        <span style={styles.sliderLabel}>{label}</span>
        <span style={styles.sliderValue}>{value}</span>
      </div>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        style={{ width: "100%" }}
      />
    </div>
  );
}

function MiniChart({ history }) {
  if (history.length < 2) {
    return <div style={styles.chartEmpty}>Запусти симуляцию, чтобы увидеть график</div>;
  }
  const w = 260, h = 60;
  const max = Math.max(...history, 1);
  const min = Math.min(...history, 0);
  const range = Math.max(max - min, 1);
  const points = history
    .map((v, i) => {
      const x = (i / (history.length - 1)) * w;
      const y = h - ((v - min) / range) * h;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg width={w} height={h} style={{ background: "#10141b", borderRadius: 6 }}>
      <polyline points={points} fill="none" stroke="#2196f3" strokeWidth={1.5} />
    </svg>
  );
}

const styles = {
  app: {
    fontFamily: "'JetBrains Mono', 'Courier New', monospace",
    background: "#0a0c10",
    color: "#e6e9ef",
    minHeight: "100vh",
    padding: "20px 16px 40px",
  },
  appFullscreen: {
    minHeight: "100vh",
    height: "100vh",
    overflowY: "auto",
    padding: "16px 16px 24px",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: 16,
    flexWrap: "wrap",
    gap: 12,
  },
  headerBtns: {
    display: "flex",
    gap: 8,
    alignItems: "center",
    flexWrap: "wrap",
  },
  modeSwitch: {
    display: "flex",
    gap: 2,
    background: "#12161f",
    borderRadius: 6,
    padding: 3,
  },
  modeBtn: {
    background: "transparent",
    border: "none",
    color: "#8a93a3",
    borderRadius: 5,
    padding: "7px 12px",
    cursor: "pointer",
    fontSize: 12,
    fontFamily: "inherit",
  },
  modeBtnActive: {
    background: "#1f4d33",
    color: "#dffce9",
    fontWeight: 700,
  },
  title: {
    fontSize: 22,
    margin: 0,
    letterSpacing: 0.5,
  },
  subtitle: {
    margin: "4px 0 0",
    color: "#8a93a3",
    fontSize: 13,
  },
  panelToggle: {
    background: "#1a1f2a",
    border: "1px solid #2a2f3a",
    color: "#e6e9ef",
    borderRadius: 6,
    padding: "8px 14px",
    cursor: "pointer",
    fontSize: 12,
    height: "fit-content",
  },
  layout: {
    display: "flex",
    gap: 20,
    flexWrap: "wrap",
    alignItems: "flex-start",
  },
  boardWrap: {
    flex: "1 1 600px",
    minWidth: 320,
  },
  toolbar: {
    display: "flex",
    gap: 8,
    alignItems: "center",
    marginBottom: 10,
    flexWrap: "wrap",
  },
  puzzleBar: {
    display: "flex",
    gap: 10,
    alignItems: "center",
    marginBottom: 10,
    flexWrap: "wrap",
  },
  puzzleLevelBadge: {
    background: "#1f4d33",
    color: "#dffce9",
    borderRadius: 6,
    padding: "8px 12px",
    fontSize: 12,
    fontWeight: 700,
  },
  puzzleDroplets: {
    background: "#12161f",
    color: "#cfe8ff",
    borderRadius: 6,
    padding: "8px 12px",
    fontSize: 12,
  },
  btn: {
    background: "#1a1f2a",
    border: "1px solid #2a2f3a",
    color: "#e6e9ef",
    borderRadius: 6,
    padding: "8px 12px",
    cursor: "pointer",
    fontSize: 12,
  },
  btnPrimary: {
    background: "#1f4d33",
    border: "1px solid #2ecc71",
    color: "#dffce9",
    borderRadius: 6,
    padding: "8px 14px",
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 700,
  },
  speedControl: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    marginLeft: 4,
  },
  speedLabel: { fontSize: 11, color: "#8a93a3" },
  tickBadge: {
    marginLeft: "auto",
    fontSize: 12,
    color: "#8a93a3",
    background: "#12161f",
    padding: "4px 10px",
    borderRadius: 6,
  },
  brushRow: {
    display: "flex",
    gap: 6,
    alignItems: "center",
    marginBottom: 10,
    flexWrap: "wrap",
  },
  brushBtn: {
    border: "2px solid transparent",
    borderRadius: 5,
    padding: "5px 8px",
    cursor: "pointer",
  },
  brushLabel: {
    fontSize: 10,
    color: "#0a0c10",
    fontWeight: 700,
    textShadow: "0 1px 0 rgba(255,255,255,0.3)",
  },
  hint: {
    fontSize: 11,
    color: "#5b6577",
    marginLeft: 6,
  },
  svgWrap: {
    background: "#06080b",
    border: "1px solid #1c212b",
    borderRadius: 8,
    padding: 0,
    overflow: "hidden",
    height: "min(70vh, 620px)",
    position: "relative",
    touchAction: "none",
    userSelect: "none",
  },
  svg: { display: "block" },
  puzzleOverlay: {
    position: "absolute",
    inset: 0,
    background: "rgba(6,8,11,0.86)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 5,
  },
  puzzleOverlayCard: {
    background: "#0e1218",
    border: "1px solid #2a2f3a",
    borderRadius: 12,
    padding: "28px 32px",
    maxWidth: 360,
    textAlign: "center",
    display: "flex",
    flexDirection: "column",
    gap: 12,
    alignItems: "center",
  },
  puzzleOverlayTitle: {
    fontSize: 18,
    fontWeight: 700,
    color: "#dffce9",
  },
  puzzleOverlayText: {
    fontSize: 13,
    color: "#aab3c2",
    lineHeight: 1.5,
  },
  winProgressBar: {
    marginTop: 12,
    background: "#0e1218",
    border: "1px solid #1c212b",
    borderRadius: 8,
    padding: "10px 12px",
  },
  winProgressHeader: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 12,
    color: "#8a93a3",
    marginBottom: 8,
  },
  winProgressTrack: {
    height: 8,
    background: "#1c212b",
    borderRadius: 4,
    overflow: "hidden",
  },
  winProgressFill: {
    height: "100%",
    background: "linear-gradient(90deg, #2196f3, #2ecc71)",
    transition: "width 0.2s ease",
  },
  zoomControl: {
    display: "flex",
    alignItems: "center",
    gap: 4,
    marginLeft: 8,
    background: "#12161f",
    borderRadius: 6,
    padding: "3px 4px",
  },
  zoomBtn: {
    background: "#1a1f2a",
    border: "1px solid #2a2f3a",
    color: "#e6e9ef",
    borderRadius: 5,
    width: 26,
    height: 26,
    cursor: "pointer",
    fontSize: 14,
    lineHeight: 1,
  },
  zoomResetBtn: {
    background: "#1a1f2a",
    border: "1px solid #2a2f3a",
    color: "#8a93a3",
    borderRadius: 5,
    width: 26,
    height: 26,
    cursor: "pointer",
    fontSize: 12,
    lineHeight: 1,
  },
  zoomLabel: {
    fontSize: 11,
    color: "#8a93a3",
    minWidth: 38,
    textAlign: "center",
  },
  waterBar: {
    marginTop: 12,
    background: "#0e1218",
    border: "1px solid #1c212b",
    borderRadius: 8,
    padding: "10px 12px",
  },
  waterBarHeader: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 12,
    marginBottom: 6,
  },
  waterBarRow: {
    display: "flex",
    gap: 16,
    fontSize: 12,
    color: "#8a93a3",
  },
  statsRow: {
    display: "flex",
    gap: 10,
    flexWrap: "wrap",
    marginTop: 12,
  },
  statChip: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    background: "#12161f",
    borderRadius: 6,
    padding: "5px 10px",
    fontSize: 11,
  },
  statDot: {
    width: 9,
    height: 9,
    borderRadius: 2,
    display: "inline-block",
  },
  statPct: { color: "#5b6577" },
  panel: {
    flex: "0 0 300px",
    background: "#0e1218",
    border: "1px solid #1c212b",
    borderRadius: 10,
    padding: 16,
    maxHeight: "calc(100vh - 60px)",
    display: "flex",
    flexDirection: "column",
  },
  tabBar: {
    display: "flex",
    gap: 4,
    marginBottom: 14,
    borderBottom: "1px solid #1c212b",
    paddingBottom: 10,
    flexWrap: "wrap",
  },
  tabBtn: {
    background: "transparent",
    border: "none",
    color: "#8a93a3",
    borderRadius: 6,
    padding: "6px 10px",
    cursor: "pointer",
    fontSize: 12,
    fontFamily: "inherit",
  },
  tabBtnActive: {
    background: "#1f4d33",
    color: "#dffce9",
    fontWeight: 700,
  },
  tabContent: {
    overflowY: "auto",
    flex: 1,
    minHeight: 0,
  },
  panelTitle: {
    fontSize: 13,
    margin: "4px 0 10px",
    color: "#cfd8e3",
    borderBottom: "1px solid #1c212b",
    paddingBottom: 6,
  },
  statsRowVertical: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
  },
  presetList: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
    marginBottom: 18,
  },
  presetBtn: {
    textAlign: "left",
    border: "1px solid #2a2f3a",
    borderRadius: 8,
    padding: "8px 10px",
    cursor: "pointer",
    color: "#e6e9ef",
  },
  presetLabel: { fontSize: 12.5, fontWeight: 700, marginBottom: 2 },
  presetDesc: { fontSize: 10.5, color: "#8a93a3", lineHeight: 1.3 },
  sliderRow: { marginBottom: 12 },
  sliderLabelRow: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 11,
    color: "#aab3c2",
    marginBottom: 3,
  },
  sliderLabel: { flex: 1, paddingRight: 8 },
  sliderValue: { color: "#2ecc71", fontWeight: 700 },
  checkboxRow: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontSize: 12,
    margin: "10px 0 4px",
    cursor: "pointer",
  },
  rulesList: {
    fontSize: 11.5,
    color: "#aab3c2",
    lineHeight: 1.6,
    paddingLeft: 18,
    margin: 0,
  },
  chartEmpty: {
    fontSize: 11,
    color: "#5b6577",
  },
};
