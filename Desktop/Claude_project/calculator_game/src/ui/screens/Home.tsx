import type { CSSProperties } from 'react';
import { CATEGORIES, categoryCrowns } from '../../core/categories';
import { useGame } from '../../state/GameContext';
import { activeProfile } from '../../state/store';
import { Mascot } from '../components/Mascot';
import { TopBar } from '../components/TopBar';

export function Home() {
  const profile = useGame(activeProfile);
  const goto = useGame((s) => s.goto);
  if (!profile) return null;

  return (
    <>
      <TopBar />
      <main className="screen home">
        <Mascot mood="idle" size={88} speech={`${profile.name}, 오늘은 뭘 연습할까?`} />
        <div className="cat-grid">
          {CATEGORIES.map((c) => {
            const { earned, total } = categoryCrowns(c, profile.stages);
            return (
              <button
                key={c.id}
                className="cat-card"
                style={{ '--c': c.color } as CSSProperties}
                aria-label={`${c.title} 카테고리`}
                onClick={() => goto({ name: 'category', categoryId: c.id })}
              >
                <span className="cat-icon display" aria-hidden>{c.icon}</span>
                <span className="cat-title display">{c.title}</span>
                <span className="cat-crowns">{`👑 ${earned}/${total}`}</span>
              </button>
            );
          })}
        </div>
      </main>
    </>
  );
}
