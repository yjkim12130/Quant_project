import type { Navigate } from '../routes';
import { ScreenHeader } from '../components/ScreenHeader';

export function TodayScreen(_props: { navigate: Navigate }) {
  return <ScreenHeader title="오늘" />;
}
