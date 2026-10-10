import { pick, randInt, type Rng } from './random';
import type { Operands } from './types';

export interface StageDef {
  id: string;
  unit: number;
  title: string;
  picture: 'none' | 'mixed' | 'priority';
  preferBlank?: boolean;
  hint?: string;
  make: (rng: Rng) => Operands;
}

export interface UnitDef {
  unit: number;
  title: string;
  color: string;
  icon: string;
}

type Maker = (rng: Rng) => Operands;

const add = (a: number, b: number): Operands => ({ op: 'add', a, b });
const sub = (a: number, b: number): Operands => ({ op: 'sub', a, b });

const plusSmall: Maker = (rng) => add(randInt(rng, 1, 8), randInt(rng, 1, 2));
const minusSmall: Maker = (rng) => sub(randInt(rng, 2, 6), randInt(rng, 1, 2));

const sumTo = (max: number): Maker => (rng) => {
  const a = randInt(rng, 1, max - 1);
  return add(a, randInt(rng, 1, max - a));
};

const makeTen: Maker = (rng) => {
  const a = randInt(rng, 1, 9);
  return add(a, 10 - a);
};

const subWithin = (max: number): Maker => (rng) => {
  const a = randInt(rng, 1, max);
  return sub(a, randInt(rng, 1, a));
};

const teenNoCarry: Maker = (rng) => {
  const a = randInt(rng, 10, 18);
  return add(a, randInt(rng, 1, 9 - (a % 10)));
};

const addCarry: Maker = (rng) => {
  const a = randInt(rng, 2, 9);
  return add(a, randInt(rng, Math.max(2, 11 - a), 9));
};

const subBorrow: Maker = (rng) => {
  const a = randInt(rng, 11, 18);
  return sub(a, randInt(rng, (a % 10) + 1, 9));
};

const times = (ds: number[]): Maker => (rng) => ({ op: 'mul', a: pick(rng, ds), b: randInt(rng, 1, 9) });

const divide = (ds: number[]): Maker => (rng) => {
  const d = pick(rng, ds);
  return { op: 'div', a: d * randInt(rng, 1, 9), b: d };
};

const mix = (...makers: Maker[]): Maker => (rng) => pick(rng, makers)(rng);

const ALL = [2, 3, 4, 5, 6, 7, 8, 9];

export const UNITS: UnitDef[] = [
  { unit: 1, title: '10까지 덧셈', color: '#58CC02', icon: '➕' },
  { unit: 2, title: '10까지 뺄셈', color: '#1CB0F6', icon: '➖' },
  { unit: 3, title: '20까지 덧셈·뺄셈', color: '#CE82FF', icon: '🔢' },
  { unit: 4, title: '구구단 ①', color: '#FF9600', icon: '✖️' },
  { unit: 5, title: '구구단 ②', color: '#FF4B4B', icon: '✖️' },
  { unit: 6, title: '나눗셈', color: '#2B70C9', icon: '➗' },
];

export const STAGES: StageDef[] = [
  { id: 'u1s1', unit: 1, title: '그림 세기', picture: 'priority', make: plusSmall },
  { id: 'u1s2', unit: 1, title: '합 5까지', picture: 'mixed', make: sumTo(5) },
  { id: 'u1s3', unit: 1, title: '합 10까지', picture: 'mixed', make: sumTo(10) },
  { id: 'u1s4', unit: 1, title: '10 만들기', picture: 'mixed', preferBlank: true, make: makeTen },
  { id: 'u2s1', unit: 2, title: '그림 빼기', picture: 'priority', make: minusSmall },
  { id: 'u2s2', unit: 2, title: '5 안에서 빼기', picture: 'mixed', make: subWithin(5) },
  { id: 'u2s3', unit: 2, title: '10 안에서 빼기', picture: 'mixed', make: subWithin(10) },
  { id: 'u2s4', unit: 2, title: '더하기 빼기 섞기', picture: 'mixed', make: mix(sumTo(10), subWithin(10)) },
  { id: 'u3s1', unit: 3, title: '10 넘는 덧셈', picture: 'none', make: teenNoCarry },
  { id: 'u3s2', unit: 3, title: '받아올림 덧셈', picture: 'none', make: addCarry },
  { id: 'u3s3', unit: 3, title: '받아내림 뺄셈', picture: 'none', make: subBorrow },
  { id: 'u3s4', unit: 3, title: '20까지 섞기', picture: 'none', make: mix(teenNoCarry, addCarry, subBorrow) },
  { id: 'u4s1', unit: 4, title: '2단', picture: 'none', make: times([2]) },
  { id: 'u4s2', unit: 4, title: '5단', picture: 'none', make: times([5]) },
  { id: 'u4s3', unit: 4, title: '3단', picture: 'none', make: times([3]) },
  { id: 'u4s4', unit: 4, title: '4단', picture: 'none', make: times([4]) },
  { id: 'u5s1', unit: 5, title: '6단', picture: 'none', make: times([6]) },
  { id: 'u5s2', unit: 5, title: '7단', picture: 'none', make: times([7]) },
  { id: 'u5s3', unit: 5, title: '8단·9단', picture: 'none', make: times([8, 9]) },
  { id: 'u5s4', unit: 5, title: '구구단 섞기', picture: 'none', make: times(ALL) },
  {
    id: 'u6s1', unit: 6, title: '2단·5단 나누기', picture: 'none', make: divide([2, 5]),
    hint: '나눗셈은 구구단 거꾸로! 12 ÷ 3 = ? 는 3 × ? = 12 와 같아요.',
  },
  { id: 'u6s2', unit: 6, title: '3단·4단 나누기', picture: 'none', make: divide([3, 4]) },
  { id: 'u6s3', unit: 6, title: '6~9단 나누기', picture: 'none', make: divide([6, 7, 8, 9]) },
  { id: 'u6s4', unit: 6, title: '곱셈 나눗셈 섞기', picture: 'none', make: mix(times(ALL), divide(ALL)) },
];

export function stageIndex(id: string): number {
  return STAGES.findIndex((s) => s.id === id);
}

export function getStage(id: string): StageDef {
  const stage = STAGES.find((s) => s.id === id);
  if (!stage) throw new Error(`알 수 없는 단계: ${id}`);
  return stage;
}
