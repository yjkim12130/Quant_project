# TrackingWorkout ("오늘도 +1") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 부부가 각자 폰(안드로이드·아이폰)에서 헬스장 세트 단위로 기록하고, 운동별 점진적 과부하 목표를 추천받고, 그래프로 실천 여부를 확인하는 오프라인 PWA.

**Architecture:** `src/core`(추천·지표·배지·그래프 데이터 — 순수 함수) ← `src/ui`(React 화면) → `src/db`(Dexie/IndexedDB 저장·백업). core는 db를 모르고 db는 추천을 모른다. 화면은 `dexie-react-hooks`의 `useLiveQuery`로 DB를 구독한다. 라우팅은 App의 상태 하나(`Route`)로 처리한다.

**Tech Stack:** React 19, TypeScript, Vite 8, vite-plugin-pwa, Dexie 4 + dexie-react-hooks, Recharts 3, Vitest 5 + Testing Library + fake-indexeddb, Cloudflare Pages(wrangler).

**Spec:** `docs/superpowers/specs/2026-10-17-tracking-workout-design.md`

## Global Constraints

- 작업 디렉터리: `Desktop/Claude_project/TrackingWorkout/` (저장소 루트는 `C:/Users/yjkim` 모노레포). 브랜치 `feature/tracking-workout-v1`. `git add`는 항상 이 폴더의 경로만 지정한다(`git add -A` 금지).
- 커밋 메시지 형식: `feat(tracking-workout): …` / `chore(tracking-workout): …`, 마지막 줄 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- 툴체인 버전은 `calculator_game/package.json`과 동일 계열(react ^19.3, vite ^8.3, vitest ^5.0, typescript ^7.0, vite-plugin-pwa ^2.0). 추가: dexie ^4.4.6, dexie-react-hooks ^4.4.0, recharts ^3.10.1, fake-indexeddb ^6.2.6(dev).
- 단위 kg 고정. 날짜는 로컬 기준 `YYYY-MM-DD` 문자열.
- 기본값: repMin 8, repMax 12, targetSets 3, increment 2.5, volumeGrowthPct 3(허용 2~5), restSeconds 90, 유산소 20~30분·timeStep 2분, 복귀 기준 14일 초과, 백업 경고 14일 초과, 디로드 90%.
- UI 문구는 한국어. 앱 이름 "오늘도 +1"(short_name "+1"). 검색엔진 비노출(noindex + robots.txt).
- 스펙에서 바꾼 두 가지(의도적): 오늘 목록 순서 변경은 "길게 누르기" 대신 **[순서 편집] → ↑↓ 버튼**, 세트 수정은 길게 누르기 대신 **세트 행 탭**. (jsdom 테스트 가능성과 한 손 조작 안정성 때문)

---

## File Structure

```
TrackingWorkout/
  package.json, tsconfig.json, vite.config.ts, index.html, .gitignore, README.md
  public/icon.svg, robots.txt (+ 생성 아이콘들)
  src/main.tsx                 DB 생성·persist 요청·렌더
  src/App.tsx                  Route 상태 + TabBar + 화면 분기
  src/core/types.ts            도메인 타입
  src/core/defaults.ts         기본 설정 상수
  src/core/date.ts             todayLocal, addDays, daysBetween, shortDate
  src/core/metrics.ts          roundTo, workingWeight, effectiveReps, hasDrop, totalVolume, firstSegmentVolume, e1rm, sessionE1rm, targetVolume
  src/core/progression/weightDouble.ts   doubleTarget
  src/core/progression/weightVolume.ts   volumePlan
  src/core/progression/cardio.ts         cardioTarget
  src/core/progression/rules.ts          isStalled, recommendWeight, recommendCardio, recommend
  src/core/badge.ts            weightBadge, cardioBadge, badgesFor, achievementRate
  src/core/series.ts           weightSeries, cardioSeries, filterByRange
  src/db/schema.ts             WorkoutDB (Dexie)
  src/db/repository.ts         운동·세션·세트·유산소·히스토리·메타 CRUD
  src/db/backup.ts             exportBackup, parseBackup, restoreBackup, markBackedUp, backupFileName
  src/ui/DbContext.tsx         DbProvider, useDb
  src/ui/routes.ts             Route, Navigate, Tab, tabOf
  src/ui/format.ts             표시 문자열 포맷터
  src/ui/theme.css
  src/ui/components/TabBar.tsx, ScreenHeader.tsx, Stepper.tsx, BadgeStrip.tsx, InstallBanner.tsx
  src/ui/timer/useRestTimer.ts, notify.ts, RestTimerBar.tsx
  src/ui/backupFile.ts         deliverBackup (공유 시트 / 다운로드)
  src/ui/today/loadToday.ts    오늘 화면 데이터 로더 + addToToday + moveItem
  src/ui/screens/TodayScreen.tsx, LogScreen.tsx, WeightLog.tsx, CardioLog.tsx,
                 HistoryScreen.tsx, DetailScreen.tsx, SettingsScreen.tsx, ExerciseFormScreen.tsx
  src/ui/settings/exerciseForm.ts   폼 값 변환·검증
  src/test/setup.ts, testDb.ts, fixtures.ts, renderApp.tsx
```

---

### Task 1: 프로젝트 골격

**Files:**
- Create: `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `.gitignore`, `src/main.tsx`, `src/App.tsx`, `src/test/setup.ts`, `src/App.test.tsx`

**Interfaces:**
- Produces: `npm test`/`npm run build` 동작, `src/test/setup.ts`(fake-indexeddb, jest-dom, ResizeObserver 스텁)

- [ ] **Step 1: package.json 작성**

```json
{
  "name": "tracking-workout",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host",
    "build": "tsc && vite build",
    "preview": "vite preview --host",
    "test": "vitest run",
    "test:watch": "vitest",
    "deploy": "npm test && npm run build && npx --yes wrangler@4 pages deploy dist --project-name tracking-workout --branch main"
  }
}
```

- [ ] **Step 2: 의존성 설치**

```bash
npm install react@^19.3.0 react-dom@^19.3.0 dexie@^4.4.6 dexie-react-hooks@^4.4.0 recharts@^3.10.1
npm install -D typescript@^7.0.2 vite@^8.3.4 @vitejs/plugin-react@^6.1.2 vitest@^5.0.3 jsdom@^30.1.2 @types/react@^19.3.0 @types/react-dom@^19.3.0 @testing-library/react@^16.3.3 @testing-library/dom@^10.4.2 @testing-library/jest-dom@^7.0.1 @testing-library/user-event@^14.6.7 fake-indexeddb@^6.2.6
```

- [ ] **Step 3: 설정 파일**

`tsconfig.json`
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "types": ["vite/client"]
  },
  "include": ["src", "vite.config.ts"]
}
```

`vite.config.ts` (PWA는 Task 16에서 추가)
```ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  base: './',
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
});
```

`index.html`
```html
<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
    <meta name="theme-color" content="#FF6B35" />
    <!-- 부부용 개인 앱: 검색엔진에 노출하지 않는다 -->
    <meta name="robots" content="noindex, nofollow" />
    <title>오늘도 +1</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

`.gitignore`
```
node_modules/
dist/
dev-dist/
*.local
coverage/
.wrangler/
```

`src/test/setup.ts`
```ts
import 'fake-indexeddb/auto';
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Recharts의 ResponsiveContainer가 요구하지만 jsdom에는 없다
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;

