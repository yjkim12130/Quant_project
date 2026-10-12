import { describe, it, expect } from 'vitest';
import { callName } from './korean';

describe('callName (받침 있으면 "이"를 붙여 부르는 이름)', () => {
  it.each([
    ['동현', '동현이'],
    ['하늘', '하늘이'],
    ['지우', '지우'],
    ['민서', '민서'],
    [' 동현 ', '동현이'],
    ['Tom', 'Tom'],
    ['', ''],
  ])('%s → %s', (name, expected) => {
    expect(callName(name)).toBe(expected);
  });
});
