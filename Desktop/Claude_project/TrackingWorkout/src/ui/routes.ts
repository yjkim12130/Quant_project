export type Route =
  | { name: 'today' }
  | { name: 'log'; exerciseId: string }
  | { name: 'history' }
  | { name: 'detail'; exerciseId: string }
  | { name: 'settings' }
  | { name: 'exerciseForm'; exerciseId?: string };

export type Navigate = (route: Route) => void;
export type Tab = 'today' | 'history' | 'settings';

export function tabOf(route: Route): Tab {
  switch (route.name) {
    case 'today':
    case 'log':
      return 'today';
    case 'history':
    case 'detail':
      return 'history';
    default:
      return 'settings';
  }
}
