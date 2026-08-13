import { useEffect, useState } from 'react';

type ToastType = 'info' | 'success' | 'error';

interface ToastMessage {
  id: number;
  text: string;
  type: ToastType;
}

let toastId = 0;
let addToastFn: ((text: string, type?: ToastType) => void) | null = null;

export function showToast(text: string, type: ToastType = 'info') {
  addToastFn?.(text, type);
}

export function ToastContainer() {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  useEffect(() => {
    addToastFn = (text: string, type: ToastType = 'info') => {
      const id = ++toastId;
      setToasts(prev => [...prev, { id, text, type }]);
      setTimeout(() => {
        setToasts(prev => prev.filter(t => t.id !== id));
      }, 3000);
    };
    return () => { addToastFn = null; };
  }, []);

  const colors: Record<ToastType, string> = {
    info: '#1f6feb',
    success: '#238636',
    error: '#da3633',
  };

  return (
    <div style={{
      position: 'fixed', bottom: 80, left: '50%', transform: 'translateX(-50%)',
      zIndex: 99999, display: 'flex', flexDirection: 'column', gap: 6,
      pointerEvents: 'none',
    }}>
      {toasts.map(t => (
        <div key={t.id} style={{
          padding: '10px 18px', borderRadius: 10, background: colors[t.type],
          color: '#fff', fontSize: 13, fontWeight: 500, whiteSpace: 'nowrap',
          boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
          animation: 'toastSlideUp 0.25s ease-out',
          pointerEvents: 'auto',
        }}>
          {t.text}
        </div>
      ))}
    </div>
  );
}
