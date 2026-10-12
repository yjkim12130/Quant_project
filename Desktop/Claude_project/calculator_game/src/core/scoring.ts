import type { OpStats } from './types';

export const XP_CORRECT = 10;
export const XP_LESSON = 20;
export const XP_PERFECT = 10;
export const PASS_ACCURACY = 0.7;

export interface LessonOutcome {
  firstTryCorrect: number;
  total: number;
  heartsLeft: number;
  stats: OpStats;
}

export function emptyStats(): OpStats {
  return {
    add: { correct: 0, total: 0 },
    sub: { correct: 0, total: 0 },
    mul: { correct: 0, total: 0 },
    div: { correct: 0, total: 0 },
  };
}

export function lessonXp(o: LessonOutcome): number {
  const perfect = o.total > 0 && o.firstTryCorrect === o.total;
  return o.firstTryCorrect * XP_CORRECT + XP_LESSON + (perfect ? XP_PERFECT : 0);
}

export function accuracy(o: LessonOutcome): number {
  return o.total === 0 ? 0 : o.firstTryCorrect / o.total;
}

export function isPassed(o: LessonOutcome): boolean {
  return accuracy(o) >= PASS_ACCURACY && o.heartsLeft > 0;
}

// 레벨 n → n+1 에 필요한 누적 XP = 50·n·(n+1)
export function levelFromXp(xp: number): number {
  let level = 1;
  while (xp >= 50 * level * (level + 1)) level++;
  return level;
}

export function xpForLevel(level: number): number {
  return 50 * (level - 1) * level;
}
