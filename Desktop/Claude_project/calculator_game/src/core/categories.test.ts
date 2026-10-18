import { describe, it, expect } from 'vitest';
import { CATEGORIES, categoryCrowns, categoryOf, getCategory } from './categories';
import { STAGES, getStage } from './stages';
import { mulberry32 } from './random';

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

  it('덧셈 탭 끝은 20까지·100까지 덧셈 섞기, 뺄셈 탭 끝은 뺄셈 섞기', () => {
    const add = getCategory('add').stageIds;
    const sub = getCategory('sub').stageIds;
    expect(add).toContain('u3s1');
    expect(sub).toContain('u3s2');
    expect(add.slice(-2).map((id) => getStage(id).title)).toEqual(['20까지 섞기', '100까지 섞기']);
    expect(sub.slice(-2).map((id) => getStage(id).title)).toEqual(['20까지 섞기', '100까지 섞기']);
    expect(add.slice(-2)).toEqual(['u3s3', 'u3s5']);
    expect(sub.slice(-2)).toEqual(['u3s4', 'u3s6']);
  });

  it('덧셈 탭에는 뺄셈이, 뺄셈 탭에는 덧셈이 섞이지 않는다', () => {
    for (const [cat, op] of [['add', 'add'], ['sub', 'sub']] as const) {
      for (const id of getCategory(cat).stageIds) {
        const rng = mulberry32(3);
        for (let n = 0; n < 200; n++) expect(getStage(id).make(rng).op, id).toBe(op);
      }
    }
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
    expect(categoryOf('u3s4')).toBe('sub');
    expect(categoryOf('u6s1')).toBe('div');
  });

  it('categoryCrowns는 받은 왕관과 최대 왕관을 센다', () => {
    const stages = { u4s1: { crowns: 3, bestAccuracy: 1 }, u5s4: { crowns: 1, bestAccuracy: 0.8 }, u1s1: { crowns: 2, bestAccuracy: 1 } };
    expect(categoryCrowns(getCategory('mul'), stages)).toEqual({ earned: 4, total: 30 });
  });
});
