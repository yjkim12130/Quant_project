import { describe, expect, it } from 'vitest';
import { DEFAULT_WEIGHT } from '../defaults';
import { doubleTarget } from './weightDouble';

const cfg = { ...DEFAULT_WEIGHT }; // 8~12회, 3세트, 2.5kg
const s = (weight: number, reps: number) => [{ weight, reps }];

describe('doubleTarget', () => {
  it('모든 세트 repMax 달성 → 증량, repMin', () => {
    expect(doubleTarget(cfg, [s(40, 12), s(40, 12), s(40, 13)])).toEqual([
      { weight: 42.5, reps: 8 }, { weight: 42.5, reps: 8 }, { weight: 42.5, reps: 8 },
    ]);
  });
  it('증량 무게는 증량 단위로 반올림', () => {
    expect(doubleTarget(cfg, [s(41, 12), s(41, 12), s(41, 12)])[0].weight).toBe(42.5);
  });
  it('스펙 예시: 드롭 세트는 유효 횟수+1과 dropHint', () => {
    const last = [[{ weight: 10, reps: 7 }, { weight: 8, reps: 5 }], s(10, 12), s(10, 9)];
    expect(doubleTarget(cfg, last)).toEqual([
      { weight: 10, reps: 8, dropHint: true }, { weight: 10, reps: 12 }, { weight: 10, reps: 10 },
    ]);
  });
  it('세트가 모자라면 repMin 세트를 추가', () => {
    expect(doubleTarget(cfg, [s(40, 10), s(40, 9)])).toEqual([
      { weight: 40, reps: 11 }, { weight: 40, reps: 10 }, { weight: 40, reps: 8 },
    ]);
  });
  it('repMax를 채웠어도 드롭이 있으면 증량하지 않는다', () => {
    const last = [[{ weight: 40, reps: 12 }, { weight: 30, reps: 4 }], s(40, 12), s(40, 12)];
    expect(doubleTarget(cfg, last)).toEqual([
      { weight: 40, reps: 12, dropHint: true }, { weight: 40, reps: 12 }, { weight: 40, reps: 12 },
    ]);
  });
  it('W가 아닌 무게로 한 세트는 repMin부터', () => {
    expect(doubleTarget(cfg, [s(40, 10), s(40, 10), s(35, 12)])[2]).toEqual({ weight: 40, reps: 8 });
  });
  it('세트 수가 모자라면 repMax를 채웠어도 증량하지 않는다', () => {
    expect(doubleTarget(cfg, [s(40, 12), s(40, 12)])).toEqual([
      { weight: 40, reps: 12 }, { weight: 40, reps: 12 }, { weight: 40, reps: 8 },
    ]);
  });
});
