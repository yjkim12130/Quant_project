import type { CSSProperties } from 'react';
import { getCategory, type CategoryId } from '../../core/categories';
import { getStage } from '../../core/stages';
import { useGame } from '../../state/GameContext';
import { activeProfile } from '../../state/store';
import { TopBar } from '../components/TopBar';

export function Category({ categoryId }: { categoryId: CategoryId }) {
  const profile = useGame(activeProfile);
  const goto = useGame((s) => s.goto);
  if (!profile) return null;
  const cat = getCategory(categoryId);

  return (
    <>
      <TopBar />
      <main className="screen category" style={{ '--c': cat.color } as CSSProperties}>
        <div className="cat-head">
          <button className="icon-btn" aria-label="뒤로" onClick={() => goto({ name: 'home' })}>
            ←
          </button>
          <h1 className="cat-head-title">{cat.title}</h1>
        </div>
        <div className="tile-grid">
          {cat.stageIds.map((id) => {
            const s = getStage(id);
            const crowns = profile.stages[id]?.crowns ?? 0;
            const done = crowns >= 3;
            return (
              <button
                key={id}
                className={`tile${s.short ? '' : ' wide'}${done ? ' done' : ''}`}
                aria-label={`${s.title} 단계`}
                onClick={() => goto({ name: 'lesson', stageId: id, categoryId })}
              >
                <span className="tile-label display">{s.short ?? s.title}</span>
                <span className="tile-crowns" aria-hidden>
                  {[0, 1, 2].map((i) => (
                    <span key={i} className={i < crowns ? 'on' : ''} />
                  ))}
                </span>
              </button>
            );
          })}
        </div>
      </main>
    </>
  );
}
