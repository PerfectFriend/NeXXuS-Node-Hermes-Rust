/**
 * BrushSelector — выбор кисти для режима Песочница.
 *
 * Показывает 6 кнопок (по числу стихий) с цветом и иконкой.
 * В режиме Головоломка показывает подсказку "кликай по пустыне".
 */

import { STATE, COLORS, STATE_LABELS } from '../engine/engine';
import type { StateKey } from '../engine/engine';

const STATE_ICONS: Record<string, string> = {
  empty: '⬛', life: '🟢', fire: '🔴',
  water: '🔵', earth: '🟤', steam: '⚪',
} as const;

interface BrushSelectorProps {
  mode: 'sandbox' | 'puzzle';
  brush: StateKey;
  onSetBrush: (brush: StateKey) => void;
}

export function BrushSelector({ mode, brush, onSetBrush }: BrushSelectorProps) {
  if (mode === 'puzzle') {
    return (
      <div className="brush-row">
        <span className="hint">💧 Кликай по пустыне — залить водой</span>
      </div>
    );
  }

  return (
    <div className="brush-row">
      {Object.values(STATE).map((s) => (
        <button
          key={s}
          onClick={() => onSetBrush(s as StateKey)}
          className={`brush-btn ${brush === s ? 'active' : ''}`}
          style={{ background: COLORS[s as StateKey], borderColor: brush === s ? '#fff' : 'transparent' }}
          title={STATE_LABELS[s as StateKey]}
          aria-label={STATE_LABELS[s as StateKey]}
        >
          <span className="brush-icon">{STATE_ICONS[s]}</span>
        </button>
      ))}
    </div>
  );
}
