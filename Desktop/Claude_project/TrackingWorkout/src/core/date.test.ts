import { describe, expect, it } from 'vitest';
import { addDays, daysBetween, shortDate, todayLocal } from './date';

describe('date', () => {
  it('todayLocal은 로컬 날짜를 YYYY-MM-DD로', () => {
    expect(todayLocal(new Date(2026, 9, 17, 23, 30))).toBe('2026-10-17');
    expect(todayLocal(new Date(2026, 0, 5, 0, 1))).toBe('2026-01-05');
  });
  it('addDays는 월말을 넘긴다', () => {
    expect(addDays('2026-10-31', 1)).toBe('2026-11-01');
    expect(addDays('2026-03-01', -1)).toBe('2026-02-28');
  });
  it('daysBetween', () => {
    expect(daysBetween('2026-10-01', '2026-10-17')).toBe(16);
    expect(daysBetween('2026-10-17', '2026-10-17')).toBe(0);
  });
  it('shortDate', () => {
    expect(shortDate('2026-10-04')).toBe('10/4');
  });
});
