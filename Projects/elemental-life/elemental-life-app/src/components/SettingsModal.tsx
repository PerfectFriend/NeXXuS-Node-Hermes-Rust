/**
 * SettingsModal — модальное окно настроек.
 *
 * Вкладки (зависят от режима):
 * - Песочница: Пресеты, Настройка, График, Правила
 * - Головоломка: График, Правила
 *
 * Вкладка Пресеты: выбор пресета из GEOMETRY_PRESETS[geometry]
 * Вкладка Настройка: слайдеры параметров симуляции
 * Вкладка График: график воды и статистика поля
 * Вкладка Правила: описание правил игры
 *
 * Футер настроек: выбор геометрии поля и seed
 */

import { useState } from 'react';
import { GEOMETRY_PRESETS, COLORS, STATE_LABELS, WIN_MAX_AGE, WIN_STABLE_TICKS, type Params } from '../engine/engine';
import { ParamSlider, CheckboxRow } from './Controls';
import { MiniChart } from './MiniChart';
import type { GeometryKey, PresetKey, StateKey } from '../engine/engine';

const TABS_CONFIG: Record<string, string[]> = {
  sandbox: ['presets', 'tuning', 'chart', 'rules'],
  puzzle: ['chart', 'rules'],
};

type TabId = 'presets' | 'tuning' | 'chart' | 'rules';

const GEOMETRIES: GeometryKey[] = ['hex', 'square'];

const GEOMETRY_LABELS: Record<GeometryKey, string> = {
  hex: '⬢ Гекс (6 соседей)',
  square: '▢ Квадрат (8 соседей)',
};

const GEOMETRY_CELL_COUNTS: Record<GeometryKey, { sandbox: number; puzzle: number }> = {
  hex: { sandbox: 2611, puzzle: 469 },
  square: { sandbox: 841, puzzle: 441 },
};

interface SettingsModalProps {
  mode: string;
  geometry: GeometryKey;
  preset: string;
  params: Params;
  seed: number;
  counts: Record<string, number>;
  totalCells: number;
  waterHistory: number[];
  onClose: () => void;
  onApplyPreset: (key: string) => void;
  onSetParam: (key: string, value: number | boolean) => void;
  onSetGeometry: (g: GeometryKey) => void;
  onSetSeed: (seed: number) => void;
  onChangePin?: () => void;
}

