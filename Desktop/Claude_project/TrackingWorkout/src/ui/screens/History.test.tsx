import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { addDays, todayLocal } from '../../core/date';
import { addExercise } from '../../db/repository';
import { cardioExercise, seedCardioSession, seedWeightSession, weightExercise } from '../../test/fixtures';
import { renderApp } from '../../test/renderApp';
import { makeTestDb } from '../../test/testDb';

describe('기록·그래프', () => {
  it('운동 목록 → 상세에서 세션 기록과 배지, 기간 필터', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, weightExercise());
    const t = { type: 'double' as const, sets: [{ weight: 40, reps: 12 }] };
    await seedWeightSession(db, ex.id, addDays(todayLocal(), -60), [[{ weight: 40, reps: 10 }]]);
    await seedWeightSession(db, ex.id, addDays(todayLocal(), -3), [[{ weight: 40, reps: 12 }, { weight: 30, reps: 4 }]], t);
    const { user } = renderApp(db);
    await user.click(screen.getByRole('button', { name: '기록' }));
    await user.click(await screen.findByRole('button', { name: /레그프레스 · 하체/ }));

    const list = await screen.findByRole('list', { name: '세션 기록' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(1);
    expect(within(list).getByText('40kg×12 → 30kg×4')).toBeInTheDocument();
    expect(within(list).getByTitle('달성')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '전체' }));
    expect(within(screen.getByRole('list', { name: '세션 기록' })).getAllByRole('listitem')).toHaveLength(2);
    expect(screen.getByRole('heading', { name: '추정 1RM (kg)' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '볼륨 (kg)' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '목표 달성률 (%)' })).toBeInTheDocument();
  });
  it('유산소는 측정값마다 그래프를 따로 그린다', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, cardioExercise());
    await seedCardioSession(db, ex.id, addDays(todayLocal(), -1), { minutes: 30, intensity: { speed: 10, incline: 2 }, kcal: 280 });
    const { user } = renderApp(db);
    await user.click(screen.getByRole('button', { name: '기록' }));
    await user.click(await screen.findByRole('button', { name: /러닝머신 · 달리기/ }));
    expect(await screen.findByRole('heading', { name: '시간 (분)' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '속도 (km/h)' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '칼로리 (kcal)' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '거리 (km)' })).not.toBeInTheDocument();
    expect(screen.getByText('30분 · 속도 10km/h · 경사 2% · 280kcal')).toBeInTheDocument();
  });
  it('기록이 없으면 안내', async () => {
    const db = makeTestDb();
    await addExercise(db, weightExercise());
    const { user } = renderApp(db);
    await user.click(screen.getByRole('button', { name: '기록' }));
    await user.click(await screen.findByRole('button', { name: /레그프레스 · 하체/ }));
    expect(await screen.findByText('이 기간에 기록이 없어요.')).toBeInTheDocument();
  });
});
