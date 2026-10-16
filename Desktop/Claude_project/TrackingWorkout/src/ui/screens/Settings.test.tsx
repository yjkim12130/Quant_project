import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { addExercise, listExercises } from '../../db/repository';
import { weightExercise } from '../../test/fixtures';
import { renderApp } from '../../test/renderApp';

async function openSettings() {
  const app = renderApp();
  await app.user.click(screen.getByRole('button', { name: '설정' }));
  return app;
}

describe('설정 — 운동 관리', () => {
  it('웨이트 운동을 등록한다', async () => {
    const { user, db } = await openSettings();
    await user.click(screen.getByRole('button', { name: '+ 운동 추가' }));
    await user.type(screen.getByLabelText('기구 이름'), '레그프레스');
    await user.type(screen.getByLabelText('운동 종류'), '하체');
    await user.click(screen.getByRole('button', { name: '저장' }));
    expect(await screen.findByRole('button', { name: /레그프레스 · 하체/ })).toBeInTheDocument();
    expect((await listExercises(db))[0].weight?.repMax).toBe(12);
  });
  it('검증 오류를 보여준다', async () => {
    const { user } = await openSettings();
    await user.click(screen.getByRole('button', { name: '+ 운동 추가' }));
    await user.click(screen.getByRole('button', { name: '저장' }));
    expect(screen.getByRole('alert')).toHaveTextContent('기구 이름을 입력하세요');
  });
  it('중복 등록은 거부한다', async () => {
    const { user, db } = await openSettings();
    await addExercise(db, weightExercise());
    await user.click(screen.getByRole('button', { name: '+ 운동 추가' }));
    await user.type(screen.getByLabelText('기구 이름'), '레그프레스');
    await user.type(screen.getByLabelText('운동 종류'), '하체');
    await user.click(screen.getByRole('button', { name: '저장' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('이미 등록된 운동이에요');
  });
  it('유산소 운동을 강도 항목과 함께 등록한다', async () => {
    const { user, db } = await openSettings();
    await user.click(screen.getByRole('button', { name: '+ 운동 추가' }));
    await user.click(screen.getByRole('button', { name: '유산소' }));
    await user.type(screen.getByLabelText('기구 이름'), '러닝머신');
    await user.type(screen.getByLabelText('운동 종류'), '달리기');
    await user.click(screen.getByRole('button', { name: '+ 강도 항목' }));
    const names = screen.getAllByLabelText('강도 항목 이름');
    await user.type(names[1], '경사');
    await user.click(screen.getByRole('button', { name: '저장' }));
    await screen.findByRole('button', { name: /러닝머신 · 달리기/ });
    const [ex] = await listExercises(db);
    expect(ex.cardio?.metrics.map((m) => m.label)).toEqual(['레벨', '경사']);
    expect(ex.weight).toBeUndefined();
  });
  it('운동을 숨기면 숨긴 운동 목록으로 간다', async () => {
    const { user, db } = await openSettings();
    await addExercise(db, weightExercise());
    await user.click(await screen.findByRole('button', { name: /레그프레스 · 하체/ }));
    await user.click(await screen.findByRole('button', { name: '숨기기' }));
    const hidden = await screen.findByRole('region', { name: '숨긴 운동' });
    expect(within(hidden).getByRole('button', { name: /레그프레스 · 하체/ })).toBeInTheDocument();
  });
});