afterEach(() => {
  cleanup();
});
```

- [ ] **Step 4: 실패하는 스모크 테스트**

`src/App.test.tsx`
```tsx
import { render, screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { App } from './App';

it('앱 이름을 보여준다', () => {
  render(<App />);
  expect(screen.getByText('오늘도 +1')).toBeInTheDocument();
});
```

Run: `npm test` → FAIL (`./App` 없음)

- [ ] **Step 5: 최소 구현**

`src/App.tsx`
```tsx
export function App() {
  return <h1>오늘도 +1</h1>;
}
```

`src/main.tsx`
```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

- [ ] **Step 6: 확인** — `npm test` PASS, `npm run build` 성공
- [ ] **Step 7: 커밋** — `git add Desktop/Claude_project/TrackingWorkout/{package.json,package-lock.json,tsconfig.json,vite.config.ts,index.html,.gitignore,src}` → `chore(tracking-workout): Vite+React+TS 골격과 테스트 환경`

---

### Task 2: 도메인 타입·기본값·날짜·지표

**Files:**
- Create: `src/core/types.ts`, `src/core/defaults.ts`, `src/core/date.ts`, `src/core/metrics.ts`
- Test: `src/core/date.test.ts`, `src/core/metrics.test.ts`

**Interfaces:**
- Produces: 아래 타입 전부, `todayLocal(now?: Date): string`, `addDays(date: string, n: number): string`, `daysBetween(from: string, to: string): number`, `shortDate(date: string): string`, `roundTo(v, step)`, `workingWeight(sets: SetSegments[]): number`, `effectiveReps(set: SetSegments, w: number): number`, `hasDrop(set): boolean`, `totalVolume(sets): number`, `firstSegmentVolume(sets): number`, `e1rm(weight, reps): number`, `sessionE1rm(sets): number`, `targetVolume(sets: SetTarget[]): number`

- [ ] **Step 1: 타입과 기본값 작성**

`src/core/types.ts`
```ts
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
```

`src/core/defaults.ts`
```ts
import type { CardioConfig, WeightConfig } from './types';

export const DEFAULT_WEIGHT: WeightConfig = {
  progression: 'double',
  repMin: 8,
  repMax: 12,
  targetSets: 3,
  increment: 2.5,
  volumeGrowthPct: 3,
};

export const DEFAULT_CARDIO: CardioConfig = {
  metrics: [{ key: 'level', label: '레벨', unit: '', step: 1 }],
  primaryMetric: 'level',
  minMinutes: 20,
  maxMinutes: 30,
  timeStep: 2,
};

export const DEFAULT_REST_SECONDS = 90;
/** 마지막 기록이 이 일수보다 오래되면 "지난번 그대로" */
export const RETURN_GAP_DAYS = 14;
/** 마지막 백업이 이 일수보다 오래되면 경고 */
export const BACKUP_WARN_DAYS = 14;
export const DELOAD_RATIO = 0.9;
```

- [ ] **Step 2: 실패하는 테스트**

`src/core/date.test.ts`
```ts
import { describe, expect, it } from 'vitest';
import { addDays, daysBetween, shortDate, todayLocal } from './date';

describe('date', () => {
  it('todayLocal은 로컬 날짜를 YYYY-MM-DD로', () => {
    expect(todayLocal(new Date(2026, 9, 17, 23, 30))).toBe('2026-10-17');
    expect(todayLocal(new Date(2026, 0, 5, 0, 1))).toBe('2026-01-05');
  });
  it('addDays는 월말을 넘긴다', () => {
    expect(addDays('2026-10-31', 1)).toBe('2026-11-01');
    expect(addDays('2026-03-01', -1)).toBe('2026-02-28');
  });
  it('daysBetween', () => {
    expect(daysBetween('2026-10-01', '2026-10-17')).toBe(16);
    expect(daysBetween('2026-10-17', '2026-10-17')).toBe(0);
  });
  it('shortDate', () => {
    expect(shortDate('2026-10-04')).toBe('10/4');
  });
});
```

`src/core/metrics.test.ts`
```ts
import { describe, expect, it } from 'vitest';
import {
  e1rm, effectiveReps, firstSegmentVolume, hasDrop, roundTo, sessionE1rm, targetVolume, totalVolume, workingWeight,
} from './metrics';

const drop = [{ weight: 10, reps: 7 }, { weight: 8, reps: 5 }];

describe('roundTo', () => {
  it('step 배수로 반올림', () => {
    expect(roundTo(41.2, 2.5)).toBe(40);
    expect(roundTo(41.3, 2.5)).toBe(42.5);
    expect(roundTo(10.25, 0.5)).toBe(10.5);
    expect(roundTo(0.1 + 0.2, 0.1)).toBe(0.3);
  });
  it('step이 0 이하면 그대로', () => {
    expect(roundTo(3.3, 0)).toBe(3.3);
  });
});

describe('workingWeight', () => {
  it('첫 구간 무게의 최빈값', () => {
    expect(workingWeight([[{ weight: 10, reps: 12 }], [{ weight: 10, reps: 10 }], [{ weight: 12, reps: 8 }]])).toBe(10);
  });
  it('동률이면 큰 무게', () => {
    expect(workingWeight([[{ weight: 10, reps: 12 }], [{ weight: 12, reps: 8 }]])).toBe(12);
  });
  it('드롭 세트는 첫 구간만 본다', () => {
    expect(workingWeight([drop, drop, [{ weight: 8, reps: 12 }]])).toBe(10);
  });
  it('세트가 없으면 0', () => {
    expect(workingWeight([])).toBe(0);
  });
});

describe('세트 지표', () => {
  it('effectiveReps는 첫 구간이 W일 때만', () => {
    expect(effectiveReps(drop, 10)).toBe(7);
    expect(effectiveReps([{ weight: 8, reps: 10 }], 10)).toBe(0);
  });
  it('hasDrop', () => {
    expect(hasDrop(drop)).toBe(true);
    expect(hasDrop([{ weight: 10, reps: 12 }])).toBe(false);
  });
  it('볼륨은 드롭 포함, 첫 구간 볼륨은 제외', () => {
    const sets = [drop, [{ weight: 10, reps: 12 }]];
    expect(totalVolume(sets)).toBe(230);
    expect(firstSegmentVolume(sets)).toBe(190);
  });
  it('targetVolume', () => {
    expect(targetVolume([{ weight: 10, reps: 8 }, { weight: 12.5, reps: 4 }])).toBe(130);
  });
});

describe('e1rm', () => {
  it('Epley', () => {
    expect(e1rm(100, 10)).toBeCloseTo(133.333, 2);
    expect(e1rm(100, 1)).toBe(100);
    expect(e1rm(100, 0)).toBe(0);
  });
  it('세션 e1RM은 모든 구간 중 최대', () => {
    expect(sessionE1rm([drop, [{ weight: 10, reps: 12 }]])).toBeCloseTo(14, 5);
    expect(sessionE1rm([])).toBe(0);
  });
});
```

Run: `npm test` → FAIL (모듈 없음)

- [ ] **Step 3: 구현**

`src/core/date.ts`
```ts
const pad = (n: number) => String(n).padStart(2, '0');

export function todayLocal(now: Date = new Date()): string {
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

function toUtcMs(date: string): number {
  return Date.parse(`${date}T00:00:00Z`);
}

export function addDays(date: string, n: number): string {
  return new Date(toUtcMs(date) + n * 86_400_000).toISOString().slice(0, 10);
}

export function daysBetween(from: string, to: string): number {
  return Math.round((toUtcMs(to) - toUtcMs(from)) / 86_400_000);
}

export function shortDate(date: string): string {
  return `${Number(date.slice(5, 7))}/${Number(date.slice(8, 10))}`;
}
```

`src/core/metrics.ts`
```ts
import type { SetSegments, SetTarget } from './types';

export function roundTo(value: number, step: number): number {
  if (step <= 0) return value;
  return Number((Math.round(value / step) * step).toFixed(3));
}

/** 각 세트 첫 구간 무게의 최빈값(동률이면 큰 값) */
export function workingWeight(sets: SetSegments[]): number {
  const counts = new Map<number, number>();
  for (const set of sets) {
    if (set.length === 0) continue;
    counts.set(set[0].weight, (counts.get(set[0].weight) ?? 0) + 1);
  }
  let best = 0;
  let bestCount = 0;
  for (const [weight, count] of counts) {
    if (count > bestCount || (count === bestCount && weight > best)) {
      best = weight;
      bestCount = count;
    }
  }
  return best;
}

/** 작업 무게 W로 한 첫 구간의 횟수. 드롭 구간은 세지 않는다 */
export function effectiveReps(set: SetSegments, w: number): number {
  return set.length > 0 && set[0].weight === w ? set[0].reps : 0;
}

export function hasDrop(set: SetSegments): boolean {
  return set.length > 1;
}

export function totalVolume(sets: SetSegments[]): number {
  return sets.reduce((sum, set) => sum + set.reduce((a, s) => a + s.weight * s.reps, 0), 0);
}

export function firstSegmentVolume(sets: SetSegments[]): number {
  return sets.reduce((sum, set) => sum + (set.length ? set[0].weight * set[0].reps : 0), 0);
}

export function e1rm(weight: number, reps: number): number {
  if (reps <= 0) return 0;
  if (reps === 1) return weight;
  return weight * (1 + reps / 30);
}

export function sessionE1rm(sets: SetSegments[]): number {
  let best = 0;
  for (const set of sets) for (const s of set) best = Math.max(best, e1rm(s.weight, s.reps));
  return best;
}

export function targetVolume(sets: SetTarget[]): number {
  return sets.reduce((sum, s) => sum + s.weight * s.reps, 0);
}
```

- [ ] **Step 4: 확인** — `npm test` PASS
- [ ] **Step 5: 커밋** — `feat(tracking-workout): 도메인 타입·기본값·날짜·운동 지표`

---

### Task 3: 웨이트 더블 프로그레션

**Files:**
- Create: `src/core/progression/weightDouble.ts`
- Test: `src/core/progression/weightDouble.test.ts`

**Interfaces:**
- Consumes: `workingWeight`, `effectiveReps`, `hasDrop`, `roundTo`, `WeightConfig`, `SetSegments`, `SetTarget`
- Produces: `doubleTarget(cfg: WeightConfig, lastSets: SetSegments[]): SetTarget[]`

- [ ] **Step 1: 실패하는 테스트**

```ts
import { describe, expect, it } from 'vitest';
import { DEFAULT_WEIGHT } from '../defaults';
import { doubleTarget } from './weightDouble';

const cfg = { ...DEFAULT_WEIGHT }; // 8~12회, 3세트, 2.5kg
const s = (weight: number, reps: number) => [{ weight, reps }];

describe('doubleTarget', () => {
  it('모든 세트 repMax 달성 → 증량, repMin', () => {
    expect(doubleTarget(cfg, [s(40, 12), s(40, 12), s(40, 13)])).toEqual([
      { weight: 42.5, reps: 8 }, { weight: 42.5, reps: 8 }, { weight: 42.5, reps: 8 },
    ]);
  });
  it('증량 무게는 증량 단위로 반올림', () => {
    expect(doubleTarget(cfg, [s(41, 12), s(41, 12), s(41, 12)])[0].weight).toBe(42.5);
  });
  it('스펙 예시: 드롭 세트는 유효 횟수+1과 dropHint', () => {
    const last = [[{ weight: 10, reps: 7 }, { weight: 8, reps: 5 }], s(10, 12), s(10, 9)];
    expect(doubleTarget(cfg, last)).toEqual([
      { weight: 10, reps: 8, dropHint: true }, { weight: 10, reps: 12 }, { weight: 10, reps: 10 },
    ]);
  });
  it('세트가 모자라면 repMin 세트를 추가', () => {
    expect(doubleTarget(cfg, [s(40, 10), s(40, 9)])).toEqual([
      { weight: 40, reps: 11 }, { weight: 40, reps: 10 }, { weight: 40, reps: 8 },
    ]);
  });
  it('repMax를 채웠어도 드롭이 있으면 증량하지 않는다', () => {
    const last = [[{ weight: 40, reps: 12 }, { weight: 30, reps: 4 }], s(40, 12), s(40, 12)];
    expect(doubleTarget(cfg, last)).toEqual([
      { weight: 40, reps: 12, dropHint: true }, { weight: 40, reps: 12 }, { weight: 40, reps: 12 },
    ]);
  });
  it('W가 아닌 무게로 한 세트는 repMin부터', () => {
    expect(doubleTarget(cfg, [s(40, 10), s(40, 10), s(35, 12)])[2]).toEqual({ weight: 40, reps: 8 });
  });
  it('세트 수가 모자라면 repMax를 채웠어도 증량하지 않는다', () => {
    expect(doubleTarget(cfg, [s(40, 12), s(40, 12)])).toEqual([
      { weight: 40, reps: 12 }, { weight: 40, reps: 12 }, { weight: 40, reps: 8 },
    ]);
  });
});
```

Run: `npx vitest run src/core/progression/weightDouble.test.ts` → FAIL

- [ ] **Step 2: 구현**

```ts
import { effectiveReps, hasDrop, roundTo, workingWeight } from '../metrics';
import type { SetSegments, SetTarget, WeightConfig } from '../types';

export function doubleTarget(cfg: WeightConfig, lastSets: SetSegments[]): SetTarget[] {
  const w = workingWeight(lastSets);
  const head = lastSets.slice(0, cfg.targetSets);
  const maxed =
    head.length >= cfg.targetSets &&
    head.every((set) => !hasDrop(set) && effectiveReps(set, w) >= cfg.repMax);

  if (maxed) {
    const next = roundTo(w + cfg.increment, cfg.increment);
    return Array.from({ length: cfg.targetSets }, () => ({ weight: next, reps: cfg.repMin }));
  }

  return Array.from({ length: cfg.targetSets }, (_, i) => {
    const set = lastSets[i];
    const eff = set ? effectiveReps(set, w) : 0;
    if (eff === 0) return { weight: w, reps: cfg.repMin };
    const target: SetTarget = { weight: w, reps: Math.min(eff + 1, cfg.repMax) };
    if (hasDrop(set)) target.dropHint = true;
    return target;
  });
}
```

- [ ] **Step 3: 확인** — PASS
- [ ] **Step 4: 커밋** — `feat(tracking-workout): 웨이트 더블 프로그레션 목표 계산`

---

### Task 4: 웨이트 볼륨 증가

**Files:**
- Create: `src/core/progression/weightVolume.ts`
- Test: `src/core/progression/weightVolume.test.ts`

**Interfaces:**
- Produces: `interface VolumePlan { goal: number; byReps: SetTarget[]; byWeight: SetTarget[] }`, `volumePlan(cfg: WeightConfig, lastSets: SetSegments[]): VolumePlan`

- [ ] **Step 1: 실패하는 테스트**

```ts
import { describe, expect, it } from 'vitest';
import { DEFAULT_WEIGHT } from '../defaults';
import { volumePlan } from './weightVolume';

const cfg = { ...DEFAULT_WEIGHT, progression: 'volume' as const }; // 3%
const s = (weight: number, reps: number) => [{ weight, reps }];

describe('volumePlan', () => {
  it('스펙 예시: 드롭 포함 볼륨의 +3%, 마지막 세트부터 +1씩', () => {
    const last = [[{ weight: 10, reps: 7 }, { weight: 8, reps: 5 }], s(10, 12), s(10, 9)];
    const plan = volumePlan(cfg, last); // 320 → 330
    expect(plan.goal).toBe(330);
    expect(plan.byReps).toEqual([{ weight: 10, reps: 8 }, { weight: 10, reps: 14 }, { weight: 10, reps: 11 }]);
    expect(plan.byWeight).toEqual([{ weight: 12.5, reps: 9 }, { weight: 12.5, reps: 9 }, { weight: 12.5, reps: 9 }]);
  });
  it('부동소수 오차로 목표가 1 커지지 않는다', () => {
    const plan = volumePlan(cfg, [s(50, 10), s(50, 10), s(50, 10)]); // 1500 → 1545
    expect(plan.goal).toBe(1545);
    expect(plan.byReps.map((t) => t.reps)).toEqual([10, 10, 11]);
    expect(plan.byWeight[0]).toEqual({ weight: 52.5, reps: 10 });
  });
  it('맨몸(0kg)이면 마지막 세트 +1회', () => {
    expect(volumePlan(cfg, [s(0, 10), s(0, 10), s(0, 10)]).byReps.map((t) => t.reps)).toEqual([10, 10, 11]);
  });
});
```

- [ ] **Step 2: 구현**

```ts
import { effectiveReps, roundTo, totalVolume, workingWeight } from '../metrics';
import type { SetSegments, SetTarget, WeightConfig } from '../types';

export interface VolumePlan {
  goal: number;
  byReps: SetTarget[];
  byWeight: SetTarget[];
}

export function volumePlan(cfg: WeightConfig, lastSets: SetSegments[]): VolumePlan {
  const w = workingWeight(lastSets);
  // 1e-9: 1500 × 1.03 같은 부동소수 오차로 1kg 더 요구하지 않도록
  const goal = Math.ceil((totalVolume(lastSets) * (100 + cfg.volumeGrowthPct)) / 100 - 1e-9);

  const reps = Array.from({ length: cfg.targetSets }, (_, i) => {
    const set = lastSets[i];
    const eff = set ? effectiveReps(set, w) : 0;
    return eff > 0 ? eff : cfg.repMin;
  });
  if (w > 0) {
    let i = reps.length - 1;
    while (reps.reduce((a, r) => a + r * w, 0) < goal) {
      reps[i] += 1;
      i = i === 0 ? reps.length - 1 : i - 1;
    }
  } else {
    reps[reps.length - 1] += 1;
  }

  const next = roundTo(w + cfg.increment, cfg.increment);
  const r = Math.max(1, Math.ceil(goal / (next * cfg.targetSets)));
  return {
    goal,
    byReps: reps.map((n) => ({ weight: w, reps: n })),
    byWeight: Array.from({ length: cfg.targetSets }, () => ({ weight: next, reps: r })),
  };
}
```

- [ ] **Step 3: 확인** — PASS
- [ ] **Step 4: 커밋** — `feat(tracking-workout): 웨이트 볼륨 증가 목표(횟수안·무게안)`

---

### Task 5: 유산소 시간 → 강도

**Files:**
- Create: `src/core/progression/cardio.ts`
- Test: `src/core/progression/cardio.test.ts`

**Interfaces:**
- Produces: `cardioTarget(cfg: CardioConfig, last: { minutes: number; intensity: Record<string, number> }): CardioTarget`

- [ ] **Step 1: 실패하는 테스트**

```ts
import { describe, expect, it } from 'vitest';
import type { CardioConfig } from '../types';
import { cardioTarget } from './cardio';

const cfg: CardioConfig = {
  metrics: [
    { key: 'speed', label: '속도', unit: 'km/h', step: 0.5 },
    { key: 'incline', label: '경사', unit: '%', step: 1 },
  ],
  primaryMetric: 'speed',
  minMinutes: 20,
  maxMinutes: 30,
  timeStep: 2,
};

describe('cardioTarget', () => {
  it('최대 시간 달성 → 주 강도 +1단계, 시간은 최소부터, 다른 강도 유지', () => {
    expect(cardioTarget(cfg, { minutes: 30, intensity: { speed: 10, incline: 3 } })).toEqual({
      type: 'cardio', minutes: 20, intensity: { speed: 10.5, incline: 3 },
    });
  });
  it('미달 → 같은 강도로 시간 +timeStep', () => {
    expect(cardioTarget(cfg, { minutes: 24, intensity: { speed: 10, incline: 3 } })).toEqual({
      type: 'cardio', minutes: 26, intensity: { speed: 10, incline: 3 },
    });
  });
  it('시간은 최대를 넘지 않는다', () => {
    expect(cardioTarget(cfg, { minutes: 29, intensity: { speed: 10 } }).minutes).toBe(30);
  });
  it('주 강도 값이 없으면 0에서 올린다', () => {
    expect(cardioTarget(cfg, { minutes: 30, intensity: {} }).intensity.speed).toBe(0.5);
  });
});
```

- [ ] **Step 2: 구현**

```ts
import { roundTo } from '../metrics';
import type { CardioConfig, CardioTarget } from '../types';

export function cardioTarget(
  cfg: CardioConfig,
  last: { minutes: number; intensity: Record<string, number> },
): CardioTarget {
  const key = cfg.primaryMetric;
  const step = cfg.metrics.find((m) => m.key === key)?.step ?? 1;
  if (last.minutes >= cfg.maxMinutes) {
    const current = last.intensity[key] ?? 0;
    return {
      type: 'cardio',
      minutes: cfg.minMinutes,
      intensity: { ...last.intensity, [key]: roundTo(current + step, step) },
    };
  }
  return {
    type: 'cardio',
    minutes: Math.min(last.minutes + cfg.timeStep, cfg.maxMinutes),
    intensity: { ...last.intensity },
  };
}
```

- [ ] **Step 3: 확인** — PASS
- [ ] **Step 4: 커밋** — `feat(tracking-workout): 유산소 시간→강도 목표 계산`

---

### Task 6: 추천 진입점과 예외 규칙

**Files:**
- Create: `src/core/progression/rules.ts`
- Test: `src/core/progression/rules.test.ts`

**Interfaces:**
- Consumes: `doubleTarget`, `volumePlan`, `cardioTarget`, `daysBetween`, `sessionE1rm`, `workingWeight`, `totalVolume`, `targetVolume`, `roundTo`, 기본값 상수
- Produces: `isStalled(e1rms: number[]): boolean`, `recommendWeight(cfg, history: WeightHistoryItem[], today): Recommendation`, `recommendCardio(cfg, history: CardioHistoryItem[], today): Recommendation`, `recommend(ex: Exercise, history: History, today: string): Recommendation`. 히스토리는 날짜 오름차순이며 함수 안에서 `date < today`만 사용한다.

- [ ] **Step 1: 실패하는 테스트**

```ts
import { describe, expect, it } from 'vitest';
import { DEFAULT_CARDIO, DEFAULT_WEIGHT } from '../defaults';
import type { CardioHistoryItem, Exercise, WeightHistoryItem } from '../types';
import { isStalled, recommend, recommendCardio, recommendWeight } from './rules';

const today = '2026-10-17';
const cfg = { ...DEFAULT_WEIGHT };
const s = (weight: number, reps: number) => [{ weight, reps }];
const day = (date: string, sets: WeightHistoryItem['sets']): WeightHistoryItem => ({ date, sets });

describe('isStalled', () => {
  it('최근 2회가 모두 그 이전 최고보다 낮으면 정체', () => {
    expect(isStalled([133, 126, 130])).toBe(true);
    expect(isStalled([126, 130, 133])).toBe(false);
    expect(isStalled([133, 140, 130])).toBe(false);
  });
  it('기록이 3개 미만이면 정체 아님', () => {
    expect(isStalled([133, 120])).toBe(false);
  });
});

describe('recommendWeight', () => {
  it('기록이 없으면 first', () => {
    expect(recommendWeight(cfg, [], today)).toEqual({ status: 'first' });
  });
  it('오늘 기록은 기준에서 제외한다', () => {
    expect(recommendWeight(cfg, [day(today, [s(40, 12)])], today)).toEqual({ status: 'first' });
  });
  it('더블 → main 옵션', () => {
    const rec = recommendWeight(cfg, [day('2026-10-14', [s(40, 12), s(40, 10), s(40, 9)])], today);
    expect(rec).toEqual({
      status: 'ok',
      options: [{
        id: 'main', label: '더블 프로그레션',
        target: { type: 'double', sets: [{ weight: 40, reps: 12 }, { weight: 40, reps: 11 }, { weight: 40, reps: 10 }] },
      }],
    });
  });
  it('볼륨 → 횟수안·무게안', () => {
    const rec = recommendWeight({ ...cfg, progression: 'volume' }, [day('2026-10-14', [s(50, 10), s(50, 10), s(50, 10)])], today);
    if (rec.status !== 'ok') throw new Error('ok 기대');
    expect(rec.options.map((o) => o.id)).toEqual(['reps', 'weight']);
    expect(rec.options[0].target).toMatchObject({ type: 'volume', volume: 1545 });
  });
  it('14일 초과 공백 → 지난번 그대로', () => {
    const rec = recommendWeight(cfg, [day('2026-10-02', [[{ weight: 40, reps: 10 }, { weight: 30, reps: 4 }], s(40, 9)])], today);
    expect(rec).toEqual({
      status: 'ok',
      note: '15일 만의 복귀 — 지난번 그대로 반복해요',
      options: [{
        id: 'repeat', label: '지난번 그대로',
        target: { type: 'double', sets: [{ weight: 40, reps: 10 }, { weight: 40, reps: 9 }] },
      }],
    });
  });
  it('정확히 14일이면 정상 추천', () => {
    const rec = recommendWeight(cfg, [day('2026-10-03', [s(40, 10)])], today);
    if (rec.status !== 'ok') throw new Error('ok 기대');
    expect(rec.options[0].id).toBe('main');
  });
  it('정체면 디로드 옵션과 안내 문구 추가', () => {
    const history = [day('2026-10-10', [s(100, 10)]), day('2026-10-12', [s(100, 8)]), day('2026-10-14', [s(100, 9)])];
    const rec = recommendWeight(cfg, history, today);
    if (rec.status !== 'ok') throw new Error('ok 기대');
    expect(rec.note).toBe('최근 2회 연속 정체 — 디로드(90%)를 고려해 보세요');
    expect(rec.options.at(-1)).toEqual({
      id: 'deload', label: '디로드 90%',
      target: { type: 'double', sets: [{ weight: 90, reps: 8 }, { weight: 90, reps: 8 }, { weight: 90, reps: 8 }] },
    });
  });
});

describe('recommendCardio', () => {
  const ccfg = { ...DEFAULT_CARDIO };
  const item = (date: string, minutes: number, level: number): CardioHistoryItem => ({ date, minutes, intensity: { level } });
  it('first / main / repeat', () => {
    expect(recommendCardio(ccfg, [], today)).toEqual({ status: 'first' });
    expect(recommendCardio(ccfg, [item('2026-10-16', 30, 8)], today)).toEqual({
      status: 'ok',
      options: [{ id: 'main', label: '시간→강도', target: { type: 'cardio', minutes: 20, intensity: { level: 9 } } }],
    });
    const back = recommendCardio(ccfg, [item('2026-09-01', 25, 8)], today);
    expect(back).toMatchObject({ status: 'ok', options: [{ id: 'repeat', target: { type: 'cardio', minutes: 25, intensity: { level: 8 } } }] });
  });
});

describe('recommend', () => {
  it('운동 종류에 따라 분기', () => {
    const ex: Exercise = {
      id: 'c', equipment: '사이클', name: '인터벌', kind: 'cardio', archived: false,
      restSeconds: 90, createdAt: 1, cardio: { ...DEFAULT_CARDIO },
    };
    expect(recommend(ex, [], today)).toEqual({ status: 'first' });
  });
});
```

- [ ] **Step 2: 구현**

```ts
import { daysBetween } from '../date';
import { DELOAD_RATIO, RETURN_GAP_DAYS } from '../defaults';
import { roundTo, sessionE1rm, targetVolume, totalVolume, workingWeight } from '../metrics';
import type {
  CardioConfig, CardioHistoryItem, Exercise, History, Recommendation, SetSegments, SetTarget,
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
    const sets = last.sets.map((set: SetSegments) => ({ weight: set[0].weight, reps: set[0].reps }));
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
```

- [ ] **Step 3: 확인** — PASS
- [ ] **Step 4: 커밋** — `feat(tracking-workout): 추천 진입점(첫 기록·복귀·디로드)`

---

### Task 7: 배지·달성률·그래프 데이터

**Files:**
- Create: `src/core/badge.ts`, `src/core/series.ts`
- Test: `src/core/badge.test.ts`, `src/core/series.test.ts`

**Interfaces:**
- Produces: `weightBadge(item, prev?): Badge | null`, `cardioBadge(item, prev, primary): Badge | null`, `badgesFor(ex: Exercise, history: History): (Badge | null)[]`, `achievementRate(badges: (Badge | null)[]): number | null`; `interface WeightPoint { date; label; e1rm; mainVolume; dropVolume; achievementPct: number | null; isPR: boolean }`, `weightSeries(history: WeightHistoryItem[]): WeightPoint[]`, `interface CardioPoint { date; label; minutes; primary: number; distanceKm: number | null; kcal: number | null; kcalPerMin: number | null; speedKmh: number | null }`, `cardioSeries(history, primary): CardioPoint[]`, `type Range = '4w' | '3m' | 'all'`, `filterByRange<T extends { date: string }>(points: T[], range: Range, today: string): T[]`

- [ ] **Step 1: 실패하는 테스트**

`src/core/badge.test.ts`
```ts
import { describe, expect, it } from 'vitest';
import { DEFAULT_CARDIO, DEFAULT_WEIGHT } from './defaults';
import { achievementRate, badgesFor, cardioBadge, weightBadge } from './badge';
import type { CardioHistoryItem, Exercise, WeightHistoryItem } from './types';

const s = (weight: number, reps: number) => [{ weight, reps }];
const doubleTarget = { type: 'double' as const, sets: [{ weight: 40, reps: 12 }, { weight: 40, reps: 11 }] };

describe('weightBadge', () => {
  const prev: WeightHistoryItem = { date: '2026-10-14', sets: [s(40, 12), s(40, 10)] };
  it('목표 충족 → up', () => {
    expect(weightBadge({ date: '2026-10-17', sets: [s(40, 12), s(40, 11)], target: doubleTarget }, prev)).toBe('up');
  });
  it('무게를 더 들었으면 충족', () => {
    expect(weightBadge({ date: '2026-10-17', sets: [s(42.5, 12), s(40, 11)], target: doubleTarget }, prev)).toBe('up');
  });
  it('미달이지만 하락 아님 → same', () => {
    expect(weightBadge({ date: '2026-10-17', sets: [s(40, 12), s(40, 10)], target: doubleTarget }, prev)).toBe('same');
  });
  it('e1RM과 볼륨이 모두 낮음 → down', () => {
    expect(weightBadge({ date: '2026-10-17', sets: [s(40, 10), s(40, 9)], target: doubleTarget }, prev)).toBe('down');
  });
  it('볼륨 목표', () => {
    const target = { type: 'volume' as const, volume: 900, sets: [] };
    expect(weightBadge({ date: '2026-10-17', sets: [s(40, 12), s(40, 11)], target }, prev)).toBe('up');
  });
  it('목표가 없으면 null', () => {
    expect(weightBadge({ date: '2026-10-17', sets: [s(40, 12)] }, prev)).toBeNull();
  });
});

describe('cardioBadge', () => {
  const target = { type: 'cardio' as const, minutes: 26, intensity: { level: 8 } };
  const prev: CardioHistoryItem = { date: '2026-10-14', minutes: 24, intensity: { level: 8 } };
  it('up / same / down', () => {
    expect(cardioBadge({ date: 'd', minutes: 26, intensity: { level: 8 }, target }, prev, 'level')).toBe('up');
    expect(cardioBadge({ date: 'd', minutes: 25, intensity: { level: 8 }, target }, prev, 'level')).toBe('same');
    expect(cardioBadge({ date: 'd', minutes: 20, intensity: { level: 8 }, target }, prev, 'level')).toBe('down');
    expect(cardioBadge({ date: 'd', minutes: 20, intensity: { level: 9 }, target }, prev, 'level')).toBe('same');
  });
});

describe('badgesFor / achievementRate', () => {
  it('히스토리와 같은 길이로 정렬된 배지', () => {
    const ex: Exercise = {
      id: 'w', equipment: '바벨', name: '스쿼트', kind: 'weight', archived: false,
      restSeconds: 90, createdAt: 1, weight: { ...DEFAULT_WEIGHT },
    };
    const history: WeightHistoryItem[] = [
      { date: '2026-10-10', sets: [s(40, 12)] },
      { date: '2026-10-14', sets: [s(40, 12), s(40, 11)], target: doubleTarget },
    ];
    expect(badgesFor(ex, history)).toEqual([null, 'up']);
    const cex: Exercise = { ...ex, kind: 'cardio', weight: undefined, cardio: { ...DEFAULT_CARDIO } };
    expect(badgesFor(cex, [])).toEqual([]);
  });
  it('달성률은 배지가 있는 세션 중 up 비율', () => {
    expect(achievementRate(['up', 'same', null, 'up'])).toBeCloseTo(2 / 3);
    expect(achievementRate([null])).toBeNull();
  });
});
```

`src/core/series.test.ts`
```ts
import { describe, expect, it } from 'vitest';
import { cardioSeries, filterByRange, weightSeries } from './series';

describe('weightSeries', () => {
  it('e1RM·볼륨 분해·달성률·PR', () => {
    const points = weightSeries([
      { date: '2026-10-10', sets: [[{ weight: 10, reps: 12 }]] },
      {
        date: '2026-10-14',
        sets: [[{ weight: 10, reps: 8 }, { weight: 8, reps: 4 }], [{ weight: 10, reps: 12 }], [{ weight: 10, reps: 9 }]],
        target: { type: 'double', sets: [{ weight: 10, reps: 8, dropHint: true }, { weight: 10, reps: 12 }, { weight: 10, reps: 10 }] },
      },
      { date: '2026-10-16', sets: [[{ weight: 10, reps: 10 }]] },
    ]);
    expect(points[0]).toEqual({
      date: '2026-10-10', label: '10/10', e1rm: 14, mainVolume: 120, dropVolume: 0, achievementPct: null, isPR: false,
    });
    expect(points[1]).toMatchObject({ mainVolume: 290, dropVolume: 32, achievementPct: 97, isPR: false });
    expect(points[2].isPR).toBe(false);
  });
  it('이전 최고를 넘으면 PR', () => {
    const points = weightSeries([
      { date: '2026-10-10', sets: [[{ weight: 10, reps: 12 }]] },
      { date: '2026-10-14', sets: [[{ weight: 12.5, reps: 10 }]] },
    ]);
    expect(points.map((p) => p.isPR)).toEqual([false, true]);
  });
});

describe('cardioSeries', () => {
  it('평균 속도와 분당 칼로리', () => {
    expect(cardioSeries([{ date: '2026-10-14', minutes: 30, intensity: { speed: 10 }, distanceKm: 5, kcal: 300 }], 'speed')).toEqual([
      { date: '2026-10-14', label: '10/14', minutes: 30, primary: 10, distanceKm: 5, kcal: 300, kcalPerMin: 10, speedKmh: 10 },
    ]);
    expect(cardioSeries([{ date: '2026-10-14', minutes: 30, intensity: {} }], 'speed')[0]).toMatchObject({
      primary: 0, distanceKm: null, kcal: null, kcalPerMin: null, speedKmh: null,
    });
  });
});

describe('filterByRange', () => {
  const pts = [{ date: '2026-07-01' }, { date: '2026-09-20' }, { date: '2026-10-10' }];
  it('4주 / 3개월 / 전체', () => {
    expect(filterByRange(pts, '4w', '2026-10-17')).toEqual([{ date: '2026-09-20' }, { date: '2026-10-10' }]);
    expect(filterByRange(pts, '3m', '2026-10-17')).toEqual([{ date: '2026-09-20' }, { date: '2026-10-10' }]);
    expect(filterByRange(pts, 'all', '2026-10-17')).toHaveLength(3);
  });
});
```

(4주 = 2026-09-19 이후, 3개월 = 2026-07-18 이후)

- [ ] **Step 2: 구현**

`src/core/badge.ts`
```ts
import { sessionE1rm, totalVolume } from './metrics';
import type { Badge, CardioHistoryItem, Exercise, History, WeightHistoryItem } from './types';

export function weightBadge(item: WeightHistoryItem, prev?: WeightHistoryItem): Badge | null {
  const t = item.target;
  if (!t || t.type === 'cardio' || item.sets.length === 0) return null;
  const achieved =
    t.type === 'double'
      ? t.sets.every((st, i) => {
          const set = item.sets[i];
          return !!set && set[0].weight >= st.weight && set[0].reps >= st.reps;
        })
      : totalVolume(item.sets) >= t.volume;
  if (achieved) return 'up';
  if (
    prev && prev.sets.length > 0 &&
    sessionE1rm(item.sets) < sessionE1rm(prev.sets) &&
    totalVolume(item.sets) < totalVolume(prev.sets)
  ) {
    return 'down';
  }
  return 'same';
}

export function cardioBadge(item: CardioHistoryItem, prev: CardioHistoryItem | undefined, primary: string): Badge | null {
  const t = item.target;
  if (!t || t.type !== 'cardio') return null;
  const current = item.intensity[primary] ?? 0;
  if (current >= (t.intensity[primary] ?? 0) && item.minutes >= t.minutes) return 'up';
  if (prev && current <= (prev.intensity[primary] ?? 0) && item.minutes < prev.minutes) return 'down';
  return 'same';
}

export function badgesFor(ex: Exercise, history: History): (Badge | null)[] {
  if (ex.kind === 'weight') {
    const h = history as WeightHistoryItem[];
    return h.map((item, i) => weightBadge(item, h[i - 1]));
  }
  const h = history as CardioHistoryItem[];
  return h.map((item, i) => cardioBadge(item, h[i - 1], ex.cardio!.primaryMetric));
}

export function achievementRate(badges: (Badge | null)[]): number | null {
  const judged = badges.filter((b): b is Badge => b !== null);
  if (judged.length === 0) return null;
  return judged.filter((b) => b === 'up').length / judged.length;
}
```

`src/core/series.ts`
```ts
import { addDays, shortDate } from './date';
import { firstSegmentVolume, sessionE1rm, totalVolume } from './metrics';
import type { CardioHistoryItem, WeightHistoryItem } from './types';

export interface WeightPoint {
  date: string;
  label: string;
  e1rm: number;
  mainVolume: number;
  dropVolume: number;
  achievementPct: number | null;
  isPR: boolean;
}

export interface CardioPoint {
  date: string;
  label: string;
  minutes: number;
  primary: number;
  distanceKm: number | null;
  kcal: number | null;
  kcalPerMin: number | null;
  speedKmh: number | null;
}

export type Range = '4w' | '3m' | 'all';

const round1 = (n: number) => Number(n.toFixed(1));

function achievementPct(h: WeightHistoryItem): number | null {
  const t = h.target;
  if (!t || t.type === 'cardio') return null;
  const goal = t.sets.reduce((a, s) => a + s.reps, 0);
  if (goal === 0) return null;
  const done = t.sets.reduce((a, s, i) => {
    const set = h.sets[i];
    return a + (set && set[0].weight >= s.weight ? Math.min(set[0].reps, s.reps) : 0);
  }, 0);
  return Math.round((done / goal) * 100);
}

export function weightSeries(history: WeightHistoryItem[]): WeightPoint[] {
  let best = 0;
  return history.map((h, i) => {
    const e = round1(sessionE1rm(h.sets));
    const isPR = i > 0 && e > best;
    best = Math.max(best, e);
    const main = firstSegmentVolume(h.sets);
    return {
      date: h.date,
      label: shortDate(h.date),
      e1rm: e,
      mainVolume: main,
      dropVolume: totalVolume(h.sets) - main,
      achievementPct: achievementPct(h),
      isPR,
    };
  });
}

export function cardioSeries(history: CardioHistoryItem[], primary: string): CardioPoint[] {
  return history.map((h) => ({
    date: h.date,
    label: shortDate(h.date),
    minutes: h.minutes,
    primary: h.intensity[primary] ?? 0,
    distanceKm: h.distanceKm ?? null,
    kcal: h.kcal ?? null,
    kcalPerMin: h.kcal != null && h.minutes > 0 ? round1(h.kcal / h.minutes) : null,
    speedKmh: h.distanceKm != null && h.minutes > 0 ? round1(h.distanceKm / (h.minutes / 60)) : null,
  }));
}

export function filterByRange<T extends { date: string }>(points: T[], range: Range, today: string): T[] {
  if (range === 'all') return points;
  const from = addDays(today, range === '4w' ? -28 : -91);
  return points.filter((p) => p.date >= from);
}
```

- [ ] **Step 3: 확인** — PASS
- [ ] **Step 4: 커밋** — `feat(tracking-workout): 과부하 배지·달성률·그래프 데이터`

---

### Task 8: Dexie 스키마와 저장소

**Files:**
- Create: `src/db/schema.ts`, `src/db/repository.ts`, `src/test/testDb.ts`, `src/test/fixtures.ts`
- Test: `src/db/repository.test.ts`

**Interfaces:**
- Produces: `class WorkoutDB(name?)` with tables `exercises, sessions, weightSets, cardioEntries, meta`; `interface MetaRow { key: string; value: unknown }`; repository: `newId()`, `DuplicateExerciseError`, `type NewExercise`, `addExercise`, `updateExercise`, `listExercises(db, includeArchived?)`, `findSession(db, exerciseId, date)`, `getOrCreateSession(db, exerciseId, date, target?)`, `setSessionTarget(db, sessionId, target)`, `validateSegments`, `listWeightSets`, `addWeightSet`, `updateWeightSet`, `deleteWeightSet`, `type CardioInput`, `validateCardio`, `getCardioEntry`, `saveCardioEntry`, `weightHistory`, `cardioHistory`, `exerciseHistory(db, ex)`, `recentExerciseIds(db, today, days?)`, `getMeta<T>`, `setMeta`; test helpers `makeTestDb()`, `weightExercise(overrides?)`, `cardioExercise(overrides?)`, `seedWeightSession(db, exerciseId, date, sets, target?)`, `seedCardioSession(db, exerciseId, date, input, target?)`

- [ ] **Step 1: 스키마와 테스트 헬퍼**

`src/db/schema.ts`
```ts
import Dexie, { type Table } from 'dexie';
import type { CardioEntry, Exercise, Session, WeightSetRecord } from '../core/types';

export interface MetaRow {
  key: string;
  value: unknown;
}

export class WorkoutDB extends Dexie {
  exercises!: Table<Exercise, string>;
  sessions!: Table<Session, string>;
  weightSets!: Table<WeightSetRecord, string>;
  cardioEntries!: Table<CardioEntry, string>;
  meta!: Table<MetaRow, string>;

  constructor(name = 'tracking-workout') {
    super(name);
    this.version(1).stores({
      exercises: 'id, &[equipment+name]',
      sessions: 'id, exerciseId, date, &[exerciseId+date]',
      weightSets: 'id, sessionId',
      cardioEntries: 'id, sessionId',
      meta: 'key',
    });
  }
}
```

`src/test/testDb.ts`
```ts
import { WorkoutDB } from '../db/schema';

let seq = 0;
/** 테스트마다 이름이 다른 DB — 서로 간섭하지 않는다 */
export function makeTestDb(): WorkoutDB {
  seq += 1;
  return new WorkoutDB(`test-${Date.now()}-${seq}`);
}
```

`src/test/fixtures.ts`
```ts
import { DEFAULT_CARDIO, DEFAULT_REST_SECONDS, DEFAULT_WEIGHT } from '../core/defaults';
import type { SetSegments, Target } from '../core/types';
import {
  addWeightSet, getOrCreateSession, saveCardioEntry, type CardioInput, type NewExercise,
} from '../db/repository';
import type { WorkoutDB } from '../db/schema';

export function weightExercise(overrides: Partial<NewExercise> = {}): NewExercise {
  return {
    equipment: '레그프레스', name: '하체', kind: 'weight', restSeconds: DEFAULT_REST_SECONDS,
    weight: { ...DEFAULT_WEIGHT }, ...overrides,
  };
}

export function cardioExercise(overrides: Partial<NewExercise> = {}): NewExercise {
  return {
    equipment: '러닝머신', name: '달리기', kind: 'cardio', restSeconds: DEFAULT_REST_SECONDS,
    cardio: {
      ...DEFAULT_CARDIO,
      metrics: [
        { key: 'speed', label: '속도', unit: 'km/h', step: 0.5 },
        { key: 'incline', label: '경사', unit: '%', step: 1 },
      ],
      primaryMetric: 'speed',
    },
    ...overrides,
  };
}

export async function seedWeightSession(
  db: WorkoutDB, exerciseId: string, date: string, sets: SetSegments[], target?: Target,
) {
  const session = await getOrCreateSession(db, exerciseId, date, target);
  for (const segments of sets) await addWeightSet(db, session.id, segments);
  return session;
}

export async function seedCardioSession(
  db: WorkoutDB, exerciseId: string, date: string, input: CardioInput, target?: Target,
) {
  const session = await getOrCreateSession(db, exerciseId, date, target);
  await saveCardioEntry(db, session.id, input);
  return session;
}
```

- [ ] **Step 2: 실패하는 테스트**

`src/db/repository.test.ts`
```ts
import { describe, expect, it } from 'vitest';
import { cardioExercise, seedCardioSession, seedWeightSession, weightExercise } from '../test/fixtures';
import { makeTestDb } from '../test/testDb';
import {
  addExercise, addWeightSet, cardioHistory, deleteWeightSet, DuplicateExerciseError, exerciseHistory,
  getCardioEntry, getMeta, getOrCreateSession, listExercises, listWeightSets, recentExerciseIds,
  saveCardioEntry, setMeta, setSessionTarget, updateExercise, updateWeightSet, weightHistory,
} from './repository';

const target = { type: 'double' as const, sets: [{ weight: 40, reps: 12 }] };

describe('운동', () => {
  it('공백을 다듬어 저장하고 id를 붙인다', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, weightExercise({ equipment: ' 레그프레스 ', name: '하체 ' }));
    expect(ex).toMatchObject({ equipment: '레그프레스', name: '하체', archived: false });
    expect(ex.id).toBeTruthy();
  });
  it('(기구, 종류) 중복을 거부한다', async () => {
    const db = makeTestDb();
    await addExercise(db, weightExercise());
    await expect(addExercise(db, weightExercise())).rejects.toBeInstanceOf(DuplicateExerciseError);
  });
  it('이름이 비면 거부한다', async () => {
    const db = makeTestDb();
    await expect(addExercise(db, weightExercise({ name: '  ' }))).rejects.toThrow('기구 이름과 운동 종류를 입력하세요');
  });
  it('수정할 때 자기 자신은 중복이 아니다, 남과 겹치면 거부', async () => {
    const db = makeTestDb();
    const a = await addExercise(db, weightExercise());
    const b = await addExercise(db, weightExercise({ name: '종아리' }));
    await expect(updateExercise(db, { ...a, restSeconds: 60 })).resolves.toMatchObject({ restSeconds: 60 });
    await expect(updateExercise(db, { ...b, name: '하체' })).rejects.toBeInstanceOf(DuplicateExerciseError);
  });
  it('목록은 등록 순, 숨긴 운동은 기본 제외', async () => {
    const db = makeTestDb();
    const a = await addExercise(db, weightExercise({ name: 'A' }));
    await addExercise(db, weightExercise({ name: 'B' }));
    await updateExercise(db, { ...a, archived: true });
    expect((await listExercises(db)).map((e) => e.name)).toEqual(['B']);
    expect((await listExercises(db, true)).map((e) => e.name)).toEqual(['A', 'B']);
  });
});

describe('세션과 세트', () => {
  it('같은 운동·같은 날은 한 세션, 목표는 처음 것만 저장', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, weightExercise());
    const s1 = await getOrCreateSession(db, ex.id, '2026-10-17');
    const s2 = await getOrCreateSession(db, ex.id, '2026-10-17', target);
    const s3 = await getOrCreateSession(db, ex.id, '2026-10-17', { type: 'double', sets: [] });
    expect(s2.id).toBe(s1.id);
    expect(s3.target).toEqual(target);
    await setSessionTarget(db, s1.id, { type: 'double', sets: [] });
    expect((await db.sessions.get(s1.id))?.target).toEqual({ type: 'double', sets: [] });
  });
  it('세트 순서는 마지막+1, 삭제 후에도 겹치지 않는다', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, weightExercise());
    const s = await getOrCreateSession(db, ex.id, '2026-10-17');
    const a = await addWeightSet(db, s.id, [{ weight: 40, reps: 12 }]);
    await addWeightSet(db, s.id, [{ weight: 40, reps: 10 }]);
    await deleteWeightSet(db, a.id);
    const c = await addWeightSet(db, s.id, [{ weight: 40, reps: 9 }, { weight: 30, reps: 3 }]);
    expect(c.order).toBe(2);
    await updateWeightSet(db, c.id, [{ weight: 40, reps: 10 }]);
    expect((await listWeightSets(db, s.id)).map((x) => x.segments[0].reps)).toEqual([10, 10]);
  });
  it('잘못된 구간을 거부한다', async () => {
    const db = makeTestDb();
    await expect(addWeightSet(db, 's', [])).rejects.toThrow('구간이 하나 이상 있어야 해요');
    await expect(addWeightSet(db, 's', [{ weight: -1, reps: 5 }])).rejects.toThrow('무게는 0 이상이어야 해요');
    await expect(addWeightSet(db, 's', [{ weight: 10, reps: 0 }])).rejects.toThrow('횟수는 1 이상의 정수여야 해요');
  });
});

describe('유산소', () => {
  it('세션당 한 기록 — 다시 저장하면 교체', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, cardioExercise());
    const s = await getOrCreateSession(db, ex.id, '2026-10-17');
    await saveCardioEntry(db, s.id, { minutes: 20, intensity: { speed: 10 } });
    await saveCardioEntry(db, s.id, { minutes: 25, intensity: { speed: 10 }, distanceKm: 4.2, kcal: 250 });
    expect(await db.cardioEntries.count()).toBe(1);
    expect(await getCardioEntry(db, s.id)).toMatchObject({ minutes: 25, distanceKm: 4.2, kcal: 250 });
  });
  it('잘못된 값을 거부한다', async () => {
    const db = makeTestDb();
    await expect(saveCardioEntry(db, 's', { minutes: 0, intensity: {} })).rejects.toThrow('운동 시간은 0보다 커야 해요');
    await expect(saveCardioEntry(db, 's', { minutes: 10, intensity: { speed: -1 } })).rejects.toThrow('강도는 0 이상이어야 해요');
    await expect(saveCardioEntry(db, 's', { minutes: 10, intensity: {}, distanceKm: -1 })).rejects.toThrow('거리는 0 이상이어야 해요');
    await expect(saveCardioEntry(db, 's', { minutes: 10, intensity: {}, kcal: -5 })).rejects.toThrow('칼로리는 0 이상이어야 해요');
  });
});

describe('히스토리', () => {
  it('웨이트: 날짜 오름차순, 빈 세션 제외, 목표 포함', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, weightExercise());
    await seedWeightSession(db, ex.id, '2026-10-14', [[{ weight: 40, reps: 12 }]], target);
    await seedWeightSession(db, ex.id, '2026-10-10', [[{ weight: 40, reps: 10 }]]);
    await getOrCreateSession(db, ex.id, '2026-10-16');
    expect(await weightHistory(db, ex.id)).toEqual([
      { date: '2026-10-10', sets: [[{ weight: 40, reps: 10 }]] },
      { date: '2026-10-14', sets: [[{ weight: 40, reps: 12 }]], target },
    ]);
    expect(await exerciseHistory(db, ex)).toHaveLength(2);
  });
  it('유산소', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, cardioExercise());
    await seedCardioSession(db, ex.id, '2026-10-14', { minutes: 30, intensity: { speed: 10 }, kcal: 300 });
    expect(await cardioHistory(db, ex.id)).toEqual([{ date: '2026-10-14', minutes: 30, intensity: { speed: 10 }, kcal: 300 }]);
  });
  it('최근 7일 안에 기록한 운동 id', async () => {
    const db = makeTestDb();
    const a = await addExercise(db, weightExercise({ name: 'A' }));
    const b = await addExercise(db, weightExercise({ name: 'B' }));
    await seedWeightSession(db, a.id, '2026-10-11', [[{ weight: 1, reps: 1 }]]);
    await seedWeightSession(db, b.id, '2026-10-09', [[{ weight: 1, reps: 1 }]]);
    expect(await recentExerciseIds(db, '2026-10-17')).toEqual([a.id]);
  });
});

describe('메타', () => {
  it('get/set', async () => {
    const db = makeTestDb();
    expect(await getMeta(db, 'x')).toBeUndefined();
    await setMeta(db, 'x', ['a']);
    expect(await getMeta<string[]>(db, 'x')).toEqual(['a']);
  });
});
```

Run: `npx vitest run src/db` → FAIL

- [ ] **Step 3: 구현** — `src/db/repository.ts`

```ts
import { addDays } from '../core/date';
import type {
  CardioEntry, CardioHistoryItem, Exercise, History, Segment, Session, Target, WeightHistoryItem, WeightSetRecord,
} from '../core/types';
import type { WorkoutDB } from './schema';

export class DuplicateExerciseError extends Error {
  constructor(equipment: string, name: string) {
    super(`이미 등록된 운동이에요: ${equipment} · ${name}`);
    this.name = 'DuplicateExerciseError';
  }
}

export type NewExercise = Omit<Exercise, 'id' | 'createdAt' | 'archived'>;
export type CardioInput = Omit<CardioEntry, 'id' | 'sessionId'>;

/** http(LAN 개발 서버)에서는 crypto.randomUUID가 없을 수 있다 */
export function newId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

let lastCreatedAt = 0;
function nextCreatedAt(): number {
  lastCreatedAt = Math.max(Date.now(), lastCreatedAt + 1);
  return lastCreatedAt;
}

function cleanNames(e: { equipment: string; name: string }) {
  const equipment = e.equipment.trim();
  const name = e.name.trim();
  if (!equipment || !name) throw new Error('기구 이름과 운동 종류를 입력하세요');
  return { equipment, name };
}

async function assertUnique(db: WorkoutDB, equipment: string, name: string, selfId?: string) {
  const dup = await db.exercises.where('[equipment+name]').equals([equipment, name]).first();
  if (dup && dup.id !== selfId) throw new DuplicateExerciseError(equipment, name);
}

export async function addExercise(db: WorkoutDB, input: NewExercise): Promise<Exercise> {
  const names = cleanNames(input);
  await assertUnique(db, names.equipment, names.name);
  const ex: Exercise = { ...input, ...names, id: newId(), createdAt: nextCreatedAt(), archived: false };
  await db.exercises.add(ex);
  return ex;
}

export async function updateExercise(db: WorkoutDB, ex: Exercise): Promise<Exercise> {
  const names = cleanNames(ex);
  await assertUnique(db, names.equipment, names.name, ex.id);
  const next = { ...ex, ...names };
  await db.exercises.put(next);
  return next;
}

export async function listExercises(db: WorkoutDB, includeArchived = false): Promise<Exercise[]> {
  const all = await db.exercises.toArray();
  return all.filter((e) => includeArchived || !e.archived).sort((a, b) => a.createdAt - b.createdAt);
}

export function findSession(db: WorkoutDB, exerciseId: string, date: string): Promise<Session | undefined> {
  return db.sessions.where('[exerciseId+date]').equals([exerciseId, date]).first();
}

/** 같은 운동·같은 날 세션은 하나. 목표 스냅샷은 비어 있을 때만 채운다 */
export async function getOrCreateSession(
  db: WorkoutDB, exerciseId: string, date: string, target?: Target,
): Promise<Session> {
  return db.transaction('rw', db.sessions, async () => {
    const found = await findSession(db, exerciseId, date);
    if (found) {
      if (!found.target && target) {
        const next = { ...found, target };
        await db.sessions.put(next);
        return next;
      }
      return found;
    }
    const session: Session = { id: newId(), exerciseId, date, ...(target ? { target } : {}) };
    await db.sessions.add(session);
    return session;
  });
}

export async function setSessionTarget(db: WorkoutDB, sessionId: string, target: Target): Promise<void> {
  const s = await db.sessions.get(sessionId);
  if (s) await db.sessions.put({ ...s, target });
}

export function validateSegments(segments: Segment[]): void {
  if (segments.length === 0) throw new Error('구간이 하나 이상 있어야 해요');
  for (const s of segments) {
    if (!Number.isFinite(s.weight) || s.weight < 0) throw new Error('무게는 0 이상이어야 해요');
    if (!Number.isInteger(s.reps) || s.reps < 1) throw new Error('횟수는 1 이상의 정수여야 해요');
  }
}

const copySegments = (segments: Segment[]) => segments.map((s) => ({ weight: s.weight, reps: s.reps }));

export async function listWeightSets(db: WorkoutDB, sessionId: string): Promise<WeightSetRecord[]> {
  const sets = await db.weightSets.where('sessionId').equals(sessionId).toArray();
  return sets.sort((a, b) => a.order - b.order);
}

export async function addWeightSet(db: WorkoutDB, sessionId: string, segments: Segment[]): Promise<WeightSetRecord> {
  validateSegments(segments);
  return db.transaction('rw', db.weightSets, async () => {
    const existing = await listWeightSets(db, sessionId);
    const order = existing.length ? existing[existing.length - 1].order + 1 : 0;
    const record: WeightSetRecord = { id: newId(), sessionId, order, segments: copySegments(segments) };
    await db.weightSets.add(record);
    return record;
  });
}

export async function updateWeightSet(db: WorkoutDB, id: string, segments: Segment[]): Promise<void> {
  validateSegments(segments);
  const record = await db.weightSets.get(id);
  if (!record) throw new Error('세트를 찾을 수 없어요');
  await db.weightSets.put({ ...record, segments: copySegments(segments) });
}

export async function deleteWeightSet(db: WorkoutDB, id: string): Promise<void> {
  await db.weightSets.delete(id);
}

export function validateCardio(input: CardioInput): void {
  if (!Number.isFinite(input.minutes) || input.minutes <= 0) throw new Error('운동 시간은 0보다 커야 해요');
  for (const v of Object.values(input.intensity)) {
    if (!Number.isFinite(v) || v < 0) throw new Error('강도는 0 이상이어야 해요');
  }
  if (input.distanceKm !== undefined && (!Number.isFinite(input.distanceKm) || input.distanceKm < 0)) {
    throw new Error('거리는 0 이상이어야 해요');
  }
  if (input.kcal !== undefined && (!Number.isFinite(input.kcal) || input.kcal < 0)) {
    throw new Error('칼로리는 0 이상이어야 해요');
  }
}

export function getCardioEntry(db: WorkoutDB, sessionId: string): Promise<CardioEntry | undefined> {
  return db.cardioEntries.where('sessionId').equals(sessionId).first();
}

export async function saveCardioEntry(db: WorkoutDB, sessionId: string, input: CardioInput): Promise<CardioEntry> {
  validateCardio(input);
  return db.transaction('rw', db.cardioEntries, async () => {
    const existing = await getCardioEntry(db, sessionId);
    const entry: CardioEntry = {
      id: existing?.id ?? newId(),
      sessionId,
      minutes: input.minutes,
      intensity: { ...input.intensity },
      ...(input.distanceKm !== undefined ? { distanceKm: input.distanceKm } : {}),
      ...(input.kcal !== undefined ? { kcal: input.kcal } : {}),
    };
    await db.cardioEntries.put(entry);
    return entry;
  });
}

async function sessionsOf(db: WorkoutDB, exerciseId: string): Promise<Session[]> {
  const sessions = await db.sessions.where('exerciseId').equals(exerciseId).toArray();
  return sessions.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
}

export async function weightHistory(db: WorkoutDB, exerciseId: string): Promise<WeightHistoryItem[]> {
  const out: WeightHistoryItem[] = [];
  for (const s of await sessionsOf(db, exerciseId)) {
    const sets = await listWeightSets(db, s.id);
    if (sets.length === 0) continue;
    out.push({ date: s.date, sets: sets.map((x) => x.segments), ...(s.target ? { target: s.target } : {}) });
  }
  return out;
}

export async function cardioHistory(db: WorkoutDB, exerciseId: string): Promise<CardioHistoryItem[]> {
  const out: CardioHistoryItem[] = [];
  for (const s of await sessionsOf(db, exerciseId)) {
    const e = await getCardioEntry(db, s.id);
    if (!e) continue;
    out.push({
      date: s.date,
      minutes: e.minutes,
      intensity: e.intensity,
      ...(e.distanceKm !== undefined ? { distanceKm: e.distanceKm } : {}),
      ...(e.kcal !== undefined ? { kcal: e.kcal } : {}),
      ...(s.target ? { target: s.target } : {}),
    });
  }
  return out;
}

export function exerciseHistory(db: WorkoutDB, ex: Exercise): Promise<History> {
  return ex.kind === 'weight' ? weightHistory(db, ex.id) : cardioHistory(db, ex.id);
}

export async function recentExerciseIds(db: WorkoutDB, today: string, days = 7): Promise<string[]> {
  const sessions = await db.sessions.where('date').between(addDays(today, -days), today, true, true).toArray();
  return [...new Set(sessions.map((s) => s.exerciseId))];
}

export async function getMeta<T>(db: WorkoutDB, key: string): Promise<T | undefined> {
  return (await db.meta.get(key))?.value as T | undefined;
}

export async function setMeta(db: WorkoutDB, key: string, value: unknown): Promise<void> {
  await db.meta.put({ key, value });
}
```

- [ ] **Step 4: 확인** — PASS
- [ ] **Step 5: 커밋** — `feat(tracking-workout): Dexie 스키마와 기록 저장소`

---

### Task 9: JSON 백업·복원

**Files:**
- Create: `src/db/backup.ts`
- Test: `src/db/backup.test.ts`

**Interfaces:**
- Produces: `BACKUP_APP`, `BACKUP_VERSION`, `interface BackupFile`, `BackupError`, `exportBackup(db, now?)`, `parseBackup(text): BackupFile`, `restoreBackup(db, file)`, `markBackedUp(db, now?)`, `backupFileName(now?)`

- [ ] **Step 1: 실패하는 테스트**

```ts
import { describe, expect, it } from 'vitest';
import { seedWeightSession, weightExercise } from '../test/fixtures';
import { makeTestDb } from '../test/testDb';
import { BackupError, backupFileName, exportBackup, markBackedUp, parseBackup, restoreBackup } from './backup';
import { addExercise, getMeta, listExercises, weightHistory } from './repository';

describe('backup', () => {
  it('내보내기 → 파싱 → 다른 DB에 복원하면 같은 데이터', async () => {
    const src = makeTestDb();
    const ex = await addExercise(src, weightExercise());
    await seedWeightSession(src, ex.id, '2026-10-14', [[{ weight: 40, reps: 12 }, { weight: 30, reps: 4 }]]);
    const file = await exportBackup(src, new Date('2026-10-17T10:00:00Z'));
    expect(file).toMatchObject({ app: 'tracking-workout', version: 1, exportedAt: '2026-10-17T10:00:00.000Z' });

    const dst = makeTestDb();
    await addExercise(dst, weightExercise({ name: '지워질 운동' }));
    await restoreBackup(dst, parseBackup(JSON.stringify(file)));
    expect((await listExercises(dst)).map((e) => e.name)).toEqual(['하체']);
    expect(await weightHistory(dst, ex.id)).toEqual(await weightHistory(src, ex.id));
  });
  it('잘못된 파일을 거부한다', () => {
    expect(() => parseBackup('not json')).toThrow(BackupError);
    expect(() => parseBackup(JSON.stringify({ app: 'other' }))).toThrow('이 앱의 백업 파일이 아니에요');
    expect(() => parseBackup(JSON.stringify({ app: 'tracking-workout', version: 99, data: {} }))).toThrow('지원하지 않는 백업 버전');
    const base = { app: 'tracking-workout', version: 1, exportedAt: '', data: { exercises: [], sessions: [], weightSets: [], cardioEntries: [], meta: [] } };
    expect(() => parseBackup(JSON.stringify({ ...base, data: { ...base.data, sessions: undefined } }))).toThrow('백업에 sessions 목록이 없어요');
    expect(() => parseBackup(JSON.stringify({ ...base, data: { ...base.data, exercises: [{ id: 'x' }] } }))).toThrow('운동 데이터가 손상됐어요');
    expect(() => parseBackup(JSON.stringify({ ...base, data: { ...base.data, sessions: [{ id: 's', exerciseId: 'x', date: '10/17' }] } }))).toThrow('세션 데이터가 손상됐어요');
    expect(parseBackup(JSON.stringify(base)).data.exercises).toEqual([]);
  });
  it('백업 시각 기록과 파일 이름', async () => {
    const db = makeTestDb();
    await markBackedUp(db, new Date('2026-10-17T10:00:00Z'));
    expect(await getMeta(db, 'lastBackupAt')).toBe('2026-10-17T10:00:00.000Z');
    expect(backupFileName(new Date(2026, 9, 17, 9, 5))).toBe('tracking-workout-20261017-0905.json');
  });
});
```

- [ ] **Step 2: 구현**

```ts
import type { CardioEntry, Exercise, Session, WeightSetRecord } from '../core/types';
import { setMeta } from './repository';
import type { MetaRow, WorkoutDB } from './schema';

export const BACKUP_APP = 'tracking-workout';
export const BACKUP_VERSION = 1;

export interface BackupData {
  exercises: Exercise[];
  sessions: Session[];
  weightSets: WeightSetRecord[];
  cardioEntries: CardioEntry[];
  meta: MetaRow[];
}

export interface BackupFile {
  app: typeof BACKUP_APP;
  version: number;
  exportedAt: string;
  data: BackupData;
}

export class BackupError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'BackupError';
  }
}

export async function exportBackup(db: WorkoutDB, now: Date = new Date()): Promise<BackupFile> {
  const [exercises, sessions, weightSets, cardioEntries, meta] = await Promise.all([
    db.exercises.toArray(), db.sessions.toArray(), db.weightSets.toArray(), db.cardioEntries.toArray(), db.meta.toArray(),
  ]);
  return {
    app: BACKUP_APP, version: BACKUP_VERSION, exportedAt: now.toISOString(),
    data: { exercises, sessions, weightSets, cardioEntries, meta },
  };
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function check(items: unknown[], ok: (v: Record<string, unknown>) => boolean, message: string) {
  for (const v of items) if (!isObj(v) || !ok(v)) throw new BackupError(message);
}

export function parseBackup(text: string): BackupFile {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    throw new BackupError('JSON 형식의 백업 파일이 아니에요');
  }
  if (!isObj(raw) || raw.app !== BACKUP_APP) throw new BackupError('이 앱의 백업 파일이 아니에요');
  if (typeof raw.version !== 'number' || raw.version > BACKUP_VERSION) {
    throw new BackupError('지원하지 않는 백업 버전이에요. 앱을 업데이트하세요');
  }
  const d = raw.data;
  if (!isObj(d)) throw new BackupError('백업에 데이터가 없어요');
  const list = (key: string): unknown[] => {
    const v = d[key];
    if (!Array.isArray(v)) throw new BackupError(`백업에 ${key} 목록이 없어요`);
    return v;
  };
  const exercises = list('exercises');
  const sessions = list('sessions');
  const weightSets = list('weightSets');
  const cardioEntries = list('cardioEntries');
  const meta = Array.isArray(d.meta) ? d.meta : [];

  check(exercises, (e) => typeof e.id === 'string' && typeof e.equipment === 'string' && typeof e.name === 'string'
    && (e.kind === 'weight' || e.kind === 'cardio'), '운동 데이터가 손상됐어요');
  check(sessions, (s) => typeof s.id === 'string' && typeof s.exerciseId === 'string'
    && typeof s.date === 'string' && DATE_RE.test(s.date), '세션 데이터가 손상됐어요');
  check(weightSets, (w) => typeof w.id === 'string' && typeof w.sessionId === 'string' && Array.isArray(w.segments),
    '세트 데이터가 손상됐어요');
  check(cardioEntries, (c) => typeof c.id === 'string' && typeof c.sessionId === 'string' && typeof c.minutes === 'number',
    '유산소 데이터가 손상됐어요');
  check(meta, (m) => typeof m.key === 'string', '설정 데이터가 손상됐어요');

  return {
    app: BACKUP_APP,
    version: raw.version,
    exportedAt: typeof raw.exportedAt === 'string' ? raw.exportedAt : '',
    data: {
      exercises: exercises as Exercise[],
      sessions: sessions as Session[],
      weightSets: weightSets as WeightSetRecord[],
      cardioEntries: cardioEntries as CardioEntry[],
      meta: meta as MetaRow[],
    },
  };
}

/** 현재 데이터를 모두 지우고 백업 내용으로 교체한다(한 트랜잭션) */
export async function restoreBackup(db: WorkoutDB, file: BackupFile): Promise<void> {
  const tables = [db.exercises, db.sessions, db.weightSets, db.cardioEntries, db.meta];
  await db.transaction('rw', tables, async () => {
    await Promise.all(tables.map((t) => t.clear()));
    await db.exercises.bulkAdd(file.data.exercises);
    await db.sessions.bulkAdd(file.data.sessions);
    await db.weightSets.bulkAdd(file.data.weightSets);
    await db.cardioEntries.bulkAdd(file.data.cardioEntries);
    await db.meta.bulkAdd(file.data.meta);
  });
}

export async function markBackedUp(db: WorkoutDB, now: Date = new Date()): Promise<void> {
  await setMeta(db, 'lastBackupAt', now.toISOString());
}

export function backupFileName(now: Date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `tracking-workout-${now.getFullYear()}${p(now.getMonth() + 1)}${p(now.getDate())}-${p(now.getHours())}${p(now.getMinutes())}.json`;
}
```

- [ ] **Step 3: 확인** — PASS
- [ ] **Step 4: 커밋** — `feat(tracking-workout): JSON 백업 내보내기·검증·복원`

---

### Task 10: 앱 셸 — DB 컨텍스트·라우팅·탭바·포맷터·테마

**Files:**
- Create: `src/ui/DbContext.tsx`, `src/ui/routes.ts`, `src/ui/format.ts`, `src/ui/theme.css`, `src/ui/components/TabBar.tsx`, `src/ui/components/ScreenHeader.tsx`, `src/ui/components/BadgeStrip.tsx`, `src/ui/screens/{TodayScreen,LogScreen,HistoryScreen,DetailScreen,SettingsScreen,ExerciseFormScreen}.tsx`(자리표시), `src/test/renderApp.tsx`
- Modify: `src/App.tsx`, `src/main.tsx`, `src/App.test.tsx`
- Test: `src/ui/format.test.ts`, `src/App.test.tsx`

**Interfaces:**
- Produces: `DbProvider({db, children})`, `useDb(): WorkoutDB`; `type Route`, `type Navigate = (r: Route) => void`, `type Tab`, `tabOf(route): Tab`; format: `formatKg`, `formatSet`, `formatWeightTarget`, `formatCardio`, `formatTarget`, `formatLongDate`, `exerciseLabel`, `BADGE_SYMBOL`, `BADGE_LABEL`; `ScreenHeader({title, onBack?})`, `BadgeStrip({badges})`; `renderApp(db?) → { db, user, ...RenderResult }`. 모든 화면 컴포넌트 props: `{ navigate: Navigate }` (+ `exerciseId` for log/detail, `exerciseId?` for exerciseForm).

- [ ] **Step 1: 실패하는 테스트**

`src/ui/format.test.ts`
```ts
import { describe, expect, it } from 'vitest';
import { cardioExercise } from '../test/fixtures';
import { exerciseLabel, formatCardio, formatKg, formatLongDate, formatSet, formatTarget, formatWeightTarget } from './format';

describe('format', () => {
  it('무게와 세트', () => {
    expect(formatKg(42.5)).toBe('42.5');
    expect(formatKg(40)).toBe('40');
    expect(formatSet([{ weight: 10, reps: 7 }, { weight: 8, reps: 5 }])).toBe('10kg×7 → 8kg×5');
  });
  it('웨이트 목표', () => {
    expect(formatWeightTarget({ type: 'double', sets: [{ weight: 40, reps: 12 }, { weight: 40, reps: 11 }] })).toBe('40kg × 12/11');
    expect(formatWeightTarget({ type: 'double', sets: [{ weight: 40, reps: 12 }, { weight: 35, reps: 10 }] })).toBe('40×12 / 35×10');
    expect(formatWeightTarget({ type: 'volume', volume: 330, sets: [{ weight: 10, reps: 8 }] })).toBe('10kg × 8 (볼륨 330kg)');
  });
  it('유산소', () => {
    const ex = { ...cardioExercise(), id: 'c', createdAt: 1, archived: false };
    expect(formatCardio({ minutes: 25, intensity: { speed: 10.5, incline: 3 } }, ex.cardio!.metrics)).toBe('25분 · 속도 10.5km/h · 경사 3%');
    expect(formatTarget({ type: 'cardio', minutes: 20, intensity: { speed: 10 } }, ex)).toBe('20분 · 속도 10km/h · 경사 0%');
    expect(exerciseLabel(ex)).toBe('러닝머신 · 달리기');
  });
  it('긴 날짜', () => {
    expect(formatLongDate('2026-10-17')).toBe('10월 17일 (토)');
  });
});
```

`src/App.test.tsx` (교체)
```tsx
import { screen } from '@testing-library/react';
import { expect, it } from 'vitest';
import { renderApp } from './test/renderApp';

it('하단 탭으로 화면을 전환한다', async () => {
  const { user } = renderApp();
  expect(screen.getByRole('button', { name: '오늘' })).toHaveAttribute('aria-current', 'page');
  await user.click(screen.getByRole('button', { name: '설정' }));
  expect(screen.getByRole('button', { name: '설정' })).toHaveAttribute('aria-current', 'page');
  await user.click(screen.getByRole('button', { name: '기록' }));
  expect(screen.getByRole('button', { name: '기록' })).toHaveAttribute('aria-current', 'page');
});
```

- [ ] **Step 2: 구현**

`src/ui/DbContext.tsx`
```tsx
import { createContext, useContext, type ReactNode } from 'react';
import type { WorkoutDB } from '../db/schema';

const DbContext = createContext<WorkoutDB | null>(null);

export function DbProvider({ db, children }: { db: WorkoutDB; children: ReactNode }) {
  return <DbContext.Provider value={db}>{children}</DbContext.Provider>;
}

export function useDb(): WorkoutDB {
  const db = useContext(DbContext);
  if (!db) throw new Error('DbProvider가 없습니다');
  return db;
}
```

`src/ui/routes.ts`
```ts
export type Route =
  | { name: 'today' }
  | { name: 'log'; exerciseId: string }
  | { name: 'history' }
  | { name: 'detail'; exerciseId: string }
  | { name: 'settings' }
  | { name: 'exerciseForm'; exerciseId?: string };

export type Navigate = (route: Route) => void;
export type Tab = 'today' | 'history' | 'settings';

export function tabOf(route: Route): Tab {
  switch (route.name) {
    case 'today':
    case 'log':
      return 'today';
    case 'history':
    case 'detail':
      return 'history';
    default:
      return 'settings';
  }
}
```

`src/ui/format.ts`
```ts
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
```

`src/ui/components/TabBar.tsx`
```tsx
import type { Tab } from '../routes';

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'today', label: '오늘', icon: '🏋️' },
  { id: 'history', label: '기록', icon: '📈' },
  { id: 'settings', label: '설정', icon: '⚙️' },
];

export function TabBar({ active, onSelect }: { active: Tab; onSelect: (tab: Tab) => void }) {
  return (
    <nav className="tabbar" aria-label="메인 메뉴">
      {TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          className={t.id === active ? 'tab active' : 'tab'}
          aria-current={t.id === active ? 'page' : undefined}
          onClick={() => onSelect(t.id)}
        >
          <span aria-hidden="true">{t.icon}</span>
          {t.label}
        </button>
      ))}
    </nav>
  );
}
```

`src/ui/components/ScreenHeader.tsx`
```tsx
export function ScreenHeader({ title, onBack }: { title: string; onBack?: () => void }) {
  return (
    <header className="screen-header">
      {onBack && (
        <button type="button" className="back" aria-label="뒤로" onClick={onBack}>
          ←
        </button>
      )}
      <h1>{title}</h1>
    </header>
  );
}
```

`src/ui/components/BadgeStrip.tsx`
```tsx
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
```

자리표시 화면 6개 (이후 태스크에서 파일 전체 교체). 예: `src/ui/screens/TodayScreen.tsx`
```tsx
import type { Navigate } from '../routes';
import { ScreenHeader } from '../components/ScreenHeader';

export function TodayScreen(_props: { navigate: Navigate }) {
  return <ScreenHeader title="오늘" />;
}
```
같은 형태로 `HistoryScreen`(title "기록"), `SettingsScreen`("설정"), `LogScreen`(props `{ exerciseId: string; navigate: Navigate }`, title "기록하기"), `DetailScreen`(`{ exerciseId: string; navigate }`, "운동 상세"), `ExerciseFormScreen`(`{ exerciseId?: string; navigate }`, "운동 등록").

`src/App.tsx`
```tsx
import { useState } from 'react';
import { TabBar } from './ui/components/TabBar';
import { tabOf, type Navigate, type Route } from './ui/routes';
import { DetailScreen } from './ui/screens/DetailScreen';
import { ExerciseFormScreen } from './ui/screens/ExerciseFormScreen';
import { HistoryScreen } from './ui/screens/HistoryScreen';
import { LogScreen } from './ui/screens/LogScreen';
import { SettingsScreen } from './ui/screens/SettingsScreen';
import { TodayScreen } from './ui/screens/TodayScreen';

function renderRoute(route: Route, navigate: Navigate) {
  switch (route.name) {
    case 'today':
      return <TodayScreen navigate={navigate} />;
    case 'log':
      return <LogScreen key={route.exerciseId} exerciseId={route.exerciseId} navigate={navigate} />;
    case 'history':
      return <HistoryScreen navigate={navigate} />;
    case 'detail':
      return <DetailScreen key={route.exerciseId} exerciseId={route.exerciseId} navigate={navigate} />;
    case 'settings':
      return <SettingsScreen navigate={navigate} />;
    case 'exerciseForm':
      return <ExerciseFormScreen key={route.exerciseId ?? 'new'} exerciseId={route.exerciseId} navigate={navigate} />;
  }
}

export function App() {
  const [route, setRoute] = useState<Route>({ name: 'today' });
  const navigate: Navigate = (r) => {
    setRoute(r);
    window.scrollTo?.(0, 0);
  };
  return (
    <div className="app">
      <main className="screen">{renderRoute(route, navigate)}</main>
      <TabBar active={tabOf(route)} onSelect={(tab) => navigate({ name: tab })} />
    </div>
  );
}
```

`src/main.tsx`
```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { WorkoutDB } from './db/schema';
import { DbProvider } from './ui/DbContext';
import './ui/theme.css';

const db = new WorkoutDB();
// 브라우저가 저장소를 임의로 비우지 않도록 요청(특히 iOS)
navigator.storage?.persist?.().catch(() => undefined);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <DbProvider db={db}>
      <App />
    </DbProvider>
  </StrictMode>,
);
```

`src/test/renderApp.tsx`
```tsx
import { render } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from '../App';
import type { WorkoutDB } from '../db/schema';
import { DbProvider } from '../ui/DbContext';
import { makeTestDb } from './testDb';

export function renderApp(db: WorkoutDB = makeTestDb()) {
  const user = userEvent.setup();
  const result = render(
    <DbProvider db={db}>
      <App />
    </DbProvider>,
  );
  return { ...result, db, user };
}
```

`src/ui/theme.css`
```css
:root {
  --bg: #f6f6f4;
  --surface: #ffffff;
  --text: #1d1d1f;
  --muted: #6e6e73;
  --line: #e2e2e0;
  --accent: #ff6b35;
  --accent-text: #ffffff;
  --drop: #7aa6ff;
  --gold: #e5a900;
  --up: #1f9d55;
  --same: #8a8a8e;
  --down: #d64545;
  --danger: #d64545;
  --radius: 14px;
  color-scheme: light;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #121214;
    --surface: #1e1e21;
    --text: #f2f2f4;
    --muted: #a0a0a6;
    --line: #2e2e33;
    --drop: #5d86d9;
    color-scheme: dark;
  }
}

* { box-sizing: border-box; }

html, body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: system-ui, -apple-system, 'Apple SD Gothic Neo', 'Noto Sans KR', sans-serif;
  font-size: 16px;
  -webkit-tap-highlight-color: transparent;
}

button, input, select { font: inherit; color: inherit; }

button {
  min-height: 44px;
  padding: 0 14px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
  cursor: pointer;
}
button:disabled { opacity: 0.4; }
button.primary { background: var(--accent); border-color: var(--accent); color: var(--accent-text); font-weight: 700; }
button.danger { color: var(--danger); }
button[aria-pressed='true'] { background: var(--accent); border-color: var(--accent); color: var(--accent-text); }

input[type='number'], input[type='text'] {
  min-height: 44px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
  width: 100%;
}

.app { min-height: 100dvh; padding-bottom: calc(72px + env(safe-area-inset-bottom)); }
.screen { max-width: 560px; margin: 0 auto; padding: 12px 16px 24px; padding-top: calc(12px + env(safe-area-inset-top)); }

.tabbar {
  position: fixed; left: 0; right: 0; bottom: 0;
  display: grid; grid-template-columns: repeat(3, 1fr);
  padding-bottom: env(safe-area-inset-bottom);
  background: var(--surface); border-top: 1px solid var(--line);
}
.tab { border: none; border-radius: 0; min-height: 60px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 2px; font-size: 13px; color: var(--muted); background: none; }
.tab.active { color: var(--accent); font-weight: 700; }

.screen-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.screen-header h1 { font-size: 22px; margin: 0; }
.back { min-width: 44px; padding: 0; }

.card-list, .set-list, .plain-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); display: flex; align-items: stretch; }
.card-main { flex: 1; text-align: left; border: none; background: none; padding: 14px; min-height: 64px; display: grid; gap: 4px; }
.card-title { font-weight: 700; }
.card-sub { color: var(--muted); font-size: 14px; }
.order-btns { display: grid; border-left: 1px solid var(--line); }
.order-btns button { border: none; border-radius: 0; background: none; }

.row { display: flex; gap: 8px; flex-wrap: wrap; margin: 12px 0; }
.row > button { flex: 1; }
.muted { color: var(--muted); }
.note { color: var(--accent); font-weight: 600; }
.hint { color: var(--muted); font-size: 14px; }

.badges { display: inline-flex; gap: 4px; font-size: 14px; }
.badge-up { color: var(--up); }
.badge-same { color: var(--same); }
.badge-down { color: var(--down); }

.banner { background: color-mix(in srgb, var(--accent) 12%, var(--surface)); border: 1px solid var(--accent); border-radius: var(--radius); padding: 10px 12px; margin-bottom: 12px; font-size: 14px; display: flex; gap: 8px; align-items: center; justify-content: space-between; }

.today-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px; }
.today-head h1 { margin: 0; font-size: 22px; }
.rate { font-weight: 700; color: var(--accent); }

.target-box { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 12px 14px; margin-bottom: 12px; }
.target-text { font-size: 18px; font-weight: 700; margin: 4px 0; }
.seg-toggle { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 6px; }
.seg-toggle button { min-height: 36px; font-size: 14px; }

.set-row { width: 100%; text-align: left; display: flex; justify-content: space-between; align-items: center; }
.ok { color: var(--up); }

.editor { background: var(--surface); border: 2px solid var(--accent); border-radius: var(--radius); padding: 12px 14px; margin-top: 12px; }
.editor h2 { font-size: 17px; margin: 0 0 8px; }
.editor h2 small { color: var(--muted); font-weight: 400; margin-left: 6px; }
.segment { display: grid; gap: 8px; padding: 6px 0; border-top: 1px dashed var(--line); }
.segment:first-of-type { border-top: none; }
.seg-label { display: flex; justify-content: space-between; align-items: center; color: var(--drop); font-weight: 600; }

.stepper { display: grid; grid-template-columns: 56px 64px 1fr 64px; align-items: center; gap: 6px; }
.stepper label { color: var(--muted); font-size: 14px; }
.stepper input { text-align: center; font-size: 22px; font-weight: 700; }
.stepper button { font-size: 22px; padding: 0; }

.timer { position: fixed; left: 0; right: 0; bottom: calc(60px + env(safe-area-inset-bottom)); display: flex; gap: 8px; align-items: center; justify-content: center; padding: 8px; background: var(--text); color: var(--bg); }
.timer button { min-height: 36px; background: transparent; color: inherit; border-color: currentColor; }
.timer-time { font-size: 26px; font-weight: 800; font-variant-numeric: tabular-nums; min-width: 72px; text-align: center; }
.timer.done { background: var(--up); color: #fff; }

.field { display: grid; gap: 4px; margin: 10px 0; }
.field > span { color: var(--muted); font-size: 14px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.metric-row { display: grid; grid-template-columns: 1fr 70px 70px auto auto; gap: 6px; align-items: center; margin: 6px 0; }
.errors { color: var(--danger); padding-left: 18px; }
.section-title { font-size: 15px; color: var(--muted); margin: 20px 0 8px; }

.chart-card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius); padding: 10px 6px 4px; margin-bottom: 12px; }
.chart-card h2 { font-size: 15px; margin: 0 8px 6px; }
.history-row { display: flex; justify-content: space-between; gap: 8px; padding: 10px 2px; border-bottom: 1px solid var(--line); font-size: 14px; }
```

- [ ] **Step 3: 확인** — `npm test` PASS
- [ ] **Step 4: 커밋** — `feat(tracking-workout): 앱 셸(DB 컨텍스트·탭 라우팅·포맷터·테마)`

---

### Task 11: 설정 — 운동 등록·수정·숨김

**Files:**
- Create: `src/ui/settings/exerciseForm.ts`, `src/ui/components/NumberField.tsx`
- Modify(전체 교체): `src/ui/screens/SettingsScreen.tsx`, `src/ui/screens/ExerciseFormScreen.tsx`
- Test: `src/ui/settings/exerciseForm.test.ts`, `src/ui/screens/Settings.test.tsx`

**Interfaces:**
- Produces: `interface ExerciseFormValues { equipment; name; kind; restSeconds; weight: WeightConfig; cardio: CardioConfig }`, `toFormValues(ex?: Exercise): ExerciseFormValues`, `validateExerciseForm(v): string[]`, `fromFormValues(v): NewExercise`; `NumberField({label, value, onChange, step?})`. SettingsScreen의 백업 섹션은 Task 16에서 추가한다.

- [ ] **Step 1: 실패하는 테스트**

`src/ui/settings/exerciseForm.test.ts`
```ts
import { describe, expect, it } from 'vitest';
import { fromFormValues, toFormValues, validateExerciseForm } from './exerciseForm';

const valid = () => ({ ...toFormValues(), equipment: '레그프레스', name: '하체' });

describe('exerciseForm', () => {
  it('새 운동 기본값', () => {
    expect(toFormValues()).toMatchObject({
      equipment: '', name: '', kind: 'weight', restSeconds: 90,
      weight: { repMin: 8, repMax: 12, targetSets: 3, increment: 2.5, volumeGrowthPct: 3 },
      cardio: { minMinutes: 20, maxMinutes: 30, timeStep: 2 },
    });
  });
  it('정상 값은 오류 없음', () => {
    expect(validateExerciseForm(valid())).toEqual([]);
  });
  it('웨이트 검증', () => {
    const v = valid();
    expect(validateExerciseForm({ ...v, equipment: ' ' })).toContain('기구 이름을 입력하세요');
    expect(validateExerciseForm({ ...v, name: '' })).toContain('운동 종류를 입력하세요');
    expect(validateExerciseForm({ ...v, restSeconds: 700 })).toContain('휴식 시간은 0~600초로 입력하세요');
    expect(validateExerciseForm({ ...v, weight: { ...v.weight, repMin: 0 } })).toContain('최소 횟수는 1 이상의 정수예요');
    expect(validateExerciseForm({ ...v, weight: { ...v.weight, repMax: 6 } })).toContain('최대 횟수는 최소 횟수 이상이어야 해요');
    expect(validateExerciseForm({ ...v, weight: { ...v.weight, targetSets: 0 } })).toContain('세트 수는 1~10이에요');
    expect(validateExerciseForm({ ...v, weight: { ...v.weight, increment: 0 } })).toContain('증량 단위는 0보다 커야 해요');
    expect(validateExerciseForm({ ...v, weight: { ...v.weight, progression: 'volume', volumeGrowthPct: 7 } })).toContain('볼륨 증가율은 2~5%예요');
    expect(validateExerciseForm({ ...v, weight: { ...v.weight, volumeGrowthPct: 7 } })).toEqual([]);
  });
  it('유산소 검증', () => {
    const v = { ...valid(), kind: 'cardio' as const };
    expect(validateExerciseForm(v)).toEqual([]);
    expect(validateExerciseForm({ ...v, cardio: { ...v.cardio, maxMinutes: 10 } })).toContain('최대 시간은 최소 시간 이상이어야 해요');
    expect(validateExerciseForm({ ...v, cardio: { ...v.cardio, minMinutes: 0 } })).toContain('최소 시간은 1분 이상이에요');
    expect(validateExerciseForm({ ...v, cardio: { ...v.cardio, timeStep: 0 } })).toContain('시간 증가 단위는 1분 이상이에요');
    expect(validateExerciseForm({ ...v, cardio: { ...v.cardio, metrics: [] } })).toContain('강도 항목을 하나 이상 추가하세요');
    expect(validateExerciseForm({ ...v, cardio: { ...v.cardio, metrics: [{ key: 'a', label: '', unit: '', step: 1 }], primaryMetric: 'a' } })).toContain('강도 항목 이름을 입력하세요');
    expect(validateExerciseForm({ ...v, cardio: { ...v.cardio, metrics: [{ key: 'a', label: 'A', unit: '', step: 0 }], primaryMetric: 'a' } })).toContain('강도 증가 단위는 0보다 커야 해요');
    expect(validateExerciseForm({ ...v, cardio: { ...v.cardio, primaryMetric: 'zzz' } })).toContain('올릴 강도 항목을 고르세요');
  });
  it('fromFormValues는 종류에 맞는 설정만 담는다', () => {
    const w = fromFormValues(valid());
    expect(w.weight).toBeDefined();
    expect(w.cardio).toBeUndefined();
    const c = fromFormValues({ ...valid(), kind: 'cardio' });
    expect(c.cardio).toBeDefined();
    expect(c.weight).toBeUndefined();
  });
});
```

`src/ui/screens/Settings.test.tsx`
```tsx
import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { addExercise, listExercises } from '../../db/repository';
import { weightExercise } from '../../test/fixtures';
import { renderApp } from '../../test/renderApp';

async function openSettings() {
  const app = renderApp();
  await app.user.click(screen.getByRole('button', { name: '설정' }));
  return app;
}

describe('설정 — 운동 관리', () => {
  it('웨이트 운동을 등록한다', async () => {
    const { user, db } = await openSettings();
    await user.click(screen.getByRole('button', { name: '+ 운동 추가' }));
    await user.type(screen.getByLabelText('기구 이름'), '레그프레스');
    await user.type(screen.getByLabelText('운동 종류'), '하체');
    await user.click(screen.getByRole('button', { name: '저장' }));
    expect(await screen.findByRole('button', { name: /레그프레스 · 하체/ })).toBeInTheDocument();
    expect((await listExercises(db))[0].weight?.repMax).toBe(12);
  });
  it('검증 오류를 보여준다', async () => {
    const { user } = await openSettings();
    await user.click(screen.getByRole('button', { name: '+ 운동 추가' }));
    await user.click(screen.getByRole('button', { name: '저장' }));
    expect(screen.getByRole('alert')).toHaveTextContent('기구 이름을 입력하세요');
  });
  it('중복 등록은 거부한다', async () => {
    const { user, db } = await openSettings();
    await addExercise(db, weightExercise());
    await user.click(screen.getByRole('button', { name: '+ 운동 추가' }));
    await user.type(screen.getByLabelText('기구 이름'), '레그프레스');
    await user.type(screen.getByLabelText('운동 종류'), '하체');
    await user.click(screen.getByRole('button', { name: '저장' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('이미 등록된 운동이에요');
  });
  it('유산소 운동을 강도 항목과 함께 등록한다', async () => {
    const { user, db } = await openSettings();
    await user.click(screen.getByRole('button', { name: '+ 운동 추가' }));
    await user.click(screen.getByRole('button', { name: '유산소' }));
    await user.type(screen.getByLabelText('기구 이름'), '러닝머신');
    await user.type(screen.getByLabelText('운동 종류'), '달리기');
    await user.click(screen.getByRole('button', { name: '+ 강도 항목' }));
    const names = screen.getAllByLabelText('강도 항목 이름');
    await user.type(names[1], '경사');
    await user.click(screen.getByRole('button', { name: '저장' }));
    await screen.findByRole('button', { name: /러닝머신 · 달리기/ });
    const [ex] = await listExercises(db);
    expect(ex.cardio?.metrics.map((m) => m.label)).toEqual(['레벨', '경사']);
    expect(ex.weight).toBeUndefined();
  });
  it('운동을 숨기면 숨긴 운동 목록으로 간다', async () => {
    const { user, db } = await openSettings();
    await addExercise(db, weightExercise());
    await user.click(await screen.findByRole('button', { name: /레그프레스 · 하체/ }));
    await user.click(screen.getByRole('button', { name: '숨기기' }));
    const hidden = await screen.findByRole('region', { name: '숨긴 운동' });
    expect(within(hidden).getByRole('button', { name: /레그프레스 · 하체/ })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 구현**

`src/ui/settings/exerciseForm.ts`
```ts
import { DEFAULT_CARDIO, DEFAULT_REST_SECONDS, DEFAULT_WEIGHT } from '../../core/defaults';
import type { CardioConfig, Exercise, ExerciseKind, WeightConfig } from '../../core/types';
import type { NewExercise } from '../../db/repository';

export interface ExerciseFormValues {
  equipment: string;
  name: string;
  kind: ExerciseKind;
  restSeconds: number;
  weight: WeightConfig;
  cardio: CardioConfig;
}

export function toFormValues(ex?: Exercise): ExerciseFormValues {
  return {
    equipment: ex?.equipment ?? '',
    name: ex?.name ?? '',
    kind: ex?.kind ?? 'weight',
    restSeconds: ex?.restSeconds ?? DEFAULT_REST_SECONDS,
    weight: { ...(ex?.weight ?? DEFAULT_WEIGHT) },
    cardio: {
      ...(ex?.cardio ?? DEFAULT_CARDIO),
      metrics: (ex?.cardio ?? DEFAULT_CARDIO).metrics.map((m) => ({ ...m })),
    },
  };
}

const isInt = (n: number) => Number.isInteger(n);

export function validateExerciseForm(v: ExerciseFormValues): string[] {
  const errors: string[] = [];
  if (!v.equipment.trim()) errors.push('기구 이름을 입력하세요');
  if (!v.name.trim()) errors.push('운동 종류를 입력하세요');
  if (!isInt(v.restSeconds) || v.restSeconds < 0 || v.restSeconds > 600) errors.push('휴식 시간은 0~600초로 입력하세요');

  if (v.kind === 'weight') {
    const w = v.weight;
    if (!isInt(w.repMin) || w.repMin < 1) errors.push('최소 횟수는 1 이상의 정수예요');
    if (!isInt(w.repMax) || w.repMax < w.repMin) errors.push('최대 횟수는 최소 횟수 이상이어야 해요');
    if (!isInt(w.targetSets) || w.targetSets < 1 || w.targetSets > 10) errors.push('세트 수는 1~10이에요');
    if (!(w.increment > 0)) errors.push('증량 단위는 0보다 커야 해요');
    if (w.progression === 'volume' && !(w.volumeGrowthPct >= 2 && w.volumeGrowthPct <= 5)) {
      errors.push('볼륨 증가율은 2~5%예요');
    }
  } else {
    const c = v.cardio;
    if (!isInt(c.minMinutes) || c.minMinutes < 1) errors.push('최소 시간은 1분 이상이에요');
    if (!isInt(c.maxMinutes) || c.maxMinutes < c.minMinutes) errors.push('최대 시간은 최소 시간 이상이어야 해요');
    if (!isInt(c.timeStep) || c.timeStep < 1) errors.push('시간 증가 단위는 1분 이상이에요');
    if (c.metrics.length === 0) errors.push('강도 항목을 하나 이상 추가하세요');
    if (c.metrics.some((m) => !m.label.trim())) errors.push('강도 항목 이름을 입력하세요');
    if (c.metrics.some((m) => !(m.step > 0))) errors.push('강도 증가 단위는 0보다 커야 해요');
    if (c.metrics.length > 0 && !c.metrics.some((m) => m.key === c.primaryMetric)) errors.push('올릴 강도 항목을 고르세요');
  }
  return errors;
}

export function fromFormValues(v: ExerciseFormValues): NewExercise {
  const base = { equipment: v.equipment.trim(), name: v.name.trim(), kind: v.kind, restSeconds: v.restSeconds };
  if (v.kind === 'weight') return { ...base, weight: { ...v.weight } };
  return {
    ...base,
    cardio: { ...v.cardio, metrics: v.cardio.metrics.map((m) => ({ ...m, label: m.label.trim(), unit: m.unit.trim() })) },
  };
}
```

`src/ui/components/NumberField.tsx`
```tsx
import { useId } from 'react';

export function NumberField({
  label, value, onChange, step = 1,
}: { label: string; value: number; onChange: (v: number) => void; step?: number }) {
  const id = useId();
  return (
    <div className="field">
      <span>
        <label htmlFor={id}>{label}</label>
      </span>
      <input
        id={id}
        type="number"
        inputMode="decimal"
        step={step}
        value={Number.isNaN(value) ? '' : value}
        onChange={(e) => onChange(e.target.value === '' ? Number.NaN : Number(e.target.value))}
      />
    </div>
  );
}
```

`src/ui/screens/ExerciseFormScreen.tsx`
```tsx
import { useLiveQuery } from 'dexie-react-hooks';
import { useId, useState } from 'react';
import type { CardioConfig, Exercise, WeightConfig } from '../../core/types';
import { addExercise, newId, updateExercise } from '../../db/repository';
import { NumberField } from '../components/NumberField';
import { ScreenHeader } from '../components/ScreenHeader';
import { useDb } from '../DbContext';
import type { Navigate } from '../routes';
import { fromFormValues, toFormValues, validateExerciseForm, type ExerciseFormValues } from '../settings/exerciseForm';

export function ExerciseFormScreen({ exerciseId, navigate }: { exerciseId?: string; navigate: Navigate }) {
  const db = useDb();
  const loaded = useLiveQuery(
    async () => ({ ex: exerciseId ? await db.exercises.get(exerciseId) : undefined }),
    [db, exerciseId],
  );
  if (!loaded) return <p className="muted">불러오는 중…</p>;
  return <ExerciseForm original={loaded.ex} navigate={navigate} />;
}

function ExerciseForm({ original, navigate }: { original?: Exercise; navigate: Navigate }) {
  const db = useDb();
  const [v, setV] = useState<ExerciseFormValues>(() => toFormValues(original));
  const [errors, setErrors] = useState<string[]>([]);
  const equipmentId = useId();
  const nameId = useId();
  const back = () => navigate({ name: 'settings' });

  const setWeight = (patch: Partial<WeightConfig>) => setV((p) => ({ ...p, weight: { ...p.weight, ...patch } }));
  const setCardio = (patch: Partial<CardioConfig>) => setV((p) => ({ ...p, cardio: { ...p.cardio, ...patch } }));
  const setMetric = (i: number, patch: Partial<CardioConfig['metrics'][number]>) =>
    setCardio({ metrics: v.cardio.metrics.map((m, j) => (j === i ? { ...m, ...patch } : m)) });

  async function save() {
    const errs = validateExerciseForm(v);
    setErrors(errs);
    if (errs.length) return;
    try {
      const data = fromFormValues(v);
      if (original) {
        await updateExercise(db, { ...original, ...data, weight: data.weight, cardio: data.cardio });
      } else {
        await addExercise(db, data);
      }
      back();
    } catch (e) {
      setErrors([(e as Error).message]);
    }
  }

  async function toggleArchive() {
    if (!original) return;
    await updateExercise(db, { ...original, archived: !original.archived });
    back();
  }

  return (
    <>
      <ScreenHeader title={original ? '운동 수정' : '운동 추가'} onBack={back} />

      <div className="field">
        <span><label htmlFor={equipmentId}>기구 이름</label></span>
        <input id={equipmentId} type="text" value={v.equipment} onChange={(e) => setV({ ...v, equipment: e.target.value })} />
      </div>
      <div className="field">
        <span><label htmlFor={nameId}>운동 종류</label></span>
        <input id={nameId} type="text" value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
      </div>

      <div className="seg-toggle" role="group" aria-label="운동 구분">
        {(['weight', 'cardio'] as const).map((k) => (
          <button key={k} type="button" aria-pressed={v.kind === k} disabled={!!original && original.kind !== k}
            onClick={() => setV({ ...v, kind: k })}>
            {k === 'weight' ? '웨이트' : '유산소'}
          </button>
        ))}
      </div>

      {v.kind === 'weight' ? (
        <>
          <div className="seg-toggle" role="group" aria-label="추천 방식">
            <button type="button" aria-pressed={v.weight.progression === 'double'} onClick={() => setWeight({ progression: 'double' })}>
              더블 프로그레션
            </button>
            <button type="button" aria-pressed={v.weight.progression === 'volume'} onClick={() => setWeight({ progression: 'volume' })}>
              볼륨 증가
            </button>
          </div>
          <p className="hint">
            {v.weight.progression === 'double'
              ? '모든 세트에서 최대 횟수를 채우면 무게를 올리고, 아니면 횟수를 1회씩 늘려요.'
              : '지난번 총 볼륨(무게×횟수)보다 증가율만큼 더 하도록 횟수안·무게안을 제시해요.'}
          </p>
          <div className="grid2">
            <NumberField label="최소 횟수" value={v.weight.repMin} onChange={(n) => setWeight({ repMin: n })} />
            <NumberField label="최대 횟수" value={v.weight.repMax} onChange={(n) => setWeight({ repMax: n })} />
            <NumberField label="목표 세트 수" value={v.weight.targetSets} onChange={(n) => setWeight({ targetSets: n })} />
            <NumberField label="증량 단위(kg)" step={0.5} value={v.weight.increment} onChange={(n) => setWeight({ increment: n })} />
            {v.weight.progression === 'volume' && (
              <NumberField label="볼륨 증가율(%)" value={v.weight.volumeGrowthPct} onChange={(n) => setWeight({ volumeGrowthPct: n })} />
            )}
          </div>
        </>
      ) : (
        <>
          <div className="grid2">
            <NumberField label="최소 시간(분)" value={v.cardio.minMinutes} onChange={(n) => setCardio({ minMinutes: n })} />
            <NumberField label="최대 시간(분)" value={v.cardio.maxMinutes} onChange={(n) => setCardio({ maxMinutes: n })} />
            <NumberField label="시간 증가(분)" value={v.cardio.timeStep} onChange={(n) => setCardio({ timeStep: n })} />
          </div>
          <h2 className="section-title">강도 항목 (●: 최대 시간 달성 시 올릴 항목)</h2>
          {v.cardio.metrics.map((m, i) => (
            <div className="metric-row" key={m.key}>
              <input type="text" aria-label="강도 항목 이름" placeholder="예: 속도" value={m.label}
                onChange={(e) => setMetric(i, { label: e.target.value })} />
              <input type="text" aria-label="단위" placeholder="km/h" value={m.unit}
                onChange={(e) => setMetric(i, { unit: e.target.value })} />
              <input type="number" inputMode="decimal" aria-label="증가 단위" value={Number.isNaN(m.step) ? '' : m.step}
                onChange={(e) => setMetric(i, { step: e.target.value === '' ? Number.NaN : Number(e.target.value) })} />
              <input type="radio" name="primary" aria-label="올릴 항목" checked={v.cardio.primaryMetric === m.key}
                onChange={() => setCardio({ primaryMetric: m.key })} />
              <button type="button" aria-label="항목 삭제" onClick={() => setCardio({ metrics: v.cardio.metrics.filter((_, j) => j !== i) })}>
                ×
              </button>
            </div>
          ))}
          <button type="button" onClick={() => setCardio({ metrics: [...v.cardio.metrics, { key: `m-${newId()}`, label: '', unit: '', step: 1 }] })}>
            + 강도 항목
          </button>
        </>
      )}

      <NumberField label="휴식 타이머(초)" value={v.restSeconds} onChange={(n) => setV({ ...v, restSeconds: n })} />

      {errors.length > 0 && (
        <ul className="errors" role="alert">
          {errors.map((e) => <li key={e}>{e}</li>)}
        </ul>
      )}

      <div className="row">
        <button type="button" className="primary" onClick={save}>저장</button>
      </div>
      {original && (
        <div className="row">
          <button type="button" onClick={toggleArchive}>{original.archived ? '다시 보이기' : '숨기기'}</button>
        </div>
      )}
    </>
  );
}
```

`src/ui/screens/SettingsScreen.tsx`
```tsx
import { useLiveQuery } from 'dexie-react-hooks';
import type { Exercise } from '../../core/types';
import { listExercises } from '../../db/repository';
import { ScreenHeader } from '../components/ScreenHeader';
import { useDb } from '../DbContext';
import { exerciseLabel } from '../format';
import type { Navigate } from '../routes';

function ExerciseList({ items, navigate }: { items: Exercise[]; navigate: Navigate }) {
  return (
    <ul className="card-list">
      {items.map((ex) => (
        <li key={ex.id} className="card">
          <button type="button" className="card-main" onClick={() => navigate({ name: 'exerciseForm', exerciseId: ex.id })}>
            <span className="card-title">{exerciseLabel(ex)}</span>
            <span className="card-sub">{ex.kind === 'weight' ? '웨이트' : '유산소'}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

export function SettingsScreen({ navigate }: { navigate: Navigate }) {
  const db = useDb();
  const exercises = useLiveQuery(() => listExercises(db, true), [db]);
  const active = exercises?.filter((e) => !e.archived) ?? [];
  const archived = exercises?.filter((e) => e.archived) ?? [];

  return (
    <>
      <ScreenHeader title="설정" />
      <h2 className="section-title">운동</h2>
      {exercises && active.length === 0 && <p className="muted">등록된 운동이 없어요.</p>}
      <ExerciseList items={active} navigate={navigate} />
      <div className="row">
        <button type="button" className="primary" onClick={() => navigate({ name: 'exerciseForm' })}>+ 운동 추가</button>
      </div>
      {archived.length > 0 && (
        <section aria-label="숨긴 운동">
          <h2 className="section-title">숨긴 운동</h2>
          <ExerciseList items={archived} navigate={navigate} />
        </section>
      )}
      <p className="muted" style={{ marginTop: 24, fontSize: 13 }}>오늘도 +1 · 기록은 이 기기에만 저장돼요.</p>
    </>
  );
}
```

- [ ] **Step 3: 확인** — `npm test` PASS, `npx tsc --noEmit` 통과
- [ ] **Step 4: 커밋** — `feat(tracking-workout): 설정 — 운동 등록·수정·숨김`

---

### Task 12: 오늘 화면

**Files:**
- Create: `src/ui/today/loadToday.ts`, `src/ui/components/InstallBanner.tsx`
- Modify(전체 교체): `src/ui/screens/TodayScreen.tsx`
- Test: `src/ui/today/loadToday.test.ts`, `src/ui/screens/Today.test.tsx`, `src/ui/components/InstallBanner.test.ts`

**Interfaces:**
- Consumes: `listExercises`, `recentExerciseIds`, `getMeta`, `setMeta`, `exerciseHistory`, `recommend`, `badgesFor`, `achievementRate`, `daysBetween`, `addDays`, `BACKUP_WARN_DAYS`
- Produces: `interface TodayItem { exercise; recommendation; recentBadges: Badge[]; doneToday: boolean }`, `interface TodayData { items: TodayItem[]; others: Exercise[]; rate: number | null; needsBackup: boolean }`, `loadToday(db, today): Promise<TodayData>`, `addToToday(db, today, exerciseId)`, `moveItem(db, ids, index, delta)`; `shouldShowInstallHint(ua, standalone): boolean`, `InstallBanner()`

- [ ] **Step 1: 실패하는 테스트**

`src/ui/today/loadToday.test.ts`
```ts
import { describe, expect, it } from 'vitest';
import { addDays, todayLocal } from '../../core/date';
import { markBackedUp } from '../../db/backup';
import { addExercise } from '../../db/repository';
import { seedWeightSession, weightExercise } from '../../test/fixtures';
import { makeTestDb } from '../../test/testDb';
import { addToToday, loadToday, moveItem } from './loadToday';

const today = '2026-10-17';
const t40 = { type: 'double' as const, sets: [{ weight: 40, reps: 12 }] };

describe('loadToday', () => {
  it('최근 7일 기록 운동 + 수동 추가 운동, 나머지는 others', async () => {
    const db = makeTestDb();
    const a = await addExercise(db, weightExercise({ name: 'A' }));
    const b = await addExercise(db, weightExercise({ name: 'B' }));
    const c = await addExercise(db, weightExercise({ name: 'C' }));
    await seedWeightSession(db, a.id, '2026-10-15', [[{ weight: 40, reps: 10 }]]);
    await addToToday(db, today, c.id);
    const data = await loadToday(db, today);
    expect(data.items.map((i) => i.exercise.name)).toEqual(['A', 'C']);
    expect(data.others.map((e) => e.name)).toEqual(['B']);
    expect(data.items[0].recommendation.status).toBe('ok');
    expect(data.items[1].recommendation.status).toBe('first');
    void b;
  });
  it('순서 변경이 저장된다', async () => {
    const db = makeTestDb();
    const a = await addExercise(db, weightExercise({ name: 'A' }));
    const b = await addExercise(db, weightExercise({ name: 'B' }));
    await addToToday(db, today, a.id);
    await addToToday(db, today, b.id);
    await moveItem(db, [a.id, b.id], 1, -1);
    expect((await loadToday(db, today)).items.map((i) => i.exercise.name)).toEqual(['B', 'A']);
  });
  it('오늘 완료 여부·최근 배지·4주 달성률', async () => {
    const db = makeTestDb();
    const a = await addExercise(db, weightExercise());
    await seedWeightSession(db, a.id, '2026-09-01', [[{ weight: 40, reps: 12 }]], t40);
    await seedWeightSession(db, a.id, '2026-10-14', [[{ weight: 40, reps: 12 }]], t40);
    await seedWeightSession(db, a.id, today, [[{ weight: 40, reps: 10 }]], t40);
    const data = await loadToday(db, today);
    expect(data.items[0].doneToday).toBe(true);
    expect(data.items[0].recentBadges).toEqual(['up', 'up', 'down']);
    expect(data.rate).toBeCloseTo(1 / 2);
  });
  it('백업 경고: 데이터가 있고 14일 넘게 백업 안 함', async () => {
    const db = makeTestDb();
    expect((await loadToday(db, today)).needsBackup).toBe(false);
    const a = await addExercise(db, weightExercise());
    await seedWeightSession(db, a.id, '2026-10-14', [[{ weight: 40, reps: 12 }]]);
    expect((await loadToday(db, today)).needsBackup).toBe(true);
    await markBackedUp(db, new Date('2026-10-10T12:00:00Z'));
    expect((await loadToday(db, today)).needsBackup).toBe(false);
  });
  it('todayLocal 기준 날짜 헬퍼가 동작한다', () => {
    expect(addDays(todayLocal(), 0)).toBe(todayLocal());
  });
});
```

`src/ui/components/InstallBanner.test.ts`
```ts
import { expect, it } from 'vitest';
import { shouldShowInstallHint } from './InstallBanner';

it('iOS Safari 탭에서만 설치 안내', () => {
  const iphone = 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1';
  expect(shouldShowInstallHint(iphone, false)).toBe(true);
  expect(shouldShowInstallHint(iphone, true)).toBe(false);
  expect(shouldShowInstallHint('Mozilla/5.0 (Linux; Android 15)', false)).toBe(false);
});
```

`src/ui/screens/Today.test.tsx`
```tsx
import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { addDays, todayLocal } from '../../core/date';
import { addExercise } from '../../db/repository';
import { seedWeightSession, weightExercise } from '../../test/fixtures';
import { renderApp } from '../../test/renderApp';
import { makeTestDb } from '../../test/testDb';

describe('오늘 화면', () => {
  it('최근 운동과 오늘 목표를 보여준다', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, weightExercise());
    await seedWeightSession(db, ex.id, addDays(todayLocal(), -2), [
      [{ weight: 40, reps: 12 }], [{ weight: 40, reps: 10 }], [{ weight: 40, reps: 9 }],
    ]);
    renderApp(db);
    expect(await screen.findByText('레그프레스 · 하체')).toBeInTheDocument();
    expect(screen.getByText('목표 40kg × 12/11/10')).toBeInTheDocument();
  });
  it('운동이 없으면 안내, 오늘 할 운동을 추가할 수 있다', async () => {
    const db = makeTestDb();
    await addExercise(db, weightExercise());
    const { user } = renderApp(db);
    expect(await screen.findByText(/아래에서 오늘 할 운동을 추가하세요/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '+ 오늘 할 운동 추가' }));
    await user.click(screen.getByRole('button', { name: '레그프레스 · 하체 추가' }));
    expect(await screen.findByText('첫 기록 — 시작 값을 입력하세요')).toBeInTheDocument();
  });
  it('순서 편집', async () => {
    const db = makeTestDb();
    const a = await addExercise(db, weightExercise({ name: 'A' }));
    const b = await addExercise(db, weightExercise({ name: 'B' }));
    const d = addDays(todayLocal(), -1);
    await seedWeightSession(db, a.id, d, [[{ weight: 10, reps: 10 }]]);
    await seedWeightSession(db, b.id, d, [[{ weight: 10, reps: 10 }]]);
    const { user } = renderApp(db);
    await screen.findByText('레그프레스 · A');
    await user.click(screen.getByRole('button', { name: '순서 편집' }));
    await user.click(screen.getByRole('button', { name: '레그프레스 · B 위로' }));
    await waitFor(() =>
      expect(screen.getAllByText(/^레그프레스 · [AB]$/).map((el) => el.textContent)).toEqual(['레그프레스 · B', '레그프레스 · A']),
    );
  });
});
```

- [ ] **Step 2: 구현**

`src/ui/today/loadToday.ts`
```ts
import { achievementRate, badgesFor } from '../../core/badge';
import { addDays, daysBetween } from '../../core/date';
import { BACKUP_WARN_DAYS } from '../../core/defaults';
import { recommend } from '../../core/progression/rules';
import type { Badge, Exercise, History, Recommendation } from '../../core/types';
import { exerciseHistory, getMeta, listExercises, recentExerciseIds, setMeta } from '../../db/repository';
import type { WorkoutDB } from '../../db/schema';

export interface TodayItem {
  exercise: Exercise;
  recommendation: Recommendation;
  recentBadges: Badge[];
  doneToday: boolean;
}

export interface TodayData {
  items: TodayItem[];
  others: Exercise[];
  rate: number | null;
  needsBackup: boolean;
}

const extraKey = (today: string) => `todayExtra:${today}`;

export async function loadToday(db: WorkoutDB, today: string): Promise<TodayData> {
  const exercises = await listExercises(db);
  const recent = new Set(await recentExerciseIds(db, today, 7));
  const extra = new Set((await getMeta<string[]>(db, extraKey(today))) ?? []);
  const order = (await getMeta<string[]>(db, 'order')) ?? [];
  const pos = (id: string) => {
    const i = order.indexOf(id);
    return i === -1 ? Number.MAX_SAFE_INTEGER : i;
  };
  const chosen = exercises
    .filter((e) => recent.has(e.id) || extra.has(e.id))
    .sort((a, b) => pos(a.id) - pos(b.id) || a.createdAt - b.createdAt);

  const from = addDays(today, -28);
  const windowBadges: (Badge | null)[] = [];
  const cache = new Map<string, { history: History; badges: (Badge | null)[] }>();
  for (const ex of exercises) {
    const history = await exerciseHistory(db, ex);
    const badges = badgesFor(ex, history);
    history.forEach((h, i) => {
      if (h.date >= from && h.date <= today) windowBadges.push(badges[i]);
    });
    cache.set(ex.id, { history, badges });
  }

  const items = chosen.map((ex) => {
    const { history, badges } = cache.get(ex.id)!;
    return {
      exercise: ex,
      recommendation: recommend(ex, history, today),
      recentBadges: badges.filter((b): b is Badge => b !== null).slice(-5),
      doneToday: history.some((h) => h.date === today),
    };
  });

  const lastBackupAt = await getMeta<string>(db, 'lastBackupAt');
  const hasData = (await db.sessions.count()) > 0;
  const needsBackup = hasData && (!lastBackupAt || daysBetween(lastBackupAt.slice(0, 10), today) > BACKUP_WARN_DAYS);

  return { items, others: exercises.filter((e) => !chosen.includes(e)), rate: achievementRate(windowBadges), needsBackup };
}

export async function addToToday(db: WorkoutDB, today: string, exerciseId: string): Promise<void> {
  const current = (await getMeta<string[]>(db, extraKey(today))) ?? [];
  if (!current.includes(exerciseId)) await setMeta(db, extraKey(today), [...current, exerciseId]);
}

/** 화면에 보이는 순서(ids)에서 index 항목을 delta만큼 옮겨 전역 순서로 저장 */
export async function moveItem(db: WorkoutDB, ids: string[], index: number, delta: -1 | 1): Promise<void> {
  const j = index + delta;
  if (j < 0 || j >= ids.length) return;
  const next = [...ids];
  [next[index], next[j]] = [next[j], next[index]];
  const old = (await getMeta<string[]>(db, 'order')) ?? [];
  await setMeta(db, 'order', [...next, ...old.filter((id) => !next.includes(id))]);
}
```

`src/ui/components/InstallBanner.tsx`
```tsx
export function shouldShowInstallHint(userAgent: string, standalone: boolean): boolean {
  return /iPhone|iPad|iPod/.test(userAgent) && !standalone;
}

export function InstallBanner() {
  const standalone =
    window.matchMedia?.('(display-mode: standalone)')?.matches === true ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true;
  if (!shouldShowInstallHint(navigator.userAgent, standalone)) return null;
  return (
    <div className="banner" role="note">
      <span>Safari 공유 버튼 → <b>홈 화면에 추가</b>로 설치해야 기록이 안전하게 보관돼요.</span>
    </div>
  );
}
```

`src/ui/screens/TodayScreen.tsx`
```tsx
import { useLiveQuery } from 'dexie-react-hooks';
import { useState } from 'react';
import { todayLocal } from '../../core/date';
import { BadgeStrip } from '../components/BadgeStrip';
import { InstallBanner } from '../components/InstallBanner';
import { useDb } from '../DbContext';
import { exerciseLabel, formatLongDate, formatTarget } from '../format';
import type { Navigate } from '../routes';
import { addToToday, loadToday, moveItem, type TodayItem } from '../today/loadToday';

function summary(item: TodayItem): string {
  if (item.doneToday) return '✔ 오늘 기록함';
  const rec = item.recommendation;
  return rec.status === 'first' ? '첫 기록 — 시작 값을 입력하세요' : `목표 ${formatTarget(rec.options[0].target, item.exercise)}`;
}

export function TodayScreen({ navigate }: { navigate: Navigate }) {
  const db = useDb();
  const today = todayLocal();
  const data = useLiveQuery(() => loadToday(db, today), [db, today]);
  const [editing, setEditing] = useState(false);
  const [picking, setPicking] = useState(false);

  if (!data) return <p className="muted">불러오는 중…</p>;
  const ids = data.items.map((i) => i.exercise.id);

  return (
    <>
      <header className="today-head">
        <h1>{formatLongDate(today)}</h1>
        <span className="rate">4주 달성률 {data.rate === null ? '-' : `${Math.round(data.rate * 100)}%`}</span>
      </header>

      <InstallBanner />
      {data.needsBackup && (
        <div className="banner" role="note">
          <span>백업한 지 오래됐어요.</span>
          <button type="button" onClick={() => navigate({ name: 'settings' })}>백업하러 가기</button>
        </div>
      )}

      {data.items.length === 0 && (
        <p className="muted">설정에서 운동을 등록하거나, 아래에서 오늘 할 운동을 추가하세요.</p>
      )}

      <ul className="card-list">
        {data.items.map((item, i) => {
          const label = exerciseLabel(item.exercise);
          return (
            <li key={item.exercise.id} className="card">
              <button type="button" className="card-main" onClick={() => navigate({ name: 'log', exerciseId: item.exercise.id })}>
                <span className="card-title">{label}</span>
                <span className="card-sub">{summary(item)}</span>
                <BadgeStrip badges={item.recentBadges} />
              </button>
              {editing && (
                <div className="order-btns">
                  <button type="button" aria-label={`${label} 위로`} disabled={i === 0} onClick={() => moveItem(db, ids, i, -1)}>↑</button>
                  <button type="button" aria-label={`${label} 아래로`} disabled={i === ids.length - 1} onClick={() => moveItem(db, ids, i, 1)}>↓</button>
                </div>
              )}
            </li>
          );
        })}
      </ul>

      <div className="row">
        <button type="button" onClick={() => setPicking((p) => !p)}>+ 오늘 할 운동 추가</button>
        {data.items.length > 1 && (
          <button type="button" onClick={() => setEditing((e) => !e)}>{editing ? '순서 완료' : '순서 편집'}</button>
        )}
      </div>

      {picking && (
        <ul className="plain-list">
          {data.others.map((ex) => (
            <li key={ex.id}>
              <button
                type="button"
                aria-label={`${exerciseLabel(ex)} 추가`}
                style={{ width: '100%', textAlign: 'left' }}
                onClick={async () => {
                  await addToToday(db, today, ex.id);
                  setPicking(false);
                }}
              >
                {exerciseLabel(ex)}
              </button>
            </li>
          ))}
          {data.others.length === 0 && <li className="muted">추가할 운동이 없어요. 설정에서 운동을 등록하세요.</li>}
        </ul>
      )}
    </>
  );
}
```

- [ ] **Step 3: 확인** — PASS
- [ ] **Step 4: 커밋** — `feat(tracking-workout): 오늘 화면(목표 요약·배지·달성률·순서·백업 경고)`

---

### Task 13: 웨이트 기록 화면 + 휴식 타이머

**Files:**
- Create: `src/ui/components/Stepper.tsx`, `src/ui/timer/useRestTimer.ts`, `src/ui/timer/notify.ts`, `src/ui/timer/RestTimerBar.tsx`, `src/ui/screens/WeightLog.tsx`
- Modify(전체 교체): `src/ui/screens/LogScreen.tsx`
- Test: `src/ui/timer/useRestTimer.test.ts`, `src/ui/screens/WeightLog.test.tsx`

**Interfaces:**
- Produces: `Stepper({label, unit, value, step, min?, integer?, onChange})` — 입력칸 aria-label = `label`, 버튼 aria-label = `${label} 감소`/`${label} 증가`; `interface RestTimer { remaining: number | null; finished: boolean; start(s); add(s); skip() }`, `useRestTimer(onFinish?): RestTimer`, `notifyRestDone()`, `RestTimerBar({timer})`; `WeightLog({exercise, navigate})`; `LogScreen`이 kind로 `WeightLog`/`CardioLog` 분기(CardioLog는 Task 14 — 이 태스크에서는 자리표시 파일 생성)

- [ ] **Step 1: 실패하는 테스트**

`src/ui/timer/useRestTimer.test.ts`
```ts
import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useRestTimer } from './useRestTimer';

describe('useRestTimer', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('카운트다운 후 종료 알림', () => {
    const onFinish = vi.fn();
    const { result } = renderHook(() => useRestTimer(onFinish));
    expect(result.current.remaining).toBeNull();
    act(() => result.current.start(90));
    expect(result.current.remaining).toBe(90);
    act(() => vi.advanceTimersByTime(30_000));
    expect(result.current.remaining).toBe(60);
    act(() => result.current.add(15));
    act(() => vi.advanceTimersByTime(250));
    expect(result.current.remaining).toBe(75);
    act(() => vi.advanceTimersByTime(75_000));
    expect(result.current.remaining).toBeNull();
    expect(result.current.finished).toBe(true);
    expect(onFinish).toHaveBeenCalledTimes(1);
    act(() => result.current.skip());
    expect(result.current.finished).toBe(false);
  });
  it('건너뛰기', () => {
    const onFinish = vi.fn();
    const { result } = renderHook(() => useRestTimer(onFinish));
    act(() => result.current.start(60));
    act(() => result.current.skip());
    act(() => vi.advanceTimersByTime(61_000));
    expect(result.current.remaining).toBeNull();
    expect(onFinish).not.toHaveBeenCalled();
  });
});
```

`src/ui/screens/WeightLog.test.tsx`
```tsx
import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { addDays, todayLocal } from '../../core/date';
import { addExercise, findSession, listWeightSets } from '../../db/repository';
import { seedWeightSession, weightExercise } from '../../test/fixtures';
import { renderApp } from '../../test/renderApp';
import { makeTestDb } from '../../test/testDb';
import { addToToday } from '../today/loadToday';

async function openLog(seed?: (db: ReturnType<typeof makeTestDb>, id: string) => Promise<void>) {
  const db = makeTestDb();
  const ex = await addExercise(db, weightExercise());
  if (seed) await seed(db, ex.id);
  else await seedWeightSession(db, ex.id, addDays(todayLocal(), -2), [
    [{ weight: 40, reps: 12 }], [{ weight: 40, reps: 10 }], [{ weight: 40, reps: 9 }],
  ]);
  const app = renderApp(db);
  await app.user.click(await screen.findByRole('button', { name: /레그프레스 · 하체/ }));
  await screen.findByText(/목표: /);
  return { ...app, ex };
}

const editor = () => screen.getByRole('region', { name: '세트 입력' });

describe('웨이트 기록', () => {
  it('목표가 미리 채워지고, 완료하면 세트 저장·타이머 시작·다음 세트 목표', async () => {
    const { user, db, ex } = await openLog();
    expect(screen.getByText('목표: 40kg × 12/11/10')).toBeInTheDocument();
    expect(within(editor()).getByLabelText('무게')).toHaveValue(40);
    expect(within(editor()).getByLabelText('횟수')).toHaveValue(12);
    await user.click(screen.getByRole('button', { name: '✔ 완료' }));
    expect(await screen.findByRole('button', { name: /세트1 40kg×12/ })).toBeInTheDocument();
    expect(screen.getByRole('timer', { name: '휴식 타이머' })).toBeInTheDocument();
    expect(within(editor()).getByLabelText('횟수')).toHaveValue(11);
    const session = await findSession(db, ex.id, todayLocal());
    expect(session?.target).toEqual({
      type: 'double', sets: [{ weight: 40, reps: 12 }, { weight: 40, reps: 11 }, { weight: 40, reps: 10 }],
    });
  });
  it('세트 중간에 무게를 바꾸면 드롭 구간으로 저장', async () => {
    const { user, db, ex } = await openLog();
    await user.click(screen.getByRole('button', { name: '횟수 감소' }));
    await user.click(screen.getByRole('button', { name: '무게 바꿈' }));
    const weights = within(editor()).getAllByLabelText('무게');
    expect(weights[1]).toHaveValue(37.5);
    expect(within(editor()).getAllByLabelText('횟수')[1]).toHaveValue(1);
    await user.click(screen.getByRole('button', { name: '✔ 완료' }));
    expect(await screen.findByRole('button', { name: /세트1 40kg×11 → 37.5kg×1/ })).toBeInTheDocument();
    const session = await findSession(db, ex.id, todayLocal());
    expect((await listWeightSets(db, session!.id))[0].segments).toHaveLength(2);
  });
  it('완료한 세트를 탭해 수정·삭제', async () => {
    const { user } = await openLog();
    await user.click(screen.getByRole('button', { name: '✔ 완료' }));
    await user.click(await screen.findByRole('button', { name: /세트1 40kg×12/ }));
    await user.click(screen.getByRole('button', { name: '횟수 감소' }));
    await user.click(screen.getByRole('button', { name: '저장' }));
    expect(await screen.findByRole('button', { name: /세트1 40kg×11/ })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /세트1 40kg×11/ }));
    await user.click(screen.getByRole('button', { name: '삭제' }));
    expect(await screen.findByRole('heading', { name: /세트1/ })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /세트1 40kg/ })).not.toBeInTheDocument();
  });
  it('첫 기록이면 안내를 보여준다', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, weightExercise());
    await addToToday(db, todayLocal(), ex.id);
    const app = renderApp(db);
    await app.user.click(await screen.findByRole('button', { name: /레그프레스 · 하체/ }));
    expect(await screen.findByText(/첫 기록이에요/)).toBeInTheDocument();
  });
  it('볼륨 방식은 횟수안/무게안을 고를 수 있다', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, weightExercise({ weight: { progression: 'volume', repMin: 8, repMax: 12, targetSets: 3, increment: 2.5, volumeGrowthPct: 3 } }));
    await seedWeightSession(db, ex.id, addDays(todayLocal(), -1), [[{ weight: 50, reps: 10 }], [{ weight: 50, reps: 10 }], [{ weight: 50, reps: 10 }]]);
    const { user } = renderApp(db);
    await user.click(await screen.findByRole('button', { name: /레그프레스 · 하체/ }));
    expect(await screen.findByText('목표: 50kg × 10/10/11 (볼륨 1545kg)')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '무게로 달성' }));
    expect(screen.getByText('목표: 52.5kg × 10/10/10 (볼륨 1545kg)')).toBeInTheDocument();
    expect(within(editor()).getByLabelText('무게')).toHaveValue(52.5);
  });
});
```

- [ ] **Step 2: 구현**

`src/ui/components/Stepper.tsx`
```tsx
import { useId, useState } from 'react';

