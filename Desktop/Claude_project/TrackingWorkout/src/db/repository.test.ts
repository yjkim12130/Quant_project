import { describe, expect, it } from 'vitest';
import { cardioExercise, seedCardioSession, seedWeightSession, weightExercise } from '../test/fixtures';
import { makeTestDb } from '../test/testDb';
import {
  addExercise, addWeightSet, cardioHistory, deleteWeightSet, DuplicateExerciseError, exerciseHistory,
  getCardioEntry, getMeta, getOrCreateSession, listExercises, listWeightSets, recentExerciseIds,
  saveCardioEntry, setMeta, setSessionTarget, updateExercise, updateWeightSet, weightHistory,
} from './repository';

const target = { type: 'double' as const, sets: [{ weight: 40, reps: 12 }] };

describe('운동', () => {
  it('공백을 다듬어 저장하고 id를 붙인다', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, weightExercise({ equipment: ' 레그프레스 ', name: '하체 ' }));
    expect(ex).toMatchObject({ equipment: '레그프레스', name: '하체', archived: false });
    expect(ex.id).toBeTruthy();
  });
  it('(기구, 종류) 중복을 거부한다', async () => {
    const db = makeTestDb();
    await addExercise(db, weightExercise());
    await expect(addExercise(db, weightExercise())).rejects.toBeInstanceOf(DuplicateExerciseError);
  });
  it('이름이 비면 거부한다', async () => {
    const db = makeTestDb();
    await expect(addExercise(db, weightExercise({ name: '  ' }))).rejects.toThrow('기구 이름과 운동 종류를 입력하세요');
  });
  it('수정할 때 자기 자신은 중복이 아니다, 남과 겹치면 거부', async () => {
    const db = makeTestDb();
    const a = await addExercise(db, weightExercise());
    const b = await addExercise(db, weightExercise({ name: '종아리' }));
    await expect(updateExercise(db, { ...a, restSeconds: 60 })).resolves.toMatchObject({ restSeconds: 60 });
    await expect(updateExercise(db, { ...b, name: '하체' })).rejects.toBeInstanceOf(DuplicateExerciseError);
  });
  it('목록은 등록 순, 숨긴 운동은 기본 제외', async () => {
    const db = makeTestDb();
    const a = await addExercise(db, weightExercise({ name: 'A' }));
    await addExercise(db, weightExercise({ name: 'B' }));
    await updateExercise(db, { ...a, archived: true });
    expect((await listExercises(db)).map((e) => e.name)).toEqual(['B']);
    expect((await listExercises(db, true)).map((e) => e.name)).toEqual(['A', 'B']);
  });
});

describe('세션과 세트', () => {
  it('같은 운동·같은 날은 한 세션, 목표는 처음 것만 저장', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, weightExercise());
    const s1 = await getOrCreateSession(db, ex.id, '2026-10-17');
    const s2 = await getOrCreateSession(db, ex.id, '2026-10-17', target);
    const s3 = await getOrCreateSession(db, ex.id, '2026-10-17', { type: 'double', sets: [] });
    expect(s2.id).toBe(s1.id);
    expect(s3.target).toEqual(target);
    await setSessionTarget(db, s1.id, { type: 'double', sets: [] });
    expect((await db.sessions.get(s1.id))?.target).toEqual({ type: 'double', sets: [] });
  });
  it('세트 순서는 마지막+1, 삭제 후에도 겹치지 않는다', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, weightExercise());
    const s = await getOrCreateSession(db, ex.id, '2026-10-17');
    const a = await addWeightSet(db, s.id, [{ weight: 40, reps: 12 }]);
    await addWeightSet(db, s.id, [{ weight: 40, reps: 10 }]);
    await deleteWeightSet(db, a.id);
    const c = await addWeightSet(db, s.id, [{ weight: 40, reps: 9 }, { weight: 30, reps: 3 }]);
    expect(c.order).toBe(2);
    await updateWeightSet(db, c.id, [{ weight: 40, reps: 10 }]);
    expect((await listWeightSets(db, s.id)).map((x) => x.segments[0].reps)).toEqual([10, 10]);
  });
  it('잘못된 구간을 거부한다', async () => {
    const db = makeTestDb();
    await expect(addWeightSet(db, 's', [])).rejects.toThrow('구간이 하나 이상 있어야 해요');
    await expect(addWeightSet(db, 's', [{ weight: -1, reps: 5 }])).rejects.toThrow('무게는 0 이상이어야 해요');
    await expect(addWeightSet(db, 's', [{ weight: 10, reps: 0 }])).rejects.toThrow('횟수는 1 이상의 정수여야 해요');
  });
});

