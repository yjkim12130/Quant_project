import { describe, expect, it } from 'vitest';
import { seedWeightSession, weightExercise } from '../test/fixtures';
import { makeTestDb } from '../test/testDb';
import { BackupError, backupFileName, exportBackup, markBackedUp, parseBackup, restoreBackup } from './backup';
import { addExercise, getMeta, listExercises, weightHistory } from './repository';

describe('backup', () => {
  it('내보내기 → 파싱 → 다른 DB에 복원하면 같은 데이터', async () => {
    const src = makeTestDb();
    const ex = await addExercise(src, weightExercise());
    await seedWeightSession(src, ex.id, '2026-10-14', [[{ weight: 40, reps: 12 }, { weight: 30, reps: 4 }]]);
    const file = await exportBackup(src, new Date('2026-10-17T10:00:00Z'));
    expect(file).toMatchObject({ app: 'tracking-workout', version: 1, exportedAt: '2026-10-17T10:00:00.000Z' });

    const dst = makeTestDb();
    await addExercise(dst, weightExercise({ name: '지워질 운동' }));
    await restoreBackup(dst, parseBackup(JSON.stringify(file)));
    expect((await listExercises(dst)).map((e) => e.name)).toEqual(['하체']);
    expect(await weightHistory(dst, ex.id)).toEqual(await weightHistory(src, ex.id));
  });
  it('잘못된 파일을 거부한다', () => {
    expect(() => parseBackup('not json')).toThrow(BackupError);
    expect(() => parseBackup(JSON.stringify({ app: 'other' }))).toThrow('이 앱의 백업 파일이 아니에요');
    expect(() => parseBackup(JSON.stringify({ app: 'tracking-workout', version: 99, data: {} }))).toThrow('지원하지 않는 백업 버전');
    const base = { app: 'tracking-workout', version: 1, exportedAt: '', data: { exercises: [], sessions: [], weightSets: [], cardioEntries: [], meta: [] } };
    expect(() => parseBackup(JSON.stringify({ ...base, data: { ...base.data, sessions: undefined } }))).toThrow('백업에 sessions 목록이 없어요');
    expect(() => parseBackup(JSON.stringify({ ...base, data: { ...base.data, exercises: [{ id: 'x' }] } }))).toThrow('운동 데이터가 손상됐어요');
    expect(() => parseBackup(JSON.stringify({ ...base, data: { ...base.data, sessions: [{ id: 's', exerciseId: 'x', date: '10/17' }] } }))).toThrow('세션 데이터가 손상됐어요');
    expect(parseBackup(JSON.stringify(base)).data.exercises).toEqual([]);
  });
  it('백업 시각 기록과 파일 이름', async () => {
    const db = makeTestDb();
    await markBackedUp(db, new Date('2026-10-17T10:00:00Z'));
    expect(await getMeta(db, 'lastBackupAt')).toBe('2026-10-17T10:00:00.000Z');
    expect(backupFileName(new Date(2026, 9, 17, 9, 5))).toBe('tracking-workout-20261017-0905.json');
  });
});
