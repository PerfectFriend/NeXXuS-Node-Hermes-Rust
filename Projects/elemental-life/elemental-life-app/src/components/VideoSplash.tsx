import { useEffect, useRef, useState, useCallback } from 'react';
import { soundSystem } from '../sound/soundSystem';

interface Props {
  onComplete: () => void;
  imageSrc?: string;
}

export function VideoSplash({ onComplete, imageSrc = '/8b973c35-60ca-42a8-b896-9d435a0215e8.jpg' }: Props) {
  const [showImage, setShowImage] = useState(true);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [fadeOut, setFadeOut] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const transitionStarted = useRef(false);

  const handleTransition = useCallback(() => {
    if (transitionStarted.current) return;
    transitionStarted.current = true;
    soundSystem.play('transition', { volume: 0.5 });
    setFadeOut(true);
    timeoutRef.current = setTimeout(() => {
      setShowImage(false);
      setTimeout(() => onComplete(), 200);
    }, 500);
  }, [onComplete]);

  useEffect(() => {
    // Load sound system
    soundSystem.loadAll().then(() => {
      // Start ambient music
      soundSystem.play('ambient', { loop: true, volume: 0.3 });
    });
    
    // Auto-transition after 3 seconds
    timeoutRef.current = setTimeout(() => {
      handleTransition();
    }, 3000);
    
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      // Stop ambient on unmount
      soundSystem.stop('ambient');
    };
  }, [handleTransition]);

  if (!showImage) return null;

  return (
    <div
      className="image-splash"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10000,
        background: '#000',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'hidden',
        opacity: fadeOut ? 0 : 1,
        transition: 'opacity 0.5s ease-out',
      }}
      onClick={handleTransition}
    >
      <img
        src={imageSrc}
        alt="Elemental Life Intro"
        onLoad={() => setImageLoaded(true)}
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          opacity: imageLoaded ? 0.95 : 0,
          transition: 'opacity 0.3s ease',
        }}
      />
      
      {/* Title overlay */}
      <div
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          textAlign: 'center',
          zIndex: 10001,
          pointerEvents: 'none',
        }}
      >
        <h1 style={{
          fontSize: 'clamp(32px, 6vw, 64px)',
          fontWeight: 'bold',
          fontFamily: 'Georgia, serif',
          color: '#fff',
          textShadow: '0 0 30px rgba(0, 255, 180, 0.5)',
          margin: 0,
          letterSpacing: '2px',
        }}>
          Elemental Life
        </h1>
        <p style={{
          fontSize: 'clamp(14px, 2vw, 18px)',
          fontFamily: '"JetBrains Mono", monospace',
          color: 'rgba(180, 200, 255, 0.8)',
          marginTop: '16px',
          letterSpacing: '3px',
        }}>
          Cyberpunk Oasis
        </p>
      </div>

      {/* Tap to continue hint */}
      <div
        style={{
          position: 'absolute',
          bottom: '40px',
          left: '50%',
          transform: 'translateX(-50%)',
          zIndex: 10001,
          pointerEvents: 'none',
          animation: 'pulse 2s ease-in-out infinite',
        }}
      >
        <span style={{
          display: 'inline-block',
          padding: '10px 20px',
          background: 'rgba(0, 255, 180, 0.2)',
          border: '1px solid rgba(0, 255, 180, 0.5)',
          borderRadius: '20px',
          color: '#00ffb4',
          fontSize: '12px',
          fontFamily: '"JetBrains Mono", monospace',
          letterSpacing: '1px',
        }}>
          Tap to continue
        </span>
        <style>{`
          @keyframes pulse {
            0%, 100% { opacity: 0.6; transform: translateX(-50%) scale(1); }
            50% { opacity: 1; transform: translateX(-50%) scale(1.02); }
          }
        `}</style>
      </div>
    </div>
  );
}