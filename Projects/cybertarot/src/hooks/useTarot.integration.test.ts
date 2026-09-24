/**
 * Integration tests: Phase 1.4 из EVOLUTION_PLAN.md
 * - Integration: draw → interpretation → mint → sell цикл
 * - Integration: harvest → mint → sell цикл
 *
 * Unit-покрытие экономики Фазы 1 (78 карт, тир-экономика) уже есть
 * в game.test.ts / useTarot.test.ts / magicWell.test.ts / interpret.test.ts.
 * Здесь — сквозные циклы через весь hook useTarot: реальный interpret()
 * (замокан только сетевой слой ollama → срабатывает fallback-цепочка)
 * и localStorage-мок из vitest.setup.ts.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useTarot } from '@/hooks/useTarot';
import { ollamaInterpret } from '@/services/ollama';

// Мокаем только ollama (сетевой слой): interpret() идёт по цепочке
// cache → ollama (null) → API (VITE_API_URL не задан) → mockInterpret fallback
vi.mock('@/services/ollama', () => ({
  ollamaInterpret: vi.fn().mockResolvedValue(null),
}));

// vitest.setup.ts глушит setInterval → RTL waitFor не поллит.
// Восстанавливаем реальный setInterval только для этого файла,
// чтобы дожидаться асинхронного interpret() (fallback-цепочка).
const realSetInterval = globalThis.setInterval.bind(globalThis);
const realClearInterval = globalThis.clearInterval.bind(globalThis);
vi.stubGlobal('setInterval', realSetInterval);
vi.stubGlobal('clearInterval', realClearInterval);

const STATE_KEY = 'cybertarot-state';

/** Ждём, пока predicate не станет true (poll реальными таймерами, timeout 5s). */
async function pollUntil(predicate: () => boolean, timeoutMs = 5000): Promise<void> {
  const start = Date.now();
  while (!predicate()) {
    if (Date.now() - start > timeoutMs) {
      throw new Error(`pollUntil: timeout after ${timeoutMs}ms`);
    }
    await new Promise((r) => setTimeout(r, 10));
  }
}

/** Пре-сейв состояния в localStorage-мок (как делает реальное приложение) */
function seedState(over: Record<string, unknown>) {
  localStorage.setItem(STATE_KEY, JSON.stringify({
    balance: 0,
    collection: [],
    locale: 'en',
    refCode: 'TAROT-TEST',
    well: {
      pending: 0,
      nextFillAt: Date.now() + 60 * 60 * 1000,
      dryAt: Date.now() + 2 * 60 * 60 * 1000,
      totalHarvests: 0,
      totalHarvested: 0,
      totalDryouts: 0,
    },
    ...over,
  }));
}

describe('Integration: full game cycles (Phase 1.4)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(ollamaInterpret).mockClear();
  });

  it('draw → interpretation → mint → sell: полный цикл одной сессии', async () => {
    // Свежий игрок: пустой localStorage → стартовый баланс 100 (loadState default)
    const { result } = renderHook(() => useTarot());
    await waitFor(() => expect(result.current.balance).toBe(100));

    // 1. Draw: 3 карты (spreadSize по умолчанию), интерпретация грузится
    act(() => { result.current.draw(); });
    expect(result.current.drawn).not.toBeNull();
    expect(result.current.drawn!.length).toBe(3);
    expect(result.current.interpretationLoading).toBe(true);

    // 2. Interpretation: реальный interpret() дошёл до fallback и вернул текст
    await pollUntil(() => {
      act(() => {}); // flush React-обновлений
      return !result.current.interpretationLoading;
    });
    expect(ollamaInterpret).toHaveBeenCalledTimes(1);
    expect(result.current.interpretation.length).toBeGreaterThan(0);
    // интерпретация соответствует выпавшим картам (имена карт в тексте)
    const names = result.current.drawn!.map((c) => c.name.en);
    for (const n of names) expect(result.current.interpretation).toContain(n);

    // 3. Mint: rare стоит 40 (RARITIES.rare.cost), баланс 100 → 60
    const balanceBeforeMint = result.current.balance;
    act(() => { result.current.mint('rare'); });
    const minted = result.current.mintResult!;
    expect(result.current.balance).toBe(balanceBeforeMint - 40);
    expect(result.current.collection).toHaveLength(1);
    expect(minted.rarity).toBe('rare');
    expect(minted.uid).toBeTruthy();

    // сквозная проверка персиста: hook сохранил баланс в localStorage
    // (saveState в useEffect flush'ится синхронно внутри act())
    const saved = JSON.parse(localStorage.getItem(STATE_KEY)!);
    expect(saved.balance).toBe(60);

    // 4. Sell: возврат 60% от 40 = 24, карта покидает коллекцию
    act(() => { result.current.sellCard(minted.uid); });
    expect(result.current.balance).toBe(60 + 24);
    expect(result.current.collection).toHaveLength(0);
    expect(result.current.collection.find((c) => c.uid === minted.uid)).toBeUndefined();
  });

  it('harvest → mint → sell: колодец финансирует минт, продажа возвращает 60%', async () => {
    // Игрок с нулевым балансом и полным колодцем (40 маны ждут сбора)
    seedState({ well: { pending: 40, nextFillAt: Date.now() + 60 * 60 * 1000, dryAt: Date.now() + 2 * 60 * 60 * 1000, totalHarvests: 0, totalHarvested: 0, totalDryouts: 0 } });
    const { result } = renderHook(() => useTarot());
    await waitFor(() => expect(result.current.balance).toBe(0));
    expect(result.current.harvestReady).toBe(true);

    // 1. Harvest: +40 маны из колодца, статистика сбора растёт
    act(() => { result.current.harvestMana(); });
    expect(result.current.balance).toBe(40);
    expect(result.current.well.pending).toBe(0);
    expect(result.current.well.totalHarvests).toBe(1);
    expect(result.current.well.totalHarvested).toBe(40);
    expect(result.current.harvestReady).toBe(false);

    // 2. Mint: собранная мана ровно оплачивает rare (40) → кошелёк пуст
    act(() => { result.current.mint('rare'); });
    const minted = result.current.mintResult!;
    expect(result.current.balance).toBe(0);
    expect(result.current.collection).toHaveLength(1);

    // 3. Sell: возврат 24 (60% от 40) — цикл колодец→минт→рынок замкнут
    act(() => { result.current.sellCard(minted.uid); });
    expect(result.current.balance).toBe(24);
    expect(result.current.collection).toHaveLength(0);
  });
});
