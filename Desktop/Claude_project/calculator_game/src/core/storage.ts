import { emptyStats } from './scoring';
import { emptyStreak } from './streak';
import type { AppData, Profile } from './types';

export const STORAGE_KEY = 'calculator_game:v1';

export type KV = Pick<Storage, 'getItem' | 'setItem'>;

export function defaultAppData(): AppData {
  return { schemaVersion: 1, profiles: [], activeProfileId: null, settings: { soundOn: true, timerSec: null } };
}

export function newProfile(id: string, name: string, avatar: string): Profile {
  return { id, name, avatar, xp: 0, streak: emptyStreak(), stages: {}, unlockAll: false, stats: emptyStats() };
}

export function browserStorage(): KV | null {
  try {
    const s = window.localStorage;
    s.getItem(STORAGE_KEY); // 사생활 보호 모드 등에서 여기서 예외가 난다
    return s;
  } catch {
    return null;
  }
}

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function normalize(v: unknown): AppData | null {
  if (!isObj(v) || v.schemaVersion !== 1 || !Array.isArray(v.profiles)) return null;
  const profiles: Profile[] = [];
  for (const p of v.profiles) {
    if (!isObj(p) || typeof p.id !== 'string' || typeof p.name !== 'string') return null;
    const base = newProfile(p.id, p.name, typeof p.avatar === 'string' ? p.avatar : '🐣');
    const stats = { ...base.stats, ...(isObj(p.stats) ? p.stats : {}) };
    profiles.push({ ...base, ...p, stats } as Profile);
  }
  const settings = isObj(v.settings) ? v.settings : {};
  const activeProfileId =
    typeof v.activeProfileId === 'string' && profiles.some((p) => p.id === v.activeProfileId) ? v.activeProfileId : null;
  return {
    schemaVersion: 1,
    profiles,
    activeProfileId,
    settings: {
      soundOn: settings.soundOn !== false,
      timerSec: typeof settings.timerSec === 'number' ? settings.timerSec : null,
    },
  };
}

export function loadAppData(kv: KV | null): { data: AppData; error: boolean } {
  if (!kv) return { data: defaultAppData(), error: true };
  let raw: string | null;
  try {
    raw = kv.getItem(STORAGE_KEY);
  } catch {
    return { data: defaultAppData(), error: true };
  }
  if (raw === null) return { data: defaultAppData(), error: false };
  try {
    const data = normalize(JSON.parse(raw));
    return data ? { data, error: false } : { data: defaultAppData(), error: true };
  } catch {
    return { data: defaultAppData(), error: true };
  }
}

export function saveAppData(kv: KV | null, data: AppData): boolean {
  if (!kv) return false;
  try {
    kv.setItem(STORAGE_KEY, JSON.stringify(data));
    return true;
  } catch {
    return false;
  }
}
