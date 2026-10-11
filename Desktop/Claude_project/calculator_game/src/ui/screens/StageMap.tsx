import { motion } from 'framer-motion';
import { useEffect, useRef, type CSSProperties } from 'react';
import { isStageUnlocked } from '../../core/scoring';
import { STAGES, UNITS } from '../../core/stages';
import { useGame } from '../../state/GameContext';
import { activeProfile } from '../../state/store';
import { TopBar } from '../components/TopBar';

// 지그재그 경로 가로 위치(px)
const OFFSETS = [0, 56, 84, 56, 0, -56, -84, -56];

export function StageMap() {
  const profile = useGame(activeProfile);
  const goto = useGame((s) => s.goto);
  const currentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    currentRef.current?.scrollIntoView?.({ block: 'center' });
  }, []);

  if (!profile) return null;
  const current = STAGES.find((s) => isStageUnlocked(s.id, profile) && (profile.stages[s.id]?.crowns ?? 0) < 3);

  return (
    <>
      <TopBar />
      <main className="screen map">
        {UNITS.map((u) => (
          <section key={u.unit} className="unit">
            <div className="unit-banner" style={{ background: u.color }}>
              <div className="unit-label">유닛 {u.unit}</div>
              <h2>{u.title}</h2>
            </div>
            <div className="unit-path">
              {STAGES.filter((s) => s.unit === u.unit).map((s) => {
                const crowns = profile.stages[s.id]?.crowns ?? 0;
                const unlocked = isStageUnlocked(s.id, profile);
                const isCurrent = s.id === current?.id;
                const state = crowns >= 3 ? 'done' : unlocked ? 'open' : 'locked';
                return (
                  <div
                    key={s.id}
                    ref={isCurrent ? currentRef : undefined}
                    className="node-wrap"
                    style={{ transform: `translateX(${OFFSETS[STAGES.indexOf(s) % OFFSETS.length]}px)` }}
                  >
                    {isCurrent && <div className="node-start display">시작!</div>}
                    <motion.button
                      className={`node ${state}`}
                      style={{ '--c': u.color } as CSSProperties}
                      disabled={!unlocked}
                      aria-label={`${s.title} 단계${unlocked ? '' : ' (잠김)'}`}
                      animate={isCurrent ? { y: [0, -6, 0] } : undefined}
                      transition={isCurrent ? { duration: 1.4, repeat: Infinity } : undefined}
                      onClick={() => goto({ name: 'lesson', stageId: s.id })}
                    >
                      {state === 'done' ? '👑' : state === 'open' ? u.icon : '🔒'}
                    </motion.button>
                    <div className="node-title">{s.title}</div>
                    <div className="node-crowns" aria-hidden>
                      {[0, 1, 2].map((i) => (
                        <span key={i} className={i < crowns ? 'on' : ''} />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </main>
    </>
  );
}
