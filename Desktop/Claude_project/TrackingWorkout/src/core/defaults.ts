import type { CardioConfig, WeightConfig } from './types';

export const DEFAULT_WEIGHT: WeightConfig = {
  progression: 'double',
  repMin: 8,
  repMax: 12,
  targetSets: 3,
  increment: 2.5,
  volumeGrowthPct: 3,
};

export const DEFAULT_CARDIO: CardioConfig = {
  metrics: [{ key: 'level', label: '레벨', unit: '', step: 1 }],
  primaryMetric: 'level',
  minMinutes: 20,
  maxMinutes: 30,
  timeStep: 2,
};

export const DEFAULT_REST_SECONDS = 90;
/** 마지막 기록이 이 일수보다 오래되면 "지난번 그대로" */
export const RETURN_GAP_DAYS = 14;
/** 마지막 백업이 이 일수보다 오래되면 경고 */
export const BACKUP_WARN_DAYS = 14;
export const DELOAD_RATIO = 0.9;
