// ManaWell — колодец маны: механика нарастающего вознаграждения с риском пересыхания
//
// Правила:
// 1. Первое получение: 1 мана
// 2. Каждые 6 часов: +1 мана (1→2→3→4→...)
// 3. Если игрок НЕ забрал ману в течение 6 часов после начисления — колодец пересыхает
// 4. После пересыхания всё начинается заново с 1 маны
// 5. Уведомление когда колодец наполнен (готов к забору)
//
// Привязка: чем больше маны в колодце, тем больший стресс потерять → FOMO

export interface ManaWellState {
  /** Сколько маны сейчас в колодце (доступно для сбора) */
  pending: number;
  /** UTC timestamp когда мана будет начислена следующая порция */
  nextFillAt: number;
  /** UTC timestamp когда колодец пересохнет если не собрать */
  dryAt: number;
  /** Сколько раз игрок собирал ману (статистика) */
  totalHarvests: number;
  /** Сколько маны всего собрано за всё время */
  totalHarvested: number;
  /** Сколько раз колодец пересох (статистика потерь) */
  totalDryouts: number;
}

const FILL_INTERVAL = 6 * 60 * 60 * 1000; // 6 часов в миллисекундах
const DRY_THRESHOLD = 6 * 60 * 60 * 1000; // 6 часов после заполнения = пересыхание

/** Создать новый колодец (первый запуск) */
export function createWell(): ManaWellState {
  const now = Date.now();
  return {
    pending: 1, // первая мана сразу доступна
    nextFillAt: now + FILL_INTERVAL,
    dryAt: now + FILL_INTERVAL + DRY_THRESHOLD, // 6ч на заполнение + 6ч на сбор
    totalHarvests: 0,
    totalHarvested: 0,
    totalDryouts: 0,
  };
}

/**
 * Тик колодца — вызывается при каждом рендере/загрузке.
 * Проверяет: нужно ли начислить ману, нужно ли пересушить колодец.
 * Возвращает обновлённое состояние + флаги что произошло.
 */
export function tickWell(well: ManaWellState): {
  well: ManaWellState;
  filled: boolean;   // колодец наполнился новой порцией (можно отправить уведомление)
  dried: boolean;    // колодец пересох (мана потеряна)
  harvestReady: boolean; // есть мана для сбора
} {
  const now = Date.now();
  let state = { ...well };
  let filled = false;
  let dried = false;

  // Проверяем пересыхание ВПЕРВЫХ — если колодец не собран вовремя
  if (now >= state.dryAt && state.pending > 0) {
    // Колодец пересох! Всё сбрасывается
    state.totalDryouts += 1;
    state.pending = 0;
    dried = true;
  }

  // Проверяем заполнение — если пришло время новой порции и колодец не пересох
  if (now >= state.nextFillAt && !dried) {
    // Если pending уже 0 (пересох ранее в этом тике или игрок забрал), начинаем с 1
    const nextAmount = state.pending === 0 ? 1 : state.pending + 1;
    state.pending = nextAmount;
    state.nextFillAt = now + FILL_INTERVAL;
    state.dryAt = now + DRY_THRESHOLD;
    filled = true;
  }

  // Если колодец пересох, но время заполнения пришло — начинаем заново с 1
  if (dried && now >= state.nextFillAt) {
    state.pending = 1;
    state.nextFillAt = now + FILL_INTERVAL;
    state.dryAt = now + DRY_THRESHOLD;
    filled = true;
  }

  const harvestReady = state.pending > 0;

  return { well: state, filled, dried, harvestReady };
}

/**
 * Забрать ману из колодца.
 * Возвращает сколько маны получено и обновлённое состояние.
 * После сбора колодец пустой, следующая мана через 6 часов.
 */
export function harvestWell(well: ManaWellState): {
  well: ManaWellState;
  amount: number; // сколько маны получено
} {
  if (well.pending <= 0) {
    return { well, amount: 0 };
  }

  const now = Date.now();
  return {
    amount: well.pending,
    well: {
      ...well,
      pending: 0,
      nextFillAt: now + FILL_INTERVAL, // следующая порция через 6 часов
      dryAt: now + FILL_INTERVAL + DRY_THRESHOLD,
      totalHarvests: well.totalHarvests + 1,
      totalHarvested: well.totalHarvested + well.pending,
    },
  };
}

/**
 * Сколько времени до следующего заполнения (в мс).
 * Отрицательное = уже должно быть заполнено.
 */
export function timeUntilFill(well: ManaWellState): number {
  return well.nextFillAt - Date.now();
}

/**
 * Сколько времени до пересыхания (в мс).
 * Отрицательное = уже должно было пересохнуть.
 */
export function timeUntilDry(well: ManaWellState): number {
  return well.dryAt - Date.now();
}

/**
 * Форматировать время до события в человекочитаемый вид.
 * "4ч 32м" или "12м 5с" или "горит!" (если прошло)
 */
export function formatTimeLeft(ms: number, locale: string = "en"): string {
  if (ms <= 0) return locale === "ru" ? "пора!" : "ready!";
  const totalMin = Math.floor(ms / 60000);
  const h = Math.floor(totalMin / 60);
  const m = totalMin % 60;
  const s = Math.floor((ms % 60000) / 1000);
  if (h > 0) return `${h}ч ${m}м`;
  if (m > 0) return `${m}м ${s}с`;
  return `${s}с`;
}
