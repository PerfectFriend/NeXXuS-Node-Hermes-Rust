/**
 * StatsDisplay — панель статистики и водного баланса.
 *
 * Содержит:
 * - Водный бар: иконка, дрифт воды, количество воды/пара/сумма
 * - Статистика по всем стихиям: цветной кружок, иконка, количество
 */

import { STATE, COLORS } from '../engine/engine';
import type { StateKey, WaterStats } from '../engine/engine';

const STATE_ICONS: Record<string, string> = {
  empty: '⬛', life: '🟢', fire: '🔴',
  water: '🔵', earth: '🟤', steam: '⚪',
};

interface StatsDisplayProps {
  counts: Record<StateKey, number>;
  waterStats: WaterStats;
  waterDrift: number;
}

export function StatsDisplay({ counts, waterStats, waterDrift }: StatsDisplayProps) {
  const waterBarColor = waterDrift === 0 ? '#2ecc71' : '#ff5a36';
  const waterBarText = waterDrift === 0 ? '✓' : `Δ${waterDrift > 0 ? '+' : ''}${waterDrift}`;

  return (
    <>
      <div className="water-bar">
        <div className="water-bar-header">
          <span>💧</span>
          <span style={{ color: waterBarColor, fontWeight: 700 }}>{waterBarText}</span>
        </div>
        <div className="water-bar-row">
          <span>💧 {waterStats.water}</span>
          <span>⚪ {waterStats.steam}</span>
          <span>Σ {waterStats.total}</span>
        </div>
      </div>
      <div className="stats-row">
        {Object.values(STATE).map((s) => (
          <div key={s} className="stat-chip">
            <span className="stat-dot" style={{ background: COLORS[s as StateKey] }} />
            <span className="stat-icon">{STATE_ICONS[s]}</span>
            <b>{counts[s as StateKey]}</b>
          </div>
        ))}
      </div>
    </>
  );
}
