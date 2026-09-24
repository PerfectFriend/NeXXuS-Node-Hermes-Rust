/**
 * GridRenderer — низкоуровневый Canvas-рендерер для игрового поля.
 * Модель viewport:
 *   viewport.x/y  = CSS-пиксельная позиция мирового нуля (0,0) на canvas
 *   viewport.zoom = масштаб (1 = 100%)
 *   canvas_x_css  = world_x * zoom + viewport.x
 *   world_x       = (canvas_x_css - viewport.x) / zoom
 */

import { COLORS, type GeometryKey, type CellData } from '../engine/engine';

export interface Viewport { x: number; y: number; zoom: number; width: number; height: number; initialized?: boolean; }

interface HexCellGeometry { type: 'hex'; centerX: number; centerY: number; radius: number; points: number[][]; }
interface SquareCellGeometry { type: 'square'; x: number; y: number; size: number; }
type CellGeometry = HexCellGeometry | SquareCellGeometry;

export class GridRenderer {
	private canvas: HTMLCanvasElement;
	private ctx: CanvasRenderingContext2D;
	private cellSize: number;
	private geometry: GeometryKey;
	private radius: number;
	private cells = new Map<string, CellGeometry>();
	private viewport: Viewport = { x: 0, y: 0, zoom: 1, width: 0, height: 0 };
	private dirty = true;
	private field = new Map<string, CellData>();
	private dpr = 1;
	private resizeObserver?: ResizeObserver;
	private viewportSynced = false;
	private hasResized = false;
	private userHasInteracted = false;

	private boundPointerDown: (e: PointerEvent) => void = null!;
	private boundPointerMove: (e: PointerEvent) => void = null!;
	private boundPointerUp: (e: PointerEvent) => void = null!;
	private boundWheel: (e: WheelEvent) => void = null!;

	constructor(canvas: HTMLCanvasElement, geometry: GeometryKey, radius: number, cellSize: number) {
		this.canvas = canvas; this.geometry = geometry; this.radius = radius; this.cellSize = cellSize;
		const ctx = canvas.getContext('2d', { alpha: false, desynchronized: true });
		if (!ctx) throw new Error('Canvas 2D context not available');
		this.ctx = ctx;
		this.dpr = window.devicePixelRatio || 1;
		this.precomputeCellGeometry();
		this.setupResizeObserver();
		this.setupEventListeners();
	}

	private precomputeCellGeometry(): void {
		this.cells.clear();
		if (this.geometry === 'hex') this.precomputeHexGeometry(); else this.precomputeSquareGeometry();
	}

	private precomputeHexGeometry(): void {
		const size = this.cellSize; const sqrt3 = Math.sqrt(3);
		for (let q = -this.radius; q <= this.radius; q++) {
			const rMin = Math.max(-this.radius, -q - this.radius);
			const rMax = Math.min(this.radius, -q + this.radius);
			for (let r = rMin; r <= rMax; r++) {
				const x = size * sqrt3 * (q + r / 2); const y = size * 1.5 * r;
				const points: number[][] = [];
				for (let i = 0; i < 6; i++) {
					const angle = (Math.PI / 180) * (60 * i - 30);
					points.push([x + size * Math.cos(angle), y + size * Math.sin(angle)]);
				}
				this.cells.set(`${q},${r}`, { type: 'hex', centerX: x, centerY: y, radius: size, points });
			}
		}
	}

	private precomputeSquareGeometry(): void {
		const size = this.cellSize;
		for (let q = -this.radius; q <= this.radius; q++) {
			const rMin = Math.max(-this.radius, -q - this.radius);
			const rMax = Math.min(this.radius, -q + this.radius);
			for (let r = rMin; r <= rMax; r++) {
				this.cells.set(`${q},${r}`, { type: 'square', x: size * q, y: size * r, size });
			}
		}
	}

	private setupResizeObserver(): void {
		this.resizeObserver = new ResizeObserver(() => this.resize());
		if (this.canvas.parentElement) this.resizeObserver.observe(this.canvas.parentElement);
		this.resize();
	}

	requestResize(): void { this.resize(); this.dirty = true; }
	fitToScreen(): void { this.hasResized = false; this.resize(); }

	private recenterViewport(): void {
		if (this.viewport.width > 0 && this.viewport.height > 0) {
			this.centerGrid();
		}
	}

