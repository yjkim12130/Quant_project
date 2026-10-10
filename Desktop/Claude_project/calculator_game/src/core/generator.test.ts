import { describe, it, expect } from 'vitest';
import { generateLesson, makeChoices, makeQuestion, pickKind, resultOf } from './generator';
import { STAGES, getStage } from './stages';
import { mulberry32 } from './random';

describe('resultOf', () => {
  it('네 연산의 결과를 계산한다', () => {
    expect(resultOf({ op: 'add', a: 3, b: 4 })).toBe(7);
    expect(resultOf({ op: 'sub', a: 9, b: 4 })).toBe(5);
    expect(resultOf({ op: 'mul', a: 6, b: 7 })).toBe(42);
    expect(resultOf({ op: 'div', a: 42, b: 7 })).toBe(6);
  });
});

describe('makeChoices', () => {
  it('모든 단계에서 보기 4개가 서로 다르고, 정답을 포함하고, 0 이상이다', () => {
    const rng = mulberry32(11);
    for (const stage of STAGES) {
      for (let i = 0; i < 300; i++) {
        const o = stage.make(rng);
        const answer = resultOf(o);
        const choices = makeChoices(rng, o, answer);
        expect(choices).toHaveLength(4);
        expect(new Set(choices).size).toBe(4);
        expect(choices).toContain(answer);
        for (const c of choices) expect(c).toBeGreaterThanOrEqual(0);
      }
    }
  });

  it('정답이 0이어도 보기 4개를 만든다', () => {
    const choices = makeChoices(mulberry32(1), { op: 'sub', a: 3, b: 3 }, 0);
    expect(new Set(choices).size).toBe(4);
    expect(choices).toContain(0);
  });
});

describe('pickKind', () => {
  it('왕관 0개일 때 객관식이 약 70% 나온다', () => {
    const rng = mulberry32(5);
    const stage = getStage('u4s1');
    const n = 10000;
    let choice = 0;
    for (let i = 0; i < n; i++) if (pickKind(rng, stage, 0) === 'choice') choice++;
    expect(choice / n).toBeGreaterThan(0.67);
    expect(choice / n).toBeLessThan(0.73);
  });

  it('왕관 2개 이상이면 키패드가 가장 많다', () => {
    const rng = mulberry32(6);
    const stage = getStage('u4s1');
    const counts = { choice: 0, keypad: 0, blank: 0, picture: 0 };
    for (let i = 0; i < 10000; i++) counts[pickKind(rng, stage, 3)]++;
    expect(counts.keypad / 10000).toBeGreaterThan(0.47);
    expect(counts.keypad / 10000).toBeLessThan(0.53);
    expect(counts.picture).toBe(0);
  });

  it('picture=priority 단계는 객관식 몫을 모두 그림 문제로 낸다', () => {
    const rng = mulberry32(7);
    for (let i = 0; i < 2000; i++) expect(pickKind(rng, getStage('u1s1'), 0)).not.toBe('choice');
  });

  it('preferBlank 단계는 키패드 대신 빈칸을 낸다', () => {
    const rng = mulberry32(8);
    for (let i = 0; i < 2000; i++) expect(pickKind(rng, getStage('u1s4'), 2)).not.toBe('keypad');
  });
});

describe('makeQuestion', () => {
  it('blank 문제의 답은 b이고, 그 외는 계산 결과다', () => {
    const rng = mulberry32(3);
    const stage = getStage('u4s4');
    const blank = makeQuestion(rng, stage, 'blank', 0);
    expect(blank.answer).toBe(blank.b);
    expect(blank.result).toBe(blank.a * blank.b);
    expect(blank.choices).toBeUndefined();
    const keypad = makeQuestion(rng, stage, 'keypad', 1);
    expect(keypad.answer).toBe(keypad.result);
  });

  it('곱셈·나눗셈에 picture를 요청하면 choice로 바꾼다', () => {
    const q = makeQuestion(mulberry32(1), getStage('u4s1'), 'picture', 0);
    expect(q.kind).toBe('choice');
    expect(q.choices).toHaveLength(4);
  });
});

describe('generateLesson', () => {
  it('10문제를 만들고, 같은 시드면 같은 레슨이다', () => {
    const a = generateLesson(getStage('u3s2'), 0, 99);
    const b = generateLesson(getStage('u3s2'), 0, 99);
    expect(a).toHaveLength(10);
    expect(a).toEqual(b);
  });

  it('같은 수식이 연속으로 나오지 않는다 (경우의 수가 적은 단계 포함)', () => {
    for (const id of ['u1s4', 'u4s1', 'u2s1']) {
      for (let seed = 0; seed < 200; seed++) {
        const qs = generateLesson(getStage(id), 0, seed);
        for (let i = 1; i < qs.length; i++) expect(qs[i].key).not.toBe(qs[i - 1].key);
      }
    }
  });

  it('id는 레슨 안에서 모두 다르다', () => {
    const qs = generateLesson(getStage('u4s1'), 0, 1);
    expect(new Set(qs.map((q) => q.id)).size).toBe(10);
  });
});
