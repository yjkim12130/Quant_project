import type { CardioEntry, Exercise, Session, WeightSetRecord } from '../core/types';
import { setMeta } from './repository';
import type { MetaRow, WorkoutDB } from './schema';

export const BACKUP_APP = 'tracking-workout';
export const BACKUP_VERSION = 1;

export interface BackupData {
  exercises: Exercise[];
  sessions: Session[];
  weightSets: WeightSetRecord[];
  cardioEntries: CardioEntry[];
  meta: MetaRow[];
}

export interface BackupFile {
  app: typeof BACKUP_APP;
  version: number;
  exportedAt: string;
  data: BackupData;
}

export class BackupError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'BackupError';
  }
}

export async function exportBackup(db: WorkoutDB, now: Date = new Date()): Promise<BackupFile> {
  const [exercises, sessions, weightSets, cardioEntries, meta] = await Promise.all([
    db.exercises.toArray(), db.sessions.toArray(), db.weightSets.toArray(), db.cardioEntries.toArray(), db.meta.toArray(),
  ]);
  return {
    app: BACKUP_APP, version: BACKUP_VERSION, exportedAt: now.toISOString(),
    data: { exercises, sessions, weightSets, cardioEntries, meta },
  };
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function check(items: unknown[], ok: (v: Record<string, unknown>) => boolean, message: string) {
  for (const v of items) if (!isObj(v) || !ok(v)) throw new BackupError(message);
}

export function parseBackup(text: string): BackupFile {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    throw new BackupError('JSON 형식의 백업 파일이 아니에요');
  }
  if (!isObj(raw) || raw.app !== BACKUP_APP) throw new BackupError('이 앱의 백업 파일이 아니에요');
  if (typeof raw.version !== 'number' || raw.version > BACKUP_VERSION) {
    throw new BackupError('지원하지 않는 백업 버전이에요. 앱을 업데이트하세요');
  }
  const d = raw.data;
  if (!isObj(d)) throw new BackupError('백업에 데이터가 없어요');
  const list = (key: string): unknown[] => {
    const v = d[key];
    if (!Array.isArray(v)) throw new BackupError(`백업에 ${key} 목록이 없어요`);
    return v;
  };
  const exercises = list('exercises');
  const sessions = list('sessions');
  const weightSets = list('weightSets');
  const cardioEntries = list('cardioEntries');
  const meta: unknown[] = Array.isArray(d.meta) ? d.meta : [];

  check(exercises, (e) => typeof e.id === 'string' && typeof e.equipment === 'string' && typeof e.name === 'string'
    && (e.kind === 'weight' || e.kind === 'cardio'), '운동 데이터가 손상됐어요');
  check(sessions, (s) => typeof s.id === 'string' && typeof s.exerciseId === 'string'
    && typeof s.date === 'string' && DATE_RE.test(s.date), '세션 데이터가 손상됐어요');
  check(weightSets, (w) => typeof w.id === 'string' && typeof w.sessionId === 'string' && Array.isArray(w.segments),
    '세트 데이터가 손상됐어요');
  check(cardioEntries, (c) => typeof c.id === 'string' && typeof c.sessionId === 'string' && typeof c.minutes === 'number',
    '유산소 데이터가 손상됐어요');
  check(meta, (m) => typeof m.key === 'string', '설정 데이터가 손상됐어요');

  return {
    app: BACKUP_APP,
    version: raw.version,
    exportedAt: typeof raw.exportedAt === 'string' ? raw.exportedAt : '',
    data: {
      exercises: exercises as Exercise[],
      sessions: sessions as Session[],
      weightSets: weightSets as WeightSetRecord[],
      cardioEntries: cardioEntries as CardioEntry[],
      meta: meta as MetaRow[],
    },
  };
}

/** 현재 데이터를 모두 지우고 백업 내용으로 교체한다(한 트랜잭션) */
export async function restoreBackup(db: WorkoutDB, file: BackupFile): Promise<void> {
  await db.transaction('rw', [db.exercises, db.sessions, db.weightSets, db.cardioEntries, db.meta], async () => {
    await Promise.all([
      db.exercises.clear(), db.sessions.clear(), db.weightSets.clear(), db.cardioEntries.clear(), db.meta.clear(),
    ]);
    await db.exercises.bulkAdd(file.data.exercises);
    await db.sessions.bulkAdd(file.data.sessions);
    await db.weightSets.bulkAdd(file.data.weightSets);
    await db.cardioEntries.bulkAdd(file.data.cardioEntries);
    await db.meta.bulkAdd(file.data.meta);
  });
}

export async function markBackedUp(db: WorkoutDB, now: Date = new Date()): Promise<void> {
  await setMeta(db, 'lastBackupAt', now.toISOString());
}

export function backupFileName(now: Date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `tracking-workout-${now.getFullYear()}${p(now.getMonth() + 1)}${p(now.getDate())}-${p(now.getHours())}${p(now.getMinutes())}.json`;
}
