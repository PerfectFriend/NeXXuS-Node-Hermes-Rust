const STORAGE_KEY = 'el_tx_history';

export interface TxRecord {
  hash: string;
  token: string;
  amount: string;
  to: string;
  timestamp: number;
  status: 'pending' | 'confirmed' | 'failed';
  direction?: 'sent' | 'received';
}

function loadHistory(): TxRecord[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

function saveHistory(txs: TxRecord[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(txs));
}

export function addTx(record: TxRecord): void {
  const txs = loadHistory();
  txs.unshift(record);
  saveHistory(txs.slice(0, 50));
}

export function updateTxStatus(hash: string, status: TxRecord['status']): void {
  const txs = loadHistory();
  const tx = txs.find(t => t.hash === hash);
  if (tx) tx.status = status;
  saveHistory(txs);
}

export function getTxHistory(token?: string): TxRecord[] {
  const txs = loadHistory();
  return token ? txs.filter(t => t.token === token) : txs;
}

export function clearHistory(): void {
  localStorage.removeItem(STORAGE_KEY);
}
