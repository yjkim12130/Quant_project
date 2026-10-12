import { describe, it, expect } from 'vitest';
import { STAGES, getStage, stageIndex } from './stages';
import { mulberry32 } from './random';
import type { Operands } from './types';

const between = (n: number, lo: number, hi: number) => n >= lo && n <= hi;
const isAdd = (q: Operands) => q.op === 'add';
const isSub = (q: Operands) => q.op === 'sub';
const mulOf = (ds: number[]) => (q: Operands) => q.op === 'mul' && ds.includes(q.a) && between(q.b, 1, 9);
const divOf = (ds: number[]) => (q: Operands) =>
  q.op === 'div' && ds.includes(q.b) && q.a % q.b === 0 && between(q.a / q.b, 1, 9);
const range = (lo: number, hi: number) => Array.from({ length: hi - lo + 1 }, (_, i) => lo + i);
const all = range(1, 9);

const RULES: Record<string, (q: Operands) => boolean> = {
  u1s1: (q) => isAdd(q) && between(q.a, 1, 8) && between(q.b, 1, 2),
  ...Object.fromEntries(range(1, 9).map((n) => [`u1s${n + 1}`, (q: Operands) => isAdd(q) && between(q.a, 1, 9) && q.b === n])),
  u1s11: (q) => isAdd(q) && q.a >= 1 && q.b >= 1 && q.a + q.b === 10,
  u2s1: (q) => isSub(q) && between(q.a, 2, 6) && between(q.b, 1, 2),
  ...Object.fromEntries(range(1, 9).map((n) => [`u2s${n + 1}`, (q: Operands) => isSub(q) && q.b === n && between(q.a - q.b, 0, 9)])),
  u3s1: (q) => isAdd(q) && between(q.a, 2, 9) && between(q.b, 2, 9) && between(q.a + q.b, 11, 18),
  u3s2: (q) => isSub(q) && between(q.a, 11, 18) && between(q.b, 2, 9) && q.a % 10 < q.b,
  u3s3: (q) =>
    (isAdd(q) && between(q.a, 10, 19) && q.b >= 1 && (q.a % 10) + q.b <= 9) || RULES.u3s1(q) || RULES.u3s2(q),
  ...Object.fromEntries(range(1, 5).map((d) => [`u4s${d}`, mulOf([d])])),
  ...Object.fromEntries(range(6, 9).map((d) => [`u5s${d - 5}`, mulOf([d])])),
  u5s5: mulOf(all),
  ...Object.fromEntries(range(1, 9).map((d) => [`u6s${d}`, divOf([d])])),
  u6s10: (q) => mulOf(all)(q) || divOf(all)(q),
};

describe('STAGES', () => {
  it('단계 44개이고 ID가 규칙표와 일치한다', () => {
    expect(STAGES.map((s) => s.id)).toEqual(Object.keys(RULES));
  });

  it.each(STAGES.map((s, i) => [s.id, i] as const))('%s 는 1000문제 모두 규칙을 지킨다', (id, i) => {
    const stage = getStage(id);
    const rng = mulberry32(i + 1);
    for (let n = 0; n < 1000; n++) {
      const q = stage.make(rng);
      expect(RULES[id](q), `${id}: ${JSON.stringify(q)}`).toBe(true);
    }
  });

  it('getStage는 없는 ID에 에러, stageIndex는 -1', () => {
    expect(() => getStage('nope')).toThrow();
    expect(stageIndex('nope')).toBe(-1);
    expect(stageIndex('u1s1')).toBe(0);
    expect(stageIndex('u6s10')).toBe(43);
  });

  it('그림 문제는 유닛 1~2에만, 나눗셈 힌트는 u6s1에만', () => {
    for (const s of STAGES) {
      if (s.unit > 2) expect(s.picture).toBe('none');
    }
    expect(getStage('u1s1').picture).toBe('priority');
    expect(getStage('u2s1').picture).toBe('priority');
    expect(getStage('u1s11').preferBlank).toBe(true);
    expect(getStage('u6s1').hint).toContain('구구단 거꾸로');
  });

  it('구구단은 1~9단, 나눗셈은 1~9로 나누기가 모두 있다', () => {
    expect(STAGES.filter((s) => /^\d단$/.test(s.title)).map((s) => s.title)).toEqual(all.map((d) => `${d}단`));
    expect(STAGES.filter((s) => s.unit === 6).map((s) => s.title)).toEqual([
      '1로 나누기', '2로 나누기', '3으로 나누기', '4로 나누기', '5로 나누기',
      '6으로 나누기', '7로 나누기', '8로 나누기', '9로 나누기', '곱셈 나눗셈 섞기',
    ]);
  });
});
