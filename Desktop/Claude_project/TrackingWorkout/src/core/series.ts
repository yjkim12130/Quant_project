import { addDays, shortDate } from './date';
import { firstSegmentVolume, sessionE1rm, totalVolume } from './metrics';
import type { CardioHistoryItem, WeightHistoryItem } from './types';

export interface WeightPoint {
  date: string;
  label: string;
  e1rm: number;
  mainVolume: number;
  dropVolume: number;
  achievementPct: number | null;
  isPR: boolean;
}

export interface CardioPoint {
  date: string;
  label: string;
  minutes: number;
  primary: number;
  distanceKm: number | null;
  kcal: number | null;
  kcalPerMin: number | null;
  speedKmh: number | null;
}

export type Range = '4w' | '3m' | 'all';

const round1 = (n: number) => Number(n.toFixed(1));

function achievementPct(h: WeightHistoryItem): number | null {
  const t = h.target;
  if (!t || t.type === 'cardio') return null;
  const goal = t.sets.reduce((a, s) => a + s.reps, 0);
  if (goal === 0) return null;
  const done = t.sets.reduce((a, s, i) => {
    const set = h.sets[i];
    return a + (set && set[0].weight >= s.weight ? Math.min(set[0].reps, s.reps) : 0);
  }, 0);
  return Math.round((done / goal) * 100);
}

export function weightSeries(history: WeightHistoryItem[]): WeightPoint[] {
  let best = 0;
  return history.map((h, i) => {
    const e = round1(sessionE1rm(h.sets));
    const isPR = i > 0 && e > best;
    best = Math.max(best, e);
    const main = firstSegmentVolume(h.sets);
    return {
      date: h.date,
      label: shortDate(h.date),
      e1rm: e,
      mainVolume: main,
      dropVolume: totalVolume(h.sets) - main,
      achievementPct: achievementPct(h),
      isPR,
    };
  });
}

export function cardioSeries(history: CardioHistoryItem[], primary: string): CardioPoint[] {
  return history.map((h) => ({
    date: h.date,
    label: shortDate(h.date),
    minutes: h.minutes,
    primary: h.intensity[primary] ?? 0,
    distanceKm: h.distanceKm ?? null,
    kcal: h.kcal ?? null,
    kcalPerMin: h.kcal != null && h.minutes > 0 ? round1(h.kcal / h.minutes) : null,
    speedKmh: h.distanceKm != null && h.minutes > 0 ? round1(h.distanceKm / (h.minutes / 60)) : null,
  }));
}

export function filterByRange<T extends { date: string }>(points: T[], range: Range, today: string): T[] {
  if (range === 'all') return points;
  const from = addDays(today, range === '4w' ? -28 : -91);
  return points.filter((p) => p.date >= from);
}
