import { useLiveQuery } from 'dexie-react-hooks';
import { useState } from 'react';
import { badgesFor } from '../../core/badge';
import { shortDate, todayLocal } from '../../core/date';
import { cardioSeries, filterByRange, weightSeries, type Range } from '../../core/series';
import type { CardioHistoryItem, Exercise, History, HistoryItem, WeightHistoryItem } from '../../core/types';
import { exerciseHistory } from '../../db/repository';
import { CardioCharts } from '../charts/CardioCharts';
import { WeightCharts } from '../charts/WeightCharts';
import { ScreenHeader } from '../components/ScreenHeader';
import { useDb } from '../DbContext';
import { BADGE_LABEL, BADGE_SYMBOL, exerciseLabel, formatCardio, formatSet } from '../format';
import type { Navigate } from '../routes';

const RANGES: { id: Range; label: string }[] = [
  { id: '4w', label: '4주' },
  { id: '3m', label: '3개월' },
  { id: 'all', label: '전체' },
];

function describeItem(ex: Exercise, item: HistoryItem): string {
  if (ex.kind === 'weight') return (item as WeightHistoryItem).sets.map(formatSet).join(' / ');
  const c = item as CardioHistoryItem;
  const extra = [c.distanceKm != null ? `${c.distanceKm}km` : null, c.kcal != null ? `${c.kcal}kcal` : null]
    .filter((s): s is string => s !== null);
  return [formatCardio(c, ex.cardio!.metrics), ...extra].join(' · ');
}

export function DetailScreen({ exerciseId, navigate }: { exerciseId: string; navigate: Navigate }) {
  const db = useDb();
  const today = todayLocal();
  const [range, setRange] = useState<Range>('4w');
  const data = useLiveQuery(async () => {
    const ex = await db.exercises.get(exerciseId);
    return ex ? { ex, history: await exerciseHistory(db, ex) } : { ex: null, history: [] as History };
  }, [db, exerciseId]);

  if (!data) return <p className="muted">불러오는 중…</p>;
  const back = () => navigate({ name: 'history' });
  if (!data.ex) return <ScreenHeader title="운동을 찾을 수 없어요" onBack={back} />;
  const ex = data.ex;

  const badges = badgesFor(ex, data.history);
  const rows = (data.history as HistoryItem[])
    .map((item, i) => ({ item, badge: badges[i] }))
    .filter(({ item }) => filterByRange([item], range, today).length > 0)
    .reverse();

  return (
    <>
      <ScreenHeader title={exerciseLabel(ex)} onBack={back} />
      <div className="seg-toggle" role="group" aria-label="기간">
        {RANGES.map((r) => (
          <button key={r.id} type="button" aria-pressed={range === r.id} onClick={() => setRange(r.id)}>{r.label}</button>
        ))}
      </div>

      {rows.length === 0 ? (
        <p className="muted">이 기간에 기록이 없어요.</p>
      ) : ex.kind === 'weight' ? (
        <WeightCharts points={filterByRange(weightSeries(data.history as WeightHistoryItem[]), range, today)} />
      ) : (
        <CardioCharts
          points={filterByRange(cardioSeries(data.history as CardioHistoryItem[], ex.cardio!.primaryMetric), range, today)}
          primary={ex.cardio!.metrics.find((m) => m.key === ex.cardio!.primaryMetric)}
        />
      )}

      {rows.length > 0 && <h2 className="section-title">세션 기록</h2>}
      <ul className="plain-list history-list" aria-label="세션 기록">
        {rows.map(({ item, badge }) => (
          <li key={item.date} className="history-row">
            <span className="muted">{shortDate(item.date)}</span>
            <span style={{ flex: 1 }}>{describeItem(ex, item)}</span>
            {badge && <span className={`badge badge-${badge}`} title={BADGE_LABEL[badge]}>{BADGE_SYMBOL[badge]}</span>}
          </li>
        ))}
      </ul>
    </>
  );
}
