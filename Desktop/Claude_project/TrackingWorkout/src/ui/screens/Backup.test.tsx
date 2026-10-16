import { screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { exportBackup } from '../../db/backup';
import { addExercise, getMeta, listExercises } from '../../db/repository';
import { weightExercise } from '../../test/fixtures';
import { renderApp } from '../../test/renderApp';
import { makeTestDb } from '../../test/testDb';

const deliver = vi.hoisted(() => vi.fn(async () => 'downloaded' as const));
vi.mock('../backupFile', () => ({ deliverBackup: deliver }));

afterEach(() => {
  deliver.mockClear();
  vi.restoreAllMocks();
});

describe('백업 UI', () => {
  it('내보내기 후 마지막 백업 시각을 기록한다', async () => {
    const db = makeTestDb();
    await addExercise(db, weightExercise());
    const { user } = renderApp(db);
    await user.click(screen.getByRole('button', { name: '설정' }));
    await user.click(await screen.findByRole('button', { name: '백업 내보내기' }));
    expect(deliver).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/백업 파일을 저장했어요/)).toBeInTheDocument();
    expect(await getMeta(db, 'lastBackupAt')).toEqual(expect.any(String));
  });
  it('가져오기: 확인 후 안전 백업을 만들고 교체한다', async () => {
    const src = makeTestDb();
    await addExercise(src, weightExercise({ name: '백업된 운동' }));
    const json = JSON.stringify(await exportBackup(src));

    const db = makeTestDb();
    await addExercise(db, weightExercise({ name: '기존 운동' }));
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { user } = renderApp(db);
    await user.click(screen.getByRole('button', { name: '설정' }));
    await user.upload(await screen.findByLabelText('백업 가져오기'), new File([json], 'b.json', { type: 'application/json' }));
    expect(await screen.findByText('백업을 복원했어요.')).toBeInTheDocument();
    expect(deliver).toHaveBeenCalledTimes(1);
    expect((await listExercises(db)).map((e) => e.name)).toEqual(['백업된 운동']);
  });
  it('잘못된 파일이면 오류를 보여주고 데이터를 유지한다', async () => {
    const db = makeTestDb();
    await addExercise(db, weightExercise());
    const { user } = renderApp(db);
    await user.click(screen.getByRole('button', { name: '설정' }));
    await user.upload(await screen.findByLabelText('백업 가져오기'), new File(['nope'], 'b.json', { type: 'application/json' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('JSON 형식의 백업 파일이 아니에요');
    expect(await listExercises(db)).toHaveLength(1);
  });
});
