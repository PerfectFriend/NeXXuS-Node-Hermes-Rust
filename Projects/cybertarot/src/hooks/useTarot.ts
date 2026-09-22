
import { useState, useEffect, useCallback, useRef } from "react";
import type { DrawnCard, Locale, MintedCard, Rarity } from "@/types";
import { DECK, LOCALES, RARITIES, rollRarity, shuffleDeck } from "@/data/game";
import { interpret } from "@/services/interpret";
import {
  createWell,
  tickWell,
  harvestWell,
  type ManaWellState,
} from "@/services/magicWell";

const STORAGE_KEY = "cybertarot-state";

interface PersistedState {
  balance: number;
  collection: MintedCard[];
  locale: Locale;
  refCode: string;
  well: ManaWellState;
}

function loadState(): PersistedState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      // Ensure well exists (migration safety)
      if (!parsed.well) parsed.well = createWell();
      return parsed;
    }
  } catch { /* ignore */ }
  return {
    balance: 100,
    collection: [],
    locale: "en",
    refCode: "TAROT-" + Math.random().toString(36).slice(2, 8).toUpperCase(),
    well: createWell(),
  };
}

function saveState(state: PersistedState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch { /* ignore */ }
}

export function useTarot() {
  const initial = useRef(loadState());
  const [locale, setLocale] = useState<Locale>(initial.current.locale);
  const [balance, setBalance] = useState(initial.current.balance);
  const [collection, setCollection] = useState<MintedCard[]>(initial.current.collection);
  const [refCode] = useState(initial.current.refCode);
  const [well, setWell] = useState<ManaWellState>(initial.current.well);
  const [spreadSize, setSpreadSize] = useState(3);
  const [drawn, setDrawn] = useState<DrawnCard[] | null>(null);
  const [interpretation, setInterpretation] = useState<string>("");
  const [interpretationLoading, setInterpretationLoading] = useState(false);
  const [mintResult, setMintResult] = useState<MintedCard | null>(null);
  const [copied, setCopied] = useState(false);

  // ManaWell event flags (transient — for notifications)
  const [wellFilled, setWellFilled] = useState(false);
  const [wellDried, setWellDried] = useState(false);
  const [harvestReady, setHarvestReady] = useState(initial.current.well.pending > 0);

  // Tick well every 10 seconds — check fill/dry
  useEffect(() => {
    const tick = () => {
      setWell((prev) => {
        const { well: newWell, filled, dried, harvestReady: ready } = tickWell(prev);
        if (filled) {
          setWellFilled(true);
          // Auto-clear notification after 10 seconds
          setTimeout(() => setWellFilled(false), 10000);
          // 🔔 Phase 2: send push notification here
          // if ("Notification" in window && Notification.permission === "granted") {
          //   new Notification("🪻 CyberTarot — Колодец наполнен!", {
          //     body: `Забери ${newWell.pending} маны из колодца!`,
          //   });
          // }
        }
        if (dried) {
          setWellDried(true);
          setTimeout(() => setWellDried(false), 10000);
        }
        setHarvestReady(ready);
        return newWell;
      });
    };

    // Tick immediately
    tick();
    // Then every 10 seconds
    const id = setInterval(tick, 10000);
    return () => clearInterval(id);
  }, []);

  // Persist to localStorage on changes
  useEffect(() => {
    saveState({ balance, collection, locale, refCode, well });
  }, [balance, collection, locale, refCode, well]);

  const draw = useCallback(() => {
    const cards = shuffleDeck(spreadSize);
    setDrawn(cards);
    setInterpretationLoading(true);
    const t = LOCALES[locale] || LOCALES.en;
    interpret(cards, locale, t.positions)
      .then((r) => {
        const text = r.perCard
          .map((p) => (p.position ? `${p.position}: ` : "") + p.text)
          .join(" ");
        setInterpretation(text);
      })
      .finally(() => setInterpretationLoading(false));
  }, [spreadSize, locale]);

  const mint = useCallback((rarity: Rarity) => {
    const cost = RARITIES[rarity].cost;
    if (balance < cost) return;
    setBalance((b) => b - cost);
    const card = DECK[Math.floor(Math.random() * DECK.length)];
    const minted: MintedCard = {
      ...card,
      uid: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      rarity,
      mintedAt: Date.now(),
    };
    setCollection((c) => [minted, ...c]);
    setMintResult(minted);
  }, [balance]);

  const mintRandom = useCallback(() => {
    mint(rollRarity());
  }, [mint]);

  // Harvest mana from well — replaces old earnMagic
  const harvestMana = useCallback(() => {
    setWell((prev) => {
      const { well: newWell, amount } = harvestWell(prev);
      if (amount > 0) {
        setBalance((b) => b + amount);
        setHarvestReady(false);
      }
      return newWell;
    });
  }, []);

  // Legacy earn for backwards compat (small daily bonus, separate from well)
  const earnMagic = useCallback(() => {
    setBalance((b) => b + 5);
  }, []);

  const sellCard = useCallback((uid: string) => {
    setCollection((c) => {
      const card = c.find((x) => x.uid === uid);
      if (card) {
        setBalance((b) => b + Math.round(RARITIES[card.rarity].cost * 0.6));
      }
      return c.filter((x) => x.uid !== uid);
    });
  }, []);

  const copyRef = useCallback(() => {
    navigator.clipboard?.writeText(refCode).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }, [refCode]);

  return {
    locale, setLocale,
    balance, setBalance,
    collection, setCollection,
    refCode,
    well,
    wellFilled,
    wellDried,
    harvestReady,
    spreadSize, setSpreadSize,
    drawn,
    interpretation,
    interpretationLoading,
    mintResult,
    copied,
    draw,
    mint,
    mintRandom,
    harvestMana,
    earnMagic,
    sellCard,
    copyRef,
  };
}