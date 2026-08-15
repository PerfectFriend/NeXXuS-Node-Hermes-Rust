/**
 * PuzzleOverlay — оверлей победы/поражения в режиме Головоломка.
 *
 * Победа:
 * - Поздравление с прохождением уровня
 * - Кнопка "Следующий уровень" (если не последний)
 * - Кнопка "Переиграть"
 *
 * Поражение:
 * - Сообщение о конце капель
 * - Кнопка "Попробовать снова"
 *
 * Полоса прогресса стабильности показывается во время игры:
 * - Отображает winStreak / WIN_STABLE_TICKS
 */

interface PuzzleOverlayProps {
  puzzleWon: boolean;
  puzzleFailed: boolean;
  winStreak: number;
  winStableTicks: number;
  levelIndex: number;
  totalLevels: number;
  onNextLevel: () => void;
  onRetryLevel: () => void;
}

export function PuzzleOverlay({
  puzzleWon, puzzleFailed, winStreak, winStableTicks,
  levelIndex, totalLevels, onNextLevel, onRetryLevel,
}: PuzzleOverlayProps) {
  return (
    <>
      {/* Оверлей победы/поражения */}
      {(puzzleWon || puzzleFailed) && (
        <div className="puzzle-overlay">
          <div className="puzzle-overlay-card">
            {puzzleWon ? (
              <>
                <h2 className="overlay-title">🌿 Уровень пройден!</h2>
                <p className="overlay-text">
                  Экосистема сама исцеляет любую новую пустоту — порядок наведён.
                </p>
                {levelIndex < totalLevels - 1 ? (
                  <button className="btn primary" onClick={onNextLevel}>
                    Следующий уровень →
                  </button>
                ) : (
                  <p className="overlay-text">
                    Это был последний уровень — ты прошёл всю головоломку!
                  </p>
                )}
                <button className="btn" onClick={onRetryLevel}>Переиграть</button>
              </>
            ) : (
              <>
                <h2 className="overlay-title">💀 Капли закончились</h2>
                <p className="overlay-text">
                  Пустыня не зажила достаточно быстро — попробуй другую стратегию полива.
                </p>
                <button className="btn primary" onClick={onRetryLevel}>
                  Попробовать снова
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Полоса прогресса стабильности */}
      {!puzzleWon && !puzzleFailed && (
        <div className="win-progress">
          <div className="win-progress-header">
            <span>Стабильность</span>
            <span>{winStreak} / {winStableTicks}</span>
          </div>
          <div className="win-progress-track">
            <div
              className="win-progress-fill"
              style={{ width: `${Math.min(100, (winStreak / winStableTicks) * 100)}%` }}
            />
          </div>
        </div>
      )}
    </>
  );
}
