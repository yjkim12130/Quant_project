export type ExerciseKind = 'weight' | 'cardio';
export type Progression = 'double' | 'volume';

export interface WeightConfig {
  progression: Progression;
  repMin: number;
  repMax: number;
  targetSets: number;
  /** kg — 증량 단위이자 무게 반올림 단위 */
  increment: number;
  /** 볼륨 방식 증가율(%) 2~5 */
  volumeGrowthPct: number;
}

export interface CardioMetric {
  key: string;
  label: string;
  unit: string;
  step: number;
}

export interface CardioConfig {
  metrics: CardioMetric[];
  /** 올릴 강도 항목의 key */
  primaryMetric: string;
  minMinutes: number;
  maxMinutes: number;
  timeStep: number;
}

export interface Exercise {
  id: string;
  equipment: string;
  name: string;
  kind: ExerciseKind;
  archived: boolean;
  restSeconds: number;
  createdAt: number;
  weight?: WeightConfig;
  cardio?: CardioConfig;
}

export interface Segment {
  weight: number;
  reps: number;
}

/** 한 세트 = 구간 배열. 길이가 2 이상이면 세트 중간에 무게를 바꾼(드롭) 세트 */
export type SetSegments = Segment[];

export interface SetTarget {
  weight: number;
  reps: number;
  /** 지난번 이 세트에서 드롭했음 — "W에서 reps회 버틴 뒤 드롭" 안내 */
  dropHint?: boolean;
}

export type WeightTarget =
  | { type: 'double'; sets: SetTarget[] }
  | { type: 'volume'; volume: number; sets: SetTarget[] };

export interface CardioTarget {
  type: 'cardio';
  minutes: number;
  intensity: Record<string, number>;
}

export type Target = WeightTarget | CardioTarget;

export interface Session {
  id: string;
  exerciseId: string;
  date: string;
  memo?: string;
  /** 기록 시점의 목표 스냅샷 — 배지 판정용 */
  target?: Target;
}

export interface WeightSetRecord {
  id: string;
  sessionId: string;
  order: number;
  segments: SetSegments;
}

export interface CardioEntry {
  id: string;
  sessionId: string;
  minutes: number;
  intensity: Record<string, number>;
  distanceKm?: number;
  kcal?: number;
}

export interface WeightHistoryItem {
  date: string;
  sets: SetSegments[];
  target?: Target;
}

export interface CardioHistoryItem {
  date: string;
  minutes: number;
  intensity: Record<string, number>;
  distanceKm?: number;
  kcal?: number;
  target?: Target;
}

export type History = WeightHistoryItem[] | CardioHistoryItem[];
export type HistoryItem = WeightHistoryItem | CardioHistoryItem;

export type OptionId = 'main' | 'reps' | 'weight' | 'deload' | 'repeat';

export interface TargetOption {
  id: OptionId;
  label: string;
  target: Target;
}

export type Recommendation =
  | { status: 'first' }
  | { status: 'ok'; options: TargetOption[]; note?: string };

export type Badge = 'up' | 'same' | 'down';
