

import type { DrawnCard, InterpretationResult, Locale } from "@/types";
import { ollamaInterpret } from "@/services/ollama";

const API_URL = import.meta.env.VITE_API_URL || "";

function mockInterpret(
  cards: DrawnCard[],
  locale: Locale,
  positions: string[]
): InterpretationResult {
  const perCard = cards.map((c, i) => {
    const meaning = c.orientation === "reversed"
      ? c.keywords.reversed[locale] || c.keywords.reversed.en
      : c.keywords.upright[locale] || c.keywords.upright.en;
    const posLabel = cards.length === 3 ? positions[i] : null;
    return { position: posLabel, text: `${c.name[locale] || c.name.en} — ${meaning}.` };
  });

  const summary = perCard.map(pc => pc.text).join(" ");
  const reflectionPrompt = locale === "ru"
    ? "Что эти карты говорят о вашем текущем пути?"
    : "What do these cards say about your current path?";

  return { summary, perCard, reflectionPrompt };
}

function getCached(cards: DrawnCard[], locale: Locale): InterpretationResult | null {
  const date = new Date().toDateString();
  const key = `ct_interp_${cards.map(c => c.id + c.orientation).join(",")}_${locale}_${date}`;
  try {
    const cached = localStorage.getItem(key);
    if (cached) return JSON.parse(cached);
  } catch {}
  return null;
}

function setCache(cards: DrawnCard[], locale: Locale, result: InterpretationResult) {
  const date = new Date().toDateString();
  const key = `ct_interp_${cards.map(c => c.id + c.orientation).join(",")}_${locale}_${date}`;
  try {
    localStorage.setItem(key, JSON.stringify(result));
  } catch {}
}

export async function interpret(
  cards: DrawnCard[],
  locale: Locale,
  positions: string[]
): Promise<InterpretationResult> {
  // 1. Check cache
  const cached = getCached(cards, locale);
  if (cached) return cached;

  // 2. Try Ollama (local, 30s timeout)
  const ollamaResult = await ollamaInterpret(cards, locale, positions);
  if (ollamaResult && ollamaResult.summary) {
    setCache(cards, locale, ollamaResult);
    return ollamaResult;
  }

  // 3. Try API (if configured, 15s timeout)
  if (API_URL) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 15000);
      const resp = await fetch(`${API_URL}/api/interpret`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cards, locale, positions }),
        signal: controller.signal,
      });
      clearTimeout(timeout);
      if (resp.ok) {
        const result = await resp.json();
        if (result.summary) {
          setCache(cards, locale, result);
          return result;
        }
      }
    } catch {}
  }

  // 4. Fallback to mock
  const mock = mockInterpret(cards, locale, positions);
  setCache(cards, locale, mock);
  return mock;
}