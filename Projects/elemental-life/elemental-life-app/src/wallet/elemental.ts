/**
 * ELEMENTAL token — внутренний токен экосистемы.
 *
 * Хранится в локальном ledger'е (localStorage).
 * Не требует газа или внешней сети.
 *
 * Способы получения:
 * - Прохождение уровней головоломки (награда)
 * - Достижения в песочнице
 * - Отправка/получение между пользователями (через QR или relay)
 */

const STORAGE_KEY = 'el_elemental_ledger';

export interface LedgerEntry {
  /** Адрес получателя */
  to: string;
  /** Количество */
  amount: number;
  /** Причина/заметка */
  reason: string;
  /** Timestamp */
  ts: number;
}

interface ElementalLedger {
  /** Баланс текущего пользователя */
  balance: number;
  /** История транзакций */
  history: LedgerEntry[];
  /** Всего добыто (mined) */
  totalMined: number;
  /** Всего отправлено */
  totalSent: number;
  /** Всего получено */
  totalReceived: number;
}

function loadLedger(): ElementalLedger {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return { balance: 0, history: [], totalMined: 0, totalSent: 0, totalReceived: 0 };
}

function saveLedger(ledger: ElementalLedger): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ledger));
}

/** Добавить ELEMENTAL за прохождение уровня */
export function rewardLevelCompletion(levelIndex: number, _geometry: string): number {
  const ledger = loadLedger();
  const reward = 10 + levelIndex * 5; // 10, 15, 20, 25, 30
  const reason = `Puzzle ${_geometry}: level ${levelIndex + 1}`;
  ledger.balance += reward;
  ledger.totalMined += reward;
  ledger.history.push({ to: 'self', amount: reward, reason, ts: Date.now() });
  saveLedger(ledger);
  return reward;
}

/** Получить текущий баланс ELEMENTAL */
export function getElementalBalance(): number {
  return loadLedger().balance;
}

/** Получить историю ELEMENTAL */
export function getElementalHistory() {
  return loadLedger().history;
}

/** Отправить ELEMENTAL другому пользователю */
export function sendElemental(to: string, amount: number, reason?: string): boolean {
  const ledger = loadLedger();
  if (ledger.balance < amount) return false;
  ledger.balance -= amount;
  ledger.totalSent += amount;
  ledger.history.push({ to, amount: -amount, reason: reason ?? `Sent to ${to}`, ts: Date.now() });
  saveLedger(ledger);
  return true;
}

/** Получить ELEMENTAL от другого пользователя */
export function receiveElemental(from: string, amount: number, reason?: string): void {
  const ledger = loadLedger();
  ledger.balance += amount;
  ledger.totalReceived += amount;
  ledger.history.push({ to: 'self', amount, reason: reason ?? `Received from ${from}`, ts: Date.now() });
  saveLedger(ledger);
}

/** Сбросить баланс */
export function resetElemental(): void {
  if (typeof window !== 'undefined' && (window as any).__ELEMENTAL_DEBUG) {
    localStorage.removeItem(STORAGE_KEY);
  }
}

/** Получить полную статистику */
export function getElementalStats() {
  return loadLedger();
}
