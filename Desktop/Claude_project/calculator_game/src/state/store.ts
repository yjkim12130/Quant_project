import { createStore, type StoreApi } from 'zustand/vanilla';
import { categoryOf, type CategoryId } from '../core/categories';
import { applyLesson, type LessonSummary } from '../core/progress';
import type { LessonOutcome } from '../core/scoring';
import { loadAppData, newProfile, saveAppData, type KV } from '../core/storage';
import { toLocalDateString } from '../core/streak';
import type { AppData, Profile } from '../core/types';

export type Screen =
  | { name: 'intro' }
  | { name: 'profiles' }
  | { name: 'home' }
  | { name: 'category'; categoryId: CategoryId }
  | { name: 'lesson'; stageId: string; categoryId: CategoryId }
  | { name: 'result'; stageId: string; categoryId: CategoryId; summary: LessonSummary }
  | { name: 'parent' };

export interface GameState {
  data: AppData;
  loadError: boolean;
  screen: Screen;
  nextSeed: () => number;
  today: () => string;
  goto: (screen: Screen) => void;
  /** 입장 화면에서 '시작!': 활성 프로필이 있으면 홈, 없으면 프로필 화면 */
  enter: () => void;
  addProfile: (name: string, avatar: string) => void;
  selectProfile: (id: string) => void;
  removeProfile: (id: string) => void;
  setSound: (on: boolean) => void;
  setTimer: (sec: number | null) => void;
  finishLesson: (stageId: string, outcome: LessonOutcome) => void;
}

export interface StoreOptions {
  kv: KV | null;
  nextSeed?: () => number;
  today?: () => string;
  makeId?: () => string;
}

export type GameStore = StoreApi<GameState>;

export function activeProfile(s: GameState): Profile | null {
  return s.data.profiles.find((p) => p.id === s.data.activeProfileId) ?? null;
}

export function createGameStore(opts: StoreOptions): GameStore {
  const { data, error } = loadAppData(opts.kv);
  const makeId = opts.makeId ?? (() => Math.random().toString(36).slice(2, 10));

  const store = createStore<GameState>()((set, get) => {
    const updateData = (fn: (d: AppData) => AppData) => set({ data: fn(get().data) });
    const updateProfile = (id: string, fn: (p: Profile) => Profile) =>
      updateData((d) => ({ ...d, profiles: d.profiles.map((p) => (p.id === id ? fn(p) : p)) }));

    return {
      data,
      loadError: error,
      screen: { name: 'intro' },
      nextSeed: opts.nextSeed ?? (() => Math.floor(Math.random() * 2 ** 31)),
      today: opts.today ?? (() => toLocalDateString(new Date())),

      goto: (screen) => set({ screen }),
      enter: () => set({ screen: activeProfile(get()) ? { name: 'home' } : { name: 'profiles' } }),

      addProfile: (name, avatar) => {
        const id = makeId();
        updateData((d) => ({
          ...d,
          profiles: [...d.profiles, newProfile(id, name.trim() || '친구', avatar)],
          activeProfileId: id,
        }));
        set({ screen: { name: 'home' } });
      },

      selectProfile: (id) => {
        updateData((d) => ({ ...d, activeProfileId: id }));
        set({ screen: { name: 'home' } });
      },

      removeProfile: (id) =>
        updateData((d) => ({
          ...d,
          profiles: d.profiles.filter((p) => p.id !== id),
          activeProfileId: d.activeProfileId === id ? null : d.activeProfileId,
        })),

      setSound: (on) => updateData((d) => ({ ...d, settings: { ...d.settings, soundOn: on } })),
      setTimer: (sec) => updateData((d) => ({ ...d, settings: { ...d.settings, timerSec: sec } })),

      finishLesson: (stageId, outcome) => {
        const p = activeProfile(get());
        if (!p) return;
        const { profile, summary } = applyLesson(p, stageId, outcome, get().today());
        const cur = get().screen;
        // 같은 단계가 두 카테고리에 있을 수 있어서, 들어온 카테고리로 돌아가게 기억한다
        const categoryId = cur.name === 'lesson' && cur.stageId === stageId ? cur.categoryId : categoryOf(stageId);
        updateProfile(p.id, () => profile);
        set({ screen: { name: 'result', stageId, categoryId, summary } });
      },
    };
  });

  store.subscribe((s, prev) => {
    if (s.data !== prev.data) saveAppData(opts.kv, s.data);
  });
  return store;
}
