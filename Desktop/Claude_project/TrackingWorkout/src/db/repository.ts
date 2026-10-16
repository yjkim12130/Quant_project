import { addDays } from '../core/date';
import type {
  CardioEntry, CardioHistoryItem, Exercise, History, Segment, Session, Target, WeightHistoryItem, WeightSetRecord,
} from '../core/types';
import type { WorkoutDB } from './schema';

export class DuplicateExerciseError extends Error {
  constructor(equipment: string, name: string) {
    super(`이미 등록된 운동이에요: ${equipment} · ${name}`);
    this.name = 'DuplicateExerciseError';
  }
}

export type NewExercise = Omit<Exercise, 'id' | 'createdAt' | 'archived'>;
export type CardioInput = Omit<CardioEntry, 'id' | 'sessionId'>;

/** http(LAN 개발 서버)에서는 crypto.randomUUID가 없을 수 있다 */
export function newId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

let lastCreatedAt = 0;
function nextCreatedAt(): number {
  lastCreatedAt = Math.max(Date.now(), lastCreatedAt + 1);
  return lastCreatedAt;
}

function cleanNames(e: { equipment: string; name: string }) {
  const equipment = e.equipment.trim();
  const name = e.name.trim();
  if (!equipment || !name) throw new Error('기구 이름과 운동 종류를 입력하세요');
  return { equipment, name };
}

async function assertUnique(db: WorkoutDB, equipment: string, name: string, selfId?: string) {
  const dup = await db.exercises.where('[equipment+name]').equals([equipment, name]).first();
  if (dup && dup.id !== selfId) throw new DuplicateExerciseError(equipment, name);
}

export async function addExercise(db: WorkoutDB, input: NewExercise): Promise<Exercise> {
  const names = cleanNames(input);
  await assertUnique(db, names.equipment, names.name);
  const ex: Exercise = { ...input, ...names, id: newId(), createdAt: nextCreatedAt(), archived: false };
  await db.exercises.add(ex);
  return ex;
}

export async function updateExercise(db: WorkoutDB, ex: Exercise): Promise<Exercise> {
  const names = cleanNames(ex);
  await assertUnique(db, names.equipment, names.name, ex.id);
  const next = { ...ex, ...names };
  await db.exercises.put(next);
  return next;
}

export async function listExercises(db: WorkoutDB, includeArchived = false): Promise<Exercise[]> {
  const all = await db.exercises.toArray();
  return all.filter((e) => includeArchived || !e.archived).sort((a, b) => a.createdAt - b.createdAt);
}

export function findSession(db: WorkoutDB, exerciseId: string, date: string): Promise<Session | undefined> {
  return db.sessions.where('[exerciseId+date]').equals([exerciseId, date]).first();
}

/** 같은 운동·같은 날 세션은 하나. 목표 스냅샷은 비어 있을 때만 채운다 */
export async function getOrCreateSession(
  db: WorkoutDB, exerciseId: string, date: string, target?: Target,
): Promise<Session> {
  return db.transaction('rw', db.sessions, async () => {
    const found = await findSession(db, exerciseId, date);
    if (found) {
      if (!found.target && target) {
        const next = { ...found, target };
        await db.sessions.put(next);
        return next;
      }
      return found;
    }
    const session: Session = { id: newId(), exerciseId, date, ...(target ? { target } : {}) };
    await db.sessions.add(session);
    return session;
  });
}

export async function setSessionTarget(db: WorkoutDB, sessionId: string, target: Target): Promise<void> {
  const s = await db.sessions.get(sessionId);
  if (s) await db.sessions.put({ ...s, target });
}

export function validateSegments(segments: Segment[]): void {
  if (segments.length === 0) throw new Error('구간이 하나 이상 있어야 해요');
  for (const s of segments) {
    if (!Number.isFinite(s.weight) || s.weight < 0) throw new Error('무게는 0 이상이어야 해요');
    if (!Number.isInteger(s.reps) || s.reps < 1) throw new Error('횟수는 1 이상의 정수여야 해요');
  }
}

const copySegments = (segments: Segment[]) => segments.map((s) => ({ weight: s.weight, reps: s.reps }));

export async function listWeightSets(db: WorkoutDB, sessionId: string): Promise<WeightSetRecord[]> {
  const sets = await db.weightSets.where('sessionId').equals(sessionId).toArray();
  return sets.sort((a, b) => a.order - b.order);
}

