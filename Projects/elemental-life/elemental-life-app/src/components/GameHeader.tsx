/**
 * GameHeader — шапка приложения с переключателем режимов и кнопками.
 *
 * Содержит:
 * - Название игры
 * - Переключатель Песочница / Головоломка (🧪 / 💧)
 * - Кнопка настроек ⚙️
 * - Кнопка полноэкранного режима ⛶
 */

const MODES = ['sandbox', 'puzzle'] as const;
type Mode = (typeof MODES)[number];

interface GameHeaderProps {
  mode: Mode;
  onSwitchMode: (mode: Mode) => void;
  onOpenSettings: () => void;
  onToggleFullscreen: () => void;
  onExitGame: () => void;
  onOpenInstagramImport: () => void;
}

export function GameHeader({ mode, onSwitchMode, onOpenSettings, onToggleFullscreen, onExitGame, onOpenInstagramImport }: GameHeaderProps) {
  return (
    <header className="header">
      <div className="header-left">
        <button className="icon-btn exit-btn" onClick={onExitGame} title="Выйти из игры" aria-label="Выйти из игры">
          ⏻
        </button>
        <h1 className="title">⬢ Элементарная жизнь</h1>
      </div>
      <div className="header-right">
        <div className="mode-switch">
          {MODES.map((m) => (
            <button
              key={m}
              className={`mode-btn ${mode === m ? 'active' : ''}`}
              onClick={() => m !== mode && onSwitchMode(m)}
              aria-label={m === 'sandbox' ? 'Песочница' : 'Головоломка'}
            >
              {m === 'sandbox' ? '🧪' : '💧'}
            </button>
          ))}
        </div>
        <button className="icon-btn" onClick={onOpenInstagramImport} title="Импорт уровня из Instagram" aria-label="Импорт из Instagram">
          📸
        </button>
        <button className="icon-btn" onClick={onOpenSettings} title="Настройки" aria-label="Настройки">
          ⚙️
        </button>
        <button className="icon-btn" onClick={onToggleFullscreen} title="Полноэкранный режим" aria-label="Полноэкранный">
          ⛶
        </button>
      </div>
    </header>
  );
}
