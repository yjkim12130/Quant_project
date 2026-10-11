import { motion } from 'framer-motion';

export type Mood = 'idle' | 'happy' | 'cheer';

const MOTION = {
  idle: { animate: { y: [0, -3, 0] }, transition: { duration: 2, repeat: Infinity } },
  happy: { animate: { y: [0, -14, 0] }, transition: { duration: 0.5 } },
  cheer: { animate: { rotate: [0, -8, 8, 0] }, transition: { duration: 0.5 } },
};

export function Mascot({ mood = 'idle', size = 96, speech }: { mood?: Mood; size?: number; speech?: string }) {
  const m = MOTION[mood];
  return (
    <div className="mascot">
      {speech && <div className="speech">{speech}</div>}
      <motion.svg key={mood} width={size} height={size} viewBox="0 0 100 100" aria-hidden animate={m.animate} transition={m.transition}>
        <path d="M44 14 Q50 2 56 14" stroke="#F5A700" strokeWidth="4" fill="none" strokeLinecap="round" />
        <ellipse cx="17" cy="60" rx="9" ry="14" fill="#F5C200" transform="rotate(20 17 60)" />
        <ellipse cx="83" cy="60" rx="9" ry="14" fill="#F5C200" transform="rotate(-20 83 60)" />
        <circle cx="50" cy="55" r="36" fill="#FFD43B" />
        {mood === 'happy' ? (
          <>
            <path d="M31 50 Q38 41 45 50" stroke="#3C3C3C" strokeWidth="4" fill="none" strokeLinecap="round" />
            <path d="M55 50 Q62 41 69 50" stroke="#3C3C3C" strokeWidth="4" fill="none" strokeLinecap="round" />
          </>
        ) : (
          <>
            <circle cx="38" cy="48" r="5.5" fill="#3C3C3C" />
            <circle cx="62" cy="48" r="5.5" fill="#3C3C3C" />
            <circle cx="40" cy="46" r="1.8" fill="#fff" />
            <circle cx="64" cy="46" r="1.8" fill="#fff" />
          </>
        )}
        {mood === 'cheer' && (
          <>
            <path d="M31 38 L43 36" stroke="#3C3C3C" strokeWidth="3" strokeLinecap="round" />
            <path d="M57 36 L69 38" stroke="#3C3C3C" strokeWidth="3" strokeLinecap="round" />
          </>
        )}
        <circle cx="29" cy="61" r="5" fill="#FF9AA2" opacity="0.7" />
        <circle cx="71" cy="61" r="5" fill="#FF9AA2" opacity="0.7" />
        <path d="M44 58 L56 58 L50 67 Z" fill="#FF9600" />
        <path d="M40 90 v7 M60 90 v7" stroke="#FF9600" strokeWidth="4" strokeLinecap="round" />
      </motion.svg>
    </div>
  );
}
