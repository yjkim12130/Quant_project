import type { StreakState } from './types';

const DAY_MS = 86_400_000;

function parse(date: string): number {
  const [y, m, d] = date.split('-').map(Number);
  return Date.UTC(y, m - 1, d);
}

export function toLocalDateString(d: Date): string {
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${mm}-${dd}`;
}

export function daysBetween(from: string, to: string): number {
  return Math.round((parse(to) - parse(from)) / DAY_MS);
}

export function isoWeekKey(date: string): string {
  const d = new Date(parse(date));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum); // 그 주의 목요일
  const yearStart = Date.UTC(d.getUTCFullYear(), 0, 1);
  const week = Math.ceil(((d.getTime() - yearStart) / DAY_MS + 1) / 7);
  return `${d.getUTCFullYear()}-W${String(week).padStart(2, '0')}`;
}

export function emptyStreak(): StreakState {
  return { count: 0, lastPlayedDate: null, freezeUsedWeek: null };
}

export function recordPlay(s: StreakState, today: string): StreakState {
  if (!s.lastPlayedDate) return { ...s, count: 1, lastPlayedDate: today };
  const gap = daysBetween(s.lastPlayedDate, today);
  if (gap <= 0) return s;
  if (gap === 1) return { ...s, count: s.count + 1, lastPlayedDate: today };
  const week = isoWeekKey(today);
  if (gap === 2 && s.freezeUsedWeek !== week) {
    return { count: s.count + 1, lastPlayedDate: today, freezeUsedWeek: week };
  }
  return { ...s, count: 1, lastPlayedDate: today };
}

export function displayStreak(s: StreakState, today: string): number {
  if (!s.lastPlayedDate) return 0;
  const gap = daysBetween(s.lastPlayedDate, today);
  if (gap <= 1) return s.count;
  if (gap === 2 && s.freezeUsedWeek !== isoWeekKey(today)) return s.count;
  return 0;
}
