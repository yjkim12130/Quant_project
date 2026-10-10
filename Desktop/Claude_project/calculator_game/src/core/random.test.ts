import { describe, it, expect } from 'vitest';
import { mulberry32, randInt, pick, shuffle } from './random';

describe('mulberry32', () => {
  it('같은 시드는 같은 수열을 만든다', () => {
    const a = mulberry32(42);
    const b = mulberry32(42);
    const seqA = Array.from({ length: 5 }, () => a());
    const seqB = Array.from({ length: 5 }, () => b());
    expect(seqA).toEqual(seqB);
  });

  it('다른 시드는 다른 수열을 만든다', () => {
    expect(mulberry32(1)()).not.toBe(mulberry32(2)());
  });

  it('0 이상 1 미만의 값을 만든다', () => {
    const rng = mulberry32(7);
    for (let i = 0; i < 1000; i++) {
      const v = rng();
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    }
  });
});

describe('randInt', () => {
  it('양 끝을 포함한 범위의 정수를 모두 만든다', () => {
    const rng = mulberry32(3);
    const seen = new Set<number>();
    for (let i = 0; i < 500; i++) {
      const v = randInt(rng, 2, 5);
      expect(Number.isInteger(v)).toBe(true);
      seen.add(v);
    }
    expect([...seen].sort()).toEqual([2, 3, 4, 5]);
  });
});

describe('pick / shuffle', () => {
  it('pick은 배열 안의 값을 고른다', () => {
    const rng = mulberry32(5);
    for (let i = 0; i < 50; i++) expect(['a', 'b', 'c']).toContain(pick(rng, ['a', 'b', 'c']));
  });

  it('shuffle은 원본을 바꾸지 않고 같은 원소를 돌려준다', () => {
    const src = [1, 2, 3, 4, 5];
    const out = shuffle(mulberry32(9), src);
    expect(src).toEqual([1, 2, 3, 4, 5]);
    expect([...out].sort()).toEqual([1, 2, 3, 4, 5]);
  });
});
