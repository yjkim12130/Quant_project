import type { Exercise } from '../../core/types';
import { ScreenHeader } from '../components/ScreenHeader';
import { exerciseLabel } from '../format';
import type { Navigate } from '../routes';

export function CardioLog({ exercise, navigate }: { exercise: Exercise; navigate: Navigate }) {
  return <ScreenHeader title={exerciseLabel(exercise)} onBack={() => navigate({ name: 'today' })} />;
}
