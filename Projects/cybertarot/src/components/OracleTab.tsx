
import { RotateCw } from "lucide-react";
import type { DrawnCard, Locale, LocaleConfig } from "@/types";
import { CardFace } from "./CardFace";

interface OracleTabProps {
  t: LocaleConfig;
  locale: Locale;
  spreadSize: number;
  setSpreadSize: (n: number) => void;
  drawn: DrawnCard[] | null;
  draw: () => void;
  interpretation: string;
  interpretationLoading: boolean;
}

export function OracleTab({ t, spreadSize, setSpreadSize, drawn, draw, interpretation, interpretationLoading }: OracleTabProps) {
  return (
    <div>
      <div className="flex gap-2 mb-5">
        <button
          onClick={() => setSpreadSize(1)}
          className="px-3 py-1.5 rounded-md text-xs border"
          style={{ borderColor: spreadSize === 1 ? "#8C6CFF" : "#2A2E4A", color: spreadSize === 1 ? "#E4E5F1" : "#6B7094" }}
        >
          {t.one}
        </button>
        <button
          onClick={() => setSpreadSize(3)}
          className="px-3 py-1.5 rounded-md text-xs border"
          style={{ borderColor: spreadSize === 3 ? "#8C6CFF" : "#2A2E4A", color: spreadSize === 3 ? "#E4E5F1" : "#6B7094" }}
        >
          {t.three}
        </button>
        <button
          onClick={draw}
          className="ml-auto px-4 py-1.5 rounded-md text-xs flex items-center gap-2"
          style={{ background: "#8C6CFF", color: "#0B0E1A" }}
        >
          <RotateCw size={12} /> {t.draw}
        </button>
      </div>

      {drawn && (
        <div className="space-y-5">
          <div className="flex gap-4 justify-center flex-wrap">
            {drawn.map((c, i) => (
              <CardFace key={i} card={c} orientation={c.orientation} rarity="common" size="lg" />
            ))}
          </div>
          <div className="text-sm leading-relaxed p-4 rounded-lg border" style={{ borderColor: "#1E2138", background: "#10122080" }}>
            {interpretationLoading ? (
              <span className="opacity-50 animate-pulse">⏳ Consulting the oracle…</span>
            ) : (
              interpretation
            )}
          </div>
        </div>
      )}
        <div className="mt-4 p-3 rounded-lg bg-yellow-900/30 border border-yellow-700/50 text-xs text-yellow-200/70 text-center">
      ⚠️ CyberTarot — это развлекательное приложение. Толкования генерируются AI и не являются прогнозом судьбы или профессиональной консультацией.
    </div>

</div>
  );
}
