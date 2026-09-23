import { useState, useEffect, useCallback } from 'react';
import { type WalletBalance, formatBalance } from '../wallet';
import { getElementalStats, sendElemental } from '../wallet/elemental';
import { WalletQrCode } from './WalletQrCode';
import { WalletTxHistory } from './WalletTxHistory';

interface WalletScreenProps {
  onClose: () => void;
}

type WalletView = 'portfolio' | 'send' | 'receive' | 'history';

export function WalletScreen({ onClose }: WalletScreenProps) {
  const [balances, setBalances] = useState<WalletBalance[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<WalletView>('portfolio');
  const [selectedToken, setSelectedToken] = useState<string | null>(null);
  const [detailToken, setDetailToken] = useState<WalletBalance | null>(null);

  // Send form state
  const [to, setTo] = useState('');
  const [amount, setAmount] = useState('');
  const [success, setSuccess] = useState('');

  const selectedBalance = balances.find(b => b.token.symbol === selectedToken);

  const loadBalances = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Only ELEMENTAL token (internal, no external network needed)
      const elementalStats = getElementalStats();
      const elementalBalance: WalletBalance = {
        token: {
          symbol: 'ELEMENTAL',
          name: 'Elemental Token',
          chain: 'internal',
          contract: '',
          decimals: 0,
          icon: '⬡',
        },
        balance: String(elementalStats.balance),
        balanceUsd: null, // No USD price for internal token
        address: 'internal',
      };
      setBalances([elementalBalance]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load balance');
    } finally {
      setLoading(false);
    }
  }, []);

  const handleSend = useCallback(() => {
    setError('');
    setSuccess('');
    const numAmount = parseInt(amount);
    if (!to) { setError('Enter recipient address'); return; }
    if (!amount || isNaN(numAmount) || numAmount <= 0) { setError('Enter a valid amount'); return; }
    const elementalStats = getElementalStats();
    if (numAmount > elementalStats.balance) { setError('Insufficient balance'); return; }
    const ok = sendElemental(to, numAmount, `Sent to ${to.slice(0, 8)}...`);
    if (ok) {
      setSuccess(`Sent ${numAmount} ELEMENTAL`);
      setAmount('');
      setTo('');
      loadBalances();
    } else {
      setError('Send failed');
    }
  }, [to, amount, loadBalances]);

  useEffect(() => { loadBalances(); }, [loadBalances]);

  const containerStyle: React.CSSProperties = {
    position: 'fixed', inset: 0, zIndex: 10000,
    display: 'flex', flexDirection: 'column',
    background: '#0d1117', color: '#e6edf3',
    fontFamily: 'system-ui, -apple-system, sans-serif',
  };

  const headerStyle: React.CSSProperties = {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '16px 20px', borderBottom: '1px solid #21262d',
  };

  const totalUsd = balances.reduce((sum, b) => sum + (b.balanceUsd ?? 0), 0);

  // Send view - token selected
  if (view === 'send' && selectedBalance) {
    return (
      <div style={containerStyle}>
        <div style={headerStyle}>
          <button onClick={() => { setView('portfolio'); setSelectedToken(null); }} style={{ background: 'none', border: 'none', color: '#58a6ff', cursor: 'pointer', fontSize: 14 }}>← Back</button>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Send {selectedBalance.token.symbol}</h2>
          <div style={{ width: 60 }} />
        </div>
        <div style={{ padding: 20 }}>
          <p style={{ fontSize: 13, color: '#8b949e', marginBottom: 16 }}>Balance: {selectedBalance.balance} {selectedBalance.token.symbol}</p>
          <label style={{ fontSize: 12, color: '#8b949e', display: 'block', marginBottom: 4 }}>Recipient address</label>
          <input type="text" value={to} onChange={e => { setTo(e.target.value); setError(''); setSuccess(''); }}
            placeholder="0x... or ENS"
            style={{
              width: '100%', padding: 12, marginBottom: 16, boxSizing: 'border-box',
              background: '#0d1117', color: '#e6edf3', border: `1px solid ${error ? '#f85149' : '#30363d'}`,
              borderRadius: 8, fontSize: 14, fontFamily: 'monospace', outline: 'none',
            }} />
          <label style={{ fontSize: 12, color: '#8b949e', display: 'block', marginBottom: 4 }}>Amount</label>
          <input type="number" value={amount} onChange={e => { setAmount(e.target.value); setError(''); setSuccess(''); }}
            placeholder="0" min="0" step="1"
            style={{
              width: '100%', padding: 12, marginBottom: 16, boxSizing: 'border-box',
              background: '#0d1117', color: '#e6edf3', border: `1px solid ${error ? '#f85149' : '#30363d'}`,
              borderRadius: 8, fontSize: 14, outline: 'none',
            }} />
          {error && <p style={{ color: '#f85149', fontSize: 12, marginBottom: 12 }}>{error}</p>}
          {success && <p style={{ color: '#3fb950', fontSize: 12, marginBottom: 12 }}>{success}</p>}
          <button onClick={handleSend} style={{
            width: '100%', padding: 14, border: 'none', borderRadius: 8,
            background: '#1f6feb', color: '#fff', fontSize: 15, cursor: 'pointer',
            opacity: to && amount ? 1 : 0.5,
          }}>Send</button>
        </div>
      </div>
    );
  }

  // Receive view
  if (view === 'receive' && selectedBalance) {
    return (
      <div style={containerStyle}>
        <div style={headerStyle}>
          <button onClick={() => { setView('portfolio'); setSelectedToken(null); }} style={{ background: 'none', border: 'none', color: '#58a6ff', cursor: 'pointer', fontSize: 14 }}>← Back</button>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Receive {selectedBalance.token.symbol}</h2>
          <div style={{ width: 60 }} />
        </div>
        <div style={{ padding: 20, flex: 1, textAlign: 'center' }}>
          <p style={{ fontSize: 14, color: '#8b949e', marginBottom: 12 }}>
            {selectedBalance.token.icon} {selectedBalance.token.name} · {selectedBalance.token.chain}
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
            <WalletQrCode address={selectedBalance.address} size={180} />
          </div>
          <p style={{ fontSize: 11, color: '#8b949e', marginBottom: 6 }}>Address</p>
          <div
            onClick={() => {
              if (selectedBalance.address && selectedBalance.address !== 'unsupported') {
                navigator.clipboard.writeText(selectedBalance.address);
              }
            }}
            style={{
              background: '#161b22', border: '1px solid #30363d', borderRadius: 8,
              padding: 12, fontFamily: 'monospace', fontSize: 11, wordBreak: 'break-all',
              marginBottom: 16, cursor: 'pointer',
            }}>
            {selectedBalance.address || 'Unavailable'}
          </div>
          <button
            onClick={() => {
              if (selectedBalance.address && selectedBalance.address !== 'unsupported') {
                navigator.clipboard.writeText(selectedBalance.address);
              }
            }}
            style={{
              padding: '10px 20px', background: '#1f6feb', color: '#fff',
              border: 'none', borderRadius: 8, fontSize: 14, cursor: 'pointer',
            }}>
            Copy address
          </button>
        </div>
      </div>
    );
  }

  // Token detail view
  if (detailToken) {
    return (
      <div style={containerStyle}>
        <div style={headerStyle}>
          <button onClick={() => setDetailToken(null)} style={{ background: 'none', border: 'none', color: '#58a6ff', cursor: 'pointer', fontSize: 14 }}>← Back</button>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>{detailToken.token.symbol}</h2>
          <div style={{ width: 60 }} />
        </div>
        <div style={{ padding: 20 }}>
          <p style={{ fontSize: 14, color: '#8b949e', marginBottom: 16 }}>Balance: {detailToken.balance} {detailToken.token.symbol}</p>
          {detailToken.balanceUsd !== null && (
            <p style={{ fontSize: 14, marginBottom: 16 }}>≈ ${detailToken.balanceUsd.toFixed(2)}</p>
          )}
          <p style={{ fontSize: 11, color: '#8b949e', marginBottom: 6 }}>Address</p>
          <div style={{
            background: '#161b22', border: '1px solid #30363d', borderRadius: 8,
            padding: 12, fontFamily: 'monospace', fontSize: 11, wordBreak: 'break-all',
            marginBottom: 16,
          }}>
            {detailToken.address}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => navigator.clipboard.writeText(detailToken.address)} style={{
              flex: 1, padding: 12, background: '#1f6feb', color: '#fff',
              border: 'none', borderRadius: 8, fontSize: 14, cursor: 'pointer',
            }}>Copy address</button>
          </div>
        </div>
      </div>
    );
  }

  // History view
  if (view === 'history') {
    return <WalletTxHistory onClose={() => setView('portfolio')} />;
  }

  // ====== Portfolio (main view) ======
  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <h1 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Wallet</h1>
        <button onClick={onClose} style={{
          background: '#21262d', border: '1px solid #30363d', color: '#e6edf3',
          borderRadius: 6, padding: '6px 12px', cursor: 'pointer', fontSize: 12,
        }}>
          Close
        </button>
      </div>

      {error && (
        <div style={{ padding: '8px 16px', background: '#3d1515', color: '#f85149', fontSize: 12 }}>
          {error}
          <button onClick={loadBalances} style={{ marginLeft: 8, background: 'none', border: 'none', color: '#58a6ff', cursor: 'pointer', textDecoration: 'underline' }}>Retry</button>
        </div>
      )}

      <div style={{ padding: '16px 20px', borderBottom: '1px solid #21262d' }}>
        <p style={{ fontSize: 11, color: '#8b949e', margin: '0 0 4px' }}>Total balance</p>
        <p style={{ fontSize: 28, fontWeight: 700, margin: 0 }}>
          {loading ? '...' : `$${totalUsd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
        </p>
      </div>

      <div
        style={{ flex: 1, overflowY: 'auto', WebkitOverflowScrolling: 'touch' as any }}
        onTouchStart={(e) => {
          const el = e.currentTarget;
          const startScroll = el.scrollTop;
          const startY = e.touches[0].clientY;
          const onMove = (ev: TouchEvent) => {
            const pull = ev.touches[0].clientY - startY;
            if (startScroll === 0 && pull > 80) {
              el.removeEventListener('touchmove', onMove);
              el.removeEventListener('touchend', onEnd);
              loadBalances();
            }
          };
          const onEnd = () => {
            el.removeEventListener('touchmove', onMove);
            el.removeEventListener('touchend', onEnd);
          };
          el.addEventListener('touchmove', onMove, { passive: true });
          el.addEventListener('touchend', onEnd);
        }}
      >
        {loading && balances.length === 0 && (
          <div style={{ padding: 20 }}>
            {[1,2,3,4].map(i => (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', padding: '12px 0',
                borderBottom: '1px solid #161b22', gap: 12,
              }}>
                <div style={{ width: 36, height: 36, borderRadius: '50%', background: '#161b22' }} />
                <div style={{ flex: 1 }}>
                  <div style={{ width: 80, height: 14, background: '#161b22', borderRadius: 4, marginBottom: 6 }} />
                  <div style={{ width: 140, height: 11, background: '#161b22', borderRadius: 4 }} />
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ width: 60, height: 14, background: '#161b22', borderRadius: 4, marginBottom: 4, marginLeft: 'auto' }} />
                  <div style={{ width: 40, height: 11, background: '#161b22', borderRadius: 4, marginLeft: 'auto' }} />
                </div>
              </div>
            ))}
          </div>
        )}

        {balances.map((b) => (
          <div key={b.token.symbol} style={{
            display: 'flex', alignItems: 'center', padding: '12px 20px',
            borderBottom: '1px solid #161b22', cursor: 'pointer',
          }}
            onClick={() => {
                          if (b.token.symbol === 'ELEMENTAL') {
                            // ELEMENTAL is handled inline in portfolio view
                          } else {
                            setDetailToken(b);
                          }
                        }}>
            <div style={{
              width: 36, height: 36, borderRadius: '50%',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 16, background: '#161b22', marginRight: 12, flexShrink: 0,
            }}>
              {b.token.icon}
            </div>
            <div style={{ flex: 1 }}>
              <p style={{ margin: 0, fontSize: 14, fontWeight: 600 }}>{b.token.symbol}</p>
              <p style={{ margin: 0, fontSize: 11, color: '#8b949e' }}>{b.token.name}</p>
            </div>
            <div style={{ textAlign: 'right' }}>
              <p style={{ margin: 0, fontSize: 14, fontWeight: 500 }}>
                {formatBalance(b.balance, b.token.decimals)}
              </p>
              {b.balanceUsd !== null && (
                <p style={{ margin: 0, fontSize: 11, color: '#8b949e' }}>
                  ${b.balanceUsd.toFixed(2)}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>

      {!loading && balances.length > 0 && (
        <div style={{ display: 'flex', borderTop: '1px solid #21262d' }}>
          <button onClick={() => { setView('receive'); setSelectedToken(null); }} style={{
            flex: 1, padding: 14, background: 'none', border: 'none',
            color: '#e6edf3', fontSize: 14, cursor: 'pointer',
            borderRight: '1px solid #21262d',
          }}>
            Receive
          </button>
          <button onClick={() => { setView('send'); setSelectedToken(null); }} style={{
            flex: 1, padding: 14, background: 'none', border: 'none',
            color: '#e6edf3', fontSize: 14, cursor: 'pointer',
            borderRight: '1px solid #21262d',
          }}>
            Send
          </button>
          <button onClick={() => setView('history')} style={{
            flex: 1, padding: 14, background: 'none', border: 'none',
            color: '#e6edf3', fontSize: 14, cursor: 'pointer',
          }}>
            History
          </button>
        </div>
      )}
    </div>
  );
}