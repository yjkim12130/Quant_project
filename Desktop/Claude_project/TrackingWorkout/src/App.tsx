import { useState } from 'react';
import { TabBar } from './ui/components/TabBar';
import { tabOf, type Navigate, type Route } from './ui/routes';
import { DetailScreen } from './ui/screens/DetailScreen';
import { ExerciseFormScreen } from './ui/screens/ExerciseFormScreen';
import { HistoryScreen } from './ui/screens/HistoryScreen';
import { LogScreen } from './ui/screens/LogScreen';
import { SettingsScreen } from './ui/screens/SettingsScreen';
import { TodayScreen } from './ui/screens/TodayScreen';

function renderRoute(route: Route, navigate: Navigate) {
  switch (route.name) {
    case 'today':
      return <TodayScreen navigate={navigate} />;
    case 'log':
      return <LogScreen key={route.exerciseId} exerciseId={route.exerciseId} navigate={navigate} />;
    case 'history':
      return <HistoryScreen navigate={navigate} />;
    case 'detail':
      return <DetailScreen key={route.exerciseId} exerciseId={route.exerciseId} navigate={navigate} />;
    case 'settings':
      return <SettingsScreen navigate={navigate} />;
    case 'exerciseForm':
      return <ExerciseFormScreen key={route.exerciseId ?? 'new'} exerciseId={route.exerciseId} navigate={navigate} />;
  }
}

export function App() {
  const [route, setRoute] = useState<Route>({ name: 'today' });
  const navigate: Navigate = (r) => {
    setRoute(r);
    window.scrollTo?.(0, 0);
  };
  return (
    <div className="app">
      <main className="screen">{renderRoute(route, navigate)}</main>
      <TabBar active={tabOf(route)} onSelect={(tab) => navigate({ name: tab })} />
    </div>
  );
}
