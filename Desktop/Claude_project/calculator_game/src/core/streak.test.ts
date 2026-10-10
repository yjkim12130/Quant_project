import { describe, it, expect } from 'vitest';
import { daysBetween, displayStreak, emptyStreak, isoWeekKey, recordPlay, toLocalDateString } from './streak';

describe('날짜 유틸', () => {
  it('로컬 날짜를 YYYY-MM-DD로 만든다', () => {
    expect(toLocalDateString(new Date(2026, 9, 5, 23, 59))).toBe('2026-10-05');
  });

  it('날짜 사이 일수를 센다 (월 경계 포함)', () => {
    expect(daysBetween('2026-09-30', '2026-10-01')).toBe(1);
    expect(daysBetween('2026-10-10', '2026-10-10')).toBe(0);
    expect(daysBetween('2026-10-01', '2026-10-04')).toBe(3);
  });

  it('ISO 주 키를 만든다', () => {
    expect(isoWeekKey('2026-10-10')).toBe('2026-W41');
    expect(isoWeekKey('2025-12-29')).toBe('2026-W01');
    expect(isoWeekKey('2026-10-05')).toBe(isoWeekKey('2026-10-11')); // 월~일 같은 주
    expect(isoWeekKey('2026-10-12')).not.toBe(isoWeekKey('2026-10-11'));
  });
});

describe('recordPlay', () => {
  const s = (count: number, last: string | null, freeze: string | null = null) => ({
    count, lastPlayedDate: last, freezeUsedWeek: freeze,
  });

  it('처음 플레이하면 1', () => {
    expect(recordPlay(emptyStreak(), '2026-10-10')).toEqual(s(1, '2026-10-10'));
  });

  it('같은 날 다시 하면 그대로', () => {
    expect(recordPlay(s(3, '2026-10-10'), '2026-10-10')).toEqual(s(3, '2026-10-10'));
  });

  it('어제 했으면 +1', () => {
    expect(recordPlay(s(3, '2026-10-09'), '2026-10-10')).toEqual(s(4, '2026-10-10'));
  });

  it('하루 걸렀고 이번 주 얼리기를 안 썼으면 얼리기를 쓰고 +1', () => {
    expect(recordPlay(s(3, '2026-10-07'), '2026-10-09')).toEqual(s(4, '2026-10-09', isoWeekKey('2026-10-09')));
  });

  it('하루 걸렀는데 이번 주 얼리기를 이미 썼으면 1로 리셋', () => {
    const week = isoWeekKey('2026-10-09');
    expect(recordPlay(s(3, '2026-10-07', week), '2026-10-09')).toEqual(s(1, '2026-10-09', week));
  });

  it('지난주에 쓴 얼리기는 이번 주에 다시 쓸 수 있다', () => {
    const lastWeek = isoWeekKey('2026-10-01');
    expect(recordPlay(s(5, '2026-10-07', lastWeek), '2026-10-09').count).toBe(6);
  });

  it('이틀 이상 거르면 1로 리셋', () => {
    expect(recordPlay(s(9, '2026-10-06'), '2026-10-09').count).toBe(1);
  });
});

describe('displayStreak', () => {
  const s = (count: number, last: string | null, freeze: string | null = null) => ({
    count, lastPlayedDate: last, freezeUsedWeek: freeze,
  });

  it('오늘/어제 했으면 그대로 보여준다', () => {
    expect(displayStreak(s(4, '2026-10-10'), '2026-10-10')).toBe(4);
    expect(displayStreak(s(4, '2026-10-09'), '2026-10-10')).toBe(4);
  });

  it('하루 걸렀어도 얼리기가 남아 있으면 유지', () => {
    expect(displayStreak(s(4, '2026-10-08'), '2026-10-10')).toBe(4);
  });

  it('얼리기를 이미 썼거나 이틀 이상 걸렀으면 0', () => {
    expect(displayStreak(s(4, '2026-10-08', isoWeekKey('2026-10-10')), '2026-10-10')).toBe(0);
    expect(displayStreak(s(4, '2026-10-06'), '2026-10-10')).toBe(0);
    expect(displayStreak(emptyStreak(), '2026-10-10')).toBe(0);
  });
});
