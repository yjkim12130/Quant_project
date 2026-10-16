import type { SetSegments, SetTarget } from './types';

export function roundTo(value: number, step: number): number {
  if (step <= 0) return value;
  return Number((Math.round(value / step) * step).toFixed(3));
}

/** 각 세트 첫 구간 무게의 최빈값(동률이면 큰 값) */
export function workingWeight(sets: SetSegments[]): number {
  const counts = new Map<number, number>();
  for (const set of sets) {
    if (set.length === 0) continue;
    counts.set(set[0].weight, (counts.get(set[0].weight) ?? 0) + 1);
  }
  let best = 0;
  let bestCount = 0;
  for (const [weight, count] of counts) {
    if (count > bestCount || (count === bestCount && weight > best)) {
      best = weight;
      bestCount = count;
    }
  }
  return best;
}

/** 작업 무게 W로 한 첫 구간의 횟수. 드롭 구간은 세지 않는다 */
export function effectiveReps(set: SetSegments, w: number): number {
  return set.length > 0 && set[0].weight === w ? set[0].reps : 0;
}

export function hasDrop(set: SetSegments): boolean {
  return set.length > 1;
}

export function totalVolume(sets: SetSegments[]): number {
  return sets.reduce((sum, set) => sum + set.reduce((a, s) => a + s.weight * s.reps, 0), 0);
}

export function firstSegmentVolume(sets: SetSegments[]): number {
  return sets.reduce((sum, set) => sum + (set.length ? set[0].weight * set[0].reps : 0), 0);
}

export function e1rm(weight: number, reps: number): number {
  if (reps <= 0) return 0;
  if (reps === 1) return weight;
  return weight * (1 + reps / 30);
}

export function sessionE1rm(sets: SetSegments[]): number {
  let best = 0;
  for (const set of sets) for (const s of set) best = Math.max(best, e1rm(s.weight, s.reps));
  return best;
}

export function targetVolume(sets: SetTarget[]): number {
  return sets.reduce((sum, s) => sum + s.weight * s.reps, 0);
}
