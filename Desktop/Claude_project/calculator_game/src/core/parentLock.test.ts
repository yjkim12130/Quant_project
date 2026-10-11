import { describe, it, expect } from 'vitest';
import { makeParentChallenge } from './parentLock';
import { mulberry32 } from './random';

describe('makeParentChallenge', () => {
  it('두 자리 × 한 자리 곱셈을 만든다', () => {
    const rng = mulberry32(1);
    for (let i = 0; i < 200; i++) {
      const c = makeParentChallenge(rng);
      expect(c.a).toBeGreaterThanOrEqual(12);
      expect(c.a).toBeLessThanOrEqual(29);
      expect(c.b).toBeGreaterThanOrEqual(3);
      expect(c.b).toBeLessThanOrEqual(9);
      expect(c.answer).toBe(c.a * c.b);
    }
  });
});
