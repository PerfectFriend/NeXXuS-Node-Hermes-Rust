# CyberTarot Tokenomics — TON Spec

## Chain & standards

- **Chain:** TON (The Open Network) — NOT the defunct Telegram GRAM project.
- **Fungible token (Magic):** TON **Jetton** standard.
- **Card NFTs:** TON NFT standard (**TIP-4**, collection + item contracts).
- **Wallet UX:** TON Connect for web, native Telegram wallet for in-app.

## Asset tiers

| Tier | Acquisition | Transferable | Notes |
|---|---|---|---|
| Base 78-card deck | Free on signup | No (soul-bound) | Prevents day-1 farming/dumping |
| Rare / Epic / Legendary | Minted with Magic | Yes | Weighted random: 70/25/5 |
| Gold / Silver mini-sets | Limited-window direct sale | Yes | Fixed price + fixed supply, no gacha |

Gacha mechanics apply **only** to the rare+ single-card mint, never to
mini-sets — mini-sets are direct-buy to reduce regulatory exposure (fixed
price/fixed odds sales face far less scrutiny than randomized loot boxes).

## Magic emission (earn side)

Magic is **not** purchasable with fiat or crypto directly — it is earned,
which keeps it structurally closer to a loyalty/utility point than a
security. (Not legal advice — confirm with counsel before launch.)

- Daily login streak: flat small amount, decreasing marginal return to
  discourage bot farming
- Completed reading: small fixed amount, capped per day
- Referral: percentage of the **referred user's own earned Magic**, not a
  flat bonus per signup — this avoids classic pyramid-recruitment shape
  (reward tracks real usage, not just headcount)
- Referral percentage decays over time to avoid infinite passive farms

## Magic spend side

- Mint rare/epic/legendary
- Enter limited mini-set sale windows (some sets may require Magic + a
  small allowlist criterion, e.g. account age, to slow bot sniping)
- Marketplace fee (small % burn on every P2P trade — deflationary sink so
  emission doesn't run away)

## Auto-exchange / auction

- Sell-back path: instant sell to a bonding-curve-style pool at a
  discount to floor (prevents users treating mint→instant-sell as a free
  arbitrage loop that drains the Magic supply)
- Peer auction: standard English auction, TON-native escrow contract
  holds the NFT until settlement
- Anti-wash-trading: same-wallet-cluster trades between accounts sharing
  device/IP fingerprint are excluded from any volume-based rewards

## Compliance flags for legal review (not exhaustive)

1. Loot-box-style randomized mint — several jurisdictions require
   disclosed odds or restrict entirely (e.g. Belgium bans them outright).
2. Any path that lets Magic be effectively cashed out to fiat value
   (even indirectly via NFT resale) increases scrutiny under
   e-money / virtual asset service provider (VASP) rules in many
   countries.
3. Referral-based token emission can resemble MLM reward structures if
   not carefully scoped to usage rather than recruitment — spec above
   ties it to the referred user's *activity*, not their *signup*, for
   this reason, but a lawyer should confirm this is sufficient in your
   target markets.