export async function addWeightSet(db: WorkoutDB, sessionId: string, segments: Segment[]): Promise<WeightSetRecord> {
  validateSegments(segments);
  return db.transaction('rw', db.weightSets, async () => {
    const existing = await listWeightSets(db, sessionId);
    const order = existing.length ? existing[existing.length - 1].order + 1 : 0;
    const record: WeightSetRecord = { id: newId(), sessionId, order, segments: copySegments(segments) };
    await db.weightSets.add(record);
    return record;
  });
}

export async function updateWeightSet(db: WorkoutDB, id: string, segments: Segment[]): Promise<void> {
  validateSegments(segments);
  const record = await db.weightSets.get(id);
  if (!record) throw new Error('세트를 찾을 수 없어요');
  await db.weightSets.put({ ...record, segments: copySegments(segments) });
}

export async function deleteWeightSet(db: WorkoutDB, id: string): Promise<void> {
  await db.weightSets.delete(id);
}

export function validateCardio(input: CardioInput): void {
  if (!Number.isFinite(input.minutes) || input.minutes <= 0) throw new Error('운동 시간은 0보다 커야 해요');
  for (const v of Object.values(input.intensity)) {
    if (!Number.isFinite(v) || v < 0) throw new Error('강도는 0 이상이어야 해요');
  }
  if (input.distanceKm !== undefined && (!Number.isFinite(input.distanceKm) || input.distanceKm < 0)) {
    throw new Error('거리는 0 이상이어야 해요');
  }
  if (input.kcal !== undefined && (!Number.isFinite(input.kcal) || input.kcal < 0)) {
    throw new Error('칼로리는 0 이상이어야 해요');
  }
}

export function getCardioEntry(db: WorkoutDB, sessionId: string): Promise<CardioEntry | undefined> {
  return db.cardioEntries.where('sessionId').equals(sessionId).first();
}

export async function saveCardioEntry(db: WorkoutDB, sessionId: string, input: CardioInput): Promise<CardioEntry> {
  validateCardio(input);
  return db.transaction('rw', db.cardioEntries, async () => {
    const existing = await getCardioEntry(db, sessionId);
    const entry: CardioEntry = {
      id: existing?.id ?? newId(),
      sessionId,
      minutes: input.minutes,
      intensity: { ...input.intensity },
      ...(input.distanceKm !== undefined ? { distanceKm: input.distanceKm } : {}),
      ...(input.kcal !== undefined ? { kcal: input.kcal } : {}),
    };
    await db.cardioEntries.put(entry);
    return entry;
  });
}

async function sessionsOf(db: WorkoutDB, exerciseId: string): Promise<Session[]> {
  const sessions = await db.sessions.where('exerciseId').equals(exerciseId).toArray();
  return sessions.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
}

export async function weightHistory(db: WorkoutDB, exerciseId: string): Promise<WeightHistoryItem[]> {
  const out: WeightHistoryItem[] = [];
  for (const s of await sessionsOf(db, exerciseId)) {
    const sets = await listWeightSets(db, s.id);
    if (sets.length === 0) continue;
    out.push({ date: s.date, sets: sets.map((x) => x.segments), ...(s.target ? { target: s.target } : {}) });
  }
  return out;
}

export async function cardioHistory(db: WorkoutDB, exerciseId: string): Promise<CardioHistoryItem[]> {
  const out: CardioHistoryItem[] = [];
  for (const s of await sessionsOf(db, exerciseId)) {
    const e = await getCardioEntry(db, s.id);
    if (!e) continue;
    out.push({
      date: s.date,
      minutes: e.minutes,
      intensity: e.intensity,
      ...(e.distanceKm !== undefined ? { distanceKm: e.distanceKm } : {}),
      ...(e.kcal !== undefined ? { kcal: e.kcal } : {}),
      ...(s.target ? { target: s.target } : {}),
    });
  }
  return out;
}

export function exerciseHistory(db: WorkoutDB, ex: Exercise): Promise<History> {
  return ex.kind === 'weight' ? weightHistory(db, ex.id) : cardioHistory(db, ex.id);
}

export async function recentExerciseIds(db: WorkoutDB, today: string, days = 7): Promise<string[]> {
  const sessions = await db.sessions.where('date').between(addDays(today, -days), today, true, true).toArray();
  return [...new Set(sessions.map((s) => s.exerciseId))];
}

export async function getMeta<T>(db: WorkoutDB, key: string): Promise<T | undefined> {
  return (await db.meta.get(key))?.value as T | undefined;
}

export async function setMeta(db: WorkoutDB, key: string, value: unknown): Promise<void> {
  await db.meta.put({ key, value });
}
