import { describe, it, expect } from 'vitest';
import { STORAGE_KEY, defaultAppData, loadAppData, newProfile, saveAppData } from './storage';
import { MemoryKV } from '../test/memoryKV';

const throwing = {
  getItem: () => { throw new Error('blocked'); },
  setItem: () => { throw new Error('quota'); },
};

describe('loadAppData', () => {
  it('저장된 게 없으면 기본값, 에러 아님', () => {
    expect(loadAppData(new MemoryKV())).toEqual({ data: defaultAppData(), error: false });
  });

  it('저장 → 불러오기 왕복', () => {
    const kv = new MemoryKV();
    const data = { ...defaultAppData(), profiles: [newProfile('p1', '하늘', '🐶')], activeProfileId: 'p1' };
    data.profiles[0].xp = 250;
    expect(saveAppData(kv, data)).toBe(true);
    expect(loadAppData(kv)).toEqual({ data, error: false });
  });

  it('깨진 JSON이면 기본값 + 에러', () => {
    const kv = new MemoryKV();
    kv.setItem(STORAGE_KEY, '{not json');
    expect(loadAppData(kv)).toEqual({ data: defaultAppData(), error: true });
  });

  it('스키마 버전이 다르면 기본값 + 에러', () => {
    const kv = new MemoryKV();
    kv.setItem(STORAGE_KEY, JSON.stringify({ ...defaultAppData(), schemaVersion: 2 }));
    expect(loadAppData(kv).error).toBe(true);
  });

  it('프로필에 빠진 필드는 기본값으로 채운다', () => {
    const kv = new MemoryKV();
    kv.setItem(STORAGE_KEY, JSON.stringify({ schemaVersion: 1, profiles: [{ id: 'p1', name: '하늘' }], activeProfileId: 'p1', settings: {} }));
    const { data, error } = loadAppData(kv);
    expect(error).toBe(false);
    expect(data.profiles[0]).toEqual(newProfile('p1', '하늘', '🐣'));
    expect(data.settings).toEqual({ soundOn: true, timerSec: null });
  });

  it('없는 프로필을 가리키는 activeProfileId는 null로', () => {
    const kv = new MemoryKV();
    kv.setItem(STORAGE_KEY, JSON.stringify({ ...defaultAppData(), activeProfileId: 'ghost' }));
    expect(loadAppData(kv).data.activeProfileId).toBeNull();
  });

  it('읽기가 예외를 던지거나 저장소가 없으면 기본값 + 에러', () => {
    expect(loadAppData(throwing)).toEqual({ data: defaultAppData(), error: true });
    expect(loadAppData(null)).toEqual({ data: defaultAppData(), error: true });
  });
});

describe('saveAppData', () => {
  it('쓰기 예외는 삼키고 false', () => {
    expect(saveAppData(throwing, defaultAppData())).toBe(false);
    expect(saveAppData(null, defaultAppData())).toBe(false);
  });
});
