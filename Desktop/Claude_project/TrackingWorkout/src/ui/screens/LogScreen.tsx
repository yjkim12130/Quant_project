import type { Navigate } from '../routes';
import { ScreenHeader } from '../components/ScreenHeader';

export function LogScreen(_props: { exerciseId: string; navigate: Navigate }) {
  return <ScreenHeader title="기록하기" />;
}
