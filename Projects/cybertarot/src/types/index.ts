
// CyberTarot — Type Definitions

export type Locale = "en" | "ru" | "es" | "zh" | "hi" | "ar" | "pt" | "ja" | "fr" | "de";

export type Arcana = "major" | "minor";
export type Suit = "wands" | "cups" | "swords" | "pentacles";
export type Rarity = "common" | "rare" | "epic" | "legendary";
export type Orientation = "upright" | "reversed";

export interface LocalizedString {
  en: string;
  ru: string;
  [key: string]: string;
}

export interface CardData {
  id: string;
  arcana: Arcana;
  number: number;
  name: LocalizedString;
  keywords: {
    upright: LocalizedString;
    reversed: LocalizedString;
  };
  default_rarity: Rarity;
  suit?: Suit;
  element?: string;
  court?: string;
}

export interface DrawnCard extends CardData {
  orientation: Orientation;
}

export interface MintedCard extends CardData {
  uid: string;
  rarity: Rarity;
  mintedAt: number;
}

export interface RarityConfig {
  label: LocalizedString;
  color: string;
  glow: string;
  weight: number;
  cost: number;
}

export interface LocaleConfig {
  name: string;
  app: string;
  tag: string;
  draw: string;
  one: string;
  three: string;
  balance: string;
  ref: string;
  tabs: string[];
  mintBtn: string;
  mintCost: string;
  earn: string;
  copy: string;
  copied: string;
  reversedTag: string;
  uprightTag: string;
  positions: string[];
}

export interface InterpretationResult {
  summary: string;
  perCard: { position: string | null; text: string }[];
  reflectionPrompt: string;
}
