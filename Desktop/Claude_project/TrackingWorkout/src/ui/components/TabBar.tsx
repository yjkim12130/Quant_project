import type { Tab } from '../routes';

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'today', label: '오늘', icon: '🏋️' },
  { id: 'history', label: '기록', icon: '📈' },
  { id: 'settings', label: '설정', icon: '⚙️' },
];

export function TabBar({ active, onSelect }: { active: Tab; onSelect: (tab: Tab) => void }) {
  return (
    <nav className="tabbar" aria-label="메인 메뉴">
      {TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          className={t.id === active ? 'tab active' : 'tab'}
          aria-current={t.id === active ? 'page' : undefined}
          onClick={() => onSelect(t.id)}
        >
          <span aria-hidden="true">{t.icon}</span>
          {t.label}
        </button>
      ))}
    </nav>
  );
}
