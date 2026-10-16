import { sessionE1rm, totalVolume } from './metrics';
import type { Badge, CardioHistoryItem, Exercise, History, WeightHistoryItem } from './types';

export function weightBadge(item: WeightHistoryItem, prev?: WeightHistoryItem): Badge | null {
  const t = item.target;
  if (!t || t.type === 'cardio' || item.sets.length === 0) return null;
  const achieved =
    t.type === 'double'
      ? t.sets.every((st, i) => {
          const set = item.sets[i];
          return !!set && set[0].weight >= st.weight && set[0].reps >= st.reps;
        })
      : totalVolume(item.sets) >= t.volume;
  if (achieved) return 'up';
  if (
    prev && prev.sets.length > 0 &&
    sessionE1rm(item.sets) < sessionE1rm(prev.sets) &&
    totalVolume(item.sets) < totalVolume(prev.sets)
  ) {
    return 'down';
  }
  return 'same';
}

export function cardioBadge(item: CardioHistoryItem, prev: CardioHistoryItem | undefined, primary: string): Badge | null {
  const t = item.target;
  if (!t || t.type !== 'cardio') return null;
  const current = item.intensity[primary] ?? 0;
  if (current >= (t.intensity[primary] ?? 0) && item.minutes >= t.minutes) return 'up';
  if (prev && current <= (prev.intensity[primary] ?? 0) && item.minutes < prev.minutes) return 'down';
  return 'same';
}

export function badgesFor(ex: Exercise, history: History): (Badge | null)[] {
  if (ex.kind === 'weight') {
    const h = history as WeightHistoryItem[];
    return h.map((item, i) => weightBadge(item, h[i - 1]));
  }
  const h = history as CardioHistoryItem[];
  return h.map((item, i) => cardioBadge(item, h[i - 1], ex.cardio!.primaryMetric));
}

export function achievementRate(badges: (Badge | null)[]): number | null {
  const judged = badges.filter((b): b is Badge => b !== null);
  if (judged.length === 0) return null;
  return judged.filter((b) => b === 'up').length / judged.length;
}
