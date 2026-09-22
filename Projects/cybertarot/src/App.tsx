
import { Coins, Droplets, Users, Copy, Check } from "lucide-react";
import type { Locale } from "@/types";
import { LOCALES } from "@/data/game";
import { useTarot } from "@/hooks/useTarot";
import { OracleTab } from "@/components/OracleTab";
import { CollectionTab } from "@/components/CollectionTab";
import { MintTab } from "@/components/MintTab";
import { MarketTab } from "@/components/MarketTab";
import { ManaWellTab } from "@/components/ManaWellTab";
import { useState } from "react";

export default function App() {
  const tarot = useTarot();
  const t = LOCALES[tarot.locale];
  const isRTL = tarot.locale === "ar";
  const [tab, setTab] = useState(0);

  // Tabs: 0=Oracle, 1=Well, 2=Collection, 3=Mint, 4=Market
  const tabs = isRu(tarot.locale)
    ? ["Оракул", "Колодец", "Коллекция", "Минт", "Рынок"]
    : ["Oracle", "Well", "Collection", "Mint", "Market"];

  return (
    <div
      dir={isRTL ? "rtl" : "ltr"}
      className="min-h-screen w-full"
      style={{ background: "#0B0E1A", color: "#C9CBE0", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" }}
    >
      <div className="max-w-2xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-6">
          <div>
            <h1 className="font-serif text-2xl tracking-wide" style={{ color: "#E4E5F1" }}>
              {t.app}
            </h1>
            <p className="text-xs mt-1 opacity-70">{t.tag}</p>
          </div>
          <select
            value={tarot.locale}
            onChange={(e) => tarot.setLocale(e.target.value as Locale)}
            className="bg-transparent border rounded px-2 py-1 text-xs"
            style={{ borderColor: "#2A2E4A", color: "#C9CBE0" }}
          >
            {Object.entries(LOCALES).map(([k, v]) => (
              <option key={k} value={k} style={{ background: "#14162a" }}>
                {v.name}
              </option>
            ))}
          </select>
        </div>

        {/* Balance / well indicator / referral bar */}
        <div className="flex flex-wrap items-center gap-3 mb-6">
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg border text-sm" style={{ borderColor: "#2A2E4A" }}>
            <Coins size={14} color="#E8B94A" />
            <span>{t.balance}:</span>
            <span style={{ color: "#E8B94A" }}>{tarot.balance}</span>
          </div>

          {/* Mana well quick indicator */}
          <button
            onClick={() => setTab(1)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border text-xs hover:opacity-80 transition"
            style={{
              borderColor: tarot.harvestReady ? "#22D3C8" : "#2A2E4A",
              background: tarot.harvestReady ? "rgba(34,211,200,0.1)" : "transparent",
            }}
          >
            <Droplets size={14} color={tarot.harvestReady ? "#22D3C8" : "#6B7094"} />
            {tarot.well.pending > 0 ? (
              <span style={{ color: "#22D3C8" }}>🪻 {tarot.well.pending}</span>
            ) : (
              <span className="opacity-50">🪻 —</span>
            )}
          </button>

          <button
            onClick={tarot.copyRef}
            className="flex items-center gap-2 px-3 py-2 rounded-lg border text-xs hover:opacity-80 transition ml-auto"
            style={{ borderColor: "#2A2E4A" }}
          >
            <Users size={14} color="#8C6CFF" />
            {tarot.refCode}
            {tarot.copied ? <Check size={12} color="#22D3C8" /> : <Copy size={12} />}
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 border-b overflow-x-auto" style={{ borderColor: "#1E2138" }}>
          {tabs.map((label, i) => (
            <button
              key={i}
              onClick={() => setTab(i)}
              className="px-3 py-2 text-xs uppercase tracking-wider transition whitespace-nowrap"
              style={{
                color: tab === i ? "#E4E5F1" : "#6B7094",
                borderBottom: tab === i ? "2px solid #8C6CFF" : "2px solid transparent",
              }}
            >
              {label}
              {i === 1 && tarot.harvestReady && (
                <span className="ml-1 inline-block w-2 h-2 rounded-full" style={{ background: "#22D3C8" }} />
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {tab === 0 && (
          <OracleTab
            t={t}
            locale={tarot.locale}
            spreadSize={tarot.spreadSize}
            setSpreadSize={tarot.setSpreadSize}
            drawn={tarot.drawn}
            draw={tarot.draw}
            interpretation={tarot.interpretation}
            interpretationLoading={tarot.interpretationLoading}
          />
        )}
        {tab === 1 && (
          <ManaWellTab
            locale={tarot.locale}
            well={tarot.well}
            onHarvest={tarot.harvestMana}
            harvestReady={tarot.harvestReady}
            filled={tarot.wellFilled}
            dried={tarot.wellDried}
          />
        )}
        {tab === 2 && <CollectionTab collection={tarot.collection} />}
        {tab === 3 && (
          <MintTab
            t={t}
            balance={tarot.balance}
            mint={tarot.mint}
            mintRandom={tarot.mintRandom}
            mintResult={tarot.mintResult}
          />
        )}
        {tab === 4 && <MarketTab collection={tarot.collection} sellCard={tarot.sellCard} />}
      </div>
    </div>
  );
}

function isRu(locale: string): boolean {
  return locale === "ru";
}
