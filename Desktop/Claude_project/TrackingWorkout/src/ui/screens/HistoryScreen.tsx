import type { Navigate } from '../routes';
import { ScreenHeader } from '../components/ScreenHeader';

export function HistoryScreen(_props: { navigate: Navigate }) {
  return <ScreenHeader title="기록" />;
}
