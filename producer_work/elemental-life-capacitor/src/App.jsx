import React, { useState, useRef, useEffect, useCallback } from 'react';
import { STATE, COLORS, STATE_LABELS, GEOMETRIES, GEOMETRY_PRESETS, GEOMETRY_LEVELS, PUZZLE_RADIUS, WIN_MAX_AGE, WIN_STABLE_TICKS, buildInitialField, buildLevelField, checkPuzzleWinTick, countWater, stepField, mulberry32 } from './engine.js';
import './App.css';

const CONFIG = {
  // sandbox field size (radius) for hex: side = radius+1? Actually makeGrid radius.
  // For hex, radius = side-1. We'll use radius that gives reasonable cell count.
  sandboxRadiusHex: 15, // side = radius+1 = 16? Actually hexGridCellCount(side) with side = radius+1? We'll compute later.
  sandboxRadiusSquare: 15, // side = 2*radius+1
  cellSize: 20, // base size in pixels at zoom=1
  backgroundColor: '#0d1117',
};

function App() {
  const canvasRef = useRef(null);
  const animationFrameRef = useRef(null);
  const [field, setField] = useState(null);
  const [geometryKey, setGeometryKey] = useState('hex');
  const [presetKey, setPresetKey] = useState('classic_balanced');
  const [mode, setMode] = useState('sandbox'); // sandbox or puzzle
  const [levelId, setLevelId] = useState(1);
  const [droplets, setDroplets] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);
  const [lastTimestamp, setLastTimestamp] = useState(0);
  const [stats, setStats] = useState({ water: 0, steam: 0, life: 0, fire: 0, earth: 0, ash: 0, empty: 0 });
  const [isRunning, setIsRunning] = useState(true);
  const [showWin, setShowWin] = useState(false);
  const [stableTicks, setStableTicks] = useState(0);

  // Initialize field
  useEffect(() => {
    initField();
    // eslint-disable-next-line
  }, [geometryKey, presetKey, mode, levelId]);

  function initField() {
    let radius;
    let seed = Date.now();
    if (mode === 'sandbox') {
      radius = geometryKey === 'hex' ? CONFIG.sandboxRadiusHex : CONFIG.sandboxRadiusSquare;
      const field = buildInitialField(geometryKey, radius, mulberry32(seed));
      setField(field);
      setDroplets(0);
      setStableTicks(0);
      setShowWin(false);
    } else {
      // puzzle mode
      radius = PUZZLE_RADIUS[geometryKey];
      const level = GEOMETRY_LEVELS[geometryKey].find(l => l.id === levelId);
      const field = buildLevelField(geometryKey, radius, mulberry32(seed), level);
      setField(field);
      setDroplets(level.droplets);
      setStableTicks(0);
      setShowWin(false);
    }
  }

  // Start/stop simulation
  useEffect(() => {
    if (!isRunning) return;
    function step(timestamp) {
      if (lastTimestamp === 0) {
        setLastTimestamp(timestamp);
      }
      const delta = timestamp - lastTimestamp;
      // target ~60 FPS, but we step simulation at fixed rate? We'll step each frame for simplicity.
      setLastTimestamp(timestamp);
      if (field) {
        const params = GEOMETRY_PRESETS[geometryKey][presetKey].params;
        const rng = mulberry32(Date.now() + timestamp); // simple rng per frame
        const next = stepField(geometryKey, field, (geometryKey === 'hex' ? CONFIG.sandboxRadiusHex : CONFIG.sandboxRadiusSquare), params, rng);
        setField(next);
        // update stats
        const counts = { water: 0, steam: 0, life: 0, fire: 0, earth: 0, ash: 0, empty: 0 };
        for (const cell of next.values()) {
          counts[cell.state] += 1;
        }
        setStats(counts);
        // check puzzle win condition
        if (mode === 'puzzle') {
          const winTick = checkPuzzleWinTick(next);
          if (winTick) {
            setStableTicks(prev => prev + 1);
            if (stableTicks >= WIN_STABLE_TICKS) {
              setShowWin(true);
              setIsRunning(false);
            }
          } else {
            setStableTicks(0);
          }
        }
      }
      animationFrameRef.current = requestAnimationFrame(step);
    }
    animationFrameRef.current = requestAnimationFrame(step);
    return () => {
      cancelAnimationFrame(animationFrameRef.current);
    };
  }, [isRunning, field, geometryKey, presetKey, mode, levelId, stableTicks]);

  // Canvas rendering
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = canvas.clientWidth * dpr;
      canvas.height = canvas.clientHeight * dpr;
      ctx.scale(dpr, dpr);
    };
    resize();
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);

  // Render loop (separate from simulation step)
  useEffect(() => {
    if (!field) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const draw = () => {
      const dpr = window.devicePixelRatio || 1;
      const width = canvas.clientWidth;
      const height = canvas.clientHeight;
      ctx.clearRect(0, 0, width * dpr, height * dpr);
      ctx.fillStyle = CONFIG.backgroundColor;
      ctx.fillRect(0, 0, width * dpr, height * dpr);

      // Determine visible world coordinates based on pan/zoom
      const cellSize = CONFIG.cellSize * zoom;
      const radius = geometryKey === 'hex' ? CONFIG.sandboxRadiusHex : CONFIG.sandboxRadiusSquare;
      // We'll render all cells; for large fields this may be heavy but okay for demo.
      // For hex grid, we need to convert axial (q,r) to pixel.
      const hexSize = cellSize; // size of hex (distance from center to corner)
      const sqrt3 = Math.sqrt(3);
      const hexWidth = hexSize * 2;
      const hexHeight = hexSize * sqrt3;

      for (const [keyStr, cell] of field.entries()) {
        const [q, r] = keyStr.split(',').map(Number);
        let screenX, screenY;
        if (geometryKey === 'hex') {
          // axial to pixel (flat-top hex)
          screenX = (hexSize * sqrt3 * (q + r/2)) * zoom + panX * width + width/2;
          screenY = (hexSize * 3/2 * r) * zoom + panY * height + height/2;
        } else {
          // square grid
          screenX = (q * hexSize) * zoom + panX * width + width/2;
          screenY = (r * hexSize) * zoom + panY * height + height/2;
        }
        // Only draw if within viewport (with some margin)
        if (screenX < -hexSize || screenX > width + hexSize || screenY < -hexSize || screenY > height + hexSize) continue;

        ctx.fillStyle = COLORS[cell.state] || '#fff';
        if (geometryKey === 'hex') {
          drawHex(ctx, screenX, screenY, hexSize);
        } else {
          ctx.fillRect(screenX - hexSize/2, screenY - hexSize/2, hexSize, hexSize);
        }
        // Optional: draw border
        ctx.strokeStyle = 'rgba(255,255,255,0.1)';
        ctx.lineWidth = 1;
        if (geometryKey === 'hex') {
          drawHex(ctx, screenX, screenY, hexSize, true);
        } else {
          ctx.strokeRect(screenX - hexSize/2, screenY - hexSize/2, hexSize, hexSize);
        }
      }
      // UI overlay
      drawUI(ctx, width, height);
      animationFrameRef.current = requestAnimationFrame(draw);
    };
    animationFrameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animationFrameRef.current);
  }, [field, geometryKey, zoom, panX, panY]);

  function drawHex(ctx, x, y, size, strokeOnly = false) {
    ctx.beginPath();
    for (let i = 0; i < 6; i++) {
      const angle = (i * Math.PI) / 3;
      const dx = x + size * Math.cos(angle);
      const dy = y + size * Math.sin(angle);
      if (i === 0) ctx.moveTo(dx, dy);
      else ctx.lineTo(dx, dy);
    }
    ctx.closePath();
    if (!strokeOnly) ctx.fill();
    if (strokeOnly) ctx.stroke();
  }

  function drawUI(ctx, width, height) {
    ctx.fillStyle = 'rgba(0,0,0,0.5)';
    ctx.font = '16px sans-serif';
    ctx.textBaseline = 'top';
    let y = 10;
    ctx.fillText(`Геометрия: ${geometryKey === 'hex' ? 'Гекс' : 'Квадрат'}`, 10, y); y += 20;
    ctx.fillText(`Пресет: ${presetKey}`, 10, y); y += 20;
    ctx.fillText(`Режим: ${mode === 'sandbox' ? 'Песочница' : 'Головоломка'}`, 10, y); y += 20;
    if (mode === 'puzzle') {
      ctx.fillText(`Уровень: ${levelId}`, 10, y); y += 20;
      ctx.fillText(`Капли: ${droplets}`, 10, y); y += 20;
    }
    ctx.fillText(`Вода: ${stats.water} Пар: ${stats.steam}`, 10, y); y += 20;
    ctx.fillText(`Жизнь: ${stats.life} Огонь: ${stats.fire}`, 10, y); y += 20;
    ctx.fillText(`Земля: ${stats.earth} Пепел: ${stats.ash} Пустота: ${stats.empty}`, 10, y); y += 20;
    if (mode === 'puzzle') {
      ctx.fillText(`Стабильные тики: ${stableTicks}/${WIN_STABLE_TICKS}`, 10, y); y += 20;
    }
    if (showWin) {
      ctx.fillStyle = 'rgba(0,255,0,0.7)';
      ctx.fillRect(0, 0, width * dpr, height * dpr);
      ctx.fillStyle = '#000';
      ctx.font = 'bold 32px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('ПОБЕДА!', width/2, height/2);
    }
  }

  // Touch handling for pan and zoom
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let pinchStart = { distance: 0, zoom: 1 };
    let panStart = { x: 0, y: 0, panX: 0, panY: 0 };
    const handleTouchStart = (e) => {
      if (e.touches.length === 2) {
        const touch1 = e.touches[0];
        const touch2 = e.touches[1];
        const dx = touch2.clientX - touch1.clientX;
        const dy = touch2.clientY - touch1.clientY;
        pinchStart.distance = Math.sqrt(dx*dx + dy*dy);
        pinchStart.zoom = zoom;
        e.preventDefault();
      } else if (e.touches.length === 1) {
        const touch = e.touches[0];
        panStart.x = touch.clientX;
        panStart.y = touch.clientY;
        panStart.panX = panX;
        panStart.panY = panY;
        e.preventDefault();
      }
    };
    const handleTouchMove = (e) => {
      if (e.touches.length === 2) {
        const touch1 = e.touches[0];
        const touch2 = e.touches[1];
        const dx = touch2.clientX - touch1.clientX;
        const dy = touch2.clientY - touch1.clientY;
        const distance = Math.sqrt(dx*dx + dy*dy);
        const scale = distance / pinchStart.distance;
        setZoom(Math.min(5, Math.max(0.5, pinchStart.zoom * scale)));
        e.preventDefault();
      } else if (e.touches.length === 1) {
        const touch = e.touches[0];
        const dx = touch.clientX - panStart.x;
        const dy = touch.clientY - panStart.y;
        setPanX(panStart.panX + dx / (window.innerWidth * zoom));
        setPanY(panStart.panY + dy / (window.innerHeight * zoom));
        e.preventDefault();
      }
    };
    const handleTouchEnd = (e) => {
      // Optionally handle taps for placing water in puzzle mode
      if (e.touches.length === 0 && e.changedTouches.length === 1) {
        const touch = e.changedTouches[0];
        // Convert client coordinates to world coordinates to toggle cell
        // For simplicity, we'll just add water at center for now.
        // In a full implementation we'd compute which cell was tapped.
        if (mode === 'puzzle' && droplets > 0) {
          // Place water at center of field (q=0,r=0) for demo
          const keyStr = '0,0';
          const cell = field.get(keyStr);
          if (cell && (cell.state === STATE.EMPTY || cell.state === STATE.ASH)) {
            const newField = new Map(field);
            newField.set(keyStr, { state: STATE.WATER, age: 0 });
            setField(newField);
            setDroplets(droplets - 1);
          }
        }
      }
    };
    canvas.addEventListener('touchstart', handleTouchStart, { passive: false });
    canvas.addEventListener('touchmove', handleTouchMove, { passive: false });
    canvas.addEventListener('touchend', handleTouchEnd, { passive: false });
    return () => {
      canvas.removeEventListener('touchstart', handleTouchStart);
      canvas.removeEventListener('touchmove', handleTouchMove);
      canvas.removeEventListener('touchend', handleTouchEnd);
    };
  }, [zoom, panX, panY, field, droplets, mode]);

  // Simple UI controls (HTML overlay)
  return (
    <div style={{ position: 'relative', width: '100vw', height: '100vh', overflow: 'hidden' }}>
      <canvas ref={canvasRef} style={{ display: 'block', width: '100%', height: '100%' }} />
      <div style={{
        position: 'absolute',
        top: 10,
        left: 10,
        color: '#fff',
        background: 'rgba(0,0,0,0.5)',
        padding: '10px',
        borderRadius: '5px',
        pointerEvents: 'none',
        zIndex: 10
      }}>
        <div>
          <button onClick={() => setIsRunning(!isRunning)} style={{ margin: '5px' }}>
            {isRunning ? 'Пауза' : 'Старт'}
          </button>
          <button onClick={() => initField()} style={{ margin: '5px' }}>
            Сбросить
          </button>
          <select onChange={(e) => setGeometryKey(e.target.value)} value={geometryKey} style={{ margin: '5px' }}>
            <option value="hex">Гекс</option>
            <option value="square">Квадрат</option>
          </select>
          <select onChange={(e) => setPresetKey(e.target.value)} value={presetKey} style={{ margin: '5px' }}>
            {Object.keys(GEOMETRY_PRESETS[geometryKey]).map(key => (
              <option key={key} value={key}>
                {GEOMETRY_PRESETS[geometryKey][key].label}
              </option>
            ))}
          </select>
          <button onClick={() => setMode(mode === 'sandbox' ? 'puzzle' : 'sandbox')} style={{ margin: '5px' }}>
            Переключить режим
          </button>
          {mode === 'puzzle' && (
            <select onChange={(e) => setLevelId(parseInt(e.target.value))} value={levelId} style={{ margin: '5px' }}>
              {GEOMETRY_LEVELS[geometryKey].map(l => (
                <option key={l.id} value={l.id}>
                  {l.label}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;