import { screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { emptyStats } from '../../core/scoring';
import { MemoryKV } from '../../test/memoryKV';
import { renderApp } from '../../test/renderApp';
import { createGameStore } from '../../state/store';

// 프로필이 저장된 상태로 앱을 "다시 켠" 상황을 만든다
function savedKV(name: string) {
  const kv = new MemoryKV();
  const s = createGameStore({ kv, nextSeed: () => 42, today: () => '2026-10-10', makeId: () => 'p1' });
  s.getState().addProfile(name, '🦁');
  s.getState().goto({ name: 'lesson', stageId: 'u4s2', categoryId: 'mul' });
  s.getState().finishLesson('u4s2', { firstTryCorrect: 10, total: 10, heartsLeft: 5, stats: emptyStats() });
  return kv;
}

describe('입장 화면', () => {
  it('앱을 켜면 아이 이름으로 된 입장 화면이 먼저 나오고, 시작하면 홈으로 간다', async () => {
    const { user, store } = renderApp({ kv: savedKV('동현') });
    expect(store.getState().screen).toEqual({ name: 'intro' });
    expect(screen.getByRole('heading', { name: '동현이만을 위한 계산 게임~' })).toBeInTheDocument();
    expect(screen.getByText('👑 1개')).toBeInTheDocument();
    expect(screen.getByText('🔥 1일 연속')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '시작!' }));
    expect(store.getState().screen).toEqual({ name: 'home' });
  });

  it('받침 없는 이름은 "이"를 붙이지 않는다', () => {
    renderApp({ kv: savedKV('지우') });
    expect(screen.getByRole('heading', { name: '지우만을 위한 계산 게임~' })).toBeInTheDocument();
  });

  it('프로필이 없으면 "우리 친구"로 부르고, 시작하면 프로필 만들기로 간다', async () => {
    const { user, store } = renderApp();
    expect(screen.getByRole('heading', { name: '우리 친구만을 위한 계산 게임~' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '시작!' }));
    expect(store.getState().screen).toEqual({ name: 'profiles' });
    expect(screen.getByRole('button', { name: '시작하기' })).toBeInTheDocument();
  });
});
