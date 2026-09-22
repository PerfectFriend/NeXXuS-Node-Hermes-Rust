
import { Gem } from "lucide-react";
import type { CardData, Rarity, Orientation } from "@/types";
import { RARITIES } from "@/data/game";

interface CardFaceProps {
  card: CardData;
  orientation?: Orientation;
  rarity?: Rarity;
  size?: "sm" | "md" | "lg";
}

export function CardFace({ card, orientation = "upright", rarity = "common", size = "md" }: CardFaceProps) {
  const rr = RARITIES[rarity];
  const dims = size === "sm" ? "w-20 h-32" : size === "lg" ? "w-36 h-56" : "w-28 h-44";

  return (
    <div
      className={`${dims} rounded-lg relative shrink-0 overflow-hidden border transition-transform duration-500`}
      style={{
        borderColor: rr.color,
        boxShadow: `0 0 18px ${rr.glow}`,
        background: "linear-gradient(160deg, #14162a 0%, #0B0E1A 65%)",
        transform: orientation === "reversed" ? "rotate(180deg)" : "none",
      }}
    >
      <div
        className="absolute inset-0 opacity-40"
        style={{ background: `radial-gradient(circle at 50% 20%, ${rr.glow}, transparent 60%)` }}
      />
      <div className="absolute inset-2 rounded-md border" style={{ borderColor: rr.color + "55" }} />
      <div className="absolute inset-0 flex flex-col items-center justify-center px-2 text-center gap-1">
        <Gem size={size === "sm" ? 12 : 16} color={rr.color} />
        <div className="font-serif text-[11px] leading-tight" style={{ color: "#E4E5F1" }}>
          {card.name.en}
        </div>
      </div>
      <div
        className="absolute bottom-1 left-1 right-1 text-center text-[8px] tracking-widest uppercase font-mono"
        style={{ color: rr.color }}
      >
        {rr.label.en}
      </div>
    </div>
  );
}
