import { motion } from 'framer-motion';

const EMOJI = ['🎉', '⭐', '🎊', '✨'];
// i, i+8, i+16 은 가로로 4%씩만 떨어져 있어서, 지연·모양까지 같으면 세 개가 붙어서 떨어진다 → 둘 다 섞는다
const PIECES = Array.from({ length: 24 }, (_, i) => ({
  left: (i * 37) % 100,
  delay: ((i * 7) % 24) * 0.05,
  emoji: EMOJI[(i + Math.floor(i / 8)) % EMOJI.length],
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
