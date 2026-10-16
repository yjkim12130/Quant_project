import { effectiveReps, roundTo, totalVolume, workingWeight } from '../metrics';
import type { SetSegments, SetTarget, WeightConfig } from '../types';

export interface VolumePlan {
  goal: number;
  byReps: SetTarget[];
  byWeight: SetTarget[];
}

export function volumePlan(cfg: WeightConfig, lastSets: SetSegments[]): VolumePlan {
  const w = workingWeight(lastSets);
  // 1e-9: 1500 × 1.03 같은 부동소수 오차로 1kg 더 요구하지 않도록
  const goal = Math.ceil((totalVolume(lastSets) * (100 + cfg.volumeGrowthPct)) / 100 - 1e-9);

  const reps = Array.from({ length: cfg.targetSets }, (_, i) => {
    const set = lastSets[i];
    const eff = set ? effectiveReps(set, w) : 0;
    return eff > 0 ? eff : cfg.repMin;
  });
  if (w > 0) {
    let i = reps.length - 1;
    while (reps.reduce((a, r) => a + r * w, 0) < goal) {
      reps[i] += 1;
      i = i === 0 ? reps.length - 1 : i - 1;
    }
  } else {
    reps[reps.length - 1] += 1;
  }

  const next = roundTo(w + cfg.increment, cfg.increment);
  const r = Math.max(1, Math.ceil(goal / (next * cfg.targetSets)));
  return {
    goal,
    byReps: reps.map((n) => ({ weight: w, reps: n })),
    byWeight: Array.from({ length: cfg.targetSets }, () => ({ weight: next, reps: r })),
  };
}
