import { useEffect, useRef, useState, useCallback } from 'react';
import { soundSystem } from '../sound/soundSystem';

interface Props {
  onComplete: () => void;
  imageSrc?: string;
}

export function LoadingSplash({ onComplete, imageSrc = '/8b973c35-60ca-42a8-b896-9d435a0215e8.jpg' }: Props) {
  const [progress, setProgress] = useState(0);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [fadeOut, setFadeOut] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const progressIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const transitionStarted = useRef(false);

  const handleTransition = useCallback(() => {
    if (transitionStarted.current) return;
    transitionStarted.current = true;
    soundSystem.play('transition', { volume: 0.5 });
    setFadeOut(true);
    
    if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    
    timeoutRef.current = setTimeout(() => {
      setTimeout(() => onComplete(), 200);
    }, 500);
  }, [onComplete]);

  useEffect(() => {
    // Load sound system and start ambient
    soundSystem.loadAll().then(() => {
      soundSystem.play('ambient', { loop: true, volume: 0.3 });
    });

    // Simulate resource loading progress
    let currentProgress = 0;
    progressIntervalRef.current = setInterval(() => {
      currentProgress += Math.random() * 8 + 2;
      if (currentProgress >= 90) {
        currentProgress = 90;
        clearInterval(progressIntervalRef.current!);
      }
      setProgress(currentProgress);
    }, 150);

    // Wait for image load + minimum time
    const minTimePromise = new Promise(resolve => setTimeout(resolve, 2000));
    const imagePromise = new Promise(resolve => {
      const img = new Image();
      img.onload = resolve;
      img.onerror = resolve;
      img.src = imageSrc;
    });

    Promise.all([minTimePromise, imagePromise]).then(() => {
      setImageLoaded(true);
      // Complete progress
      const completeInterval = setInterval(() => {
        setProgress(p => {
          if (p >= 100) {
            clearInterval(completeInterval);
            handleTransition();
            return 100;
          }
          return p + (100 - p) * 0.15;
        });
      }, 50);
    });

    return () => {
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      soundSystem.stop('ambient');
    };
  }, [handleTransition, imageSrc]);

  return (
    <div
      className="loading-splash"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10000,
        background: '#000',
        overflow: 'hidden',
        opacity: fadeOut ? 0 : 1,
        transition: 'opacity 0.5s ease-out',
      }}
      onClick={handleTransition}
    >
      {/* Fullscreen background image */}
      <img
        src={imageSrc}
        alt="Elemental Life"
        onLoad={() => setImageLoaded(true)}
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          opacity: imageLoaded ? 1 : 0,
          transition: 'opacity 0.4s ease',
        }}
      />

      {/* Thin progress bar at bottom */}
      <div
        style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: '3px',
          background: 'rgba(255,255,255,0.1)',
          overflow: 'hidden',
          zIndex: 10,
        }}
      >
        <div
          style={{
            width: `${progress}%`,
            height: '100%',
            background: 'linear-gradient(90deg, #00ffb4, #00d4a0)',
            transition: 'width 0.3s ease-out',
            boxShadow: '0 0 15px rgba(0, 255, 180, 0.6)',
          }}
        />
      </div>
    </div>
  );
}