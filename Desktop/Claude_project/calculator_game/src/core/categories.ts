import type { Op, StageProgress } from './types';

export type CategoryId = Op;

export interface CategoryDef {
  id: CategoryId;
  title: string;
  color: string;
  icon: string;
  /** 화면에 보이는 순서. 한 단계가 두 카테고리에 들어갈 수 있다(진도는 공유). */
  stageIds: string[];
}

const ids = (prefix: string, from: number, to: number) =>
  Array.from({ length: to - from + 1 }, (_, i) => `${prefix}${from + i}`);

export const CATEGORIES: CategoryDef[] = [
  { id: 'add', title: '덧셈', color: '#58CC02', icon: '+', stageIds: [...ids('u1s', 1, 11), 'u3s1', 'u3s3'] },
  { id: 'sub', title: '뺄셈', color: '#1CB0F6', icon: '−', stageIds: [...ids('u2s', 1, 10), 'u3s2', 'u3s3'] },
  { id: 'mul', title: '구구단', color: '#FF9600', icon: '×', stageIds: [...ids('u4s', 1, 5), ...ids('u5s', 1, 5)] },
  { id: 'div', title: '나눗셈', color: '#CE82FF', icon: '÷', stageIds: ids('u6s', 1, 10) },
];

export function getCategory(id: CategoryId): CategoryDef {
  const c = CATEGORIES.find((x) => x.id === id);
  if (!c) throw new Error(`알 수 없는 카테고리: ${id}`);
  return c;
}

export function categoryOf(stageId: string): CategoryId {
  return (CATEGORIES.find((c) => c.stageIds.includes(stageId)) ?? CATEGORIES[0]).id;
}

export function categoryCrowns(c: CategoryDef, stages: Record<string, StageProgress>): { earned: number; total: number } {
  const earned = c.stageIds.reduce((sum, id) => sum + (stages[id]?.crowns ?? 0), 0);
  return { earned, total: c.stageIds.length * 3 };
}

