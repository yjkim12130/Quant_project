import { describe, it, expect } from 'vitest';
import { accuracy, emptyStats, isPassed, lessonXp, levelFromXp, xpForLevel, type LessonOutcome } from './scoring';

const outcome = (firstTryCorrect: number, heartsLeft: number, total = 10): LessonOutcome => ({
  firstTryCorrect, total, heartsLeft, stats: emptyStats(),
});

describe('XP', () => {
  it('무실수 10문제 = 10×10 + 20 + 10 = 130', () => {
    expect(lessonXp(outcome(10, 5))).toBe(130);
  });
  it('7개 정답 = 70 + 20 = 90 (무실수 보너스 없음)', () => {
    expect(lessonXp(outcome(7, 2))).toBe(90);
  });
});

describe('통과 판정', () => {
  it('70% 이상이고 하트가 남으면 통과', () => {
    expect(accuracy(outcome(7, 2))).toBeCloseTo(0.7);
    expect(isPassed(outcome(7, 2))).toBe(true);
  });
  it('69% 이하면 실패', () => {
    expect(isPassed(outcome(6, 1))).toBe(false);
  });
  it('하트가 0이면 정답률이 높아도 실패', () => {
    expect(isPassed(outcome(8, 0))).toBe(false);
  });
  it('문제가 0개면 정답률 0', () => {
    expect(accuracy(outcome(0, 5, 0))).toBe(0);
  });
});

describe('레벨', () => {
  it.each([
    [0, 1], [99, 1], [100, 2], [299, 2], [300, 3], [599, 3], [600, 4],
  ])('XP %i → 레벨 %i', (xp, level) => {
    expect(levelFromXp(xp)).toBe(level);
  });
  it('레벨 시작 XP', () => {
    expect(xpForLevel(1)).toBe(0);
    expect(xpForLevel(2)).toBe(100);
    expect(xpForLevel(4)).toBe(600);
  });
});
