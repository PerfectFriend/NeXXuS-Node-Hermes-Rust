/**
 * Controls — UI-компоненты для управления параметрами симуляции.
 *
 * ParamSlider: ползунок + числовой ввод для параметров (например, шанс молнии).
 *   - Поддерживает drag (мышь) и swipe (touch) для точной подстройки
 *   - Ограничивает значение в диапазоне [min, max] с заданным шагом
 *   - Отображает процент заполнения через CSS-переменную --slider-percent
 *
 * CheckboxRow: простой чекбокс с меткой для boolean-параметров.
 */

import { useState, useRef, useEffect, type ChangeEvent } from 'react';

interface ParamSliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
}

export function ParamSlider({ label, value, min, max, step, onChange }: ParamSliderProps) {
  const [localValue, setLocalValue] = useState(value);
  const dragging = useRef(false);
  const startX = useRef(0);
  const startValue = useRef(0);

  // Синхронизация локального значения с пропом (только когда не идёт drag)
  useEffect(() => {
    if (!dragging.current) setLocalValue(value);
  }, [value]);

  // Drag-обработчики для мыши
  const handleMouseDown = (e: React.MouseEvent) => {
    dragging.current = true;
    startX.current = e.clientX;
    startValue.current = localValue;
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (!dragging.current) return;
    const dx = e.clientX - startX.current;
    const delta = (dx / 200) * (max - min);
    const newValue = Math.round((startValue.current + delta) / step) * step;
    setLocalValue(Math.max(min, Math.min(max, newValue)));
  };

  const handleMouseUp = () => {
    dragging.current = false;
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
    onChange(localValue);
  };

  // Drag-обработчики для touch
  const handleTouchStart = (e: React.TouchEvent) => {
    dragging.current = true;
    startX.current = e.touches[0].clientX;
    startValue.current = localValue;
    document.addEventListener('touchmove', handleTouchMove, { passive: false });
    document.addEventListener('touchend', handleTouchEnd);
  };

  const handleTouchMove = (e: TouchEvent) => {
    e.preventDefault();
    if (!dragging.current) return;
    const dx = e.touches[0].clientX - startX.current;
    const delta = (dx / 200) * (max - min);
    const newValue = Math.round((startValue.current + delta) / step) * step;
    setLocalValue(Math.max(min, Math.min(max, newValue)));
  };

  const handleTouchEnd = () => {
    dragging.current = false;
    document.removeEventListener('touchmove', handleTouchMove);
    document.removeEventListener('touchend', handleTouchEnd);
    onChange(localValue);
  };

  // Обработка прямого ввода числа
  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const num = parseFloat(e.target.value);
    if (!isNaN(num)) {
      setLocalValue(Math.max(min, Math.min(max, num)));
    }
  };

  const handleInputBlur = () => onChange(localValue);

  const percent = ((localValue - min) / (max - min)) * 100;

  return (
    <div className="slider-wrapper">
      <label className="slider-label">{label}</label>
      <div className="slider-row">
        <input
          type="range" min={min} max={max} step={step}
          value={localValue}
          onChange={handleInputChange} onBlur={handleInputBlur}
          onMouseDown={handleMouseDown} onTouchStart={handleTouchStart}
          className="slider"
          style={{ '--slider-percent': `${percent}%` } as React.CSSProperties}
        />
        <input
          type="number" value={localValue}
          onChange={handleInputChange} onBlur={handleInputBlur}
          min={min} max={max} step={step}
          className="slider-value"
        />
      </div>
    </div>
  );
}

interface CheckboxRowProps {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

export function CheckboxRow({ label, checked, onChange }: CheckboxRowProps) {
  return (
    <label className="checkbox-row">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  );
}
