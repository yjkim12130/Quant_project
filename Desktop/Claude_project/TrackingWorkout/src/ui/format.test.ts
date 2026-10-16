import { describe, expect, it } from 'vitest';
import { cardioExercise } from '../test/fixtures';
import { exerciseLabel, formatCardio, formatKg, formatLongDate, formatSet, formatTarget, formatWeightTarget } from './format';

describe('format', () => {
  it('무게와 세트', () => {
    expect(formatKg(42.5)).toBe('42.5');
    expect(formatKg(40)).toBe('40');
    expect(formatSet([{ weight: 10, reps: 7 }, { weight: 8, reps: 5 }])).toBe('10kg×7 → 8kg×5');
  });
  it('웨이트 목표', () => {
    expect(formatWeightTarget({ type: 'double', sets: [{ weight: 40, reps: 12 }, { weight: 40, reps: 11 }] })).toBe('40kg × 12/11');
    expect(formatWeightTarget({ type: 'double', sets: [{ weight: 40, reps: 12 }, { weight: 35, reps: 10 }] })).toBe('40×12 / 35×10');
    expect(formatWeightTarget({ type: 'volume', volume: 330, sets: [{ weight: 10, reps: 8 }] })).toBe('10kg × 8 (볼륨 330kg)');
  });
  it('유산소', () => {
    const ex = { ...cardioExercise(), id: 'c', createdAt: 1, archived: false };
    expect(formatCardio({ minutes: 25, intensity: { speed: 10.5, incline: 3 } }, ex.cardio!.metrics)).toBe('25분 · 속도 10.5km/h · 경사 3%');
    expect(formatTarget({ type: 'cardio', minutes: 20, intensity: { speed: 10 } }, ex)).toBe('20분 · 속도 10km/h · 경사 0%');
    expect(exerciseLabel(ex)).toBe('러닝머신 · 달리기');
  });
  it('긴 날짜', () => {
    expect(formatLongDate('2026-10-17')).toBe('10월 17일 (토)');
  });
});
