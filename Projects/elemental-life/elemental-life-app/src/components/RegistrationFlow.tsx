/**
 * RegistrationFlow — упрощённый мастер регистрации пользователя.
 *
 * Шаги:
 * 1. ВВОД 3-5 СЛОВ — пользователь вводит слова (только буквы)
 * 2. ПОКАЗ 12-СЛОВНОЙ ФРАЗЫ — сгенерированная фраза для бэкапа + COPY
 * 3. ВЕРИФИКАЦИЯ — ввести 3 случайных слова из фразы
 * 4. ГОТОВО — создаём профиль
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { parseWords, validateWords, todayDate, wordsToEntropy, entropyToDisplayPhrase } from '../engine/crypto';

interface RegistrationFlowProps {
  onComplete: (data: RegistrationData) => void;
  onBack?: () => void;
}

export interface RegistrationData {
  /** 3-5 слов, введённых пользователем (исходная энтропия) */
  userWords: string[];
  /** 12-словная фраза для бэкапа (display only) */
  backupPhrase: string[];
  /** Дата регистрации YYYY-MM-DD */
  regDate: string;
}

type Step = 'input' | 'phrase' | 'verify' | 'done';

export function RegistrationFlow({ onComplete, onBack }: RegistrationFlowProps) {
  const [step, setStep] = useState<Step>('input');
  const [error, setError] = useState('');
  const [wordsInput, setWordsInput] = useState('');
  const [backupPhrase, setBackupPhrase] = useState<string[]>([]);
  const [regDate, setRegDate] = useState('');
  const [copied, setCopied] = useState(false);

  // Верификация
  const [verifyWords, setVerifyWords] = useState<number[]>([]);
  const [verifyInputs, setVerifyInputs] = useState<string[]>([]);

  // 10-second delay before "I've saved it" button activates
  const [saveDelayElapsed, setSaveDelayElapsed] = useState(false);
  const [countdown, setCountdown] = useState(10);
  const delayTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const countdownIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startSaveDelay = useCallback(() => {
    setSaveDelayElapsed(false);
    setCountdown(10);
    if (delayTimerRef.current) clearTimeout(delayTimerRef.current);
    if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
    delayTimerRef.current = setTimeout(() => {
      setSaveDelayElapsed(true);
      setCountdown(0);
      if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
    }, 10000);
    countdownIntervalRef.current = setInterval(() => {
      setCountdown(prev => Math.max(0, prev - 1));
    }, 1000);
  }, []);

  const inputRef = useRef<HTMLInputElement>(null);
  const completeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cleanup таймеров при размонтировании
  useEffect(() => {
    return () => {
      if (completeTimerRef.current) clearTimeout(completeTimerRef.current);
      if (delayTimerRef.current) clearTimeout(delayTimerRef.current);
      if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current);
    };
  }, []);

  // Фокус на поле ввода при переходе на verify
  useEffect(() => { if (step === 'verify') inputRef.current?.focus(); }, [step]);

  // ====== Шаг 1: Ввод 3-5 слов ======

  const handleSubmitWords = useCallback(async () => {
    const words = parseWords(wordsInput);
    const err = validateWords(words);
    if (err) { setError(err); return; }
    setError('');

    try {
      const date = todayDate();
      setRegDate(date);
      const entropy = wordsToEntropy(words, date);
      const phrase = entropyToDisplayPhrase(entropy);
      setBackupPhrase(phrase);
      setStep('phrase');
      startSaveDelay();
    } catch (e) {
      setError('Generation error: ' + (e instanceof Error ? e.message : String(e)));
    }
  }, [wordsInput, startSaveDelay]);

  // ====== Шаг 2: Показ фразы ======

  const handleCopyPhrase = useCallback(() => {
    navigator.clipboard.writeText(backupPhrase.join(' ')).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {
      // fallback
      const ta = document.createElement('textarea');
      ta.value = backupPhrase.join(' ');
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [backupPhrase]);

  const handlePhraseNext = useCallback(() => {
      // Выбираем 3 случайных слова для верификации
      const indices = new Set<number>();
      while (indices.size < 3) {
        indices.add(Math.floor(Math.random() * 12));
      }
      setVerifyWords(Array.from(indices).sort((a, b) => a - b));
      setVerifyInputs([]);
      setStep('verify');
    }, []);

  // ====== Шаг 3: Верификация ======

  const handleVerifySubmit = useCallback(() => {
    const allCorrect = verifyWords.every(
      (idx, i) => verifyInputs[i]?.toLowerCase().trim() === backupPhrase[idx]
    );
    if (!allCorrect) {
      setError('Not all words matched. Try again.');
      // Сбрасываем ввод
      setVerifyInputs([]);
      setTimeout(() => inputRef.current?.focus(), 100);
      return;
    }
    setError('');

    // Все шаги пройдены!
    const data: RegistrationData = {
      userWords: parseWords(wordsInput),
      backupPhrase,
      regDate,
    };
    setStep('done');
    completeTimerRef.current = setTimeout(() => onComplete(data), 300);
  }, [verifyWords, verifyInputs, backupPhrase, wordsInput, regDate, onComplete]);

  // ====== Render ======

  const containerStyle: React.CSSProperties = {
    position: 'fixed', inset: 0, zIndex: 9999, overflowY: 'auto',
    display: 'flex', flexDirection: 'column',
    background: '#0d1117', color: '#e6edf3',
    fontFamily: 'system-ui, -apple-system, sans-serif',
    padding: 20,
  };

  const cardStyle: React.CSSProperties = {
    maxWidth: 440, width: '100%', margin: 'auto',
    background: '#161b22', border: '1px solid #30363d',
    borderRadius: 12, padding: 20,
  };

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '10px 12px',
    border: `1px solid ${error ? '#ff5a36' : '#30363d'}`,
    borderRadius: 8, background: '#0d1117', color: '#e6edf3',
    fontSize: '0.9rem', outline: 'none', boxSizing: 'border-box',
    fontFamily: 'system-ui, sans-serif',
  };

  const btnPrimary: React.CSSProperties = {
    padding: '10px 20px', border: '2px solid #238636', borderRadius: 8,
    background: '#238636', color: '#fff', fontSize: '0.85rem',
    fontWeight: 600, cursor: 'pointer', width: '100%',
  };

  const btnSecondary: React.CSSProperties = {
    padding: '8px 16px', border: '1px solid #30363d', borderRadius: 8,
    background: 'transparent', color: '#e6edf3', fontSize: '0.8rem',
    cursor: 'pointer',
  };

  const stepIndicator = (current: Step) => {
    const steps: { id: Step; label: string }[] = [
      { id: 'input', label: 'Words' },
      { id: 'phrase', label: 'Backup' },
      { id: 'verify', label: 'Verify' },
    ];
    const currentIdx = steps.findIndex(s => s.id === current);
    return (
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, justifyContent: 'center' }}>
        {steps.map((s, i) => (
          <div key={s.id} style={{
            flex: 1, height: 3, borderRadius: 2,
            background: i <= currentIdx ? '#238636' : '#21262d',
            transition: 'background 0.3s',
          }} />
        ))}
      </div>
    );
  };

  return (
    <div style={containerStyle}>
      <div style={cardStyle}>
        {stepIndicator(step)}

        {/* ===== Шаг 1: Ввод 3-5 слов ===== */}
        {step === 'input' && (
          <div style={{ animation: 'fadeIn 0.3s ease' }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: '0 0 8px' }}>
              Create your master seed
            </h2>
            <p style={{ fontSize: '0.7rem', color: '#8b949e', margin: '0 0 16px', lineHeight: 1.5 }}>
              Enter 3–5 words (letters only, max 16 chars each). Combined with
              today's date ({todayDate()}) they generate your recovery phrase.
            </p>
            <input
              ref={inputRef}
              type="text" value={wordsInput}
              onChange={(e) => { setWordsInput(e.target.value); setError(''); }}
              onKeyDown={(e) => { if (e.key === 'Enter') handleSubmitWords(); }}
              placeholder="sky earth fire water wind"
              autoFocus
              style={inputStyle}
            />
            {error && <p style={{ fontSize: '0.7rem', color: '#ff5a36', margin: '8px 0' }}>{error}</p>}
            <p style={{ fontSize: '0.65rem', color: '#484f58', marginTop: 8 }}>
              Words: {parseWords(wordsInput).length} / 3–5
            </p>
            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              {onBack && <button onClick={onBack} style={btnSecondary}>← Back</button>}
              <button onClick={handleSubmitWords} style={{
                ...btnPrimary,
                opacity: parseWords(wordsInput).length >= 3 ? 1 : 0.5,
                cursor: parseWords(wordsInput).length >= 3 ? 'pointer' : 'default',
              }}>
                Generate recovery phrase →
              </button>
            </div>
          </div>
        )}

        {/* ===== Шаг 2: Показ 12 слов ===== */}
        {step === 'phrase' && (
          <div style={{ animation: 'fadeIn 0.3s ease' }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: '0 0 8px', color: '#f0883e' }}>
              Recovery phrase
            </h2>
            <p style={{ fontSize: '0.7rem', color: '#ff5a36', margin: '0 0 12px', lineHeight: 1.4, fontWeight: 500 }}>
              Write down these 12 words in order. Keep them offline and secure.
              This is the ONLY way to recover your profile.
            </p>

            <div style={{
              display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6,
              background: '#0d1117', border: '1px solid #30363d',
              borderRadius: 8, padding: 16, marginBottom: 12,
            }}>
              {backupPhrase.map((word, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 4,
                  fontSize: '0.85rem', fontFamily: 'ui-monospace, monospace',
                  color: '#e6edf3', padding: '3px 0',
                }}>
                  <span style={{ color: '#484f58', minWidth: 16, fontSize: '0.7rem' }}>{i + 1}</span>
                  <span style={{ fontWeight: 500 }}>{word}</span>
                </div>
              ))}
            </div>

            <button onClick={handleCopyPhrase} style={{
              ...btnPrimary, marginBottom: 6, background: '#1f6feb', borderColor: '#1f6feb',
            }}>
              {copied ? 'Copied' : 'Copy to clipboard'}
            </button>

            <p style={{ fontSize: '0.65rem', color: '#484f58', marginBottom: 8, textAlign: 'center' }}>
              {saveDelayElapsed ? 'You can proceed below' : `Wait ${countdown}s before confirming`}
            </p>

            <button
              onClick={handlePhraseNext}
              disabled={!saveDelayElapsed}
              style={{
                ...btnPrimary,
                opacity: saveDelayElapsed ? 1 : 0.4,
                cursor: saveDelayElapsed ? 'pointer' : 'not-allowed',
              }}
            >
              I have saved my recovery phrase
            </button>
          </div>
        )}

        {/* ===== Шаг 3: Верификация ===== */}
        {step === 'verify' && (
          <div style={{ animation: 'fadeIn 0.3s ease' }}>
            <h2 style={{ fontSize: '1rem', fontWeight: 600, margin: '0 0 8px' }}>
              Verify recovery phrase
            </h2>
            <p style={{ fontSize: '0.7rem', color: '#8b949e', margin: '0 0 16px', lineHeight: 1.5 }}>
              Enter words #{verifyWords.map(i => i + 1).join(', ')} from your phrase:
            </p>

            {verifyWords.map((wordIdx, i) => (
              <div key={i} style={{ marginBottom: 10 }}>
                <label style={{ fontSize: '0.7rem', color: '#8b949e', display: 'block', marginBottom: 4 }}>
                  Word #{wordIdx + 1}:
                </label>
                <input
                  ref={i === 0 ? inputRef : undefined}
                  type="text"
                  value={verifyInputs[i] || ''}
                  onChange={(e) => {
                    const next = [...verifyInputs];
                    next[i] = e.target.value;
                    setVerifyInputs(next);
                    setError('');
                  }}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleVerifySubmit(); }}
                  placeholder="enter word"
                  autoComplete="off"
                  style={inputStyle}
                />
              </div>
            ))}

            {error && <p style={{ fontSize: '0.7rem', color: '#ff5a36', margin: '0 0 8px' }}>{error}</p>}

            <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
              <button onClick={() => setStep('phrase')} style={btnSecondary}>← Back</button>
              <button onClick={handleVerifySubmit} style={btnPrimary}>
                Verify
              </button>
            </div>
          </div>
        )}

        {/* ===== Шаг 4: Готово ===== */}
        {step === 'done' && (
          <div style={{ animation: 'fadeIn 0.3s ease', textAlign: 'center', padding: '20px 0' }}>
            <div style={{ fontSize: '3rem', marginBottom: 12 }}>✅</div>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 600, margin: '0 0 8px' }}>
              Profile Created
            </h2>
            <p style={{ fontSize: '0.8rem', color: '#8b949e', margin: 0 }}>
              Your elemental identity is ready. Starting game...
            </p>
          </div>
        )}
      </div>
          </div>
        );
      }