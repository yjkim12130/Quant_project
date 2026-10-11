import { screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { renderApp, withProfile } from './test/renderApp';

describe('프로필 선택', () => {
  it('프로필이 없으면 만들기 폼이 나오고, 만들면 맵으로 간다', async () => {
    const { user, store } = renderApp();
    expect(screen.getByRole('heading', { name: '셈셈 병아리' })).toBeInTheDocument();
    const start = screen.getByRole('button', { name: '시작하기' });
    expect(start).toBeDisabled();
    await user.type(screen.getByRole('textbox', { name: '이름' }), '하늘');
    await user.click(screen.getByRole('button', { name: '아바타 🐰' }));
    await user.click(start);
    expect(await screen.findByRole('heading', { name: '10까지 덧셈' })).toBeInTheDocument();
    expect(store.getState().data.profiles[0]).toMatchObject({ name: '하늘', avatar: '🐰' });
  });

  it('프로필이 있으면 카드에서 고른다', async () => {
    const { user } = renderApp({
      setup: (s) => {
        withProfile(s);
        s.getState().goto({ name: 'profiles' });
      },
    });
    await user.click(screen.getByRole('button', { name: /하늘/ }));
    expect(await screen.findByRole('heading', { name: '10까지 덧셈' })).toBeInTheDocument();
  });
});

describe('단계 맵', () => {
  it('첫 단계만 열려 있고 다음 단계는 잠겨 있다', () => {
    renderApp({ setup: withProfile });
    expect(screen.getByRole('button', { name: '그림 세기 단계' })).toBeEnabled();
    expect(screen.getByRole('button', { name: '합 5까지 단계 (잠김)' })).toBeDisabled();
    expect(screen.getByText('시작!')).toBeInTheDocument();
    expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(6);
  });

  it('모든 단계 열기면 마지막 단계도 열린다', () => {
    renderApp({
      setup: (s) => {
        withProfile(s);
        s.getState().setUnlockAll('p1', true);
      },
    });
    expect(screen.getByRole('button', { name: '곱셈 나눗셈 섞기 단계' })).toBeEnabled();
  });

  it('상단 바에 스트릭·레벨·소리 토글이 있다', async () => {
    const { user, store } = renderApp({ setup: withProfile });
    expect(screen.getByLabelText('연속 0일')).toBeInTheDocument();
    expect(screen.getByLabelText('레벨 1, 0 XP')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '소리 끄기' }));
    expect(store.getState().data.settings.soundOn).toBe(false);
    expect(screen.getByRole('button', { name: '소리 켜기' })).toBeInTheDocument();
  });

  it('단계를 누르면 레슨 화면으로 간다', async () => {
    const { user, store } = renderApp({ setup: withProfile });
    await user.click(screen.getByRole('button', { name: '그림 세기 단계' }));
    expect(store.getState().screen).toEqual({ name: 'lesson', stageId: 'u1s1' });
  });
});
