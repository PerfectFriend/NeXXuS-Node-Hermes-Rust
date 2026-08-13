/**
 * useSimulation — главный хук состояния игры.
 *
 * Управляет:
 * - Игровым полем (field) и всеми параметрами симуляции
 * - Режимами: песочница (sandbox) и головоломка (puzzle)
 * - Циклом симуляции (setInterval на каждый tick)
 * - Логикой победы/поражения в головоломке
 * - Подсчётом статистики (counts, waterStats)
 *
 * Принимает опциональный `identitySeed` из BIP39-идентификации:
 * если передан — используется как начальный seed для детерминированной
 * генерации поля (восстанавливаемая вселенная).
 */

import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import {
  STATE, GEOMETRY_PRESETS, GEOMETRY_LEVELS, PUZZLE_RADIUS, WIN_STABLE_TICKS,
  type GeometryKey, type PresetKey, type StateKey, type CellData, type Params,
  buildInitialField, buildLevelField, stepField, countWater, checkPuzzleWinTick,
  mulberry32, gridCellCount,
} from '../engine/engine';

type Mode = 'sandbox' | 'puzzle';

const DEFAULT_SPEED = 220;        // интервал между тиками в мс
const SANDBOX_SIDE = 30;          // сторона поля для песочницы (в клетках)

interface SimulationState {
  field: Map<string, CellData>;
  running: boolean;
  tick: number;
  speed: number;
  seed: number;
  geometry: GeometryKey;
  radius: number;
  side: number;
  cellSize: number;
  mode: Mode;
  preset: PresetKey;
  params: Params;
  levelIndex: number;
  levelSeed: number;
  dropletsLeft: number;
  winStreak: number;
  puzzleWon: boolean;
  puzzleFailed: boolean;
  brush: StateKey;
  waterHistory: number[];
  initialWater: number;
  waterDrift: number;
  dropletsRanOutTick: number;
  rng: () => number;
  rngState?: number;
  viewport: { x: number; y: number; zoom: number; width: number; height: number; initialized?: boolean };
}

