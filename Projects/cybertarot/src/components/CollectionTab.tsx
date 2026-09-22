
import type { MintedCard } from "@/types";
import { CardFace } from "./CardFace";

interface CollectionTabProps {
  collection: MintedCard[];
}

export function CollectionTab({ collection }: CollectionTabProps) {
  if (collection.length === 0) {
    return <p className="text-xs opacity-60">No minted cards yet — visit Mint to acquire rare/epic/legendary NFTs.</p>;
  }
  return (
    <div className="flex flex-wrap gap-3">
      {collection.map((c) => (
        <CardFace key={c.uid} card={c} orientation="upright" rarity={c.rarity} size="sm" />
      ))}
    </div>
  );
}
