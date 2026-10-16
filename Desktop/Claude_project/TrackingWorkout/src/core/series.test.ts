import { describe, expect, it } from 'vitest';
import { cardioSeries, filterByRange, weightSeries } from './series';

describe('weightSeries', () => {
  it('e1RM·볼륨 분해·달성률·PR', () => {
    const points = weightSeries([
      { date: '2026-10-10', sets: [[{ weight: 10, reps: 12 }]] },
      {
        date: '2026-10-14',
        sets: [[{ weight: 10, reps: 8 }, { weight: 8, reps: 4 }], [{ weight: 10, reps: 12 }], [{ weight: 10, reps: 9 }]],
        target: { type: 'double', sets: [{ weight: 10, reps: 8, dropHint: true }, { weight: 10, reps: 12 }, { weight: 10, reps: 10 }] },
      },
      { date: '2026-10-16', sets: [[{ weight: 10, reps: 10 }]] },
    ]);
    expect(points[0]).toEqual({
      date: '2026-10-10', label: '10/10', e1rm: 14, mainVolume: 120, dropVolume: 0, achievementPct: null, isPR: false,
    });
    expect(points[1]).toMatchObject({ mainVolume: 290, dropVolume: 32, achievementPct: 97, isPR: false });
    expect(points[2].isPR).toBe(false);
  });
  it('이전 최고를 넘으면 PR', () => {
    const points = weightSeries([
      { date: '2026-10-10', sets: [[{ weight: 10, reps: 12 }]] },
      { date: '2026-10-14', sets: [[{ weight: 12.5, reps: 10 }]] },
    ]);
    expect(points.map((p) => p.isPR)).toEqual([false, true]);
  });
});

describe('cardioSeries', () => {
  it('평균 속도와 분당 칼로리', () => {
    expect(cardioSeries([{ date: '2026-10-14', minutes: 30, intensity: { speed: 10 }, distanceKm: 5, kcal: 300 }], 'speed')).toEqual([
      { date: '2026-10-14', label: '10/14', minutes: 30, primary: 10, distanceKm: 5, kcal: 300, kcalPerMin: 10, speedKmh: 10 },
    ]);
    expect(cardioSeries([{ date: '2026-10-14', minutes: 30, intensity: {} }], 'speed')[0]).toMatchObject({
      primary: 0, distanceKm: null, kcal: null, kcalPerMin: null, speedKmh: null,
    });
  });
});

describe('filterByRange', () => {
  const pts = [{ date: '2026-07-01' }, { date: '2026-09-20' }, { date: '2026-10-10' }];
  it('4주 / 3개월 / 전체', () => {
    expect(filterByRange(pts, '4w', '2026-10-17')).toEqual([{ date: '2026-09-20' }, { date: '2026-10-10' }]);
    expect(filterByRange(pts, '3m', '2026-10-17')).toEqual([{ date: '2026-09-20' }, { date: '2026-10-10' }]);
    expect(filterByRange(pts, 'all', '2026-10-17')).toHaveLength(3);
  });
});
