import { describe, expect, it } from 'vitest';
import type { CardioConfig } from '../types';
import { cardioTarget } from './cardio';

const cfg: CardioConfig = {
  metrics: [
    { key: 'speed', label: '속도', unit: 'km/h', step: 0.5 },
    { key: 'incline', label: '경사', unit: '%', step: 1 },
  ],
  primaryMetric: 'speed',
  minMinutes: 20,
  maxMinutes: 30,
  timeStep: 2,
};

describe('cardioTarget', () => {
  it('최대 시간 달성 → 주 강도 +1단계, 시간은 최소부터, 다른 강도 유지', () => {
    expect(cardioTarget(cfg, { minutes: 30, intensity: { speed: 10, incline: 3 } })).toEqual({
      type: 'cardio', minutes: 20, intensity: { speed: 10.5, incline: 3 },
    });
  });
  it('미달 → 같은 강도로 시간 +timeStep', () => {
    expect(cardioTarget(cfg, { minutes: 24, intensity: { speed: 10, incline: 3 } })).toEqual({
      type: 'cardio', minutes: 26, intensity: { speed: 10, incline: 3 },
    });
  });
  it('시간은 최대를 넘지 않는다', () => {
    expect(cardioTarget(cfg, { minutes: 29, intensity: { speed: 10 } }).minutes).toBe(30);
  });
  it('주 강도 값이 없으면 0에서 올린다', () => {
    expect(cardioTarget(cfg, { minutes: 30, intensity: {} }).intensity.speed).toBe(0.5);
  });
});
