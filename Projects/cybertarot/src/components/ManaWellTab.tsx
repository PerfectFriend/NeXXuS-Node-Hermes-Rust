
// ManaWellTab — визуализация колодца маны с таймерами и кнопкой сбора

import { useState, useEffect } from "react";
import { Droplets, Clock, AlertTriangle, TrendingUp } from "lucide-react";
import type { Locale } from "@/types";
import type { ManaWellState } from "@/services/magicWell";
import {
  timeUntilFill,
  timeUntilDry,
  formatTimeLeft,
} from "@/services/magicWell";

interface ManaWellTabProps {
  locale: Locale;
  well: ManaWellState;
  onHarvest: () => void;
  harvestReady: boolean;
  filled: boolean;
  dried: boolean;
}

export function ManaWellTab({
  locale,
  well,
  onHarvest,
  harvestReady,
  filled,
  dried,
}: ManaWellTabProps) {
  // Tick every second for countdown
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const fillMs = timeUntilFill(well);
  const dryMs = timeUntilDry(well);
  const isRu = locale === "ru";

  // Risk level: how close to drying out
  const dryProgress = Math.max(0, Math.min(1, 1 - dryMs / (6 * 60 * 60 * 1000)));
  const riskLevel = dryProgress > 0.75 ? "high" : dryProgress > 0.5 ? "medium" : "low";
  const riskColor = riskLevel === "high" ? "#FF4444" : riskLevel === "medium" ? "#E8B94A" : "#22D3C8";

  return (
    <div className="space-y-5">
      {/* Notification banners */}
      {filled && (
        <div
          className="p-3 rounded-lg border flex items-center gap-2 text-sm animate-pulse"
          style={{ borderColor: "#22D3C8", background: "rgba(34,211,200,0.1)" }}
        >
          <Droplets size={16} color="#22D3C8" />
          {isRu ? "🪻 Колодец наполнился! Забери ману." : "🪻 The well is full! Harvest your mana."}
        </div>
      )}
      {dried && (
        <div
          className="p-3 rounded-lg border flex items-center gap-2 text-sm"
          style={{ borderColor: "#FF4444", background: "rgba(255,68,68,0.1)" }}
        >
          <AlertTriangle size={16} color="#FF4444" />
          {isRu
            ? "💔 Колодец пересох! Мана потеряна. Начинаем заново."
            : "💔 The well ran dry! Mana lost. Starting fresh."}
        </div>
      )}

      {/* Well visual */}
      <div className="flex flex-col items-center gap-4 py-6">
        {/* Well circle showing pending mana */}
        <div
          className="relative w-48 h-48 rounded-full flex items-center justify-center border-4 transition-all duration-500"
          style={{
            borderColor: harvestReady ? "#22D3C8" : "#2A2E4A",
            background: harvestReady
              ? "radial-gradient(circle at 50% 30%, rgba(34,211,200,0.15), transparent 70%)"
              : "transparent",
            boxShadow: harvestReady ? `0 0 40px rgba(34,211,200,0.3)` : "none",
          }}
        >
          <Droplets
            size={64}
            color={harvestReady ? "#22D3C8" : "#2A2E4A"}
            className="transition-colors duration-500"
          />
          <div className="absolute bottom-12 text-4xl font-bold" style={{ color: harvestReady ? "#E4E5F1" : "#6B7094" }}>
            {well.pending}
          </div>
          <div className="absolute bottom-4 text-xs uppercase tracking-widest opacity-60">
            {isRu ? "маны" : "mana"}
          </div>
        </div>

        {/* Harvest button */}
        <button
          onClick={onHarvest}
          disabled={!harvestReady}
          className="px-8 py-3 rounded-lg text-sm flex items-center gap-2 transition disabled:opacity-30"
          style={{
            background: harvestReady ? "#22D3C8" : "transparent",
            color: harvestReady ? "#0B0E1A" : "#6B7094",
            border: harvestReady ? "none" : "1px solid #2A2E4A",
          }}
        >
          <Droplets size={16} />
          {harvestReady
            ? isRu ? "Забрать ману" : "Harvest mana"
            : isRu ? "Колодец пуст" : "Well is empty"}
        </button>
      </div>

      {/* Timers */}
      <div className="grid grid-cols-2 gap-3">
        {/* Next fill timer */}
        <div className="p-3 rounded-lg border" style={{ borderColor: "#1E2138" }}>
          <div className="flex items-center gap-2 text-xs opacity-70 mb-2">
            <Clock size={12} /> {isRu ? "Следующее наполнение" : "Next fill"}
          </div>
          <div className="text-lg font-mono" style={{ color: fillMs <= 0 ? "#22D3C8" : "#C9CBE0" }}>
            {formatTimeLeft(fillMs, locale)}
          </div>
          {well.pending > 0 && (
            <div className="text-[10px] opacity-50 mt-1">
              +{well.pending + 1} {isRu ? "маны будет" : "mana next"}
            </div>
          )}
        </div>

        {/* Dry timer — risk meter */}
        <div className="p-3 rounded-lg border" style={{ borderColor: riskColor + "44" }}>
          <div className="flex items-center gap-2 text-xs opacity-70 mb-2">
            <AlertTriangle size={12} color={riskColor} /> {isRu ? "Пересыхание через" : "Runs dry in"}
          </div>
          <div className="text-lg font-mono" style={{ color: riskColor }}>
            {formatTimeLeft(dryMs, locale)}
          </div>
          {/* Risk bar */}
          <div className="mt-2 h-1 rounded-full overflow-hidden" style={{ background: "#1E2138" }}>
            <div
              className="h-full rounded-full transition-all duration-1000"
              style={{ width: `${dryProgress * 100}%`, background: riskColor }}
            />
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="p-2 rounded-lg border" style={{ borderColor: "#1E2138" }}>
          <TrendingUp size={12} className="mx-auto mb-1" color="#22D3C8" />
          <div className="text-lg font-bold" style={{ color: "#22D3C8" }}>{well.totalHarvests}</div>
          <div className="text-[9px] opacity-50 uppercase">{isRu ? "Сборов" : "Harvests"}</div>
        </div>
        <div className="p-2 rounded-lg border" style={{ borderColor: "#1E2138" }}>
          <Droplets size={12} className="mx-auto mb-1" color="#E8B94A" />
          <div className="text-lg font-bold" style={{ color: "#E8B94A" }}>{well.totalHarvested}</div>
          <div className="text-[9px] opacity-50 uppercase">{isRu ? "Всего маны" : "Total mana"}</div>
        </div>
        <div className="p-2 rounded-lg border" style={{ borderColor: "#1E2138" }}>
          <AlertTriangle size={12} className="mx-auto mb-1" color="#FF4444" />
          <div className="text-lg font-bold" style={{ color: "#FF4444" }}>{well.totalDryouts}</div>
          <div className="text-[9px] opacity-50 uppercase">{isRu ? "Пересыханий" : "Dry-outs"}</div>
        </div>
      </div>

      {/* How it works */}
      <div className="p-4 rounded-lg border text-xs opacity-60" style={{ borderColor: "#1E2138" }}>
        <p className="font-bold mb-2 opacity-80">{isRu ? "📜 Как работает колодец" : "📜 How the well works"}</p>
        {isRu ? (
          <>
            <p>• Первая мана: 1. Каждые 6 часов: +1.</p>
            <p>• Не забрал вовремя → колодец пересыхает, начинаем заново.</p>
            <p>• Чем больше маны — тем больше потеря. Заходи регулярно!</p>
            <p>• Полученную ману трать на коллекционные карты в Mint.</p>
          </>
        ) : (
          <>
            <p>• First mana: 1. Every 6 hours: +1.</p>
            <p>• Don't harvest in time → well runs dry, start over.</p>
            <p>• More mana = bigger loss. Come back regularly!</p>
            <p>• Spend mana on collectible cards in the Mint tab.</p>
          </>
        )}
      </div>
    </div>
  );
}
