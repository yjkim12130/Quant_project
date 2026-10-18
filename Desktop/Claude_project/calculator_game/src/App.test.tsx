import { screen, within } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { emptyStats } from './core/scoring';
import { renderApp, withProfile } from './test/renderApp';

describe('프로필 선택', () => {
  it('프로필이 없으면 만들기 폼이 나오고, 만들면 맵으로 간다', async () => {
    const { user, store } = renderApp();
    await user.click(screen.getByRole('button', { name: '시작!' }));
    expect(screen.getByRole('heading', { name: '셈셈 병아리' })).toBeInTheDocument();
    const start = screen.getByRole('button', { name: '시작하기' });
    expect(start).toBeDisabled();
    await user.type(screen.getByRole('textbox', { name: '이름' }), '하늘');
    await user.click(screen.getByRole('button', { name: '아바타 🐰' }));
    await user.click(start);
    expect(await screen.findByRole('button', { name: '덧셈 카테고리' })).toBeInTheDocument();
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
    expect(await screen.findByRole('button', { name: '덧셈 카테고리' })).toBeInTheDocument();
  });
});

describe('홈과 카테고리', () => {
  it('홈에는 카테고리 카드 4개와 왕관 수가 있다', () => {
    renderApp({
      setup: (s) => {
        withProfile(s);
        s.getState().goto({ name: 'lesson', stageId: 'u4s2', categoryId: 'mul' });
        s.getState().finishLesson('u4s2', { firstTryCorrect: 10, total: 10, heartsLeft: 5, stats: emptyStats() });
        s.getState().goto({ name: 'home' });
      },
    });
    const cards = ['덧셈', '뺄셈', '구구단', '나눗셈'].map((t) => screen.getByRole('button', { name: `${t} 카테고리` }));
    expect(cards).toHaveLength(4);
    expect(within(cards[2]).getByText('👑 1/30')).toBeInTheDocument();
    expect(within(cards[0]).getByText('👑 0/42')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: / 단계$/ })).not.toBeInTheDocument();
  });

  it('구구단을 고르면 1~9단과 혼합 구구단이 한 화면에 나오고, 뒤로 가면 홈이다', async () => {
    const { user, store } = renderApp({ setup: withProfile });
    await user.click(screen.getByRole('button', { name: '구구단 카테고리' }));
    expect(store.getState().screen).toEqual({ name: 'category', categoryId: 'mul' });
    expect(screen.getByRole('heading', { name: '구구단' })).toBeInTheDocument();
    const tiles = screen.getAllByRole('button', { name: / 단계$/ });
    expect(tiles.map((t) => t.getAttribute('aria-label'))).toEqual([
      ...[1, 2, 3, 4, 5, 6, 7, 8, 9].map((d) => `${d}단 단계`),
      '혼합 구구단 단계',
    ]);
    await user.click(screen.getByRole('button', { name: '뒤로' }));
    expect(store.getState().screen).toEqual({ name: 'home' });
  });

  it('9단을 누르면 9단 레슨이 시작된다', async () => {
    const { user, store } = renderApp({ setup: withProfile });
    await user.click(screen.getByRole('button', { name: '구구단 카테고리' }));
    await user.click(screen.getByRole('button', { name: '9단 단계' }));
    expect(store.getState().screen).toEqual({ name: 'lesson', stageId: 'u5s4', categoryId: 'mul' });
  });

  it('상단 바에 스트릭·레벨·소리 토글이 있다', async () => {
    const { user, store } = renderApp({ setup: withProfile });
    expect(screen.getByLabelText('연속 0일')).toBeInTheDocument();
    expect(screen.getByLabelText('레벨 1, 0 XP')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '소리 끄기' }));
    expect(store.getState().data.settings.soundOn).toBe(false);
    expect(screen.getByRole('button', { name: '소리 켜기' })).toBeInTheDocument();
  });
});
