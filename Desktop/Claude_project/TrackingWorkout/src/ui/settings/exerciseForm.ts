import { DEFAULT_CARDIO, DEFAULT_REST_SECONDS, DEFAULT_WEIGHT } from '../../core/defaults';
import type { CardioConfig, Exercise, ExerciseKind, WeightConfig } from '../../core/types';
import type { NewExercise } from '../../db/repository';

export interface ExerciseFormValues {
  equipment: string;
  name: string;
  kind: ExerciseKind;
  restSeconds: number;
  weight: WeightConfig;
  cardio: CardioConfig;
}

export function toFormValues(ex?: Exercise): ExerciseFormValues {
  const cardio = ex?.cardio ?? DEFAULT_CARDIO;
  return {
    equipment: ex?.equipment ?? '',
    name: ex?.name ?? '',
    kind: ex?.kind ?? 'weight',
    restSeconds: ex?.restSeconds ?? DEFAULT_REST_SECONDS,
    weight: { ...(ex?.weight ?? DEFAULT_WEIGHT) },
    cardio: { ...cardio, metrics: cardio.metrics.map((m) => ({ ...m })) },
  };
}

const isInt = (n: number) => Number.isInteger(n);

export function validateExerciseForm(v: ExerciseFormValues): string[] {
  const errors: string[] = [];
  if (!v.equipment.trim()) errors.push('기구 이름을 입력하세요');
  if (!v.name.trim()) errors.push('운동 종류를 입력하세요');
  if (!isInt(v.restSeconds) || v.restSeconds < 0 || v.restSeconds > 600) errors.push('휴식 시간은 0~600초로 입력하세요');

  if (v.kind === 'weight') {
    const w = v.weight;
    if (!isInt(w.repMin) || w.repMin < 1) errors.push('최소 횟수는 1 이상의 정수예요');
    if (!isInt(w.repMax) || w.repMax < w.repMin) errors.push('최대 횟수는 최소 횟수 이상이어야 해요');
    if (!isInt(w.targetSets) || w.targetSets < 1 || w.targetSets > 10) errors.push('세트 수는 1~10이에요');
    if (!(w.increment > 0)) errors.push('증량 단위는 0보다 커야 해요');
    if (w.progression === 'volume' && !(w.volumeGrowthPct >= 2 && w.volumeGrowthPct <= 5)) {
      errors.push('볼륨 증가율은 2~5%예요');
    }
  } else {
    const c = v.cardio;
    if (!isInt(c.minMinutes) || c.minMinutes < 1) errors.push('최소 시간은 1분 이상이에요');
    if (!isInt(c.maxMinutes) || c.maxMinutes < c.minMinutes) errors.push('최대 시간은 최소 시간 이상이어야 해요');
    if (!isInt(c.timeStep) || c.timeStep < 1) errors.push('시간 증가 단위는 1분 이상이에요');
    if (c.metrics.length === 0) errors.push('강도 항목을 하나 이상 추가하세요');
    if (c.metrics.some((m) => !m.label.trim())) errors.push('강도 항목 이름을 입력하세요');
    if (c.metrics.some((m) => !(m.step > 0))) errors.push('강도 증가 단위는 0보다 커야 해요');
    if (c.metrics.length > 0 && !c.metrics.some((m) => m.key === c.primaryMetric)) errors.push('올릴 강도 항목을 고르세요');
  }
  return errors;
}

export function fromFormValues(v: ExerciseFormValues): NewExercise {
  const base = { equipment: v.equipment.trim(), name: v.name.trim(), kind: v.kind, restSeconds: v.restSeconds };
  if (v.kind === 'weight') return { ...base, weight: { ...v.weight } };
  return {
    ...base,
    cardio: { ...v.cardio, metrics: v.cardio.metrics.map((m) => ({ ...m, label: m.label.trim(), unit: m.unit.trim() })) },
  };
}
