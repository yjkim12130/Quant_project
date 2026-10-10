import { mulberry32, shuffle, type Rng } from './random';
import type { StageDef } from './stages';
import type { Op, Operands, Question, QuestionKind } from './types';

export const OP_SYMBOL: Record<Op, string> = { add: '+', sub: '−', mul: '×', div: '÷' };

export function resultOf({ op, a, b }: Operands): number {
  switch (op) {
    case 'add':
      return a + b;
    case 'sub':
      return a - b;
    case 'mul':
      return a * b;
    case 'div':
      return a / b;
  }
}

// 왕관 수(0, 1, 2+)별 객관식·키패드 비율. 나머지는 빈칸.
const KIND_SHARES = [
  { choice: 0.7, keypad: 0.2 },
  { choice: 0.4, keypad: 0.4 },
  { choice: 0.2, keypad: 0.5 },
];

export function pickKind(rng: Rng, stage: StageDef, crowns: number): QuestionKind {
  const share = KIND_SHARES[Math.min(crowns, 2)];
  const r = rng();
  if (r < share.choice) {
    if (stage.picture === 'priority') return 'picture';
    if (stage.picture === 'mixed' && rng() < 0.5) return 'picture';
    return 'choice';
  }
  if (stage.preferBlank) return 'blank';
  return r < share.choice + share.keypad ? 'keypad' : 'blank';
}

export function makeChoices(rng: Rng, { op, a, b }: Operands, answer: number): number[] {
  const candidates = [answer + 1, answer - 1, answer + 2, answer - 2];
  if (op === 'add') candidates.push(Math.abs(a - b)); // 덧셈↔뺄셈 혼동
  if (op === 'sub') candidates.push(a + b);
  if (op === 'mul') candidates.push(a * (b + 1), a * (b - 1)); // 구구단 이웃 값
  if (op === 'div') candidates.push(b);
  const pool = [...new Set(candidates.filter((n) => n >= 0 && n !== answer))];
  let extra = 3;
  while (pool.length < 3) {
    const n = answer + extra++;
    if (!pool.includes(n)) pool.push(n);
  }
  const wrong = shuffle(rng, pool).slice(0, 3);
  return shuffle(rng, [answer, ...wrong]);
}

export function makeQuestion(rng: Rng, stage: StageDef, kind: QuestionKind, index: number): Question {
  const o = stage.make(rng);
  const finalKind: QuestionKind = kind === 'picture' && (o.op === 'mul' || o.op === 'div') ? 'choice' : kind;
  const result = resultOf(o);
  const answer = finalKind === 'blank' ? o.b : result;
  const key = `${o.op}:${o.a}:${o.b}`;
  const q: Question = { ...o, id: `${index}-${key}`, key, result, answer, kind: finalKind };
  if (finalKind === 'choice' || finalKind === 'picture') q.choices = makeChoices(rng, o, answer);
  return q;
}

export function generateLesson(stage: StageDef, crowns: number, seed: number, count = 10): Question[] {
  const rng = mulberry32(seed);
  const used = new Set<string>();
  const out: Question[] = [];
  let prevKey = '';
  for (let i = 0; i < count; i++) {
    const kind = pickKind(rng, stage, crowns);
    let q: Question;
    let tries = 0;
    do {
      q = makeQuestion(rng, stage, kind, i);
      tries++;
      // 연속 중복은 절대 금지, 레슨 내 중복은 30번까지 피해본다
    } while (q.key === prevKey || (used.has(q.key) && tries < 30));
    used.add(q.key);
    prevKey = q.key;
    out.push(q);
  }
  return out;
}
