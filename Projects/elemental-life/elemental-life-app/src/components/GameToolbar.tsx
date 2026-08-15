/**
 * GameToolbar — панель управления симуляцией.
 *
 * В режиме Песочница:
 * - Кнопки Play/Pause, Шаг, Новая игра
 * - Ползунок скорости
 * - Счётчик тиков
 * - Зум-контролы (−, процент, +, сброс)
 *
 * В режиме Головоломка (Puzzle):
 * - Всё то же самое, плюс:
 * - Информация об уровне и оставшихся каплях
 */

interface GameToolbarProps {
  mode: 'sandbox' | 'puzzle';
  running: boolean;
  tick: number;
  speed: number;
  viewportZoom: number;
  levelLabel?: string;
  totalLevels?: number;
  dropletsLeft?: number;
  onToggleRunning: () => void;
  onStep: () => void;
  onNewGame: () => void;
  onRetryLevel?: () => void;
  onSetSpeed: (speed: number) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onResetView: () => void;
  onCenterView?: () => void;
  onForceCenter?: () => void;
}

export function GameToolbar({
  mode, running, tick, speed, viewportZoom,
  levelLabel, totalLevels, dropletsLeft,
  onToggleRunning, onStep, onNewGame, onRetryLevel,
  onSetSpeed, onZoomIn, onZoomOut, onResetView, onCenterView, onForceCenter,
}: GameToolbarProps) {
  return (
    <div className="toolbar">
      {mode === 'puzzle' ? (
        <>
          <div className="puzzle-info">
            <span className="level-badge">
              {levelLabel || ''} / {totalLevels || 0}
            </span>
            <span className="droplets">💧 <b>{dropletsLeft ?? 0}</b></span>
          </div>
          <div className="toolbar-actions">
            <button className="btn primary" onClick={onToggleRunning}>
              {running ? '⏸' : '▶'}
            </button>
            <button className="btn" onClick={onRetryLevel} title="Заново">⟳</button>
            <button className="btn" onClick={onNewGame} title="Новая игра">🆕</button>
          </div>
          <div className="speed-control">
            <input
              type="range" min="40" max="600" step="20"
              value={650 - speed}
              onChange={(e) => onSetSpeed(650 - Number(e.target.value))}
              aria-label="Скорость"
            />
          </div>
          <div className="tick-badge">{tick}</div>
          <div className="zoom-controls">
            <button className="zoom-btn" onClick={onZoomOut} title="Уменьшить" aria-label="Уменьшить">−</button>
            <span className="zoom-pct">{Math.round(viewportZoom * 100)}%</span>
            <button className="zoom-btn" onClick={onZoomIn} title="Увеличить" aria-label="Увеличить">+</button>
            <button className="zoom-btn" onClick={onResetView} title="Сбросить вид" aria-label="Сбросить вид">⟲</button>
            {onCenterView && <button className="zoom-btn" onClick={onCenterView} title="По центру" aria-label="По центру">⊙</button>}
                        {onForceCenter && <button className="zoom-btn" onClick={onForceCenter} title="Центрировать (без смены масштаба)" aria-label="Центрировать">⌖</button>}
                      </div>
        </>
      ) : (
        <>
          <div className="toolbar-actions">
            <button className="btn primary" onClick={onToggleRunning}>
              {running ? '⏸' : '▶'}
            </button>
            <button className="btn" onClick={onStep} title="Шаг">⏭</button>
            <button className="btn" onClick={onNewGame} title="Новая игра">🆕</button>
          </div>
          <div className="speed-control">
            <input
              type="range" min="40" max="600" step="20"
              value={650 - speed}
              onChange={(e) => onSetSpeed(650 - Number(e.target.value))}
              aria-label="Скорость"
            />
          </div>
          <div className="tick-badge">{tick}</div>
          <div className="zoom-controls">
            <button className="zoom-btn" onClick={onZoomOut} title="Уменьшить" aria-label="Уменьшить">−</button>
            <span className="zoom-pct">{Math.round(viewportZoom * 100)}%</span>
            <button className="zoom-btn" onClick={onZoomIn} title="Увеличить" aria-label="Увеличить">+</button>
            <button className="zoom-btn" onClick={onResetView} title="Сбросить вид" aria-label="Сбросить вид">⟲</button>
            {onCenterView && <button className="zoom-btn" onClick={onCenterView} title="По центру" aria-label="По центру">⊙</button>}
                        {onForceCenter && <button className="zoom-btn" onClick={onForceCenter} title="Центрировать (без смены масштаба)" aria-label="Центрировать">⌖</button>}
                      </div>
        </>
      )}
    </div>
  );
}
