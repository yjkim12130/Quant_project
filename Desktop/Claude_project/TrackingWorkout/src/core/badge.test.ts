import { describe, expect, it } from 'vitest';
import { DEFAULT_CARDIO, DEFAULT_WEIGHT } from './defaults';
import { achievementRate, badgesFor, cardioBadge, weightBadge } from './badge';
import type { CardioHistoryItem, Exercise, WeightHistoryItem } from './types';

const s = (weight: number, reps: number) => [{ weight, reps }];
const doubleTarget = { type: 'double' as const, sets: [{ weight: 40, reps: 12 }, { weight: 40, reps: 11 }] };

describe('weightBadge', () => {
  const prev: WeightHistoryItem = { date: '2026-10-14', sets: [s(40, 12), s(40, 10)] };
  it('목표 충족 → up', () => {
    expect(weightBadge({ date: '2026-10-17', sets: [s(40, 12), s(40, 11)], target: doubleTarget }, prev)).toBe('up');
  });
  it('무게를 더 들었으면 충족', () => {
    expect(weightBadge({ date: '2026-10-17', sets: [s(42.5, 12), s(40, 11)], target: doubleTarget }, prev)).toBe('up');
  });
  it('미달이지만 하락 아님 → same', () => {
    expect(weightBadge({ date: '2026-10-17', sets: [s(40, 12), s(40, 10)], target: doubleTarget }, prev)).toBe('same');
  });
  it('e1RM과 볼륨이 모두 낮음 → down', () => {
    expect(weightBadge({ date: '2026-10-17', sets: [s(40, 10), s(40, 9)], target: doubleTarget }, prev)).toBe('down');
  });
  it('볼륨 목표', () => {
    const target = { type: 'volume' as const, volume: 900, sets: [] };
    expect(weightBadge({ date: '2026-10-17', sets: [s(40, 12), s(40, 11)], target }, prev)).toBe('up');
  });
  it('목표가 없으면 null', () => {
    expect(weightBadge({ date: '2026-10-17', sets: [s(40, 12)] }, prev)).toBeNull();
  });
});

describe('cardioBadge', () => {
  const target = { type: 'cardio' as const, minutes: 26, intensity: { level: 8 } };
  const prev: CardioHistoryItem = { date: '2026-10-14', minutes: 24, intensity: { level: 8 } };
  it('up / same / down', () => {
    expect(cardioBadge({ date: 'd', minutes: 26, intensity: { level: 8 }, target }, prev, 'level')).toBe('up');
    expect(cardioBadge({ date: 'd', minutes: 25, intensity: { level: 8 }, target }, prev, 'level')).toBe('same');
    expect(cardioBadge({ date: 'd', minutes: 20, intensity: { level: 8 }, target }, prev, 'level')).toBe('down');
    expect(cardioBadge({ date: 'd', minutes: 20, intensity: { level: 9 }, target }, prev, 'level')).toBe('same');
  });
});

describe('badgesFor / achievementRate', () => {
  it('히스토리와 같은 길이로 정렬된 배지', () => {
    const ex: Exercise = {
      id: 'w', equipment: '바벨', name: '스쿼트', kind: 'weight', archived: false,
      restSeconds: 90, createdAt: 1, weight: { ...DEFAULT_WEIGHT },
    };
    const history: WeightHistoryItem[] = [
      { date: '2026-10-10', sets: [s(40, 12)] },
      { date: '2026-10-14', sets: [s(40, 12), s(40, 11)], target: doubleTarget },
    ];
    expect(badgesFor(ex, history)).toEqual([null, 'up']);
    const cex: Exercise = { ...ex, kind: 'cardio', weight: undefined, cardio: { ...DEFAULT_CARDIO } };
    expect(badgesFor(cex, [])).toEqual([]);
  });
  it('달성률은 배지가 있는 세션 중 up 비율', () => {
    expect(achievementRate(['up', 'same', null, 'up'])).toBeCloseTo(2 / 3);
    expect(achievementRate([null])).toBeNull();
  });
});
