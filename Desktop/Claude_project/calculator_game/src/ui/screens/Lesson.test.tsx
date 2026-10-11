import { screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { generateLesson } from '../../core/generator';
import { getStage } from '../../core/stages';
import type { Question } from '../../core/types';
import { renderApp, typeNumber, withProfile } from '../../test/renderApp';

type User = ReturnType<typeof renderApp>['user'];

async function answerWith(user: User, q: Question, value: number) {
  if (q.kind === 'choice' || q.kind === 'picture') {
    await user.click(screen.getByRole('button', { name: String(value) }));
  } else {
    await typeNumber(user, value);
  }
  await user.click(screen.getByRole('button', { name: '확인' }));
}

async function openStage(user: User, title: string) {
  await user.click(await screen.findByRole('button', { name: `${title} 단계` }));
}

describe('레슨', () => {
  it('모두 맞히면 결과 화면이 나오고 XP 130을 받는다', async () => {
    const { user, store } = renderApp({ setup: withProfile });
    await openStage(user, '그림 세기');
    const qs = generateLesson(getStage('u1s1'), 0, 42);
    for (const q of qs) {
      await answerWith(user, q, q.answer);
      expect(await screen.findByText('잘했어! 🎉')).toBeInTheDocument();
      await user.click(screen.getByRole('button', { name: '계속' }));
    }
    expect(await screen.findByRole('heading', { name: '레슨 끝!' })).toBeInTheDocument();
    expect(screen.getByText('+130')).toBeInTheDocument();
    expect(screen.getByText('100%')).toBeInTheDocument();
    expect(store.getState().data.profiles[0].xp).toBe(130);
    await user.click(screen.getByRole('button', { name: '계속하기' }));
    expect(store.getState().screen).toEqual({ name: 'map' });
  });

  it('틀리면 하트가 줄고 정답을 보여주며, 그 문제가 끝에 다시 나온다', async () => {
    const { user } = renderApp({ setup: withProfile });
    await openStage(user, '그림 세기');
    const qs = generateLesson(getStage('u1s1'), 0, 42);
    const first = qs[0];
    const wrong = first.choices ? first.choices.find((c) => c !== first.answer)! : first.answer + 1;
    await answerWith(user, first, wrong);
    expect(await screen.findByText('괜찮아, 다시 해보자!')).toBeInTheDocument();
    expect(screen.getByText(String(first.answer), { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByLabelText('하트 4개')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '계속' }));
    for (const q of qs.slice(1)) {
      await answerWith(user, q, q.answer);
      await user.click(await screen.findByRole('button', { name: '계속' }));
    }
    expect(await screen.findByText('다시 풀어보기')).toBeInTheDocument();
  });

  it('답을 고르기 전에는 확인 버튼이 비활성이다', async () => {
    const { user } = renderApp({ setup: withProfile });
    await openStage(user, '그림 세기');
    expect(screen.getByRole('button', { name: '확인' })).toBeDisabled();
  });

  it('그만하기를 누르면 맵으로 돌아간다', async () => {
    const { user, store } = renderApp({ setup: withProfile });
    await openStage(user, '그림 세기');
    await user.click(screen.getByRole('button', { name: '그만하기' }));
    expect(store.getState().screen).toEqual({ name: 'map' });
  });

  it('나눗셈 첫 단계는 힌트를 보여준다', async () => {
    const { user } = renderApp({
      setup: (s) => {
        withProfile(s);
        s.getState().setUnlockAll('p1', true);
      },
    });
    await openStage(user, '2단·5단 나누기');
    expect(screen.getByText(/구구단 거꾸로/)).toBeInTheDocument();
  });
});
