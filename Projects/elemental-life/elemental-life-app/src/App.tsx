import { useState, useEffect, useRef, useCallback } from 'react';
import './index.css';
import { initI18n } from './i18n';

import { GEOMETRY_LEVELS, type GeometryKey, type PresetKey } from './engine/engine';

import { useSimulation } from './hooks/useSimulation';
import { useIdentity } from './hooks/useIdentity';
import { useHiddenEntrance } from './hooks/useHiddenEntrance';

import { GridCanvas, type GridCanvasHandle } from './components/GridCanvas';
import { GameHeader } from './components/GameHeader';
import { GameToolbar } from './components/GameToolbar';
import { BrushSelector } from './components/BrushSelector';
import { StatsDisplay } from './components/StatsDisplay';
import { PuzzleOverlay } from './components/PuzzleOverlay';
import { SettingsModal } from './components/SettingsModal';
import { RegistrationFlow, type RegistrationData } from './components/RegistrationFlow';
import { PinEntryScreen } from './components/PinEntryScreen';
import { LoadingSplash } from './components/LoadingSplash';
import { WalletScreen } from './components/WalletScreen';
import { SequenceEditor } from './components/SequenceEditor';
import { ToastContainer } from './components/Toast';
import { InstagramImportModal } from './components/InstagramImportModal';
import { NewGameDialog } from './components/NewGameDialog';
import { rewardLevelCompletion } from './wallet/elemental';

// Initialize i18n on app load
initI18n();

type AppScreen = 'splash' | 'game';

