export type Op = 'add' | 'sub' | 'mul' | 'div';
export type QuestionKind = 'choice' | 'keypad' | 'blank' | 'picture';

export interface Operands {
  op: Op;
  a: number;
  b: number;
}

export interface Question extends Operands {
  id: string; // 레슨 내 고유값 `${index}-${key}`
  key: string; // 수식 식별자 `${op}:${a}:${b}`
  result: number; // a op b 의 값
  answer: number; // 아이가 입력해야 하는 값 (blank면 b, 그 외 result)
  kind: QuestionKind;
  choices?: number[]; // choice / picture 일 때만
}

export type OpStats = Record<Op, { correct: number; total: number }>;

export interface StreakState {
  count: number;
  lastPlayedDate: string | null; // YYYY-MM-DD (로컬)
  freezeUsedWeek: string | null; // YYYY-Www (ISO 주)
}

export interface StageProgress {
  crowns: number; // 0..3
  bestAccuracy: number; // 0..1
}

export interface Profile {
  id: string;
  name: string;
  avatar: string;
  xp: number;
  streak: StreakState;
  stages: Record<string, StageProgress>;
  stats: OpStats;
}

export interface Settings {
  soundOn: boolean;
  timerSec: number | null;
}

export interface AppData {
  schemaVersion: 1;
  profiles: Profile[];
  activeProfileId: string | null;
  settings: Settings;
}
