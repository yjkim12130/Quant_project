import { describe, it, expect } from 'vitest';
import { STAGES, UNITS, getStage, stageIndex } from './stages';
import { mulberry32 } from './random';
import type { Operands } from './types';

const between = (n: number, lo: number, hi: number) => n >= lo && n <= hi;
const isAdd = (q: Operands) => q.op === 'add';
const isSub = (q: Operands) => q.op === 'sub';
const mulOf = (ds: number[]) => (q: Operands) => q.op === 'mul' && ds.includes(q.a) && between(q.b, 1, 9);
const divOf = (ds: number[]) => (q: Operands) =>
  q.op === 'div' && ds.includes(q.b) && q.a % q.b === 0 && between(q.a / q.b, 1, 9);
const all = [2, 3, 4, 5, 6, 7, 8, 9];

const RULES: Record<string, (q: Operands) => boolean> = {
  u1s1: (q) => isAdd(q) && between(q.a, 1, 8) && between(q.b, 1, 2),
  u1s2: (q) => isAdd(q) && q.a >= 1 && q.b >= 1 && q.a + q.b <= 5,
  u1s3: (q) => isAdd(q) && q.a >= 1 && q.b >= 1 && q.a + q.b <= 10,
  u1s4: (q) => isAdd(q) && q.a >= 1 && q.b >= 1 && q.a + q.b === 10,
  u2s1: (q) => isSub(q) && between(q.a, 2, 6) && between(q.b, 1, 2),
  u2s2: (q) => isSub(q) && q.a <= 5 && q.b >= 1 && q.a - q.b >= 0,
  u2s3: (q) => isSub(q) && q.a <= 10 && q.b >= 1 && q.a - q.b >= 0,
  u2s4: (q) => RULES.u1s3(q) || RULES.u2s3(q),
  u3s1: (q) => isAdd(q) && between(q.a, 10, 19) && q.b >= 1 && (q.a % 10) + q.b <= 9 && q.a + q.b <= 19,
  u3s2: (q) => isAdd(q) && between(q.a, 2, 9) && between(q.b, 2, 9) && between(q.a + q.b, 11, 18),
  u3s3: (q) => isSub(q) && between(q.a, 11, 18) && between(q.b, 2, 9) && q.a % 10 < q.b,
  u3s4: (q) => RULES.u3s1(q) || RULES.u3s2(q) || RULES.u3s3(q),
  u4s1: mulOf([2]),
  u4s2: mulOf([5]),
  u4s3: mulOf([3]),
  u4s4: mulOf([4]),
  u5s1: mulOf([6]),
  u5s2: mulOf([7]),
  u5s3: mulOf([8, 9]),
  u5s4: mulOf(all),
  u6s1: divOf([2, 5]),
  u6s2: divOf([3, 4]),
  u6s3: divOf([6, 7, 8, 9]),
  u6s4: (q) => mulOf(all)(q) || divOf(all)(q),
};

describe('STAGES', () => {
  it('유닛 6개, 단계 24개이고 ID가 규칙표와 일치한다', () => {
    expect(UNITS).toHaveLength(6);
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
    expect(stageIndex('u6s4')).toBe(23);
  });

  it('그림 문제는 유닛 1~2에만, 나눗셈 힌트는 u6s1에만', () => {
    for (const s of STAGES) {
      if (s.unit > 2) expect(s.picture).toBe('none');
    }
    expect(getStage('u1s1').picture).toBe('priority');
    expect(getStage('u2s1').picture).toBe('priority');
    expect(getStage('u1s4').preferBlank).toBe(true);
    expect(getStage('u6s1').hint).toContain('구구단 거꾸로');
  });
});
