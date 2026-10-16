import { describe, expect, it } from 'vitest';
import {
  e1rm, effectiveReps, firstSegmentVolume, hasDrop, roundTo, sessionE1rm, targetVolume, totalVolume, workingWeight,
} from './metrics';

const drop = [{ weight: 10, reps: 7 }, { weight: 8, reps: 5 }];

describe('roundTo', () => {
  it('step 배수로 반올림', () => {
    expect(roundTo(41.2, 2.5)).toBe(40);
    expect(roundTo(41.3, 2.5)).toBe(42.5);
    expect(roundTo(10.25, 0.5)).toBe(10.5);
    expect(roundTo(0.1 + 0.2, 0.1)).toBe(0.3);
  });
  it('step이 0 이하면 그대로', () => {
    expect(roundTo(3.3, 0)).toBe(3.3);
  });
});

describe('workingWeight', () => {
  it('첫 구간 무게의 최빈값', () => {
    expect(workingWeight([[{ weight: 10, reps: 12 }], [{ weight: 10, reps: 10 }], [{ weight: 12, reps: 8 }]])).toBe(10);
  });
  it('동률이면 큰 무게', () => {
    expect(workingWeight([[{ weight: 10, reps: 12 }], [{ weight: 12, reps: 8 }]])).toBe(12);
  });
  it('드롭 세트는 첫 구간만 본다', () => {
    expect(workingWeight([drop, drop, [{ weight: 8, reps: 12 }]])).toBe(10);
  });
  it('세트가 없으면 0', () => {
    expect(workingWeight([])).toBe(0);
  });
});

describe('세트 지표', () => {
  it('effectiveReps는 첫 구간이 W일 때만', () => {
    expect(effectiveReps(drop, 10)).toBe(7);
    expect(effectiveReps([{ weight: 8, reps: 10 }], 10)).toBe(0);
  });
  it('hasDrop', () => {
    expect(hasDrop(drop)).toBe(true);
    expect(hasDrop([{ weight: 10, reps: 12 }])).toBe(false);
  });
  it('볼륨은 드롭 포함, 첫 구간 볼륨은 제외', () => {
    const sets = [drop, [{ weight: 10, reps: 12 }]];
    expect(totalVolume(sets)).toBe(230);
    expect(firstSegmentVolume(sets)).toBe(190);
  });
  it('targetVolume', () => {
    expect(targetVolume([{ weight: 10, reps: 8 }, { weight: 12.5, reps: 4 }])).toBe(130);
  });
});

describe('e1rm', () => {
  it('Epley', () => {
    expect(e1rm(100, 10)).toBeCloseTo(133.333, 2);
    expect(e1rm(100, 1)).toBe(100);
    expect(e1rm(100, 0)).toBe(0);
  });
  it('세션 e1RM은 모든 구간 중 최대', () => {
    expect(sessionE1rm([drop, [{ weight: 10, reps: 12 }]])).toBeCloseTo(14, 5);
    expect(sessionE1rm([])).toBe(0);
  });
});
