import { achievementRate, badgesFor } from '../../core/badge';
import { addDays, daysBetween } from '../../core/date';
import { BACKUP_WARN_DAYS } from '../../core/defaults';
import { recommend } from '../../core/progression/rules';
import type { Badge, Exercise, History, HistoryItem, Recommendation } from '../../core/types';
import { exerciseHistory, getMeta, listExercises, recentExerciseIds, setMeta } from '../../db/repository';
import type { WorkoutDB } from '../../db/schema';

export interface TodayItem {
  exercise: Exercise;
  recommendation: Recommendation;
  recentBadges: Badge[];
  doneToday: boolean;
}

export interface TodayData {
  items: TodayItem[];
  others: Exercise[];
  rate: number | null;
  needsBackup: boolean;
}

const extraKey = (today: string) => `todayExtra:${today}`;

export async function loadToday(db: WorkoutDB, today: string): Promise<TodayData> {
  const exercises = await listExercises(db);
  const recent = new Set(await recentExerciseIds(db, today, 7));
  const extra = new Set((await getMeta<string[]>(db, extraKey(today))) ?? []);
  const order = (await getMeta<string[]>(db, 'order')) ?? [];
  const pos = (id: string) => {
    const i = order.indexOf(id);
    return i === -1 ? Number.MAX_SAFE_INTEGER : i;
  };
  const chosen = exercises
    .filter((e) => recent.has(e.id) || extra.has(e.id))
    .sort((a, b) => pos(a.id) - pos(b.id) || a.createdAt - b.createdAt);

  const from = addDays(today, -28);
  const windowBadges: (Badge | null)[] = [];
  const cache = new Map<string, { history: History; badges: (Badge | null)[] }>();
  for (const ex of exercises) {
    const history = await exerciseHistory(db, ex);
    const badges = badgesFor(ex, history);
    (history as HistoryItem[]).forEach((h, i) => {
      if (h.date >= from && h.date <= today) windowBadges.push(badges[i]);
    });
    cache.set(ex.id, { history, badges });
  }

  const items = chosen.map((ex) => {
    const { history, badges } = cache.get(ex.id)!;
    return {
      exercise: ex,
      recommendation: recommend(ex, history, today),
      recentBadges: badges.filter((b): b is Badge => b !== null).slice(-5),
      doneToday: (history as HistoryItem[]).some((h) => h.date === today),
    };
  });

  const lastBackupAt = await getMeta<string>(db, 'lastBackupAt');
  const hasData = (await db.sessions.count()) > 0;
  const needsBackup = hasData && (!lastBackupAt || daysBetween(lastBackupAt.slice(0, 10), today) > BACKUP_WARN_DAYS);

  return { items, others: exercises.filter((e) => !chosen.includes(e)), rate: achievementRate(windowBadges), needsBackup };
}

export async function addToToday(db: WorkoutDB, today: string, exerciseId: string): Promise<void> {
  const current = (await getMeta<string[]>(db, extraKey(today))) ?? [];
  if (!current.includes(exerciseId)) await setMeta(db, extraKey(today), [...current, exerciseId]);
}

/** 화면에 보이는 순서(ids)에서 index 항목을 delta만큼 옮겨 전역 순서로 저장 */
export async function moveItem(db: WorkoutDB, ids: string[], index: number, delta: -1 | 1): Promise<void> {
  const j = index + delta;
  if (j < 0 || j >= ids.length) return;
  const next = [...ids];
  [next[index], next[j]] = [next[j], next[index]];
  const old = (await getMeta<string[]>(db, 'order')) ?? [];
  await setMeta(db, 'order', [...next, ...old.filter((id) => !next.includes(id))]);
}
