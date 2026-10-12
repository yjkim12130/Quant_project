import { motion } from 'framer-motion';
import { callName } from '../../core/korean';
import { levelFromXp } from '../../core/scoring';
import { displayStreak } from '../../core/streak';
import { useGame } from '../../state/GameContext';
import { activeProfile } from '../../state/store';
import { Button3D } from '../components/Button3D';
import { Confetti } from '../components/Confetti';
import { Mascot } from '../components/Mascot';

export function Intro() {
  const profile = useGame(activeProfile);
  const enter = useGame((s) => s.enter);
  const today = useGame((s) => s.today);

  const who = profile ? callName(profile.name) : '우리 친구';
  const crowns = profile ? Object.values(profile.stages).reduce((n, s) => n + s.crowns, 0) : 0;
  const streak = profile ? displayStreak(profile.streak, today()) : 0;

  return (
    <main className="screen screen-center intro">
      <Confetti />
      <motion.div initial={{ scale: 0.3, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: 'spring', damping: 11 }}>
        <Mascot mood="happy" size={140} />
      </motion.div>
      <motion.h1
        className="intro-title"
        initial={{ y: 30, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.35, type: 'spring', damping: 12 }}
      >
        <span className="intro-line">
          <span className="intro-name">{who}</span>만을 위한
        </span>{' '}
        <span className="intro-line">계산 게임~</span>
      </motion.h1>
      {profile && (
        <motion.div className="intro-badges" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.8 }}>
          <span>{`⭐ Lv.${levelFromXp(profile.xp)}`}</span>
          <span>{`👑 ${crowns}개`}</span>
          <span>{`🔥 ${streak}일 연속`}</span>
        </motion.div>
      )}
      <motion.div className="intro-start" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1 }}>
        <Button3D full onClick={enter}>
          시작!
        </Button3D>
      </motion.div>
    </main>
  );
}
