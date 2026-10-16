import { describe, expect, it } from 'vitest';
import { DEFAULT_CARDIO, DEFAULT_WEIGHT } from '../defaults';
import type { CardioHistoryItem, Exercise, WeightHistoryItem } from '../types';
import { isStalled, recommend, recommendCardio, recommendWeight } from './rules';

const today = '2026-10-17';
const cfg = { ...DEFAULT_WEIGHT };
const s = (weight: number, reps: number) => [{ weight, reps }];
const day = (date: string, sets: WeightHistoryItem['sets']): WeightHistoryItem => ({ date, sets });

describe('isStalled', () => {
  it('최근 2회가 모두 그 이전 최고보다 낮으면 정체', () => {
    expect(isStalled([133, 126, 130])).toBe(true);
    expect(isStalled([126, 130, 133])).toBe(false);
    expect(isStalled([133, 140, 130])).toBe(false);
  });
  it('기록이 3개 미만이면 정체 아님', () => {
    expect(isStalled([133, 120])).toBe(false);
  });
});

describe('recommendWeight', () => {
  it('기록이 없으면 first', () => {
    expect(recommendWeight(cfg, [], today)).toEqual({ status: 'first' });
  });
  it('오늘 기록은 기준에서 제외한다', () => {
    expect(recommendWeight(cfg, [day(today, [s(40, 12)])], today)).toEqual({ status: 'first' });
  });
  it('더블 → main 옵션', () => {
    const rec = recommendWeight(cfg, [day('2026-10-14', [s(40, 12), s(40, 10), s(40, 9)])], today);
    expect(rec).toEqual({
      status: 'ok',
      options: [{
        id: 'main', label: '더블 프로그레션',
        target: { type: 'double', sets: [{ weight: 40, reps: 12 }, { weight: 40, reps: 11 }, { weight: 40, reps: 10 }] },
      }],
    });
  });
  it('볼륨 → 횟수안·무게안', () => {
    const rec = recommendWeight({ ...cfg, progression: 'volume' }, [day('2026-10-14', [s(50, 10), s(50, 10), s(50, 10)])], today);
    if (rec.status !== 'ok') throw new Error('ok 기대');
    expect(rec.options.map((o) => o.id)).toEqual(['reps', 'weight']);
    expect(rec.options[0].target).toMatchObject({ type: 'volume', volume: 1545 });
  });
  it('14일 초과 공백 → 지난번 그대로', () => {
    const rec = recommendWeight(cfg, [day('2026-10-02', [[{ weight: 40, reps: 10 }, { weight: 30, reps: 4 }], s(40, 9)])], today);
    expect(rec).toEqual({
      status: 'ok',
      note: '15일 만의 복귀 — 지난번 그대로 반복해요',
      options: [{
        id: 'repeat', label: '지난번 그대로',
        target: { type: 'double', sets: [{ weight: 40, reps: 10 }, { weight: 40, reps: 9 }] },
      }],
    });
  });
  it('정확히 14일이면 정상 추천', () => {
    const rec = recommendWeight(cfg, [day('2026-10-03', [s(40, 10)])], today);
    if (rec.status !== 'ok') throw new Error('ok 기대');
    expect(rec.options[0].id).toBe('main');
  });
  it('정체면 디로드 옵션과 안내 문구 추가', () => {
    const history = [day('2026-10-10', [s(100, 10)]), day('2026-10-12', [s(100, 8)]), day('2026-10-14', [s(100, 9)])];
    const rec = recommendWeight(cfg, history, today);
    if (rec.status !== 'ok') throw new Error('ok 기대');
    expect(rec.note).toBe('최근 2회 연속 정체 — 디로드(90%)를 고려해 보세요');
    expect(rec.options.at(-1)).toEqual({
      id: 'deload', label: '디로드 90%',
      target: { type: 'double', sets: [{ weight: 90, reps: 8 }, { weight: 90, reps: 8 }, { weight: 90, reps: 8 }] },
    });
  });
});

describe('recommendCardio', () => {
  const ccfg = { ...DEFAULT_CARDIO };
  const item = (date: string, minutes: number, level: number): CardioHistoryItem => ({ date, minutes, intensity: { level } });
  it('first / main / repeat', () => {
    expect(recommendCardio(ccfg, [], today)).toEqual({ status: 'first' });
    expect(recommendCardio(ccfg, [item('2026-10-16', 30, 8)], today)).toEqual({
      status: 'ok',
      options: [{ id: 'main', label: '시간→강도', target: { type: 'cardio', minutes: 20, intensity: { level: 9 } } }],
    });
    const back = recommendCardio(ccfg, [item('2026-09-01', 25, 8)], today);
    expect(back).toMatchObject({ status: 'ok', options: [{ id: 'repeat', target: { type: 'cardio', minutes: 25, intensity: { level: 8 } } }] });
  });
});

describe('recommend', () => {
  it('운동 종류에 따라 분기', () => {
    const ex: Exercise = {
      id: 'c', equipment: '사이클', name: '인터벌', kind: 'cardio', archived: false,
      restSeconds: 90, createdAt: 1, cardio: { ...DEFAULT_CARDIO },
    };
    expect(recommend(ex, [], today)).toEqual({ status: 'first' });
  });
});
