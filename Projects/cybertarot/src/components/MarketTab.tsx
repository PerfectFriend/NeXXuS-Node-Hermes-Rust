
import { Store, Gem } from "lucide-react";
import type { MintedCard } from "@/types";
import { RARITIES } from "@/data/game";

interface MarketTabProps {
  collection: MintedCard[];
  sellCard: (uid: string) => void;
}

export function MarketTab({ collection, sellCard }: MarketTabProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs opacity-70 mb-2">
        <Store size={14} /> Auction / auto-exchange (mock)
      </div>
      {collection.length === 0 ? (
        <p className="text-xs opacity-60">Mint a card first to list it on the auction.</p>
      ) : (
        collection.map((c) => (
          <div key={c.uid} className="flex items-center justify-between p-2 rounded-lg border text-xs" style={{ borderColor: "#1E2138" }}>
            <div className="flex items-center gap-2">
              <Gem size={12} color={RARITIES[c.rarity].color} />
              {c.name.en}
            </div>
            <button
              onClick={() => sellCard(c.uid)}
              className="px-2 py-1 rounded border"
              style={{ borderColor: "#2A2E4A" }}
            >
              Sell ~{Math.round(RARITIES[c.rarity].cost * 0.6)} Magic
            </button>
          </div>
        ))
      )}
    </div>
  );
}
