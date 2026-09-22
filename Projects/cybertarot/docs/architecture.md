# HOT
# CyberTarot — System Architecture

## High-level flow

```
┌─────────────┐     ┌──────────────────┐     ┌────────────────────┐
│  Client app │────▶│ Backend API       │────▶│ AI engine (Qwen3)   │
│ (React/RN)  │◀────│ (source of truth  │◀────│ self-hosted, local  │
└─────────────┘     │  for balances,    │     └────────────────────┘
       │             │  odds, ownership) │
       │             └───────┬───────────┘
       │                     │
       ▼                     ▼
┌─────────────┐     ┌──────────────────┐
│ TON Connect │     │ TON blockchain    │
│ wallet auth │────▶│ Jetton + NFT      │
└─────────────┘     │ contracts         │
                     └──────────────────┘
```

## Core principle: on-chain ≠ source of truth for game logic

Rarity odds, activity-based Magic emission, and fraud flags are all
computed in the backend, then *executed* on-chain. The chain is the
settlement/ownership layer, not the decision layer. This keeps:
- odds tunable/auditable without a contract redeploy
- the AI engine's role strictly advisory/computational, never holding
  private keys or signing transactions itself

## Components

**Client (this prototype → production)**
- React (web) / React Native (mobile) sharing the same interpretation
  and mint UI logic
- TON Connect SDK for wallet linking
- No client-side balance authority — always reflects backend state

**Backend**
- Holds mint authority key that signs `MintMagic` / `MintCard` messages
- Runs the deterministic rarity roll (NOT the LLM — see ai-rules-package.md)
- Calls the AI engine only for (a) interpretation text, (b) anomaly
  flags, (c) moderation — never for anything that moves value
- Referral graph + activity ledger (Postgres or similar), append-only
  audit log for every Magic mint / NFT mint event

**AI engine (Qwen3, self-hosted)**
- Stateless request/response per the three prompt types in
  `ai-rules-package.md`
- No access to wallet keys, no access to raw balances beyond what's
  needed for anomaly detection
- Runs behind an internal-only endpoint, never exposed to the client

**Chain layer (TON)**
- `magic-jetton.tact` — Magic token
- `cybertarot-nft.tact` — card NFTs (soulbound base set + tradeable tiers)
- `auction-exchange.tact` — sell-back pool + peer auction

## Data flow example: user completes a reading and later mints

1. Client sends spread to backend → backend calls AI engine (interpretation
   prompt) → returns interpretation JSON → client renders it.
2. Backend credits a fixed Magic amount to the activity ledger (capped
   daily), independent of interpretation content.
3. User taps "Mint rare+". Backend checks Magic balance, deducts,
   deterministically rolls rarity (70/25/5, seeded server-side), then
   sends a signed `MintCard` message to the NFT collection contract.
4. AI engine's anomaly-detection prompt runs asynchronously against the
   day's mint log, not blocking the mint itself — flags go to a human
   review queue.

## Open items for opencode to size

- Choice of indexer for TON event ingestion (e.g. self-hosted vs.
  third-party indexing API)
- Backend framework (existing stack preference for Tomas's other
  projects has been Node/TypeScript per ghost-transport — recommend
  continuing that for consistency)
- Where Qwen3 is hosted: same infra as backend vs. separate GPU box
