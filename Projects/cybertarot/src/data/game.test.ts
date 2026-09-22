
/// <reference types="vitest" />
import { describe, it, expect } from 'vitest';
import { shuffleDeck, DECK, rollRarity } from "./game";

describe("shuffleDeck", () => {
  it("returns an array of the requested length", () => {
    const count = 5;
    const result = shuffleDeck(count);
    expect(result.length).toBe(count);
  });

  it("returns cards from the full 78-card deck", () => {
    const count = 78;
    const result = shuffleDeck(count);
    expect(result.length).toBe(count);
    // Check that all cards are from the original deck (by id)
    const resultIds = new Set(result.map(c => c.id));
    const deckIds = new Set(DECK.map(c => c.id));
    expect(resultIds).toEqual(deckIds);
  });

  it("sets orientation to either upright or reversed", () => {
    const count = 10;
    const result = shuffleDeck(count);
    result.forEach(card => {
      expect(["upright", "reversed"]).toContain(card.orientation);
    });
  });

  it("never returns duplicate cards within a draw", () => {
    // Fisher-Yates must sample without replacement — critical for card fairness.
    for (let round = 0; round < 20; round++) {
      const result = shuffleDeck(DECK.length); // full deck
      const ids = result.map(c => c.id);
      expect(new Set(ids).size).toBe(ids.length);
    }
  });

  it("uses random orientation (approximately 25% reversed)", () => {
    // Use a reasonable number of cards (<=78) and many rounds to get good statistics
    const rounds = 100;
    const countPerRound = 78; // full deck
    let totalReversed = 0;
    let totalCards = 0;
    for (let i = 0; i < rounds; i++) {
      const result = shuffleDeck(countPerRound);
      totalReversed += result.filter(c => c.orientation === "reversed").length;
      totalCards += result.length;
    }
    const proportion = totalReversed / totalCards;
    // We'll allow a wide margin due to randomness
    expect(proportion).toBeGreaterThan(0.2);
    expect(proportion).toBeLessThan(0.3);
  });
});

describe("rollRarity", () => {
  it("returns legendary with probability ~0.05", () => {
    const samples = 10000;
    const results = Array.from({ length: samples }, () => rollRarity());
    const legendaryCount = results.filter(r => r === "legendary").length;
    const proportion = legendaryCount / samples;
    // Allow a margin due to randomness
    expect(proportion).toBeCloseTo(0.05, 0.01);
  });

  it("returns epic with probability ~0.25", () => {
    const samples = 10000;
    const results = Array.from({ length: samples }, () => rollRarity());
    const epicCount = results.filter(r => r === "epic").length;
    const proportion = epicCount / samples;
    expect(proportion).toBeCloseTo(0.25, 0.01);
  });

  it("returns rare with probability ~0.7", () => {
    const samples = 10000;
    const results = Array.from({ length: samples }, () => rollRarity());
    const rareCount = results.filter(r => r === "rare").length;
    const proportion = rareCount / samples;
    expect(proportion).toBeCloseTo(0.7, 0.01);
  });

  it("never returns common", () => {
    const samples = 10000;
    const results = Array.from({ length: samples }, () => rollRarity());
    const commonCount = results.filter(r => r === "common").length;
    expect(commonCount).toBe(0);
  });
});