import { useEffect, useRef, useCallback } from 'react';

interface Props {
  onComplete: () => void;
}

export function FantasySplash({ onComplete }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationIdRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(performance.now());
  const doneRef = useRef(false);

  // Canvas drawing functions
  const drawCyberpunkSky = useCallback((ctx: CanvasRenderingContext2D, w: number, h: number, time: number, alpha: number) => {
    // Van Gogh style swirling night sky
    const sky = ctx.createLinearGradient(0, 0, 0, h);
    sky.addColorStop(0, '#0a0015');
    sky.addColorStop(0.2, '#150030');
    sky.addColorStop(0.5, '#200040');
    sky.addColorStop(0.8, '#100020');
    sky.addColorStop(1, '#050010');
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, w, h);

    // Gaudi-inspired organic swirls in background
    ctx.save();
    ctx.globalAlpha = alpha * 0.15;
    for (let i = 0; i < 8; i++) {
      const cx = w * (0.2 + (i % 4) * 0.25);
      const cy = h * (0.15 + Math.floor(i / 4) * 0.4);
      const r = 80 + Math.sin(time * 0.3 + i) * 20;
      const swirl = ctx.createRadialGradient(cx, cy, 10, cx, cy, r);
      const hue = (time * 15 + i * 45) % 360;
      swirl.addColorStop(0, `hsla(${hue}, 80%, 40%, 0.3)`);
      swirl.addColorStop(0.5, `hsla(${hue + 60}, 70%, 30%, 0.15)`);
      swirl.addColorStop(1, 'transparent');
      ctx.fillStyle = swirl;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }, []);

  const drawStars = useCallback((ctx: CanvasRenderingContext2D, w: number, h: number, time: number, alpha: number) => {
    ctx.save();
    ctx.globalAlpha = alpha;
    for (let i = 0; i < 100; i++) {
      const x = (i * 127 + time * 50) % w;
      const y = (i * 73 + time * 30) % (h * 0.6);
      const size = 0.5 + (Math.sin(time + i * 1.7) * 0.5 + 0.5) * 1.5;
      const brightness = 0.5 + Math.sin(time * 2 + i) * 0.5;
      ctx.fillStyle = `rgba(255, 255, 255, ${brightness * alpha})`;
      ctx.beginPath();
      ctx.arc(x, y, size, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }, []);

  const drawOasis = useCallback((ctx: CanvasRenderingContext2D, cx: number, cy: number, radius: number, time: number, alpha: number) => {
    // Oasis center - glowing pool
    const poolGradient = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius * 1.2);
    poolGradient.addColorStop(0, `rgba(0, 255, 180, ${alpha * 0.8})`);
    poolGradient.addColorStop(0.3, `rgba(0, 200, 150, ${alpha * 0.5})`);
    poolGradient.addColorStop(0.6, `rgba(0, 150, 100, ${alpha * 0.3})`);
    poolGradient.addColorStop(1, 'transparent');
    ctx.fillStyle = poolGradient;
    ctx.beginPath();
    ctx.arc(cx, cy, radius * 1.5, 0, Math.PI * 2);
    ctx.fill();

    // Ripples
    for (let i = 0; i < 5; i++) {
      const r = radius * 0.5 + (time * 30 + i * 60) % (radius * 1.5);
      const rippleAlpha = alpha * 0.3 * (1 - r / (radius * 1.5));
      ctx.strokeStyle = `rgba(0, 255, 200, ${rippleAlpha})`;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(cx, cy, r, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Central palm tree (Gaudi organic style)
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.translate(cx, cy);
    
    // Trunk - organic curves
    ctx.strokeStyle = '#2d4a1e';
    ctx.lineWidth = 6;
    ctx.lineCap = 'round';
    for (let i = 0; i < 3; i++) {
      const angle = (i - 1) * 0.15;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.quadraticCurveTo(
        Math.sin(time * 0.3 + i) * 10, -30,
        Math.sin(angle) * 20 + Math.sin(time * 0.3 + i) * 15, -70
      );
      ctx.stroke();
    }
    
    // Fronds - Van Gogh style
    ctx.fillStyle = '#1a5a1a';
    for (let i = 0; i < 8; i++) {
      const angle = (i / 8) * Math.PI * 2 + time * 0.2;
      const len = 50 + Math.sin(time + i) * 10;
      ctx.save();
      ctx.rotate(angle);
      ctx.beginPath();
      ctx.moveTo(0, -20);
      ctx.quadraticCurveTo(
        Math.sin(time + i) * 15, -len * 0.5,
        Math.cos(angle) * len, -len
      );
      ctx.quadraticCurveTo(
        Math.sin(time + i) * 10, -len * 0.3,
        0, -20
      );
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }
    ctx.restore();
  }, []);

  const drawEarthElemental = useCallback((ctx: CanvasRenderingContext2D, x: number, y: number, time: number, alpha: number, cy: number) => {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.translate(x, y);
    
    const breath = Math.sin(time * 0.4) * 3;
    const rockColor = '#5c4a3a';
    const rockHighlight = '#7a6a50';
    
    // Body - Atlas holding the oasis
    // Legs (kneeling, strong stance)
    ctx.fillStyle = rockColor;
    ctx.beginPath();
    ctx.ellipse(-35, y - cy + 10, 20, 12, -0.15, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(35, y - cy + 10, 20, 12, 0.15, 0, Math.PI * 2);
    ctx.fill();

    // Torso - massive, holding weight
    ctx.fillStyle = rockColor;
    ctx.beginPath();
    ctx.moveTo(-40, y - cy - 30 + breath);
    ctx.quadraticCurveTo(-45, y - cy - 20 + breath, -40, y - cy - 5 + breath);
    ctx.lineTo(40, y - cy - 5 + breath);
    ctx.quadraticCurveTo(45, y - cy - 20 + breath, 40, y - cy - 30 + breath);
    ctx.closePath();
    ctx.fill();

    // Rock texture
    ctx.strokeStyle = rockHighlight;
    ctx.lineWidth = 1;
    for (let i = 0; i < 4; i++) {
      const ly = y - cy - 25 + breath + i * 8;
      ctx.beginPath();
      ctx.moveTo(-30, ly);
      ctx.quadraticCurveTo(0, ly + 4, 30, ly);
      ctx.stroke();
    }

    // Shoulders
    ctx.fillStyle = rockColor;
    ctx.beginPath();
    ctx.ellipse(-38, y - cy - 35 + breath, 18, 10, -0.25, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(38, y - cy - 35 + breath, 18, 10, 0.25, 0, Math.PI * 2);
    ctx.fill();

    // Head (bowed under weight)
    ctx.fillStyle = rockColor;
    ctx.beginPath();
    ctx.ellipse(0, y - cy - 55 + breath, 20, 22, 0, 0, Math.PI * 2);
    ctx.fill();

    // Arms reaching UP to hold the oasis
    ctx.strokeStyle = rockColor;
    ctx.lineWidth = 14;
    ctx.lineCap = 'round';
    
    // Left arm - pushing up
    ctx.beginPath();
    ctx.moveTo(-38, y - cy - 30 + breath);
    ctx.quadraticCurveTo(-60 - 5, y - cy - 60, -50 - 2.5, y - cy - 80);
    ctx.stroke();
    
    // Right arm - pushing up
    ctx.beginPath();
    ctx.moveTo(38, y - cy - 30 + breath);
    ctx.quadraticCurveTo(60 + 5, y - cy - 60, 50 + 2.5, y - cy - 80);
    ctx.stroke();

    // Hands - flat, pushing up
    ctx.fillStyle = rockColor;
    ctx.beginPath();
    ctx.ellipse(-50 - 2.5, y - cy - 85, 18, 12, -0.3, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(50 + 2.5, y - cy - 85, 18, 12, 0.3, 0, Math.PI * 2);
    ctx.fill();

    // Veins on arms (glowing faintly)
    ctx.strokeStyle = `rgba(100, 200, 100, ${1 * 0.5})`;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(-38, -30);
    ctx.quadraticCurveTo(-60, -60, -50, -80);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(38, -30);
    ctx.quadraticCurveTo(60, -60, 50, -80);
    ctx.stroke();

    ctx.restore();
  }, []);

  const drawFireElemental = useCallback((ctx: CanvasRenderingContext2D, x: number, y: number, time: number, alpha: number, cy: number) => {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.translate(x, y);
    
    // Body - tall flame shape attacking
    // Outer flame
    const outerGradient = ctx.createLinearGradient(0, y - cy - 120, 0, y - cy + 20);
    outerGradient.addColorStop(0, `rgba(200, 30, 0, ${alpha})`);
    outerGradient.addColorStop(0.5, `rgba(255, 80, 0, ${alpha})`);
    outerGradient.addColorStop(1, `rgba(255, 40, 0, ${alpha})`);
    ctx.fillStyle = outerGradient;
    
    ctx.beginPath();
    ctx.moveTo(0, y - cy - 120);
    ctx.quadraticCurveTo(45, y - cy - 80, 50, y - cy - 40);
    ctx.quadraticCurveTo(55, y - cy - 5, 50, y - cy + 5);
    ctx.lineTo(-50, y - cy + 5);
    ctx.quadraticCurveTo(-55, y - cy - 5, -50, y - cy - 40);
    ctx.quadraticCurveTo(-45, y - cy - 80, 0, y - cy - 120);
    ctx.closePath();
    ctx.fill();

    // Mid flame
    const midGradient = ctx.createLinearGradient(0, y - cy - 100, 0, y - cy);
    midGradient.addColorStop(0, `rgba(255, 150, 0, ${alpha})`);
    midGradient.addColorStop(0.5, `rgba(255, 120, 0, ${alpha})`);
    midGradient.addColorStop(1, `rgba(255, 60, 0, ${alpha})`);
    ctx.fillStyle = midGradient;
    
    ctx.beginPath();
    ctx.moveTo(0, y - cy - 100);
    ctx.quadraticCurveTo(35, y - cy - 70, 35, y - cy - 35);
    ctx.quadraticCurveTo(40, y - cy - 5, 30, y - cy + 3);
    ctx.lineTo(-30, y - cy + 3);
    ctx.quadraticCurveTo(-40, y - cy - 5, -35, y - cy - 35);
    ctx.quadraticCurveTo(-35, y - cy - 70, 0, y - cy - 100);
    ctx.closePath();
    ctx.fill();

    // Inner flame
    const innerGradient = ctx.createLinearGradient(0, y - cy - 80, 0, y - cy);
    innerGradient.addColorStop(0, `rgba(255, 220, 50, ${alpha})`);
    innerGradient.addColorStop(0.5, `rgba(255, 180, 0, ${alpha})`);
    innerGradient.addColorStop(1, `rgba(255, 100, 0, ${alpha})`);
    ctx.fillStyle = innerGradient;
    
    ctx.beginPath();
    ctx.moveTo(0, y - cy - 80);
    ctx.quadraticCurveTo(22, y - cy - 55, 22, y - cy - 25);
    ctx.quadraticCurveTo(24, y - cy - 5, 15, y - cy + 1);
    ctx.lineTo(-15, y - cy + 1);
    ctx.quadraticCurveTo(-24, y - cy - 5, -22, y - cy - 25);
    ctx.quadraticCurveTo(-22, y - cy - 55, 0, y - cy - 80);
    ctx.closePath();
    ctx.fill();

    // Core
    ctx.fillStyle = `rgba(255, 255, 200, ${alpha})`;
    ctx.beginPath();
    ctx.arc(0, y - cy - 40, 12, 0, Math.PI * 2);
    ctx.fill();

    // Eyes (angry, glowing)
    ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`;
    ctx.beginPath();
    ctx.arc(-12, y - cy - 35, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(12, y - cy - 35, 4, 0, Math.PI * 2);
    ctx.fill();

    // Angry brows
    ctx.strokeStyle = `rgba(255, 255, 255, ${alpha})`;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(-20, y - cy - 42);
    ctx.lineTo(-6, y - cy - 38);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(20, y - cy - 42);
    ctx.lineTo(6, y - cy - 38);
    ctx.stroke();

    // Fire arms REACHING toward oasis (right)
    const armReach = 0.5 + Math.sin(time * 1.2) * 0.3;
    
    ctx.strokeStyle = `rgba(255, 100, 0, ${alpha})`;
    ctx.lineWidth = 12;
    ctx.lineCap = 'round';
    
    // Upper arm
    ctx.beginPath();
    ctx.moveTo(30, y - cy - 40);
    ctx.quadraticCurveTo(
      70 + armReach * 30, y - cy - 60,
      95 + armReach * 35, y - cy - 35
    );
    ctx.stroke();
    
    // Lower arm
    ctx.beginPath();
    ctx.moveTo(35, y - cy - 10);
    ctx.quadraticCurveTo(
      65 + armReach * 20, y - cy - 20,
      90 + armReach * 25, y - cy - 5
    );
    ctx.stroke();

    // Fireball at hands
    const fbSize = 15 + Math.sin(time * 6) * 5;
    ctx.fillStyle = `rgba(255, 60, 0, ${alpha})`;
    ctx.beginPath();
    ctx.arc(95 + armReach * 35, y - cy - 35, fbSize, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = `rgba(255, 180, 0, ${alpha})`;
    ctx.beginPath();
    ctx.arc(95 + armReach * 35, y - cy - 35, fbSize * 0.6, 0, Math.PI * 2);
    ctx.fill();

    // Embers flying
    for (let i = 0; i < 12; i++) {
      const ex = Math.sin(time * 3 + i * 2) * 50 + 40;
      const ey = y - cy - Math.abs(Math.sin(time + i * 1.5)) * 100 - 20;
      const es = 2 + Math.sin(time * 4 + i) * 1.5;
      ctx.fillStyle = `rgba(255, ${180 + Math.sin(time + i) * 50}, 0, ${alpha * (0.5 + Math.sin(time * 2 + i) * 0.3)})`;
      ctx.beginPath();
      ctx.arc(ex, ey, es, 0, Math.PI * 2);
      ctx.fill();
    }

    // Attack particles toward oasis
    for (let i = 0; i < 8; i++) {
      const progress = (time * 0.5 + i * 0.8) % 1;
      const px = 40 + progress * 150;
      const py = -Math.sin(progress * Math.PI) * 40 + Math.sin(time * 2 + i) * 20;
      const ps = 3 + Math.sin(time * 5 + i) * 2;
      ctx.fillStyle = `rgba(255, ${100 + progress * 100}, 0, ${alpha * (1 - progress)})`;
      ctx.beginPath();
      ctx.arc(px, py, ps, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();
  }, []);

  const drawWaterElemental = useCallback((ctx: CanvasRenderingContext2D, x: number, y: number, time: number, alpha: number, cy: number) => {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.translate(x, y);
    
    const flow = Math.sin(time * 2) * 10;
    
    // Body - flowing water form
    const waterGradient = ctx.createLinearGradient(0, y - cy - 100, 0, y - cy + 20);
    waterGradient.addColorStop(0, `rgba(0, 180, 255, ${alpha})`);
    waterGradient.addColorStop(0.3, `rgba(0, 120, 255, ${alpha})`);
    waterGradient.addColorStop(0.7, `rgba(0, 80, 255, ${alpha})`);
    waterGradient.addColorStop(1, `rgba(0, 40, 200, ${alpha})`);
    ctx.fillStyle = waterGradient;
    
    // Main body - fluid shape
    ctx.beginPath();
    ctx.moveTo(0, y - cy - 100);
    ctx.quadraticCurveTo(40, y - cy - 70, 45, y - cy - 40);
    ctx.quadraticCurveTo(55 + flow, y - cy - 10, 50, y - cy + 5);
    ctx.lineTo(-50, y - cy + 5);
    ctx.quadraticCurveTo(-55 + flow, y - cy - 10, -50, y - cy - 40);
    ctx.quadraticCurveTo(-40, y - cy - 70, 0, y - cy - 100);
    ctx.closePath();
    ctx.fill();

    // Inner highlight
    ctx.fillStyle = `rgba(100, 220, 255, ${alpha * 0.6})`;
    ctx.beginPath();
    ctx.moveTo(0, y - cy - 85);
    ctx.quadraticCurveTo(25, y - cy - 60, 25, y - cy - 35);
    ctx.quadraticCurveTo(30, y - cy - 10, 20, y - cy + 3);
    ctx.lineTo(-20, y - cy + 3);
    ctx.quadraticCurveTo(-30, y - cy - 10, -25, y - cy - 35);
    ctx.quadraticCurveTo(-25, y - cy - 60, 0, y - cy - 85);
    ctx.closePath();
    ctx.fill();

    // Splash particles (defensive)
    for (let i = 0; i < 15; i++) {
      const angle = (i / 15) * Math.PI * 2 + time;
      const dist = 40 + Math.sin(time * 3 + i) * 15;
      const sx = Math.cos(angle) * dist;
      const sy = Math.sin(angle) * dist * 0.6;
      const size = 3 + Math.sin(time * 4 + i) * 2;
      ctx.fillStyle = `rgba(100, 220, 255, ${alpha * (0.5 + Math.sin(time * 2 + i) * 0.3)})`;
      ctx.beginPath();
      ctx.arc(sx, sy, size, 0, Math.PI * 2);
      ctx.fill();
    }

    // Water arms DEFENDING oasis (left)
    const armReach = 0.5 + Math.sin(time * 1.5) * 0.4;
    
    ctx.strokeStyle = `rgba(0, 200, 255, ${alpha})`;
    ctx.lineWidth = 14;
    ctx.lineCap = 'round';
    
    // Upper arm - blocking
    ctx.beginPath();
    ctx.moveTo(-30, y - cy - 40);
    ctx.quadraticCurveTo(
      -70 - armReach * 30, y - cy - 60,
      -95 - armReach * 35, y - cy - 35
    );
    ctx.stroke();
    
    // Lower arm - sweeping
    ctx.beginPath();
    ctx.moveTo(-35, y - cy - 10);
    ctx.quadraticCurveTo(
      -65 - armReach * 20, y - cy - 20,
      -90 - armReach * 25, y - cy - 5
    );
    ctx.stroke();

    // Water shield at hands
    const shieldSize = 25 + Math.sin(time * 5) * 8;
    const shieldGradient = ctx.createRadialGradient(-95 - armReach * 35, y - cy - 35, 0, -95 - armReach * 35, y - cy - 35, shieldSize);
    shieldGradient.addColorStop(0, `rgba(100, 220, 255, ${alpha * 0.6})`);
    shieldGradient.addColorStop(0.5, `rgba(0, 150, 255, ${alpha * 0.3})`);
    shieldGradient.addColorStop(1, 'transparent');
    ctx.fillStyle = shieldGradient;
    ctx.beginPath();
    ctx.arc(-95 - armReach * 35, y - cy - 35, shieldSize, 0, Math.PI * 2);
    ctx.fill();

    // Defensive droplets toward oasis
    for (let i = 0; i < 10; i++) {
      const progress = (time * 0.7 + i * 0.6) % 1;
      const px = -40 - progress * 150;
      const py = -Math.sin(progress * Math.PI) * 40 + Math.sin(time * 2.5 + i) * 20;
      const ps = 4 + Math.sin(time * 5 + i) * 2;
      ctx.fillStyle = `rgba(0, ${200 + progress * 55}, 255, ${alpha * (1 - progress)})`;
      ctx.beginPath();
      ctx.arc(px, py, ps, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();
  }, []);

  const drawAirElemental = useCallback((ctx: CanvasRenderingContext2D, x: number, y: number, time: number, alpha: number, cy: number) => {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.translate(x, y);
    
    const float = Math.sin(time * 0.8) * 15;
    
    // Angelic figure with wind wings
    // Wings - large, ethereal
    ctx.strokeStyle = `rgba(200, 220, 255, ${alpha * 0.6})`;
    ctx.lineWidth = 1;
    ctx.lineCap = 'round';
    
    for (let wing = -1; wing <= 1; wing += 2) {
      for (let i = 0; i < 6; i++) {
        ctx.beginPath();
        ctx.moveTo(wing * 30, y - cy - 20);
        ctx.quadraticCurveTo(
          wing * (80 + Math.sin(time + i) * 20),
          y - cy - 60 - float - i * 15 + Math.sin(time + i * 0.8) * 15,
          wing * (100 + Math.sin(time * 0.8 + i) * 15),
          y - cy - 80 - float - i * 10
        );
        ctx.stroke();
      }
    }
    
    // Body - luminous figure
    const bodyGradient = ctx.createRadialGradient(0, y - cy - 30, 0, 0, y - cy - 30, 80);
    bodyGradient.addColorStop(0, `rgba(255, 255, 255, ${alpha * 0.8})`);
    bodyGradient.addColorStop(0.3, `rgba(200, 230, 255, ${alpha * 0.5})`);
    bodyGradient.addColorStop(1, `rgba(100, 200, 255, ${alpha * 0.2})`);
    ctx.fillStyle = bodyGradient;
    
    ctx.beginPath();
    ctx.ellipse(0, y - cy - 30 + float, 25, 50, 0, 0, Math.PI * 2);
    ctx.fill();
    
    // Halo
    ctx.strokeStyle = `rgba(255, 255, 255, ${alpha * 0.5})`;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(0, y - cy - 80 + float, 20 + Math.sin(time) * 3, 0, Math.PI * 2);
    ctx.stroke();
    
    // Face
    ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`;
    ctx.beginPath();
    ctx.arc(-6, y - cy - 25 + float, 2, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.arc(6, y - cy - 25 + float, 2, 0, Math.PI * 2);
    ctx.fill();
    
    // Wind currents - Van Gogh swirls around
    ctx.strokeStyle = `rgba(150, 200, 255, ${alpha * 0.4})`;
    ctx.lineWidth = 1.5;
    for (let i = 0; i < 5; i++) {
      const swirlTime = time * 0.3 + i * 1.2;
      ctx.beginPath();
      ctx.moveTo(Math.cos(swirlTime) * 100, y - cy + Math.sin(swirlTime) * 50 - 30);
      for (let j = 0; j < 10; j++) {
        const a = swirlTime + j * 0.6;
        ctx.lineTo(Math.cos(a) * (100 + j * 10), y - cy + Math.sin(a) * (50 + j * 5) - 30);
      }
      ctx.stroke();
    }
    
    // Wind currents toward oasis (blessing)
    for (let i = 0; i < 8; i++) {
      const progress = (time * 0.3 + i * 0.5) % 1;
      const angle = -Math.PI / 2;
      const dist = progress * 180;
      const wx = Math.cos(angle) * dist;
      const wy = Math.sin(angle) * dist - 30 + float;
      const ws = 8 + Math.sin(time * 2 + i) * 4;
      ctx.fillStyle = `rgba(200, 230, 255, ${alpha * (1 - progress)})`;
      ctx.beginPath();
      ctx.arc(wx, wy, ws, 0, Math.PI * 2);
      ctx.fill();
    }
    
    // Wind gusts protecting oasis
    ctx.strokeStyle = `rgba(150, 220, 255, ${alpha * 0.4})`;
    ctx.lineWidth = 2;
    for (let i = 0; i < 6; i++) {
      const gustProgress = (time * 0.6 + i * 0.8) % 1;
      const startX = -150 + gustProgress * 300;
      const baseY = -30 + float + Math.sin(i) * 20;
      ctx.beginPath();
      ctx.moveTo(startX - 30, baseY);
      ctx.quadraticCurveTo(startX, baseY - 20 - gustProgress * 10, startX + 30, baseY);
      ctx.stroke();
    }
    
    ctx.restore();
  }, []);

  const drawLoadingText = useCallback((ctx: CanvasRenderingContext2D, w: number, h: number, time: number, alpha: number) => {
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.fillStyle = '#00ffb4';
    ctx.font = 'bold 18px "JetBrains Mono", "Fira Code", monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'bottom';
    
    // Loading animation
    const dots = Math.floor(time * 2) % 4;
    const loadingText = 'Loading' + '.'.repeat(dots);
    
    // Glow effect
    ctx.shadowColor = '#00ffb4';
    ctx.shadowBlur = 20;
    ctx.fillText(loadingText, w * 0.5, h - 40);
    ctx.shadowBlur = 0;
    
    // Subtitle
    ctx.fillStyle = `rgba(180, 200, 255, ${alpha * 0.7})`;
    ctx.font = '14px "JetBrains Mono", monospace';
    ctx.fillText('Cyberpunk Oasis', w * 0.5, h - 15);
    
    ctx.restore();
  }, []);

  const render = useCallback(() => {
    const c = canvasRef.current;
    if (!c) return;
    const ctx = c.getContext('2d');
    if (!ctx) return;

    const now = performance.now();
    const time = (now - startTimeRef.current) / 1000;
    const w = c.width;
    const h = c.height;
    const progress = Math.min(1, time / 6); // 6 second splash
    const fadeIn = Math.min(1, time * 0.5);
    const fadeOut = progress > 0.85 ? 1 - (progress - 0.85) / 0.15 : 1;
    const alpha = Math.min(fadeIn, fadeOut);

    ctx.clearRect(0, 0, w, h);

    const cx = w * 0.5;
    const cy = h * 0.5;
    const oasisRadius = Math.min(w, h) * 0.18;

    // 1. Cyberpunk sky with Van Gogh swirls
    drawCyberpunkSky(ctx, w, h, time, alpha);
    
    // 2. Stars
    drawStars(ctx, w, h, time, alpha);
    
    // 3. Oasis (center)
    drawOasis(ctx, cx, cy, oasisRadius, time, alpha);
    
    // 4. Earth Elemental (bottom - Atlas holding oasis)
    drawEarthElemental(ctx, cx, h * 0.85, time, alpha, cy);
    
    // 5. Fire Elemental (left - attacking)
    drawFireElemental(ctx, w * 0.1, h * 0.5, time, alpha, cy);
    
    // 6. Water Elemental (right - defending)
    drawWaterElemental(ctx, w * 0.9, h * 0.5, time, alpha, cy);
    
    // 7. Air Elemental (top - angel blessing)
    drawAirElemental(ctx, cx, h * 0.12, time, alpha, cy);
    
    // 8. Loading text at bottom
    drawLoadingText(ctx, w, h, time, alpha);

    // Title at top
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.fillStyle = '#fff';
    ctx.font = 'bold 32px Georgia, serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.shadowColor = 'rgba(0, 255, 180, 0.5)';
    ctx.shadowBlur = 30;
    ctx.fillText('Elemental Life', w * 0.5, 30);
    ctx.restore();

    if (progress >= 1 && !doneRef.current) {
      doneRef.current = true;
      onComplete();
      return;
    }

    animationIdRef.current = requestAnimationFrame(render);
  }, []);

  useEffect(() => {
    const c = canvasRef.current;
    if (c) {
      c.width = window.innerWidth;
      c.height = window.innerHeight;
    }
    startTimeRef.current = performance.now();
    animationIdRef.current = requestAnimationFrame(render);
    
    const handleResize = () => {
      if (canvasRef.current) {
        canvasRef.current.width = window.innerWidth;
        canvasRef.current.height = window.innerHeight;
      }
    };
    window.addEventListener('resize', handleResize);
    
    return () => {
      if (animationIdRef.current) cancelAnimationFrame(animationIdRef.current);
      window.removeEventListener('resize', handleResize);
    };
  }, [render]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: '100%',
        height: '100vh',
        display: 'block',
        cursor: 'pointer',
        background: '#000'
      }}
      onClick={() => { if (!doneRef.current) { doneRef.current = true; onComplete(); }}}
    />
  );
}