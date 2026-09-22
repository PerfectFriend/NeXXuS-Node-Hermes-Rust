# HOT
# CyberTarot — handoff package for opencode

Prototype built by Claude. This package hands off everything needed to move
from "clickable concept" to a real app. Nothing here touches a live chain or
a live model — all mock logic is isolated so it's a clean swap.

## What's done (by Claude)

| Piece | File | Status |
|---|---|---|
| Interactive UI prototype (React) | `../../CyberTarot.jsx` (in outputs) | Working mock, in-memory state only |
| Full 78-card dataset (EN+RU) | `data/tarot-deck.json` | Complete, needs 8 more locales |
| AI engine rule package | `docs/ai-rules-package.md` | Complete spec + system prompt |
| Tokenomics + TON spec | `docs/tokenomics-ton-spec.md` | Complete spec |
| Smart contract outlines (Tact) | `contracts/*.tact` | Skeleton / pseudocode, NOT audited, NOT compiled |
| i18n key structure | `localization/i18n-keys.json` | Structure + en/ru filled, 8 locales stubbed |
| System architecture | `docs/architecture.md` | Complete spec |

## What opencode needs to do

1. **Wire the real AI engine**: replace `interpretation()` mock in
   `CyberTarot.jsx` with a call to the local Qwen3 instance running the
   system prompt in `ai-rules-package.md`. Must return the JSON schema
   defined there, not free text.
2. **Deploy contracts**: the `.tact` files are structural skeletons showing
   entrypoints and storage layout — they have NOT been compiled, tested, or
   security-reviewed. Treat them as a spec for a Tact/FunC developer, not
   as production code.
3. **Fill remaining locale strings** in `localization/i18n-keys.json` for
   zh/hi/ar/pt/ja/fr/de (currently English fallback placeholders).
4. **Persistence layer**: prototype uses in-memory React state only. Needs
   a real backend (balances, ownership, mint history) before any token has
   real value — client-side state is not authoritative for anything
   financial.
5. **Legal/compliance gate before launch**: loot-box-style randomized mint
   + secondary market for the reward token is regulated as gambling in
   several jurisdictions (e.g. Belgium, Netherlands classify loot boxes
   this way; other countries require probability disclosure). This is a
   blocking item, not a nice-to-have — flag to Tomas before any real-money
   integration ships.

## Directory map
```
cybertarot/
├── data/tarot-deck.json          78-card dataset, bilingual
├── contracts/
│   ├── magic-jetton.tact         Magic token (TON Jetton standard)
│   ├── cybertarot-nft.tact       Card NFT collection (TIP-4)
│   └── auction-exchange.tact     Auto auction / sell-back mechanism
├── localization/i18n-keys.json   UI string keys, 10 locales
└── docs/
    ├── ai-rules-package.md
    ├── tokenomics-ton-spec.md
    └── architecture.md
```