const fix = (n: number) => Number(n.toFixed(3));

export function Stepper({
  label, unit, value, step, min = 0, integer = false, onChange,
}: {
  label: string; unit: string; value: number; step: number; min?: number; integer?: boolean;
  onChange: (v: number) => void;
}) {
  const id = useId();
  // 입력 중인 문자열("4", "42.")을 유지하고, 포커스가 빠지면 value로 되돌린다
  const [text, setText] = useState<string | null>(null);
  const clamp = (n: number) => Math.max(min, integer ? Math.round(n) : fix(n));

  return (
    <div className="stepper">
      <label htmlFor={id}>{label}</label>
      <button type="button" aria-label={`${label} 감소`} onClick={() => { setText(null); onChange(clamp(value - step)); }}>−</button>
      <input
        id={id}
        type="number"
        inputMode={integer ? 'numeric' : 'decimal'}
        aria-label={label}
        value={text ?? String(value)}
        onChange={(e) => {
          setText(e.target.value);
          const n = Number(e.target.value);
          if (e.target.value !== '' && Number.isFinite(n)) onChange(clamp(n));
        }}
        onBlur={() => setText(null)}
      />
      <button type="button" aria-label={`${label} 증가`} onClick={() => { setText(null); onChange(clamp(value + step)); }}>
        +<span className="muted" style={{ fontSize: 12, marginLeft: 2 }}>{unit}</span>
      </button>
    </div>
  );
}
```

`src/ui/timer/notify.ts`
```ts
/** 휴식 종료 알림: 진동(안드로이드만) + 짧은 비프음. 실패해도 조용히 넘어간다 */
export function notifyRestDone(): void {
  try {
    navigator.vibrate?.([200, 100, 200]);
  } catch {
    // 진동 미지원
  }
  try {
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.value = 880;
    gain.gain.value = 0.2;
    osc.connect(gain).connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.3);
    osc.onended = () => void ctx.close();
  } catch {
    // 소리 재생 실패는 무시
  }
}
```

`src/ui/timer/useRestTimer.ts`
```ts
import { useEffect, useState } from 'react';
import { notifyRestDone } from './notify';

