
import { Wand2, Layers } from "lucide-react";
import type { LocaleConfig, MintedCard, Rarity } from "@/types";
import { RARITIES } from "@/data/game";
import { CardFace } from "./CardFace";

interface MintTabProps {
  t: LocaleConfig;
  balance: number;
  mint: (rarity: Rarity) => void;
  mintRandom: () => void;
  mintResult: MintedCard | null;
}

export function MintTab({ t, balance, mint, mintRandom, mintResult }: MintTabProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-3">
        {(["rare", "epic", "legendary"] as Rarity[]).map((r) => (
          <button
            key={r}
            onClick={() => mint(r)}
            disabled={balance < RARITIES[r].cost}
            className="rounded-lg border p-3 text-left disabled:opacity-30 hover:opacity-80 transition"
            style={{ borderColor: RARITIES[r].color }}
          >
            <Wand2 size={14} color={RARITIES[r].color} />
            <div className="text-xs mt-2" style={{ color: RARITIES[r].color }}>
              {RARITIES[r].label.en}
            </div>
            <div className="text-[10px] opacity-60 mt-1">
              {t.mintCost}: {RARITIES[r].cost} Magic
            </div>
          </button>
        ))}
      </div>
      <button
        onClick={mintRandom}
        className="w-full py-2 rounded-lg text-xs flex items-center justify-center gap-2 border"
        style={{ borderColor: "#2A2E4A" }}
      >
        <Layers size={13} /> Weighted mystery mint (70/25/5)
      </button>
      {mintResult && (
        <div className="flex items-center gap-3 p-3 rounded-lg border" style={{ borderColor: "#1E2138" }}>
          <CardFace card={mintResult} orientation="upright" rarity={mintResult.rarity} size="sm" />
          <div className="text-xs">
            Minted <span style={{ color: RARITIES[mintResult.rarity].color }}>{mintResult.name.en}</span>
            <br />
            <span className="opacity-50">tier: {mintResult.rarity}</span>
          </div>
        </div>
      )}
    </div>
  );
}
