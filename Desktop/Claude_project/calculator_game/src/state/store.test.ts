import { describe, it, expect } from 'vitest';
import { activeProfile, createGameStore } from './store';
import { MemoryKV } from '../test/memoryKV';
import { STORAGE_KEY, loadAppData } from '../core/storage';
import { emptyStats } from '../core/scoring';

function make(kv = new MemoryKV()) {
  let n = 0;
  const store = createGameStore({ kv, nextSeed: () => 1, today: () => '2026-10-10', makeId: () => `p${++n}` });
  return { kv, store };
}

describe('game store', () => {
  it('처음엔 프로필 화면에서 시작한다', () => {
    const { store } = make();
    expect(store.getState().screen).toEqual({ name: 'profiles' });
    expect(store.getState().loadError).toBe(false);
  });

  it('프로필을 추가하면 활성화되고 맵으로 가며 저장된다', () => {
    const { store, kv } = make();
    store.getState().addProfile('  하늘 ', '🐶');
    const s = store.getState();
    expect(activeProfile(s)?.name).toBe('하늘');
    expect(s.screen).toEqual({ name: 'map' });
    expect(loadAppData(kv).data.profiles).toHaveLength(1);
  });

  it('저장된 활성 프로필이 있으면 맵에서 다시 시작한다', () => {
    const { kv, store } = make();
    store.getState().addProfile('하늘', '🐶');
    const reopened = make(kv).store;
    expect(reopened.getState().screen).toEqual({ name: 'map' });
    expect(activeProfile(reopened.getState())?.name).toBe('하늘');
  });

  it('레슨을 끝내면 프로필이 갱신되고 결과 화면으로 간다', () => {
    const { store } = make();
    store.getState().addProfile('하늘', '🐶');
    const stats = emptyStats();
    stats.add = { correct: 10, total: 10 };
    store.getState().finishLesson('u1s1', { firstTryCorrect: 10, total: 10, heartsLeft: 5, stats });
    const s = store.getState();
    const p = activeProfile(s)!;
    expect(p.xp).toBe(130);
    expect(p.stages.u1s1.crowns).toBe(1);
    expect(p.streak.count).toBe(1);
    expect(s.screen).toMatchObject({ name: 'result', stageId: 'u1s1', summary: { xpGained: 130, passed: true } });
  });

  it('설정 변경', () => {
    const { store } = make();
    store.getState().addProfile('하늘', '🐶');
    store.getState().setTimer(15);
    store.getState().setSound(false);
    store.getState().setUnlockAll('p1', true);
    store.getState().setStartStage('p1', 'u2s1');
    const s = store.getState();
    expect(s.data.settings).toEqual({ soundOn: false, timerSec: 15 });
    expect(activeProfile(s)?.unlockAll).toBe(true);
    expect(activeProfile(s)?.stages.u1s4.crowns).toBe(3);
  });

  it('활성 프로필을 지우면 활성 해제된다', () => {
    const { store } = make();
    store.getState().addProfile('하늘', '🐶');
    store.getState().addProfile('바다', '🐱');
    store.getState().removeProfile('p2');
    expect(store.getState().data.profiles.map((p) => p.id)).toEqual(['p1']);
    expect(store.getState().data.activeProfileId).toBeNull();
  });

  it('손상된 저장 데이터면 loadError', () => {
    const kv = new MemoryKV();
    kv.setItem(STORAGE_KEY, 'garbage');
    expect(make(kv).store.getState().loadError).toBe(true);
  });
});
