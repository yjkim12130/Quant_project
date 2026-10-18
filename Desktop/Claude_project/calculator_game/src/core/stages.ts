import { pick, randInt, type Rng } from './random';
import type { Operands } from './types';

export interface StageDef {
  id: string;
  unit: number;
  title: string;
  /** 카테고리 화면 3열 타일에 크게 쓰는 짧은 이름. 없으면 한 줄 전체 타일. */
  short?: string;
  picture: 'none' | 'mixed' | 'priority';
  preferBlank?: boolean;
  hint?: string;
  make: (rng: Rng) => Operands;
}

type Maker = (rng: Rng) => Operands;

const add = (a: number, b: number): Operands => ({ op: 'add', a, b });
const sub = (a: number, b: number): Operands => ({ op: 'sub', a, b });

const plusSmall: Maker = (rng) => add(randInt(rng, 1, 8), randInt(rng, 1, 2));
const minusSmall: Maker = (rng) => sub(randInt(rng, 2, 6), randInt(rng, 1, 2));

// 1~9 에 n 을 더한다 (답 2~18)
const plusN = (n: number): Maker => (rng) => add(randInt(rng, 1, 9), n);

// n 을 빼서 답이 0~9 가 되게 한다
const minusN = (n: number): Maker => (rng) => sub(n + randInt(rng, 0, 9), n);

const makeTen: Maker = (rng) => {
  const a = randInt(rng, 1, 9);
  return add(a, 10 - a);
};

// 두 자리 + 두 자리, 일의 자리에서 받아올림 (합 ≤ 99)
const addCarry: Maker = (rng) => {
  const ao = randInt(rng, 1, 9);
  const bo = randInt(rng, 10 - ao, 9);
  const at = randInt(rng, 1, 7);
  const bt = randInt(rng, 1, 8 - at);
  return add(at * 10 + ao, bt * 10 + bo);
};

// 두 자리 − 두 자리, 일의 자리에서 받아내림 (답 ≥ 1)
const subBorrow: Maker = (rng) => {
  const ao = randInt(rng, 0, 8);
  const bo = randInt(rng, ao + 1, 9);
  const at = randInt(rng, 2, 9);
  const bt = randInt(rng, 1, at - 1);
  return sub(at * 10 + ao, bt * 10 + bo);
};

// 100까지: 두 자리 + 한 자리 / 두 자리 + 두 자리 (합 ≤ 100)
const add100: Maker = (rng) => {
  if (rng() < 0.5) {
    const a = randInt(rng, 10, 91);
    return add(a, randInt(rng, 1, Math.min(9, 100 - a)));
  }
  const a = randInt(rng, 10, 90);
  return add(a, randInt(rng, 10, 100 - a));
};

// 100까지: 두 자리 − 한 자리 / 두 자리 − 두 자리 (답 ≥ 1)
const sub100: Maker = (rng) => {
  if (rng() < 0.5) return sub(randInt(rng, 11, 100), randInt(rng, 1, 9));
  const a = randInt(rng, 21, 100);
  return sub(a, randInt(rng, 10, a - 1));
};

const times = (ds: number[]): Maker => (rng) => ({ op: 'mul', a: pick(rng, ds), b: randInt(rng, 1, 9) });

const divide = (ds: number[]): Maker => (rng) => {
  const d = pick(rng, ds);
  return { op: 'div', a: d * randInt(rng, 1, 9), b: d };
};

const mix = (...makers: Maker[]): Maker => (rng) => pick(rng, makers)(rng);

const range = (lo: number, hi: number) => Array.from({ length: hi - lo + 1 }, (_, i) => lo + i);
const ALL = range(1, 9);

// 받침 있는 숫자(3 삼, 6 육)는 '으로', 나머지는 '로'
const byDivisor = (d: number) => `${d}${d === 3 || d === 6 ? '으로' : '로'} 나누기`;

export const STAGES: StageDef[] = [
  { id: 'u1s1', unit: 1, title: '그림 세기', picture: 'priority', make: plusSmall },
  ...ALL.map((n): StageDef => ({ id: `u1s${n + 1}`, unit: 1, title: `${n} 더하기`, short: `+${n}`, picture: 'mixed', make: plusN(n) })),
  { id: 'u1s11', unit: 1, title: '10 만들기', picture: 'mixed', preferBlank: true, make: makeTen },
  { id: 'u2s1', unit: 2, title: '그림 빼기', picture: 'priority', make: minusSmall },
  ...ALL.map((n): StageDef => ({ id: `u2s${n + 1}`, unit: 2, title: `${n} 빼기`, short: `−${n}`, picture: 'mixed', make: minusN(n) })),
  { id: 'u3s1', unit: 3, title: '받아올림 덧셈', picture: 'none', make: addCarry },
  { id: 'u3s2', unit: 3, title: '받아내림 뺄셈', picture: 'none', make: subBorrow },
  { id: 'u3s5', unit: 3, title: '100까지 섞기', picture: 'none', make: add100 },
  { id: 'u3s6', unit: 3, title: '100까지 섞기', picture: 'none', make: sub100 },
  ...range(1, 5).map((d): StageDef => ({ id: `u4s${d}`, unit: 4, title: `${d}단`, short: `${d}단`, picture: 'none', make: times([d]) })),
  ...range(6, 9).map((d): StageDef => ({ id: `u5s${d - 5}`, unit: 5, title: `${d}단`, short: `${d}단`, picture: 'none', make: times([d]) })),
  { id: 'u5s5', unit: 5, title: '혼합 구구단', picture: 'none', make: times(ALL) },
  ...ALL.map(
    (d): StageDef => ({
      id: `u6s${d}`, unit: 6, title: byDivisor(d), short: `÷${d}`, picture: 'none', make: divide([d]),
      hint: d === 1 ? '나눗셈은 구구단 거꾸로! 12 ÷ 3 = ? 는 3 × ? = 12 와 같아요.' : undefined,
    }),
  ),
  { id: 'u6s10', unit: 6, title: '곱셈 나눗셈 섞기', picture: 'none', make: mix(times(ALL), divide(ALL)) },
];

export function stageIndex(id: string): number {
  return STAGES.findIndex((s) => s.id === id);
}

export function getStage(id: string): StageDef {
  const stage = STAGES.find((s) => s.id === id);
  if (!stage) throw new Error(`알 수 없는 단계: ${id}`);
  return stage;
}
