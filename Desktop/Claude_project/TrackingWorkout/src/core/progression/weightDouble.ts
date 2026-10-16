import { effectiveReps, hasDrop, roundTo, workingWeight } from '../metrics';
import type { SetSegments, SetTarget, WeightConfig } from '../types';

export function doubleTarget(cfg: WeightConfig, lastSets: SetSegments[]): SetTarget[] {
  const w = workingWeight(lastSets);
  const head = lastSets.slice(0, cfg.targetSets);
  const maxed =
    head.length >= cfg.targetSets &&
    head.every((set) => !hasDrop(set) && effectiveReps(set, w) >= cfg.repMax);

  if (maxed) {
    const next = roundTo(w + cfg.increment, cfg.increment);
    return Array.from({ length: cfg.targetSets }, () => ({ weight: next, reps: cfg.repMin }));
  }

  return Array.from({ length: cfg.targetSets }, (_, i) => {
    const set = lastSets[i];
    const eff = set ? effectiveReps(set, w) : 0;
    if (eff === 0) return { weight: w, reps: cfg.repMin };
    const target: SetTarget = { weight: w, reps: Math.min(eff + 1, cfg.repMax) };
    if (hasDrop(set)) target.dropHint = true;
    return target;
  });
}
