export { type TokenInfo, type WalletBalance, type Transaction, TOKENS } from './types';
export { rewardLevelCompletion, getElementalBalance, getElementalHistory, sendElemental, receiveElemental, resetElemental, getElementalStats, type LedgerEntry } from './elemental';
export { addTx, updateTxStatus, getTxHistory, clearHistory, type TxRecord } from './history';

/** Format balance for display with given decimals */
export function formatBalance(balance: string, decimals: number): string {
  const num = Number(balance);
  if (decimals === 0) return String(Math.floor(num));
  const fixed = num.toFixed(decimals);
  return fixed.replace(/\.?0+$/, '');
}