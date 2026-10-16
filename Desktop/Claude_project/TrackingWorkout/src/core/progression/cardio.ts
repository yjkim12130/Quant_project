import { roundTo } from '../metrics';
import type { CardioConfig, CardioTarget } from '../types';

export function cardioTarget(
  cfg: CardioConfig,
  last: { minutes: number; intensity: Record<string, number> },
): CardioTarget {
  const key = cfg.primaryMetric;
  const step = cfg.metrics.find((m) => m.key === key)?.step ?? 1;
  if (last.minutes >= cfg.maxMinutes) {
    const current = last.intensity[key] ?? 0;
    return {
      type: 'cardio',
      minutes: cfg.minMinutes,
      intensity: { ...last.intensity, [key]: roundTo(current + step, step) },
    };
  }
  return {
    type: 'cardio',
    minutes: Math.min(last.minutes + cfg.timeStep, cfg.maxMinutes),
    intensity: { ...last.intensity },
  };
}
