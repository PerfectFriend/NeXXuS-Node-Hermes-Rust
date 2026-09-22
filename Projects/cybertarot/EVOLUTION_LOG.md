# CyberTarot Evolution Log

## Cycle 1: Item 1 - Initialize TDD test suite
- Verified vitest configuration is working.
- Smoke tests and useTarot tests are passing.
- No changes needed.

## Cycle 2: Item 2 - Fix shuffleDeck to use full 78-card deck
- Verified shuffleDeck uses full DECK and sets orientation.
- Added test in src/data/game.test.ts to confirm.
- Tests pass.

## Cycle 3: Item 3: Fix rollRarity rarity distribution
- Current rollRarity function in src/data/game.ts:
    export function rollRarity(): Rarity {
      const r = Math.random();
      if (r < RARITIES.legendary.weight) return "legendary";
      if (r < RARITIES.legendary.weight + RARITIES.epic.weight) return "epic";
      return "rare";
    }
- Weights: legendary 0.05, epic 0.25, rare 0.7 -> distribution 5%/25%/70%.
- However, note that common weight is 0 and cost 0, but the function never returns common.
- According to the plan, common should be possible? But the EVOLUTION_PLAN.md says mint: 3 тиры (rare/epic/legendary) + weighted random 70/25/5.
- So common is not used in minting. The rollRarity function is correct for minting.
- We'll add a test to verify the distribution over many samples.
- Added comprehensive tests for rollRarity distribution and shuffleDeck orientation.
- All tests pass.

## Cycle 4: Item 4: Fix ManaWell tickWell dry/fill cycle
- Examined src/services/magicWell.ts.
- The tickWell function seems correct: it checks for dry first, then fill, and handles the case when dried and fill time has come.
- We added a test for tickWell in a new test file for magicWell.
- Tests pass.

## Cycle 5: Item 5: Add localStorage persistence tests
- Already have tests in src/hooks/useTarot.test.ts for persistence.
- They are passing.
- Verified by running the persistence tests.

## Cycle 6: Item 6: Fix card orientation property
- Verified shuffleDeck sets orientation.
- Added test in src/data/game.test.ts to confirm orientation is set.
- Tests pass.

## Cycle 7: Item 7: Add interpretation service tests
- We'll create a test for the interpret service in src/services/interpret.test.ts.
- We'll mock the ollamaInterpret and localStorage.

## Cycle 8: Item 8: Fix mint cost deduction
- Verified mint function in src/hooks/useTarot.ts deducts the cost.
- Already tested in useTarot.test.ts.

## Cycle 9: Item 9: Add collection management tests
- Already have sellCard tests in useTarot.test.ts.
- We'll add a test for selling a card that doesn't exist (already there) and for different rarities.

## Cycle 10: Item 10: Full test suite passes with no regressions
- Run the full test suite and ensure all tests pass.

Now, let's implement each cycle step by step.

Completed cycles 1-6: shuffleDeck, rollRarity, and ManaWell tests are passing.
LocalStorage persistence and card orientation tests are passing.