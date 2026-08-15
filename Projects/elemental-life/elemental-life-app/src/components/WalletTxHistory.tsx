import { useState, useEffect } from 'react';
import { getElementalHistory, type LedgerEntry } from '../wallet';

interface WalletTxHistoryProps {
  onClose: () => void;
}

export function WalletTxHistory({ onClose }: WalletTxHistoryProps) {
  const [txs, setTxs] = useState<LedgerEntry[]>([]);

  const loadTxs = () => setTxs(getElementalHistory());
  useEffect(() => {
    loadTxs();
    const id = setInterval(loadTxs, 3000);
    return () => clearInterval(id);
  }, []);

  const containerStyle: React.CSSProperties = {
    position: 'fixed', inset: 0, zIndex: 10001,
    display: 'flex', flexDirection: 'column',
    background: '#0d1117', color: '#e6edf3',
    fontFamily: 'system-ui, -apple-system, sans-serif',
  };

  const headerStyle: React.CSSProperties = {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '16px 20px', borderBottom: '1px solid #21262d',
  };

  const ago = (ts: number) => {
    const diff = Date.now() - ts;
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#58a6ff', cursor: 'pointer', fontSize: 14 }}>← Back</button>
        <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>History</h2>
        <div style={{ width: 60 }} />
      </div>
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {txs.length === 0 && (
          <p style={{ padding: 40, textAlign: 'center', color: '#8b949e', fontSize: 13 }}>
            No transactions yet
          </p>
        )}
        {[...txs].reverse().map((tx, i) => (
          <div key={i} style={{
            padding: '12px 20px', borderBottom: '1px solid #161b22',
            display: 'flex', flexDirection: 'column', gap: 2,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 600, fontSize: 14 }}>ELEMENTAL</span>
              <span style={{
                fontSize: 12, padding: '2px 8px', borderRadius: 10,
                background: tx.amount > 0 ? '#1a3a1a' : '#3d1515',
                color: tx.amount > 0 ? '#3fb950' : '#f85149',
              }}>
                {tx.amount > 0 ? '+' : ''}{tx.amount}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#8b949e' }}>
              <span style={{ fontFamily: 'monospace', fontSize: 10, wordBreak: 'break-all', flex: 1, marginRight: 8 }}>
                {tx.reason}
              </span>
              <span style={{ flexShrink: 0 }}>{tx.to}</span>
            </div>
            <span style={{ fontSize: 11, color: '#484f58' }}>{ago(tx.ts)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}