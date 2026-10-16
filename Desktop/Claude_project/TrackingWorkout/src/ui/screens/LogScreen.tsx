import { useLiveQuery } from 'dexie-react-hooks';
import { ScreenHeader } from '../components/ScreenHeader';
import { useDb } from '../DbContext';
import type { Navigate } from '../routes';
import { CardioLog } from './CardioLog';
import { WeightLog } from './WeightLog';

export function LogScreen({ exerciseId, navigate }: { exerciseId: string; navigate: Navigate }) {
  const db = useDb();
  const loaded = useLiveQuery(async () => ({ ex: await db.exercises.get(exerciseId) }), [db, exerciseId]);
  if (!loaded) return <p className="muted">불러오는 중…</p>;
  if (!loaded.ex) return <ScreenHeader title="운동을 찾을 수 없어요" onBack={() => navigate({ name: 'today' })} />;
  return loaded.ex.kind === 'weight'
    ? <WeightLog exercise={loaded.ex} navigate={navigate} />
    : <CardioLog exercise={loaded.ex} navigate={navigate} />;
}
