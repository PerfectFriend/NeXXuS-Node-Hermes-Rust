/**
 * MiniChart — миниатюрный график на Canvas для отображения истории воды.
 *
 * Рисует ломаную линию по точкам history[].
 * Масштабирует данные по вертикали (min..max) и горизонтали (0..length-1).
 * Автоматически подстраивается под размер контейнера через ResizeObserver.
 */

import { useEffect, useRef } from 'react';

interface MiniChartProps {
  history: number[];
  color?: string;
}

export function MiniChart({ history, color = '#2196f3' }: MiniChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const draw = () => {
    const canvas = canvasRef.current;
    if (!canvas || history.length < 2) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // DPR-aware подготовка Canvas
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const width = rect.width;
    const height = rect.height;
    const padding = 4;

    const maxVal = Math.max(...history, 1);
    const minVal = Math.min(...history);

    // Очистка
    ctx.clearRect(0, 0, width, height);

    // Отрисовка линии
    ctx.beginPath();
    const yScale = (v: number) =>
      height - padding - ((v - minVal) / (maxVal - minVal || 1)) * (height - 2 * padding);

    ctx.moveTo(padding, yScale(history[0]));
    for (let i = 1; i < history.length; i++) {
      const x = padding + (i / (history.length - 1)) * (width - 2 * padding);
      ctx.lineTo(x, yScale(history[i]));
    }

    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.stroke();

    // Подписи min/max
    ctx.fillStyle = '#8b949e';
    ctx.font = '10px system-ui';
    ctx.fillText(`${maxVal}`, padding, padding + 10);
    ctx.fillText(`${minVal}`, padding, height - padding - 2);
  };

  // Перерисовка при изменении данных
  useEffect(() => {
    draw();
  }, [history, color]);

  // ResizeObserver для адаптации к изменению размеров
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ro = new ResizeObserver(() => draw());
    ro.observe(canvas.parentElement ?? canvas);
    return () => ro.disconnect();
  }, []);

  return <canvas ref={canvasRef} className="mini-chart" />;
}
