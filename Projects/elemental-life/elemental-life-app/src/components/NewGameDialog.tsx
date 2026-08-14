import { useState, useEffect } from 'react';
import { GEOMETRY_PRESETS, PUZZLE_RADIUS, gridCellCount, type GeometryKey, type PresetKey } from '../engine/engine';

interface NewGameDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onStartGame: (geometry: GeometryKey, preset?: PresetKey, mode?: 'sandbox' | 'puzzle') => void;
}

const GEOMETRY_LABELS: Record<GeometryKey, string> = {
  hex: '��� Гексагональная',
  square: '�� Квадратная',
};

const GEOMETRY_DESC: Record<GeometryKey, string> = {
  hex: '6 соседей у клетки. Классическая гекс-геометрия.',
  square: '8 соседей (окружение Мура). Диагонали включены.',
};

const GEOMETRY_CELL_COUNTS: Record<GeometryKey, { sandbox: number; puzzle: number }> = {
  hex: { sandbox: gridCellCount('hex', 30), puzzle: gridCellCount('hex', PUZZLE_RADIUS.hex + 1) },
  square: { sandbox: gridCellCount('square', 29), puzzle: gridCellCount('square', PUZZLE_RADIUS.square * 2 + 1) },
};

const PRESET_KEYS: PresetKey[] = ['classic_balanced', 'fire_storm', 'water_world', 'desert_drought', 'chaos'];

export function NewGameDialog({ isOpen, onClose, onStartGame }: NewGameDialogProps) {
  const [step, setStep] = useState<'geometry' | 'preset' | 'mode'>('geometry');
  const [geometry, setGeometry] = useState<GeometryKey>('hex');
  const [preset, setPreset] = useState<PresetKey>('classic_balanced');
  const [mode, setMode] = useState<'sandbox' | 'puzzle'>('sandbox');

  // Reset to geometry selection when dialog opens
  useEffect(() => {
    if (isOpen) {
      setStep('geometry');
      setGeometry('hex');
      setPreset('classic_balanced');
      setMode('sandbox');
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleGeometrySelect = (g: GeometryKey) => {
    setGeometry(g);
    setStep('mode');
  };

  const handleModeSelect = (m: 'sandbox' | 'puzzle') => {
    setMode(m);
    if (m === 'sandbox') {
      setStep('preset');
    } else {
      // For puzzle, start directly with level 1
      onStartGame(geometry, undefined, 'puzzle');
    }
  };

  const handlePresetSelect = (p: PresetKey) => {
    setPreset(p);
    onStartGame(geometry, p, 'sandbox');
  };

  const handleBack = () => {
    if (step === 'mode') setStep('geometry');
    else if (step === 'preset') setStep('mode');
  };

  return (
    <div className="new-game-dialog-overlay" onClick={onClose}>
      <div className="new-game-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="dialog-header">
          <h2>{step === 'geometry' ? 'Выберите геометрию' : step === 'mode' ? 'Выберите режим' : 'Выберите пресет'}</h2>
          <button className="close-btn" onClick={onClose} aria-label="Закрыть">���</button>
        </div>

        {step === 'geometry' && (
          <div className="dialog-content">
            <p className="dialog-hint">Геометрия определяет форму клеток и количество соседей. Меняется только при старте новой игры.</p>
            <div className="geometry-options">
              {(['hex', 'square'] as GeometryKey[]).map((g) => (
                <button
                  key={g}
                  onClick={() => handleGeometrySelect(g)}
                  className={`geometry-option ${geometry === g ? 'selected' : ''}`}
                >
                  <div className="geometry-icon">{g === 'hex' ? '���' : '��'}</div>
                  <div className="geometry-info">
                    <div className="geometry-name">{GEOMETRY_LABELS[g]}</div>
                    <div className="geometry-desc">{GEOMETRY_DESC[g]}</div>
                    <div className="geometry-cells">
                      Песочница: <b>{GEOMETRY_CELL_COUNTS[g].sandbox}</b> клеток
                      {' | '}
                      Головоломка: <b>{GEOMETRY_CELL_COUNTS[g].puzzle}</b> клеток
                    </div>
                  </div>
                  {geometry === g && <div className="checkmark">���</div>}
                </button>
              ))}
            </div>
          </div>
        )}

        {step === 'mode' && (
          <div className="dialog-content">
            <p className="dialog-hint">Выбранная геометрия: <b>{GEOMETRY_LABELS[geometry]}</b></p>
            <div className="mode-options">
              <button
                onClick={() => handleModeSelect('sandbox')}
                className="mode-option"
              >
                <div className="mode-icon">����</div>
                <div className="mode-info">
                  <div className="mode-name">Песочница</div>
                  <div className="mode-desc">Свободная симуляция. Рисуйте стихии, меняйте параметры, наблюдайте за эволюцией.</div>
                </div>
              </button>
              <button
                onClick={() => handleModeSelect('puzzle')}
                className="mode-option"
              >
                <div className="mode-icon">����</div>
                <div className="mode-info">
                  <div className="mode-name">Головоломка</div>
                  <div className="mode-desc">«Полив пустоты». Оживите пустыню ограниченным запасом капель воды. 5 уровней сложности.</div>
                </div>
              </button>
            </div>
            <button className="back-btn" onClick={handleBack}>← Назад</button>
          </div>
        )}

        {step === 'preset' && mode === 'sandbox' && (
          <div className="dialog-content">
            <p className="dialog-hint">Геометрия: <b>{GEOMETRY_LABELS[geometry]}</b> | Режим: <b>Песочница</b></p>
            <div className="preset-options">
              {PRESET_KEYS.map((p) => {
                const presetData = GEOMETRY_PRESETS[geometry][p];
                return (
                  <button
                    key={p}
                    onClick={() => handlePresetSelect(p)}
                    className={`preset-option ${preset === p ? 'selected' : ''}`}
                  >
                    <div className="preset-name">{presetData.label}</div>
                    <div className="preset-desc">{presetData.description}</div>
                    {preset === p && <div className="checkmark">���</div>}
                  </button>
                );
              })}
            </div>
            <button className="back-btn" onClick={handleBack}>← Назад</button>
          </div>
        )}
      </div>
    </div>
  );
}