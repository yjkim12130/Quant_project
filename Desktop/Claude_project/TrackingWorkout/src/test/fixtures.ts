import { DEFAULT_CARDIO, DEFAULT_REST_SECONDS, DEFAULT_WEIGHT } from '../core/defaults';
import type { SetSegments, Target } from '../core/types';
import {
  addWeightSet, getOrCreateSession, saveCardioEntry, type CardioInput, type NewExercise,
} from '../db/repository';
import type { WorkoutDB } from '../db/schema';

export function weightExercise(overrides: Partial<NewExercise> = {}): NewExercise {
  return {
    equipment: '레그프레스', name: '하체', kind: 'weight', restSeconds: DEFAULT_REST_SECONDS,
    weight: { ...DEFAULT_WEIGHT }, ...overrides,
  };
}

export function cardioExercise(overrides: Partial<NewExercise> = {}): NewExercise {
  return {
    equipment: '러닝머신', name: '달리기', kind: 'cardio', restSeconds: DEFAULT_REST_SECONDS,
    cardio: {
      ...DEFAULT_CARDIO,
      metrics: [
        { key: 'speed', label: '속도', unit: 'km/h', step: 0.5 },
        { key: 'incline', label: '경사', unit: '%', step: 1 },
      ],
      primaryMetric: 'speed',
    },
    ...overrides,
  };
}

export async function seedWeightSession(
  db: WorkoutDB, exerciseId: string, date: string, sets: SetSegments[], target?: Target,
) {
  const session = await getOrCreateSession(db, exerciseId, date, target);
  for (const segments of sets) await addWeightSet(db, session.id, segments);
  return session;
}

export async function seedCardioSession(
  db: WorkoutDB, exerciseId: string, date: string, input: CardioInput, target?: Target,
) {
  const session = await getOrCreateSession(db, exerciseId, date, target);
  await saveCardioEntry(db, session.id, input);
  return session;
}
