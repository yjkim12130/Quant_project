import { describe, it, expect } from 'vitest';
import { CATEGORIES, categoryCrowns, categoryOf, getCategory } from './categories';
import { STAGES, getStage } from './stages';

describe('CATEGORIES', () => {
  it('덧셈·뺄셈·구구단·나눗셈 4개이고 모든 단계가 어딘가에 들어 있다', () => {
    expect(CATEGORIES.map((c) => c.title)).toEqual(['덧셈', '뺄셈', '구구단', '나눗셈']);
    const used = new Set(CATEGORIES.flatMap((c) => c.stageIds));
    for (const s of STAGES) expect(used.has(s.id), s.id).toBe(true);
    for (const id of used) expect(() => getStage(id)).not.toThrow();
  });

  it('구구단은 1~9단 다음에 혼합 구구단', () => {
    expect(getCategory('mul').stageIds.map((id) => getStage(id).title)).toEqual([
      '1단', '2단', '3단', '4단', '5단', '6단', '7단', '8단', '9단', '혼합 구구단',
    ]);
  });

  it('받아올림은 덧셈, 받아내림은 뺄셈, 20까지 섞기는 양쪽 끝에 있다', () => {
    const add = getCategory('add').stageIds;
    const sub = getCategory('sub').stageIds;
    expect(add).toContain('u3s1');
    expect(sub).toContain('u3s2');
    expect(add.at(-1)).toBe('u3s3');
    expect(sub.at(-1)).toBe('u3s3');
  });

  it('1~9 시리즈 단계에는 타일용 짧은 이름이 있다', () => {
    expect(getStage('u1s4').short).toBe('+3');
    expect(getStage('u2s4').short).toBe('−3');
    expect(getStage('u5s4').short).toBe('9단');
    expect(getStage('u6s3').short).toBe('÷3');
    expect(getStage('u5s5').short).toBeUndefined();
  });

  it('categoryOf는 단계가 처음 나오는 카테고리를 준다', () => {
    expect(categoryOf('u5s4')).toBe('mul');
    expect(categoryOf('u3s3')).toBe('add');
    expect(categoryOf('u6s1')).toBe('div');
  });

  it('categoryCrowns는 받은 왕관과 최대 왕관을 센다', () => {
    const stages = { u4s1: { crowns: 3, bestAccuracy: 1 }, u5s4: { crowns: 1, bestAccuracy: 0.8 }, u1s1: { crowns: 2, bestAccuracy: 1 } };
    expect(categoryCrowns(getCategory('mul'), stages)).toEqual({ earned: 4, total: 30 });
  });
});
