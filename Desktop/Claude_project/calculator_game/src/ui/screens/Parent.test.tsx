import { screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { makeParentChallenge } from '../../core/parentLock';
import { mulberry32 } from '../../core/random';
import { STORAGE_KEY } from '../../core/storage';
import { MemoryKV } from '../../test/memoryKV';
import { renderApp, typeNumber, withProfile } from '../../test/renderApp';

type User = ReturnType<typeof renderApp>['user'];
const challenge = () => makeParentChallenge(mulberry32(42)); // renderApp의 시드와 같다

async function unlock(user: User) {
  await user.click(screen.getByRole('button', { name: '부모 설정' }));
  await typeNumber(user, challenge().answer);
  await user.click(screen.getByRole('button', { name: '확인' }));
  await screen.findByRole('heading', { name: '부모 설정' });
}

describe('부모 설정', () => {
  it('어른 문제를 틀리면 열리지 않고, 맞히면 열린다', async () => {
    const { user } = renderApp({ setup: withProfile });
    await user.click(screen.getByRole('button', { name: '부모 설정' }));
    expect(screen.getByRole('heading', { name: '어른 확인 🔒' })).toBeInTheDocument();
    await typeNumber(user, challenge().answer + 1);
    await user.click(screen.getByRole('button', { name: '확인' }));
    expect(screen.getByText('다시 해보세요')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '부모 설정' })).toBeNull();
    await typeNumber(user, challenge().answer);
    await user.click(screen.getByRole('button', { name: '확인' }));
    expect(await screen.findByRole('heading', { name: '부모 설정' })).toBeInTheDocument();
  });

  it('돌아가기를 누르면 맵으로 간다', async () => {
    const { user, store } = renderApp({ setup: withProfile });
    await user.click(screen.getByRole('button', { name: '부모 설정' }));
    await user.click(screen.getByRole('button', { name: '돌아가기' }));
    expect(store.getState().screen).toEqual({ name: 'map' });
  });

  it('타이머와 효과음을 바꾼다', async () => {
    const { user, store } = renderApp({ setup: withProfile });
    await unlock(user);
    await user.click(screen.getByRole('button', { name: '15초' }));
    expect(store.getState().data.settings.timerSec).toBe(15);
    expect(screen.getByRole('button', { name: '15초' })).toHaveAttribute('aria-pressed', 'true');
    await user.click(screen.getByRole('checkbox', { name: '효과음' }));
    expect(store.getState().data.settings.soundOn).toBe(false);
  });

  it('시작 단계 지정과 모든 단계 열기', async () => {
    const { user, store } = renderApp({ setup: withProfile });
    await unlock(user);
    await user.selectOptions(screen.getByRole('combobox', { name: '시작 단계' }), 'u4s1');
    await user.click(screen.getByRole('button', { name: '여기부터 시작' }));
    expect(store.getState().data.profiles[0].stages.u3s4.crowns).toBe(3);
    await user.click(screen.getByRole('checkbox', { name: '모든 단계 열기' }));
    expect(store.getState().data.profiles[0].unlockAll).toBe(true);
  });

  it('연산별 정답률을 보여준다', async () => {
    const { user } = renderApp({
      setup: (s) => {
        withProfile(s);
        const stats = { add: { correct: 8, total: 10 }, sub: { correct: 0, total: 0 }, mul: { correct: 0, total: 0 }, div: { correct: 0, total: 0 } };
        s.getState().finishLesson('u1s1', { firstTryCorrect: 8, total: 10, heartsLeft: 3, stats });
        s.getState().goto({ name: 'map' });
      },
    });
    await unlock(user);
    expect(screen.getByText('덧셈 80% (8/10)')).toBeInTheDocument();
    expect(screen.getByText('뺄셈 -')).toBeInTheDocument();
  });

  it('프로필 삭제는 확인을 받은 뒤 지운다', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { user, store } = renderApp({ setup: withProfile });
    await unlock(user);
    await user.click(screen.getByRole('button', { name: '프로필 삭제' }));
    expect(confirm).toHaveBeenCalled();
    expect(store.getState().data.profiles).toHaveLength(0);
    confirm.mockRestore();
  });

  it('저장 기록을 못 불러왔으면 안내한다', async () => {
    const kv = new MemoryKV();
    kv.setItem(STORAGE_KEY, 'garbage');
    const { user } = renderApp({ kv, setup: withProfile });
    await unlock(user);
    expect(screen.getByText(/기록을 불러오지 못했어요/)).toBeInTheDocument();
  });
});