export default function App() {
  const [screen, setScreen] = useState<AppScreen>('splash');

  const [identitySeed, setIdentitySeed] = useState<number | null>(null);
  const [showRegistration, setShowRegistration] = useState(false);
  const [showPinEntry, setShowPinEntry] = useState(false);
  const [showLoadingSplash, setShowLoadingSplash] = useState(true);

  const { profile, createIdentity, markLevelCompleted, saveSession, clearIdentity } = useIdentity();

    // New Game Dialog state
    const [showNewGameDialog, setShowNewGameDialog] = useState(false);

    // Secret sequence unlocks registration or pin
    const handleSecretUnlock = useCallback(() => {
    if (profile) {
      setShowPinEntry(true);
    } else {
      setShowRegistration(true);
    }
  }, [profile]);

  const secret = useHiddenEntrance({ onUnlock: handleSecretUnlock });

  const handleRegistrationComplete = useCallback(async (regData: RegistrationData) => {
    // regData now has userWords, backupPhrase, regDate
    // We need to create identity from userWords
    const p = await createIdentity(regData.userWords);
    setIdentitySeed(p.gameSeed);
    setShowRegistration(false);
  }, [createIdentity]);

  const handlePinOk = useCallback(async () => {
    setIdentitySeed(profile?.gameSeed ?? null);
    setShowPinEntry(false);
  }, [profile]);

  const handleNewRegistration = useCallback(() => {
    clearIdentity();
    setShowPinEntry(false);
    setShowRegistration(true);
  }, [clearIdentity]);

  const sim = useSimulation(identitySeed, secret.recordTap);

  const {
      mode, geometry, setGeometry, seed, setSeed,
      radius, cellSize, preset, params,
      running, speed, tick, field,
      waterHistory, waterDrift, waterStats, counts, totalCells,
      levelIndex, dropletsLeft, winStreak, puzzleWon, puzzleFailed,
      handleCellClick, applyPreset, switchMode, reset,
      goToNextLevel, retryLevel, setParam,
      viewport, setViewport, setRunning, setSpeed, setBrush, doStep, brush,
    } = sim;

    const currentLevel = GEOMETRY_LEVELS[geometry]?.[levelIndex];
    const gridRef = useRef<GridCanvasHandle>(null);

    // New Game Dialog handler
      const handleStartNewGame = useCallback((_geometry: GeometryKey, preset?: PresetKey, mode?: 'sandbox' | 'puzzle') => {
        setShowNewGameDialog(false);
        if (mode === 'puzzle') {
          switchMode('puzzle');
        } else {
          if (preset) {
            applyPreset(preset);
          }
          reset(seed);
        }
      }, [switchMode, applyPreset, reset, seed]);

  // Fullscreen
  const [showSettings, setShowSettings] = useState(false);
  const [uiFullscreen, setUiFullscreen] = useState(false);
  const [autoFullscreenActive, setAutoFullscreenActive] = useState(false);
  const inactivityRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const showSettingsRef = useRef(showSettings);
  showSettingsRef.current = showSettings;

  const resetInactivityTimer = useCallback(() => {
    if (inactivityRef.current) clearTimeout(inactivityRef.current);
    if (showSettingsRef.current) return;
    if (!autoFullscreenActive) return;
    inactivityRef.current = setTimeout(() => {
      const el = document.documentElement;
      if (el.requestFullscreen) el.requestFullscreen().catch(() => {});
      setUiFullscreen(true);
    }, 5000);
  }, [autoFullscreenActive]);

  useEffect(() => {
    if (uiFullscreen && !autoFullscreenActive) {
      setAutoFullscreenActive(true);
    }
  }, [uiFullscreen, autoFullscreenActive]);

  useEffect(() => {
    if (screen === 'game' && !autoFullscreenActive) {
      const timer = setTimeout(() => {
        const el = document.documentElement;
        if (el.requestFullscreen) el.requestFullscreen().catch(() => {});
        setUiFullscreen(true);
        setAutoFullscreenActive(true);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [screen, autoFullscreenActive]);

  const exitFullscreen = useCallback(() => {
    setUiFullscreen(false);
    resetInactivityTimer();
  }, [resetInactivityTimer]);

  const handleToggleFullscreen = useCallback(() => {
    if (uiFullscreen) {
      if (document.exitFullscreen) document.exitFullscreen().catch(() => {});
      exitFullscreen();
    } else {
      const el = document.documentElement;
      if (el.requestFullscreen) el.requestFullscreen().catch(() => {});
      setUiFullscreen(true);
    }
  }, [uiFullscreen, exitFullscreen]);

  const handleBoardInteraction = useCallback(() => {
    resetInactivityTimer();
  }, [resetInactivityTimer]);

  // Tabs
  const TABS: Record<string, readonly string[]> = {
    sandbox: ['presets', 'tuning', 'chart', 'rules'],
    puzzle: ['chart', 'rules'],
  };
  type TabId = 'presets' | 'tuning' | 'chart' | 'rules';
  const [activeTabState, setActiveTabState] = useState<TabId>('presets');

  useEffect(() => {
    const tabs = TABS[mode];
    if (!(tabs as readonly string[]).includes(activeTabState)) {
      setActiveTabState(tabs[0] as TabId);
    }
  }, [mode, activeTabState]);

  // Zoom
  const zoomIn = useCallback(() => {
    const f = 1.3; const cx = viewport.width / 2; const cy = viewport.height / 2;
    const nz = Math.min(4, viewport.zoom * f); const r = nz / viewport.zoom;
    setViewport({ zoom: nz, x: cx - (cx - viewport.x) * r, y: cy - (cy - viewport.y) * r });
  }, [viewport, setViewport]);

  const zoomOut = useCallback(() => {
    const f = 1 / 1.3; const cx = viewport.width / 2; const cy = viewport.height / 2;
    const nz = Math.max(0.15, viewport.zoom * f); const r = nz / viewport.zoom;
    setViewport({ zoom: nz, x: cx - (cx - viewport.x) * r, y: cy - (cy - viewport.y) * r });
  }, [viewport, setViewport]);

  const forceCenterView = useCallback(() => {
      gridRef.current?.forceCenter();
    }, []);

  const resetView = useCallback(() => { gridRef.current?.resetView(); }, []);
  const centerView = useCallback(() => { gridRef.current?.centerView(); }, []);

  // Sequence Editor
  const [showSequenceEditor, setShowSequenceEditor] = useState(false);

  const openInstagramImport = useCallback(() => {
      setRunning(false);
      setShowInstagramImport(true);
      if (inactivityRef.current) clearTimeout(inactivityRef.current);
    }, [setRunning]);

    // Settings
    const openSettings = useCallback(() => {
      setRunning(false);
      setShowSettings(true);
      if (inactivityRef.current) clearTimeout(inactivityRef.current);
    }, [setRunning]);
    const closeSettings = useCallback(() => {
        setShowSettings(false);
        resetInactivityTimer();
      }, [resetInactivityTimer]);

  const handleExitGame = useCallback(() => {
      // Export viewport from grid
      const vp = gridRef.current?.exportViewport();
      if (vp) {
        setViewport({ ...vp, initialized: true } as Partial<{ x: number; y: number; zoom: number; width: number; height: number; initialized?: boolean }>);
      }
      // Stop simulation
      setRunning(false);
      // Exit fullscreen if active
      if (uiFullscreen) {
        exitFullscreen();
      }
      // Go back to splash screen
      setShowLoadingSplash(true);
      setScreen('splash');
    }, [setViewport, setRunning, uiFullscreen, exitFullscreen]);

  // New game - show dialog instead of directly resetting
    const handleNewGame = useCallback(() => {
      setShowNewGameDialog(true);
    }, []);

  // Geometry switch
  const handleGeometrySelect = useCallback((g: GeometryKey) => { if (g !== geometry) setGeometry(g); }, [geometry, setGeometry]);

  // Wallet
    const [showWallet, setShowWallet] = useState(false);
    const [unlockFlash, setUnlockFlash] = useState(false);
    const [showInstagramImport, setShowInstagramImport] = useState(false);

    const handleInstagramLevelGenerated = useCallback((_level: any, seed: string, sourceInfo: any) => {
          // Apply the generated level to the simulation
          // For now, just set the seed and reset - the buildLevelField logic is in the skill
          console.log('Instagram level generated:', { seed, sourceInfo });
          // Convert seed string to number for setSeed
          const seedNum = parseInt(seed.slice(0, 8), 16) || Date.now();
          setSeed(seedNum);
        }, [setSeed]);

  useEffect(() => {
    if (secret.showHint) {
      setUnlockFlash(true);
      setTimeout(() => setUnlockFlash(false), 600);
    }
  }, [secret.showHint]);

  // Save progress
  useEffect(() => {
    if (puzzleWon && profile) {
      markLevelCompleted(geometry, levelIndex);
      saveSession(geometry, levelIndex, 'puzzle');
      rewardLevelCompletion(levelIndex, geometry);
    }
  }, [puzzleWon, geometry, levelIndex, profile, markLevelCompleted, saveSession]);

  // Splash
  if (showLoadingSplash) {
    return <LoadingSplash onComplete={() => setShowLoadingSplash(false)} />;
  }

  if (screen === 'splash') {
    setScreen('game');
    return null;
  }

  // Registration overlay (triggered by secret sequence)
  if (showRegistration) {
    return <RegistrationFlow onComplete={handleRegistrationComplete} onBack={() => setShowRegistration(false)} />;
  }

  // Pin entry overlay (triggered by secret sequence)
  if (showPinEntry) {
    return (
      <PinEntryScreen
        onPinOk={handlePinOk}
        onNewRegistration={handleNewRegistration}
      />
    );
  }

  // Fullscreen mode
  if (uiFullscreen) {
    return (
      <div className="board-wrap fullscreen">
        <GridCanvas
          ref={gridRef}
          field={field} geometry={geometry} radius={radius}
          cellSize={cellSize} onCellClick={handleCellClick}
          viewport={viewport} onViewportChange={setViewport}
        />

        <button className="fullscreen-exit-btn" onClick={exitFullscreen} title="Выйти из полноэкранного режима" aria-label="Exit fullscreen">
          ⛶
        </button>

        <PuzzleOverlay
          puzzleWon={puzzleWon} puzzleFailed={puzzleFailed}
          winStreak={winStreak} winStableTicks={15}
          levelIndex={levelIndex} totalLevels={GEOMETRY_LEVELS[geometry]?.length ?? 5}
          onNextLevel={goToNextLevel} onRetryLevel={retryLevel}
        />
      </div>
    );
  }

  // Normal mode — full UI
  return (
    <div className="app">
      <GameHeader
              mode={mode}
              onSwitchMode={switchMode}
              onOpenSettings={openSettings}
              onToggleFullscreen={handleToggleFullscreen}
              onExitGame={handleExitGame}
              onOpenInstagramImport={openInstagramImport}
            />

          <div className="layout">
            <main className="main">
              <GameToolbar
                    mode={mode} running={running} tick={tick}
                    speed={speed} viewportZoom={viewport.zoom}
                    levelLabel={currentLevel?.label}
                    totalLevels={GEOMETRY_LEVELS[geometry]?.length}
                    dropletsLeft={dropletsLeft}
                    onToggleRunning={() => setRunning(!running)}
                    onStep={doStep} onNewGame={handleNewGame}
                    onRetryLevel={retryLevel} onSetSpeed={setSpeed}
                    onZoomIn={zoomIn} onZoomOut={zoomOut}
                    onResetView={resetView} onCenterView={centerView}
                    onForceCenter={forceCenterView}
                  />

        <BrushSelector mode={mode} brush={brush} onSetBrush={setBrush} />

        <div
          className="board-wrap"
          onPointerDown={handleBoardInteraction}
          onPointerMove={handleBoardInteraction}
          onWheel={handleBoardInteraction}
        >
          <GridCanvas
            ref={gridRef}
            field={field} geometry={geometry} radius={radius}
            cellSize={cellSize} onCellClick={handleCellClick}
            viewport={viewport} onViewportChange={setViewport}
          />

          <PuzzleOverlay
            puzzleWon={puzzleWon} puzzleFailed={puzzleFailed}
            winStreak={winStreak} winStableTicks={15}
            levelIndex={levelIndex} totalLevels={GEOMETRY_LEVELS[geometry]?.length ?? 5}
            onNextLevel={goToNextLevel} onRetryLevel={retryLevel}
          />

          {secret.unlocked && (
            <button onClick={() => setShowWallet(true)} style={{
              position: 'absolute', top: 12, right: 12, zIndex: 100,
              background: '#1f6feb', color: '#fff', borderRadius: 8,
              padding: '8px 14px', fontSize: 13, fontWeight: 600, cursor: 'pointer',
              border: 'none', animation: 'walletPulse 2s ease-in-out infinite',
              boxShadow: '0 0 20px rgba(31,111,235,0.4)',
            }}>
              🔓 Wallet
            </button>
          )}

          {unlockFlash && (
            <div style={{
              position: 'absolute', inset: 0, zIndex: 99, pointerEvents: 'none',
              background: 'radial-gradient(circle at center, rgba(31,111,235,0.3) 0%, transparent 70%)',
              animation: 'flashOut 0.6s ease-out forwards',
            }} />
          )}
        </div>

        <StatsDisplay counts={counts} waterStats={waterStats} waterDrift={waterDrift} />
      </main>
    </div>

    {showWallet && profile && (
          <WalletScreen
            onClose={() => setShowWallet(false)}
          />
        )}

    <ToastContainer />

    {showSequenceEditor && (
      <SequenceEditor onClose={() => setShowSequenceEditor(false)} />
    )}

    {showSettings && (
          <SettingsModal
            mode={mode} geometry={geometry} preset={preset}
            params={params} seed={seed}
            counts={counts} totalCells={totalCells} waterHistory={waterHistory}
            onClose={closeSettings}
            onApplyPreset={(k) => applyPreset(k as any)}
            onSetParam={setParam as (key: string, value: number | boolean) => void} onSetGeometry={handleGeometrySelect}
            onSetSeed={setSeed}
            onChangePin={() => { setShowSettings(false); setShowSequenceEditor(true); }}
          />
        )}

        <InstagramImportModal
                  isOpen={showInstagramImport}
                  onClose={() => setShowInstagramImport(false)}
                  onLevelGenerated={handleInstagramLevelGenerated}
                />
                <NewGameDialog
                  isOpen={showNewGameDialog}
                  onClose={() => setShowNewGameDialog(false)}
                  onStartGame={handleStartNewGame}
                />
              </div>
              );
    }