export function SettingsModal({
  mode, geometry, preset, params,   seed, counts, totalCells, waterHistory,
  onClose, onApplyPreset, onSetParam, onSetGeometry, onSetSeed, onChangePin,
}: SettingsModalProps) {
  const [activeTab, setActiveTab] = useState<TabId>(
    mode === 'sandbox' ? 'presets' : 'chart'
  );
  const tabs = TABS_CONFIG[mode] as readonly string[];

  return (
    <div className="settings-modal" onClick={onClose}>
      <div className="settings-content" onClick={(e) => e.stopPropagation()}>
        {/* Заголовок */}
        <div className="settings-header">
          <h2 className="settings-title">⚙️ Настройки</h2>
          <button className="close-btn" onClick={onClose} aria-label="Закрыть">✕</button>
        </div>

        {/* Тело */}
        <div className="settings-body">
          {/* Вкладки */}
          <div className="settings-tabs">
            {tabs.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab as TabId)}
                className={`settings-tab ${activeTab === tab ? 'active' : ''}`}
              >
                {tab === 'presets' && '🎨 Пресеты'}
                {tab === 'tuning' && '🔧 Настройка'}
                {tab === 'chart' && '📊 График'}
                {tab === 'rules' && '📖 Правила'}
              </button>
            ))}
          </div>

          {/* Панель выбранной вкладки */}
          <div className="settings-panel">
            {activeTab === 'presets' && mode === 'sandbox' && (
              <div className="preset-list">
                {Object.entries(GEOMETRY_PRESETS[geometry]).map(([k, p]) => (
                  <button
                    key={k}
                    onClick={() => onApplyPreset(k as PresetKey)}
                    className={`preset-btn ${preset === k ? 'active' : ''}`}
                  >
                    <div className="preset-label">{p.label}</div>
                    <div className="preset-desc">{p.description}</div>
                  </button>
                ))}
              </div>
            )}

            {activeTab === 'tuning' && mode === 'sandbox' && (
              <div className="tuning-panel">
                <ParamSlider label="Перенаселение без воды → самовозгорание через N тиков" value={params.overpopulationIgniteTicks} min={1} max={5} step={1} onChange={(v) => onSetParam('overpopulationIgniteTicks', v)} />
                <ParamSlider label="Молния (шанс случайного возгорания)" value={params.lightningChance} min={0} max={0.02} step={0.0005} onChange={(v) => onSetParam('lightningChance', v)} />
                <ParamSlider label="Шанс распространения огня в пустоту" value={params.fireSpreadChance} min={0} max={1} step={0.05} onChange={(v) => onSetParam('fireSpreadChance', v)} />
                <ParamSlider label="Минимум соседей для выживания жизни (survMin)" value={params.survMin} min={0} max={3} step={1} onChange={(v) => onSetParam('survMin', v)} />
                <ParamSlider label="Перенаселение жизни (порог соседей)" value={params.lifeOverpopulation} min={3} max={8} step={1} onChange={(v) => onSetParam('lifeOverpopulation', v)} />
                <ParamSlider label="Рождение земли: сумма соседей вода+жизнь (birthCount)" value={params.birthCount} min={1} max={8} step={1} onChange={(v) => onSetParam('birthCount', v)} />
                <ParamSlider label="Шанс высыхания земли" value={params.earthDryoutChance} min={0} max={0.1} step={0.005} onChange={(v) => onSetParam('earthDryoutChance', v)} />
                <ParamSlider label="Возраст земли для высыхания (тиков)" value={params.earthDryoutMinAge} min={1} max={20} step={1} onChange={(v) => onSetParam('earthDryoutMinAge', v)} />
                <CheckboxRow label="Перелив воды в пустоты (острова)" checked={params.waterOverflowEnabled} onChange={(v) => onSetParam('waterOverflowEnabled', v)} />
              </div>
            )}

            {activeTab === 'chart' && (
              <div className="chart-panel">
                <h3 className="panel-title">График воды (последние тики)</h3>
                <MiniChart history={waterHistory} color="#2196f3" />
                <h3 className="panel-title">Текущее состояние поля</h3>
                <div className="stats-vertical">
                  {(Object.keys(counts) as StateKey[]).map((s) => (
                    <div key={s} className="stat-chip">
                      <span className="stat-dot" style={{ background: COLORS[s] }} />
                      <span>{STATE_LABELS[s]}</span>
                      <b>{counts[s]}</b>
                      <span className="stat-pct">{((counts[s] / totalCells) * 100).toFixed(0)}%</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeTab === 'rules' && (
              <div className="rules-panel">
                {mode === 'puzzle' && (
                  <>
                    <h3 className="panel-title">Режим головоломки</h3>
                    <p className="rule-text">
                      Заливай пустыню водой (капля = 1 клетка). Лимит капель ограничен.
                      Мир тикает сам — подливай воду по ходу дела.
                    </p>
                    <p className="rule-text">
                      <b>Победа:</b> пустыня не задерживается дольше {WIN_MAX_AGE} тиков подряд,
                      и это держится {WIN_STABLE_TICKS} тиков стабильно.
                    </p>
                    <p className="rule-text">
                      <b>Поражение:</b> капли закончились, и долго (80+ тиков) нет победы.
                    </p>
                    <h3 className="panel-title">Геометрия: {GEOMETRY_LABELS[geometry]}</h3>
                    <p className="rule-text">
                      Клеток в песочнице: {GEOMETRY_CELL_COUNTS[geometry].sandbox}.
                      Клеток в головоломке: {GEOMETRY_CELL_COUNTS[geometry].puzzle}.
                    </p>
                  </>
                )}
                <h3 className="panel-title">Правила стихий (кратко)</h3>
                <ul className="rule-list">
                  <li><b>Жизнь</b> рядом с огнём: с водой — выживает (вода→пар), без воды → огонь.</li>
                  <li><b>Жизнь</b> перенаселена (≥ {params.lifeOverpopulation} соседей-жизнь) без воды: нагревается, через {params.overpopulationIgniteTicks} тиков → огонь.</li>
                  <li><b>Жизнь</b> изолирована (соседей-жизнь меньше {params.survMin}) → земля.</li>
                  <li><b>Молния</b> ({params.lightningChance}): случайный огонь в жизни/земле.</li>
                  <li><b>Огонь</b> рядом с водой → пустота. Без тушения 2 тика → пустота.</li>
                  <li><b>Вода</b> тушит огонь/спасает жизнь → пар. Пар через {params.steamRainTicks} тик → дождь (вода).</li>
                  <li><b>Земля</b>: соседей вода+жизнь ≥ {params.birthCount} (из них ≥1 жизни) → жизнь.</li>
                  <li><b>Земля</b> без воды давно: шанс {params.earthDryoutChance} → пустота.</li>
                  <li><b>Пустота</b> + вода + жизнь рядом → земля мгновенно.</li>
                  <li><b>Пустота</b> с водой 3 тика подряд → земля.</li>
                  <li><b>Перелив:</b> вода, окружённая водой, течёт в соседнюю пустоту (источник→берег, цель→вода).</li>
                  <li><b>Закон воды:</b> вода + пар = const (кроме капель игрока в головоломке).</li>
                </ul>
              </div>
            )}
          </div>
        </div>

        {/* Футер: геометрия и seed */}
        <div className="settings-footer">
          <div className="panel-section">
            <h3 className="panel-title">Геометрия поля</h3>
            <div className="geometry-selector">
              {GEOMETRIES.map((g) => (
                <button
                  key={g}
                  onClick={() => onSetGeometry(g)}
                  className={`geometry-btn ${geometry === g ? 'active' : ''}`}
                >
                  <div className="geometry-icon">{g === 'hex' ? '⬢' : '▢'}</div>
                  <div className="geometry-info">
                    <div className="geometry-name">{GEOMETRY_LABELS[g]}</div>
                    <div className="geometry-cells">
                      Песочница: {GEOMETRY_CELL_COUNTS[g].sandbox} клеток
                      {' | '}
                      Головоломка: {GEOMETRY_CELL_COUNTS[g].puzzle} клеток
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div className="panel-section">
            <h3 className="panel-title">Сид и пресет</h3>
            <div className="seed-input">
              <label>
                Сид: <input
                  type="number"
                  value={seed}
                  onChange={(e) => onSetSeed(Number(e.target.value) || 0)}
                  min={0} max={2147483647}
                />
              </label>
            </div>
          </div>

          {onChangePin && (
            <div className="panel-section">
              <button onClick={onChangePin} style={{
                width: '100%', padding: '10px 16px', background: '#21262d',
                border: '1px solid #30363d', borderRadius: 8, color: '#e6edf3',
                fontSize: 13, cursor: 'pointer', textAlign: 'center',
              }}>
                🔐 Change wallet PIN sequence
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
