/**
 * GridCanvas — React-обёртка над GridRenderer.
 *
 * Управляет жизненным циклом рендерера:
 * - Создаёт GridRenderer при монтировании / смене геометрии
 * - Синхронизирует field (React → renderer)
 * - Синхронизирует viewport (React ⇄ renderer, двусторонняя)
 * - Запускает RAF-цикл рендеринга
 * - Вызывает onViewportChange при изменениях от жестов (через RAF)
 *
 * Двусторонняя синхронизация viewport:
 * - React → renderer: через useEffect, когда меняется viewport-проп
 * - Renderer → React: через RAF, читает getViewport() и вызывает onViewportChange
 * - lastReportedVp ref предотвращает цикличные вызовы
 */

import { useEffect, useRef, useCallback, useImperativeHandle, forwardRef } from 'react';
import { GridRenderer, type Viewport } from '../renderer/GridRenderer';
import type { CellData, GeometryKey } from '../engine/engine';

export interface GridCanvasHandle {
  centerView: () => void;
  resetView: () => void;
  exportViewport: () => Viewport;
  importViewport: (vp: Viewport) => void;
  forceCenter: () => void;
}

interface GridCanvasProps {
  field: Map<string, CellData>;
  geometry: GeometryKey;
  radius: number;
  cellSize: number;
  onCellClick: (q: number, r: number) => void;
  viewport: Viewport;
  onViewportChange: (vp: Viewport) => void;
}

export const GridCanvas = forwardRef<GridCanvasHandle, GridCanvasProps>(function GridCanvas({
  field, geometry, radius, cellSize, onCellClick, viewport, onViewportChange,
}, ref) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
    const rendererRef = useRef<GridRenderer | null>(null);
    const lastReportedVp = useRef<Viewport | null>(null);
    /** true после первого RAF (рендерер проинициализирован, его viewport — истина) */
    const rendererInitialized = useRef(false);
    /** Предотвращает синхронизацию React→Renderer на первом кадре (не затираем центрирование) */
    const skipFirstReactSync = useRef(true);
    /** Prevent sync effect from overwriting a programmatic center/pan/zoom */
    const ignoreNextSync = useRef(false);

  useImperativeHandle(ref, () => ({
      centerView: () => {
        rendererRef.current?.centerGrid();
      },
      resetView: () => {
        rendererRef.current?.resetView();
      },
      exportViewport: () => {
        return rendererRef.current?.getViewport() ?? { x: 0, y: 0, zoom: 1, width: 0, height: 0 };
      },
      importViewport: (vp: Viewport) => {
        rendererRef.current?.setViewport(vp);
      },
      forceCenter: () => {
              if (rendererRef.current) {
                rendererRef.current.centerGrid();
                const centeredVp = rendererRef.current.getViewport();
                ignoreNextSync.current = true;
                onViewportChange({ ...centeredVp, initialized: true });
              }
            },
    }), []);

  // Инициализация рендерера при монтировании или смене геометрии
            useEffect(() => {
              if (!canvasRef.current) return;
              const renderer = new GridRenderer(canvasRef.current, geometry, radius, cellSize);
              rendererRef.current = renderer;
              rendererInitialized.current = false;
              skipFirstReactSync.current = true;
              // Force resize and center with actual container dimensions
              renderer.fitToScreen();
              // Defer centering to next frame when container dimensions are known
              requestAnimationFrame(() => {
                if (rendererRef.current) {
                  rendererRef.current.centerGrid();
                  const centeredVp = rendererRef.current.getViewport();
                  lastReportedVp.current = centeredVp;
                  onViewportChange({ ...centeredVp, initialized: true });
                }
              });

              return () => {
                renderer.destroy();
                rendererRef.current = null;
              };
            }, [geometry, radius, cellSize, onCellClick]);

  // Синхронизация field: React → renderer
  useEffect(() => {
    if (!rendererRef.current) return;
    rendererRef.current.setField(field);
  }, [field]);

  // Синхронизация viewport: React → renderer
            useEffect(() => {
              if (!rendererRef.current) return;
              // Не затираем viewport рендерера, если он еще не инициализирован в React (initialized: false)
              // Это позволяет рендереру установить свой центрированный viewport первым
              if (!viewport.initialized) return;
              if (skipFirstReactSync.current) return;
              // Skip sync if a programmatic change (center/pan/zoom) just happened
              if (ignoreNextSync.current) {
                ignoreNextSync.current = false;
                return;
              }
              // Синхронизируем только x, y, zoom из React. width/height принадлежат рендереру (контейнер).
              const vp = rendererRef.current.getViewport();
              if (
                vp.x !== viewport.x || vp.y !== viewport.y ||
                vp.zoom !== viewport.zoom
              ) {
                rendererRef.current.setViewport({ ...viewport, width: vp.width, height: vp.height });
                // Помечаем что ресайз уже обработан — не автоцентрируем
                rendererRef.current.markViewportSynced();
              }
            }, [viewport, onViewportChange]);

  // RAF-цикл
      const render = useCallback(() => {
        if (!rendererRef.current) return;
        rendererRef.current.render();

        if (!rendererInitialized.current) {
          rendererInitialized.current = true;
          skipFirstReactSync.current = false;
          // На первом рендере сообщаем React реальный viewport рендерера (уже отцентрированный)
          const initVp = rendererRef.current.getViewport();
          lastReportedVp.current = initVp;
          // Mark viewport as initialized so React sync can proceed
          onViewportChange({ ...initVp, initialized: true });
    
          requestAnimationFrame(render);
          return;
        }

      const currentVp = rendererRef.current.getViewport();
      const last = lastReportedVp.current;
      if (
        !last || currentVp.x !== last.x || currentVp.y !== last.y ||
        currentVp.zoom !== last.zoom || currentVp.width !== last.width || currentVp.height !== last.height
      ) {
        lastReportedVp.current = currentVp;
        onViewportChange(currentVp);
      }
      requestAnimationFrame(render);
    }, [onViewportChange]);

  useEffect(() => {
    const id = requestAnimationFrame(render);
    return () => cancelAnimationFrame(id);
  }, [render]);

  return <canvas ref={canvasRef} style={{ width: '100%', height: '100%', touchAction: 'none' }} />;
});
