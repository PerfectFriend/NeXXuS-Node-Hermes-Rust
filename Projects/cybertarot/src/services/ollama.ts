
// Connects to local Ollama for AI tarot interpretations

import type { DrawnCard, InterpretationResult, Locale } from "@/types";

const OLLAMA_URL = import.meta.env.VITE_OLLAMA_URL || "http://localhost:11434";
const MODEL = "qwen3:8b";

function hashSeed(cards: DrawnCard[], locale: Locale): number {
  const date = new Date().toDateString();
  const key = cards.map(c => c.id + c.orientation).join(",") + date + locale;
  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = ((hash << 5) - hash) + key.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash);
}

export async function ollamaInterpret(
  cards: DrawnCard[],
  locale: Locale,
  positions: string[]
): Promise<InterpretationResult | null> {
  const seed = hashSeed(cards, locale);

  const systemPrompt = `You are a cyberpunk tarot reader. Respond in ${locale === "ru" ? "Russian" : "English"}. Return ONLY valid JSON with keys: perCard (array of {position, text}), summary (string), advice24h (string). Each card gets 2-3 sentences. Summary 3-4 sentences. Advice 1-2 practical sentences for next 24h.`;

  const userMessage = cards.map((c, i) => {
    const pos = positions[i] || `Position ${i + 1}`;
    const orient = c.orientation === "reversed" ? " (Reversed)" : "";
    const meaning = c.orientation === "reversed"
      ? (c.keywords.reversed[locale] || c.keywords.reversed.en)
      : (c.keywords.upright[locale] || c.keywords.upright.en);
    return `Card ${i + 1}: ${c.name[locale] || c.name.en}${orient} — ${pos}. Meaning: ${meaning}`;
  }).join("\n");

  const body = {
    model: MODEL,
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: userMessage }
    ],
    stream: false,
    options: {
      temperature: 0.9,
      top_p: 0.95,
      seed: seed,
      num_ctx: 4096,
    },
    format: "json",
  };

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 30000);

    const resp = await fetch(`${OLLAMA_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (!resp.ok) return null;

    const data = await resp.json();
    const content = data.message?.content || "";
    const parsed = JSON.parse(content);

    return {
      summary: parsed.summary || "",
      perCard: (parsed.perCard || []).map((pc: any, i: number) => ({
        position: positions[i] || null,
        text: pc.text || "",
      })),
      reflectionPrompt: locale === "ru"
        ? "Что эти карты говорят о вашем текущем пути?"
        : "What do these cards say about your current path?",
    };
  } catch {
    return null;
  }
}
