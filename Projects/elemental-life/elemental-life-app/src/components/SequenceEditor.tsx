import { useState } from 'react';

type SequenceElement = 'FIRE' | 'WATER' | 'EARTH' | 'EMPTY';

const VALID_ELEMENTS: SequenceElement[] = ['FIRE', 'WATER', 'EARTH', 'EMPTY'];

const ELEM_LABELS: Record<SequenceElement, { icon: string; label: string }> = {
  FIRE: { icon: '🔥', label: 'Fire' },
  WATER: { icon: '💧', label: 'Water' },
  EARTH: { icon: '⛰️', label: 'Earth' },
  EMPTY: { icon: '⬜', label: 'Empty' },
};

const STORAGE_KEY = 'el_elemental_sequence';

function getStoredSequence(): SequenceElement[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return [];
}

function setStoredSequence(seq: SequenceElement[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(seq));
}

interface SequenceEditorProps {
  onClose: () => void;
}

export function SequenceEditor({ onClose }: SequenceEditorProps) {
  const [seq, setSeq] = useState<SequenceElement[]>(getStoredSequence());
  const [confirmSeq, setConfirmSeq] = useState<SequenceElement[]>([]);
  const [step, setStep] = useState<'set' | 'confirm' | 'done'>('set');
  const [error, setError] = useState('');

  const addElement = (el: SequenceElement) => {
    setError('');
    if (step === 'set') {
      setSeq(prev => {
        const next = [...prev, el];
        if (next.length > 8) return prev;
        return next;
      });
    } else if (step === 'confirm') {
      setConfirmSeq(prev => {
        const next = [...prev, el];
        return next;
      });
    }
  };

  const removeLast = () => {
    setError('');
    if (step === 'set') setSeq(prev => prev.slice(0, -1));
    else if (step === 'confirm') setConfirmSeq(prev => prev.slice(0, -1));
  };

  const startConfirm = () => {
    if (seq.length < 3) { setError('At least 3 elements required'); return; }
    setConfirmSeq([]);
    setStep('confirm');
    setError('');
  };

  const finishConfirm = () => {
    if (confirmSeq.length !== seq.length || !confirmSeq.every((e, i) => e === seq[i])) {
      setError('Sequences do not match');
      setConfirmSeq([]);
      setStep('set');
      return;
    }
    setStoredSequence(seq);
    setStep('done');
  };

  const containerStyle: React.CSSProperties = {
    position: 'fixed', inset: 0, zIndex: 9999,
    display: 'flex', flexDirection: 'column',
    background: '#0d1117', color: '#e6edf3',
    fontFamily: 'system-ui, -apple-system, sans-serif',
  };

  const headerStyle: React.CSSProperties = {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '16px 20px', borderBottom: '1px solid #21262d',
  };

  const renderSeq = (elements: SequenceElement[], label: string) => (
    <div style={{ marginBottom: 16 }}>
      <p style={{ fontSize: 12, color: '#8b949e', margin: '0 0 8px' }}>{label}</p>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', minHeight: 40, padding: 8, background: '#161b22', borderRadius: 8, border: '1px solid #30363d' }}>
        {elements.length === 0 && <span style={{ color: '#484f58', fontSize: 12 }}>Tap elements below</span>}
        {elements.map((e, i) => (
          <span key={i} style={{
            padding: '4px 10px', background: '#21262d', borderRadius: 6,
            fontSize: 14, border: '1px solid #30363d',
          }}>
            {ELEM_LABELS[e].icon} {ELEM_LABELS[e].label}
          </span>
        ))}
      </div>
    </div>
  );

  if (step === 'done') {
    return (
      <div style={containerStyle}>
        <div style={headerStyle}>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#58a6ff', cursor: 'pointer', fontSize: 14 }}>← Back</button>
          <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Change PIN</h2>
          <div style={{ width: 60 }} />
        </div>
        <div style={{ padding: 40, textAlign: 'center', flex: 1 }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>✓</div>
          <p style={{ fontSize: 16, color: '#3fb950', marginBottom: 8 }}>PIN changed successfully</p>
          <p style={{ fontSize: 12, color: '#8b949e', marginBottom: 24 }}>
            Remember your new element sequence
          </p>
          <div style={{ display: 'flex', gap: 6, justifyContent: 'center', flexWrap: 'wrap', marginBottom: 24 }}>
            {seq.map((e, i) => (
              <span key={i} style={{
                padding: '6px 12px', background: '#21262d', borderRadius: 6, fontSize: 16,
              }}>
                {ELEM_LABELS[e].icon}
              </span>
            ))}
          </div>
          <button onClick={onClose} style={{
            padding: '12px 24px', background: '#1f6feb', color: '#fff',
            border: 'none', borderRadius: 8, fontSize: 14, cursor: 'pointer',
          }}>
            Done
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#58a6ff', cursor: 'pointer', fontSize: 14 }}>← Back</button>
        <h2 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>
          {step === 'set' ? 'Set new PIN' : 'Confirm PIN'}
        </h2>
        <div style={{ width: 60 }} />
      </div>

      <div style={{ padding: 20, flex: 1, overflowY: 'auto' }}>
        {step === 'set' ? renderSeq(seq, 'Your new sequence (min 3 elements)') : renderSeq(confirmSeq, `Re-enter the ${seq.length} elements to confirm`)}

        {error && <p style={{ color: '#f85149', fontSize: 12, marginBottom: 12 }}>{error}</p>}

        {/* Element buttons */}
        <p style={{ fontSize: 12, color: '#8b949e', margin: '0 0 8px' }}>
          {step === 'set' ? 'Choose elements:' : 'Re-enter your sequence:'}
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
          {VALID_ELEMENTS.map(el => (
            <button key={el} onClick={() => addElement(el)} style={{
              flex: 1, minWidth: 60, padding: '10px 8px', background: '#21262d',
              border: '1px solid #30363d', borderRadius: 8, color: '#e6edf3',
              fontSize: 13, cursor: 'pointer', textAlign: 'center',
            }}>
              <span style={{ fontSize: 18, display: 'block', marginBottom: 2 }}>{ELEM_LABELS[el].icon}</span>
              {ELEM_LABELS[el].label}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={removeLast} style={{
            flex: 1, padding: 10, background: '#21262d', border: '1px solid #30363d',
            borderRadius: 8, color: '#e6edf3', fontSize: 13, cursor: 'pointer',
          }}>
            ← Delete last
          </button>
          {step === 'set' ? (
            <button onClick={startConfirm} style={{
              flex: 1, padding: 10, background: '#1f6feb', border: 'none',
              borderRadius: 8, color: '#fff', fontSize: 13, cursor: 'pointer',
            }}>
              Continue →
            </button>
          ) : (
            <button onClick={finishConfirm} style={{
              flex: 1, padding: 10, background: '#238636', border: 'none',
              borderRadius: 8, color: '#fff', fontSize: 13, cursor: 'pointer',
            }}>
              Confirm
            </button>
          )}
        </div>
      </div>
    </div>
  );
}