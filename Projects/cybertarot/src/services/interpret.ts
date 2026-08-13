// CyberTarot — Interpretation service
// Phase 1: mock implementation. Phase 2: swap for Qwen3/Ollama API.

import type { DrawnCard, InterpretationResult, Locale } from "@/types";

export async function interpret(
  cards: DrawnCard[],
  locale: Locale,
  positions: string[]
): Promise<InterpretationResult> {
  // Phase 1: deterministic mock from keywords
  // Phase 2: POST to /api/interpret with cards + locale, get AI response

  const perCard = cards.map((c, i) => {
    const meaning = c.orientation === "reversed"
      ? c.keywords.reversed[locale] || c.keywords.reversed.en
      : c.keywords.upright[locale] || c.keywords.upright.en;
    const posLabel = cards.length === 3 ? positions[i] : null;
    return { position: posLabel, text: `${c.name[locale] || c.name.en} — ${meaning}.` };
  });

  const summary = cards.length === 1
    ? perCard[0].text
    : `${perCard[0].text} ${perCard[1]?.text ?? ""} ${perCard[2]?.text ?? ""}`;

  const reflectionPrompt = locale === "ru"
    ? "Что эти карты говорят о вашем текущем пути?"
    : "What do these cards say about your current path?";

  return { summary, perCard, reflectionPrompt };
}