export function useSimulation(
  identitySeed?: number | null,
  onCellPlaced?: (element: StateKey) => void,
) {
  // Load persisted state from localStorage
  const loadPersistedState = (): Partial<SimulationState> => {
    try {
      const saved = localStorage.getItem('elemental-life-state');
      if (saved) {
        const parsed = JSON.parse(saved);
        // Convert field back to Map
        if (parsed.field) {
          parsed.field = new Map(Object.entries(parsed.field));
        }
        return parsed;
      }
    } catch (e) {
      console.warn('Failed to load persisted state:', e);
    }
    return {};
  };

  const [state, setState] = useState<SimulationState>(() => {
    const geometry: GeometryKey = 'hex';
    const side = SANDBOX_SIDE;
    const radius = side - 1;
    const cellSize = 9;
    // Используем identitySeed, если передан (BIP39), иначе fallback = 42
    const seed = identitySeed ?? 42;
    const rng = mulberry32(seed + 999);
    const params = GEOMETRY_PRESETS.hex.classic_balanced.params;
    const field = buildInitialField(geometry, radius, seed, params);
    const initialWater = countWater(field).total;

    const persisted = loadPersistedState();
    
    return {
      field: persisted.field ?? field,
      running: false,
      tick: persisted.tick ?? 0,
      speed: persisted.speed ?? DEFAULT_SPEED,
      seed: persisted.seed ?? seed,
      geometry: persisted.geometry ?? geometry,
      radius: persisted.radius ?? radius,
      side: persisted.side ?? side,
      cellSize: persisted.cellSize ?? cellSize,
      mode: persisted.mode ?? 'sandbox',
      preset: persisted.preset ?? 'classic_balanced',
      params: persisted.params ?? GEOMETRY_PRESETS.hex.classic_balanced.params,
      levelIndex: persisted.levelIndex ?? 0,
      levelSeed: persisted.levelSeed ?? 1,
      dropletsLeft: persisted.dropletsLeft ?? GEOMETRY_LEVELS.hex[0].droplets,
      winStreak: persisted.winStreak ?? 0,
      puzzleWon: persisted.puzzleWon ?? false,
      puzzleFailed: persisted.puzzleFailed ?? false,
      brush: persisted.brush ?? STATE.LIFE,
      waterHistory: persisted.waterHistory ?? [],
      initialWater: persisted.initialWater ?? initialWater,
      waterDrift: persisted.waterDrift ?? 0,
      dropletsRanOutTick: persisted.dropletsRanOutTick ?? Infinity,
      rng: persisted.rng ? mulberry32(persisted.rngState ?? (seed + 999)) : rng,
      viewport: persisted.viewport ?? { x: 0, y: 0, zoom: 1, width: 800, height: 600, initialized: false },
    };
  });

  const intervalRef = useRef<number | null>(null);
  /** Ref для отслеживания начального количества воды в текущей симуляции */
  const initialWaterRef = useRef<number | null>(null);

  // Текущий уровень (мемоизирован)
  const currentLevel = useMemo(
    () => GEOMETRY_LEVELS[state.geometry][state.levelIndex],
    [state.geometry, state.levelIndex]
  );

  // ====== Действия (callbacks) ======

  /**
   * Применить пресет параметров.
   * Меняет params и preset, но НЕ пересоздаёт поле.
   */
  const applyPreset = useCallback((presetKey: PresetKey) => {
    setState((prev) => ({
      ...prev,
      preset: presetKey,
      params: GEOMETRY_PRESETS[prev.geometry][presetKey].params,
    }));
  }, []);

  /**
   * Запустить уровень головоломки.
   * Создаёт поле через buildLevelField, сбрасывает счётчики.
   */
  const startLevel = useCallback((index: number, newSeed?: number) => {
    const level = GEOMETRY_LEVELS[state.geometry][index];
    const seed = newSeed ?? Math.floor(Math.random() * 1e9);
    const radius = PUZZLE_RADIUS[state.geometry];
    const cellSize = state.geometry === 'hex' ? 22 : 20;
    const field = buildLevelField(state.geometry, radius, seed, level);
    const rng = mulberry32(seed + 999);
    const initialWater = countWater(field).total;

    setState((prev) => ({
      ...prev,
      levelIndex: index, levelSeed: seed,
      field, radius, cellSize,
      dropletsLeft: level.droplets,
      winStreak: 0, puzzleWon: false, puzzleFailed: false,
      tick: 0, waterHistory: [], initialWater, waterDrift: 0,
      dropletsRanOutTick: Infinity, rng, running: true,
    }));
    initialWaterRef.current = initialWater;
  }, [state.geometry]);

  /**
   * Переключение режима (песочница ↔ головоломка).
   * При переходе в головоломку создаёт уровень 1.
   * При переходе в песочницу создаёт поле из текущих params.
   */
  const switchMode = useCallback((mode: Mode) => {
    setState((prev) => {
      if (mode === 'puzzle') {
        const level = GEOMETRY_LEVELS[prev.geometry][0];
        const seed = 1;
        const radius = PUZZLE_RADIUS[prev.geometry];
        const cellSize = prev.geometry === 'hex' ? 22 : 20;
        const field = buildLevelField(prev.geometry, radius, seed, level);
        const rng = mulberry32(seed + 999);
        const initialWater = countWater(field).total;
        return {
          ...prev, mode: 'puzzle', running: true,
          levelIndex: 0, levelSeed: seed, field, radius, cellSize,
          dropletsLeft: level.droplets,
          winStreak: 0, puzzleWon: false, puzzleFailed: false,
          tick: 0, waterHistory: [], initialWater, waterDrift: 0,
          dropletsRanOutTick: Infinity, rng,
        };
      } else {
        const params = GEOMETRY_PRESETS[prev.geometry].classic_balanced.params;
        const radius = prev.side - 1;
        const cellSize = 9;
        const field = buildInitialField(prev.geometry, radius, prev.seed, params);
        const rng = mulberry32(prev.seed + 999);
        const initialWater = countWater(field).total;
        return {
          ...prev, params, mode: 'sandbox', running: false,
          field, radius, cellSize, tick: 0, waterHistory: [],
          initialWater, waterDrift: 0, dropletsRanOutTick: Infinity, rng,
        };
      }
    });
    initialWaterRef.current = null;
  }, []);

  /** Сброс песочницы: восстанавливает исходное поле (текущий seed), если newSeed не передан */
  const reset = useCallback((newSeed?: number) => {
    setState((prev) => {
      const seed = newSeed ?? prev.seed;
      const radius = prev.side - 1;
      const field = buildInitialField(prev.geometry, radius, seed, prev.params);
      const rng = mulberry32(seed + 999);
      const initialWater = countWater(field).total;
      return {
        ...prev, seed, field, rng, tick: 0, waterHistory: [],
        initialWater, waterDrift: 0, dropletsRanOutTick: Infinity,
      };
    });
    initialWaterRef.current = null;
  }, []);

  /**
   * Один шаг симуляции (tick).
   *
   * Выполняет:
   * 1. stepField() — расчёт следующего состояния поля
   * 2. Подсчёт воды (water conservation check)
   * 3. В режиме puzzle: проверку победы/поражения
   */
  const doStep = useCallback(() => {
    setState((prev) => {
      const nextField = stepField(prev.geometry, prev.field, prev.radius, prev.params, prev.rng, prev.tick);
      const waterStats = countWater(nextField);
      const totalWater = waterStats.total;

      // Инициализация initialWater при первом тике
      if (initialWaterRef.current === null) {
        initialWaterRef.current = totalWater;
      }
      const initWater = initialWaterRef.current;
      const waterDrift = totalWater - initWater;
      const newHistory = [...prev.waterHistory.slice(-119), totalWater];

      // Логика победы/поражения в головоломке
      let winStreak = prev.winStreak;
      let puzzleWon = prev.puzzleWon;
      let puzzleFailed = prev.puzzleFailed;
      let running = prev.running;
      let dropletsRanOutTick = prev.dropletsRanOutTick;

      // Проверка: все ли пустые клетки моложе WIN_MAX_AGE
      if (prev.mode === 'puzzle' && !prev.puzzleWon) {
        const tickOk = checkPuzzleWinTick(nextField);
        if (tickOk) {
          winStreak += 1;
          if (winStreak >= WIN_STABLE_TICKS) {
            puzzleWon = true;
            running = false;
          }
        } else {
          winStreak = 0;
        }
      }

      // Проверка поражения: капли кончились и прошло > 80 тиков
      if (prev.mode === 'puzzle' && !prev.puzzleWon) {
        if (prev.dropletsLeft <= 0 && dropletsRanOutTick === Infinity) {
          dropletsRanOutTick = prev.tick + 1;
        }
        if (prev.dropletsLeft > 0) {
          dropletsRanOutTick = Infinity;
        }
        if (prev.dropletsLeft <= 0 && dropletsRanOutTick !== Infinity &&
            prev.tick + 1 - dropletsRanOutTick > 80) {
          puzzleFailed = true;
          running = false;
        }
      }

      return {
        ...prev, field: nextField, tick: prev.tick + 1,
        waterHistory: newHistory, initialWater: initWater, waterDrift,
        winStreak, puzzleWon, puzzleFailed, running, dropletsRanOutTick,
      };
    });
  }, []);

  // Цикл симуляции: setInterval при running=true
  useEffect(() => {
    if (state.running) {
      intervalRef.current = window.setInterval(doStep, state.speed);
      return () => {
        if (intervalRef.current) clearInterval(intervalRef.current);
      };
    }
  }, [state.running, state.speed, doStep]);

  // ====== Клик по клетке поля ======

  /**
   * Обработчик клика по клетке поля.
   * В режиме puzzle: ставит воду в пустую клетку, тратит каплю.
   * В режиме sandbox: ставит текущую кисть.
   */
  const lastPlacedRef = useRef<StateKey | null>(null);
  const handleCellClick = useCallback((q: number, r: number) => {
    setState((prev) => {
      const key = `${q},${r}`;
      const current = prev.field.get(key);

      if (prev.mode === 'puzzle') {
        if (prev.puzzleWon || prev.dropletsLeft <= 0) return prev;
        if (!current || current.state !== STATE.EMPTY) return prev;
        const next = new Map(prev.field);
        next.set(key, { state: STATE.WATER, age: 0 });
        lastPlacedRef.current = STATE.WATER;
        return { ...prev, field: next, dropletsLeft: Math.max(0, prev.dropletsLeft - 1) };
      }

      const next = new Map(prev.field);
      next.set(key, { state: prev.brush, age: 0 });
      lastPlacedRef.current = prev.brush;
      return { ...prev, field: next };
    });
  }, []);

  // Notify parent when user places an element
  useEffect(() => {
    const element = lastPlacedRef.current;
    if (element !== null) {
      lastPlacedRef.current = null;
      onCellPlaced?.(element);
    }
  });

  // ====== Смена геометрии ======

  /**
   * Смена геометрии поля (hex ↔ square).
   * Полностью пересоздаёт поле (новая структура сетки) с текущим seed.
   */
  const setGeometry = useCallback((geometry: GeometryKey) => {
    setState((prev) => {
      const side = geometry === 'hex' ? 30 : 29;
      const radius = geometry === 'hex' ? side - 1 : Math.floor((side - 1) / 2);
      const cellSize = 9;
      const seed = prev.seed;
      const params = GEOMETRY_PRESETS[geometry].classic_balanced.params;
      const field = buildInitialField(geometry, radius, seed, params);
      const rng = mulberry32(seed + 999);
      const initialWater = countWater(field).total;
      return {
        ...prev, geometry, radius, side, cellSize, field, rng,
        tick: 0, waterHistory: [], initialWater, waterDrift: 0,
        dropletsRanOutTick: Infinity,
        puzzleWon: false, puzzleFailed: false, winStreak: 0,
        running: false, preset: 'classic_balanced',
        params: GEOMETRY_PRESETS[geometry].classic_balanced.params,
      };
    });
  }, []);

  // ====== Простые сеттеры ======

  const setBrush = useCallback((brush: StateKey) => setState((prev) => ({ ...prev, brush })), []);
  const setSpeed = useCallback((speed: number) => setState((prev) => ({ ...prev, speed })), []);
  const setParam = useCallback((key: keyof Params, value: number | boolean) => {
    setState((prev) => ({ ...prev, params: { ...prev.params, [key]: value } }));
  }, []);
  const setRunning = useCallback((running: boolean) => setState((prev) => ({ ...prev, running })), []);
  const setSeed = useCallback((seed: number) => setState((prev) => ({ ...prev, seed })), []);

  const goToNextLevel = useCallback(() => {
    const nextIndex = Math.min(state.levelIndex + 1, GEOMETRY_LEVELS[state.geometry].length - 1);
    startLevel(nextIndex, Math.floor(Math.random() * 1e9));
  }, [state.geometry, state.levelIndex, startLevel]);

  const retryLevel = useCallback(() => {
    startLevel(state.levelIndex, Math.floor(Math.random() * 1e9));
  }, [state.geometry, state.levelIndex, startLevel]);

  /** Обновление viewport (панорамирование, зум, ресайз) */
  const setViewport = useCallback(
    (vp: Partial<{ x: number; y: number; zoom: number; width: number; height: number }>) => {
      setState((prev) => ({ ...prev, viewport: { ...prev.viewport, ...vp } }));
    }, []
  );

  // ====== Мемоизированные вычисления ======

  /** Подсчёт количества клеток каждого состояния */
  const counts = useMemo(() => {
    const result = Object.values(STATE).reduce((acc, s) => {
      acc[s as StateKey] = 0;
      return acc;
    }, {} as Record<StateKey, number>);
    state.field.forEach((cell) => {
      if (result[cell.state] !== undefined) result[cell.state]++;
    });
    return result;
  }, [state.field]);

  const totalCells = useMemo(() => gridCellCount(state.geometry, state.side), [state.geometry, state.side]);
  const waterStats = useMemo(() => countWater(state.field), [state.field]);

  return {
    ...state,
    currentLevel, counts, totalCells, waterStats,
    applyPreset, switchMode, reset, handleCellClick,
    setGeometry, setBrush, setSpeed, setParam,
    goToNextLevel, retryLevel, setRunning, setSeed,
    startLevel, setViewport, doStep,
  };

  // Persist state to localStorage
    useEffect(() => {
      const saveState = () => {
        try {
          const toSave = {
            ...state,
            field: Object.fromEntries(state.field),
            rngState: state.rng ? (state.rng() as number) : undefined,
          };
          localStorage.setItem('elemental-life-state', JSON.stringify(toSave));
        } catch (e) {
          console.warn('Failed to save state:', e);
        }
      };

      const interval = setInterval(saveState, 5000);
      window.addEventListener('beforeunload', saveState);

      return () => {
        clearInterval(interval);
        window.removeEventListener('beforeunload', saveState);
        saveState();
      };
    }, [state]);
  }