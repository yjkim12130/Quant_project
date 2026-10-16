import { describe, expect, it } from 'vitest';
import { fromFormValues, toFormValues, validateExerciseForm } from './exerciseForm';

const valid = () => ({ ...toFormValues(), equipment: '레그프레스', name: '하체' });

describe('exerciseForm', () => {
  it('새 운동 기본값', () => {
    expect(toFormValues()).toMatchObject({
      equipment: '', name: '', kind: 'weight', restSeconds: 90,
      weight: { repMin: 8, repMax: 12, targetSets: 3, increment: 2.5, volumeGrowthPct: 3 },
      cardio: { minMinutes: 20, maxMinutes: 30, timeStep: 2 },
    });
  });
  it('정상 값은 오류 없음', () => {
    expect(validateExerciseForm(valid())).toEqual([]);
  });
  it('웨이트 검증', () => {
    const v = valid();
    expect(validateExerciseForm({ ...v, equipment: ' ' })).toContain('기구 이름을 입력하세요');
    expect(validateExerciseForm({ ...v, name: '' })).toContain('운동 종류를 입력하세요');
    expect(validateExerciseForm({ ...v, restSeconds: 700 })).toContain('휴식 시간은 0~600초로 입력하세요');
    expect(validateExerciseForm({ ...v, weight: { ...v.weight, repMin: 0 } })).toContain('최소 횟수는 1 이상의 정수예요');
    expect(validateExerciseForm({ ...v, weight: { ...v.weight, repMax: 6 } })).toContain('최대 횟수는 최소 횟수 이상이어야 해요');
    expect(validateExerciseForm({ ...v, weight: { ...v.weight, targetSets: 0 } })).toContain('세트 수는 1~10이에요');
    expect(validateExerciseForm({ ...v, weight: { ...v.weight, increment: 0 } })).toContain('증량 단위는 0보다 커야 해요');
    expect(validateExerciseForm({ ...v, weight: { ...v.weight, progression: 'volume', volumeGrowthPct: 7 } })).toContain('볼륨 증가율은 2~5%예요');
    expect(validateExerciseForm({ ...v, weight: { ...v.weight, volumeGrowthPct: 7 } })).toEqual([]);
  });
  it('유산소 검증', () => {
    const v = { ...valid(), kind: 'cardio' as const };
    expect(validateExerciseForm(v)).toEqual([]);
    expect(validateExerciseForm({ ...v, cardio: { ...v.cardio, maxMinutes: 10 } })).toContain('최대 시간은 최소 시간 이상이어야 해요');
    expect(validateExerciseForm({ ...v, cardio: { ...v.cardio, minMinutes: 0 } })).toContain('최소 시간은 1분 이상이에요');
    expect(validateExerciseForm({ ...v, cardio: { ...v.cardio, timeStep: 0 } })).toContain('시간 증가 단위는 1분 이상이에요');
    expect(validateExerciseForm({ ...v, cardio: { ...v.cardio, metrics: [] } })).toContain('강도 항목을 하나 이상 추가하세요');
    expect(validateExerciseForm({ ...v, cardio: { ...v.cardio, metrics: [{ key: 'a', label: '', unit: '', step: 1 }], primaryMetric: 'a' } })).toContain('강도 항목 이름을 입력하세요');
    expect(validateExerciseForm({ ...v, cardio: { ...v.cardio, metrics: [{ key: 'a', label: 'A', unit: '', step: 0 }], primaryMetric: 'a' } })).toContain('강도 증가 단위는 0보다 커야 해요');
    expect(validateExerciseForm({ ...v, cardio: { ...v.cardio, primaryMetric: 'zzz' } })).toContain('올릴 강도 항목을 고르세요');
  });
  it('fromFormValues는 종류에 맞는 설정만 담는다', () => {
    const w = fromFormValues(valid());
    expect(w.weight).toBeDefined();
    expect(w.cardio).toBeUndefined();
    const c = fromFormValues({ ...valid(), kind: 'cardio' });
    expect(c.cardio).toBeDefined();
    expect(c.weight).toBeUndefined();
  });
});