describe('유산소', () => {
  it('세션당 한 기록 — 다시 저장하면 교체', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, cardioExercise());
    const s = await getOrCreateSession(db, ex.id, '2026-10-17');
    await saveCardioEntry(db, s.id, { minutes: 20, intensity: { speed: 10 } });
    await saveCardioEntry(db, s.id, { minutes: 25, intensity: { speed: 10 }, distanceKm: 4.2, kcal: 250 });
    expect(await db.cardioEntries.count()).toBe(1);
    expect(await getCardioEntry(db, s.id)).toMatchObject({ minutes: 25, distanceKm: 4.2, kcal: 250 });
  });
  it('잘못된 값을 거부한다', async () => {
    const db = makeTestDb();
    await expect(saveCardioEntry(db, 's', { minutes: 0, intensity: {} })).rejects.toThrow('운동 시간은 0보다 커야 해요');
    await expect(saveCardioEntry(db, 's', { minutes: 10, intensity: { speed: -1 } })).rejects.toThrow('강도는 0 이상이어야 해요');
    await expect(saveCardioEntry(db, 's', { minutes: 10, intensity: {}, distanceKm: -1 })).rejects.toThrow('거리는 0 이상이어야 해요');
    await expect(saveCardioEntry(db, 's', { minutes: 10, intensity: {}, kcal: -5 })).rejects.toThrow('칼로리는 0 이상이어야 해요');
  });
});

describe('히스토리', () => {
  it('웨이트: 날짜 오름차순, 빈 세션 제외, 목표 포함', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, weightExercise());
    await seedWeightSession(db, ex.id, '2026-10-14', [[{ weight: 40, reps: 12 }]], target);
    await seedWeightSession(db, ex.id, '2026-10-10', [[{ weight: 40, reps: 10 }]]);
    await getOrCreateSession(db, ex.id, '2026-10-16');
    expect(await weightHistory(db, ex.id)).toEqual([
      { date: '2026-10-10', sets: [[{ weight: 40, reps: 10 }]] },
      { date: '2026-10-14', sets: [[{ weight: 40, reps: 12 }]], target },
    ]);
    expect(await exerciseHistory(db, ex)).toHaveLength(2);
  });
  it('유산소', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, cardioExercise());
    await seedCardioSession(db, ex.id, '2026-10-14', { minutes: 30, intensity: { speed: 10 }, kcal: 300 });
    expect(await cardioHistory(db, ex.id)).toEqual([{ date: '2026-10-14', minutes: 30, intensity: { speed: 10 }, kcal: 300 }]);
  });
  it('최근 7일 안에 기록한 운동 id', async () => {
    const db = makeTestDb();
    const a = await addExercise(db, weightExercise({ name: 'A' }));
    const b = await addExercise(db, weightExercise({ name: 'B' }));
    await seedWeightSession(db, a.id, '2026-10-11', [[{ weight: 1, reps: 1 }]]);
    await seedWeightSession(db, b.id, '2026-10-09', [[{ weight: 1, reps: 1 }]]);
    expect(await recentExerciseIds(db, '2026-10-17')).toEqual([a.id]);
  });
});

describe('메타', () => {
  it('get/set', async () => {
    const db = makeTestDb();
    expect(await getMeta(db, 'x')).toBeUndefined();
    await setMeta(db, 'x', ['a']);
    expect(await getMeta<string[]>(db, 'x')).toEqual(['a']);
  });
});
