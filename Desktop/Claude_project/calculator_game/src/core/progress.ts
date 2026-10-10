import { accuracy, isPassed, lessonXp, levelFromXp, type LessonOutcome } from './scoring';
import { STAGES, stageIndex } from './stages';
import { recordPlay } from './streak';
import type { Op, OpStats, Profile } from './types';

export interface LessonSummary {
  xpGained: number;
  accuracy: number;
  passed: boolean;
  perfect: boolean;
  crowns: number;
  stageCompleted: boolean;
  levelBefore: number;
  levelAfter: number;
  streak: number;
}

function mergeStats(a: OpStats, b: OpStats): OpStats {
  const out = { ...a };
  for (const op of Object.keys(out) as Op[]) {
    out[op] = { correct: a[op].correct + b[op].correct, total: a[op].total + b[op].total };
  }
  return out;
}

export function applyLesson(
  profile: Profile,
  stageId: string,
  outcome: LessonOutcome,
  today: string,
): { profile: Profile; summary: LessonSummary } {
  const xpGained = lessonXp(outcome);
  const acc = accuracy(outcome);
  const passed = isPassed(outcome);
  const prev = profile.stages[stageId] ?? { crowns: 0, bestAccuracy: 0 };
  const crowns = passed ? Math.min(3, prev.crowns + 1) : prev.crowns;
  const streak = recordPlay(profile.streak, today);
  const next: Profile = {
    ...profile,
    xp: profile.xp + xpGained,
    streak,
    stages: { ...profile.stages, [stageId]: { crowns, bestAccuracy: Math.max(prev.bestAccuracy, acc) } },
    stats: mergeStats(profile.stats, outcome.stats),
  };
  return {
    profile: next,
    summary: {
      xpGained,
      accuracy: acc,
      passed,
      perfect: outcome.total > 0 && outcome.firstTryCorrect === outcome.total,
      crowns,
      stageCompleted: prev.crowns < 3 && crowns === 3,
      levelBefore: levelFromXp(profile.xp),
      levelAfter: levelFromXp(next.xp),
      streak: streak.count,
    },
  };
}

export function withStartStage(profile: Profile, stageId: string): Profile {
  const idx = stageIndex(stageId);
  const stages = { ...profile.stages };
  STAGES.forEach((s, i) => {
    if (i < idx) stages[s.id] = { crowns: 3, bestAccuracy: stages[s.id]?.bestAccuracy ?? 0 };
  });
  return { ...profile, stages };
}
