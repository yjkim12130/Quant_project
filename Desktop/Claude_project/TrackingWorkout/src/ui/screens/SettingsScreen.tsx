import { useLiveQuery } from 'dexie-react-hooks';
import type { Exercise } from '../../core/types';
import { listExercises } from '../../db/repository';
import { ScreenHeader } from '../components/ScreenHeader';
import { useDb } from '../DbContext';
import { exerciseLabel } from '../format';
import type { Navigate } from '../routes';

function ExerciseList({ items, navigate }: { items: Exercise[]; navigate: Navigate }) {
  return (
    <ul className="card-list">
      {items.map((ex) => (
        <li key={ex.id} className="card">
          <button type="button" className="card-main" onClick={() => navigate({ name: 'exerciseForm', exerciseId: ex.id })}>
            <span className="card-title">{exerciseLabel(ex)}</span>
            <span className="card-sub">{ex.kind === 'weight' ? '웨이트' : '유산소'}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

export function SettingsScreen({ navigate }: { navigate: Navigate }) {
  const db = useDb();
  const exercises = useLiveQuery(() => listExercises(db, true), [db]);
  const active = exercises?.filter((e) => !e.archived) ?? [];
  const archived = exercises?.filter((e) => e.archived) ?? [];

  return (
    <>
      <ScreenHeader title="설정" />
      <h2 className="section-title">운동</h2>
      {exercises && active.length === 0 && <p className="muted">등록된 운동이 없어요.</p>}
      <ExerciseList items={active} navigate={navigate} />
      <div className="row">
        <button type="button" className="primary" onClick={() => navigate({ name: 'exerciseForm' })}>+ 운동 추가</button>
      </div>
      {archived.length > 0 && (
        <section aria-label="숨긴 운동">
          <h2 className="section-title">숨긴 운동</h2>
          <ExerciseList items={archived} navigate={navigate} />
        </section>
      )}
      <p className="muted" style={{ marginTop: 24, fontSize: 13 }}>오늘도 +1 · 기록은 이 기기에만 저장돼요.</p>
    </>
  );
}
