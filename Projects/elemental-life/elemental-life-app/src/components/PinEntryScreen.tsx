/**
 * PinEntryScreen — упрощённый экран восстановления профиля.
 *
 * Вместо PIN: пользователь вводит свои 3-5 слов + дата (опционально).
 * Если профиль существует — восстанавливает его.
 * Если нет — предлагает создать новый.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { parseWords, validateWords, todayDate } from '../engine/crypto';
import { useIdentity } from '../hooks/useIdentity';

interface PinEntryScreenProps {
  onPinOk: () => void;
  onNewRegistration: () => void;
}

type PinState = 'entry' | 'not_found';

export function PinEntryScreen({ onPinOk, onNewRegistration }: PinEntryScreenProps) {
  const [state, setState] = useState<PinState>('entry');
  const [wordsInput, setWordsInput] = useState('');
  const [dateInput, setDateInput] = useState('');
  const [error, setError] = useState('');
  const [syncing, setSyncing] = useState(false);

  const { profile, restoreIdentity, clearIdentity } = useIdentity();

  const inputRef = useRef<HTMLInputElement>(null);

  // Фокус на поле ввода
  useEffect(() => { inputRef.current?.focus(); }, []);

  // При входе проверяем, есть ли профиль
  useEffect(() => {
    if (!profile) {
      // Профиля нет — сразу к созданию
      setState('entry');
    }
  }, [profile]);

  const handleSubmitWords = useCallback(async () => {
    const words = parseWords(wordsInput);
    const err = validateWords(words);
    if (err) { setError(err); return; }
    setError('');

    setSyncing(true);
    try {
      const date = dateInput || todayDate();
      // Try to restore existing profile
      const restored = await restoreIdentity(words, date);
      if (restored) {
        onPinOk();
        return;
      }
      // Profile not found with these words
      setError('Profile not found with these words. Check words and date, or create new.');
      setState('not_found');
    } catch (e) {
      setError('Error: ' + (e instanceof Error ? e.message : String(e)));
    } finally {
      setSyncing(false);
    }
  }, [wordsInput, dateInput, restoreIdentity, onPinOk]);

  const handleCreateNew = useCallback(() => {
    clearIdentity();
    onNewRegistration();
  }, [clearIdentity, onNewRegistration]);

  // ====== Style ======
  const containerStyle: React.CSSProperties = {
    position: 'fixed', inset: 0, zIndex: 9999, overflowY: 'auto',
    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
    background: '#0d1117', color: '#e6edf3',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    padding: 20,
  };

  const cardStyle: React.CSSProperties = {
    width: '100%', maxWidth: 400,
    background: '#161b22', borderRadius: 12, padding: 24,
    border: '1px solid #30363d',
  };

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '12px 14px',
    border: `1px solid ${error ? '#ff5a36' : '#30363d'}`,
    borderRadius: 8, background: '#0d1117', color: '#e6edf3',
    fontSize: '1rem', outline: 'none', boxSizing: 'border-box',
    fontFamily: 'system-ui, sans-serif',
  };

  const btnPrimary: React.CSSProperties = {
    padding: '12px 24px', border: 'none', borderRadius: 8,
    background: '#238636', color: '#fff', fontSize: '1rem',
    fontWeight: 600, cursor: 'pointer', width: '100%',
  };

  const btnSecondary: React.CSSProperties = {
    padding: '10px 20px', border: '1px solid #30363d', borderRadius: 8,
    background: 'transparent', color: '#e6edf3', fontSize: '0.9rem',
    cursor: 'pointer', width: '100%',
  };

  const btnDanger: React.CSSProperties = {
    padding: '10px 20px', border: '1px solid #da3633', borderRadius: 8,
    background: 'transparent', color: '#f85149', fontSize: '0.9rem',
    cursor: 'pointer', width: '100%',
  };

  return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        {/* ===== STATE: ENTRY ===== */}
        {state === 'entry' && (
          <div style={{ animation: 'fadeIn 0.3s ease' }}>
            <h1 style={{ fontSize: '1.3rem', fontWeight: 600, margin: '0 0 4px', textAlign: 'center' }}>
              Restore Profile
            </h1>
            <p style={{ fontSize: '0.8rem', color: '#8b949e', marginBottom: 24, textAlign: 'center' }}>
              Enter your 3–5 words to restore your elemental identity
            </p>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', color: '#8b949e' }}>
                Words (3–5, letters only)
              </label>
              <input
                ref={inputRef}
                type="text" value={wordsInput}
                onChange={(e) => { setWordsInput(e.target.value); setError(''); }}
                onKeyDown={(e) => { if (e.key === 'Enter') handleSubmitWords(); }}
                placeholder="sky earth fire water wind"
                autoFocus
                style={inputStyle}
              />
            </div>

            <div style={{ marginBottom: 20 }}>
              <label style={{ display: 'block', marginBottom: 6, fontSize: '0.8rem', color: '#8b949e' }}>
                Date (YYYY-MM-DD, optional — defaults to today)
              </label>
              <input
                type="text" value={dateInput}
                onChange={(e) => { setDateInput(e.target.value); setError(''); }}
                onKeyDown={(e) => { if (e.key === 'Enter') handleSubmitWords(); }}
                placeholder={todayDate()}
                style={inputStyle}
              />
            </div>

            {error && <p style={{ fontSize: '0.8rem', color: '#ff5a36', margin: '0 0 16px', textAlign: 'center' }}>{error}</p>}

            <button onClick={handleSubmitWords} disabled={syncing} style={{
              ...btnPrimary, opacity: syncing ? 0.6 : 1, cursor: syncing ? 'not-allowed' : 'pointer',
            }}>
              {syncing ? 'Restoring...' : 'Restore Profile'}
            </button>

            <p style={{ fontSize: '0.75rem', color: '#484f58', marginTop: 16, textAlign: 'center' }}>
              Don't have a profile?{' '}
              <button onClick={handleCreateNew} style={{ background: 'none', border: 'none', color: '#58a6ff', cursor: 'pointer', fontSize: '0.75rem' }}>
                Create new
              </button>
            </p>
          </div>
        )}

        {/* ===== STATE: NOT FOUND ===== */}
        {state === 'not_found' && (
          <div style={{ animation: 'fadeIn 0.3s ease', textAlign: 'center' }}>
            <div style={{ fontSize: '3rem', marginBottom: 12 }}>🔍</div>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 600, margin: '0 0 8px', color: '#f85149' }}>
              Profile Not Found
            </h2>
            <p style={{ fontSize: '0.85rem', color: '#8b949e', margin: '0 0 20px', lineHeight: 1.5 }}>
              No profile matches those words and date.<br/>
              Check your backup phrase or create a new profile.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <button onClick={() => { setState('entry'); setError(''); setWordsInput(''); }} style={btnSecondary}>
                Try Different Words
              </button>
              <button onClick={handleCreateNew} style={btnDanger}>
                Create New Profile
              </button>
            </div>
          </div>
        )}
      </div>
          </div>
        );
      }