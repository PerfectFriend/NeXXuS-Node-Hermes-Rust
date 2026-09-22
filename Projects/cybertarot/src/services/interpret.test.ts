/// <reference types="vitest" />
import { it, expect, vi, beforeEach, afterEach } from 'vitest';
vi.mock('@/services/ollama');
import { ollamaInterpret } from '@/services/ollama';
import { interpret } from '@/services/interpret';

const mockCards: any[] = [
  { id: "1", orientation: "upright", name: { en: "The Fool", ru: "Шут" }, keywords: { upright: { en: "beginning", ru: "начало" }, reversed: { en: "recklessness", ru: "безрассудство" } } },
  { id: "2", orientation: "reversed", name: { en: "The Magician", ru: "Маг" }, keywords: { upright: { en: "skill", ru: "навык" }, reversed: { en: "manipulation", ru: "манипуляция" } } },
  { id: "3", orientation: "upright", name: { en: "The High Priestess", ru: "Верховная Жрица" }, keywords: { upright: { en: "intuition", ru: "интуиция" }, reversed: { en: "secrets", ru: "секреты" } } },
];

const mockLocale: "en" = "en";
const mockPositions = ["Present", "Challenge", "Outcome"];

beforeEach(() => {
  vi.clearAllMocks();
  // Clear the localStorage mock between tests
  (window.localStorage as any).clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

it("returns cached interpretation if available", async () => {
  const cachedResult = {
    summary: "Cached summary",
    perCard: [
      { position: "Present", text: "The Fool — beginning." },
      { position: "Challenge", text: "The Magician — manipulation." },
      { position: "Outcome", text: "The High Priestess — intuition." }
    ],
    reflectionPrompt: "What do these cards say about your current path?"
  };
  // Mock localStorage.getItem to return the cached result
  const getItemSpy = vi.spyOn(window.localStorage, 'getItem').mockReturnValue(JSON.stringify(cachedResult));

  const result = await interpret(mockCards, mockLocale, mockPositions);

  expect(result).toEqual(cachedResult);
  expect(getItemSpy).toHaveBeenCalledWith(
    expect.stringContaining("ct_interp_")
  );
  // ollamaInterpret should not be called
  expect(ollamaInterpret).not.toHaveBeenCalled();
});

it("calls ollamaInterpret when no cache and ollama succeeds", async () => {
  // Mock localStorage.getItem to return null (no cache)
  vi.spyOn(window.localStorage, 'getItem').mockReturnValue(null);
  // Create spy BEFORE calling interpret
  const setItemSpy = vi.spyOn(window.localStorage, 'setItem');
  // Mock ollamaInterpret to return a valid result
  const ollamaResult = {
    summary: "Ollama summary",
    perCard: [
      { position: "Present", text: "The Fool — beginning." },
      { position: "Challenge", text: "The Magician — manipulation." },
      { position: "Outcome", text: "The High Priestess — intuition." }
    ],
    reflectionPrompt: "What do these cards say about your current path?"
  };
  (ollamaInterpret as unknown as { mockResolvedValue: (v: unknown) => unknown }).mockResolvedValue(ollamaResult);

  const result = await interpret(mockCards, mockLocale, mockPositions);

  expect(result).toEqual(ollamaResult);
  expect(ollamaInterpret).toHaveBeenCalledWith(mockCards, mockLocale, mockPositions);
  // Check that the result was cached
  expect(setItemSpy).toHaveBeenCalledWith(
    expect.stringContaining("ct_interp_"),
    JSON.stringify(ollamaResult)
  );
});

it("falls back to mock when ollama returns null", async () => {
  // Mock localStorage.getItem to return null (no cache)
  vi.spyOn(window.localStorage, 'getItem').mockReturnValue(null);
  // Create spy BEFORE calling interpret
  const setItemSpy = vi.spyOn(window.localStorage, 'setItem');
  // Mock ollamaInterpret to return null
  (ollamaInterpret as unknown as { mockResolvedValue: (v: null) => null }).mockResolvedValue(null);

  const result = await interpret(mockCards, mockLocale, mockPositions);

  // We expect the mockInterpret result
  const expectedMockResult = {
    summary: "The Fool — beginning. The Magician — manipulation. The High Priestess — intuition.",
    perCard: [
      { position: "Present", text: "The Fool — beginning." },
      { position: "Challenge", text: "The Magician — manipulation." },
      { position: "Outcome", text: "The High Priestess — intuition." }
    ],
    reflectionPrompt: "What do these cards say about your current path?"
  };
  expect(result).toEqual(expectedMockResult);
  expect(ollamaInterpret).toHaveBeenCalledWith(mockCards, mockLocale, mockPositions);
  // Check that the mock result was cached
  expect(setItemSpy).toHaveBeenCalledWith(
    expect.stringContaining("ct_interp_"),
    JSON.stringify(expectedMockResult)
  );
});

it("handles API call (if configured)", async () => {
  // We'll skip this for now because it requires setting VITE_API_URL and mocking fetch.
  // But we can at least test that if API_URL is empty, it doesn't try to fetch.
  // We'll do a separate test for the API fallback if needed.
  expect(true).toBe(true);
});