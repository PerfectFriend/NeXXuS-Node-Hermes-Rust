/**
 * useIdentity — управление идентификацией пользователя через 3-5 слов + дата.
 *
 * Упрощённая схема:
 * - Пользователь вводит 3-5 слов
 * - Сохраняем слова + дату в localStorage
 * - Детерминированный игровой seed = SHA256(слова + "|" + дата)
 * - Для бэкапа показываем 12-словную фразу (не BIP39, просто для UX)
 * - Нет PIN, нет panic, нет BIP39 — просто localStorage + SHA-256
 */

import { useState, useCallback, useEffect } from 'react';
import { wordsToEntropy, entropyToGameSeed, entropyToHex, entropyToDisplayPhrase, parseWords, validateWords, todayDate } from '../engine/crypto';
import type { GeometryKey } from '../engine/engine';

export interface UserProfile {
  /** Слова, введённые пользователем (исходная энтропия) */
  phraseWords: string[];
  /** 12-словная фраза для бэкапа (display only) */
  backupPhrase: string[];
  /** Hex первых 8 байт энтропии */
  entropyHex: string;
  /** Игровой seed (число) */
  gameSeed: number;
  /** Дата создания профиля (YYYY-MM-DD) */
  createdAt: string;
  /** Пройденные уровни: { hex: [1,2,3], square: [1] } */
  completedLevels: Record<GeometryKey, number[]>;
  /** Последняя геометрия */
  lastGeometry: GeometryKey;
  /** Последний уровень */
  lastLevel: number;
  /** Последний режим */
  lastMode: 'sandbox' | 'puzzle';
}

const STORAGE_KEY = 'elemental_life_identity';

function loadProfile(): UserProfile | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as UserProfile;
  } catch { return null; }
}

function saveProfile(profile: UserProfile): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
}

export function useIdentity() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);

  // Загрузка профиля при монтировании
  useEffect(() => {
    const existing = loadProfile();
    if (existing) setProfile(existing);
    setLoading(false);
  }, []);

  /**
   * Создать новый профиль из слов пользователя.
   */
  const createIdentity = useCallback(async (userWords: string[]): Promise<UserProfile> => {
    const date = todayDate();
    const entropy = wordsToEntropy(userWords, date);
    const gameSeed = entropyToGameSeed(entropy);
    const entropyHex = entropyToHex(entropy);
    const backupPhrase = entropyToDisplayPhrase(entropy);

    const newProfile: UserProfile = {
      phraseWords: userWords,
      backupPhrase,
      entropyHex,
      gameSeed,
      createdAt: date,
      completedLevels: { hex: [], square: [] },
      lastGeometry: 'hex',
      lastLevel: 0,
      lastMode: 'sandbox',
    };

    saveProfile(newProfile);
    setProfile(newProfile);
    return newProfile;
  }, []);

  /**
   * Восстановить профиль из слов пользователя.
   */
  const restoreIdentity = useCallback(async (userWords: string[], date?: string): Promise<UserProfile | null> => {
    const entropy = wordsToEntropy(userWords, date);
    const gameSeed = entropyToGameSeed(entropy);
    const existing = loadProfile();

    // Verify the backup phrase matches (optional check)
    const backupPhrase = entropyToDisplayPhrase(entropy);
    if (existing && existing.backupPhrase.join(' ') !== backupPhrase.join(' ')) {
      // Words don't match existing profile
      return null;
    }

    const restoredProfile: UserProfile = {
      phraseWords: userWords,
      backupPhrase,
      entropyHex: entropyToHex(entropy),
      gameSeed,
      createdAt: existing?.createdAt ?? (date ?? todayDate()),
      completedLevels: existing?.completedLevels ?? { hex: [], square: [] },
      lastGeometry: 'hex',
      lastLevel: 0,
      lastMode: 'sandbox',
    };

    saveProfile(restoredProfile);
    setProfile(restoredProfile);
    return restoredProfile;
  }, []);

  /** Отметить уровень как пройденный */
  const markLevelCompleted = useCallback((geometry: GeometryKey, levelIndex: number) => {
    setProfile((prev) => {
      if (!prev) return prev;
      const current = prev.completedLevels[geometry] || [];
      if (current.includes(levelIndex + 1)) return prev;
      const updated = {
        ...prev,
        completedLevels: {
          ...prev.completedLevels,
          [geometry]: [...current, levelIndex + 1].sort((a, b) => a - b),
        },
      };
      saveProfile(updated);
      return updated;
    });
  }, []);

  /** Сохранить последнюю сессию */
  const saveSession = useCallback((geometry: GeometryKey, level: number, mode: 'sandbox' | 'puzzle') => {
    setProfile((prev) => {
      if (!prev) return prev;
      const updated = { ...prev, lastGeometry: geometry, lastLevel: level, lastMode: mode };
      saveProfile(updated);
      return updated;
    });
  }, []);

  /** Удалить профиль */
  const clearIdentity = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY);
    setProfile(null);
  }, []);

  return {
    profile,
    loading,
    createIdentity,
    restoreIdentity,
    markLevelCompleted,
    saveSession,
    clearIdentity,
    // Expose utilities for UI
    parseWords,
    validateWords,
    todayDate,
    wordsToEntropy,
    entropyToDisplayPhrase,
    entropyToGameSeed,
    entropyToHex,
  };
}