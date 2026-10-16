import { describe, expect, it } from 'vitest';
import { DEFAULT_WEIGHT } from '../defaults';
import { volumePlan } from './weightVolume';

const cfg = { ...DEFAULT_WEIGHT, progression: 'volume' as const }; // 3%
const s = (weight: number, reps: number) => [{ weight, reps }];

describe('volumePlan', () => {
  it('스펙 예시: 드롭 포함 볼륨의 +3%, 마지막 세트부터 +1씩', () => {
    const last = [[{ weight: 10, reps: 7 }, { weight: 8, reps: 5 }], s(10, 12), s(10, 9)];
    const plan = volumePlan(cfg, last); // 320 → 330
    expect(plan.goal).toBe(330);
    expect(plan.byReps).toEqual([{ weight: 10, reps: 8 }, { weight: 10, reps: 14 }, { weight: 10, reps: 11 }]);
    expect(plan.byWeight).toEqual([{ weight: 12.5, reps: 9 }, { weight: 12.5, reps: 9 }, { weight: 12.5, reps: 9 }]);
  });
  it('부동소수 오차로 목표가 1 커지지 않는다', () => {
    const plan = volumePlan(cfg, [s(50, 10), s(50, 10), s(50, 10)]); // 1500 → 1545
    expect(plan.goal).toBe(1545);
    expect(plan.byReps.map((t) => t.reps)).toEqual([10, 10, 11]);
    expect(plan.byWeight[0]).toEqual({ weight: 52.5, reps: 10 });
  });
  it('맨몸(0kg)이면 마지막 세트 +1회', () => {
    expect(volumePlan(cfg, [s(0, 10), s(0, 10), s(0, 10)]).byReps.map((t) => t.reps)).toEqual([10, 10, 11]);
  });
});