export interface RestTimer {
  remaining: number | null;
  finished: boolean;
  start: (seconds: number) => void;
  add: (seconds: number) => void;
  skip: () => void;
}

/** 종료 시각 기준으로 계산 — 앱이 백그라운드에 있다 돌아와도 남은 시간이 정확하다 */
export function useRestTimer(onFinish: () => void = notifyRestDone): RestTimer {
  const [endAt, setEndAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [finished, setFinished] = useState(false);

  useEffect(() => {
    if (endAt === null) return;
    const id = setInterval(() => {
      const t = Date.now();
      setNow(t);
      if (t >= endAt) {
        setEndAt(null);
        setFinished(true);
        onFinish();
      }
    }, 250);
    return () => clearInterval(id);
  }, [endAt, onFinish]);

  return {
    remaining: endAt === null ? null : Math.max(0, Math.ceil((endAt - now) / 1000)),
    finished,
    start: (seconds) => {
      const t = Date.now();
      setNow(t);
      setEndAt(t + seconds * 1000);
      setFinished(false);
    },
    add: (seconds) => setEndAt((e) => (e === null ? e : Math.max(Date.now(), e + seconds * 1000))),
    skip: () => {
      setEndAt(null);
      setFinished(false);
    },
  };
}
```

`src/ui/timer/RestTimerBar.tsx`
```tsx
import type { RestTimer } from './useRestTimer';

export function RestTimerBar({ timer }: { timer: RestTimer }) {
  if (timer.finished) {
    return (
      <div className="timer done" role="status">
        <span>휴식 끝! 다음 세트</span>
        <button type="button" onClick={timer.skip}>닫기</button>
      </div>
    );
  }
  if (timer.remaining === null) return null;
  const m = Math.floor(timer.remaining / 60);
  const s = timer.remaining % 60;
  return (
    <div className="timer" role="timer" aria-label="휴식 타이머">
      <span className="timer-time">{m}:{String(s).padStart(2, '0')}</span>
      <button type="button" onClick={() => timer.add(-15)}>−15초</button>
      <button type="button" onClick={() => timer.add(15)}>+15초</button>
      <button type="button" onClick={timer.skip}>건너뛰기</button>
    </div>
  );
}
```

`src/ui/screens/LogScreen.tsx`
```tsx
import { useLiveQuery } from 'dexie-react-hooks';
import { ScreenHeader } from '../components/ScreenHeader';
import { useDb } from '../DbContext';
import type { Navigate } from '../routes';
import { CardioLog } from './CardioLog';
import { WeightLog } from './WeightLog';

export function LogScreen({ exerciseId, navigate }: { exerciseId: string; navigate: Navigate }) {
  const db = useDb();
  const loaded = useLiveQuery(async () => ({ ex: await db.exercises.get(exerciseId) }), [db, exerciseId]);
  if (!loaded) return <p className="muted">불러오는 중…</p>;
  if (!loaded.ex) {
    return (
      <>
        <ScreenHeader title="운동을 찾을 수 없어요" onBack={() => navigate({ name: 'today' })} />
      </>
    );
  }
  return loaded.ex.kind === 'weight'
    ? <WeightLog exercise={loaded.ex} navigate={navigate} />
    : <CardioLog exercise={loaded.ex} navigate={navigate} />;
}
```

`src/ui/screens/CardioLog.tsx` (자리표시 — Task 14에서 교체)
```tsx
import type { Exercise } from '../../core/types';
import { ScreenHeader } from '../components/ScreenHeader';
import { exerciseLabel } from '../format';
import type { Navigate } from '../routes';

export function CardioLog({ exercise, navigate }: { exercise: Exercise; navigate: Navigate }) {
  return <ScreenHeader title={exerciseLabel(exercise)} onBack={() => navigate({ name: 'today' })} />;
}
```

`src/ui/screens/WeightLog.tsx`
```tsx
import { useLiveQuery } from 'dexie-react-hooks';
import { useState } from 'react';
import { todayLocal } from '../../core/date';
import { roundTo } from '../../core/metrics';
import { recommend } from '../../core/progression/rules';
import type { Exercise, OptionId, Segment, TargetOption, WeightTarget } from '../../core/types';
import {
  addWeightSet, deleteWeightSet, findSession, getOrCreateSession, listWeightSets, setSessionTarget,
  updateWeightSet, weightHistory,
} from '../../db/repository';
import { ScreenHeader } from '../components/ScreenHeader';
import { Stepper } from '../components/Stepper';
import { useDb } from '../DbContext';
import { exerciseLabel, formatKg, formatSet, formatWeightTarget } from '../format';
import type { Navigate } from '../routes';
import { shortDate } from '../../core/date';
import { RestTimerBar } from '../timer/RestTimerBar';
import { useRestTimer } from '../timer/useRestTimer';

export function WeightLog({ exercise, navigate }: { exercise: Exercise; navigate: Navigate }) {
  const db = useDb();
  const today = todayLocal();
  const cfg = exercise.weight!;
  const data = useLiveQuery(async () => {
    const history = await weightHistory(db, exercise.id);
    const session = await findSession(db, exercise.id, today);
    const sets = session ? await listWeightSets(db, session.id) : [];
    return { history, session, sets };
  }, [db, exercise.id, today]);
  const timer = useRestTimer();
  const [optionId, setOptionId] = useState<OptionId | null>(null);
  const [draft, setDraft] = useState<Segment[] | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!data) return <p className="muted">불러오는 중…</p>;

  const rec = recommend(exercise, data.history, today);
  const options: TargetOption[] = rec.status === 'ok' ? rec.options : [];
  const savedKey = data.session?.target ? JSON.stringify(data.session.target) : null;
  const selected =
    options.find((o) => o.id === optionId) ?? options.find((o) => JSON.stringify(o.target) === savedKey) ?? options[0];
  const target = selected?.target as WeightTarget | undefined;
  const prev = data.history.filter((h) => h.date < today).at(-1);
  const index = data.sets.length;
  const targetSet = target?.sets[index];

  function prefill(): Segment[] {
    if (targetSet) return [{ weight: targetSet.weight, reps: targetSet.reps }];
    const lastToday = data!.sets.at(-1)?.segments[0];
    if (lastToday) return [{ ...lastToday }];
    const prevSet = prev?.sets[index]?.[0] ?? prev?.sets.at(-1)?.[0];
    if (prevSet) return [{ ...prevSet }];
    return [{ weight: 0, reps: cfg.repMin }];
  }
  const segments = draft ?? prefill();

  const updateSeg = (i: number, patch: Partial<Segment>) =>
    setDraft(segments.map((s, j) => (j === i ? { ...s, ...patch } : s)));
  const addDrop = () => {
    const last = segments[segments.length - 1];
    const goal = targetSet?.reps;
    setDraft([
      ...segments,
      {
        weight: Math.max(0, roundTo(last.weight - cfg.increment, cfg.increment)),
        reps: goal && goal > last.reps ? goal - last.reps : 1,
      },
    ]);
  };
  const resetEditor = () => {
    setDraft(null);
    setEditingId(null);
    setError(null);
  };

  async function complete() {
    try {
      setError(null);
      if (editingId) {
        await updateWeightSet(db, editingId, segments);
        resetEditor();
        return;
      }
      const session = await getOrCreateSession(db, exercise.id, today, target);
      await addWeightSet(db, session.id, segments);
      setDraft(null);
      timer.start(exercise.restSeconds);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function remove() {
    if (!editingId) return;
    await deleteWeightSet(db, editingId);
    resetEditor();
  }

  async function choose(o: TargetOption) {
    setOptionId(o.id);
    setDraft(null);
    if (data!.session) await setSessionTarget(db, data!.session.id, o.target);
  }

  const dropHint = target?.sets.find((s) => s.dropHint);

  return (
    <>
      <ScreenHeader title={exerciseLabel(exercise)} onBack={() => navigate({ name: 'today' })} />

      <section className="target-box" aria-label="오늘 목표">
        {rec.status === 'first' ? (
          <p>첫 기록이에요. 오늘 한 무게와 횟수를 입력하면 다음부터 목표를 추천해 드려요.</p>
        ) : (
          <>
            {rec.note && <p className="note">{rec.note}</p>}
            {options.length > 1 && (
              <div className="seg-toggle" role="group" aria-label="목표 선택">
                {options.map((o) => (
                  <button key={o.id} type="button" aria-pressed={o.id === selected?.id} onClick={() => choose(o)}>
                    {o.label}
                  </button>
                ))}
              </div>
            )}
            {target && <p className="target-text">목표: {formatWeightTarget(target)}</p>}
            {dropHint && (
              <p className="hint">지난번 드롭한 세트는 {formatKg(dropHint.weight)}kg에서 {dropHint.reps}회까지 버틴 뒤 무게를 바꿔 보세요.</p>
            )}
          </>
        )}
        {prev && (
          <p className="muted">지난번: {prev.sets.map(formatSet).join(' / ')} ({shortDate(prev.date)})</p>
        )}
      </section>

      <ol className="set-list">
        {data.sets.map((s, i) => (
          <li key={s.id}>
            <button type="button" className="set-row" onClick={() => { setEditingId(s.id); setDraft(s.segments.map((g) => ({ ...g }))); }}>
              <span>세트{i + 1} {formatSet(s.segments)}</span>
              <span className="ok">✔</span>
            </button>
          </li>
        ))}
      </ol>

      <section className="editor" aria-label="세트 입력">
        <h2>
          {editingId ? '세트 수정' : `세트${index + 1}`}
          {!editingId && targetSet && (
            <small>목표 {formatKg(targetSet.weight)}kg × {targetSet.reps}{targetSet.dropHint ? ' (후 드롭)' : ''}</small>
          )}
        </h2>
        {segments.map((seg, i) => (
          <div className="segment" key={i}>
            {i > 0 && (
              <div className="seg-label">
                <span>↳ 드롭 {i}</span>
                <button type="button" aria-label={`드롭 ${i} 삭제`} onClick={() => setDraft(segments.filter((_, j) => j !== i))}>×</button>
              </div>
            )}
            <Stepper label="무게" unit="kg" value={seg.weight} step={cfg.increment} onChange={(v) => updateSeg(i, { weight: v })} />
            <Stepper label="횟수" unit="회" value={seg.reps} step={1} min={1} integer onChange={(v) => updateSeg(i, { reps: v })} />
          </div>
        ))}
        <div className="row">
          <button type="button" onClick={addDrop}>무게 바꿈</button>
          <button type="button" className="primary" onClick={complete}>{editingId ? '저장' : '✔ 완료'}</button>
        </div>
        {editingId && (
          <div className="row">
            <button type="button" className="danger" onClick={remove}>삭제</button>
            <button type="button" onClick={resetEditor}>취소</button>
          </div>
        )}
        {error && <p role="alert" className="errors">{error}</p>}
      </section>

      <RestTimerBar timer={timer} />
    </>
  );
}
```

- [ ] **Step 3: 확인** — `npm test` PASS, `npx tsc --noEmit` 통과
- [ ] **Step 4: 커밋** — `feat(tracking-workout): 웨이트 세트 기록(드롭 구간·수정·삭제)과 휴식 타이머`

---

### Task 14: 유산소 기록 화면

**Files:**
- Modify(전체 교체): `src/ui/screens/CardioLog.tsx`
- Test: `src/ui/screens/CardioLog.test.tsx`

**Interfaces:**
- Consumes: `cardioHistory`, `findSession`, `getCardioEntry`, `getOrCreateSession`, `saveCardioEntry`, `recommend`, `Stepper`, `formatCardio`

- [ ] **Step 1: 실패하는 테스트**

```tsx
import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { addDays, todayLocal } from '../../core/date';
import { addExercise, findSession, getCardioEntry } from '../../db/repository';
import { cardioExercise, seedCardioSession } from '../../test/fixtures';
import { renderApp } from '../../test/renderApp';
import { makeTestDb } from '../../test/testDb';

describe('유산소 기록', () => {
  it('목표가 미리 채워지고 저장하면 오늘 기록 요약으로 바뀐다', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, cardioExercise());
    await seedCardioSession(db, ex.id, addDays(todayLocal(), -1), { minutes: 30, intensity: { speed: 10, incline: 3 } });
    const { user } = renderApp(db);
    await user.click(await screen.findByRole('button', { name: /러닝머신 · 달리기/ }));
    expect(await screen.findByText('목표: 20분 · 속도 10.5km/h · 경사 3%')).toBeInTheDocument();
    expect(screen.getByLabelText('시간')).toHaveValue(20);
    expect(screen.getByLabelText('속도')).toHaveValue(10.5);
    await user.type(screen.getByLabelText('거리(km)'), '3.6');
    await user.type(screen.getByLabelText('칼로리(kcal)'), '210');
    await user.click(screen.getByRole('button', { name: '저장' }));
    expect(await screen.findByText(/오늘 기록: 20분 · 속도 10.5km\/h · 경사 3% · 3.6km · 210kcal/)).toBeInTheDocument();
    const session = await findSession(db, ex.id, todayLocal());
    expect(session?.target).toEqual({ type: 'cardio', minutes: 20, intensity: { speed: 10.5, incline: 3 } });
    expect(await getCardioEntry(db, session!.id)).toMatchObject({ minutes: 20, distanceKm: 3.6, kcal: 210 });
  });
  it('저장한 기록을 수정한다', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, cardioExercise());
    await seedCardioSession(db, ex.id, todayLocal(), { minutes: 25, intensity: { speed: 9, incline: 1 } });
    const { user } = renderApp(db);
    await user.click(await screen.findByRole('button', { name: /러닝머신 · 달리기/ }));
    await user.click(await screen.findByRole('button', { name: '수정' }));
    expect(screen.getByLabelText('시간')).toHaveValue(25);
    await user.click(screen.getByRole('button', { name: '시간 증가' }));
    await user.click(screen.getByRole('button', { name: '저장' }));
    expect(await screen.findByText(/오늘 기록: 26분/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 구현**

```tsx
import { useLiveQuery } from 'dexie-react-hooks';
import { useId, useState } from 'react';
import { shortDate, todayLocal } from '../../core/date';
import { recommend } from '../../core/progression/rules';
import type { CardioEntry, CardioTarget, Exercise } from '../../core/types';
import { cardioHistory, findSession, getCardioEntry, getOrCreateSession, saveCardioEntry } from '../../db/repository';
import { ScreenHeader } from '../components/ScreenHeader';
import { Stepper } from '../components/Stepper';
import { useDb } from '../DbContext';
import { exerciseLabel, formatCardio } from '../format';
import type { Navigate } from '../routes';

interface Draft {
  minutes: number;
  intensity: Record<string, number>;
  distanceKm: string;
  kcal: string;
}

function extras(v: { distanceKm?: number; kcal?: number }): string {
  return [v.distanceKm != null ? `${v.distanceKm}km` : null, v.kcal != null ? `${v.kcal}kcal` : null]
    .filter(Boolean)
    .map((s) => ` · ${s}`)
    .join('');
}

const fromEntry = (e: CardioEntry): Draft => ({
  minutes: e.minutes,
  intensity: { ...e.intensity },
  distanceKm: e.distanceKm != null ? String(e.distanceKm) : '',
  kcal: e.kcal != null ? String(e.kcal) : '',
});

export function CardioLog({ exercise, navigate }: { exercise: Exercise; navigate: Navigate }) {
  const db = useDb();
  const today = todayLocal();
  const cfg = exercise.cardio!;
  const data = useLiveQuery(async () => {
    const history = await cardioHistory(db, exercise.id);
    const session = await findSession(db, exercise.id, today);
    const entry = session ? await getCardioEntry(db, session.id) : undefined;
    return { history, entry: entry ?? null };
  }, [db, exercise.id, today]);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const distanceId = useId();
  const kcalId = useId();

  if (!data) return <p className="muted">불러오는 중…</p>;

  const rec = recommend(exercise, data.history, today);
  const target = rec.status === 'ok' ? (rec.options[0].target as CardioTarget) : undefined;
  const prev = data.history.filter((h) => h.date < today).at(-1);
  const base: Draft = data.entry
    ? fromEntry(data.entry)
    : {
        minutes: target?.minutes ?? prev?.minutes ?? cfg.minMinutes,
        intensity: Object.fromEntries(cfg.metrics.map((m) => [m.key, target?.intensity[m.key] ?? prev?.intensity[m.key] ?? 0])),
        distanceKm: '',
        kcal: '',
      };
  const v = draft ?? base;
  const showForm = !data.entry || editing;

  async function save() {
    try {
      setError(null);
      const session = await getOrCreateSession(db, exercise.id, today, target);
      await saveCardioEntry(db, session.id, {
        minutes: v.minutes,
        intensity: v.intensity,
        ...(v.distanceKm.trim() !== '' ? { distanceKm: Number(v.distanceKm) } : {}),
        ...(v.kcal.trim() !== '' ? { kcal: Number(v.kcal) } : {}),
      });
      setEditing(false);
      setDraft(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <>
      <ScreenHeader title={exerciseLabel(exercise)} onBack={() => navigate({ name: 'today' })} />

      <section className="target-box" aria-label="오늘 목표">
        {rec.status === 'first' ? (
          <p>첫 기록이에요. 오늘 한 시간과 강도를 입력하면 다음부터 목표를 추천해 드려요.</p>
        ) : (
          <>
            {rec.note && <p className="note">{rec.note}</p>}
            {target && <p className="target-text">목표: {formatCardio(target, cfg.metrics)}</p>}
          </>
        )}
        {prev && (
          <p className="muted">지난번: {formatCardio(prev, cfg.metrics)}{extras(prev)} ({shortDate(prev.date)})</p>
        )}
      </section>

      {!showForm && data.entry && (
        <section className="target-box" aria-label="오늘 기록">
          <p>오늘 기록: {formatCardio(data.entry, cfg.metrics)}{extras(data.entry)}</p>
          <div className="row">
            <button type="button" onClick={() => { setDraft(fromEntry(data.entry!)); setEditing(true); }}>수정</button>
          </div>
        </section>
      )}

      {showForm && (
        <section className="editor" aria-label="유산소 입력">
          <Stepper label="시간" unit="분" value={v.minutes} step={1} min={1} integer onChange={(n) => setDraft({ ...v, minutes: n })} />
          {cfg.metrics.map((m) => (
            <Stepper
              key={m.key}
              label={m.label}
              unit={m.unit}
              value={v.intensity[m.key] ?? 0}
              step={m.step}
              onChange={(n) => setDraft({ ...v, intensity: { ...v.intensity, [m.key]: n } })}
            />
          ))}
          <div className="grid2">
            <div className="field">
              <span><label htmlFor={distanceId}>거리(km)</label></span>
              <input id={distanceId} type="number" inputMode="decimal" value={v.distanceKm}
                onChange={(e) => setDraft({ ...v, distanceKm: e.target.value })} />
            </div>
            <div className="field">
              <span><label htmlFor={kcalId}>칼로리(kcal)</label></span>
              <input id={kcalId} type="number" inputMode="numeric" value={v.kcal}
                onChange={(e) => setDraft({ ...v, kcal: e.target.value })} />
            </div>
          </div>
          <div className="row">
            <button type="button" className="primary" onClick={save}>저장</button>
            {editing && <button type="button" onClick={() => { setEditing(false); setDraft(null); }}>취소</button>}
          </div>
          {error && <p role="alert" className="errors">{error}</p>}
        </section>
      )}
    </>
  );
}
```

- [ ] **Step 3: 확인** — PASS
- [ ] **Step 4: 커밋** — `feat(tracking-workout): 유산소 기록(강도 항목·거리·칼로리)`

---

### Task 15: 기록 목록과 운동 상세 그래프

**Files:**
- Modify(전체 교체): `src/ui/screens/HistoryScreen.tsx`, `src/ui/screens/DetailScreen.tsx`
- Create: `src/ui/charts/WeightCharts.tsx`, `src/ui/charts/CardioCharts.tsx`
- Test: `src/ui/screens/History.test.tsx`

**Interfaces:**
- Consumes: `exerciseHistory`, `badgesFor`, `weightSeries`, `cardioSeries`, `filterByRange`, `type Range`, Recharts
- Produces: `WeightCharts({points})`, `CardioCharts({points, primaryLabel})`

- [ ] **Step 1: 실패하는 테스트**

```tsx
import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { addDays, todayLocal } from '../../core/date';
import { addExercise } from '../../db/repository';
import { seedWeightSession, weightExercise } from '../../test/fixtures';
import { renderApp } from '../../test/renderApp';
import { makeTestDb } from '../../test/testDb';

describe('기록·그래프', () => {
  it('운동 목록 → 상세에서 세션 기록과 배지, 기간 필터', async () => {
    const db = makeTestDb();
    const ex = await addExercise(db, weightExercise());
    const t = { type: 'double' as const, sets: [{ weight: 40, reps: 12 }] };
    await seedWeightSession(db, ex.id, addDays(todayLocal(), -60), [[{ weight: 40, reps: 10 }]]);
    await seedWeightSession(db, ex.id, addDays(todayLocal(), -3), [[{ weight: 40, reps: 12 }, { weight: 30, reps: 4 }]], t);
    const { user } = renderApp(db);
    await user.click(screen.getByRole('button', { name: '기록' }));
    await user.click(await screen.findByRole('button', { name: /레그프레스 · 하체/ }));

    const list = await screen.findByRole('list', { name: '세션 기록' });
    expect(within(list).getAllByRole('listitem')).toHaveLength(1);
    expect(within(list).getByText('40kg×12 → 30kg×4')).toBeInTheDocument();
    expect(within(list).getByTitle('달성')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '전체' }));
    expect(within(screen.getByRole('list', { name: '세션 기록' })).getAllByRole('listitem')).toHaveLength(2);
    expect(screen.getByRole('heading', { name: '추정 1RM (e1RM)' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '볼륨 (목표 무게 / 드롭)' })).toBeInTheDocument();
  });
  it('기록이 없으면 안내', async () => {
    const db = makeTestDb();
    await addExercise(db, weightExercise());
    const { user } = renderApp(db);
    await user.click(screen.getByRole('button', { name: '기록' }));
    await user.click(await screen.findByRole('button', { name: /레그프레스 · 하체/ }));
    expect(await screen.findByText('이 기간에 기록이 없어요.')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 구현**

`src/ui/charts/WeightCharts.tsx`
```tsx
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import type { WeightPoint } from '../../core/series';

interface DotProps {
  cx?: number;
  cy?: number;
  index?: number;
  payload?: WeightPoint;
}

function PrDot({ cx, cy, index, payload }: DotProps) {
  if (cx == null || cy == null) return <g key={index} />;
  const pr = payload?.isPR;
  return <circle key={index} cx={cx} cy={cy} r={pr ? 6 : 3} fill={pr ? 'var(--gold)' : 'var(--accent)'} />;
}

export function WeightCharts({ points }: { points: WeightPoint[] }) {
  return (
    <>
      <section className="chart-card">
        <h2>추정 1RM (e1RM)</h2>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={points}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
            <XAxis dataKey="label" fontSize={12} />
            <YAxis width={40} fontSize={12} domain={['auto', 'auto']} />
            <Tooltip />
            <Line type="monotone" dataKey="e1rm" name="e1RM(kg)" stroke="var(--accent)" strokeWidth={2} dot={(p: DotProps) => <PrDot {...p} />} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
        <p className="hint" style={{ margin: '0 8px' }}>● 큰 금색 점 = 최고 기록 경신</p>
      </section>
      <section className="chart-card">
        <h2>볼륨 (목표 무게 / 드롭)</h2>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={points}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
            <XAxis dataKey="label" fontSize={12} />
            <YAxis width={44} fontSize={12} />
            <Tooltip />
            <Legend />
            <Bar dataKey="mainVolume" stackId="v" name="목표 무게 구간" fill="var(--accent)" isAnimationActive={false} />
            <Bar dataKey="dropVolume" stackId="v" name="드롭 구간" fill="var(--drop)" isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </section>
      <section className="chart-card">
        <h2>목표 달성률 (%)</h2>
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={points}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
            <XAxis dataKey="label" fontSize={12} />
            <YAxis width={36} fontSize={12} domain={[0, 100]} />
            <Tooltip />
            <Line type="monotone" dataKey="achievementPct" name="달성률(%)" stroke="var(--up)" strokeWidth={2} connectNulls isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </section>
    </>
  );
}
```

`src/ui/charts/CardioCharts.tsx`
```tsx
import {
  Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import type { CardioPoint } from '../../core/series';

export function CardioCharts({ points, primaryLabel }: { points: CardioPoint[]; primaryLabel: string }) {
  return (
    <>
      <section className="chart-card">
        <h2>시간과 {primaryLabel}</h2>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={points}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
            <XAxis dataKey="label" fontSize={12} />
            <YAxis yAxisId="min" width={36} fontSize={12} />
            <YAxis yAxisId="int" orientation="right" width={36} fontSize={12} />
            <Tooltip />
            <Legend />
            <Line yAxisId="min" type="monotone" dataKey="minutes" name="시간(분)" stroke="var(--accent)" strokeWidth={2} isAnimationActive={false} />
            <Line yAxisId="int" type="stepAfter" dataKey="primary" name={primaryLabel} stroke="var(--drop)" strokeWidth={2} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </section>
      <section className="chart-card">
        <h2>거리·칼로리</h2>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={points}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
            <XAxis dataKey="label" fontSize={12} />
            <YAxis yAxisId="km" width={36} fontSize={12} />
            <YAxis yAxisId="kcal" orientation="right" width={40} fontSize={12} />
            <Tooltip />
            <Legend />
            <Bar yAxisId="km" dataKey="distanceKm" name="거리(km)" fill="var(--accent)" isAnimationActive={false} />
            <Bar yAxisId="kcal" dataKey="kcal" name="칼로리(kcal)" fill="var(--drop)" isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </section>
    </>
  );
}
```

`src/ui/screens/HistoryScreen.tsx`
```tsx
import { useLiveQuery } from 'dexie-react-hooks';
import { badgesFor } from '../../core/badge';
import { shortDate } from '../../core/date';
import { exerciseHistory, listExercises } from '../../db/repository';
import { BadgeStrip } from '../components/BadgeStrip';
import { ScreenHeader } from '../components/ScreenHeader';
import { useDb } from '../DbContext';
import { exerciseLabel } from '../format';
import type { Navigate } from '../routes';
import type { Badge } from '../../core/types';

export function HistoryScreen({ navigate }: { navigate: Navigate }) {
  const db = useDb();
  const rows = useLiveQuery(async () => {
    const exercises = await listExercises(db);
    return Promise.all(
      exercises.map(async (ex) => {
        const history = await exerciseHistory(db, ex);
        const badges = badgesFor(ex, history).filter((b): b is Badge => b !== null).slice(-5);
        return { ex, last: history.at(-1)?.date ?? null, count: history.length, badges };
      }),
    );
  }, [db]);

  return (
    <>
      <ScreenHeader title="기록" />
      {!rows && <p className="muted">불러오는 중…</p>}
      {rows && rows.length === 0 && <p className="muted">등록된 운동이 없어요.</p>}
      <ul className="card-list">
        {rows?.map(({ ex, last, count, badges }) => (
          <li key={ex.id} className="card">
            <button type="button" className="card-main" onClick={() => navigate({ name: 'detail', exerciseId: ex.id })}>
              <span className="card-title">{exerciseLabel(ex)}</span>
              <span className="card-sub">{last ? `최근 ${shortDate(last)} · 총 ${count}회` : '기록 없음'}</span>
              <BadgeStrip badges={badges} />
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}
```

`src/ui/screens/DetailScreen.tsx`
```tsx
import { useLiveQuery } from 'dexie-react-hooks';
import { useState } from 'react';
import { badgesFor } from '../../core/badge';
import { shortDate, todayLocal } from '../../core/date';
import { cardioSeries, filterByRange, weightSeries, type Range } from '../../core/series';
import type { CardioHistoryItem, Exercise, History, WeightHistoryItem } from '../../core/types';
import { exerciseHistory } from '../../db/repository';
import { CardioCharts } from '../charts/CardioCharts';
import { WeightCharts } from '../charts/WeightCharts';
import { ScreenHeader } from '../components/ScreenHeader';
import { useDb } from '../DbContext';
import { BADGE_LABEL, BADGE_SYMBOL, exerciseLabel, formatCardio, formatSet } from '../format';
import type { Navigate } from '../routes';

const RANGES: { id: Range; label: string }[] = [
  { id: '4w', label: '4주' },
  { id: '3m', label: '3개월' },
  { id: 'all', label: '전체' },
];

function describe(ex: Exercise, item: History[number]): string {
  if (ex.kind === 'weight') return (item as WeightHistoryItem).sets.map(formatSet).join(' / ');
  const c = item as CardioHistoryItem;
  const extra = [c.distanceKm != null ? `${c.distanceKm}km` : null, c.kcal != null ? `${c.kcal}kcal` : null].filter(Boolean);
  return [formatCardio(c, ex.cardio!.metrics), ...extra].join(' · ');
}

export function DetailScreen({ exerciseId, navigate }: { exerciseId: string; navigate: Navigate }) {
  const db = useDb();
  const today = todayLocal();
  const [range, setRange] = useState<Range>('4w');
  const data = useLiveQuery(async () => {
    const ex = await db.exercises.get(exerciseId);
    return ex ? { ex, history: await exerciseHistory(db, ex) } : { ex: null, history: [] as History };
  }, [db, exerciseId]);

  if (!data) return <p className="muted">불러오는 중…</p>;
  const back = () => navigate({ name: 'history' });
  if (!data.ex) return <ScreenHeader title="운동을 찾을 수 없어요" onBack={back} />;
  const ex = data.ex;

  const badges = badgesFor(ex, data.history);
  const rows = data.history
    .map((item, i) => ({ item, badge: badges[i] }))
    .filter(({ item }) => filterByRange([item], range, today).length > 0)
    .reverse();

  return (
    <>
      <ScreenHeader title={exerciseLabel(ex)} onBack={back} />
      <div className="seg-toggle" role="group" aria-label="기간">
        {RANGES.map((r) => (
          <button key={r.id} type="button" aria-pressed={range === r.id} onClick={() => setRange(r.id)}>{r.label}</button>
        ))}
      </div>

      {rows.length === 0 ? (
        <p className="muted">이 기간에 기록이 없어요.</p>
      ) : ex.kind === 'weight' ? (
        <WeightCharts points={filterByRange(weightSeries(data.history as WeightHistoryItem[]), range, today)} />
      ) : (
        <CardioCharts
          points={filterByRange(cardioSeries(data.history as CardioHistoryItem[], ex.cardio!.primaryMetric), range, today)}
          primaryLabel={ex.cardio!.metrics.find((m) => m.key === ex.cardio!.primaryMetric)?.label ?? '강도'}
        />
      )}

      <ul className="plain-list" aria-label="세션 기록" style={{ gap: 0 }}>
        {rows.map(({ item, badge }) => (
          <li key={item.date} className="history-row">
            <span>{shortDate(item.date)}</span>
            <span style={{ flex: 1 }}>{describe(ex, item)}</span>
            {badge && <span className={`badge badge-${badge}`} title={BADGE_LABEL[badge]}>{BADGE_SYMBOL[badge]}</span>}
          </li>
        ))}
      </ul>
    </>
  );
}
```

- [ ] **Step 3: 확인** — `npm test` PASS, `npx tsc --noEmit` 통과
- [ ] **Step 4: 커밋** — `feat(tracking-workout): 기록 목록과 운동별 그래프(e1RM·볼륨·달성률·유산소)`

---

### Task 16: 백업 UI와 PWA 배포 설정

**Files:**
- Create: `src/ui/backupFile.ts`, `public/icon.svg`, `public/robots.txt`, `README.md`
- Modify: `src/ui/screens/SettingsScreen.tsx`(백업 섹션 추가), `vite.config.ts`(PWA), `index.html`(아이콘 링크)
- Test: `src/ui/screens/Backup.test.tsx`

**Interfaces:**
- Consumes: `exportBackup`, `parseBackup`, `restoreBackup`, `markBackedUp`, `backupFileName`, `getMeta`
- Produces: `deliverBackup(file: BackupFile, now?: Date): Promise<'shared' | 'downloaded' | 'cancelled'>`

- [ ] **Step 1: 실패하는 테스트**

```tsx
import { screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { exportBackup } from '../../db/backup';
import { addExercise, getMeta, listExercises } from '../../db/repository';
import { weightExercise } from '../../test/fixtures';
import { renderApp } from '../../test/renderApp';
import { makeTestDb } from '../../test/testDb';

const deliver = vi.hoisted(() => vi.fn(async () => 'downloaded' as const));
vi.mock('../backupFile', () => ({ deliverBackup: deliver }));

afterEach(() => {
  deliver.mockClear();
  vi.restoreAllMocks();
});

describe('백업 UI', () => {
  it('내보내기 후 마지막 백업 시각을 기록한다', async () => {
    const db = makeTestDb();
    await addExercise(db, weightExercise());
    const { user } = renderApp(db);
    await user.click(screen.getByRole('button', { name: '설정' }));
    await user.click(await screen.findByRole('button', { name: '백업 내보내기' }));
    expect(deliver).toHaveBeenCalledTimes(1);
    expect(await screen.findByText(/백업 파일을 저장했어요/)).toBeInTheDocument();
    expect(await getMeta(db, 'lastBackupAt')).toEqual(expect.any(String));
  });
  it('가져오기: 확인 후 안전 백업을 만들고 교체한다', async () => {
    const src = makeTestDb();
    await addExercise(src, weightExercise({ name: '백업된 운동' }));
    const json = JSON.stringify(await exportBackup(src));

    const db = makeTestDb();
    await addExercise(db, weightExercise({ name: '기존 운동' }));
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { user } = renderApp(db);
    await user.click(screen.getByRole('button', { name: '설정' }));
    await user.upload(await screen.findByLabelText('백업 가져오기'), new File([json], 'b.json', { type: 'application/json' }));
    expect(await screen.findByText('백업을 복원했어요.')).toBeInTheDocument();
    expect(deliver).toHaveBeenCalledTimes(1);
    expect((await listExercises(db)).map((e) => e.name)).toEqual(['백업된 운동']);
  });
  it('잘못된 파일이면 오류를 보여주고 데이터를 유지한다', async () => {
    const db = makeTestDb();
    await addExercise(db, weightExercise());
    const { user } = renderApp(db);
    await user.click(screen.getByRole('button', { name: '설정' }));
    await user.upload(await screen.findByLabelText('백업 가져오기'), new File(['nope'], 'b.json', { type: 'application/json' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('JSON 형식의 백업 파일이 아니에요');
    expect(await listExercises(db)).toHaveLength(1);
  });
});
```

- [ ] **Step 2: 구현**

`src/ui/backupFile.ts`
```ts
import { backupFileName, type BackupFile } from '../db/backup';

/** 공유 시트(모바일)로 보내고, 안 되면 파일 다운로드로 대체한다 */
export async function deliverBackup(file: BackupFile, now: Date = new Date()): Promise<'shared' | 'downloaded' | 'cancelled'> {
  const name = backupFileName(now);
  const blob = new Blob([JSON.stringify(file)], { type: 'application/json' });
  const shareFile = new File([blob], name, { type: 'application/json' });
  if (navigator.canShare?.({ files: [shareFile] })) {
    try {
      await navigator.share({ files: [shareFile], title: name });
      return 'shared';
    } catch (e) {
      if ((e as Error).name === 'AbortError') return 'cancelled';
      // 사용자 제스처가 끊긴 경우 등 — 다운로드로 대체
    }
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return 'downloaded';
}
```

`SettingsScreen.tsx` — 백업 섹션 추가 (파일 전체):
```tsx
import { useLiveQuery } from 'dexie-react-hooks';
import { useId, useState } from 'react';
import type { Exercise } from '../../core/types';
import { exportBackup, markBackedUp, parseBackup, restoreBackup } from '../../db/backup';
import { getMeta, listExercises } from '../../db/repository';
import { deliverBackup } from '../backupFile';
import { ScreenHeader } from '../components/ScreenHeader';
import { useDb } from '../DbContext';
import { exerciseLabel } from '../format';
import type { Navigate } from '../routes';

function ExerciseList({ items, navigate }: { items: Exercise[]; navigate: Navigate }) {
  return (
    <ul className="card-list">
      {items.map((ex) => (
        <li key={ex.id} className="card">
          <button type="button" className="card-main" onClick={() => navigate({ name: 'exerciseForm', exerciseId: ex.id })}>
            <span className="card-title">{exerciseLabel(ex)}</span>
            <span className="card-sub">{ex.kind === 'weight' ? '웨이트' : '유산소'}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export function SettingsScreen({ navigate }: { navigate: Navigate }) {
  const db = useDb();
  const exercises = useLiveQuery(() => listExercises(db, true), [db]);
  const lastBackupAt = useLiveQuery(async () => ({ v: await getMeta<string>(db, 'lastBackupAt') }), [db]);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const importId = useId();
  const active = exercises?.filter((e) => !e.archived) ?? [];
  const archived = exercises?.filter((e) => e.archived) ?? [];

  async function doExport() {
    setError(null);
    const now = new Date();
    const result = await deliverBackup(await exportBackup(db, now), now);
    if (result === 'cancelled') {
      setMessage('백업을 취소했어요.');
      return;
    }
    await markBackedUp(db, now);
    setMessage('백업 파일을 저장했어요. 클라우드 드라이브나 메신저 "나에게 보내기"에 보관하세요.');
  }

  async function doImport(file: File | undefined) {
    if (!file) return;
    setError(null);
    setMessage(null);
    try {
      const backup = parseBackup(await file.text());
      if (!window.confirm('지금 기록을 모두 지우고 백업 내용으로 바꿉니다. 계속할까요?')) return;
      const safety = await deliverBackup(await exportBackup(db));
      if (safety === 'cancelled') {
        setMessage('현재 기록을 먼저 백업해야 복원할 수 있어요. 복원을 취소했어요.');
        return;
      }
      await restoreBackup(db, backup);
      setMessage('백업을 복원했어요.');
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <>
      <ScreenHeader title="설정" />
      <h2 className="section-title">운동</h2>
      {exercises && active.length === 0 && <p className="muted">등록된 운동이 없어요.</p>}
      <ExerciseList items={active} navigate={navigate} />
      <div className="row">
        <button type="button" className="primary" onClick={() => navigate({ name: 'exerciseForm' })}>+ 운동 추가</button>
      </div>
      {archived.length > 0 && (
        <section aria-label="숨긴 운동">
          <h2 className="section-title">숨긴 운동</h2>
          <ExerciseList items={archived} navigate={navigate} />
        </section>
      )}

      <h2 className="section-title">백업</h2>
      <p className="muted">
        마지막 백업: {lastBackupAt?.v ? formatDateTime(lastBackupAt.v) : '없음'} · 폰을 바꾸거나 앱을 지우기 전에 꼭 백업하세요.
      </p>
      <div className="row">
        <button type="button" onClick={doExport}>백업 내보내기</button>
        <label htmlFor={importId} className="button-like" style={{ flex: 1 }}>
          <span style={{ display: 'flex', minHeight: 44, alignItems: 'center', justifyContent: 'center', border: '1px solid var(--line)', borderRadius: 10, background: 'var(--surface)' }}>
            백업 가져오기
          </span>
        </label>
        <input
          id={importId}
          type="file"
          accept="application/json,.json"
          aria-label="백업 가져오기"
          style={{ display: 'none' }}
          onChange={(e) => {
            void doImport(e.target.files?.[0]);
            e.target.value = '';
          }}
        />
      </div>
      {message && <p role="status">{message}</p>}
      {error && <p role="alert" className="errors">{error}</p>}

      <p className="muted" style={{ marginTop: 24, fontSize: 13 }}>오늘도 +1 · 기록은 이 기기에만 저장돼요.</p>
    </>
  );
}
```

PWA 설정:
```bash
npm install -D vite-plugin-pwa@^2.0.0 @vite-pwa/assets-generator@^2.0.0
```

`vite.config.ts`
```ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig(({ mode }) => ({
  base: './',
  plugins: [
    react(),
    ...(mode === 'test'
      ? []
      : [
          VitePWA({
            registerType: 'autoUpdate',
            includeAssets: ['favicon.ico', 'apple-touch-icon-180x180.png', 'icon.svg'],
            manifest: {
              name: '오늘도 +1',
              short_name: '+1',
              description: '점진적 과부하 운동 기록',
              lang: 'ko',
              theme_color: '#FF6B35',
              background_color: '#f6f6f4',
              display: 'standalone',
              orientation: 'portrait',
              start_url: '.',
              scope: '.',
              icons: [
                { src: 'pwa-64x64.png', sizes: '64x64', type: 'image/png' },
                { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
                { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png' },
                { src: 'maskable-icon-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
              ],
            },
            workbox: { globPatterns: ['**/*.{js,css,html,svg,png,ico}'] },
          }),
        ]),
  ],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
}));
```

`public/icon.svg`
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="96" fill="#FF6B35"/>
  <rect x="96" y="226" width="320" height="60" rx="14" fill="#fff"/>
  <rect x="70" y="170" width="56" height="172" rx="16" fill="#fff"/>
  <rect x="386" y="170" width="56" height="172" rx="16" fill="#fff"/>
  <text x="256" y="150" text-anchor="middle" font-family="Arial, sans-serif" font-weight="900" font-size="120" fill="#fff">+1</text>
</svg>
```

`public/robots.txt`
```
User-agent: *
Disallow: /
```

`index.html` head에 추가:
```html
    <link rel="icon" href="favicon.ico" sizes="48x48" />
    <link rel="icon" href="icon.svg" type="image/svg+xml" />
    <link rel="apple-touch-icon" href="apple-touch-icon-180x180.png" />
```

아이콘 생성: `npx pwa-assets-generator --preset minimal-2023 public/icon.svg`

`README.md`
```markdown
# 오늘도 +1 (TrackingWorkout)

부부용 점진적 과부하 운동 기록 PWA. 웨이트(세트·드롭 구간)와 유산소(시간·강도·거리·칼로리)를 기록하고,
운동별 오늘 목표를 추천받고, 그래프로 과부하 실천 여부를 확인한다.

```bash
npm install
npm run dev      # 개발 서버 (같은 Wi-Fi 폰에서 Network 주소로 접속)
npm test
npm run build    # dist/ 정적 파일(PWA)
npm run deploy   # 테스트 → 빌드 → Cloudflare Pages(tracking-workout)
```

- 설계: `docs/superpowers/specs/2026-10-17-tracking-workout-design.md`
- 계획: `docs/superpowers/plans/2026-10-17-tracking-workout.md`
- 기록은 각 기기의 IndexedDB에만 저장된다. 설정 → 백업 내보내기로 JSON 파일을 보관할 것.
- 아이폰은 Safari → 공유 → 홈 화면에 추가로 설치해야 저장소가 안정적으로 유지된다.
```

- [ ] **Step 3: 확인** — `npm test` 전체 PASS, `npm run build` 성공(dist에 `manifest.webmanifest`, `sw.js`)
- [ ] **Step 4: 커밋** — `feat(tracking-workout): 백업 내보내기·가져오기 UI와 PWA 설정`

---

### Task 17: 최종 검증

- [ ] `npm test` 전체 통과 수 기록
- [ ] `npm run build` 성공
- [ ] `npm run preview` 후 브라우저(모바일 폭)에서 수동 확인: 운동 등록 → 오늘 추가 → 세트 기록(드롭 포함) → 타이머 → 그래프 → 백업
- [ ] 배포(`npm run deploy`)는 외부 공개 작업이므로 **사용자 확인 후** 실행
```

---

## Self-Review 결과

- 스펙 커버리지: 2장 결정(PWA·Dexie·Recharts·세트/구간·방식 선택·강도 정의·거리/칼로리) → Task 1·8·10·11·13·14·15. 3장 데이터 모델 → Task 2·8. 4.1~4.6 → Task 2~7. 5장 화면 1~4 + 휴식 타이머 → Task 11~16. 7장 persist/설치 안내/백업 경고/복원 전 안전 백업/입력 검증 → Task 8·9·10(main.tsx)·12·16. 8장 테스트 → 각 태스크. 9장 범위 밖 항목은 계획에 없음.
- 의도적 변경 2건(순서 편집 ↑↓, 세트 탭 수정)은 Global Constraints에 명시.
- 타입 일관성: `WeightHistoryItem.sets: SetSegments[]`, `TargetOption.id: OptionId`, `recommend(ex, history, today)`, `getOrCreateSession(db, exerciseId, date, target?)` — 모든 태스크에서 같은 시그니처 사용.