	private resize(): void {
		const parent = this.canvas.parentElement; if (!parent) return;
		const rect = parent.getBoundingClientRect();
		this.dpr = window.devicePixelRatio || 1;
		const width = Math.floor(rect.width), height = Math.floor(rect.height);
		if (this.canvas.width !== width * this.dpr || this.canvas.height !== height * this.dpr) {
			this.canvas.width = width * this.dpr; this.canvas.height = height * this.dpr;
			this.canvas.style.width = `${width}px`; this.canvas.style.height = `${height}px`;
			this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
		}
		const widthChanged = this.viewport.width !== width;
		const heightChanged = this.viewport.height !== height;
		this.viewport.width = width; this.viewport.height = height;
		// Center on first resize, or when dimensions change significantly, unless viewport was explicitly set
		if (!this.hasResized || widthChanged || heightChanged) {
			if (!this.viewportSynced) {
				this.hasResized = true;
				this.recenterViewport();
			}
		}
		this.dirty = true;
	}

	private setupEventListeners(): void {
		const pointers = new Map<number, { x: number; y: number }>();
		let isPanning = false; let lastPan = { x: 0, y: 0 }; let lastPinchDist = 0;
		const getRect = () => this.canvas.getBoundingClientRect();

		this.boundPointerDown = (e: PointerEvent) => {
			e.preventDefault(); this.canvas.setPointerCapture(e.pointerId);
			pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
			if (pointers.size === 1) { isPanning = true; lastPan = { x: e.clientX, y: e.clientY }; }
			else if (pointers.size === 2) { isPanning = false; const entries = Array.from(pointers.values());
				const dx = entries[0].x - entries[1].x; const dy = entries[0].y - entries[1].y;
				lastPinchDist = Math.sqrt(dx * dx + dy * dy); }
		};

		this.boundPointerMove = (e: PointerEvent) => {
			if (!pointers.has(e.pointerId)) return; e.preventDefault();
			pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
			if (pointers.size === 1 && isPanning) {
				const dx = e.clientX - lastPan.x; const dy = e.clientY - lastPan.y;
				this.panBy(dx / this.viewport.zoom, dy / this.viewport.zoom);
				lastPan = { x: e.clientX, y: e.clientY };
			} else if (pointers.size === 2) {
				const entries = Array.from(pointers.values());
				const dx = entries[0].x - entries[1].x; const dy = entries[0].y - entries[1].y;
				const dist = Math.sqrt(dx * dx + dy * dy);
				if (lastPinchDist > 0) {
					const factor = dist / lastPinchDist;
					const centerX = (entries[0].x + entries[1].x) / 2;
					const centerY = (entries[0].y + entries[1].y) / 2;
					const rect = getRect();
					// Viewport model is in CSS pixels (see header comment); convert client
					// coords to CSS px relative to canvas. NOTE: multiplying by dpr here
					// would corrupt the zoom anchor on HiDPI (dpr > 1) devices.
					const canvasCenterX = centerX - rect.left;
					const canvasCenterY = centerY - rect.top;
					this.zoomBy(factor, canvasCenterX, canvasCenterY);
				}
				lastPinchDist = dist;
			}
		};

		this.boundPointerUp = (e: PointerEvent) => {
			pointers.delete(e.pointerId);
			if (pointers.size < 2) lastPinchDist = 0;
			if (pointers.size === 0) isPanning = false;
		};

		this.boundWheel = (e: WheelEvent) => {
			e.preventDefault(); const rect = getRect();
			// CSS px, matching the viewport model (see header comment) — dpr must
			// NOT be applied here (device px would misplace the wheel zoom anchor
			// on HiDPI screens, e.g. dpr=2-3 on Android).
			const centerX = e.clientX - rect.left; const centerY = e.clientY - rect.top;
			const factor = e.deltaY > 0 ? 1 / 1.15 : 1.15;
			this.zoomBy(factor, centerX, centerY);
		};

		this.canvas.addEventListener('pointerdown', this.boundPointerDown);
		this.canvas.addEventListener('pointermove', this.boundPointerMove);
		this.canvas.addEventListener('pointerup', this.boundPointerUp);
		this.canvas.addEventListener('pointercancel', this.boundPointerUp);
		this.canvas.addEventListener('wheel', this.boundWheel, { passive: false });
	}

	getViewport(): Viewport { return { ...this.viewport }; }
	setViewport(vp: Viewport): void { this.viewport = { ...vp }; this.viewportSynced = true; this.dirty = true; }
	markViewportSynced(): void { this.viewportSynced = true; }
	hasUserInteracted(): boolean { return this.userHasInteracted; }
	resetInteractionFlag(): void { this.userHasInteracted = false; }
	panBy(dx: number, dy: number): void { this.viewport.x += dx; this.viewport.y += dy; this.dirty = true; this.userHasInteracted = true; }

