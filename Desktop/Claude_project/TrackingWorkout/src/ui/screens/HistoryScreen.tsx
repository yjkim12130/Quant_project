import { useLiveQuery } from 'dexie-react-hooks';
import { badgesFor } from '../../core/badge';
import { shortDate } from '../../core/date';
import type { Badge, HistoryItem } from '../../core/types';
import { exerciseHistory, listExercises } from '../../db/repository';
import { BadgeStrip } from '../components/BadgeStrip';
import { ScreenHeader } from '../components/ScreenHeader';
import { useDb } from '../DbContext';
import { exerciseLabel } from '../format';
import type { Navigate } from '../routes';

export function HistoryScreen({ navigate }: { navigate: Navigate }) {
  const db = useDb();
  const rows = useLiveQuery(async () => {
    const exercises = await listExercises(db);
    return Promise.all(
      exercises.map(async (ex) => {
        const history = await exerciseHistory(db, ex);
        const badges = badgesFor(ex, history).filter((b): b is Badge => b !== null).slice(-5);
        const last = (history as HistoryItem[]).at(-1)?.date ?? null;
        return { ex, last, count: history.length, badges };
      }),
    );
  }, [db]);

  return (
    <>
      <ScreenHeader title="기록" />
      {!rows && <p className="muted">불러오는 중…</p>}
      {rows && rows.length === 0 && <p className="muted">등록된 운동이 없어요.</p>}
      <ul className="card-list">
        {rows?.map(({ ex, last, count, badges }) => (
          <li key={ex.id} className="card">
            <button type="button" className="card-main" onClick={() => navigate({ name: 'detail', exerciseId: ex.id })}>
              <span className="card-title">{exerciseLabel(ex)}</span>
              <span className="card-sub">{last ? `최근 ${shortDate(last)} · 총 ${count}회` : '기록 없음'}</span>
              <BadgeStrip badges={badges} />
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}
