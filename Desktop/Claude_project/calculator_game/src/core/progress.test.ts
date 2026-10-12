import { describe, it, expect } from 'vitest';
import { applyLesson } from './progress';
import { emptyStats, type LessonOutcome } from './scoring';
import type { Profile } from './types';

const profile = (over: Partial<Profile> = {}): Profile => ({
  id: 'p1', name: '하늘', avatar: '🐶', xp: 0,
  streak: { count: 0, lastPlayedDate: null, freezeUsedWeek: null },
  stages: {}, stats: emptyStats(), ...over,
});

const outcome = (firstTryCorrect: number, heartsLeft = 5): LessonOutcome => {
  const stats = emptyStats();
  stats.add = { correct: firstTryCorrect, total: 10 };
  return { firstTryCorrect, total: 10, heartsLeft, stats };
};

describe('applyLesson', () => {
  it('통과하면 XP·왕관·스트릭·통계가 오른다', () => {
    const { profile: p, summary } = applyLesson(profile(), 'u1s1', outcome(10), '2026-10-10');
    expect(p.xp).toBe(130);
    expect(p.stages.u1s1).toEqual({ crowns: 1, bestAccuracy: 1 });
    expect(p.streak.count).toBe(1);
    expect(p.stats.add).toEqual({ correct: 10, total: 10 });
    expect(summary).toMatchObject({
      xpGained: 130, accuracy: 1, passed: true, perfect: true, crowns: 1,
      stageCompleted: false, levelBefore: 1, levelAfter: 2, streak: 1,
    });
  });

  it('실패하면 왕관은 그대로지만 XP와 스트릭은 인정된다', () => {
    const { profile: p, summary } = applyLesson(profile(), 'u1s1', outcome(5, 0), '2026-10-10');
    expect(p.stages.u1s1.crowns).toBe(0);
    expect(p.xp).toBe(70);
    expect(p.streak.count).toBe(1);
    expect(summary.passed).toBe(false);
  });

  it('세 번째 왕관을 받는 순간에만 stageCompleted', () => {
    const start = profile({ stages: { u1s1: { crowns: 2, bestAccuracy: 0.8 } } });
    const first = applyLesson(start, 'u1s1', outcome(9), '2026-10-10');
    expect(first.summary.crowns).toBe(3);
    expect(first.summary.stageCompleted).toBe(true);
    const again = applyLesson(first.profile, 'u1s1', outcome(10), '2026-10-10');
    expect(again.summary.crowns).toBe(3);
    expect(again.summary.stageCompleted).toBe(false);
  });

  it('최고 정답률은 내려가지 않는다', () => {
    const start = profile({ stages: { u1s1: { crowns: 1, bestAccuracy: 0.9 } } });
    const { profile: p } = applyLesson(start, 'u1s1', outcome(7), '2026-10-10');
    expect(p.stages.u1s1.bestAccuracy).toBe(0.9);
  });

  it('원본 프로필을 바꾸지 않는다', () => {
    const start = profile();
    applyLesson(start, 'u1s1', outcome(10), '2026-10-10');
    expect(start.xp).toBe(0);
    expect(start.stats.add.total).toBe(0);
  });
});