	zoomBy(factor: number, centerX: number, centerY: number): void {
		const newZoom = Math.min(4, Math.max(0.15, this.viewport.zoom * factor));
		const ratio = newZoom / this.viewport.zoom;
		this.viewport.x = centerX - (centerX - this.viewport.x) * ratio;
		this.viewport.y = centerY - (centerY - this.viewport.y) * ratio;
		this.viewport.zoom = newZoom; this.dirty = true;
		this.userHasInteracted = true;
	}

	centerGrid(): void {
		const { width, height } = this.viewport;
		if (width <= 0 || height <= 0) return;
		// World (0,0) is at grid center. To put it at screen center:
		// translateX = width/2, translateY = height/2 (in CSS pixels)
		this.viewport.x = width / 2; 
		this.viewport.y = height / 2; 
		this.dirty = true;
	}

	resetView(): void {
		const { width, height } = this.viewport;
		if (width <= 0 || height <= 0) return;
		const gw = this.getGridWidth(), gh = this.getGridHeight();
		const fitZoom = Math.min(width / gw, height / gh) * 0.9;
		const zoom = Math.min(4, Math.max(0.15, fitZoom));
		this.viewport.zoom = zoom;
		// Center grid (world 0,0 at screen center)
		this.viewport.x = width / 2; 
		this.viewport.y = height / 2; 
		this.dirty = true;
	}

	private getGridWidth(): number {
		if (this.geometry === 'hex') {
			// x = cellSize * sqrt(3) * (q + r/2), q,r in [-radius, radius]
			// Max at q=radius, r=0: cellSize * sqrt(3) * radius
			// Min at q=-radius, r=0: -cellSize * sqrt(3) * radius
			return 2 * this.radius * this.cellSize * Math.sqrt(3);
		}
		// square: x = cellSize * q, q in [-radius, radius]
		return 2 * this.radius * this.cellSize;
	}

	private getGridHeight(): number {
		if (this.geometry === 'hex') {
			// y = cellSize * 1.5 * r, r in [-radius, radius]
			return 3 * this.radius * this.cellSize;
		}
		// square: y = cellSize * r, r in [-radius, radius]
		return 2 * this.radius * this.cellSize;
	}

	setField(field: Map<string, CellData>): void { this.field = field; this.dirty = true; }

	render(): void {
		if (!this.dirty) return; this.dirty = false;
		const { width, height, x, y, zoom } = this.viewport;
		this.ctx.setTransform(this.dpr * zoom, 0, 0, this.dpr * zoom, this.dpr * x, this.dpr * y);
		this.ctx.clearRect(-x / zoom, -y / zoom, width / zoom, height / zoom);
		if (this.geometry === 'hex') this.renderHexGrid(); else this.renderSquareGrid();
	}

	private renderHexGrid(): void {
		const ctx = this.ctx;
		for (const [key, cell] of this.cells) {
			const cellData = this.field.get(key); if (!cellData) continue; if (cell.type !== 'hex') continue;
			const color = COLORS[cellData.state as keyof typeof COLORS] || '#333';
			ctx.fillStyle = color; ctx.beginPath();
			ctx.moveTo(cell.points[0][0], cell.points[0][1]);
			for (let i = 1; i < cell.points.length; i++) ctx.lineTo(cell.points[i][0], cell.points[i][1]);
			ctx.closePath(); ctx.fill();
		}
	}

	private renderSquareGrid(): void {
		const ctx = this.ctx;
		for (const [key, cell] of this.cells) {
			const cellData = this.field.get(key); if (!cellData) continue; if (cell.type !== 'square') continue;
			const color = COLORS[cellData.state as keyof typeof COLORS] || '#333';
			ctx.fillStyle = color; ctx.fillRect(cell.x, cell.y, cell.size, cell.size);
		}
	}

	destroy(): void {
		if (this.resizeObserver) { this.resizeObserver.disconnect(); this.resizeObserver = undefined; }
		this.canvas.removeEventListener('pointerdown', this.boundPointerDown);
		this.canvas.removeEventListener('pointermove', this.boundPointerMove);
		this.canvas.removeEventListener('pointerup', this.boundPointerUp);
		this.canvas.removeEventListener('pointercancel', this.boundPointerUp);
		this.canvas.removeEventListener('wheel', this.boundWheel);
	}
}