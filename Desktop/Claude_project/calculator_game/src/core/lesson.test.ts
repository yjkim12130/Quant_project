import { describe, it, expect } from 'vitest';
import { currentItem, lessonProgress, nextQuestion, startLesson, submitAnswer, toOutcome, type LessonState } from './lesson';
import type { Question } from './types';

const q = (i: number, answer = i + 1): Question => ({
  id: `${i}`, key: `add:${i}:1`, op: 'add', a: i, b: 1, result: i + 1, answer, kind: 'keypad',
});
const lesson = (n = 10) => startLesson(Array.from({ length: n }, (_, i) => q(i)));
const answer = (s: LessonState, correct: boolean) =>
  nextQuestion(submitAnswer(s, correct ? currentItem(s)!.q.answer : -1));

describe('lesson', () => {
  it('시작 상태', () => {
    const s = lesson();
    expect(s.phase).toBe('answering');
    expect(s.hearts).toBe(5);
    expect(currentItem(s)?.q.id).toBe('0');
    expect(lessonProgress(s)).toBe(0);
  });

  it('정답이면 점수가 오르고 피드백 단계가 된다', () => {
    const s = submitAnswer(lesson(), 1);
    expect(s.phase).toBe('feedback');
    expect(s.last).toEqual({ correct: true, timedOut: false, review: false });
    expect(s.firstTryCorrect).toBe(1);
    expect(s.hearts).toBe(5);
    expect(s.inARow).toBe(1);
    expect(s.stats.add).toEqual({ correct: 1, total: 1 });
    expect(lessonProgress(s)).toBeCloseTo(0.1);
  });

  it('오답이면 하트가 줄고 복습 문제가 끝에 붙는다', () => {
    const s = submitAnswer(lesson(), 99);
    expect(s.last).toEqual({ correct: false, timedOut: false, review: false });
    expect(s.hearts).toBe(4);
    expect(s.items).toHaveLength(11);
    expect(s.items[10]).toEqual({ q: q(0), review: true });
    expect(s.inARow).toBe(0);
    expect(s.stats.add).toEqual({ correct: 0, total: 1 });
  });

  it('시간 초과는 하트를 깎지 않지만 오답으로 세고 복습에 넣는다', () => {
    const s = submitAnswer(lesson(), null);
    expect(s.last).toEqual({ correct: false, timedOut: true, review: false });
    expect(s.hearts).toBe(5);
    expect(s.firstTryCorrect).toBe(0);
    expect(s.items).toHaveLength(11);
  });

  it('피드백 단계에서는 답을 다시 받지 않는다', () => {
    const s = submitAnswer(lesson(), 1);
    expect(submitAnswer(s, 1)).toBe(s);
  });

  it('하트는 0 아래로 내려가지 않는다', () => {
    let s = lesson();
    for (let i = 0; i < 7; i++) s = answer(s, false);
    expect(s.hearts).toBe(0);
  });

  it('복습 문제는 점수·하트·진행도에 영향이 없고 다시 붙지 않는다', () => {
    let s = lesson(2);
    s = answer(s, false); // 0번 오답 → 복습 추가
    s = answer(s, true); // 1번 정답
    expect(currentItem(s)).toEqual({ q: q(0), review: true });
    const before = { hearts: s.hearts, answeredMain: s.answeredMain, firstTryCorrect: s.firstTryCorrect };
    s = submitAnswer(s, 99); // 복습도 오답
    expect(s.last?.review).toBe(true);
    expect(s).toMatchObject(before);
    expect(s.items).toHaveLength(3);
    s = nextQuestion(s);
    expect(s.phase).toBe('done');
    expect(currentItem(s)).toBeNull();
  });

  it('끝까지 풀면 결과를 만든다', () => {
    let s = lesson();
    for (let i = 0; i < 7; i++) s = answer(s, true);
    for (let i = 0; i < 3; i++) s = answer(s, false);
    while (s.phase !== 'done') s = answer(s, true);
    expect(lessonProgress(s)).toBe(1);
    expect(toOutcome(s)).toEqual({
      firstTryCorrect: 7, total: 10, heartsLeft: 2,
      stats: { add: { correct: 7, total: 10 }, sub: { correct: 0, total: 0 }, mul: { correct: 0, total: 0 }, div: { correct: 0, total: 0 } },
    });
  });
});
