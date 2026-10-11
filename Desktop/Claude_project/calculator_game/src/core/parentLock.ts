import { randInt, type Rng } from './random';

export interface ParentChallenge {
  a: number;
  b: number;
  answer: number;
}

export function makeParentChallenge(rng: Rng): ParentChallenge {
  const a = randInt(rng, 12, 29);
  const b = randInt(rng, 3, 9);
  return { a, b, answer: a * b };
}
