import { describe, expect, it } from 'vitest';
import { markBackedUp } from '../../db/backup';
import { addExercise } from '../../db/repository';
import { seedWeightSession, weightExercise } from '../../test/fixtures';
import { makeTestDb } from '../../test/testDb';
import { addToToday, loadToday, moveItem } from './loadToday';

const today = '2026-10-17';
const t40 = { type: 'double' as const, sets: [{ weight: 40, reps: 12 }] };

describe('loadToday', () => {
  it('최근 7일 기록 운동 + 수동 추가 운동, 나머지는 others', async () => {
    const db = makeTestDb();
    const a = await addExercise(db, weightExercise({ name: 'A' }));
    await addExercise(db, weightExercise({ name: 'B' }));
    const c = await addExercise(db, weightExercise({ name: 'C' }));
    await seedWeightSession(db, a.id, '2026-10-15', [[{ weight: 40, reps: 10 }]]);
    await addToToday(db, today, c.id);
    const data = await loadToday(db, today);
    expect(data.items.map((i) => i.exercise.name)).toEqual(['A', 'C']);
    expect(data.others.map((e) => e.name)).toEqual(['B']);
    expect(data.items[0].recommendation.status).toBe('ok');
    expect(data.items[1].recommendation.status).toBe('first');
  });
  it('순서 변경이 저장된다', async () => {
    const db = makeTestDb();
    const a = await addExercise(db, weightExercise({ name: 'A' }));
    const b = await addExercise(db, weightExercise({ name: 'B' }));
    await addToToday(db, today, a.id);
    await addToToday(db, today, b.id);
    await moveItem(db, [a.id, b.id], 1, -1);
    expect((await loadToday(db, today)).items.map((i) => i.exercise.name)).toEqual(['B', 'A']);
  });
  it('오늘 완료 여부·최근 배지·4주 달성률', async () => {
    const db = makeTestDb();
    const a = await addExercise(db, weightExercise());
    await seedWeightSession(db, a.id, '2026-09-01', [[{ weight: 40, reps: 12 }]], t40);
    await seedWeightSession(db, a.id, '2026-10-14', [[{ weight: 40, reps: 12 }]], t40);
    await seedWeightSession(db, a.id, today, [[{ weight: 40, reps: 10 }]], t40);
    const data = await loadToday(db, today);
    expect(data.items[0].doneToday).toBe(true);
    expect(data.items[0].recentBadges).toEqual(['up', 'up', 'down']);
    expect(data.rate).toBeCloseTo(1 / 2);
  });
  it('백업 경고: 데이터가 있고 14일 넘게 백업 안 함', async () => {
    const db = makeTestDb();
    expect((await loadToday(db, today)).needsBackup).toBe(false);
    const a = await addExercise(db, weightExercise());
    await seedWeightSession(db, a.id, '2026-10-14', [[{ weight: 40, reps: 12 }]]);
    expect((await loadToday(db, today)).needsBackup).toBe(true);
    await markBackedUp(db, new Date('2026-10-10T12:00:00Z'));
    expect((await loadToday(db, today)).needsBackup).toBe(false);
  });
});
