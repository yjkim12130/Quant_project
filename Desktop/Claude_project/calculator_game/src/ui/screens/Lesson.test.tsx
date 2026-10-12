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

async function openStage(user: User, title: string, category = '덧셈') {
  await user.click(await screen.findByRole('button', { name: `${category} 카테고리` }));
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
    expect(store.getState().screen).toEqual({ name: 'category', categoryId: 'add' });
  });

  it('틀리면 하트가 줄고 정답은 알려주지 않으며, 그 문제가 끝에 다시 나온다', async () => {
    const { user } = renderApp({ setup: withProfile });
    await openStage(user, '그림 세기');
    const qs = generateLesson(getStage('u1s1'), 0, 42);
    const first = qs[0];
    const wrong = first.choices ? first.choices.find((c) => c !== first.answer)! : first.answer + 1;
    await answerWith(user, first, wrong);
    expect(await screen.findByText('괜찮아, 다시 해보자!')).toBeInTheDocument();
    expect(screen.queryByText(/정답/)).toBeNull();
    expect(document.querySelector('.sheet')).not.toHaveTextContent(String(first.answer));
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

  it('그만하기를 누르면 카테고리 화면으로 돌아간다', async () => {
    const { user, store } = renderApp({ setup: withProfile });
    await openStage(user, '그림 세기');
    await user.click(screen.getByRole('button', { name: '그만하기' }));
    expect(store.getState().screen).toEqual({ name: 'category', categoryId: 'add' });
  });

  it('나눗셈 첫 단계는 힌트를 보여준다', async () => {
    const { user } = renderApp({ setup: withProfile });
    await openStage(user, '1로 나누기', '나눗셈');
    expect(screen.getByText(/구구단 거꾸로/)).toBeInTheDocument();
  });
});
