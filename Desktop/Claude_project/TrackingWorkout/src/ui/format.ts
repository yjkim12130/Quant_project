import type { Badge, CardioMetric, Exercise, SetSegments, Target, WeightTarget } from '../core/types';

export const BADGE_SYMBOL: Record<Badge, string> = { up: '▲', same: '＝', down: '▼' };
export const BADGE_LABEL: Record<Badge, string> = { up: '달성', same: '유지', down: '하락' };

const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

export function formatKg(w: number): string {
  return String(Number(w.toFixed(2)));
}

export function formatSet(set: SetSegments): string {
  return set.map((s) => `${formatKg(s.weight)}kg×${s.reps}`).join(' → ');
}

export function formatWeightTarget(t: WeightTarget): string {
  const sameWeight = new Set(t.sets.map((s) => s.weight)).size === 1;
  const base = sameWeight
    ? `${formatKg(t.sets[0].weight)}kg × ${t.sets.map((s) => s.reps).join('/')}`
    : t.sets.map((s) => `${formatKg(s.weight)}×${s.reps}`).join(' / ');
  return t.type === 'volume' ? `${base} (볼륨 ${t.volume}kg)` : base;
}

export function formatCardio(v: { minutes: number; intensity: Record<string, number> }, metrics: CardioMetric[]): string {
  return [`${v.minutes}분`, ...metrics.map((m) => `${m.label} ${v.intensity[m.key] ?? 0}${m.unit}`)].join(' · ');
}

export function formatTarget(t: Target, ex: Exercise): string {
  return t.type === 'cardio' ? formatCardio(t, ex.cardio?.metrics ?? []) : formatWeightTarget(t);
}

export function formatLongDate(date: string): string {
  const day = new Date(`${date}T00:00:00Z`).getUTCDay();
  return `${Number(date.slice(5, 7))}월 ${Number(date.slice(8, 10))}일 (${WEEKDAYS[day]})`;
}

export function exerciseLabel(ex: Pick<Exercise, 'equipment' | 'name'>): string {
  return `${ex.equipment} · ${ex.name}`;
}
