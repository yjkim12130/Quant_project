import type { Badge } from '../../core/types';
import { BADGE_LABEL, BADGE_SYMBOL } from '../format';

export function BadgeStrip({ badges }: { badges: Badge[] }) {
  if (badges.length === 0) return null;
  return (
    <span className="badges" aria-label={`최근 기록 ${badges.map((b) => BADGE_LABEL[b]).join(', ')}`}>
      {badges.map((b, i) => (
        <span key={i} className={`badge badge-${b}`} title={BADGE_LABEL[b]}>
          {BADGE_SYMBOL[b]}
        </span>
      ))}
    </span>
  );
}
