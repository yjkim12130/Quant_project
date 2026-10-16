import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { addDays, todayLocal } from '../../core/date';
import { addExercise, findSession, getCardioEntry } from '../../db/repository';
import { cardioExercise, seedCardioSession } from '../../test/fixtures';
import { renderApp } from '../../test/renderApp';
import { makeTestDb } from '../../test/testDb';

describe('유산소 기록', () => {
  it('목표가 미리 채워지고 저장하면 오늘 기록 요약으로 바뀐다', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, cardioExercise());
    await seedCardioSession(db, ex.id, addDays(todayLocal(), -1), { minutes: 30, intensity: { speed: 10, incline: 3 } });
    const { user } = renderApp(db);
    await user.click(await screen.findByRole('button', { name: /러닝머신 · 달리기/ }));
    expect(await screen.findByText('목표: 20분 · 속도 10.5km/h · 경사 3%')).toBeInTheDocument();
    expect(screen.getByLabelText('시간')).toHaveValue(20);
    expect(screen.getByLabelText('속도')).toHaveValue(10.5);
    await user.type(screen.getByLabelText('거리(km)'), '3.6');
    await user.type(screen.getByLabelText('칼로리(kcal)'), '210');
    await user.click(screen.getByRole('button', { name: '저장' }));
    expect(await screen.findByText('오늘 기록: 20분 · 속도 10.5km/h · 경사 3% · 3.6km · 210kcal')).toBeInTheDocument();
    const session = await findSession(db, ex.id, todayLocal());
    expect(session?.target).toEqual({ type: 'cardio', minutes: 20, intensity: { speed: 10.5, incline: 3 } });
    expect(await getCardioEntry(db, session!.id)).toMatchObject({ minutes: 20, distanceKm: 3.6, kcal: 210 });
  });
  it('저장한 기록을 수정한다', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, cardioExercise());
    await seedCardioSession(db, ex.id, todayLocal(), { minutes: 25, intensity: { speed: 9, incline: 1 } });
    const { user } = renderApp(db);
    await user.click(await screen.findByRole('button', { name: /러닝머신 · 달리기/ }));
    await user.click(await screen.findByRole('button', { name: '수정' }));
    expect(screen.getByLabelText('시간')).toHaveValue(25);
    await user.click(screen.getByRole('button', { name: '시간 증가' }));
    await user.click(screen.getByRole('button', { name: '저장' }));
    expect(await screen.findByText(/오늘 기록: 26분/)).toBeInTheDocument();
  });
});
