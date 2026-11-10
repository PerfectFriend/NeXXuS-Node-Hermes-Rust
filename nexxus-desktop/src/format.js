// Чистые функции форматирования — без DOM, покрыты node --test (tests/format.test.mjs).

/// Аптайм из миллисекунд в человекочитаемую строку.
export function formatUptime(ms) {
  if (ms == null || ms < 0 || !Number.isFinite(ms)) return '—';
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const h = Math.floor(m / 60);
  const d = Math.floor(h / 24);
  if (d > 0) return `${d} д ${h % 24} ч`;
  if (h > 0) return `${h} ч ${m % 60} мин`;
  if (m > 0) return `${m} мин ${s % 60} с`;
  return `${s} с`;
}

/// Байты в человекочитаемую строку (КБ/МБ/ГБ).
export function formatBytes(n) {
  if (n == null || n < 0 || !Number.isFinite(n)) return '—';
  if (n < 1024) return `${n} Б`;
  const units = ['КБ', 'МБ', 'ГБ', 'ТБ'];
  let v = n;
  let u = -1;
  do {
    v /= 1024;
    u++;
  } while (v >= 1024 && u < units.length - 1);
  return `${v.toFixed(v >= 100 ? 0 : 1)} ${units[u]}`;
}

/// CSS-класс статуса для подсветки.
export function statusClass(state) {
  switch (state) {
    case 'Running':
      return 'status-running';
    case 'Unhealthy':
      return 'status-unhealthy';
    case 'Starting':
    case 'Restarting':
      return 'status-starting';
    default:
      return 'status-stopped';
  }
}
