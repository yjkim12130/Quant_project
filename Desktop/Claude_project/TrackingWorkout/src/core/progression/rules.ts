import { daysBetween } from '../date';
import { DELOAD_RATIO, RETURN_GAP_DAYS } from '../defaults';
import { roundTo, sessionE1rm, targetVolume, totalVolume, workingWeight } from '../metrics';
import type {
  CardioConfig, CardioHistoryItem, Exercise, History, Recommendation, SetTarget,
  TargetOption, WeightConfig, WeightHistoryItem, WeightTarget,
} from '../types';
import { cardioTarget } from './cardio';
import { doubleTarget } from './weightDouble';
import { volumePlan } from './weightVolume';

export function isStalled(e1rms: number[]): boolean {
  if (e1rms.length < 3) return false;
  const best = Math.max(...e1rms.slice(0, -2));
  const [a, b] = e1rms.slice(-2);
  return a < best && b < best;
}

function weightTargetOf(cfg: WeightConfig, sets: SetTarget[]): WeightTarget {
  return cfg.progression === 'double'
    ? { type: 'double', sets }
    : { type: 'volume', volume: targetVolume(sets), sets };
}

function returnNote(gap: number): string {
  return `${gap}일 만의 복귀 — 지난번 그대로 반복해요`;
}

export function recommendWeight(cfg: WeightConfig, history: WeightHistoryItem[], today: string): Recommendation {
  const past = history.filter((h) => h.date < today && h.sets.length > 0);
  const last = past.at(-1);
  if (!last) return { status: 'first' };

  const gap = daysBetween(last.date, today);
  if (gap > RETURN_GAP_DAYS) {
    const sets = last.sets.map((set) => ({ weight: set[0].weight, reps: set[0].reps }));
    const target: WeightTarget =
      cfg.progression === 'double'
        ? { type: 'double', sets }
        : { type: 'volume', volume: totalVolume(last.sets), sets };
    return { status: 'ok', note: returnNote(gap), options: [{ id: 'repeat', label: '지난번 그대로', target }] };
  }

  const options: TargetOption[] = [];
  if (cfg.progression === 'double') {
    options.push({ id: 'main', label: '더블 프로그레션', target: { type: 'double', sets: doubleTarget(cfg, last.sets) } });
  } else {
    const plan = volumePlan(cfg, last.sets);
    options.push(
      { id: 'reps', label: '횟수로 달성', target: { type: 'volume', volume: plan.goal, sets: plan.byReps } },
      { id: 'weight', label: '무게로 달성', target: { type: 'volume', volume: plan.goal, sets: plan.byWeight } },
    );
  }

  if (isStalled(past.map((h) => sessionE1rm(h.sets)))) {
    const w = roundTo(workingWeight(last.sets) * DELOAD_RATIO, cfg.increment);
    const sets = Array.from({ length: cfg.targetSets }, () => ({ weight: w, reps: cfg.repMin }));
    options.push({ id: 'deload', label: '디로드 90%', target: weightTargetOf(cfg, sets) });
    return { status: 'ok', note: '최근 2회 연속 정체 — 디로드(90%)를 고려해 보세요', options };
  }
  return { status: 'ok', options };
}

export function recommendCardio(cfg: CardioConfig, history: CardioHistoryItem[], today: string): Recommendation {
  const last = history.filter((h) => h.date < today).at(-1);
  if (!last) return { status: 'first' };
  const gap = daysBetween(last.date, today);
  if (gap > RETURN_GAP_DAYS) {
    return {
      status: 'ok',
      note: returnNote(gap),
      options: [{ id: 'repeat', label: '지난번 그대로', target: { type: 'cardio', minutes: last.minutes, intensity: { ...last.intensity } } }],
    };
  }
  return { status: 'ok', options: [{ id: 'main', label: '시간→강도', target: cardioTarget(cfg, last) }] };
}

export function recommend(ex: Exercise, history: History, today: string): Recommendation {
  return ex.kind === 'weight'
    ? recommendWeight(ex.weight!, history as WeightHistoryItem[], today)
    : recommendCardio(ex.cardio!, history as CardioHistoryItem[], today);
}
