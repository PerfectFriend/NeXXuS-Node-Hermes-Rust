import { useState, useCallback, useRef, useEffect } from 'react';
import type { StateKey } from '../engine/engine';

type SequenceElement = 'FIRE' | 'WATER' | 'EARTH' | 'EMPTY';

const STATE_MAP: Record<SequenceElement, StateKey> = {
  FIRE: 'fire',
  WATER: 'water',
  EARTH: 'earth',
  EMPTY: 'empty',
};

const STORAGE_KEY = 'el_elemental_sequence';

function getStoredSequence(): SequenceElement[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch { /* ignore */ }
  return [];
}

interface HiddenEntranceOptions {
  onUnlock?: () => void;
}

export function useHiddenEntrance(options?: HiddenEntranceOptions) {
  const seqRef = useRef<StateKey[]>([]);
  const [unlocked, setUnlocked] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const targetRef = useRef<StateKey[]>([]);
  const firedRef = useRef(false);

  const getTarget = useCallback(() => {
    if (targetRef.current.length === 0) {
      const stored = getStoredSequence();
      targetRef.current = stored.map(s => STATE_MAP[s] ?? 'fire');
    }
    return targetRef.current;
  }, []);

  const recordTap = useCallback((element: StateKey) => {
    if (unlocked) return;
    const target = getTarget();
    const seqLen = target.length;

    seqRef.current = [...seqRef.current, element].slice(-seqLen);
    if (
      seqRef.current.length === seqLen &&
      seqRef.current.every((s, i) => s === target[i])
    ) {
      setUnlocked(true);
      setShowHint(true);
      setTimeout(() => setShowHint(false), 3000);
    }
  }, [unlocked, getTarget]);

  // Fire onUnlock callback once when unlocked
  useEffect(() => {
    if (unlocked && !firedRef.current) {
      firedRef.current = true;
      options?.onUnlock?.();
    }
  }, [unlocked, options]);

  const reset = useCallback(() => {
    seqRef.current = [];
    setUnlocked(false);
    setShowHint(false);
    firedRef.current = false;
  }, []);

  return { unlocked, showHint, recordTap, reset, setShowHint };
}