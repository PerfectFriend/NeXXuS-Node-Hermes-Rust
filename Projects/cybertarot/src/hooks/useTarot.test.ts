
import { describe, it, expect } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useTarot } from '@/hooks/useTarot';

describe('useTarot hook', () => {
  // beforeEach(() => {
  //   vi.useFakeTimers();
  //   vi.clearAllMocks();
  // });
  //
  // afterEach(() => {
  //   vi.useRealTimers();
  // });

  // --- mint tests ---
  describe('mint', () => {
    it('deducts balance and adds card to collection when sufficient balance', async () => {
      const { result } = renderHook(() => useTarot());

      // Wait for initial load
      await waitFor(() => expect(result.current.balance).toBeDefined());

      const cost = 40; // rare cost

      // Set balance high enough
      act(() => {
        result.current.setBalance(cost + 100);
      });

      const balanceBefore = result.current.balance;
      const collectionBefore = result.current.collection.length;

      // Mint a rare card
      act(() => {
        result.current.mint('rare');
      });

      expect(result.current.balance).toBe(balanceBefore - cost);
      expect(result.current.collection.length).toBe(collectionBefore + 1);
      expect(result.current.mintResult).not.toBeNull();
      expect(result.current.mintResult!.rarity).toBe('rare');
    });

    it('does nothing when balance is insufficient', async () => {
      const { result } = renderHook(() => useTarot());

      await waitFor(() => expect(result.current.balance).toBeDefined());

      // Set balance lower than cost
      act(() => {
        result.current.setBalance(10); // Less than rare cost (40)
      });

      const balanceBefore = result.current.balance;
      const collectionBefore = result.current.collection.length;

      act(() => {
        result.current.mint('rare');
      });

      expect(result.current.balance).toBe(balanceBefore);
      expect(result.current.collection.length).toBe(collectionBefore);
      expect(result.current.mintResult).toBeNull();
    });

    it('mintRandom rolls rarity and mints', async () => {
      const { result } = renderHook(() => useTarot());

      await waitFor(() => expect(result.current.balance).toBeDefined());

      // Set high balance
      act(() => {
        result.current.setBalance(1000);
      });

      const collectionBefore = result.current.collection.length;

      act(() => {
        result.current.mintRandom();
      });

      expect(result.current.collection.length).toBe(collectionBefore + 1);
      expect(result.current.mintResult).not.toBeNull();
      expect(['rare', 'epic', 'legendary']).toContain(result.current.mintResult!.rarity);
    });
  });

  // --- sellCard tests ---
  describe('sellCard', () => {
    it('adds 60% of card cost to balance and removes from collection', async () => {
      const { result } = renderHook(() => useTarot());

      await waitFor(() => expect(result.current.balance).toBeDefined());

      // Set high balance and mint a card first
      act(() => {
        result.current.setBalance(1000);
      });

      act(() => {
        result.current.mint('rare');
      });

      const mintedCard = result.current.mintResult!;
      const cost = 40; // rare cost
      const expectedRefund = Math.round(cost * 0.6); // 24

      const balanceBefore = result.current.balance;
      const collectionBefore = result.current.collection.length;

      act(() => {
        result.current.sellCard(mintedCard.uid);
      });

      expect(result.current.balance).toBe(balanceBefore + expectedRefund);
      expect(result.current.collection.length).toBe(collectionBefore - 1);
      expect(result.current.collection.find((c) => c.uid === mintedCard.uid)).toBeUndefined();
    });

    it('does nothing when card not found', async () => {
      const { result } = renderHook(() => useTarot());

      await waitFor(() => expect(result.current.balance).toBeDefined());

      const balanceBefore = result.current.balance;
      const collectionBefore = result.current.collection.length;

      act(() => {
        result.current.sellCard('nonexistent-uid');
      });

      expect(result.current.balance).toBe(balanceBefore);
      expect(result.current.collection.length).toBe(collectionBefore);
    });

    it('calculates refund correctly for different rarities', async () => {
      const { result } = renderHook(() => useTarot());

      await waitFor(() => expect(result.current.balance).toBeDefined());

      act(() => {
        result.current.setBalance(1000);
      });

      // Mint epic
      act(() => {
        result.current.mint('epic');
      });
      const epicCard = result.current.mintResult!;
      const epicCost = 120;
      const epicRefund = Math.round(epicCost * 0.6); // 72

      const balanceBeforeEpic = result.current.balance;
      act(() => {
        result.current.sellCard(epicCard.uid);
      });
      expect(result.current.balance).toBe(balanceBeforeEpic + epicRefund);

      // Mint legendary
      act(() => {
        result.current.mint('legendary');
      });
      const legendaryCard = result.current.mintResult!;
      const legendaryCost = 400;
      const legendaryRefund = Math.round(legendaryCost * 0.6); // 240

      const balanceBeforeLegendary = result.current.balance;
      act(() => {
        result.current.sellCard(legendaryCard.uid);
      });
      expect(result.current.balance).toBe(balanceBeforeLegendary + legendaryRefund);
    });
  });

  // --- draw/interpretation tests ---
  describe('draw', () => {
    it('draws cards and sets interpretation loading', async () => {
      const { result } = renderHook(() => useTarot());

      await waitFor(() => expect(result.current.balance).toBeDefined());

      act(() => {
        result.current.draw();
      });

      expect(result.current.drawn).not.toBeNull();
      expect(result.current.drawn!.length).toBe(3); // default spreadSize
      expect(result.current.interpretationLoading).toBe(true);
    });

    it('draws 1 card when spreadSize is 1', async () => {
      const { result } = renderHook(() => useTarot());
      await waitFor(() => expect(result.current.balance).toBeDefined());
      act(() => {
        result.current.setSpreadSize(1);
      });
      act(() => {
        result.current.draw();
      });
      expect(result.current.drawn!.length).toBe(1);
    });
  });

  // --- harvestMana tests ---
  describe('harvestMana', () => {
    it('adds pending mana to balance and resets well', async () => {
      const { result } = renderHook(() => useTarot());

      await waitFor(() => expect(result.current.balance).toBeDefined());

      // Wait for well to be ready (harvestReady should be true initially)
      await waitFor(() => expect(result.current.harvestReady).toBe(true));

      const balanceBefore = result.current.balance;
      const pendingBefore = result.current.well.pending;

      act(() => {
        result.current.harvestMana();
      });

      expect(result.current.balance).toBe(balanceBefore + pendingBefore);
      expect(result.current.well.pending).toBe(0);
      expect(result.current.harvestReady).toBe(false);
    });

    it('does nothing when well is empty', async () => {
      const { result } = renderHook(() => useTarot());

      await waitFor(() => expect(result.current.balance).toBeDefined());

      // Harvest once to empty it
      if (result.current.harvestReady) {
        act(() => {
          result.current.harvestMana();
        });
      }

      // Wait a bit and try again
      const balanceBefore = result.current.balance;

      act(() => {
        result.current.harvestMana();
      });

      expect(result.current.balance).toBe(balanceBefore);
    });
  });

  // --- copyRef tests ---
  describe('copyRef', () => {
    it('copies refCode to clipboard and sets copied flag', async () => {
      const { result } = renderHook(() => useTarot());

      await waitFor(() => expect(result.current.refCode).toBeDefined());

      expect(result.current.copied).toBe(false);

      act(() => {
        result.current.copyRef();
      });

      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(result.current.refCode);
      expect(result.current.copied).toBe(true);
    });
  });

  // --- persistence tests ---
  describe('localStorage persistence', () => {
    it('saves state to localStorage on changes', async () => {
      const { result } = renderHook(() => useTarot());

      await waitFor(() => expect(result.current.balance).toBeDefined());

      act(() => {
        result.current.setBalance(999);
      });

      // Check localStorage was called
      expect(localStorage.setItem).toHaveBeenCalledWith(
        'cybertarot-state',
        expect.stringContaining('999')
      );
    });

    it('loads state from localStorage on init', async () => {
      const savedState = {
        balance: 555,
        collection: [],
        locale: 'ru' as const,
        refCode: 'TAROT-TEST',
        well: { pending: 3, nextFillAt: Date.now() + 10000, dryAt: Date.now() + 20000, totalHarvests: 5, totalHarvested: 15, totalDryouts: 0 }
      };
      // Since we already have a mock in vitest.setup.ts, we can just set the mock return value
      // But note: the mock is already set in vitest.setup.ts, so we can just use:
      // localStorage.getItem.mockReturnValue(JSON.stringify(savedState));
      // However, the mock function is already defined in the setup, so we can just call it.
      // We'll do it here as well to be safe.
      (localStorage.getItem as unknown as { mockReturnValue: (v: string) => void }).mockReturnValue(JSON.stringify(savedState));

      const { result } = renderHook(() => useTarot());

      await waitFor(() => expect(result.current.balance).toBeDefined());

      expect(result.current.balance).toBe(555);
      expect(result.current.locale).toBe('ru');
      expect(result.current.refCode).toBe('TAROT-TEST');
      expect(result.current.well.pending).toBe(3);
    });
  });
});