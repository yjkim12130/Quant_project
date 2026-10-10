# 셈셈 병아리 (계산력 게임) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 7살 어린이가 덧셈·뺄셈·구구단·나눗셈을 듀오링고처럼 단계 맵 + 레슨으로 훈련하는 PWA 웹앱을 만든다.

**Architecture:** 게임 규칙(문제 생성·점수·스트릭·저장·레슨 진행)은 React를 모르는 순수 TS 모듈(`src/core`)로 두고 Vitest로 촘촘히 검증한다. Zustand 바닐라 스토어(`src/state`)가 core 함수를 호출해 앱 상태를 바꾸고 localStorage에 저장한다. 화면(`src/ui`)은 스토어를 읽어 그리기만 한다.

**Tech Stack:** React 18+ / TypeScript / Vite / Zustand / Framer Motion / vite-plugin-pwa / Vitest + Testing Library (jsdom)

**Spec:** `docs/superpowers/specs/2026-10-10-calculator-game-design.md`

## Global Constraints

- 모든 명령은 `C:/Users/yjkim/Desktop/Claude_project/calculator_game` 에서 실행한다.
- 저장소 루트가 홈 디렉터리(`C:/Users/yjkim`)인 모노레포다. **`git add`는 항상 이 프로젝트 안의 경로만** 지정한다. 루트 `.gitignore`에 `node_modules` 규칙이 없으므로 Task 1의 `.gitignore`를 가장 먼저 만든다.
- 브랜치: `feature/calculator-game-v1` (이미 생성됨). 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- 앱 이름: **셈셈 병아리**. UI 문구는 한국어.
- 색: 초록 `#58CC02`, 하늘 `#1CB0F6`, 노랑 `#FFC800`, 빨강 `#FF4B4B`, 글자 `#3C3C3C`, 연회색 배경 `#F7F7F7`.
- 아이가 누르는 요소(버튼·보기·키패드·노드·아바타)는 높이 56px 이상. 최대 너비 480px 가운데 정렬.
- 레슨 = 10문제, 하트 5개, 통과 = 첫 시도 정답률 ≥ 70% 그리고 하트 > 0, 왕관 최대 3.
- XP: 정답 +10, 레슨 완료 +20, 무실수 +10. 레벨 n→n+1 누적 XP = `50·n·(n+1)`.
- localStorage 키 `calculator_game:v1`, `schemaVersion: 1`.
- 테스트 파일은 대상 파일 옆에 `*.test.ts(x)` 로 둔다. vitest 전역(globals)은 쓰지 않고 `import { describe, it, expect } from 'vitest'`.

## File Map

```
calculator_game/
  .gitignore  package.json  tsconfig.json  vite.config.ts  index.html  README.md
  public/icon.svg (+ 생성된 PNG 아이콘들)
  src/
    main.tsx  App.tsx  App.test.tsx
    core/
      types.ts        공용 타입
      random.ts       시드 랜덤 (mulberry32, randInt, pick, shuffle)
      stages.ts       유닛 6개·단계 24개 정의
      generator.ts    문제·보기·레슨 생성
      streak.ts       날짜 문자열, ISO 주, 스트릭
      scoring.ts      XP·레벨·통과·잠금
      progress.ts     레슨 결과를 프로필에 반영, 시작 단계 지정
      storage.ts      localStorage 읽기/쓰기/검증
      lesson.ts       레슨 진행 상태기계 (답 제출·복습·하트)
      parentLock.ts   부모 잠금 문제
    state/
      store.ts        Zustand 바닐라 스토어
      GameContext.tsx React 연결 (Provider, useGame)
    audio/sfx.ts      Web Audio 효과음, 진동
    ui/
      theme.css
      components/     Button3D, ProgressBar, Hearts, Mascot, Keypad, FeedbackSheet,
                      TopBar, QuestionView, Confetti
      screens/        ProfileSelect, StageMap, Lesson, Result, Parent
    test/
      setup.ts  memoryKV.ts  renderApp.tsx
```

---

### Task 1: 프로젝트 골격 + 테마 CSS

**Files:**
- Create: `.gitignore`, `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `src/main.tsx`, `src/App.tsx`, `src/App.test.tsx`, `src/test/setup.ts`, `src/ui/theme.css`

**Interfaces:**
- Produces: `App` 컴포넌트(`src/App.tsx`, named export), 전역 CSS 클래스(아래 theme.css 전체 — 이후 태스크의 컴포넌트가 이 클래스명을 사용).

- [ ] **Step 1: `.gitignore` 작성 (가장 먼저)**

```gitignore
node_modules/
dist/
dev-dist/
*.local
coverage/
```

- [ ] **Step 2: `package.json` 작성**

```json
{
  "name": "calculator-game",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite --host",
    "build": "tsc && vite build",
    "preview": "vite preview --host",
    "test": "vitest run",
    "test:watch": "vitest"
  }
}
```

- [ ] **Step 3: 의존성 설치**

```bash
npm install react react-dom zustand framer-motion
npm install -D vite @vitejs/plugin-react typescript @types/react @types/react-dom vitest jsdom @testing-library/react @testing-library/dom @testing-library/user-event @testing-library/jest-dom
```

Expected: `added N packages`, 에러 없음.

- [ ] **Step 4: `tsconfig.json`, `vite.config.ts`, `index.html` 작성**

`tsconfig.json`:
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

`vite.config.ts`:
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

`index.html`:
```html
<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
    <meta name="theme-color" content="#58CC02" />
    <title>셈셈 병아리</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Jua&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: 테스트 셋업과 실패하는 스모크 테스트 작성**

`src/test/setup.ts`:
```ts
import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

afterEach(() => {
  cleanup();
  localStorage.clear();
});
```

`src/App.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { App } from './App';

describe('App', () => {
  it('앱 제목을 보여준다', () => {
    render(<App />);
    expect(screen.getByRole('heading', { name: '셈셈 병아리' })).toBeInTheDocument();
  });
});
```

- [ ] **Step 6: 테스트 실패 확인**

Run: `npx vitest run src/App.test.tsx`
Expected: FAIL — `Failed to resolve import "./App"`

- [ ] **Step 7: `App.tsx`, `main.tsx`, `theme.css` 작성**

`src/App.tsx` (Task 10에서 교체됨):
```tsx
export function App() {
  return (
    <div className="app">
      <h1 className="title">셈셈 병아리</h1>
    </div>
  );
}
```

`src/main.tsx` (Task 10에서 교체됨):
```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import './ui/theme.css';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

`src/ui/theme.css` (전체 — 이후 태스크는 이 클래스명을 사용):
```css
/* ---------- 토큰 ---------- */
:root {
  --green: #58cc02; --green-dark: #46a302; --green-soft: #d7ffb8;
  --blue: #1cb0f6; --blue-dark: #1899d6; --blue-soft: #ddf4ff;
  --yellow: #ffc800; --yellow-dark: #e5a400;
  --red: #ff4b4b; --red-dark: #ea2b2b; --red-soft: #ffdfe0;
  --orange: #ff9600;
  --gray: #e5e5e5; --gray-dark: #afafaf;
  --bg: #ffffff; --bg-soft: #f7f7f7;
  --text: #3c3c3c; --text-soft: #777777;
  --radius: 16px;
  --font-display: 'Jua', system-ui, sans-serif;
}
* { box-sizing: border-box; }
html, body, #root { min-height: 100%; margin: 0; }
body {
  background: var(--bg-soft); color: var(--text); font-size: 16px;
  font-family: system-ui, -apple-system, 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
  -webkit-tap-highlight-color: transparent; user-select: none; -webkit-user-select: none;
}
input, select { font: inherit; user-select: text; -webkit-user-select: text; }
button { font: inherit; }
h1, h2, h3, .display { font-family: var(--font-display); font-weight: 400; margin: 0; }
h1 { font-size: 2rem; }
p { margin: 0; }
.app {
  max-width: 480px; min-height: 100vh; min-height: 100dvh; margin: 0 auto; background: var(--bg);
  display: flex; flex-direction: column; position: relative; overflow-x: hidden;
}
.screen {
  flex: 1; display: flex; flex-direction: column; gap: 16px;
  padding: 16px; padding-bottom: calc(16px + env(safe-area-inset-bottom));
}
.screen-center { align-items: center; justify-content: center; text-align: center; }
.title { color: var(--green); font-size: 2.5rem; }

