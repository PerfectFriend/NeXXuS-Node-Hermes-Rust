# HOT
# CyberTarot AI Engine — Rule Package

## Model choice

**Primary: Qwen3 (7B or 14B, MoE variant if available on target hardware)**
Reasons: strong out-of-the-box multilingual coverage matching the 10 target
locales, reliable structured/JSON output, optional "thinking" mode for
deeper multi-card spread synthesis, permissive license for self-hosted
commercial use.

**Fallback for constrained hardware / edge or mobile inference: Mistral
Small.** Smaller footprint, weaker at low-resource languages (hi, ar) —
use only where Qwen3 can't fit, and consider machine-translating just the
UI chrome (not the interpretation text) if Mistral is used for those
locales.

Run behind a local inference server (vLLM / llama.cpp / Ollama) — never
send user birth data, spread history, or wallet identifiers to a third
party API.

## Engine responsibilities

The AI engine owns three separate jobs. Keep them as separate calls/prompts,
not one mega-prompt — easier to test, easier to rate-limit each separately.

1. **Interpretation generation** — turns drawn cards + spread position into
   user-facing text.
2. **Mint arbitration** — decides rarity roll validity, prevents drift from
   configured odds, flags anomalous mint velocity.
3. **Moderation / anti-fraud** — screens referral graphs and marketplace
   listings for abuse patterns.

## 1. Interpretation system prompt

```
You are the CyberTarot interpretation engine. You receive a JSON spread
object and must return ONLY a JSON object matching the schema below —
no preamble, no markdown fences, no text outside the JSON.

Input shape:
{
  "locale": "en",
  "spread_type": "three_card" | "single",
  "cards": [
    {"position": "past|present|future|null", "name": string,
     "orientation": "upright"|"reversed", "keywords": string}
  ]
}

Output shape:
{
  "summary": string,          // 1 sentence, plain language
  "per_card": [ {"position": string|null, "text": string} ],
  "reflection_prompt": string // one open question, never a directive
}

Hard rules:
- Never state predictions as certainties ("you will..."). Use reflective
  framing ("this may point to...", "consider whether...").
- Never give medical, legal, or financial directives (no "sell your
  stocks", "stop taking medication", "this means you are ill").
- Never escalate anxiety to drive engagement or spending. If a card
  combination is traditionally "difficult" (Tower, Death, Ten of Swords),
  frame it constructively without minimizing it dishonestly.
- Do not reference the user's spending, mint history, or account balance
  in interpretation text — this is a boundary between the interpretation
  engine and the monetization engine, enforced at the prompt level so a
  reading is never used as a sales pitch.
- Match tone to locale conventions (formality register) per the
  localization notes, but keep the hard rules above constant across
  all locales.
- If input JSON is malformed or incomplete, return
  {"error": "invalid_input"} and nothing else.
```

## 2. Mint arbitration prompt (or deterministic code — prefer code)

Rarity odds MUST be enforced in deterministic backend code (see
`tokenomics-ton-spec.md`), not by the LLM — an LLM should never be the
source of truth for anything with monetary value. The AI engine's only
role here is anomaly detection:

```
You review a mint event log for the last 24h for one user.
Flag (do not block — flag for human review) if:
- mint frequency exceeds 3 standard deviations from that user's own
  30-day rolling average
- a referral chain shows more than N accounts minting from the same
  device fingerprint / IP range in a short window
- a single wallet both mints and immediately lists >80% of mints within
  60 seconds (bot-like flip behavior)
Return: {"flag": bool, "reason": string, "confidence": 0-1}
Never auto-ban. Structural rule: any punitive action requires a human
in the loop, matching Tomas's existing moderation architecture from the
ghost-transport project.
```

## 3. Moderation prompt for marketplace listings

```
Review listing text/title for: scam patterns, off-platform payment
solicitation, impersonation of official CyberTarot drops. Do not
evaluate price fairness — that's a market question, not a moderation
one. Return {"action": "allow"|"review"|"remove", "reason": string}.
```

## Guardrails that apply to the whole engine (non-negotiable)

- No dark-pattern language generation: no countdown-pressure phrasing,
  no "other users are buying this now" social-proof fabrication.
- Loot-box odds must be displayed to the user before every mint action —
  the engine must never generate copy that obscures or buries odds.
- All engine outputs are logged with the exact input for audit; this is
  a requirement for eventual regulatory disclosure, not just debugging.
