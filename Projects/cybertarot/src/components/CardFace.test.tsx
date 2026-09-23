
// Component tests: CardFace renders card with correct orientation, rarity, size
// (EVOLUTION_PLAN.md 1.4: "Component: CardFace рендерит карту с правильной ориентацией")

import { describe, it, expect, afterEach } from "vitest";
import { render, cleanup } from "@testing-library/react";
import { CardFace } from "@/components/CardFace";
import { RARITIES } from "@/data/game";
import type { CardData } from "@/types";

afterEach(cleanup);

// jsdom normalizes hex colors to rgb() on inline style reads
function toRgb(hex: string): string {
  const n = parseInt(hex.slice(1), 16);
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
}

const card: CardData = {
  id: "major-0",
  arcana: "major",
  number: 0,
  name: { en: "The Fool", ru: "Шут" },
  keywords: {
    upright: { en: "beginnings", ru: "начала" },
    reversed: { en: "recklessness", ru: "безрассудство" },
  },
  default_rarity: "common",
};

describe("CardFace", () => {
  it("renders the card name", () => {
    const { getByText } = render(<CardFace card={card} />);
    expect(getByText("The Fool")).toBeTruthy();
  });

  it("is upright by default (no rotation transform)", () => {
    const { getByText } = render(<CardFace card={card} />);
    const face = getByText("The Fool").parentElement!.parentElement!;
    expect(face.style.transform).toBe("none");
  });

  it("rotates 180deg when orientation is reversed", () => {
    const { getByText } = render(<CardFace card={card} orientation="reversed" />);
    const face = getByText("The Fool").parentElement!.parentElement!;
    expect(face.style.transform).toBe("rotate(180deg)");
  });

  it("keeps upright transform explicitly set", () => {
    const { getByText } = render(<CardFace card={card} orientation="upright" />);
    const face = getByText("The Fool").parentElement!.parentElement!;
    expect(face.style.transform).toBe("none");
  });

  it("applies rarity color to border and renders rarity label", () => {
    const { getByText } = render(<CardFace card={card} rarity="rare" />);
    const face = getByText("The Fool").parentElement!.parentElement!;
    expect(face.style.borderColor).toBe(toRgb(RARITIES.rare.color));
    expect(getByText("Rare")).toBeTruthy();
  });

  it("applies legendary rarity styling", () => {
    const { getByText } = render(<CardFace card={card} rarity="legendary" />);
    const face = getByText("The Fool").parentElement!.parentElement!;
    expect(face.style.borderColor).toBe(toRgb(RARITIES.legendary.color));
    expect(getByText("Legendary")).toBeTruthy();
  });

  it("defaults to common rarity styling", () => {
    const { getByText } = render(<CardFace card={card} />);
    const face = getByText("The Fool").parentElement!.parentElement!;
    expect(face.style.borderColor).toBe(toRgb(RARITIES.common.color));
    expect(getByText("Common")).toBeTruthy();
  });

  it.each([
    ["sm", "w-20"],
    ["md", "w-28"],
    ["lg", "w-36"],
  ] as const)("applies %s size class", (size, expected) => {
    const { getByText } = render(<CardFace card={card} size={size} />);
    const face = getByText("The Fool").parentElement!.parentElement!;
    expect(face.className).toContain(expected);
  });
});
