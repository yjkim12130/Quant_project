import { useLiveQuery } from 'dexie-react-hooks';
import { useState } from 'react';
import { todayLocal } from '../../core/date';
import { BadgeStrip } from '../components/BadgeStrip';
import { InstallBanner } from '../components/InstallBanner';
import { useDb } from '../DbContext';
import { exerciseLabel, formatLongDate, formatTarget } from '../format';
import type { Navigate } from '../routes';
import { addToToday, loadToday, moveItem, type TodayItem } from '../today/loadToday';

function summary(item: TodayItem): string {
  if (item.doneToday) return '✔ 오늘 기록함';
  const rec = item.recommendation;
  return rec.status === 'first' ? '첫 기록 — 시작 값을 입력하세요' : `목표 ${formatTarget(rec.options[0].target, item.exercise)}`;
}

export function TodayScreen({ navigate }: { navigate: Navigate }) {
  const db = useDb();
  const today = todayLocal();
  const data = useLiveQuery(() => loadToday(db, today), [db, today]);
  const [editing, setEditing] = useState(false);
  const [picking, setPicking] = useState(false);

  if (!data) return <p className="muted">불러오는 중…</p>;
  const ids = data.items.map((i) => i.exercise.id);

  return (
    <>
      <header className="today-head">
        <h1>{formatLongDate(today)}</h1>
        <span className="rate">4주 달성률 {data.rate === null ? '-' : `${Math.round(data.rate * 100)}%`}</span>
      </header>

      <InstallBanner />
      {data.needsBackup && (
        <div className="banner" role="note">
          <span>백업한 지 오래됐어요.</span>
          <button type="button" onClick={() => navigate({ name: 'settings' })}>백업하러 가기</button>
        </div>
      )}

      {data.items.length === 0 && (
        <p className="muted">설정에서 운동을 등록하거나, 아래에서 오늘 할 운동을 추가하세요.</p>
      )}

      <ul className="card-list">
        {data.items.map((item, i) => {
          const label = exerciseLabel(item.exercise);
          return (
            <li key={item.exercise.id} className="card">
              <button type="button" className="card-main" onClick={() => navigate({ name: 'log', exerciseId: item.exercise.id })}>
                <span className="card-title">{label}</span>
                <span className="card-sub">{summary(item)}</span>
                <BadgeStrip badges={item.recentBadges} />
              </button>
              {editing && (
                <div className="order-btns">
                  <button type="button" aria-label={`${label} 위로`} disabled={i === 0} onClick={() => moveItem(db, ids, i, -1)}>↑</button>
                  <button type="button" aria-label={`${label} 아래로`} disabled={i === ids.length - 1} onClick={() => moveItem(db, ids, i, 1)}>↓</button>
                </div>
              )}
            </li>
          );
        })}
      </ul>

      <div className="row">
        <button type="button" onClick={() => setPicking((p) => !p)}>+ 오늘 할 운동 추가</button>
        {data.items.length > 1 && (
          <button type="button" onClick={() => setEditing((e) => !e)}>{editing ? '순서 완료' : '순서 편집'}</button>
        )}
      </div>

      {picking && (
        <ul className="plain-list">
          {data.others.map((ex) => (
            <li key={ex.id}>
              <button
                type="button"
                aria-label={`${exerciseLabel(ex)} 추가`}
                style={{ width: '100%', textAlign: 'left' }}
                onClick={async () => {
                  await addToToday(db, today, ex.id);
                  setPicking(false);
                }}
              >
                {exerciseLabel(ex)}
              </button>
            </li>
          ))}
          {data.others.length === 0 && <li className="muted">추가할 운동이 없어요. 설정에서 운동을 등록하세요.</li>}
        </ul>
      )}
    </>
  );
}
