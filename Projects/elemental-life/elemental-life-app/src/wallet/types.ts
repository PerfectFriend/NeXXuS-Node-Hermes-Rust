export interface TokenInfo {
  symbol: string;
  name: string;
  chain: string;
  contract: string;
  decimals: number;
  coinGeckoId?: string;
  derivationIndex?: number;
  icon: string;
}

export interface WalletBalance {
  token: TokenInfo;
  balance: string;
  balanceUsd: number | null;
  address: string;
}

export const TOKENS: TokenInfo[] = [
  { symbol: 'ELEMENTAL', name: 'Elemental Token', chain: 'internal', contract: '', decimals: 0, icon: '⬡' },
];

export interface Transaction {
  hash: string;
  from: string;
  to: string;
  value: string;
  token: string;
  timestamp: number;
  status: 'pending' | 'confirmed' | 'failed';
}