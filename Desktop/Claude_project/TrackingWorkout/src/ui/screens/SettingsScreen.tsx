import type { Navigate } from '../routes';
import { ScreenHeader } from '../components/ScreenHeader';

export function SettingsScreen(_props: { navigate: Navigate }) {
  return <ScreenHeader title="설정" />;
}
