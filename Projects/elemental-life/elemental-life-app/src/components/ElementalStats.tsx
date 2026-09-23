import { useState, useEffect } from 'react';
import { getElementalStats, sendElemental } from '../wallet/elemental';
import { WalletQrCode } from './WalletQrCode';

interface ElementalStatsProps {
  onClose: () => void;
}

type View = 'stats' | 'send' | 'receive';

export function ElementalStats({ onClose }: ElementalStatsProps) {
  const [view, setView] = useState<View>('stats');
  const [stats, setStats] = useState(getElementalStats());
  const [to, setTo] = useState('');
  const [amount, setAmount] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [copied, setCopied] = useState(false);

  // ELEMENTAL is internal - no external wallet address needed
  // Users share their 3-5 words + date to receive ELEMENTAL

  useEffect(() => {
    setStats(getElementalStats());
  }, []);

  const refresh = () => setStats(getElementalStats());

  const handleSend = () => {
    setError('');
    setSuccess('');
    const numAmount = parseInt(amount);
    if (!to) { setError('Enter recipient address'); return; }
    if (!amount || isNaN(numAmount) || numAmount <= 0) { setError('Enter a valid amount'); return; }
    if (numAmount > stats.balance) { setError('Insufficient balance'); return; }
    const ok = sendElemental(to, numAmount, `Sent to ${to.slice(0, 8)}...`);
    if (ok) {
      setSuccess(`Sent ${numAmount} ELEMENTAL`);
      setAmount('');
      setTo('');
      refresh();
    } else {
      setError('Send failed');
    }
  };

  const handleCopy = async () => {
    // Copy the backup phrase for receiving (not a wallet address)
    const profile = JSON.parse(localStorage.getItem('el_profile') || '{}');
    const shareText = `${profile.backupPhrase?.join(' ') || ''} | ${profile.createdDate || ''}`;
    await navigator.clipboard.writeText(shareText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const containerStyle: React.CSSProperties = {
    position: 'fixed', inset: 0, zIndex: 10002,
    display: 'flex', flexDirection: 'column',
    background: '#0d1117', color: '#e6edf3',
    fontFamily: 'system-ui, -apple-system, sans-serif',
  };

  const headerStyle: React.CSSProperties = {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '16px 20px', borderBottom: '1px solid #21262d',
  };

  if (view === 'send') {
    return (
      <div style={containerStyle}>
        <div style={headerStyle}>
          <button onClick={() => setView('stats')} style={{ background: 'none', border: 'none', color: '#58a6ff', cursor: 'pointer', fontSize: 14 }}>← Back</button>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Send ELEMENTAL</h2>
          <div style={{ width: 60 }} />
        </div>
        <div style={{ padding: 20 }}>
          <p style={{ fontSize: 13, color: '#8b949e', marginBottom: 16 }}>Balance: {stats.balance} ELEMENTAL</p>
          <label style={{ fontSize: 12, color: '#8b949e', display: 'block', marginBottom: 4 }}>Recipient address (or their words)</label>
          <input type="text" value={to} onChange={e => { setTo(e.target.value); setError(''); setSuccess(''); }}
            placeholder="recipient identifier"
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

  if (view === 'receive') {
    const profile = JSON.parse(localStorage.getItem('el_profile') || '{}');
    const shareText = `${profile.backupPhrase?.join(' ') || ''} | ${profile.createdDate || ''}`;

    return (
      <div style={containerStyle}>
        <div style={headerStyle}>
          <button onClick={() => setView('stats')} style={{ background: 'none', border: 'none', color: '#58a6ff', cursor: 'pointer', fontSize: 14 }}>← Back</button>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Receive ELEMENTAL</h2>
          <div style={{ width: 60 }} />
        </div>
        <div style={{ padding: 20, textAlign: 'center', flex: 1 }}>
          <p style={{ fontSize: 12, color: '#8b949e', marginBottom: 16 }}>
            Share your backup phrase to receive ELEMENTAL
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
            <WalletQrCode address={shareText} size={200} />
          </div>
          <p style={{ fontSize: 11, color: '#8b949e', marginBottom: 6 }}>Your backup phrase</p>
          <div
            onClick={handleCopy}
            style={{
              background: '#161b22', border: '1px solid #30363d', borderRadius: 8,
              padding: 12, marginBottom: 16, cursor: 'pointer',
            }}>
            <p style={{ margin: 0, fontFamily: 'monospace', fontSize: 11, wordBreak: 'break-all' }}>
              {shareText}
            </p>
          </div>
          <button onClick={handleCopy} style={{
            padding: '10px 24px', background: '#1f6feb', color: '#fff',
            border: 'none', borderRadius: 8, fontSize: 14, cursor: 'pointer',
          }}>
            {copied ? 'Copied!' : 'Copy phrase'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#58a6ff', cursor: 'pointer', fontSize: 14 }}>← Back</button>
        <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>ELEMENTAL</h2>
        <div style={{ width: 60 }} />
      </div>
      <div style={{ padding: '20px 20px 0' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ fontSize: 40, marginBottom: 4 }}>⬡</div>
          <p style={{ fontSize: 11, color: '#8b949e', margin: '0 0 4px' }}>Balance</p>
          <p style={{ fontSize: 36, fontWeight: 700, margin: 0 }}>{stats.balance}</p>
          <p style={{ fontSize: 11, color: '#484f58', margin: '4px 0 0' }}>ELEMENTAL</p>
        </div>

        <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
          <button onClick={() => setView('send')} style={{
            flex: 1, padding: 12, background: '#1f6feb', border: 'none',
            borderRadius: 8, color: '#fff', fontSize: 14, cursor: 'pointer',
          }}>Send</button>
          <button onClick={() => setView('receive')} style={{
            flex: 1, padding: 12, background: '#21262d', border: '1px solid #30363d',
            borderRadius: 8, color: '#e6edf3', fontSize: 14, cursor: 'pointer',
          }}>Receive</button>
        </div>

        <div style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
          {[
            { label: 'Mined', value: stats.totalMined, color: '#3fb950' },
            { label: 'Sent', value: stats.totalSent, color: '#f85149' },
            { label: 'Received', value: stats.totalReceived, color: '#58a6ff' },
          ].map(item => (
                      <div key={item.label} style={{
                        flex: 1, padding: 10, background: '#161b22', borderRadius: 8, textAlign: 'center',
                      }}>
                        <p style={{ fontSize: 10, color: '#8b949e', margin: '0 0 2px' }}>{item.label}</p>
                        <p style={{ fontSize: 16, fontWeight: 700, margin: 0, color: item.color }}>{item.value}</p>
                      </div>
                    ))}
        </div>

        <p style={{ fontSize: 12, fontWeight: 600, margin: '0 0 8px' }}>History</p>
        {stats.history.length === 0 && (
          <p style={{ fontSize: 11, color: '#484f58' }}>No activity yet. Complete levels to earn ELEMENTAL.</p>
        )}
        <div style={{ flex: 1, overflowY: 'auto', maxHeight: 240 }}>
          {[...stats.history].reverse().map((entry, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '8px 0', borderBottom: '1px solid #161b22',
            }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ margin: 0, fontSize: 11, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {entry.reason}
                </p>
                <p style={{ margin: 0, fontSize: 10, color: '#484f58' }}>
                  {new Date(entry.ts).toLocaleString()}
                </p>
              </div>
              <span style={{
                fontSize: 13, fontWeight: 600, flexShrink: 0, marginLeft: 8,
                color: entry.amount > 0 ? '#3fb950' : '#f85149',
              }}>
                {entry.amount > 0 ? '+' : ''}{entry.amount}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}