/* ---------- 3D 버튼 ---------- */
.btn {
  font-family: var(--font-display); font-size: 1.3rem; min-height: 56px; padding: 10px 20px;
  border-radius: var(--radius); border: 2px solid var(--bd); background: var(--bgc); color: var(--fg, #fff);
  box-shadow: 0 5px 0 var(--bd); margin-bottom: 5px; cursor: pointer; transition: transform 60ms, box-shadow 60ms;
}
.btn:active:not(:disabled) { transform: translateY(5px); box-shadow: none; }
.btn-green { --bgc: var(--green); --bd: var(--green-dark); }
.btn-blue { --bgc: var(--blue); --bd: var(--blue-dark); }
.btn-red { --bgc: var(--red); --bd: var(--red-dark); }
.btn-yellow { --bgc: var(--yellow); --bd: var(--yellow-dark); }
.btn-white { --bgc: #fff; --bd: var(--gray); --fg: var(--text); }
.btn:disabled { --bgc: var(--gray); --bd: #d0d0d0; --fg: var(--gray-dark); cursor: default; }
.btn-white:disabled { --bgc: #fff; --bd: var(--gray); --fg: var(--gray-dark); }
.btn-selected, .btn-selected:disabled { --bgc: var(--blue-soft); --bd: #84d8ff; --fg: var(--blue-dark); }
.btn-full { width: 100%; }

/* ---------- 상단 바 ---------- */
.topbar {
  display: flex; align-items: center; gap: 6px; padding: 10px 12px; border-bottom: 2px solid var(--gray);
  position: sticky; top: 0; background: var(--bg); z-index: 10;
}
.chip {
  font-family: var(--font-display); font-size: 1.15rem; background: none; border: none; color: var(--text);
  padding: 6px 8px; border-radius: 12px; min-height: 44px; display: inline-flex; align-items: center; gap: 4px; cursor: pointer;
}
.chip-fire { color: var(--orange); }
.chip-xp { color: var(--yellow-dark); }
.spacer { flex: 1; }

/* ---------- 진행 바 / 하트 ---------- */
.progress { flex: 1; height: 18px; background: var(--gray); border-radius: 999px; overflow: hidden; }
.progress-fill {
  height: 100%; border-radius: 999px; transition: width 300ms ease;
  background: linear-gradient(to bottom, rgba(255, 255, 255, 0.35) 0 30%, transparent 30%), var(--green);
}
.hearts { font-family: var(--font-display); color: var(--red); font-size: 1.2rem; display: flex; gap: 4px; align-items: center; }

/* ---------- 마스코트 ---------- */
.mascot { display: flex; flex-direction: column; align-items: center; gap: 10px; }
.speech {
  font-family: var(--font-display); font-size: 1.1rem; background: #fff; border: 2px solid var(--gray);
  border-radius: 16px; padding: 8px 14px; position: relative;
}
.speech::after {
  content: ''; position: absolute; bottom: -9px; left: 50%; width: 14px; height: 14px; background: #fff;
  transform: translateX(-50%) rotate(45deg); border-right: 2px solid var(--gray); border-bottom: 2px solid var(--gray);
}

/* ---------- 프로필 ---------- */
.profile-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; width: 100%; }
.profile-card {
  display: flex; flex-direction: column; align-items: center; gap: 6px; padding: 16px; min-height: 56px;
  border: 2px solid var(--gray); border-bottom-width: 5px; border-radius: var(--radius); background: #fff;
  color: var(--text); font-size: 1.2rem; cursor: pointer;
}
.profile-card:active { transform: translateY(3px); border-bottom-width: 2px; }
.profile-avatar { font-size: 3rem; line-height: 1; }
.add-form { display: flex; flex-direction: column; gap: 12px; width: 100%; }
.name-input {
  min-height: 56px; border: 2px solid var(--gray); border-radius: var(--radius); padding: 0 16px;
  font-size: 1.3rem; background: var(--bg-soft); outline: none;
}
.name-input:focus { border-color: var(--blue); }
.avatar-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.avatar-pick { font-size: 2rem; min-height: 56px; border: 2px solid var(--gray); border-radius: 14px; background: #fff; cursor: pointer; }
.avatar-pick.on { border-color: var(--blue); background: var(--blue-soft); }

/* ---------- 단계 맵 ---------- */
.map { gap: 24px; padding-top: 12px; }
.unit-banner { color: #fff; border-radius: var(--radius); padding: 14px 16px; box-shadow: 0 4px 0 rgba(0, 0, 0, 0.15); }
.unit-label { font-size: 0.85rem; font-weight: 700; opacity: 0.9; }
.unit-banner h2 { font-size: 1.4rem; }
.unit-path { display: flex; flex-direction: column; align-items: center; gap: 18px; padding: 16px 0 4px; }
.node-wrap { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.node {
  width: 72px; height: 72px; border-radius: 50%; border: none; font-size: 1.9rem; color: #fff; cursor: pointer;
  background: var(--c, var(--green)); box-shadow: 0 6px 0 rgba(0, 0, 0, 0.22);
}
.node.done { background: var(--yellow); box-shadow: 0 6px 0 var(--yellow-dark); }
.node.locked { background: var(--gray); box-shadow: 0 6px 0 var(--gray-dark); cursor: default; filter: grayscale(1); }
.node-start {
  font-size: 0.95rem; color: var(--green); background: #fff; border: 2px solid var(--gray);
  border-radius: 10px; padding: 2px 10px; white-space: nowrap;
}
.node-title { font-size: 0.85rem; font-weight: 700; color: var(--text-soft); }
.node-crowns { display: flex; gap: 4px; }
.node-crowns span { width: 8px; height: 8px; border-radius: 50%; background: var(--gray); }
.node-crowns span.on { background: var(--yellow); }

/* ---------- 레슨 ---------- */
.lesson { gap: 12px; padding-bottom: 200px; }
.lesson-top { display: flex; align-items: center; gap: 12px; }
.icon-btn { background: none; border: none; font-size: 1.6rem; color: var(--gray-dark); min-width: 44px; min-height: 44px; cursor: pointer; }
.timer { align-self: center; font-family: var(--font-display); font-size: 1.2rem; color: var(--blue-dark); }
.review-tag { align-self: flex-start; background: #fff3e0; color: var(--orange); font-weight: 700; border-radius: 10px; padding: 4px 10px; font-size: 0.9rem; }
.hint { background: var(--blue-soft); color: var(--blue-dark); border-radius: 12px; padding: 10px 14px; font-weight: 700; }
.question { display: flex; flex-direction: column; gap: 16px; align-items: center; }
.q-prompt { font-family: var(--font-display); font-size: 1.4rem; align-self: flex-start; }
.q-expr { font-family: var(--font-display); font-size: 3rem; display: flex; align-items: center; justify-content: center; gap: 10px; flex-wrap: wrap; }
.slot { min-width: 72px; padding: 0 10px; border-bottom: 4px solid var(--blue); color: var(--blue-dark); text-align: center; }
.choices { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; width: 100%; }
.choices .btn { font-size: 2rem; min-height: 72px; }
.pics { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; align-items: center; font-size: 2rem; }
.pic-group { display: flex; flex-wrap: wrap; gap: 2px; justify-content: center; max-width: 220px; }
.pic-gone { opacity: 0.25; filter: grayscale(1); }
.pic-op { font-family: var(--font-display); color: var(--text-soft); }
.lesson-bottom { margin-top: auto; }

/* ---------- 키패드 ---------- */
.keypad { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; width: 100%; }
.key {
  font-family: var(--font-display); font-size: 1.8rem; min-height: 60px; color: var(--text); cursor: pointer;
  border: 2px solid var(--gray); border-radius: 14px; background: #fff; box-shadow: 0 4px 0 var(--gray);
}
.key:active:not(:disabled) { transform: translateY(4px); box-shadow: none; }
.key:disabled { color: var(--gray-dark); }

/* ---------- 피드백 시트 ---------- */
.sheet {
  position: fixed; left: 0; right: 0; bottom: 0; margin: 0 auto; width: 100%; max-width: 480px; z-index: 20;
  padding: 20px 16px calc(20px + env(safe-area-inset-bottom)); display: flex; flex-direction: column; gap: 10px;
}
.sheet-ok { background: var(--green-soft); color: var(--green-dark); }
.sheet-bad { background: var(--red-soft); color: var(--red-dark); }
.sheet-title { font-size: 1.6rem; }
.sheet-answer { font-size: 1.2rem; }
.sheet-answer strong { font-size: 1.5rem; }
.sheet-msg { font-weight: 700; }

/* ---------- 결과 ---------- */
.result h1 { color: var(--yellow-dark); }
.levelup { font-family: var(--font-display); background: var(--yellow); color: #fff; border-radius: 12px; padding: 8px 16px; font-size: 1.3rem; }
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; width: 100%; }
.stat { border: 2px solid var(--sc); border-radius: 14px; overflow: hidden; }
.stat-label { background: var(--sc); color: #fff; font-size: 0.8rem; font-weight: 700; padding: 4px; }
.stat-value { font-family: var(--font-display); font-size: 1.4rem; padding: 10px 4px; color: var(--sc); }
.crowns-row { font-size: 2.2rem; display: flex; gap: 8px; }
.crowns-row .off { filter: grayscale(1); opacity: 0.3; }
.confetti { position: fixed; inset: 0; pointer-events: none; overflow: hidden; z-index: 30; }
.confetti span { position: absolute; top: -20px; font-size: 1.4rem; }

/* ---------- 부모 설정 ---------- */
.parent { gap: 20px; }
.parent-header { display: flex; align-items: center; justify-content: space-between; }
.panel { border: 2px solid var(--gray); border-radius: var(--radius); padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.panel h3 { font-size: 1.2rem; }
.seg { display: flex; gap: 8px; flex-wrap: wrap; }
.seg button { flex: 1; min-height: 48px; border: 2px solid var(--gray); border-radius: 12px; background: #fff; font-weight: 700; cursor: pointer; }
.seg button[aria-pressed='true'] { border-color: var(--blue); background: var(--blue-soft); color: var(--blue-dark); }
.row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.row select { flex: 1; min-height: 48px; border: 2px solid var(--gray); border-radius: 12px; padding: 0 8px; background: #fff; }
.stat-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px; font-size: 0.95rem; }
.notice { background: var(--red-soft); color: var(--red-dark); border-radius: 12px; padding: 10px 14px; font-weight: 700; }
.error-text { color: var(--red); font-weight: 700; }
.small-btn { min-height: 44px; padding: 0 14px; border: 2px solid var(--gray); border-radius: 12px; background: #fff; font-weight: 700; cursor: pointer; }
.small-btn.danger { color: var(--red); }
.toggle { display: flex; align-items: center; gap: 8px; font-weight: 700; min-height: 44px; }
.toggle input { width: 22px; height: 22px; }
```

- [ ] **Step 8: 테스트·빌드 통과 확인**

Run: `npm test` → Expected: `1 passed`
Run: `npm run build` → Expected: `dist/` 생성, 타입 에러 없음

- [ ] **Step 9: Commit**

```bash
git add .gitignore package.json package-lock.json tsconfig.json vite.config.ts index.html src/
git status --short .   # node_modules/dist 가 없어야 한다
git commit -m "chore(calculator-game): Vite+React+TS 골격과 테마 CSS

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 공용 타입 + 시드 랜덤

**Files:**
- Create: `src/core/types.ts`, `src/core/random.ts`
- Test: `src/core/random.test.ts`

**Interfaces:**
- Produces:
  - `types.ts`: `Op`, `QuestionKind`, `Operands`, `Question`, `OpStats`, `StreakState`, `StageProgress`, `Profile`, `Settings`, `AppData`
  - `random.ts`: `type Rng = () => number`, `mulberry32(seed: number): Rng`, `randInt(rng, min, max): number` (양끝 포함), `pick<T>(rng, items: readonly T[]): T`, `shuffle<T>(rng, items: readonly T[]): T[]` (복사본 반환)

- [ ] **Step 1: `types.ts` 작성 (테스트 대상 아님 — 타입만)**

```ts
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
  unlockAll: boolean;
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
```

- [ ] **Step 2: 실패하는 테스트 작성** — `src/core/random.test.ts`

```ts
import { describe, it, expect } from 'vitest';
import { mulberry32, randInt, pick, shuffle } from './random';

describe('mulberry32', () => {
  it('같은 시드는 같은 수열을 만든다', () => {
    const a = mulberry32(42);
    const b = mulberry32(42);
    const seqA = Array.from({ length: 5 }, () => a());
    const seqB = Array.from({ length: 5 }, () => b());
    expect(seqA).toEqual(seqB);
  });

  it('다른 시드는 다른 수열을 만든다', () => {
    expect(mulberry32(1)()).not.toBe(mulberry32(2)());
  });

  it('0 이상 1 미만의 값을 만든다', () => {
    const rng = mulberry32(7);
    for (let i = 0; i < 1000; i++) {
      const v = rng();
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThan(1);
    }
  });
});

describe('randInt', () => {
  it('양 끝을 포함한 범위의 정수를 모두 만든다', () => {
    const rng = mulberry32(3);
    const seen = new Set<number>();
    for (let i = 0; i < 500; i++) {
      const v = randInt(rng, 2, 5);
      expect(Number.isInteger(v)).toBe(true);
      seen.add(v);
    }
    expect([...seen].sort()).toEqual([2, 3, 4, 5]);
  });
});

describe('pick / shuffle', () => {
  it('pick은 배열 안의 값을 고른다', () => {
    const rng = mulberry32(5);
    for (let i = 0; i < 50; i++) expect(['a', 'b', 'c']).toContain(pick(rng, ['a', 'b', 'c']));
  });

  it('shuffle은 원본을 바꾸지 않고 같은 원소를 돌려준다', () => {
    const src = [1, 2, 3, 4, 5];
    const out = shuffle(mulberry32(9), src);
    expect(src).toEqual([1, 2, 3, 4, 5]);
    expect([...out].sort()).toEqual([1, 2, 3, 4, 5]);
  });
});
```

- [ ] **Step 3: 실패 확인**

Run: `npx vitest run src/core/random.test.ts`
Expected: FAIL — `Failed to resolve import "./random"`

- [ ] **Step 4: 구현** — `src/core/random.ts`

```ts
export type Rng = () => number;

export function mulberry32(seed: number): Rng {
  let t = seed >>> 0;
  return () => {
    t = (t + 0x6d2b79f5) >>> 0;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r = (r + Math.imul(r ^ (r >>> 7), 61 | r)) ^ r;
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

export function randInt(rng: Rng, min: number, max: number): number {
  return min + Math.floor(rng() * (max - min + 1));
}

export function pick<T>(rng: Rng, items: readonly T[]): T {
  return items[Math.floor(rng() * items.length)];
}

export function shuffle<T>(rng: Rng, items: readonly T[]): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}
```

- [ ] **Step 5: 통과 확인**

Run: `npx vitest run src/core/random.test.ts` → Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add src/core/types.ts src/core/random.ts src/core/random.test.ts
git commit -m "feat(calculator-game): 공용 타입과 시드 랜덤

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 단계 정의 + 문제 생성기

**Files:**
- Create: `src/core/stages.ts`, `src/core/generator.ts`
- Test: `src/core/stages.test.ts`, `src/core/generator.test.ts`

**Interfaces:**
- Consumes: `Rng`, `randInt`, `pick`, `shuffle`, `mulberry32` (Task 2), `Op`, `Operands`, `Question`, `QuestionKind` (Task 2)
- Produces:
  - `stages.ts`: `interface StageDef { id; unit; title; picture: 'none'|'mixed'|'priority'; preferBlank?: boolean; hint?: string; make(rng): Operands }`, `interface UnitDef { unit; title; color; icon }`, `UNITS: UnitDef[]` (6개), `STAGES: StageDef[]` (24개, 순서대로), `getStage(id): StageDef` (없으면 throw), `stageIndex(id): number` (없으면 -1)
  - `generator.ts`: `OP_SYMBOL: Record<Op,string>`, `resultOf(o: Operands): number`, `pickKind(rng, stage, crowns): QuestionKind`, `makeChoices(rng, o: Operands, answer): number[]`, `makeQuestion(rng, stage, kind, index): Question`, `generateLesson(stage, crowns, seed, count = 10): Question[]`

- [ ] **Step 1: 실패하는 단계 규칙 테스트 작성** — `src/core/stages.test.ts`

각 단계가 만드는 수식이 스펙 4장 표의 규칙을 지키는지 1000번씩 확인한다.

```ts
import { describe, it, expect } from 'vitest';
import { STAGES, UNITS, getStage, stageIndex } from './stages';
import { mulberry32 } from './random';
import type { Operands } from './types';

const between = (n: number, lo: number, hi: number) => n >= lo && n <= hi;
const isAdd = (q: Operands) => q.op === 'add';
const isSub = (q: Operands) => q.op === 'sub';
const mulOf = (ds: number[]) => (q: Operands) => q.op === 'mul' && ds.includes(q.a) && between(q.b, 1, 9);
const divOf = (ds: number[]) => (q: Operands) =>
  q.op === 'div' && ds.includes(q.b) && q.a % q.b === 0 && between(q.a / q.b, 1, 9);
const all = [2, 3, 4, 5, 6, 7, 8, 9];

const RULES: Record<string, (q: Operands) => boolean> = {
  u1s1: (q) => isAdd(q) && between(q.a, 1, 8) && between(q.b, 1, 2),
  u1s2: (q) => isAdd(q) && q.a >= 1 && q.b >= 1 && q.a + q.b <= 5,
  u1s3: (q) => isAdd(q) && q.a >= 1 && q.b >= 1 && q.a + q.b <= 10,
  u1s4: (q) => isAdd(q) && q.a >= 1 && q.b >= 1 && q.a + q.b === 10,
  u2s1: (q) => isSub(q) && between(q.a, 2, 6) && between(q.b, 1, 2),
  u2s2: (q) => isSub(q) && q.a <= 5 && q.b >= 1 && q.a - q.b >= 0,
  u2s3: (q) => isSub(q) && q.a <= 10 && q.b >= 1 && q.a - q.b >= 0,
  u2s4: (q) => RULES.u1s3(q) || RULES.u2s3(q),
  u3s1: (q) => isAdd(q) && between(q.a, 10, 19) && q.b >= 1 && (q.a % 10) + q.b <= 9 && q.a + q.b <= 19,
  u3s2: (q) => isAdd(q) && between(q.a, 2, 9) && between(q.b, 2, 9) && between(q.a + q.b, 11, 18),
  u3s3: (q) => isSub(q) && between(q.a, 11, 18) && between(q.b, 2, 9) && q.a % 10 < q.b,
  u3s4: (q) => RULES.u3s1(q) || RULES.u3s2(q) || RULES.u3s3(q),
  u4s1: mulOf([2]),
  u4s2: mulOf([5]),
  u4s3: mulOf([3]),
  u4s4: mulOf([4]),
  u5s1: mulOf([6]),
  u5s2: mulOf([7]),
  u5s3: mulOf([8, 9]),
  u5s4: mulOf(all),
  u6s1: divOf([2, 5]),
  u6s2: divOf([3, 4]),
  u6s3: divOf([6, 7, 8, 9]),
  u6s4: (q) => mulOf(all)(q) || divOf(all)(q),
};

describe('STAGES', () => {
  it('유닛 6개, 단계 24개이고 ID가 규칙표와 일치한다', () => {
    expect(UNITS).toHaveLength(6);
    expect(STAGES.map((s) => s.id)).toEqual(Object.keys(RULES));
  });

  it.each(STAGES.map((s, i) => [s.id, i] as const))('%s 는 1000문제 모두 규칙을 지킨다', (id, i) => {
    const stage = getStage(id);
    const rng = mulberry32(i + 1);
    for (let n = 0; n < 1000; n++) {
      const q = stage.make(rng);
      expect(RULES[id](q), `${id}: ${JSON.stringify(q)}`).toBe(true);
    }
  });

  it('getStage는 없는 ID에 에러, stageIndex는 -1', () => {
    expect(() => getStage('nope')).toThrow();
    expect(stageIndex('nope')).toBe(-1);
    expect(stageIndex('u1s1')).toBe(0);
    expect(stageIndex('u6s4')).toBe(23);
  });

  it('그림 문제는 유닛 1~2에만, 나눗셈 힌트는 u6s1에만', () => {
    for (const s of STAGES) {
      if (s.unit > 2) expect(s.picture).toBe('none');
    }
    expect(getStage('u1s1').picture).toBe('priority');
    expect(getStage('u2s1').picture).toBe('priority');
    expect(getStage('u1s4').preferBlank).toBe(true);
    expect(getStage('u6s1').hint).toContain('구구단 거꾸로');
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run src/core/stages.test.ts`
Expected: FAIL — `Failed to resolve import "./stages"`

- [ ] **Step 3: 구현** — `src/core/stages.ts`

```ts
import { pick, randInt, type Rng } from './random';
import type { Operands } from './types';

export interface StageDef {
  id: string;
  unit: number;
  title: string;
  picture: 'none' | 'mixed' | 'priority';
  preferBlank?: boolean;
  hint?: string;
  make: (rng: Rng) => Operands;
}

export interface UnitDef {
  unit: number;
  title: string;
  color: string;
  icon: string;
}

type Maker = (rng: Rng) => Operands;

const add = (a: number, b: number): Operands => ({ op: 'add', a, b });
const sub = (a: number, b: number): Operands => ({ op: 'sub', a, b });

const plusSmall: Maker = (rng) => add(randInt(rng, 1, 8), randInt(rng, 1, 2));
const minusSmall: Maker = (rng) => sub(randInt(rng, 2, 6), randInt(rng, 1, 2));

const sumTo = (max: number): Maker => (rng) => {
  const a = randInt(rng, 1, max - 1);
  return add(a, randInt(rng, 1, max - a));
};

const makeTen: Maker = (rng) => {
  const a = randInt(rng, 1, 9);
  return add(a, 10 - a);
};

const subWithin = (max: number): Maker => (rng) => {
  const a = randInt(rng, 1, max);
  return sub(a, randInt(rng, 1, a));
};

const teenNoCarry: Maker = (rng) => {
  const a = randInt(rng, 10, 18);
  return add(a, randInt(rng, 1, 9 - (a % 10)));
};

const addCarry: Maker = (rng) => {
  const a = randInt(rng, 2, 9);
  return add(a, randInt(rng, Math.max(2, 11 - a), 9));
};

const subBorrow: Maker = (rng) => {
  const a = randInt(rng, 11, 18);
  return sub(a, randInt(rng, (a % 10) + 1, 9));
};

const times = (ds: number[]): Maker => (rng) => ({ op: 'mul', a: pick(rng, ds), b: randInt(rng, 1, 9) });

const divide = (ds: number[]): Maker => (rng) => {
  const d = pick(rng, ds);
  return { op: 'div', a: d * randInt(rng, 1, 9), b: d };
};

const mix = (...makers: Maker[]): Maker => (rng) => pick(rng, makers)(rng);

const ALL = [2, 3, 4, 5, 6, 7, 8, 9];

export const UNITS: UnitDef[] = [
  { unit: 1, title: '10까지 덧셈', color: '#58CC02', icon: '➕' },
  { unit: 2, title: '10까지 뺄셈', color: '#1CB0F6', icon: '➖' },
  { unit: 3, title: '20까지 덧셈·뺄셈', color: '#CE82FF', icon: '🔢' },
  { unit: 4, title: '구구단 ①', color: '#FF9600', icon: '✖️' },
  { unit: 5, title: '구구단 ②', color: '#FF4B4B', icon: '✖️' },
  { unit: 6, title: '나눗셈', color: '#2B70C9', icon: '➗' },
];

export const STAGES: StageDef[] = [
  { id: 'u1s1', unit: 1, title: '그림 세기', picture: 'priority', make: plusSmall },
  { id: 'u1s2', unit: 1, title: '합 5까지', picture: 'mixed', make: sumTo(5) },
  { id: 'u1s3', unit: 1, title: '합 10까지', picture: 'mixed', make: sumTo(10) },
  { id: 'u1s4', unit: 1, title: '10 만들기', picture: 'mixed', preferBlank: true, make: makeTen },
  { id: 'u2s1', unit: 2, title: '그림 빼기', picture: 'priority', make: minusSmall },
  { id: 'u2s2', unit: 2, title: '5 안에서 빼기', picture: 'mixed', make: subWithin(5) },
  { id: 'u2s3', unit: 2, title: '10 안에서 빼기', picture: 'mixed', make: subWithin(10) },
  { id: 'u2s4', unit: 2, title: '더하기 빼기 섞기', picture: 'mixed', make: mix(sumTo(10), subWithin(10)) },
  { id: 'u3s1', unit: 3, title: '10 넘는 덧셈', picture: 'none', make: teenNoCarry },
  { id: 'u3s2', unit: 3, title: '받아올림 덧셈', picture: 'none', make: addCarry },
  { id: 'u3s3', unit: 3, title: '받아내림 뺄셈', picture: 'none', make: subBorrow },
  { id: 'u3s4', unit: 3, title: '20까지 섞기', picture: 'none', make: mix(teenNoCarry, addCarry, subBorrow) },
  { id: 'u4s1', unit: 4, title: '2단', picture: 'none', make: times([2]) },
  { id: 'u4s2', unit: 4, title: '5단', picture: 'none', make: times([5]) },
  { id: 'u4s3', unit: 4, title: '3단', picture: 'none', make: times([3]) },
  { id: 'u4s4', unit: 4, title: '4단', picture: 'none', make: times([4]) },
  { id: 'u5s1', unit: 5, title: '6단', picture: 'none', make: times([6]) },
  { id: 'u5s2', unit: 5, title: '7단', picture: 'none', make: times([7]) },
  { id: 'u5s3', unit: 5, title: '8단·9단', picture: 'none', make: times([8, 9]) },
  { id: 'u5s4', unit: 5, title: '구구단 섞기', picture: 'none', make: times(ALL) },
  {
    id: 'u6s1', unit: 6, title: '2단·5단 나누기', picture: 'none', make: divide([2, 5]),
    hint: '나눗셈은 구구단 거꾸로! 12 ÷ 3 = ? 는 3 × ? = 12 와 같아요.',
  },
  { id: 'u6s2', unit: 6, title: '3단·4단 나누기', picture: 'none', make: divide([3, 4]) },
  { id: 'u6s3', unit: 6, title: '6~9단 나누기', picture: 'none', make: divide([6, 7, 8, 9]) },
  { id: 'u6s4', unit: 6, title: '곱셈 나눗셈 섞기', picture: 'none', make: mix(times(ALL), divide(ALL)) },
];

export function stageIndex(id: string): number {
  return STAGES.findIndex((s) => s.id === id);
}

export function getStage(id: string): StageDef {
  const stage = STAGES.find((s) => s.id === id);
  if (!stage) throw new Error(`알 수 없는 단계: ${id}`);
  return stage;
}
```

- [ ] **Step 4: 통과 확인**

Run: `npx vitest run src/core/stages.test.ts` → Expected: PASS (28 tests)

- [ ] **Step 5: 실패하는 생성기 테스트 작성** — `src/core/generator.test.ts`

```ts
import { describe, it, expect } from 'vitest';
import { generateLesson, makeChoices, makeQuestion, pickKind, resultOf } from './generator';
import { STAGES, getStage } from './stages';
import { mulberry32 } from './random';

describe('resultOf', () => {
  it('네 연산의 결과를 계산한다', () => {
    expect(resultOf({ op: 'add', a: 3, b: 4 })).toBe(7);
    expect(resultOf({ op: 'sub', a: 9, b: 4 })).toBe(5);
    expect(resultOf({ op: 'mul', a: 6, b: 7 })).toBe(42);
    expect(resultOf({ op: 'div', a: 42, b: 7 })).toBe(6);
  });
});

describe('makeChoices', () => {
  it('모든 단계에서 보기 4개가 서로 다르고, 정답을 포함하고, 0 이상이다', () => {
    const rng = mulberry32(11);
    for (const stage of STAGES) {
      for (let i = 0; i < 300; i++) {
        const o = stage.make(rng);
        const answer = resultOf(o);
        const choices = makeChoices(rng, o, answer);
        expect(choices).toHaveLength(4);
        expect(new Set(choices).size).toBe(4);
        expect(choices).toContain(answer);
        for (const c of choices) expect(c).toBeGreaterThanOrEqual(0);
      }
    }
  });

  it('정답이 0이어도 보기 4개를 만든다', () => {
    const choices = makeChoices(mulberry32(1), { op: 'sub', a: 3, b: 3 }, 0);
    expect(new Set(choices).size).toBe(4);
    expect(choices).toContain(0);
  });
});

describe('pickKind', () => {
  it('왕관 0개일 때 객관식이 약 70% 나온다', () => {
    const rng = mulberry32(5);
    const stage = getStage('u4s1');
    const n = 10000;
    let choice = 0;
    for (let i = 0; i < n; i++) if (pickKind(rng, stage, 0) === 'choice') choice++;
    expect(choice / n).toBeGreaterThan(0.67);
    expect(choice / n).toBeLessThan(0.73);
  });

  it('왕관 2개 이상이면 키패드가 가장 많다', () => {
    const rng = mulberry32(6);
    const stage = getStage('u4s1');
    const counts = { choice: 0, keypad: 0, blank: 0, picture: 0 };
    for (let i = 0; i < 10000; i++) counts[pickKind(rng, stage, 3)]++;
    expect(counts.keypad / 10000).toBeGreaterThan(0.47);
    expect(counts.keypad / 10000).toBeLessThan(0.53);
    expect(counts.picture).toBe(0);
  });

  it('picture=priority 단계는 객관식 몫을 모두 그림 문제로 낸다', () => {
    const rng = mulberry32(7);
    for (let i = 0; i < 2000; i++) expect(pickKind(rng, getStage('u1s1'), 0)).not.toBe('choice');
  });

  it('preferBlank 단계는 키패드 대신 빈칸을 낸다', () => {
    const rng = mulberry32(8);
    for (let i = 0; i < 2000; i++) expect(pickKind(rng, getStage('u1s4'), 2)).not.toBe('keypad');
  });
});

describe('makeQuestion', () => {
  it('blank 문제의 답은 b이고, 그 외는 계산 결과다', () => {
    const rng = mulberry32(3);
    const stage = getStage('u4s4');
    const blank = makeQuestion(rng, stage, 'blank', 0);
    expect(blank.answer).toBe(blank.b);
    expect(blank.result).toBe(blank.a * blank.b);
    expect(blank.choices).toBeUndefined();
    const keypad = makeQuestion(rng, stage, 'keypad', 1);
    expect(keypad.answer).toBe(keypad.result);
  });

  it('곱셈·나눗셈에 picture를 요청하면 choice로 바꾼다', () => {
    const q = makeQuestion(mulberry32(1), getStage('u4s1'), 'picture', 0);
    expect(q.kind).toBe('choice');
    expect(q.choices).toHaveLength(4);
  });
});

describe('generateLesson', () => {
  it('10문제를 만들고, 같은 시드면 같은 레슨이다', () => {
    const a = generateLesson(getStage('u3s2'), 0, 99);
    const b = generateLesson(getStage('u3s2'), 0, 99);
    expect(a).toHaveLength(10);
    expect(a).toEqual(b);
  });

  it('같은 수식이 연속으로 나오지 않는다 (경우의 수가 적은 단계 포함)', () => {
    for (const id of ['u1s4', 'u4s1', 'u2s1']) {
      for (let seed = 0; seed < 200; seed++) {
        const qs = generateLesson(getStage(id), 0, seed);
        for (let i = 1; i < qs.length; i++) expect(qs[i].key).not.toBe(qs[i - 1].key);
      }
    }
  });

  it('id는 레슨 안에서 모두 다르다', () => {
    const qs = generateLesson(getStage('u4s1'), 0, 1);
    expect(new Set(qs.map((q) => q.id)).size).toBe(10);
  });
});
```

- [ ] **Step 6: 실패 확인**

Run: `npx vitest run src/core/generator.test.ts`
Expected: FAIL — `Failed to resolve import "./generator"`

- [ ] **Step 7: 구현** — `src/core/generator.ts`

```ts
import { mulberry32, shuffle, type Rng } from './random';
import type { StageDef } from './stages';
import type { Op, Operands, Question, QuestionKind } from './types';

export const OP_SYMBOL: Record<Op, string> = { add: '+', sub: '−', mul: '×', div: '÷' };

export function resultOf({ op, a, b }: Operands): number {
  switch (op) {
    case 'add':
      return a + b;
    case 'sub':
      return a - b;
    case 'mul':
      return a * b;
    case 'div':
      return a / b;
  }
}

// 왕관 수(0, 1, 2+)별 객관식·키패드 비율. 나머지는 빈칸.
const KIND_SHARES = [
  { choice: 0.7, keypad: 0.2 },
  { choice: 0.4, keypad: 0.4 },
  { choice: 0.2, keypad: 0.5 },
];

export function pickKind(rng: Rng, stage: StageDef, crowns: number): QuestionKind {
  const share = KIND_SHARES[Math.min(crowns, 2)];
  const r = rng();
  if (r < share.choice) {
    if (stage.picture === 'priority') return 'picture';
    if (stage.picture === 'mixed' && rng() < 0.5) return 'picture';
    return 'choice';
  }
  if (stage.preferBlank) return 'blank';
  return r < share.choice + share.keypad ? 'keypad' : 'blank';
}

export function makeChoices(rng: Rng, { op, a, b }: Operands, answer: number): number[] {
  const candidates = [answer + 1, answer - 1, answer + 2, answer - 2];
  if (op === 'add') candidates.push(Math.abs(a - b)); // 덧셈↔뺄셈 혼동
  if (op === 'sub') candidates.push(a + b);
  if (op === 'mul') candidates.push(a * (b + 1), a * (b - 1)); // 구구단 이웃 값
  if (op === 'div') candidates.push(b);
  const pool = [...new Set(candidates.filter((n) => n >= 0 && n !== answer))];
  let extra = 3;
  while (pool.length < 3) {
    const n = answer + extra++;
    if (!pool.includes(n)) pool.push(n);
  }
  const wrong = shuffle(rng, pool).slice(0, 3);
  return shuffle(rng, [answer, ...wrong]);
}

export function makeQuestion(rng: Rng, stage: StageDef, kind: QuestionKind, index: number): Question {
  const o = stage.make(rng);
  const finalKind: QuestionKind = kind === 'picture' && (o.op === 'mul' || o.op === 'div') ? 'choice' : kind;
  const result = resultOf(o);
  const answer = finalKind === 'blank' ? o.b : result;
  const key = `${o.op}:${o.a}:${o.b}`;
  const q: Question = { ...o, id: `${index}-${key}`, key, result, answer, kind: finalKind };
  if (finalKind === 'choice' || finalKind === 'picture') q.choices = makeChoices(rng, o, answer);
  return q;
}

export function generateLesson(stage: StageDef, crowns: number, seed: number, count = 10): Question[] {
  const rng = mulberry32(seed);
  const used = new Set<string>();
  const out: Question[] = [];
  let prevKey = '';
  for (let i = 0; i < count; i++) {
    const kind = pickKind(rng, stage, crowns);
    let q: Question;
    let tries = 0;
    do {
      q = makeQuestion(rng, stage, kind, i);
      tries++;
      // 연속 중복은 절대 금지, 레슨 내 중복은 30번까지 피해본다
    } while (q.key === prevKey || (used.has(q.key) && tries < 30));
    used.add(q.key);
    prevKey = q.key;
    out.push(q);
  }
  return out;
}
```

- [ ] **Step 8: 통과 확인**

Run: `npx vitest run src/core` → Expected: PASS (stages + generator + random 전부)

- [ ] **Step 9: Commit**

```bash
git add src/core/stages.ts src/core/stages.test.ts src/core/generator.ts src/core/generator.test.ts
git commit -m "feat(calculator-game): 24단계 정의와 문제 생성기

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 스트릭 (날짜·ISO 주·얼리기)

**Files:**
- Create: `src/core/streak.ts`
- Test: `src/core/streak.test.ts`

**Interfaces:**
- Consumes: `StreakState` (Task 2)
- Produces: `toLocalDateString(d: Date): string`, `daysBetween(from: string, to: string): number`, `isoWeekKey(date: string): string` (`YYYY-Www`), `recordPlay(s: StreakState, today: string): StreakState`, `displayStreak(s: StreakState, today: string): number`, `emptyStreak(): StreakState`

- [ ] **Step 1: 실패하는 테스트 작성** — `src/core/streak.test.ts`

```ts
import { describe, it, expect } from 'vitest';
import { daysBetween, displayStreak, emptyStreak, isoWeekKey, recordPlay, toLocalDateString } from './streak';

describe('날짜 유틸', () => {
  it('로컬 날짜를 YYYY-MM-DD로 만든다', () => {
    expect(toLocalDateString(new Date(2026, 9, 5, 23, 59))).toBe('2026-10-05');
  });

  it('날짜 사이 일수를 센다 (월 경계 포함)', () => {
    expect(daysBetween('2026-09-30', '2026-10-01')).toBe(1);
    expect(daysBetween('2026-10-10', '2026-10-10')).toBe(0);
    expect(daysBetween('2026-10-01', '2026-10-04')).toBe(3);
  });

  it('ISO 주 키를 만든다', () => {
    expect(isoWeekKey('2026-10-10')).toBe('2026-W41');
    expect(isoWeekKey('2025-12-29')).toBe('2026-W01');
    expect(isoWeekKey('2026-10-05')).toBe(isoWeekKey('2026-10-11')); // 월~일 같은 주
    expect(isoWeekKey('2026-10-12')).not.toBe(isoWeekKey('2026-10-11'));
  });
});

describe('recordPlay', () => {
  const s = (count: number, last: string | null, freeze: string | null = null) => ({
    count, lastPlayedDate: last, freezeUsedWeek: freeze,
  });

  it('처음 플레이하면 1', () => {
    expect(recordPlay(emptyStreak(), '2026-10-10')).toEqual(s(1, '2026-10-10'));
  });

  it('같은 날 다시 하면 그대로', () => {
    expect(recordPlay(s(3, '2026-10-10'), '2026-10-10')).toEqual(s(3, '2026-10-10'));
  });

  it('어제 했으면 +1', () => {
    expect(recordPlay(s(3, '2026-10-09'), '2026-10-10')).toEqual(s(4, '2026-10-10'));
  });

  it('하루 걸렀고 이번 주 얼리기를 안 썼으면 얼리기를 쓰고 +1', () => {
    expect(recordPlay(s(3, '2026-10-07'), '2026-10-09')).toEqual(s(4, '2026-10-09', isoWeekKey('2026-10-09')));
  });

  it('하루 걸렀는데 이번 주 얼리기를 이미 썼으면 1로 리셋', () => {
    const week = isoWeekKey('2026-10-09');
    expect(recordPlay(s(3, '2026-10-07', week), '2026-10-09')).toEqual(s(1, '2026-10-09', week));
  });

  it('지난주에 쓴 얼리기는 이번 주에 다시 쓸 수 있다', () => {
    const lastWeek = isoWeekKey('2026-10-01');
    expect(recordPlay(s(5, '2026-10-07', lastWeek), '2026-10-09').count).toBe(6);
  });

  it('이틀 이상 거르면 1로 리셋', () => {
    expect(recordPlay(s(9, '2026-10-06'), '2026-10-09').count).toBe(1);
  });
});

describe('displayStreak', () => {
  const s = (count: number, last: string | null, freeze: string | null = null) => ({
    count, lastPlayedDate: last, freezeUsedWeek: freeze,
  });

  it('오늘/어제 했으면 그대로 보여준다', () => {
    expect(displayStreak(s(4, '2026-10-10'), '2026-10-10')).toBe(4);
    expect(displayStreak(s(4, '2026-10-09'), '2026-10-10')).toBe(4);
  });

  it('하루 걸렀어도 얼리기가 남아 있으면 유지', () => {
    expect(displayStreak(s(4, '2026-10-08'), '2026-10-10')).toBe(4);
  });

  it('얼리기를 이미 썼거나 이틀 이상 걸렀으면 0', () => {
    expect(displayStreak(s(4, '2026-10-08', isoWeekKey('2026-10-10')), '2026-10-10')).toBe(0);
    expect(displayStreak(s(4, '2026-10-06'), '2026-10-10')).toBe(0);
    expect(displayStreak(emptyStreak(), '2026-10-10')).toBe(0);
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run src/core/streak.test.ts`
Expected: FAIL — `Failed to resolve import "./streak"`

- [ ] **Step 3: 구현** — `src/core/streak.ts`

```ts
import type { StreakState } from './types';

const DAY_MS = 86_400_000;

function parse(date: string): number {
  const [y, m, d] = date.split('-').map(Number);
  return Date.UTC(y, m - 1, d);
}

export function toLocalDateString(d: Date): string {
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${mm}-${dd}`;
}

export function daysBetween(from: string, to: string): number {
  return Math.round((parse(to) - parse(from)) / DAY_MS);
}

export function isoWeekKey(date: string): string {
  const d = new Date(parse(date));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum); // 그 주의 목요일
  const yearStart = Date.UTC(d.getUTCFullYear(), 0, 1);
  const week = Math.ceil(((d.getTime() - yearStart) / DAY_MS + 1) / 7);
  return `${d.getUTCFullYear()}-W${String(week).padStart(2, '0')}`;
}

export function emptyStreak(): StreakState {
  return { count: 0, lastPlayedDate: null, freezeUsedWeek: null };
}

export function recordPlay(s: StreakState, today: string): StreakState {
  if (!s.lastPlayedDate) return { ...s, count: 1, lastPlayedDate: today };
  const gap = daysBetween(s.lastPlayedDate, today);
  if (gap <= 0) return s;
  if (gap === 1) return { ...s, count: s.count + 1, lastPlayedDate: today };
  const week = isoWeekKey(today);
  if (gap === 2 && s.freezeUsedWeek !== week) {
    return { count: s.count + 1, lastPlayedDate: today, freezeUsedWeek: week };
  }
  return { ...s, count: 1, lastPlayedDate: today };
}

export function displayStreak(s: StreakState, today: string): number {
  if (!s.lastPlayedDate) return 0;
  const gap = daysBetween(s.lastPlayedDate, today);
  if (gap <= 1) return s.count;
  if (gap === 2 && s.freezeUsedWeek !== isoWeekKey(today)) return s.count;
  return 0;
}
```

- [ ] **Step 4: 통과 확인**

Run: `npx vitest run src/core/streak.test.ts` → Expected: PASS (13 tests)

- [ ] **Step 5: Commit**

```bash
git add src/core/streak.ts src/core/streak.test.ts
git commit -m "feat(calculator-game): 스트릭과 주 1회 얼리기

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: 점수·레벨·잠금 + 레슨 결과 반영

**Files:**
- Create: `src/core/scoring.ts`, `src/core/progress.ts`
- Test: `src/core/scoring.test.ts`, `src/core/progress.test.ts`

**Interfaces:**
- Consumes: `STAGES`, `stageIndex` (Task 3), `recordPlay` (Task 4), `Profile`, `OpStats` (Task 2)
- Produces:
  - `scoring.ts`: `interface LessonOutcome { firstTryCorrect: number; total: number; heartsLeft: number; stats: OpStats }`, `emptyStats(): OpStats`, `lessonXp(o): number`, `accuracy(o): number`, `isPassed(o): boolean`, `levelFromXp(xp): number`, `xpForLevel(level): number` (그 레벨 시작 누적 XP), `isStageUnlocked(stageId, p: Pick<Profile,'stages'|'unlockAll'>): boolean`
  - `progress.ts`: `interface LessonSummary { xpGained; accuracy; passed; perfect; crowns; stageCompleted; levelBefore; levelAfter; streak }`, `applyLesson(profile, stageId, outcome, today): { profile: Profile; summary: LessonSummary }`, `withStartStage(profile, stageId): Profile`

- [ ] **Step 1: 실패하는 테스트 작성** — `src/core/scoring.test.ts`

```ts
import { describe, it, expect } from 'vitest';
import { accuracy, emptyStats, isPassed, isStageUnlocked, lessonXp, levelFromXp, xpForLevel, type LessonOutcome } from './scoring';

const outcome = (firstTryCorrect: number, heartsLeft: number, total = 10): LessonOutcome => ({
  firstTryCorrect, total, heartsLeft, stats: emptyStats(),
});

describe('XP', () => {
  it('무실수 10문제 = 10×10 + 20 + 10 = 130', () => {
    expect(lessonXp(outcome(10, 5))).toBe(130);
  });
  it('7개 정답 = 70 + 20 = 90 (무실수 보너스 없음)', () => {
    expect(lessonXp(outcome(7, 2))).toBe(90);
  });
});

describe('통과 판정', () => {
  it('70% 이상이고 하트가 남으면 통과', () => {
    expect(accuracy(outcome(7, 2))).toBeCloseTo(0.7);
    expect(isPassed(outcome(7, 2))).toBe(true);
  });
  it('69% 이하면 실패', () => {
    expect(isPassed(outcome(6, 1))).toBe(false);
  });
  it('하트가 0이면 정답률이 높아도 실패', () => {
    expect(isPassed(outcome(8, 0))).toBe(false);
  });
  it('문제가 0개면 정답률 0', () => {
    expect(accuracy(outcome(0, 5, 0))).toBe(0);
  });
});

describe('레벨', () => {
  it.each([
    [0, 1], [99, 1], [100, 2], [299, 2], [300, 3], [599, 3], [600, 4],
  ])('XP %i → 레벨 %i', (xp, level) => {
    expect(levelFromXp(xp)).toBe(level);
  });
  it('레벨 시작 XP', () => {
    expect(xpForLevel(1)).toBe(0);
    expect(xpForLevel(2)).toBe(100);
    expect(xpForLevel(4)).toBe(600);
  });
});

describe('isStageUnlocked', () => {
  const p = (stages: Record<string, { crowns: number; bestAccuracy: number }>, unlockAll = false) => ({ stages, unlockAll });
  it('첫 단계는 항상 열려 있다', () => {
    expect(isStageUnlocked('u1s1', p({}))).toBe(true);
  });
  it('이전 단계 왕관 3개면 열린다', () => {
    expect(isStageUnlocked('u1s2', p({ u1s1: { crowns: 2, bestAccuracy: 1 } }))).toBe(false);
    expect(isStageUnlocked('u1s2', p({ u1s1: { crowns: 3, bestAccuracy: 1 } }))).toBe(true);
  });
  it('unlockAll이면 모두 열린다', () => {
    expect(isStageUnlocked('u6s4', p({}, true))).toBe(true);
  });
  it('없는 단계는 닫혀 있다', () => {
    expect(isStageUnlocked('zzz', p({}))).toBe(false);
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run src/core/scoring.test.ts`
Expected: FAIL — `Failed to resolve import "./scoring"`

- [ ] **Step 3: 구현** — `src/core/scoring.ts`

```ts
import { STAGES, stageIndex } from './stages';
import type { OpStats, Profile } from './types';

export const XP_CORRECT = 10;
export const XP_LESSON = 20;
export const XP_PERFECT = 10;
export const PASS_ACCURACY = 0.7;

export interface LessonOutcome {
  firstTryCorrect: number;
  total: number;
  heartsLeft: number;
  stats: OpStats;
}

export function emptyStats(): OpStats {
  return {
    add: { correct: 0, total: 0 },
    sub: { correct: 0, total: 0 },
    mul: { correct: 0, total: 0 },
    div: { correct: 0, total: 0 },
  };
}

export function lessonXp(o: LessonOutcome): number {
  const perfect = o.total > 0 && o.firstTryCorrect === o.total;
  return o.firstTryCorrect * XP_CORRECT + XP_LESSON + (perfect ? XP_PERFECT : 0);
}

export function accuracy(o: LessonOutcome): number {
  return o.total === 0 ? 0 : o.firstTryCorrect / o.total;
}

export function isPassed(o: LessonOutcome): boolean {
  return accuracy(o) >= PASS_ACCURACY && o.heartsLeft > 0;
}

// 레벨 n → n+1 에 필요한 누적 XP = 50·n·(n+1)
export function levelFromXp(xp: number): number {
  let level = 1;
  while (xp >= 50 * level * (level + 1)) level++;
  return level;
}

export function xpForLevel(level: number): number {
  return 50 * (level - 1) * level;
}

export function isStageUnlocked(stageId: string, p: Pick<Profile, 'stages' | 'unlockAll'>): boolean {
  const i = stageIndex(stageId);
  if (i < 0) return false;
  if (p.unlockAll || i === 0) return true;
  return (p.stages[STAGES[i - 1].id]?.crowns ?? 0) >= 3;
}
```

- [ ] **Step 4: 통과 확인**

Run: `npx vitest run src/core/scoring.test.ts` → Expected: PASS

- [ ] **Step 5: 실패하는 테스트 작성** — `src/core/progress.test.ts`

```ts
import { describe, it, expect } from 'vitest';
import { applyLesson, withStartStage } from './progress';
import { emptyStats, isStageUnlocked, type LessonOutcome } from './scoring';
import type { Profile } from './types';

const profile = (over: Partial<Profile> = {}): Profile => ({
  id: 'p1', name: '하늘', avatar: '🐶', xp: 0,
  streak: { count: 0, lastPlayedDate: null, freezeUsedWeek: null },
  stages: {}, unlockAll: false, stats: emptyStats(), ...over,
});

const outcome = (firstTryCorrect: number, heartsLeft = 5): LessonOutcome => {
  const stats = emptyStats();
  stats.add = { correct: firstTryCorrect, total: 10 };
  return { firstTryCorrect, total: 10, heartsLeft, stats };
};

describe('applyLesson', () => {
  it('통과하면 XP·왕관·스트릭·통계가 오른다', () => {
    const { profile: p, summary } = applyLesson(profile(), 'u1s1', outcome(10), '2026-10-10');
    expect(p.xp).toBe(130);
    expect(p.stages.u1s1).toEqual({ crowns: 1, bestAccuracy: 1 });
    expect(p.streak.count).toBe(1);
    expect(p.stats.add).toEqual({ correct: 10, total: 10 });
    expect(summary).toMatchObject({
      xpGained: 130, accuracy: 1, passed: true, perfect: true, crowns: 1,
      stageCompleted: false, levelBefore: 1, levelAfter: 2, streak: 1,
    });
  });

  it('실패하면 왕관은 그대로지만 XP와 스트릭은 인정된다', () => {
    const { profile: p, summary } = applyLesson(profile(), 'u1s1', outcome(5, 0), '2026-10-10');
    expect(p.stages.u1s1.crowns).toBe(0);
    expect(p.xp).toBe(70);
    expect(p.streak.count).toBe(1);
    expect(summary.passed).toBe(false);
  });

  it('세 번째 왕관을 받는 순간에만 stageCompleted', () => {
    const start = profile({ stages: { u1s1: { crowns: 2, bestAccuracy: 0.8 } } });
    const first = applyLesson(start, 'u1s1', outcome(9), '2026-10-10');
    expect(first.summary.crowns).toBe(3);
    expect(first.summary.stageCompleted).toBe(true);
    const again = applyLesson(first.profile, 'u1s1', outcome(10), '2026-10-10');
    expect(again.summary.crowns).toBe(3);
    expect(again.summary.stageCompleted).toBe(false);
  });

  it('최고 정답률은 내려가지 않는다', () => {
    const start = profile({ stages: { u1s1: { crowns: 1, bestAccuracy: 0.9 } } });
    const { profile: p } = applyLesson(start, 'u1s1', outcome(7), '2026-10-10');
    expect(p.stages.u1s1.bestAccuracy).toBe(0.9);
  });

  it('원본 프로필을 바꾸지 않는다', () => {
    const start = profile();
    applyLesson(start, 'u1s1', outcome(10), '2026-10-10');
    expect(start.xp).toBe(0);
    expect(start.stats.add.total).toBe(0);
  });
});

describe('withStartStage', () => {
  it('지정한 단계 앞은 모두 왕관 3개가 되어 그 단계가 열린다', () => {
    const p = withStartStage(profile({ stages: { u1s1: { crowns: 1, bestAccuracy: 0.7 } } }), 'u3s1');
    expect(p.stages.u1s1).toEqual({ crowns: 3, bestAccuracy: 0.7 });
    expect(p.stages.u2s4.crowns).toBe(3);
    expect(p.stages.u3s1).toBeUndefined();
    expect(isStageUnlocked('u3s1', p)).toBe(true);
    expect(isStageUnlocked('u3s2', p)).toBe(false);
  });
});
```

- [ ] **Step 6: 실패 확인**

Run: `npx vitest run src/core/progress.test.ts`
Expected: FAIL — `Failed to resolve import "./progress"`

- [ ] **Step 7: 구현** — `src/core/progress.ts`

```ts
import { accuracy, isPassed, lessonXp, levelFromXp, type LessonOutcome } from './scoring';
import { STAGES, stageIndex } from './stages';
import { recordPlay } from './streak';
import type { Op, OpStats, Profile } from './types';

export interface LessonSummary {
  xpGained: number;
  accuracy: number;
  passed: boolean;
  perfect: boolean;
  crowns: number;
  stageCompleted: boolean;
  levelBefore: number;
  levelAfter: number;
  streak: number;
}

function mergeStats(a: OpStats, b: OpStats): OpStats {
  const out = { ...a };
  for (const op of Object.keys(out) as Op[]) {
    out[op] = { correct: a[op].correct + b[op].correct, total: a[op].total + b[op].total };
  }
  return out;
}

export function applyLesson(
  profile: Profile,
  stageId: string,
  outcome: LessonOutcome,
  today: string,
): { profile: Profile; summary: LessonSummary } {
  const xpGained = lessonXp(outcome);
  const acc = accuracy(outcome);
  const passed = isPassed(outcome);
  const prev = profile.stages[stageId] ?? { crowns: 0, bestAccuracy: 0 };
  const crowns = passed ? Math.min(3, prev.crowns + 1) : prev.crowns;
  const streak = recordPlay(profile.streak, today);
  const next: Profile = {
    ...profile,
    xp: profile.xp + xpGained,
    streak,
    stages: { ...profile.stages, [stageId]: { crowns, bestAccuracy: Math.max(prev.bestAccuracy, acc) } },
    stats: mergeStats(profile.stats, outcome.stats),
  };
  return {
    profile: next,
    summary: {
      xpGained,
      accuracy: acc,
      passed,
      perfect: outcome.total > 0 && outcome.firstTryCorrect === outcome.total,
      crowns,
      stageCompleted: prev.crowns < 3 && crowns === 3,
      levelBefore: levelFromXp(profile.xp),
      levelAfter: levelFromXp(next.xp),
      streak: streak.count,
    },
  };
}

export function withStartStage(profile: Profile, stageId: string): Profile {
  const idx = stageIndex(stageId);
  const stages = { ...profile.stages };
  STAGES.forEach((s, i) => {
    if (i < idx) stages[s.id] = { crowns: 3, bestAccuracy: stages[s.id]?.bestAccuracy ?? 0 };
  });
  return { ...profile, stages };
}
```

- [ ] **Step 8: 통과 확인**

Run: `npx vitest run src/core` → Expected: PASS (전부)

- [ ] **Step 9: Commit**

```bash
git add src/core/scoring.ts src/core/scoring.test.ts src/core/progress.ts src/core/progress.test.ts
git commit -m "feat(calculator-game): XP·레벨·통과 판정과 레슨 결과 반영

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: localStorage 저장소

**Files:**
- Create: `src/core/storage.ts`, `src/test/memoryKV.ts`
- Test: `src/core/storage.test.ts`

**Interfaces:**
- Consumes: `AppData`, `Profile` (Task 2), `emptyStats` (Task 5), `emptyStreak` (Task 4)
- Produces: `STORAGE_KEY = 'calculator_game:v1'`, `type KV = Pick<Storage,'getItem'|'setItem'>`, `defaultAppData(): AppData`, `newProfile(id, name, avatar): Profile`, `browserStorage(): KV | null`, `loadAppData(kv: KV | null): { data: AppData; error: boolean }`, `saveAppData(kv: KV | null, data: AppData): boolean`; 테스트용 `class MemoryKV implements KV`

- [ ] **Step 1: 테스트용 MemoryKV 작성** — `src/test/memoryKV.ts`

```ts
export class MemoryKV {
  store = new Map<string, string>();
  getItem(key: string): string | null {
    return this.store.has(key) ? this.store.get(key)! : null;
  }
  setItem(key: string, value: string): void {
    this.store.set(key, String(value));
  }
}
```

- [ ] **Step 2: 실패하는 테스트 작성** — `src/core/storage.test.ts`

```ts
import { describe, it, expect } from 'vitest';
import { STORAGE_KEY, defaultAppData, loadAppData, newProfile, saveAppData } from './storage';
import { MemoryKV } from '../test/memoryKV';

const throwing = {
  getItem: () => { throw new Error('blocked'); },
  setItem: () => { throw new Error('quota'); },
};

describe('loadAppData', () => {
  it('저장된 게 없으면 기본값, 에러 아님', () => {
    expect(loadAppData(new MemoryKV())).toEqual({ data: defaultAppData(), error: false });
  });

  it('저장 → 불러오기 왕복', () => {
    const kv = new MemoryKV();
    const data = { ...defaultAppData(), profiles: [newProfile('p1', '하늘', '🐶')], activeProfileId: 'p1' };
    data.profiles[0].xp = 250;
    expect(saveAppData(kv, data)).toBe(true);
    expect(loadAppData(kv)).toEqual({ data, error: false });
  });

  it('깨진 JSON이면 기본값 + 에러', () => {
    const kv = new MemoryKV();
    kv.setItem(STORAGE_KEY, '{not json');
    expect(loadAppData(kv)).toEqual({ data: defaultAppData(), error: true });
  });

  it('스키마 버전이 다르면 기본값 + 에러', () => {
    const kv = new MemoryKV();
    kv.setItem(STORAGE_KEY, JSON.stringify({ ...defaultAppData(), schemaVersion: 2 }));
    expect(loadAppData(kv).error).toBe(true);
  });

  it('프로필에 빠진 필드는 기본값으로 채운다', () => {
    const kv = new MemoryKV();
    kv.setItem(STORAGE_KEY, JSON.stringify({ schemaVersion: 1, profiles: [{ id: 'p1', name: '하늘' }], activeProfileId: 'p1', settings: {} }));
    const { data, error } = loadAppData(kv);
    expect(error).toBe(false);
    expect(data.profiles[0]).toEqual(newProfile('p1', '하늘', '🐣'));
    expect(data.settings).toEqual({ soundOn: true, timerSec: null });
  });

  it('없는 프로필을 가리키는 activeProfileId는 null로', () => {
    const kv = new MemoryKV();
    kv.setItem(STORAGE_KEY, JSON.stringify({ ...defaultAppData(), activeProfileId: 'ghost' }));
    expect(loadAppData(kv).data.activeProfileId).toBeNull();
  });

  it('읽기가 예외를 던지거나 저장소가 없으면 기본값 + 에러', () => {
    expect(loadAppData(throwing)).toEqual({ data: defaultAppData(), error: true });
    expect(loadAppData(null)).toEqual({ data: defaultAppData(), error: true });
  });
});

describe('saveAppData', () => {
  it('쓰기 예외는 삼키고 false', () => {
    expect(saveAppData(throwing, defaultAppData())).toBe(false);
    expect(saveAppData(null, defaultAppData())).toBe(false);
  });
});
```

- [ ] **Step 3: 실패 확인**

Run: `npx vitest run src/core/storage.test.ts`
Expected: FAIL — `Failed to resolve import "./storage"`

- [ ] **Step 4: 구현** — `src/core/storage.ts`

```ts
import { emptyStats } from './scoring';
import { emptyStreak } from './streak';
import type { AppData, Profile } from './types';

export const STORAGE_KEY = 'calculator_game:v1';

export type KV = Pick<Storage, 'getItem' | 'setItem'>;

export function defaultAppData(): AppData {
  return { schemaVersion: 1, profiles: [], activeProfileId: null, settings: { soundOn: true, timerSec: null } };
}

export function newProfile(id: string, name: string, avatar: string): Profile {
  return { id, name, avatar, xp: 0, streak: emptyStreak(), stages: {}, unlockAll: false, stats: emptyStats() };
}

export function browserStorage(): KV | null {
  try {
    const s = window.localStorage;
    s.getItem(STORAGE_KEY); // 사생활 보호 모드 등에서 여기서 예외가 난다
    return s;
  } catch {
    return null;
  }
}

function isObj(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function normalize(v: unknown): AppData | null {
  if (!isObj(v) || v.schemaVersion !== 1 || !Array.isArray(v.profiles)) return null;
  const profiles: Profile[] = [];
  for (const p of v.profiles) {
    if (!isObj(p) || typeof p.id !== 'string' || typeof p.name !== 'string') return null;
    const base = newProfile(p.id, p.name, typeof p.avatar === 'string' ? p.avatar : '🐣');
    const stats = { ...base.stats, ...(isObj(p.stats) ? p.stats : {}) };
    profiles.push({ ...base, ...p, stats } as Profile);
  }
  const settings = isObj(v.settings) ? v.settings : {};
  const activeProfileId =
    typeof v.activeProfileId === 'string' && profiles.some((p) => p.id === v.activeProfileId) ? v.activeProfileId : null;
  return {
    schemaVersion: 1,
    profiles,
    activeProfileId,
    settings: {
      soundOn: settings.soundOn !== false,
      timerSec: typeof settings.timerSec === 'number' ? settings.timerSec : null,
    },
  };
}

export function loadAppData(kv: KV | null): { data: AppData; error: boolean } {
  if (!kv) return { data: defaultAppData(), error: true };
  let raw: string | null;
  try {
    raw = kv.getItem(STORAGE_KEY);
  } catch {
    return { data: defaultAppData(), error: true };
  }
  if (raw === null) return { data: defaultAppData(), error: false };
  try {
    const data = normalize(JSON.parse(raw));
    return data ? { data, error: false } : { data: defaultAppData(), error: true };
  } catch {
    return { data: defaultAppData(), error: true };
  }
}

export function saveAppData(kv: KV | null, data: AppData): boolean {
  if (!kv) return false;
  try {
    kv.setItem(STORAGE_KEY, JSON.stringify(data));
    return true;
  } catch {
    return false;
  }
}
```

- [ ] **Step 5: 통과 확인**

Run: `npx vitest run src/core/storage.test.ts` → Expected: PASS (8 tests)

- [ ] **Step 6: Commit**

```bash
git add src/core/storage.ts src/core/storage.test.ts src/test/memoryKV.ts
git commit -m "feat(calculator-game): localStorage 저장·검증·복구

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: 레슨 진행 상태기계 + 부모 잠금 문제

**Files:**
- Create: `src/core/lesson.ts`, `src/core/parentLock.ts`
- Test: `src/core/lesson.test.ts`, `src/core/parentLock.test.ts`

**Interfaces:**
- Consumes: `Question` (Task 2), `emptyStats`, `LessonOutcome` (Task 5), `Rng`, `randInt` (Task 2)
- Produces:
  - `lesson.ts`: `START_HEARTS = 5`, `interface LessonItem { q: Question; review: boolean }`, `interface LastAnswer { correct: boolean; timedOut: boolean; review: boolean }`, `interface LessonState { items; index; mainTotal; answeredMain; firstTryCorrect; hearts; inARow; stats: OpStats; phase: 'answering'|'feedback'|'done'; last: LastAnswer | null }`, `startLesson(questions): LessonState`, `currentItem(s): LessonItem | null`, `submitAnswer(s, value: number | null): LessonState` (`null` = 시간 초과), `nextQuestion(s): LessonState`, `lessonProgress(s): number` (0..1), `toOutcome(s): LessonOutcome`
  - `parentLock.ts`: `interface ParentChallenge { a: number; b: number; answer: number }`, `makeParentChallenge(rng): ParentChallenge`

- [ ] **Step 1: 실패하는 테스트 작성** — `src/core/lesson.test.ts`

```ts
import { describe, it, expect } from 'vitest';
import { currentItem, lessonProgress, nextQuestion, startLesson, submitAnswer, toOutcome, type LessonState } from './lesson';
import type { Question } from './types';

const q = (i: number, answer = i + 1): Question => ({
  id: `${i}`, key: `add:${i}:1`, op: 'add', a: i, b: 1, result: i + 1, answer, kind: 'keypad',
});
const lesson = (n = 10) => startLesson(Array.from({ length: n }, (_, i) => q(i)));
const answer = (s: LessonState, correct: boolean) =>
  nextQuestion(submitAnswer(s, correct ? currentItem(s)!.q.answer : -1));

describe('lesson', () => {
  it('시작 상태', () => {
    const s = lesson();
    expect(s.phase).toBe('answering');
    expect(s.hearts).toBe(5);
    expect(currentItem(s)?.q.id).toBe('0');
    expect(lessonProgress(s)).toBe(0);
  });

  it('정답이면 점수가 오르고 피드백 단계가 된다', () => {
    const s = submitAnswer(lesson(), 1);
    expect(s.phase).toBe('feedback');
    expect(s.last).toEqual({ correct: true, timedOut: false, review: false });
    expect(s.firstTryCorrect).toBe(1);
    expect(s.hearts).toBe(5);
    expect(s.inARow).toBe(1);
    expect(s.stats.add).toEqual({ correct: 1, total: 1 });
    expect(lessonProgress(s)).toBeCloseTo(0.1);
  });

  it('오답이면 하트가 줄고 복습 문제가 끝에 붙는다', () => {
    const s = submitAnswer(lesson(), 99);
    expect(s.last).toEqual({ correct: false, timedOut: false, review: false });
    expect(s.hearts).toBe(4);
    expect(s.items).toHaveLength(11);
    expect(s.items[10]).toEqual({ q: q(0), review: true });
    expect(s.inARow).toBe(0);
    expect(s.stats.add).toEqual({ correct: 0, total: 1 });
  });

  it('시간 초과는 하트를 깎지 않지만 오답으로 세고 복습에 넣는다', () => {
    const s = submitAnswer(lesson(), null);
    expect(s.last).toEqual({ correct: false, timedOut: true, review: false });
    expect(s.hearts).toBe(5);
    expect(s.firstTryCorrect).toBe(0);
    expect(s.items).toHaveLength(11);
  });

  it('피드백 단계에서는 답을 다시 받지 않는다', () => {
    const s = submitAnswer(lesson(), 1);
    expect(submitAnswer(s, 1)).toBe(s);
  });

  it('하트는 0 아래로 내려가지 않는다', () => {
    let s = lesson();
    for (let i = 0; i < 7; i++) s = answer(s, false);
    expect(s.hearts).toBe(0);
  });

  it('복습 문제는 점수·하트·진행도에 영향이 없고 다시 붙지 않는다', () => {
    let s = lesson(2);
    s = answer(s, false); // 0번 오답 → 복습 추가
    s = answer(s, true); // 1번 정답
    expect(currentItem(s)).toEqual({ q: q(0), review: true });
    const before = { hearts: s.hearts, answeredMain: s.answeredMain, firstTryCorrect: s.firstTryCorrect };
    s = submitAnswer(s, 99); // 복습도 오답
    expect(s.last?.review).toBe(true);
    expect(s).toMatchObject(before);
    expect(s.items).toHaveLength(3);
    s = nextQuestion(s);
    expect(s.phase).toBe('done');
    expect(currentItem(s)).toBeNull();
  });

  it('끝까지 풀면 결과를 만든다', () => {
    let s = lesson();
    for (let i = 0; i < 7; i++) s = answer(s, true);
    for (let i = 0; i < 3; i++) s = answer(s, false);
    while (s.phase !== 'done') s = answer(s, true);
    expect(lessonProgress(s)).toBe(1);
    expect(toOutcome(s)).toEqual({
      firstTryCorrect: 7, total: 10, heartsLeft: 2,
      stats: { add: { correct: 7, total: 10 }, sub: { correct: 0, total: 0 }, mul: { correct: 0, total: 0 }, div: { correct: 0, total: 0 } },
    });
  });
});
```

`src/core/parentLock.test.ts`:
```ts
import { describe, it, expect } from 'vitest';
import { makeParentChallenge } from './parentLock';
import { mulberry32 } from './random';

describe('makeParentChallenge', () => {
  it('두 자리 × 한 자리 곱셈을 만든다', () => {
    const rng = mulberry32(1);
    for (let i = 0; i < 200; i++) {
      const c = makeParentChallenge(rng);
      expect(c.a).toBeGreaterThanOrEqual(12);
      expect(c.a).toBeLessThanOrEqual(29);
      expect(c.b).toBeGreaterThanOrEqual(3);
      expect(c.b).toBeLessThanOrEqual(9);
      expect(c.answer).toBe(c.a * c.b);
    }
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run src/core/lesson.test.ts src/core/parentLock.test.ts`
Expected: FAIL — `Failed to resolve import "./lesson"` / `"./parentLock"`

- [ ] **Step 3: 구현** — `src/core/lesson.ts`

```ts
import { emptyStats, type LessonOutcome } from './scoring';
import type { OpStats, Question } from './types';

export const START_HEARTS = 5;

export interface LessonItem {
  q: Question;
  review: boolean;
}

export interface LastAnswer {
  correct: boolean;
  timedOut: boolean;
  review: boolean;
}

export interface LessonState {
  items: LessonItem[];
  index: number;
  mainTotal: number;
  answeredMain: number;
  firstTryCorrect: number;
  hearts: number;
  inARow: number;
  stats: OpStats;
  phase: 'answering' | 'feedback' | 'done';
  last: LastAnswer | null;
}

export function startLesson(questions: Question[]): LessonState {
  return {
    items: questions.map((q) => ({ q, review: false })),
    index: 0,
    mainTotal: questions.length,
    answeredMain: 0,
    firstTryCorrect: 0,
    hearts: START_HEARTS,
    inARow: 0,
    stats: emptyStats(),
    phase: questions.length ? 'answering' : 'done',
    last: null,
  };
}

export function currentItem(s: LessonState): LessonItem | null {
  return s.phase === 'done' ? null : s.items[s.index] ?? null;
}

export function submitAnswer(s: LessonState, value: number | null): LessonState {
  const item = currentItem(s);
  if (s.phase !== 'answering' || !item) return s;
  const timedOut = value === null;
  const correct = !timedOut && value === item.q.answer;
  const next: LessonState = {
    ...s,
    phase: 'feedback',
    inARow: correct ? s.inARow + 1 : 0,
    last: { correct, timedOut, review: item.review },
  };
  if (item.review) return next;

  const op = item.q.op;
  next.answeredMain = s.answeredMain + 1;
  next.stats = { ...s.stats, [op]: { correct: s.stats[op].correct + (correct ? 1 : 0), total: s.stats[op].total + 1 } };
  if (correct) {
    next.firstTryCorrect = s.firstTryCorrect + 1;
  } else {
    if (!timedOut) next.hearts = Math.max(0, s.hearts - 1);
    next.items = [...s.items, { q: item.q, review: true }];
  }
  return next;
}

export function nextQuestion(s: LessonState): LessonState {
  if (s.phase !== 'feedback') return s;
  const index = s.index + 1;
  return { ...s, index, phase: index >= s.items.length ? 'done' : 'answering' };
}

export function lessonProgress(s: LessonState): number {
  return s.mainTotal === 0 ? 1 : s.answeredMain / s.mainTotal;
}

export function toOutcome(s: LessonState): LessonOutcome {
  return { firstTryCorrect: s.firstTryCorrect, total: s.mainTotal, heartsLeft: s.hearts, stats: s.stats };
}
```

`src/core/parentLock.ts`:
```ts
import { randInt, type Rng } from './random';

export interface ParentChallenge {
  a: number;
  b: number;
  answer: number;
}

export function makeParentChallenge(rng: Rng): ParentChallenge {
  const a = randInt(rng, 12, 29);
  const b = randInt(rng, 3, 9);
  return { a, b, answer: a * b };
}
```

- [ ] **Step 4: 통과 확인**

Run: `npx vitest run src/core` → Expected: PASS (전부)

- [ ] **Step 5: Commit**

```bash
git add src/core/lesson.ts src/core/lesson.test.ts src/core/parentLock.ts src/core/parentLock.test.ts
git commit -m "feat(calculator-game): 레슨 진행(하트·복습·시간초과)과 부모 잠금 문제

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Zustand 스토어 + React 연결

**Files:**
- Create: `src/state/store.ts`, `src/state/GameContext.tsx`
- Test: `src/state/store.test.ts`

**Interfaces:**
- Consumes: `loadAppData`, `saveAppData`, `newProfile`, `KV` (Task 6), `applyLesson`, `withStartStage`, `LessonSummary` (Task 5), `LessonOutcome` (Task 5), `toLocalDateString` (Task 4)
- Produces:
  - `store.ts`: `type Screen = {name:'profiles'} | {name:'map'} | {name:'lesson'; stageId} | {name:'result'; stageId; summary: LessonSummary} | {name:'parent'}`, `interface GameState { data; loadError; screen; nextSeed(): number; today(): string; goto(screen); addProfile(name, avatar); selectProfile(id); removeProfile(id); setSound(on); setTimer(sec|null); setUnlockAll(id, on); setStartStage(id, stageId); finishLesson(stageId, outcome) }`, `interface StoreOptions { kv: KV | null; nextSeed?; today?; makeId? }`, `type GameStore = StoreApi<GameState>`, `createGameStore(opts): GameStore`, `activeProfile(s: GameState): Profile | null`
  - `GameContext.tsx`: `GameProvider({ store, children })`, `useGame<T>(selector: (s: GameState) => T): T`

- [ ] **Step 1: 실패하는 테스트 작성** — `src/state/store.test.ts`

```ts
import { describe, it, expect } from 'vitest';
import { activeProfile, createGameStore } from './store';
import { MemoryKV } from '../test/memoryKV';
import { STORAGE_KEY, loadAppData } from '../core/storage';
import { emptyStats } from '../core/scoring';

function make(kv = new MemoryKV()) {
  let n = 0;
  const store = createGameStore({ kv, nextSeed: () => 1, today: () => '2026-10-10', makeId: () => `p${++n}` });
  return { kv, store };
}

describe('game store', () => {
  it('처음엔 프로필 화면에서 시작한다', () => {
    const { store } = make();
    expect(store.getState().screen).toEqual({ name: 'profiles' });
    expect(store.getState().loadError).toBe(false);
  });

  it('프로필을 추가하면 활성화되고 맵으로 가며 저장된다', () => {
    const { store, kv } = make();
    store.getState().addProfile('  하늘 ', '🐶');
    const s = store.getState();
    expect(activeProfile(s)?.name).toBe('하늘');
    expect(s.screen).toEqual({ name: 'map' });
    expect(loadAppData(kv).data.profiles).toHaveLength(1);
  });

  it('저장된 활성 프로필이 있으면 맵에서 다시 시작한다', () => {
    const { kv, store } = make();
    store.getState().addProfile('하늘', '🐶');
    const reopened = make(kv).store;
    expect(reopened.getState().screen).toEqual({ name: 'map' });
    expect(activeProfile(reopened.getState())?.name).toBe('하늘');
  });

  it('레슨을 끝내면 프로필이 갱신되고 결과 화면으로 간다', () => {
    const { store } = make();
    store.getState().addProfile('하늘', '🐶');
    const stats = emptyStats();
    stats.add = { correct: 10, total: 10 };
    store.getState().finishLesson('u1s1', { firstTryCorrect: 10, total: 10, heartsLeft: 5, stats });
    const s = store.getState();
    const p = activeProfile(s)!;
    expect(p.xp).toBe(130);
    expect(p.stages.u1s1.crowns).toBe(1);
    expect(p.streak.count).toBe(1);
    expect(s.screen).toMatchObject({ name: 'result', stageId: 'u1s1', summary: { xpGained: 130, passed: true } });
  });

  it('설정 변경', () => {
    const { store } = make();
    store.getState().addProfile('하늘', '🐶');
    store.getState().setTimer(15);
    store.getState().setSound(false);
    store.getState().setUnlockAll('p1', true);
    store.getState().setStartStage('p1', 'u2s1');
    const s = store.getState();
    expect(s.data.settings).toEqual({ soundOn: false, timerSec: 15 });
    expect(activeProfile(s)?.unlockAll).toBe(true);
    expect(activeProfile(s)?.stages.u1s4.crowns).toBe(3);
  });

  it('활성 프로필을 지우면 활성 해제된다', () => {
    const { store } = make();
    store.getState().addProfile('하늘', '🐶');
    store.getState().addProfile('바다', '🐱');
    store.getState().removeProfile('p2');
    expect(store.getState().data.profiles.map((p) => p.id)).toEqual(['p1']);
    expect(store.getState().data.activeProfileId).toBeNull();
  });

  it('손상된 저장 데이터면 loadError', () => {
    const kv = new MemoryKV();
    kv.setItem(STORAGE_KEY, 'garbage');
    expect(make(kv).store.getState().loadError).toBe(true);
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run src/state/store.test.ts`
Expected: FAIL — `Failed to resolve import "./store"`

- [ ] **Step 3: 구현** — `src/state/store.ts`

```ts
import { createStore, type StoreApi } from 'zustand/vanilla';
import { applyLesson, withStartStage, type LessonSummary } from '../core/progress';
import type { LessonOutcome } from '../core/scoring';
import { loadAppData, newProfile, saveAppData, type KV } from '../core/storage';
import { toLocalDateString } from '../core/streak';
import type { AppData, Profile } from '../core/types';

export type Screen =
  | { name: 'profiles' }
  | { name: 'map' }
  | { name: 'lesson'; stageId: string }
  | { name: 'result'; stageId: string; summary: LessonSummary }
  | { name: 'parent' };

export interface GameState {
  data: AppData;
  loadError: boolean;
  screen: Screen;
  nextSeed: () => number;
  today: () => string;
  goto: (screen: Screen) => void;
  addProfile: (name: string, avatar: string) => void;
  selectProfile: (id: string) => void;
  removeProfile: (id: string) => void;
  setSound: (on: boolean) => void;
  setTimer: (sec: number | null) => void;
  setUnlockAll: (id: string, on: boolean) => void;
  setStartStage: (id: string, stageId: string) => void;
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
      screen: data.activeProfileId ? { name: 'map' } : { name: 'profiles' },
      nextSeed: opts.nextSeed ?? (() => Math.floor(Math.random() * 2 ** 31)),
      today: opts.today ?? (() => toLocalDateString(new Date())),

      goto: (screen) => set({ screen }),

      addProfile: (name, avatar) => {
        const id = makeId();
        updateData((d) => ({
          ...d,
          profiles: [...d.profiles, newProfile(id, name.trim() || '친구', avatar)],
          activeProfileId: id,
        }));
        set({ screen: { name: 'map' } });
      },

      selectProfile: (id) => {
        updateData((d) => ({ ...d, activeProfileId: id }));
        set({ screen: { name: 'map' } });
      },

      removeProfile: (id) =>
        updateData((d) => ({
          ...d,
          profiles: d.profiles.filter((p) => p.id !== id),
          activeProfileId: d.activeProfileId === id ? null : d.activeProfileId,
        })),

      setSound: (on) => updateData((d) => ({ ...d, settings: { ...d.settings, soundOn: on } })),
      setTimer: (sec) => updateData((d) => ({ ...d, settings: { ...d.settings, timerSec: sec } })),
      setUnlockAll: (id, on) => updateProfile(id, (p) => ({ ...p, unlockAll: on })),
      setStartStage: (id, stageId) => updateProfile(id, (p) => withStartStage(p, stageId)),

      finishLesson: (stageId, outcome) => {
        const p = activeProfile(get());
        if (!p) return;
        const { profile, summary } = applyLesson(p, stageId, outcome, get().today());
        updateProfile(p.id, () => profile);
        set({ screen: { name: 'result', stageId, summary } });
      },
    };
  });

  store.subscribe((s, prev) => {
    if (s.data !== prev.data) saveAppData(opts.kv, s.data);
  });
  return store;
}
```

`src/state/GameContext.tsx`:
```tsx
import { createContext, useContext, type ReactNode } from 'react';
import { useStore } from 'zustand';
import type { GameState, GameStore } from './store';

const GameContext = createContext<GameStore | null>(null);

export function GameProvider({ store, children }: { store: GameStore; children: ReactNode }) {
  return <GameContext.Provider value={store}>{children}</GameContext.Provider>;
}

// selector는 기존 객체 참조나 원시값만 돌려줘야 한다 (새 객체를 만들면 무한 렌더)
export function useGame<T>(selector: (s: GameState) => T): T {
  const store = useContext(GameContext);
  if (!store) throw new Error('GameProvider 안에서만 useGame을 쓸 수 있어요');
  return useStore(store, selector);
}
```

- [ ] **Step 4: 통과 확인**

Run: `npx vitest run src/state` → Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/state/
git commit -m "feat(calculator-game): Zustand 게임 스토어와 저장 연동

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: 효과음 + 공용 UI 컴포넌트

**Files:**
- Create: `src/audio/sfx.ts`, `src/ui/components/Button3D.tsx`, `ProgressBar.tsx`, `Hearts.tsx`, `Mascot.tsx`, `Keypad.tsx`, `FeedbackSheet.tsx`, `Confetti.tsx`
- Test: `src/ui/components/components.test.tsx`

**Interfaces:**
- Produces:
  - `sfx.ts`: `playCorrect()`, `playWrong()`, `playFanfare()`, `vibrate(ms)` — AudioContext가 없으면 아무것도 안 함
  - `Button3D(props: ButtonHTMLAttributes & { variant?: 'green'|'blue'|'red'|'yellow'|'white'; full?: boolean; selected?: boolean })`
  - `ProgressBar({ value: number })` — `role="progressbar"`, `aria-valuenow` 0..100
  - `Hearts({ count })` — `aria-label="하트 N개"`
  - `type Mood = 'idle'|'happy'|'cheer'`, `Mascot({ mood?, size?, speech? })`
  - `Keypad({ value: string; onChange(v: string); disabled? })` — 버튼 `aria-label="숫자 N"`, `"지우기"`, 최대 3자리
  - `FeedbackSheet({ correct; timedOut; correctText; message; onContinue })` — 제목 `잘했어! 🎉` / `시간이 다 됐어!` / `괜찮아, 다시 해보자!`, 버튼 `계속`
  - `Confetti()`

- [ ] **Step 1: 실패하는 테스트 작성** — `src/ui/components/components.test.tsx`

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { Button3D } from './Button3D';
import { ProgressBar } from './ProgressBar';
import { Hearts } from './Hearts';
import { Keypad } from './Keypad';
import { FeedbackSheet } from './FeedbackSheet';
import { Mascot } from './Mascot';
import { playCorrect, playFanfare, playWrong, vibrate } from '../../audio/sfx';

function KeypadHarness() {
  const [v, setV] = useState('');
  return (
    <>
      <output>{v}</output>
      <Keypad value={v} onChange={setV} />
    </>
  );
}

describe('components', () => {
  it('Button3D는 변형·선택 클래스를 붙인다', () => {
    render(<Button3D variant="white" selected full>7</Button3D>);
    const btn = screen.getByRole('button', { name: '7' });
    expect(btn).toHaveClass('btn', 'btn-white', 'btn-selected', 'btn-full');
    expect(btn).toHaveAttribute('type', 'button');
  });

  it('ProgressBar는 퍼센트를 알려준다', () => {
    render(<ProgressBar value={0.3} />);
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '30');
  });

  it('Hearts는 개수를 읽어준다', () => {
    render(<Hearts count={3} />);
    expect(screen.getByLabelText('하트 3개')).toBeInTheDocument();
  });

  it('Keypad는 숫자 입력·지우기·3자리 제한', async () => {
    const user = userEvent.setup();
    render(<KeypadHarness />);
    for (const d of ['1', '2', '3', '4']) await user.click(screen.getByRole('button', { name: `숫자 ${d}` }));
    expect(screen.getByRole('status')).toHaveTextContent('123');
    await user.click(screen.getByRole('button', { name: '지우기' }));
    expect(screen.getByRole('status')).toHaveTextContent('12');
  });

  it('Keypad는 0 다음 숫자를 누르면 0을 바꾼다', async () => {
    const user = userEvent.setup();
    render(<KeypadHarness />);
    await user.click(screen.getByRole('button', { name: '숫자 0' }));
    await user.click(screen.getByRole('button', { name: '숫자 5' }));
    expect(screen.getByRole('status')).toHaveTextContent('5');
  });

  it('FeedbackSheet: 오답이면 정답과 격려, 계속 버튼', async () => {
    const user = userEvent.setup();
    const onContinue = vi.fn();
    render(<FeedbackSheet correct={false} timedOut={false} correctText="8" message="한 번 더 나올 거야" onContinue={onContinue} />);
    expect(screen.getByText('괜찮아, 다시 해보자!')).toBeInTheDocument();
    expect(screen.getByText('8')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '계속' }));
    expect(onContinue).toHaveBeenCalledOnce();
  });

  it('FeedbackSheet: 정답이면 정답 줄을 숨긴다', () => {
    render(<FeedbackSheet correct timedOut={false} correctText="8" message="" onContinue={() => {}} />);
    expect(screen.getByText('잘했어! 🎉')).toBeInTheDocument();
    expect(screen.queryByText(/정답:/)).toBeNull();
  });

  it('Mascot은 말풍선을 보여준다', () => {
    render(<Mascot mood="happy" speech="안녕!" />);
    expect(screen.getByText('안녕!')).toBeInTheDocument();
  });

  it('효과음은 AudioContext가 없어도 에러 없이 넘어간다', () => {
    expect(() => { playCorrect(); playWrong(); playFanfare(); vibrate(50); }).not.toThrow();
  });
});
```

`<output>` 요소의 암묵적 역할은 `status` 다.

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run src/ui/components`
Expected: FAIL — `Failed to resolve import "./Button3D"`

- [ ] **Step 3: 효과음 구현** — `src/audio/sfx.ts`

```ts
type AudioCtor = typeof AudioContext;
let ctx: AudioContext | null = null;

function audio(): AudioContext | null {
  if (ctx) return ctx;
  const AC: AudioCtor | undefined =
    window.AudioContext ?? (window as unknown as { webkitAudioContext?: AudioCtor }).webkitAudioContext;
  if (!AC) return null;
  try {
    ctx = new AC();
  } catch {
    return null;
  }
  return ctx;
}

function tone(freq: number, at: number, dur: number, type: OscillatorType = 'sine', vol = 0.18) {
  const c = audio();
  if (!c) return;
  if (c.state === 'suspended') void c.resume();
  const t = c.currentTime + at;
  const osc = c.createOscillator();
  const gain = c.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, t);
  gain.gain.setValueAtTime(0.0001, t);
  gain.gain.exponentialRampToValueAtTime(vol, t + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  osc.connect(gain).connect(c.destination);
  osc.start(t);
  osc.stop(t + dur + 0.05);
}

export function playCorrect() {
  tone(784, 0, 0.18);
  tone(1175, 0.12, 0.3);
}

export function playWrong() {
  tone(330, 0, 0.15, 'square', 0.08);
  tone(220, 0.12, 0.25, 'square', 0.08);
}

export function playFanfare() {
  [523, 659, 784, 1047].forEach((f, i) => tone(f, i * 0.12, i === 3 ? 0.5 : 0.18, 'triangle'));
}

export function vibrate(ms: number) {
  try {
    navigator.vibrate?.(ms);
  } catch {
    // 진동 미지원 기기
  }
}
```

- [ ] **Step 4: 컴포넌트 구현**

`src/ui/components/Button3D.tsx`:
```tsx
import type { ButtonHTMLAttributes } from 'react';

type Variant = 'green' | 'blue' | 'red' | 'yellow' | 'white';

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  full?: boolean;
  selected?: boolean;
}

export function Button3D({ variant = 'green', full, selected, className = '', type = 'button', ...rest }: Props) {
  const cls = ['btn', `btn-${variant}`, full && 'btn-full', selected && 'btn-selected', className].filter(Boolean).join(' ');
  return <button type={type} className={cls} {...rest} />;
}
```

`src/ui/components/ProgressBar.tsx`:
```tsx
export function ProgressBar({ value }: { value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
      <div className="progress-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}
```

`src/ui/components/Hearts.tsx`:
```tsx
export function Hearts({ count }: { count: number }) {
  return (
    <div className="hearts" aria-label={`하트 ${count}개`}>
      ❤️ <span>{count}</span>
    </div>
  );
}
```

`src/ui/components/Mascot.tsx`:
```tsx
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
```

`src/ui/components/Keypad.tsx`:
```tsx
const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '', '0', 'del'];
const MAX_DIGITS = 3;

interface Props {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

export function Keypad({ value, onChange, disabled }: Props) {
  const press = (key: string) => {
    if (key === 'del') onChange(value.slice(0, -1));
    else if (value === '0') onChange(key);
    else if (value.length < MAX_DIGITS) onChange(value + key);
  };
  return (
    <div className="keypad">
      {KEYS.map((key, i) =>
        key === '' ? (
          <span key={i} />
        ) : (
          <button
            key={key}
            type="button"
            className="key"
            disabled={disabled}
            aria-label={key === 'del' ? '지우기' : `숫자 ${key}`}
            onClick={() => press(key)}
          >
            {key === 'del' ? '⌫' : key}
          </button>
        ),
      )}
    </div>
  );
}
```

`src/ui/components/FeedbackSheet.tsx`:
```tsx
import { motion } from 'framer-motion';
import { Button3D } from './Button3D';

interface Props {
  correct: boolean;
  timedOut: boolean;
  correctText: string;
  message: string;
  onContinue: () => void;
}

export function FeedbackSheet({ correct, timedOut, correctText, message, onContinue }: Props) {
  const title = correct ? '잘했어! 🎉' : timedOut ? '시간이 다 됐어!' : '괜찮아, 다시 해보자!';
  return (
    <motion.div
      className={`sheet ${correct ? 'sheet-ok' : 'sheet-bad'}`}
      initial={{ y: '100%' }}
      animate={{ y: 0 }}
      transition={{ type: 'spring', damping: 22, stiffness: 260 }}
    >
      <div className="sheet-title display">{title}</div>
      {!correct && (
        <div className="sheet-answer">
          정답: <strong>{correctText}</strong>
        </div>
      )}
      {message && <div className="sheet-msg">{message}</div>}
      <Button3D variant={correct ? 'green' : 'red'} full onClick={onContinue}>
        계속
      </Button3D>
    </motion.div>
  );
}
```

`src/ui/components/Confetti.tsx`:
```tsx
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
```

- [ ] **Step 5: 통과 확인**

Run: `npx vitest run src/ui/components` → Expected: PASS (9 tests)

- [ ] **Step 6: Commit**

```bash
git add src/audio/ src/ui/components/
git commit -m "feat(calculator-game): 효과음과 듀오링고풍 공용 컴포넌트

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: 앱 라우팅 + 프로필 선택 + 단계 맵

**Files:**
- Create: `src/ui/components/TopBar.tsx`, `src/ui/screens/ProfileSelect.tsx`, `src/ui/screens/StageMap.tsx`, `src/test/renderApp.tsx`
- Create (임시, Task 11·12에서 교체): `src/ui/screens/Lesson.tsx`, `src/ui/screens/Result.tsx`, `src/ui/screens/Parent.tsx`
- Modify: `src/App.tsx` (전체 교체), `src/main.tsx` (전체 교체), `src/App.test.tsx` (전체 교체)

**Interfaces:**
- Consumes: `useGame`, `GameProvider` (Task 8), `activeProfile`, `createGameStore`, `GameStore` (Task 8), `STAGES`, `UNITS` (Task 3), `isStageUnlocked`, `levelFromXp` (Task 5), `displayStreak` (Task 4), `browserStorage` (Task 6), `MemoryKV` (Task 6), 컴포넌트 (Task 9)
- Produces:
  - `renderApp(opts?: { kv?: MemoryKV; setup?: (store: GameStore) => void }): { store; kv; user }` — 시드 42, 오늘 `2026-10-10`, 프로필 id `p1, p2…`
  - `typeNumber(user, n: number)`, `withProfile(store)` (`하늘`/`🐶` 추가)
  - 화면 컴포넌트: `ProfileSelect()`, `StageMap()`, `Lesson({ stageId })`, `Result({ stageId, summary })`, `Parent()`
  - 단계 노드 접근성 이름: `"{title} 단계"`, 잠기면 `"{title} 단계 (잠김)"`

- [ ] **Step 1: 테스트 헬퍼 작성** — `src/test/renderApp.tsx`

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from '../App';
import { GameProvider } from '../state/GameContext';
import { createGameStore, type GameStore } from '../state/store';
import { MemoryKV } from './memoryKV';

export function renderApp(opts: { kv?: MemoryKV; setup?: (store: GameStore) => void } = {}) {
  const kv = opts.kv ?? new MemoryKV();
  let n = 0;
  const store = createGameStore({ kv, nextSeed: () => 42, today: () => '2026-10-10', makeId: () => `p${++n}` });
  opts.setup?.(store);
  const user = userEvent.setup();
  render(
    <GameProvider store={store}>
      <App />
    </GameProvider>,
  );
  return { store, kv, user };
}

export async function typeNumber(user: ReturnType<typeof userEvent.setup>, n: number) {
  for (const d of String(n)) await user.click(screen.getByRole('button', { name: `숫자 ${d}` }));
}

export const withProfile = (store: GameStore) => store.getState().addProfile('하늘', '🐶');
```

- [ ] **Step 2: 실패하는 테스트 작성** — `src/App.test.tsx` (전체 교체)

```tsx
import { screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { renderApp, withProfile } from './test/renderApp';

describe('프로필 선택', () => {
  it('프로필이 없으면 만들기 폼이 나오고, 만들면 맵으로 간다', async () => {
    const { user, store } = renderApp();
    expect(screen.getByRole('heading', { name: '셈셈 병아리' })).toBeInTheDocument();
    const start = screen.getByRole('button', { name: '시작하기' });
    expect(start).toBeDisabled();
    await user.type(screen.getByRole('textbox', { name: '이름' }), '하늘');
    await user.click(screen.getByRole('button', { name: '아바타 🐰' }));
    await user.click(start);
    expect(await screen.findByRole('heading', { name: '10까지 덧셈' })).toBeInTheDocument();
    expect(store.getState().data.profiles[0]).toMatchObject({ name: '하늘', avatar: '🐰' });
  });

  it('프로필이 있으면 카드에서 고른다', async () => {
    const { user } = renderApp({
      setup: (s) => {
        withProfile(s);
        s.getState().goto({ name: 'profiles' });
      },
    });
    await user.click(screen.getByRole('button', { name: /하늘/ }));
    expect(await screen.findByRole('heading', { name: '10까지 덧셈' })).toBeInTheDocument();
  });
});

describe('단계 맵', () => {
  it('첫 단계만 열려 있고 다음 단계는 잠겨 있다', () => {
    renderApp({ setup: withProfile });
    expect(screen.getByRole('button', { name: '그림 세기 단계' })).toBeEnabled();
    expect(screen.getByRole('button', { name: '합 5까지 단계 (잠김)' })).toBeDisabled();
    expect(screen.getByText('시작!')).toBeInTheDocument();
    expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(6);
  });

  it('모든 단계 열기면 마지막 단계도 열린다', () => {
    renderApp({
      setup: (s) => {
        withProfile(s);
        s.getState().setUnlockAll('p1', true);
      },
    });
    expect(screen.getByRole('button', { name: '곱셈 나눗셈 섞기 단계' })).toBeEnabled();
  });

  it('상단 바에 스트릭·레벨·소리 토글이 있다', async () => {
    const { user, store } = renderApp({ setup: withProfile });
    expect(screen.getByLabelText('연속 0일')).toBeInTheDocument();
    expect(screen.getByLabelText('레벨 1, 0 XP')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '소리 끄기' }));
    expect(store.getState().data.settings.soundOn).toBe(false);
    expect(screen.getByRole('button', { name: '소리 켜기' })).toBeInTheDocument();
  });

  it('단계를 누르면 레슨 화면으로 간다', async () => {
    const { user, store } = renderApp({ setup: withProfile });
    await user.click(screen.getByRole('button', { name: '그림 세기 단계' }));
    expect(store.getState().screen).toEqual({ name: 'lesson', stageId: 'u1s1' });
  });
});
```

- [ ] **Step 3: 실패 확인**

Run: `npx vitest run src/App.test.tsx`
Expected: FAIL — `GameProvider`/`createGameStore`는 있지만 `App`이 스토어를 쓰지 않아 `시작하기` 버튼을 찾지 못함

- [ ] **Step 4: 구현**

`src/ui/components/TopBar.tsx`:
```tsx
import { levelFromXp } from '../../core/scoring';
import { displayStreak } from '../../core/streak';
import { useGame } from '../../state/GameContext';
import { activeProfile } from '../../state/store';

export function TopBar() {
  const profile = useGame(activeProfile);
  const soundOn = useGame((s) => s.data.settings.soundOn);
  const setSound = useGame((s) => s.setSound);
  const goto = useGame((s) => s.goto);
  const today = useGame((s) => s.today);
  if (!profile) return null;
  const streak = displayStreak(profile.streak, today());
  const level = levelFromXp(profile.xp);
  return (
    <header className="topbar">
      <button className="chip" aria-label="프로필 바꾸기" onClick={() => goto({ name: 'profiles' })}>
        {profile.avatar}
      </button>
      <span className="chip chip-fire" aria-label={`연속 ${streak}일`}>🔥 {streak}</span>
      <span className="chip chip-xp" aria-label={`레벨 ${level}, ${profile.xp} XP`}>⭐ Lv.{level}</span>
      <span className="spacer" />
      <button className="chip" aria-label={soundOn ? '소리 끄기' : '소리 켜기'} onClick={() => setSound(!soundOn)}>
        {soundOn ? '🔊' : '🔇'}
      </button>
      <button className="chip" aria-label="부모 설정" onClick={() => goto({ name: 'parent' })}>
        ⚙️
      </button>
    </header>
  );
}
```

`src/ui/screens/ProfileSelect.tsx`:
```tsx
import { useState } from 'react';
import { useGame } from '../../state/GameContext';
import { Button3D } from '../components/Button3D';
import { Mascot } from '../components/Mascot';

const AVATARS = ['🐶', '🐱', '🐰', '🦊', '🐼', '🐯', '🐸', '🐵'];

export function ProfileSelect() {
  const profiles = useGame((s) => s.data.profiles);
  const selectProfile = useGame((s) => s.selectProfile);
  const addProfile = useGame((s) => s.addProfile);
  const [adding, setAdding] = useState(profiles.length === 0);
  const [name, setName] = useState('');
  const [avatar, setAvatar] = useState(AVATARS[0]);

  return (
    <main className="screen screen-center">
      <Mascot mood="happy" speech={adding ? '이름을 알려줘!' : '누가 공부할까?'} />
      <h1 className="title">셈셈 병아리</h1>
      {adding ? (
        <form
          className="add-form"
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) addProfile(name, avatar);
          }}
        >
          <input
            className="name-input"
            aria-label="이름"
            placeholder="이름"
            maxLength={8}
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <div className="avatar-row">
            {AVATARS.map((a) => (
              <button
                key={a}
                type="button"
                className={`avatar-pick ${a === avatar ? 'on' : ''}`}
                aria-label={`아바타 ${a}`}
                aria-pressed={a === avatar}
                onClick={() => setAvatar(a)}
              >
                {a}
              </button>
            ))}
          </div>
          <Button3D type="submit" full disabled={!name.trim()}>
            시작하기
          </Button3D>
          {profiles.length > 0 && (
            <Button3D variant="white" full onClick={() => setAdding(false)}>
              취소
            </Button3D>
          )}
        </form>
      ) : (
        <div className="profile-grid">
          {profiles.map((p) => (
            <button key={p.id} className="profile-card" onClick={() => selectProfile(p.id)}>
              <span className="profile-avatar">{p.avatar}</span>
              <span className="display">{p.name}</span>
            </button>
          ))}
          <button className="profile-card" aria-label="프로필 추가" onClick={() => setAdding(true)}>
            <span className="profile-avatar">＋</span>
            <span className="display">추가</span>
          </button>
        </div>
      )}
    </main>
  );
}
```

`src/ui/screens/StageMap.tsx`:
```tsx
import { motion } from 'framer-motion';
import { useEffect, useRef, type CSSProperties } from 'react';
import { isStageUnlocked } from '../../core/scoring';
import { STAGES, UNITS } from '../../core/stages';
import { useGame } from '../../state/GameContext';
import { activeProfile } from '../../state/store';
import { TopBar } from '../components/TopBar';

// 지그재그 경로 가로 위치(px)
const OFFSETS = [0, 56, 84, 56, 0, -56, -84, -56];

export function StageMap() {
  const profile = useGame(activeProfile);
  const goto = useGame((s) => s.goto);
  const currentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    currentRef.current?.scrollIntoView?.({ block: 'center' });
  }, []);

  if (!profile) return null;
  const current = STAGES.find((s) => isStageUnlocked(s.id, profile) && (profile.stages[s.id]?.crowns ?? 0) < 3);

  return (
    <>
      <TopBar />
      <main className="screen map">
        {UNITS.map((u) => (
          <section key={u.unit} className="unit">
            <div className="unit-banner" style={{ background: u.color }}>
              <div className="unit-label">유닛 {u.unit}</div>
              <h2>{u.title}</h2>
            </div>
            <div className="unit-path">
              {STAGES.filter((s) => s.unit === u.unit).map((s) => {
                const crowns = profile.stages[s.id]?.crowns ?? 0;
                const unlocked = isStageUnlocked(s.id, profile);
                const isCurrent = s.id === current?.id;
                const state = crowns >= 3 ? 'done' : unlocked ? 'open' : 'locked';
                return (
                  <div
                    key={s.id}
                    ref={isCurrent ? currentRef : undefined}
                    className="node-wrap"
                    style={{ transform: `translateX(${OFFSETS[STAGES.indexOf(s) % OFFSETS.length]}px)` }}
                  >
                    {isCurrent && <div className="node-start display">시작!</div>}
                    <motion.button
                      className={`node ${state}`}
                      style={{ '--c': u.color } as CSSProperties}
                      disabled={!unlocked}
                      aria-label={`${s.title} 단계${unlocked ? '' : ' (잠김)'}`}
                      animate={isCurrent ? { y: [0, -6, 0] } : undefined}
                      transition={isCurrent ? { duration: 1.4, repeat: Infinity } : undefined}
                      onClick={() => goto({ name: 'lesson', stageId: s.id })}
                    >
                      {state === 'done' ? '👑' : state === 'open' ? u.icon : '🔒'}
                    </motion.button>
                    <div className="node-title">{s.title}</div>
                    <div className="node-crowns" aria-hidden>
                      {[0, 1, 2].map((i) => (
                        <span key={i} className={i < crowns ? 'on' : ''} />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </main>
    </>
  );
}
```

임시 화면 3개 (Task 11·12에서 교체):

`src/ui/screens/Lesson.tsx`:
```tsx
export function Lesson({ stageId }: { stageId: string }) {
  return <main className="screen">레슨 {stageId}</main>;
}
```

`src/ui/screens/Result.tsx`:
```tsx
import type { LessonSummary } from '../../core/progress';

export function Result({ stageId, summary }: { stageId: string; summary: LessonSummary }) {
  return <main className="screen">결과 {stageId} +{summary.xpGained}</main>;
}
```

`src/ui/screens/Parent.tsx`:
```tsx
export function Parent() {
  return <main className="screen">부모 설정</main>;
}
```

`src/App.tsx` (전체 교체):
```tsx
import { useGame } from './state/GameContext';
import { activeProfile } from './state/store';
import { Lesson } from './ui/screens/Lesson';
import { Parent } from './ui/screens/Parent';
import { ProfileSelect } from './ui/screens/ProfileSelect';
import { Result } from './ui/screens/Result';
import { StageMap } from './ui/screens/StageMap';

export function App() {
  const screen = useGame((s) => s.screen);
  const profile = useGame(activeProfile);

  let content;
  if (screen.name === 'parent') content = <Parent />;
  else if (!profile || screen.name === 'profiles') content = <ProfileSelect />;
  else if (screen.name === 'lesson') content = <Lesson stageId={screen.stageId} />;
  else if (screen.name === 'result') content = <Result stageId={screen.stageId} summary={screen.summary} />;
  else content = <StageMap />;

  return <div className="app">{content}</div>;
}
```

`src/main.tsx` (전체 교체):
```tsx
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App';
import { browserStorage } from './core/storage';
import { GameProvider } from './state/GameContext';
import { createGameStore } from './state/store';
import './ui/theme.css';

const store = createGameStore({ kv: browserStorage() });

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <GameProvider store={store}>
      <App />
    </GameProvider>
  </StrictMode>,
);
```

- [ ] **Step 5: 통과 확인**

Run: `npm test` → Expected: 전부 PASS
Run: `npx tsc` → Expected: 에러 없음

- [ ] **Step 6: Commit**

```bash
git add src/App.tsx src/App.test.tsx src/main.tsx src/test/renderApp.tsx src/ui/components/TopBar.tsx src/ui/screens/
git commit -m "feat(calculator-game): 프로필 선택과 지그재그 단계 맵

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 11: 레슨 화면 + 결과 화면

**Files:**
- Create: `src/ui/components/QuestionView.tsx`, `src/ui/screens/Lesson.test.tsx`
- Modify: `src/ui/screens/Lesson.tsx` (전체 교체), `src/ui/screens/Result.tsx` (전체 교체)

**Interfaces:**
- Consumes: `generateLesson`, `OP_SYMBOL` (Task 3), `getStage` (Task 3), `startLesson`, `submitAnswer`, `nextQuestion`, `currentItem`, `lessonProgress`, `toOutcome` (Task 7), `playCorrect`, `playWrong`, `playFanfare`, `vibrate` (Task 9), 컴포넌트 (Task 9), `renderApp`, `typeNumber`, `withProfile` (Task 10)
- Produces: `QuestionView({ q, typed, selected, onSelect, disabled })`, 완성된 `Lesson`, `Result`. 확인 버튼 이름 `확인`, 그만두기 버튼 `그만하기`, 결과 제목 `레슨 끝!` 또는 `{title} 완료! 👑`, 결과 버튼 `계속하기`.

- [ ] **Step 1: 실패하는 테스트 작성** — `src/ui/screens/Lesson.test.tsx`

테스트는 스토어와 같은 시드(42)로 `generateLesson`을 호출해 화면에 나올 문제를 미리 안다.

```tsx
import { screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { generateLesson } from '../../core/generator';
import { getStage } from '../../core/stages';
import type { Question } from '../../core/types';
import { renderApp, typeNumber, withProfile } from '../../test/renderApp';

type User = ReturnType<typeof renderApp>['user'];

async function answerWith(user: User, q: Question, value: number) {
  if (q.kind === 'choice' || q.kind === 'picture') {
    await user.click(screen.getByRole('button', { name: String(value) }));
  } else {
    await typeNumber(user, value);
  }
  await user.click(screen.getByRole('button', { name: '확인' }));
}

async function openStage(user: User, title: string) {
  await user.click(await screen.findByRole('button', { name: `${title} 단계` }));
}

describe('레슨', () => {
  it('모두 맞히면 결과 화면이 나오고 XP 130을 받는다', async () => {
    const { user, store } = renderApp({ setup: withProfile });
    await openStage(user, '그림 세기');
    const qs = generateLesson(getStage('u1s1'), 0, 42);
    for (const q of qs) {
      await answerWith(user, q, q.answer);
      expect(await screen.findByText('잘했어! 🎉')).toBeInTheDocument();
      await user.click(screen.getByRole('button', { name: '계속' }));
    }
    expect(await screen.findByRole('heading', { name: '레슨 끝!' })).toBeInTheDocument();
    expect(screen.getByText('+130')).toBeInTheDocument();
    expect(screen.getByText('100%')).toBeInTheDocument();
    expect(store.getState().data.profiles[0].xp).toBe(130);
    await user.click(screen.getByRole('button', { name: '계속하기' }));
    expect(store.getState().screen).toEqual({ name: 'map' });
  });

  it('틀리면 하트가 줄고 정답을 보여주며, 그 문제가 끝에 다시 나온다', async () => {
    const { user } = renderApp({ setup: withProfile });
    await openStage(user, '그림 세기');
    const qs = generateLesson(getStage('u1s1'), 0, 42);
    const first = qs[0];
    const wrong = first.choices ? first.choices.find((c) => c !== first.answer)! : first.answer + 1;
    await answerWith(user, first, wrong);
    expect(await screen.findByText('괜찮아, 다시 해보자!')).toBeInTheDocument();
    expect(screen.getByText(String(first.answer), { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByLabelText('하트 4개')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '계속' }));
    for (const q of qs.slice(1)) {
      await answerWith(user, q, q.answer);
      await user.click(await screen.findByRole('button', { name: '계속' }));
    }
    expect(await screen.findByText('다시 풀어보기')).toBeInTheDocument();
  });

  it('답을 고르기 전에는 확인 버튼이 비활성이다', async () => {
    const { user } = renderApp({ setup: withProfile });
    await openStage(user, '그림 세기');
    expect(screen.getByRole('button', { name: '확인' })).toBeDisabled();
  });

  it('그만하기를 누르면 맵으로 돌아간다', async () => {
    const { user, store } = renderApp({ setup: withProfile });
    await openStage(user, '그림 세기');
    await user.click(screen.getByRole('button', { name: '그만하기' }));
    expect(store.getState().screen).toEqual({ name: 'map' });
  });

  it('나눗셈 첫 단계는 힌트를 보여준다', async () => {
    const { user } = renderApp({
      setup: (s) => {
        withProfile(s);
        s.getState().setUnlockAll('p1', true);
      },
    });
    await openStage(user, '2단·5단 나누기');
    expect(screen.getByText(/구구단 거꾸로/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run src/ui/screens/Lesson.test.tsx`
Expected: FAIL — `확인` 버튼을 찾지 못함 (임시 Lesson 화면)

- [ ] **Step 3: 구현**

`src/ui/components/QuestionView.tsx`:
```tsx
import type { ReactNode } from 'react';
import { OP_SYMBOL } from '../../core/generator';
import type { Question } from '../../core/types';
import { Button3D } from './Button3D';

interface Props {
  q: Question;
  typed: string;
  selected: number | null;
  onSelect: (value: number) => void;
  disabled: boolean;
}

function prompt(q: Question): string {
  if (q.kind === 'blank') return '빈칸에 들어갈 수는?';
  if (q.kind === 'picture') return q.op === 'add' ? '모두 몇 개일까?' : '남은 건 몇 개일까?';
  return '정답은?';
}

function Pictures({ q }: { q: Question }) {
  if (q.op === 'add') {
    return (
      <div className="pics" aria-hidden>
        <span className="pic-group">{Array.from({ length: q.a }, (_, i) => <span key={i}>🍎</span>)}</span>
        <span className="pic-op">+</span>
        <span className="pic-group">{Array.from({ length: q.b }, (_, i) => <span key={i}>🍎</span>)}</span>
      </div>
    );
  }
  return (
    <div className="pics" aria-hidden>
      <span className="pic-group">
        {Array.from({ length: q.a }, (_, i) => (
          <span key={i} className={i >= q.a - q.b ? 'pic-gone' : ''}>🍪</span>
        ))}
      </span>
    </div>
  );
}

export function QuestionView({ q, typed, selected, onSelect, disabled }: Props) {
  const isChoice = q.kind === 'choice' || q.kind === 'picture';
  const slot = (content: ReactNode) => <span className="slot">{content}</span>;
  return (
    <div className="question">
      <div className="q-prompt">{prompt(q)}</div>
      {q.kind === 'picture' && <Pictures q={q} />}
      <div className="q-expr">
        <span>{q.a}</span>
        <span>{OP_SYMBOL[q.op]}</span>
        {q.kind === 'blank' ? slot(typed || '?') : <span>{q.b}</span>}
        <span>=</span>
        {q.kind === 'blank' ? <span>{q.result}</span> : slot(isChoice ? (selected ?? '?') : typed || '?')}
      </div>
      {isChoice && q.choices && (
        <div className="choices">
          {q.choices.map((c) => (
            <Button3D key={c} variant="white" selected={selected === c} disabled={disabled} onClick={() => onSelect(c)}>
              {c}
            </Button3D>
          ))}
        </div>
      )}
    </div>
  );
}
```

`src/ui/screens/Lesson.tsx` (전체 교체):
```tsx
import { useEffect, useState } from 'react';
import { generateLesson } from '../../core/generator';
import { currentItem, lessonProgress, nextQuestion, startLesson, submitAnswer, toOutcome } from '../../core/lesson';
import { getStage } from '../../core/stages';
import { playCorrect, playFanfare, playWrong, vibrate } from '../../audio/sfx';
import { useGame } from '../../state/GameContext';
import { activeProfile } from '../../state/store';
import { Button3D } from '../components/Button3D';
import { FeedbackSheet } from '../components/FeedbackSheet';
import { Hearts } from '../components/Hearts';
import { Keypad } from '../components/Keypad';
import { Mascot, type Mood } from '../components/Mascot';
import { ProgressBar } from '../components/ProgressBar';
import { QuestionView } from '../components/QuestionView';

export function Lesson({ stageId }: { stageId: string }) {
  const stage = getStage(stageId);
  const profile = useGame(activeProfile);
  const nextSeed = useGame((s) => s.nextSeed);
  const settings = useGame((s) => s.data.settings);
  const goto = useGame((s) => s.goto);
  const finishLesson = useGame((s) => s.finishLesson);

  const [lesson, setLesson] = useState(() =>
    startLesson(generateLesson(stage, profile?.stages[stageId]?.crowns ?? 0, nextSeed())),
  );
  const [selected, setSelected] = useState<number | null>(null);
  const [typed, setTyped] = useState('');
  const [left, setLeft] = useState<number | null>(null);

  const item = currentItem(lesson);
  const answering = lesson.phase === 'answering';
  const isChoice = item?.q.kind === 'choice' || item?.q.kind === 'picture';

  const check = (value: number | null) => {
    if (lesson.phase !== 'answering') return;
    const next = submitAnswer(lesson, value);
    setLesson(next);
    if (next.last?.correct) {
      if (settings.soundOn) playCorrect();
    } else {
      if (settings.soundOn) playWrong();
      vibrate(80);
    }
  };

  const onConfirm = () => {
    if (isChoice) {
      if (selected !== null) check(selected);
    } else if (typed !== '') {
      check(Number(typed));
    }
  };

  const onContinue = () => {
    const next = nextQuestion(lesson);
    setSelected(null);
    setTyped('');
    if (next.phase === 'done') {
      if (settings.soundOn) playFanfare();
      finishLesson(stageId, toOutcome(next));
      return;
    }
    setLesson(next);
  };

  // 타이머 (부모 설정에서 켰을 때만)
  useEffect(() => {
    if (!settings.timerSec || lesson.phase !== 'answering') {
      setLeft(null);
      return;
    }
    const limit = settings.timerSec;
    const started = Date.now();
    setLeft(limit);
    const id = setInterval(() => setLeft(limit - Math.floor((Date.now() - started) / 1000)), 250);
    return () => clearInterval(id);
  }, [lesson.index, lesson.phase, settings.timerSec]);

  useEffect(() => {
    if (left !== null && left <= 0) check(null);
    // check는 매 렌더 새로 만들어지므로 left 변화에만 반응한다
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [left]);

  const last = lesson.last;
  const mood: Mood = lesson.phase === 'feedback' ? (last?.correct ? 'happy' : 'cheer') : 'idle';
  let message = '';
  if (lesson.phase === 'feedback' && last) {
    if (last.correct && lesson.inARow >= 3) message = `${lesson.inARow}개 연속! 불붙었다 🔥`;
    else if (!last.correct && !last.review && !last.timedOut && lesson.hearts === 0)
      message = '하트가 다 떨어졌어. 잠깐 쉬어가자! 그래도 끝까지 풀어보자 💪';
    else if (!last.correct && !last.review) message = '이 문제는 마지막에 한 번 더 나올 거야.';
  }

  return (
    <main className="screen lesson">
      <div className="lesson-top">
        <button className="icon-btn" aria-label="그만하기" onClick={() => goto({ name: 'map' })}>
          ✕
        </button>
        <ProgressBar value={lessonProgress(lesson)} />
        <Hearts count={lesson.hearts} />
      </div>
      {left !== null && (
        <div className="timer" aria-label={`남은 시간 ${Math.max(0, left)}초`}>
          ⏱ {Math.max(0, left)}
        </div>
      )}
      {item && (
        <>
          {item.review && <div className="review-tag">다시 풀어보기</div>}
          {stage.hint && lesson.index === 0 && <div className="hint">{stage.hint}</div>}
          <QuestionView q={item.q} typed={typed} selected={selected} onSelect={setSelected} disabled={!answering} />
          <Mascot mood={mood} size={72} />
          {!isChoice && <Keypad value={typed} onChange={setTyped} disabled={!answering} />}
        </>
      )}
      <div className="lesson-bottom">
        {answering && (
          <Button3D full disabled={isChoice ? selected === null : typed === ''} onClick={onConfirm}>
            확인
          </Button3D>
        )}
      </div>
      {lesson.phase === 'feedback' && last && item && (
        <FeedbackSheet
          correct={last.correct}
          timedOut={last.timedOut}
          correctText={String(item.q.answer)}
          message={message}
          onContinue={onContinue}
        />
      )}
    </main>
  );
}
```

ESLint는 이 프로젝트에 설정돼 있지 않다. `eslint-disable` 주석은 의도를 남기는 용도이며, 지워도 동작은 같다.

`src/ui/screens/Result.tsx` (전체 교체):
```tsx
import type { CSSProperties } from 'react';
import type { LessonSummary } from '../../core/progress';
import { getStage } from '../../core/stages';
import { useGame } from '../../state/GameContext';
import { Button3D } from '../components/Button3D';
import { Confetti } from '../components/Confetti';
import { Mascot } from '../components/Mascot';

function Stat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="stat" style={{ '--sc': color } as CSSProperties}>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}

export function Result({ stageId, summary }: { stageId: string; summary: LessonSummary }) {
  const goto = useGame((s) => s.goto);
  const stage = getStage(stageId);
  const speech = summary.passed
    ? summary.perfect
      ? '완벽해! 최고야!'
      : '레슨 통과! 잘했어!'
    : '끝까지 풀었어! 다시 도전해 보자!';

  return (
    <main className="screen screen-center result">
      {summary.passed && <Confetti />}
      <Mascot mood="happy" size={120} speech={speech} />
      <h1>{summary.stageCompleted ? `${stage.title} 완료! 👑` : '레슨 끝!'}</h1>
      {summary.levelAfter > summary.levelBefore && <div className="levelup">레벨 업! Lv.{summary.levelAfter} 🎉</div>}
      <div className="stats">
        <Stat label="얻은 XP" value={`+${summary.xpGained}`} color="#FFC800" />
        <Stat label="정답률" value={`${Math.round(summary.accuracy * 100)}%`} color="#58CC02" />
        <Stat label="연속" value={`🔥 ${summary.streak}일`} color="#FF9600" />
      </div>
      <div className="crowns-row" aria-label={`왕관 ${summary.crowns}개`}>
        {[0, 1, 2].map((i) => (
          <span key={i} className={i < summary.crowns ? 'on' : 'off'}>👑</span>
        ))}
      </div>
      <Button3D full onClick={() => goto({ name: 'map' })}>
        계속하기
      </Button3D>
    </main>
  );
}
```

- [ ] **Step 4: 통과 확인**

Run: `npm test` → Expected: 전부 PASS
Run: `npx tsc` → Expected: 에러 없음

- [ ] **Step 5: Commit**

```bash
git add src/ui/components/QuestionView.tsx src/ui/screens/Lesson.tsx src/ui/screens/Lesson.test.tsx src/ui/screens/Result.tsx
git commit -m "feat(calculator-game): 레슨 화면(객관식·키패드·빈칸·그림)과 결과 화면

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 12: 부모 설정 화면

**Files:**
- Modify: `src/ui/screens/Parent.tsx` (전체 교체)
- Test: `src/ui/screens/Parent.test.tsx`

**Interfaces:**
- Consumes: `makeParentChallenge` (Task 7), `mulberry32` (Task 2), `STAGES` (Task 3), `levelFromXp` (Task 5), 스토어 액션 (Task 8), `Keypad`, `Button3D` (Task 9), `renderApp`, `typeNumber`, `withProfile` (Task 10)
- Produces: `Parent()` — 잠금 제목 `어른 확인 🔒`, 오답 문구 `다시 해보세요`, 열린 뒤 제목 `부모 설정`, 타이머 버튼 `끔/10초/15초/20초`, 콤보박스 `시작 단계`, 버튼 `여기부터 시작`, 체크박스 `모든 단계 열기`, `효과음`, 버튼 `프로필 삭제`, `닫기`

- [ ] **Step 1: 실패하는 테스트 작성** — `src/ui/screens/Parent.test.tsx`

```tsx
import { screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { makeParentChallenge } from '../../core/parentLock';
import { mulberry32 } from '../../core/random';
import { renderApp, typeNumber, withProfile } from '../../test/renderApp';

type User = ReturnType<typeof renderApp>['user'];
const challenge = () => makeParentChallenge(mulberry32(42)); // renderApp의 시드와 같다

async function unlock(user: User) {
  await user.click(screen.getByRole('button', { name: '부모 설정' }));
  await typeNumber(user, challenge().answer);
  await user.click(screen.getByRole('button', { name: '확인' }));
  await screen.findByRole('heading', { name: '부모 설정' });
}

describe('부모 설정', () => {
  it('어른 문제를 틀리면 열리지 않고, 맞히면 열린다', async () => {
    const { user } = renderApp({ setup: withProfile });
    await user.click(screen.getByRole('button', { name: '부모 설정' }));
    expect(screen.getByRole('heading', { name: '어른 확인 🔒' })).toBeInTheDocument();
    await typeNumber(user, challenge().answer + 1);
    await user.click(screen.getByRole('button', { name: '확인' }));
    expect(screen.getByText('다시 해보세요')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '부모 설정' })).toBeNull();
    await typeNumber(user, challenge().answer);
    await user.click(screen.getByRole('button', { name: '확인' }));
    expect(await screen.findByRole('heading', { name: '부모 설정' })).toBeInTheDocument();
  });

  it('돌아가기를 누르면 맵으로 간다', async () => {
    const { user, store } = renderApp({ setup: withProfile });
    await user.click(screen.getByRole('button', { name: '부모 설정' }));
    await user.click(screen.getByRole('button', { name: '돌아가기' }));
    expect(store.getState().screen).toEqual({ name: 'map' });
  });

  it('타이머와 효과음을 바꾼다', async () => {
    const { user, store } = renderApp({ setup: withProfile });
    await unlock(user);
    await user.click(screen.getByRole('button', { name: '15초' }));
    expect(store.getState().data.settings.timerSec).toBe(15);
    expect(screen.getByRole('button', { name: '15초' })).toHaveAttribute('aria-pressed', 'true');
    await user.click(screen.getByRole('checkbox', { name: '효과음' }));
    expect(store.getState().data.settings.soundOn).toBe(false);
  });

  it('시작 단계 지정과 모든 단계 열기', async () => {
    const { user, store } = renderApp({ setup: withProfile });
    await unlock(user);
    await user.selectOptions(screen.getByRole('combobox', { name: '시작 단계' }), 'u4s1');
    await user.click(screen.getByRole('button', { name: '여기부터 시작' }));
    expect(store.getState().data.profiles[0].stages.u3s4.crowns).toBe(3);
    await user.click(screen.getByRole('checkbox', { name: '모든 단계 열기' }));
    expect(store.getState().data.profiles[0].unlockAll).toBe(true);
  });

  it('연산별 정답률을 보여준다', async () => {
    const { user } = renderApp({
      setup: (s) => {
        withProfile(s);
        const stats = { add: { correct: 8, total: 10 }, sub: { correct: 0, total: 0 }, mul: { correct: 0, total: 0 }, div: { correct: 0, total: 0 } };
        s.getState().finishLesson('u1s1', { firstTryCorrect: 8, total: 10, heartsLeft: 3, stats });
        s.getState().goto({ name: 'map' });
      },
    });
    await unlock(user);
    expect(screen.getByText('덧셈 80% (8/10)')).toBeInTheDocument();
    expect(screen.getByText('뺄셈 -')).toBeInTheDocument();
  });

  it('프로필 삭제는 확인을 받은 뒤 지운다', async () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const { user, store } = renderApp({ setup: withProfile });
    await unlock(user);
    await user.click(screen.getByRole('button', { name: '프로필 삭제' }));
    expect(confirm).toHaveBeenCalled();
    expect(store.getState().data.profiles).toHaveLength(0);
    confirm.mockRestore();
  });

  it('저장 기록을 못 불러왔으면 안내한다', async () => {
    const { MemoryKV } = await import('../../test/memoryKV');
    const { STORAGE_KEY } = await import('../../core/storage');
    const kv = new MemoryKV();
    kv.setItem(STORAGE_KEY, 'garbage');
    const { user } = renderApp({ kv, setup: withProfile });
    await unlock(user);
    expect(screen.getByText(/기록을 불러오지 못했어요/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `npx vitest run src/ui/screens/Parent.test.tsx`
Expected: FAIL — `어른 확인 🔒` 제목을 찾지 못함

- [ ] **Step 3: 구현** — `src/ui/screens/Parent.tsx` (전체 교체)

```tsx
import { useState } from 'react';
import { makeParentChallenge, type ParentChallenge } from '../../core/parentLock';
import { mulberry32 } from '../../core/random';
import { levelFromXp } from '../../core/scoring';
import { STAGES } from '../../core/stages';
import type { Op, Profile } from '../../core/types';
import { useGame } from '../../state/GameContext';
import { activeProfile } from '../../state/store';
import { Button3D } from '../components/Button3D';
import { Keypad } from '../components/Keypad';

const OP_NAMES: Record<Op, string> = { add: '덧셈', sub: '뺄셈', mul: '곱셈', div: '나눗셈' };
const TIMER_OPTIONS: (number | null)[] = [null, 10, 15, 20];

function ParentGate({ challenge, onPass, onCancel }: { challenge: ParentChallenge; onPass: () => void; onCancel: () => void }) {
  const [typed, setTyped] = useState('');
  const [wrong, setWrong] = useState(false);
  const confirm = () => {
    if (Number(typed) === challenge.answer) {
      onPass();
    } else {
      setWrong(true);
      setTyped('');
    }
  };
  return (
    <main className="screen screen-center">
      <h2>어른 확인 🔒</h2>
      <p>아래 문제를 풀면 부모 설정이 열려요.</p>
      <div className="q-expr">
        <span>{challenge.a}</span>
        <span>×</span>
        <span>{challenge.b}</span>
        <span>=</span>
        <span className="slot">{typed || '?'}</span>
      </div>
      {wrong && <div className="error-text">다시 해보세요</div>}
      <Keypad
        value={typed}
        onChange={(v) => {
          setTyped(v);
          setWrong(false);
        }}
      />
      <Button3D full disabled={!typed} onClick={confirm}>
        확인
      </Button3D>
      <Button3D variant="white" full onClick={onCancel}>
        돌아가기
      </Button3D>
    </main>
  );
}

function ProfileAdmin({ profile }: { profile: Profile }) {
  const setStartStage = useGame((s) => s.setStartStage);
  const setUnlockAll = useGame((s) => s.setUnlockAll);
  const removeProfile = useGame((s) => s.removeProfile);
  const [start, setStart] = useState(STAGES[0].id);

  return (
    <section className="panel" aria-label={`${profile.name} 설정`}>
      <h3>
        {profile.avatar} {profile.name} · Lv.{levelFromXp(profile.xp)} · {profile.xp} XP
      </h3>
      <div className="stat-list">
        {(Object.keys(OP_NAMES) as Op[]).map((op) => {
          const s = profile.stats[op];
          const text = s.total ? `${Math.round((s.correct / s.total) * 100)}% (${s.correct}/${s.total})` : '-';
          return <div key={op}>{`${OP_NAMES[op]} ${text}`}</div>;
        })}
      </div>
      <div className="row">
        <select aria-label="시작 단계" value={start} onChange={(e) => setStart(e.target.value)}>
          {STAGES.map((s) => (
            <option key={s.id} value={s.id}>
              유닛 {s.unit} · {s.title}
            </option>
          ))}
        </select>
        <button className="small-btn" onClick={() => setStartStage(profile.id, start)}>
          여기부터 시작
        </button>
      </div>
      <label className="toggle">
        <input type="checkbox" checked={profile.unlockAll} onChange={(e) => setUnlockAll(profile.id, e.target.checked)} />
        모든 단계 열기
      </label>
      <button
        className="small-btn danger"
        onClick={() => {
          if (window.confirm(`${profile.name} 프로필을 지울까요? 기록이 모두 사라져요.`)) removeProfile(profile.id);
        }}
      >
        프로필 삭제
      </button>
    </section>
  );
}

export function Parent() {
  const nextSeed = useGame((s) => s.nextSeed);
  const data = useGame((s) => s.data);
  const loadError = useGame((s) => s.loadError);
  const hasProfile = useGame((s) => activeProfile(s) !== null);
  const goto = useGame((s) => s.goto);
  const setTimer = useGame((s) => s.setTimer);
  const setSound = useGame((s) => s.setSound);
  const [challenge] = useState(() => makeParentChallenge(mulberry32(nextSeed())));
  const [unlocked, setUnlocked] = useState(false);

  const close = () => goto(hasProfile ? { name: 'map' } : { name: 'profiles' });

  if (!unlocked) return <ParentGate challenge={challenge} onPass={() => setUnlocked(true)} onCancel={close} />;

  return (
    <main className="screen parent">
      <div className="parent-header">
        <h1>부모 설정</h1>
        <button className="small-btn" onClick={close}>
          닫기
        </button>
      </div>
      {loadError && <div className="notice">저장된 기록을 불러오지 못했어요. 새 기록으로 시작합니다.</div>}
      <section className="panel">
        <h3>타이머</h3>
        <div className="seg">
          {TIMER_OPTIONS.map((t) => (
            <button key={String(t)} aria-pressed={data.settings.timerSec === t} onClick={() => setTimer(t)}>
              {t === null ? '끔' : `${t}초`}
            </button>
          ))}
        </div>
        <label className="toggle">
          <input type="checkbox" checked={data.settings.soundOn} onChange={(e) => setSound(e.target.checked)} />
          효과음
        </label>
      </section>
      {data.profiles.map((p) => (
        <ProfileAdmin key={p.id} profile={p} />
      ))}
      <Button3D variant="blue" full onClick={() => goto({ name: 'profiles' })}>
        프로필 추가·바꾸기
      </Button3D>
    </main>
  );
}
```

- [ ] **Step 4: 통과 확인**

Run: `npm test` → Expected: 전부 PASS
Run: `npx tsc` → Expected: 에러 없음

- [ ] **Step 5: Commit**

```bash
git add src/ui/screens/Parent.tsx src/ui/screens/Parent.test.tsx
git commit -m "feat(calculator-game): 어른 문제 잠금이 걸린 부모 설정

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 13: PWA(홈 화면 추가·오프라인) + 빌드 + 실제 화면 확인

**Files:**
- Create: `public/icon.svg`, `README.md`, 생성되는 `public/*.png`, `public/favicon.ico`
- Modify: `vite.config.ts`, `index.html`, `package.json`

**Interfaces:**
- Consumes: 완성된 앱 전체
- Produces: `npm run build` 결과물 `dist/` (manifest + 서비스워커 포함)

- [ ] **Step 1: PWA 의존성 설치**

```bash
npm install -D vite-plugin-pwa @vite-pwa/assets-generator
```

- [ ] **Step 2: 앱 아이콘 작성** — `public/icon.svg`

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="96" fill="#58CC02"/>
  <g transform="translate(56 64) scale(4)">
    <path d="M44 14 Q50 2 56 14" stroke="#F5A700" stroke-width="4" fill="none" stroke-linecap="round"/>
    <ellipse cx="17" cy="60" rx="9" ry="14" fill="#F5C200" transform="rotate(20 17 60)"/>
    <ellipse cx="83" cy="60" rx="9" ry="14" fill="#F5C200" transform="rotate(-20 83 60)"/>
    <circle cx="50" cy="55" r="36" fill="#FFD43B"/>
    <path d="M31 50 Q38 41 45 50" stroke="#3C3C3C" stroke-width="4" fill="none" stroke-linecap="round"/>
    <path d="M55 50 Q62 41 69 50" stroke="#3C3C3C" stroke-width="4" fill="none" stroke-linecap="round"/>
    <circle cx="29" cy="61" r="5" fill="#FF9AA2" opacity="0.7"/>
    <circle cx="71" cy="61" r="5" fill="#FF9AA2" opacity="0.7"/>
    <path d="M44 58 L56 58 L50 67 Z" fill="#FF9600"/>
  </g>
</svg>
```

- [ ] **Step 3: PNG 아이콘 생성**

Run: `npx pwa-assets-generator --preset minimal-2023 public/icon.svg`
Expected: `public/` 에 `pwa-64x64.png`, `pwa-192x192.png`, `pwa-512x512.png`, `maskable-icon-512x512.png`, `apple-touch-icon-180x180.png`, `favicon.ico` 생성

- [ ] **Step 4: Vite 설정에 PWA 추가** — `vite.config.ts` 전체 교체

테스트 실행(mode `test`) 때는 PWA 플러그인을 빼서 테스트가 서비스워커 생성에 영향받지 않게 한다.

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
              name: '셈셈 병아리',
              short_name: '셈셈',
              description: '7살 어린이를 위한 계산력 게임',
              lang: 'ko',
              theme_color: '#58CC02',
              background_color: '#ffffff',
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
            workbox: {
              globPatterns: ['**/*.{js,css,html,svg,png,ico}'],
              runtimeCaching: [
                {
                  urlPattern: /^https:\/\/fonts\.(googleapis|gstatic)\.com\/.*/,
                  handler: 'CacheFirst',
                  options: {
                    cacheName: 'google-fonts',
                    expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 },
                    cacheableResponse: { statuses: [0, 200] },
                  },
                },
              ],
            },
          }),
        ]),
  ],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
}));
```

- [ ] **Step 5: `index.html`에 아이콘 링크 추가** — `<title>` 아래에 삽입

```html
    <link rel="icon" href="favicon.ico" sizes="48x48" />
    <link rel="icon" href="icon.svg" type="image/svg+xml" />
    <link rel="apple-touch-icon" href="apple-touch-icon-180x180.png" />
```

- [ ] **Step 6: README 작성** — `README.md`

````markdown
# 셈셈 병아리

7살 어린이를 위한 듀오링고풍 계산력 게임 (덧셈·뺄셈·구구단·나눗셈).

```bash
npm install
npm run dev      # 개발 서버 (같은 Wi-Fi의 폰에서 표시되는 Network 주소로 접속)
npm test         # 테스트
npm run build    # dist/ 정적 파일 생성 (PWA)
npm run preview  # 빌드 결과 미리보기
```

- 설계: `docs/superpowers/specs/2026-10-10-calculator-game-design.md`
- 기록은 기기 브라우저(localStorage)에만 저장된다.
````

- [ ] **Step 7: 전체 테스트와 빌드 확인**

Run: `npm test` → Expected: 전부 PASS
Run: `npm run build` → Expected: 에러 없음, `dist/manifest.webmanifest`, `dist/sw.js` 생성

```bash
ls dist/manifest.webmanifest dist/sw.js
```

- [ ] **Step 8: 실제 화면 확인 (수동)**

Run: `npm run preview` (백그라운드) 후 브라우저를 모바일 뷰포트(390×844)로 열어 확인한다. `run` 스킬이나 브라우저 도구를 쓸 수 있으면 스크린샷을 남긴다.

확인 목록:
- 프로필 만들기 → 맵: 유닛 배너 색, 지그재그 노드, "시작!" 표시, 현재 노드가 통통 튐
- 레슨: 진행 바·하트, 그림 문제 사과, 객관식 4개, 키패드, 확인 → 하단 시트가 올라옴, 정답 시 병아리가 뜀
- 결과: 폭죽, XP·정답률·연속 카드, 왕관
- 부모 설정: 어른 문제 잠금, 타이머 켜면 레슨에 ⏱ 표시
- 소리: 정답 "딩동", 오답 "뿅", 완료 팡파르 (소리 토글 동작)
- 버튼을 누를 때 3D로 눌리는 느낌, 가로 스크롤 없음

문제를 발견하면 고친 뒤 `npm test`를 다시 돌린다.

- [ ] **Step 9: Commit**

```bash
git add public/ vite.config.ts index.html package.json package-lock.json README.md
git status --short .   # dist/ 가 없어야 한다
git commit -m "feat(calculator-game): PWA 설정(홈 화면 추가·오프라인)과 앱 아이콘

Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

## 범위 밖 (이 계획에서 하지 않음)

- 실제 배포(GitHub Pages / Vercel): 구현이 끝난 뒤 사용자에게 확인을 받고 별도로 진행한다.
- 2단계 항목: Capacitor 앱 빌드, 클라우드 동기화, 스티커 도감, 스토어 출시 준비.
