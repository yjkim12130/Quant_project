import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { addDays, todayLocal } from '../../core/date';
import { addExercise, findSession, listWeightSets } from '../../db/repository';
import type { WorkoutDB } from '../../db/schema';
import { seedWeightSession, weightExercise } from '../../test/fixtures';
import { renderApp } from '../../test/renderApp';
import { makeTestDb } from '../../test/testDb';
import { addToToday } from '../today/loadToday';

async function openLog() {
  const db = makeTestDb();
  const ex = await addExercise(db, weightExercise());
  await seedWeightSession(db, ex.id, addDays(todayLocal(), -2), [
    [{ weight: 40, reps: 12 }], [{ weight: 40, reps: 10 }], [{ weight: 40, reps: 9 }],
  ]);
  const app = renderApp(db);
  await app.user.click(await screen.findByRole('button', { name: /레그프레스 · 하체/ }));
  await screen.findByText(/목표: /);
  return { ...app, ex };
}

const editor = () => screen.getByRole('region', { name: '세트 입력' });

async function sessionSets(db: WorkoutDB, exerciseId: string) {
  const session = await findSession(db, exerciseId, todayLocal());
  return session ? listWeightSets(db, session.id) : [];
}

describe('웨이트 기록', () => {
  it('목표가 미리 채워지고, 완료하면 세트 저장·타이머 시작·다음 세트 목표', async () => {
    const { user, db, ex } = await openLog();
    expect(screen.getByText('목표: 40kg × 12/11/10')).toBeInTheDocument();
    expect(within(editor()).getByLabelText('무게')).toHaveValue(40);
    expect(within(editor()).getByLabelText('횟수')).toHaveValue(12);
    await user.click(screen.getByRole('button', { name: '✔ 완료' }));
    expect(await screen.findByRole('button', { name: /세트1 40kg×12/ })).toBeInTheDocument();
    expect(screen.getByRole('timer', { name: '휴식 타이머' })).toBeInTheDocument();
    expect(within(editor()).getByLabelText('횟수')).toHaveValue(11);
    const session = await findSession(db, ex.id, todayLocal());
    expect(session?.target).toEqual({
      type: 'double', sets: [{ weight: 40, reps: 12 }, { weight: 40, reps: 11 }, { weight: 40, reps: 10 }],
    });
  });
  it('세트 중간에 무게를 바꾸면 드롭 구간으로 저장', async () => {
    const { user, db, ex } = await openLog();
    await user.click(screen.getByRole('button', { name: '횟수 감소' }));
    await user.click(screen.getByRole('button', { name: '무게 바꿈' }));
    const weights = within(editor()).getAllByLabelText('무게');
    expect(weights[1]).toHaveValue(37.5);
    expect(within(editor()).getAllByLabelText('횟수')[1]).toHaveValue(1);
    await user.click(screen.getByRole('button', { name: '✔ 완료' }));
    expect(await screen.findByRole('button', { name: /세트1 40kg×11 → 37.5kg×1/ })).toBeInTheDocument();
    expect((await sessionSets(db, ex.id))[0].segments).toHaveLength(2);
  });
  it('완료한 세트를 탭해 수정·삭제', async () => {
    const { user } = await openLog();
    await user.click(screen.getByRole('button', { name: '✔ 완료' }));
    await user.click(await screen.findByRole('button', { name: /세트1 40kg×12/ }));
    await user.click(screen.getByRole('button', { name: '횟수 감소' }));
    await user.click(screen.getByRole('button', { name: '저장' }));
    expect(await screen.findByRole('button', { name: /세트1 40kg×11/ })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /세트1 40kg×11/ }));
    await user.click(screen.getByRole('button', { name: '삭제' }));
    expect(await screen.findByRole('heading', { name: /세트1/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /세트1 40kg/ })).not.toBeInTheDocument();
  });
  it('첫 기록이면 안내를 보여준다', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, weightExercise());
    await addToToday(db, todayLocal(), ex.id);
    const app = renderApp(db);
    await app.user.click(await screen.findByRole('button', { name: /레그프레스 · 하체/ }));
    expect(await screen.findByText(/첫 기록이에요/)).toBeInTheDocument();
  });
  it('볼륨 방식은 횟수안/무게안을 고를 수 있다', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, weightExercise({
      weight: { progression: 'volume', repMin: 8, repMax: 12, targetSets: 3, increment: 2.5, volumeGrowthPct: 3 },
    }));
    await seedWeightSession(db, ex.id, addDays(todayLocal(), -1), [[{ weight: 50, reps: 10 }], [{ weight: 50, reps: 10 }], [{ weight: 50, reps: 10 }]]);
    const { user } = renderApp(db);
    await user.click(await screen.findByRole('button', { name: /레그프레스 · 하체/ }));
    expect(await screen.findByText('목표: 50kg × 10/10/11 (볼륨 1545kg)')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '무게로 달성' }));
    expect(screen.getByText('목표: 52.5kg × 10/10/10 (볼륨 1545kg)')).toBeInTheDocument();
    expect(within(editor()).getByLabelText('무게')).toHaveValue(52.5);
  });
});
