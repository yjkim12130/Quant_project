import { motion } from 'framer-motion';

const EMOJI = ['🎉', '⭐', '🎊', '✨'];
const PIECES = Array.from({ length: 24 }, (_, i) => ({
  left: (i * 37) % 100,
  delay: (i % 8) * 0.12,
  emoji: EMOJI[i % EMOJI.length],
}));

export function Confetti() {
  return (
    <div className="confetti" aria-hidden>
      {PIECES.map((p, i) => (
        <motion.span
          key={i}
          style={{ left: `${p.left}%` }}
          initial={{ y: -30, opacity: 1, rotate: 0 }}
          animate={{ y: 760, opacity: 0, rotate: 360 }}
          transition={{ duration: 2.2, delay: p.delay, ease: 'easeIn' }}
        >
          {p.emoji}
        </motion.span>
      ))}
    </div>
  );
}
