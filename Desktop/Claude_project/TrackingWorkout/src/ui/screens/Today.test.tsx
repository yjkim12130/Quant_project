import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { addDays, todayLocal } from '../../core/date';
import { addExercise } from '../../db/repository';
import { seedWeightSession, weightExercise } from '../../test/fixtures';
import { renderApp } from '../../test/renderApp';
import { makeTestDb } from '../../test/testDb';

describe('오늘 화면', () => {
  it('최근 운동과 오늘 목표를 보여준다', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, weightExercise());
    await seedWeightSession(db, ex.id, addDays(todayLocal(), -2), [
      [{ weight: 40, reps: 12 }], [{ weight: 40, reps: 10 }], [{ weight: 40, reps: 9 }],
    ]);
    renderApp(db);
    expect(await screen.findByText('레그프레스 · 하체')).toBeInTheDocument();
    expect(screen.getByText('목표 40kg × 12/11/10')).toBeInTheDocument();
  });
  it('운동이 없으면 안내, 오늘 할 운동을 추가할 수 있다', async () => {
    const db = makeTestDb();
    await addExercise(db, weightExercise());
    const { user } = renderApp(db);
    expect(await screen.findByText(/아래에서 오늘 할 운동을 추가하세요/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '+ 오늘 할 운동 추가' }));
    await user.click(screen.getByRole('button', { name: '레그프레스 · 하체 추가' }));
    expect(await screen.findByText('첫 기록 — 시작 값을 입력하세요')).toBeInTheDocument();
  });
  it('순서 편집', async () => {
    const db = makeTestDb();
    const a = await addExercise(db, weightExercise({ name: 'A' }));
    const b = await addExercise(db, weightExercise({ name: 'B' }));
    const d = addDays(todayLocal(), -1);
    await seedWeightSession(db, a.id, d, [[{ weight: 10, reps: 10 }]]);
    await seedWeightSession(db, b.id, d, [[{ weight: 10, reps: 10 }]]);
    const { user } = renderApp(db);
    await screen.findByText('레그프레스 · A');
    await user.click(screen.getByRole('button', { name: '순서 편집' }));
    await user.click(screen.getByRole('button', { name: '레그프레스 · B 위로' }));
    await waitFor(() =>
      expect(screen.getAllByText(/^레그프레스 · [AB]$/).map((el) => el.textContent)).toEqual(['레그프레스 · B', '레그프레스 · A']),
    );
  });
});
