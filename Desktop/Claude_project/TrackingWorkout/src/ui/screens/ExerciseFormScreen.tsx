import type { Navigate } from '../routes';
import { ScreenHeader } from '../components/ScreenHeader';

export function ExerciseFormScreen(_props: { exerciseId?: string; navigate: Navigate }) {
  return <ScreenHeader title="운동 등록" />;
}
