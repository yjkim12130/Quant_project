import { emptyStats, type LessonOutcome } from './scoring';
import type { OpStats, Question } from './types';

export const START_HEARTS = 5;

export interface LessonItem {
  q: Question;
  review: boolean;
}

export interface LastAnswer {
  correct: boolean;
  timedOut: boolean;
  review: boolean;
}

export interface LessonState {
  items: LessonItem[];
  index: number;
  mainTotal: number;
  answeredMain: number;
  firstTryCorrect: number;
  hearts: number;
  inARow: number;
  stats: OpStats;
  phase: 'answering' | 'feedback' | 'done';
  last: LastAnswer | null;
}

export function startLesson(questions: Question[]): LessonState {
  return {
    items: questions.map((q) => ({ q, review: false })),
    index: 0,
    mainTotal: questions.length,
    answeredMain: 0,
    firstTryCorrect: 0,
    hearts: START_HEARTS,
    inARow: 0,
    stats: emptyStats(),
    phase: questions.length ? 'answering' : 'done',
    last: null,
  };
}

export function currentItem(s: LessonState): LessonItem | null {
  return s.phase === 'done' ? null : s.items[s.index] ?? null;
}

export function submitAnswer(s: LessonState, value: number | null): LessonState {
  const item = currentItem(s);
  if (s.phase !== 'answering' || !item) return s;
  const timedOut = value === null;
  const correct = !timedOut && value === item.q.answer;
  const next: LessonState = {
    ...s,
    phase: 'feedback',
    inARow: correct ? s.inARow + 1 : 0,
    last: { correct, timedOut, review: item.review },
  };
  if (item.review) return next;

  const op = item.q.op;
  next.answeredMain = s.answeredMain + 1;
  next.stats = { ...s.stats, [op]: { correct: s.stats[op].correct + (correct ? 1 : 0), total: s.stats[op].total + 1 } };
  if (correct) {
    next.firstTryCorrect = s.firstTryCorrect + 1;
  } else {
    if (!timedOut) next.hearts = Math.max(0, s.hearts - 1);
    next.items = [...s.items, { q: item.q, review: true }];
  }
  return next;
}

export function nextQuestion(s: LessonState): LessonState {
  if (s.phase !== 'feedback') return s;
  const index = s.index + 1;
  return { ...s, index, phase: index >= s.items.length ? 'done' : 'answering' };
}

export function lessonProgress(s: LessonState): number {
  return s.mainTotal === 0 ? 1 : s.answeredMain / s.mainTotal;
}

export function toOutcome(s: LessonState): LessonOutcome {
  return { firstTryCorrect: s.firstTryCorrect, total: s.mainTotal, heartsLeft: s.hearts, stats: s.stats };
}
