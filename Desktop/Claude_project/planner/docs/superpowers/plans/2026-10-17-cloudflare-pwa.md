# 칭찬스티커 플래너 Cloudflare PWA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 가족이 함께 쓰는 칭찬스티커 플래너를 PC 없이 동작하는 PWA로 Cloudflare Pages에 배포한다.

**Architecture:** `planner/web/`에 정적 PWA(`public/`)와 Pages Functions(`functions/api/[[path]].js` → `src/api.js`)를 둔다. 데이터는 D1(`schema.sql`), 계산은 브라우저의 `public/stats.js`(stats.py 이식). 모든 API는 가족 비밀번호 헤더로 보호한다.

**Tech Stack:** Vanilla JS(ES modules), Cloudflare Pages + Functions + D1, wrangler 4, Node 24 (`node --test`, `node:sqlite`로 가짜 D1), Pillow(아이콘 생성).

**Spec:** `docs/superpowers/specs/2026-10-17-cloudflare-pwa-design.md`

## Global Constraints

- 새 코드는 모두 `planner/web/` 아래. 기존 Streamlit 앱(`planner/*.py`)은 수정하지 않는다.
- 날짜는 `'YYYY-MM-DD'` 문자열, 요일 번호는 월=0 … 일=6, `days`는 DB에 `'024'` 같은 문자열·API/JS에서는 정수 배열.
- 인증 헤더: `X-Family-Key: encodeURIComponent(비밀번호)`. 서버는 `encodeURIComponent(env.FAMILY_PASSWORD)`와 상수 시간 비교.
- 비밀번호는 코드·저장소에 넣지 않는다 (`.dev.vars`는 gitignore).
- 외부 라이브러리는 런타임에 쓰지 않는다 (차트도 CSS 막대).
- git 커밋은 사용자가 요청할 때만 (각 Task 끝의 커밋 단계 없음).
- 공개 배포(Task 5의 deploy) 직전 사용자 확인 필수.

---

### Task 1: 스캐폴드 + stats.js

**Files:**
- Create: `web/package.json`, `web/.gitignore`, `web/public/stats.js`
- Test: `web/tests/stats.test.js`

**Interfaces:**
- Produces: `addDays(iso, n) → iso`, `weekday(iso) → 0..6`, `weekStart(iso) → iso`, `stickerKey(habitId, date) → string`,
  `dailyCounts(habits, stickers, start, end, today) → {iso: [earned, possible]}`,
  `summary(...) → {earned, possible, rate}`, `streak(habits, stickers, today) → number`.
  `habits` = `[{id, weekStart, days}]`, `stickers` = `Set<stickerKey>`.

- [ ] **Step 1: 스캐폴드**

```json file=web/package.json
{
  "name": "sticker-planner",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "node --test \"tests/*.test.js\"",
    "dev": "wrangler pages dev --port 8788",
    "deploy": "wrangler pages deploy"
  }
}
```

```text file=web/.gitignore
node_modules/
.wrangler/
.dev.vars
```

- [ ] **Step 2: 실패하는 테스트 작성** (test_stats.py 이식)

```js file=web/tests/stats.test.js
import test from "node:test";
import assert from "node:assert/strict";
import { addDays, dailyCounts, stickerKey, streak, summary, weekday, weekStart } from "../public/stats.js";

const MON = "2026-10-05"; // 월요일
const ALL = [0, 1, 2, 3, 4, 5, 6];
const MWF = [0, 2, 4];
const h = (id, days = ALL) => ({ id, weekStart: MON, days });
const s = (...pairs) => new Set(pairs.map(([id, d]) => stickerKey(id, d)));

test("addDays / weekday / weekStart", () => {
  assert.equal(addDays("2026-10-31", 1), "2026-11-01");
  assert.equal(addDays(MON, -1), "2026-10-04");
  assert.equal(weekday(MON), 0);
  assert.equal(weekday("2026-10-11"), 6);
  assert.equal(weekStart("2026-10-07"), MON);
  assert.equal(weekStart(MON), MON);
  assert.equal(weekStart("2026-10-11"), MON);
});

test("summary counts only days up to today", () => {
  const r = summary([h(1), h(2)], s([1, MON], [2, MON], [1, "2026-10-06"]), MON, "2026-10-11", "2026-10-06");
  assert.deepEqual(r, { earned: 3, possible: 4, rate: 0.75 });
});

test("summary ignores days outside habit week", () => {
  assert.equal(summary([h(1)], s(), "2026-10-01", "2026-10-31", "2026-10-31").possible, 7);
});

test("summary ignores stickers outside slots", () => {
  assert.equal(summary([h(1)], s([1, "2026-10-20"]), "2026-10-01", "2026-10-31", "2026-10-31").earned, 0);
});

test("summary rate zero when nothing possible", () => {
  assert.deepEqual(summary([], s(), MON, MON, MON), { earned: 0, possible: 0, rate: 0 });
});

test("dailyCounts", () => {
  assert.deepEqual(dailyCounts([h(1), h(2)], s([1, MON]), MON, "2026-10-06", "2026-10-06"),
    { [MON]: [1, 2], "2026-10-06": [0, 2] });
});

test("streak counts back from today when today complete", () => {
  assert.equal(streak([h(1)], s([1, MON], [1, "2026-10-06"], [1, "2026-10-07"]), "2026-10-07"), 3);
});

test("streak starts yesterday when today incomplete", () => {
  assert.equal(streak([h(1)], s([1, MON], [1, "2026-10-06"]), "2026-10-07"), 2);
});

test("streak breaks on partial day", () => {
  assert.equal(streak([h(1), h(2)], s([1, MON], [2, MON], [1, "2026-10-06"]), "2026-10-06"), 1);
  assert.equal(streak([h(1), h(2)], s([1, MON], [2, MON]), MON), 1);
  assert.equal(streak([], s(), MON), 0);
});

test("summary counts only scheduled weekdays", () => {
  const r = summary([h(1, MWF)], s([1, MON], [1, "2026-10-07"], [1, "2026-10-09"]), MON, "2026-10-11", "2026-10-11");
  assert.deepEqual(r, { earned: 3, possible: 3, rate: 1 });
});

test("dailyCounts skips unscheduled days", () => {
  assert.deepEqual(dailyCounts([h(1, MWF)], s(), MON, "2026-10-07", "2026-10-07"),
    { [MON]: [0, 1], "2026-10-07": [0, 1] });
});

test("streak skips days without scheduled habits", () => {
  assert.equal(streak([h(1, MWF)], s([1, MON], [1, "2026-10-07"]), "2026-10-08"), 2);
});

test("streak still breaks on missed scheduled day", () => {
  assert.equal(streak([h(1, MWF)], s([1, "2026-10-07"]), "2026-10-08"), 1);
});
```

- [ ] **Step 3: 실패 확인** — Run: `cd web && npm test` / Expected: FAIL (`Cannot find module .../public/stats.js`)

- [ ] **Step 4: 구현**

```js file=web/public/stats.js
// 달성률·연속 달성일 계산 (planner/stats.py 이식). 날짜는 'YYYY-MM-DD' 문자열.
// habits: [{id, weekStart, days}] — weekStart부터 7일 중 days(월=0 … 일=6) 요일만 체크 대상
// stickers: Set of stickerKey(habitId, date)

const DAY_MS = 86400000;
const toMs = (iso) => Date.parse(iso + "T00:00:00Z");
const toIso = (ms) => new Date(ms).toISOString().slice(0, 10);

export const addDays = (iso, n) => toIso(toMs(iso) + n * DAY_MS);
export const weekday = (iso) => (new Date(toMs(iso)).getUTCDay() + 6) % 7;
export const weekStart = (iso) => addDays(iso, -weekday(iso));
export const stickerKey = (habitId, date) => `${habitId}|${date}`;

/** 기간 내 각 날짜(오늘까지)의 [받은 스티커, 받을 수 있었던 스티커]. 할 일 없는 날은 빠진다. */
export function dailyCounts(habits, stickers, start, end, today) {
  const counts = {};
  const last = end < today ? end : today;
  for (let d = start; d <= last; d = addDays(d, 1)) {
    const wd = weekday(d);
    const active = habits.filter((h) => h.weekStart <= d && d < addDays(h.weekStart, 7) && h.days.includes(wd));
    if (active.length) counts[d] = [active.filter((h) => stickers.has(stickerKey(h.id, d))).length, active.length];
  }
  return counts;
}

export function summary(habits, stickers, start, end, today) {
  let earned = 0;
  let possible = 0;
  for (const [e, p] of Object.values(dailyCounts(habits, stickers, start, end, today))) {
    earned += e;
    possible += p;
  }
  return { earned, possible, rate: possible ? earned / possible : 0 };
}

/** 모든 습관을 지킨 날이 이어진 일수. 할 일 없는 날은 건너뛰고, 오늘이 미완이면 어제부터 센다. */
export function streak(habits, stickers, today) {
  if (!habits.length) return 0;
  const earliest = habits.reduce((m, h) => (h.weekStart < m ? h.weekStart : m), habits[0].weekStart);
  const counts = dailyCounts(habits, stickers, earliest, today, today);
  let n = 0;
  for (const d of Object.keys(counts).sort().reverse()) {
    const [e, p] = counts[d];
    if (e === p) n++;
    else if (d !== today) break;
  }
  return n;
}
```

- [ ] **Step 5: 통과 확인** — Run: `cd web && npm test` / Expected: 13 pass

---

### Task 2: D1 스키마 + API

**Files:**
- Create: `web/schema.sql`, `web/src/api.js`, `web/functions/api/[[path]].js`
- Test: `web/tests/fake-d1.js`, `web/tests/api.test.js`

**Interfaces:**
- Consumes: 없음 (stats.js와 독립)
- Produces: `handle(request: Request, env: {DB, FAMILY_PASSWORD}) → Promise<Response>`.
  응답 JSON: `GET state` → `{monthGoals:[{id,month,title}], weekGoals:[{id,monthGoalId,weekStart,title}], habits:[{id,weekGoalId,title,days:number[]}], stickers:[{habitId,date}]}`;
  `POST` → 201 `{id}`; `DELETE`/`PUT stickers` → `{ok:true}`; 오류 → `{error}` + 400/401/404/500.

- [ ] **Step 1: 스키마와 가짜 D1**

```sql file=web/schema.sql
CREATE TABLE IF NOT EXISTS month_goal (
    id INTEGER PRIMARY KEY, month TEXT NOT NULL, title TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS week_goal (
    id INTEGER PRIMARY KEY,
    month_goal_id INTEGER NOT NULL REFERENCES month_goal(id) ON DELETE CASCADE,
    week_start TEXT NOT NULL, title TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS habit (
    id INTEGER PRIMARY KEY,
    week_goal_id INTEGER NOT NULL REFERENCES week_goal(id) ON DELETE CASCADE,
    title TEXT NOT NULL, days TEXT NOT NULL DEFAULT '0123456');
CREATE TABLE IF NOT EXISTS sticker (
    habit_id INTEGER NOT NULL REFERENCES habit(id) ON DELETE CASCADE,
    date TEXT NOT NULL, PRIMARY KEY (habit_id, date));
```

```js file=web/tests/fake-d1.js
// node:sqlite로 흉내 낸 D1 (prepare → bind → all/first/run). D1처럼 외래키를 강제한다.
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";

export function fakeD1() {
  const db = new DatabaseSync(":memory:");
  db.exec("PRAGMA foreign_keys = ON");
  db.exec(readFileSync(new URL("../schema.sql", import.meta.url), "utf8"));
  const stmt = (sql, args = []) => ({
    bind: (...a) => stmt(sql, a),
    all: async () => ({ results: db.prepare(sql).all(...args) }),
    first: async () => db.prepare(sql).get(...args) ?? null,
    run: async () => {
      const r = db.prepare(sql).run(...args);
      return { meta: { last_row_id: Number(r.lastInsertRowid), changes: Number(r.changes) } };
    },
  });
  return { prepare: (sql) => stmt(sql) };
}
```

- [ ] **Step 2: 실패하는 테스트 작성**

```js file=web/tests/api.test.js
import test from "node:test";
import assert from "node:assert/strict";
import { handle } from "../src/api.js";
import { fakeD1 } from "./fake-d1.js";

const KEY = "우리 가족 화이팅";

function setup(env = { DB: fakeD1(), FAMILY_PASSWORD: KEY }) {
  return async (method, path, body, key = KEY) => {
    const headers = { "content-type": "application/json" };
    if (key !== null) headers["x-family-key"] = encodeURIComponent(key);
    const init = { method, headers };
    if (body !== undefined) init.body = typeof body === "string" ? body : JSON.stringify(body);
    const res = await handle(new Request("https://planner.test/api/" + path, init), env);
    return { status: res.status, data: await res.json() };
  };
}

async function seed(call) {
  const m = (await call("POST", "month-goals", { month: "2026-10", title: "체중 2kg 감량" })).data.id;
  const w = (await call("POST", "week-goals", { monthGoalId: m, weekStart: "2026-10-05", title: "운동 3회" })).data.id;
  const h = (await call("POST", "habits", { weekGoalId: w, title: "헬스장", days: [4, 0, 2, 2] })).data.id;
  return { m, w, h };
}

test("rejects missing or wrong password", async () => {
  const call = setup();
  assert.equal((await call("GET", "state", undefined, null)).status, 401);
  assert.equal((await call("GET", "state", undefined, "틀림")).status, 401);
  assert.equal((await call("GET", "state")).status, 200);
});

test("refuses when password not configured", async () => {
  const call = setup({ DB: fakeD1() });
  assert.equal((await call("GET", "state", undefined, "")).status, 500);
});

test("creates hierarchy and returns state", async () => {
  const call = setup();
  const { m, w, h } = await seed(call);
  const { status, data } = await call("GET", "state");
  assert.equal(status, 200);
  assert.deepEqual(data, {
    monthGoals: [{ id: m, month: "2026-10", title: "체중 2kg 감량" }],
    weekGoals: [{ id: w, monthGoalId: m, weekStart: "2026-10-05", title: "운동 3회" }],
    habits: [{ id: h, weekGoalId: w, title: "헬스장", days: [0, 2, 4] }],
    stickers: [],
  });
});

test("POST returns 201", async () => {
  const call = setup();
  assert.equal((await call("POST", "month-goals", { month: "2026-10", title: "m" })).status, 201);
});

test("validates input", async () => {
  const call = setup();
  const { w } = await seed(call);
  const cases = [
    ["month-goals", { month: "2026-13", title: "x" }],
    ["month-goals", { month: "2026-10", title: "   " }],
    ["week-goals", { monthGoalId: 1, weekStart: "2026-10-06", title: "화요일 시작" }],
    ["week-goals", { monthGoalId: 1, weekStart: "2026-02-30", title: "없는 날짜" }],
    ["week-goals", { monthGoalId: 999, weekStart: "2026-10-05", title: "없는 부모" }],
    ["habits", { weekGoalId: w, title: "요일 없음", days: [] }],
    ["habits", { weekGoalId: w, title: "범위 밖", days: [7] }],
  ];
  for (const [path, body] of cases) assert.equal((await call("POST", path, body)).status, 400, JSON.stringify(body));
  assert.equal((await call("POST", "month-goals", "{not json")).status, 400);
  assert.equal((await call("POST", "month-goals", "null")).status, 400);
});

test("sticker on is idempotent and off removes", async () => {
  const call = setup();
  const { h } = await seed(call);
  await call("PUT", "stickers", { habitId: h, date: "2026-10-05", on: true });
  await call("PUT", "stickers", { habitId: h, date: "2026-10-05", on: true });
  assert.deepEqual((await call("GET", "state")).data.stickers, [{ habitId: h, date: "2026-10-05" }]);
  await call("PUT", "stickers", { habitId: h, date: "2026-10-05", on: false });
  assert.deepEqual((await call("GET", "state")).data.stickers, []);
  assert.equal((await call("PUT", "stickers", { habitId: h, date: "2026-10-05", on: "yes" })).status, 400);
  assert.equal((await call("PUT", "stickers", { habitId: 999, date: "2026-10-05", on: true })).status, 400);
});

test("deleting month goal cascades", async () => {
  const call = setup();
  const { m, h } = await seed(call);
  await call("PUT", "stickers", { habitId: h, date: "2026-10-05", on: true });
  assert.equal((await call("DELETE", `month-goals/${m}`)).status, 200);
  assert.deepEqual((await call("GET", "state")).data, { monthGoals: [], weekGoals: [], habits: [], stickers: [] });
});

test("deleting habit only removes that habit", async () => {
  const call = setup();
  const { w, h } = await seed(call);
  const h2 = (await call("POST", "habits", { weekGoalId: w, title: "물 2L", days: [0, 1, 2, 3, 4, 5, 6] })).data.id;
  await call("DELETE", `habits/${h}`);
  assert.deepEqual((await call("GET", "state")).data.habits.map((x) => x.id), [h2]);
});

test("unknown route is 404", async () => {
  const call = setup();
  assert.equal((await call("GET", "nope")).status, 404);
  assert.equal((await call("DELETE", "stickers/1")).status, 404);
  assert.equal((await call("DELETE", "habits/abc")).status, 400);
});
```

- [ ] **Step 3: 실패 확인** — Run: `cd web && npm test` / Expected: api.test.js FAIL (`Cannot find module .../src/api.js`)

- [ ] **Step 4: 구현**

```js file=web/src/api.js
// /api/* 처리. env.DB: D1, env.FAMILY_PASSWORD: 가족 비밀번호(Cloudflare secret)
class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}
const bad = (message) => {
  throw new HttpError(400, message);
};

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });

async function sameSecret(a, b) {
  const digest = async (s) => new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)));
  const [x, y] = await Promise.all([digest(a), digest(b)]);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

// ── 입력 검증 ─────────────────────────────────────────
function title(v) {
  if (typeof v !== "string" || !v.trim() || v.trim().length > 100) bad("title");
  return v.trim();
}
function id(v) {
  if (!Number.isInteger(v) || v <= 0) bad("id");
  return v;
}
function isoDate(v) {
  const ms = typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v) ? Date.parse(v + "T00:00:00Z") : NaN;
  if (Number.isNaN(ms) || new Date(ms).toISOString().slice(0, 10) !== v) bad("date");
  return v;
}
function monday(v) {
  if (new Date(isoDate(v) + "T00:00:00Z").getUTCDay() !== 1) bad("weekStart must be a Monday");
  return v;
}
function month(v) {
  if (typeof v !== "string" || !/^\d{4}-(0[1-9]|1[0-2])$/.test(v)) bad("month");
  return v;
}
function days(v) {
  if (!Array.isArray(v) || !v.length || v.some((d) => !Number.isInteger(d) || d < 0 || d > 6)) bad("days");
  return [...new Set(v)].sort().join("");
}

// ── DB ────────────────────────────────────────────────
async function getState(db) {
  const all = async (sql) => (await db.prepare(sql).all()).results;
  const [m, w, h, s] = await Promise.all([
    all("SELECT * FROM month_goal ORDER BY id"),
    all("SELECT * FROM week_goal ORDER BY week_start, id"),
    all("SELECT * FROM habit ORDER BY id"),
    all("SELECT * FROM sticker ORDER BY date, habit_id"),
  ]);
  return {
    monthGoals: m.map((r) => ({ id: r.id, month: r.month, title: r.title })),
    weekGoals: w.map((r) => ({ id: r.id, monthGoalId: r.month_goal_id, weekStart: r.week_start, title: r.title })),
    habits: h.map((r) => ({ id: r.id, weekGoalId: r.week_goal_id, title: r.title, days: [...r.days].map(Number) })),
    stickers: s.map((r) => ({ habitId: r.habit_id, date: r.date })),
  };
}

async function run(db, sql, ...args) {
  try {
    return await db.prepare(sql).bind(...args).run();
  } catch (e) {
    if (/FOREIGN KEY/i.test(String(e?.message))) bad("parent not found");
    throw e;
  }
}

const TABLES = { "month-goals": "month_goal", "week-goals": "week_goal", habits: "habit" };

export async function handle(request, env) {
  try {
    if (!env.FAMILY_PASSWORD) return json({ error: "server not configured" }, 500);
    const key = request.headers.get("x-family-key") ?? "";
    if (!(await sameSecret(key, encodeURIComponent(env.FAMILY_PASSWORD)))) return json({ error: "unauthorized" }, 401);

    const db = env.DB;
    const [res, rid, extra] = new URL(request.url).pathname.replace(/^\/api\/?/, "").split("/").filter(Boolean);
    const method = request.method;
    let body = null;
    if (method === "POST" || method === "PUT") {
      body = await request.json().catch(() => null);
      if (body === null || typeof body !== "object" || Array.isArray(body)) bad("invalid json body");
    }
    if (extra !== undefined) return json({ error: "not found" }, 404);

    if (method === "GET" && res === "state" && !rid) return json(await getState(db));

    if (method === "POST" && !rid) {
      const insert = async (sql, ...args) => json({ id: (await run(db, sql, ...args)).meta.last_row_id }, 201);
      if (res === "month-goals")
        return await insert("INSERT INTO month_goal (month, title) VALUES (?, ?)", month(body.month), title(body.title));
      if (res === "week-goals")
        return await insert("INSERT INTO week_goal (month_goal_id, week_start, title) VALUES (?, ?, ?)",
          id(body.monthGoalId), monday(body.weekStart), title(body.title));
      if (res === "habits")
        return await insert("INSERT INTO habit (week_goal_id, title, days) VALUES (?, ?, ?)",
          id(body.weekGoalId), title(body.title), days(body.days));
    }

    if (method === "DELETE" && TABLES[res] && rid) {
      await run(db, `DELETE FROM ${TABLES[res]} WHERE id = ?`, id(Number(rid)));
      return json({ ok: true });
    }

    if (method === "PUT" && res === "stickers" && !rid) {
      const habitId = id(body.habitId);
      const date = isoDate(body.date);
      if (typeof body.on !== "boolean") bad("on");
      if (body.on) await run(db, "INSERT OR IGNORE INTO sticker (habit_id, date) VALUES (?, ?)", habitId, date);
      else await run(db, "DELETE FROM sticker WHERE habit_id = ? AND date = ?", habitId, date);
      return json({ ok: true });
    }

    return json({ error: "not found" }, 404);
  } catch (e) {
    if (e instanceof HttpError) return json({ error: e.message }, e.status);
    console.error(e);
    return json({ error: "server error" }, 500);
  }
}
```

```js file=web/functions/api/[[path]].js
import { handle } from "../../src/api.js";

export const onRequest = ({ request, env }) => handle(request, env);
```

- [ ] **Step 5: 통과 확인** — Run: `cd web && npm test` / Expected: 22 pass (stats 13 + api 9)

---

### Task 3: PWA 화면

**Files:**
- Create: `web/public/index.html`, `web/public/app.js`, `web/public/style.css`, `web/public/manifest.webmanifest`, `web/public/sw.js`, `web/scripts/make_icons.py`, 생성물 `web/public/icon-192.png`, `icon-512.png`, `apple-touch-icon.png`

**Interfaces:**
- Consumes: Task 1의 `stats.js` export 전부, Task 2의 API 응답 형태.
- Produces: 없음 (최종 화면).

화면 로직은 DOM 의존이라 단위 테스트 대신 Task 4에서 실제 브라우저(로컬 서버)로 확인한다. 이 Task의 검증은 문법 검사와 아이콘 생성.

- [ ] **Step 1: index.html / manifest / sw.js**

```html file=web/public/index.html
<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#f5b700">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="칭찬스티커">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" href="icon-192.png">
<link rel="apple-touch-icon" href="apple-touch-icon.png">
<link rel="stylesheet" href="style.css">
<title>칭찬스티커 플래너</title>
<script type="module" src="app.js"></script>
</head>
<body>
<div id="app"><p class="muted center">불러오는 중…</p></div>
</body>
</html>
```

```json file=web/public/manifest.webmanifest
{
  "name": "칭찬스티커 플래너",
  "short_name": "칭찬스티커",
  "lang": "ko",
  "start_url": "./",
  "scope": "./",
  "display": "standalone",
  "background_color": "#fffaf0",
  "theme_color": "#f5b700",
  "icons": [
    { "src": "icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "icon-512.png", "sizes": "512x512", "type": "image/png" },
    { "src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}
```

```js file=web/public/sw.js
// 앱 셸만 캐시(네트워크 우선, 실패 시 캐시). /api는 가로채지 않는다.
const CACHE = "planner-v1";
const SHELL = ["./", "app.js", "stats.js", "style.css", "manifest.webmanifest", "icon-192.png", "icon-512.png", "apple-touch-icon.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        if (res.ok && !res.redirected) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
        }
        return res;
      })
      .catch(() => caches.match(e.request).then((hit) => hit || (e.request.mode === "navigate" ? caches.match("./") : undefined))),
  );
});
```

- [ ] **Step 2: style.css**

```css file=web/public/style.css
:root {
  --bg: #fffaf0; --fg: #2b2620; --muted: #7a6f63; --card: #ffffff; --line: #eadfcb;
  --accent: #f5b700; --accent-soft: #fff1c2; --blue: #3b7ddd; --ok: #2f7d4f; --warn: #9a6412; --err: #c53030;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1c1a17; --fg: #f1ebe2; --muted: #a89d8f; --card: #26231f; --line: #3a352e;
    --accent: #f5b700; --accent-soft: #4a3d12; --blue: #6aa1f0; --ok: #5fc48a; --warn: #e0a84a; --err: #f08080;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
  font: 16px/1.5 system-ui, -apple-system, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif; }
#app { max-width: 720px; margin: 0 auto; padding: 12px 16px calc(24px + env(safe-area-inset-bottom)); }
header { display: flex; justify-content: space-between; align-items: center; }
h1 { font-size: 1.4rem; margin: 8px 0; }
h2 { font-size: 1.1rem; margin: 24px 0 8px; }
h3, h4 { margin: 0; font-size: 1rem; }
.muted { color: var(--muted); }
.center { text-align: center; margin-top: 30vh; }
button { font: inherit; cursor: pointer; }
button:disabled { opacity: .5; cursor: not-allowed; }
.link { border: 0; background: none; color: var(--muted); text-decoration: underline; }

nav { display: flex; gap: 4px; border-bottom: 1px solid var(--line); margin: 8px 0 12px;
  position: sticky; top: 0; background: var(--bg); z-index: 1; }
.tab { flex: 1; padding: 10px; border: 0; border-bottom: 3px solid transparent; background: none; color: var(--muted); }
.tab.on { color: var(--fg); font-weight: 700; border-color: var(--accent); }

.stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
@media (min-width: 560px) { .stats { grid-template-columns: repeat(4, 1fr); } }
.stat { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 10px; }
.stat .label { font-size: .85rem; color: var(--muted); }
.stat .big { font-size: 1.5rem; font-weight: 700; }
.bar { height: 8px; background: var(--line); border-radius: 4px; overflow: hidden; margin-top: 6px; }
.bar i { display: block; height: 100%; background: var(--accent); transition: width .3s; }

.checks { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
.checks label { display: flex; align-items: center; gap: 12px; background: var(--card);
  border: 1px solid var(--line); border-radius: 12px; padding: 12px; cursor: pointer; }
.checks label.done { background: var(--accent-soft); border-color: var(--accent); }
.checks input { width: 22px; height: 22px; accent-color: var(--accent); }
.checks .sticker { font-size: 1.6rem; }
.checks small { display: block; color: var(--muted); font-size: .8rem; }
.empty { background: var(--card); border: 1px dashed var(--line); border-radius: 12px; padding: 16px; color: var(--muted); }

.banner { padding: 10px 12px; border-radius: 10px; margin: 8px 0; }
.banner.ok { background: color-mix(in srgb, var(--ok) 15%, transparent); color: var(--ok); }
.banner.warn { background: color-mix(in srgb, var(--warn) 15%, transparent); color: var(--warn); }
.banner.err { background: color-mix(in srgb, var(--err) 15%, transparent); color: var(--err); }

.card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 12px; margin: 12px 0; }
.head { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.week { border-top: 1px solid var(--line); padding: 10px 0; margin-top: 10px; }
.habits { list-style: none; padding: 0; margin: 8px 0; }
.habits li { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 4px 0 4px 12px; }
.habits small { color: var(--muted); }
.row { display: flex; gap: 6px; margin: 8px 0; }
.row input { flex: 1; min-width: 0; }
input, select { font: inherit; padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--bg); color: var(--fg); }
form button { padding: 8px 14px; border: 0; border-radius: 8px; background: var(--accent); color: #2b2620; font-weight: 600; }
.del { border: 1px solid var(--line); background: none; color: var(--muted); border-radius: 8px; padding: 4px 10px; font-size: .85rem; flex-shrink: 0; }
.days { display: flex; flex-wrap: wrap; gap: 4px; }
.day { display: flex; align-items: center; gap: 2px; border: 1px solid var(--line); border-radius: 8px; padding: 4px 8px; font-size: .9rem; }

.cal { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
.cal .hd { text-align: center; font-weight: 600; color: var(--muted); font-size: .85rem; }
.cal .cell { background: var(--card); border: 1px solid var(--line); border-radius: 8px; min-height: 60px;
  padding: 4px; font-size: 12px; word-break: break-all; }
.cal .full { background: var(--accent-soft); border-color: var(--accent); }
.cal .today { outline: 2px solid var(--blue); outline-offset: -2px; }
.empty-star { opacity: .35; }
.hbar { display: grid; grid-template-columns: 60px 1fr 44px; align-items: center; gap: 8px; margin: 6px 0; }
.hbar .bar { margin: 0; height: 14px; }
.goal { margin: 8px 0; }

.lock { max-width: 360px; margin: 20vh auto 0; text-align: center; }
.lock form { display: flex; gap: 6px; }
.lock input { flex: 1; min-width: 0; }
.err-text { color: var(--err); }

.fly { position: fixed; bottom: -40px; font-size: 28px; pointer-events: none; z-index: 10; animation: fly 1.8s ease-out forwards; }
@keyframes fly { to { transform: translateY(-110vh) rotate(200deg); opacity: 0; } }
@media (prefers-reduced-motion: reduce) { .fly { display: none; } .bar i { transition: none; } }
```

- [ ] **Step 3: app.js**

```js file=web/public/app.js
import { addDays, dailyCounts, stickerKey, streak, summary, weekday, weekStart } from "./stats.js";

const WEEKDAYS = "월화수목금토일";
const KEY_STORE = "familyKey";
const POLL_MS = 30000;
const $app = document.getElementById("app");
const ui = { tab: "today", offline: false, error: "", day: "" };
let data = null;

// ── 유틸 ──────────────────────────────────────────────
const pad = (n) => String(n).padStart(2, "0");
const localToday = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const pct = (r) => `${Math.round(r * 100)}%`;
const md = (iso) => `${Number(iso.slice(5, 7))}/${Number(iso.slice(8, 10))}`;
const daysLabel = (days) => (days.length === 7 ? "매일" : days.map((d) => WEEKDAYS[d]).join("·"));

function readKey() { try { return localStorage.getItem(KEY_STORE); } catch { return null; } }
function writeKey(k) { try { if (k === null) localStorage.removeItem(KEY_STORE); else localStorage.setItem(KEY_STORE, k); } catch { /* 저장 불가 시 메모리에만 */ } }
let familyKey = readKey();

function lock(message = "") {
  familyKey = null;
  writeKey(null);
  data = null;
  ui.error = message;
  render();
}

// ── API ───────────────────────────────────────────────
class Unauthorized extends Error {}

async function api(method, path, body) {
  let res;
  try {
    res = await fetch("/api/" + path, {
      method,
      headers: { "content-type": "application/json", "x-family-key": encodeURIComponent(familyKey ?? "") },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    ui.offline = true;
    throw new Error("offline");
  }
  ui.offline = false;
  if (res.status === 401) throw new Unauthorized();
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
  return json;
}

async function load() {
  try {
    data = await api("GET", "state");
    ui.error = "";
  } catch (e) {
    if (e instanceof Unauthorized) return lock("비밀번호가 바뀌었어요. 다시 입력해 주세요.");
    if (!ui.offline) ui.error = "불러오지 못했어요: " + e.message;
  }
  render();
}

async function act(method, path, body) {
  try {
    await api(method, path, body);
  } catch (e) {
    if (e instanceof Unauthorized) return lock("비밀번호가 바뀌었어요. 다시 입력해 주세요.");
    if (!ui.offline) ui.error = "저장하지 못했어요: " + e.message;
  }
  await load();
}

async function unlock(key) {
  familyKey = key;
  try {
    data = await api("GET", "state");
    writeKey(key);
    ui.error = "";
  } catch (e) {
    familyKey = null;
    ui.error = e instanceof Unauthorized ? "비밀번호가 맞지 않아요." : ui.offline ? "인터넷 연결이 필요해요." : e.message;
  }
  render();
}

// ── 화면 계산 ─────────────────────────────────────────
function derive() {
  const today = localToday();
  const weekById = new Map(data.weekGoals.map((w) => [w.id, w]));
  const habits = data.habits
    .filter((h) => weekById.has(h.weekGoalId))
    .map((h) => {
      const w = weekById.get(h.weekGoalId);
      return { ...h, weekStart: w.weekStart, weekTitle: w.title, monthGoalId: w.monthGoalId };
    });
  const stickers = new Set(data.stickers.map((s) => stickerKey(s.habitId, s.date)));
  const month = today.slice(0, 7);
  const monthStart = month + "-01";
  const monthEnd = addDays(addDays(monthStart, 32).slice(0, 7) + "-01", -1);
  const weeks = [];
  for (let w = weekStart(monthStart); w <= monthEnd; w = addDays(w, 7)) weeks.push(w);
  return { today, habits, stickers, month, monthStart, monthEnd, weeks };
}

// ── 화면 ──────────────────────────────────────────────
function render() {
  ui.day = localToday();
  if (!familyKey) return renderLock();
  if (!data) {
    $app.innerHTML = `<p class="muted center">${ui.offline ? "인터넷 연결이 필요해요." : esc(ui.error || "불러오는 중…")}</p>`;
    return;
  }
  const ctx = derive();
  const view = { today: viewToday, goals: viewGoals, board: viewBoard }[ui.tab];
  const tabs = [["today", "오늘"], ["goals", "목표 설정"], ["board", "스티커판"]];
  $app.innerHTML = `
    <header><h1>⭐ 칭찬스티커 플래너</h1><button class="link" data-act="logout">잠그기</button></header>
    ${ui.offline ? `<div class="banner warn">인터넷 연결이 필요해요. 연결되면 자동으로 다시 불러옵니다.</div>` : ""}
    ${ui.error ? `<div class="banner err">${esc(ui.error)}</div>` : ""}
    <nav>${tabs.map(([k, l]) => `<button class="tab ${ui.tab === k ? "on" : ""}" data-tab="${k}">${l}</button>`).join("")}</nav>
    <main>${view(ctx)}</main>`;
}

function renderLock() {
  $app.innerHTML = `
    <div class="lock">
      <h1>⭐ 칭찬스티커 플래너</h1>
      <p class="muted">가족 비밀번호를 입력하세요.</p>
      <form data-form="lock"><input type="password" name="key" autocomplete="current-password" aria-label="가족 비밀번호" required><button>열기</button></form>
      ${ui.error ? `<p class="err-text">${esc(ui.error)}</p>` : ""}
    </div>`;
}

function viewToday({ today, habits, stickers, monthStart, monthEnd }) {
  const ws = weekStart(today);
  const wd = weekday(today);
  const stat = (label, start, end) => {
    const r = summary(habits, stickers, start, end, today);
    return `<div class="stat"><div class="label">${label}</div><div class="big">${pct(r.rate)}</div>
      <div class="muted">⭐ ${r.earned}/${r.possible}</div><div class="bar"><i style="width:${pct(r.rate)}"></i></div></div>`;
  };
  const todays = habits.filter((h) => h.weekStart <= today && today < addDays(h.weekStart, 7) && h.days.includes(wd));
  const allDone = todays.length > 0 && todays.every((h) => stickers.has(stickerKey(h.id, today)));
  const item = (h) => {
    const on = stickers.has(stickerKey(h.id, today));
    return `<li><label class="${on ? "done" : ""}">
      <input type="checkbox" data-sticker="${h.id}" ${on ? "checked" : ""} ${ui.offline ? "disabled" : ""}>
      <span class="sticker">${on ? "⭐" : "☆"}</span>
      <span>${esc(h.title)}<small>${esc(h.weekTitle)}</small></span></label></li>`;
  };
  return `
    <section class="stats">
      ${stat("오늘", today, today)}${stat("이번 주", ws, addDays(ws, 6))}${stat("이번 달", monthStart, monthEnd)}
      <div class="stat"><div class="label">연속 달성</div><div class="big">🔥 ${streak(habits, stickers, today)}일</div></div>
    </section>
    <h2>${md(today)} (${WEEKDAYS[wd]}) 할 일</h2>
    ${todays.length
      ? `<ul class="checks">${todays.map(item).join("")}</ul>`
      : `<p class="empty">오늘 할 습관이 없어요. '목표 설정' 탭에서 이번 주 목표와 일일 습관을 추가하세요.</p>`}
    ${allDone ? `<div class="banner ok">오늘 목표를 모두 달성했어요! 정말 잘했어요 👏</div>` : ""}`;
}

function viewGoals({ today, month, weeks }) {
  const dis = ui.offline ? "disabled" : "";
  const dayPicker = [...WEEKDAYS].map((d, i) => `<label class="day"><input type="checkbox" name="days" value="${i}" checked>${d}</label>`).join("");
  const habitRow = (h) => `<li><span>${esc(h.title)} <small>(${daysLabel(h.days)})</small></span>
    <button class="del" data-del="habits/${h.id}" data-confirm="이 습관과 받은 스티커가 지워집니다." ${dis}>삭제</button></li>`;
  const weekBlock = (w) => `
    <div class="week">
      <div class="head"><h4>📅 ${md(w.weekStart)}주 — ${esc(w.title)}</h4>
        <button class="del" data-del="week-goals/${w.id}" data-confirm="주 목표와 그 아래 습관·스티커가 지워집니다." ${dis}>삭제</button></div>
      <ul class="habits">${data.habits.filter((h) => h.weekGoalId === w.id).map(habitRow).join("")}</ul>
      <form data-form="habit" data-week="${w.id}">
        <div class="row"><input name="title" placeholder="일일 습관 (예: 운동 가기)" maxlength="100" aria-label="일일 습관" required><button ${dis}>습관 추가</button></div>
        <div class="days">${dayPicker}</div>
      </form>
    </div>`;
  const monthCard = (m) => `
    <article class="card">
      <div class="head"><h3>🎯 ${esc(m.title)}</h3>
        <button class="del" data-del="month-goals/${m.id}" data-confirm="월 목표와 그 아래 주 목표·습관·스티커가 모두 지워집니다." ${dis}>삭제</button></div>
      ${data.weekGoals.filter((w) => w.monthGoalId === m.id).map(weekBlock).join("")}
      <form data-form="week" data-month="${m.id}" class="row">
        <select name="weekStart" aria-label="주">${weeks.map((w) => `<option value="${w}" ${w === weekStart(today) ? "selected" : ""}>${md(w)}주</option>`).join("")}</select>
        <input name="title" placeholder="주 목표 (예: 운동 3회)" maxlength="100" aria-label="주 목표" required><button ${dis}>주 목표 추가</button>
      </form>
    </article>`;
  return `
    <p class="muted">${month.slice(0, 4)}년 ${Number(month.slice(5))}월 목표</p>
    <form data-form="month" class="row"><input name="title" placeholder="새 월 목표 (예: 체중 2kg 감량)" maxlength="100" aria-label="새 월 목표" required><button ${dis}>월 목표 추가</button></form>
    ${data.monthGoals.filter((m) => m.month === month).map(monthCard).join("")}`;
}

function viewBoard({ today, habits, stickers, month, monthStart, monthEnd, weeks }) {
  const counts = dailyCounts(habits, stickers, monthStart, monthEnd, today);
  const total = summary(habits, stickers, monthStart, monthEnd, today);
  let cells = [...WEEKDAYS].map((d) => `<div class="hd">${d}</div>`).join("") + "<div></div>".repeat(weekday(monthStart));
  for (let d = monthStart; d <= monthEnd; d = addDays(d, 1)) {
    const [e, p] = counts[d] ?? [0, 0];
    cells += `<div class="cell ${p && e === p ? "full" : ""} ${d === today ? "today" : ""}"><b>${Number(d.slice(8))}</b>
      <div>${"⭐".repeat(e)}<span class="empty-star">${"☆".repeat(p - e)}</span></div></div>`;
  }
  const weekRows = weeks.map((w) => ({ w, ...summary(habits, stickers, w, addDays(w, 6), today) })).filter((r) => r.possible);
  const goalRow = (m) => {
    const r = summary(habits.filter((h) => h.monthGoalId === m.id), stickers, monthStart, monthEnd, today);
    return `<div class="goal"><div>🎯 ${esc(m.title)} — ⭐ ${r.earned}/${r.possible}</div><div class="bar"><i style="width:${pct(r.rate)}"></i></div></div>`;
  };
  return `
    <h2>${Number(month.slice(5))}월 스티커판 — ⭐ ${total.earned}장 (${pct(total.rate)})</h2>
    <div class="cal">${cells}</div>
    <h2>주별 달성률</h2>
    ${weekRows.length
      ? weekRows.map((r) => `<div class="hbar"><span>${md(r.w)}주</span><div class="bar"><i style="width:${pct(r.rate)}"></i></div><b>${pct(r.rate)}</b></div>`).join("")
      : `<p class="muted">아직 기록이 없어요.</p>`}
    <h2>월 목표별 달성률</h2>
    ${data.monthGoals.filter((m) => m.month === month).map(goalRow).join("") || `<p class="muted">이번 달 목표가 없어요.</p>`}`;
}

function celebrate() {
  for (let i = 0; i < 14; i++) {
    const s = document.createElement("span");
    s.className = "fly";
    s.textContent = i % 3 ? "⭐" : "🎉";
    s.style.left = Math.random() * 95 + "vw";
    s.style.animationDelay = Math.random() * 0.4 + "s";
    document.body.appendChild(s);
    setTimeout(() => s.remove(), 2400);
  }
}

// ── 이벤트 ────────────────────────────────────────────
$app.addEventListener("click", (e) => {
  const t = e.target.closest("[data-tab],[data-del],[data-act]");
  if (!t) return;
  if (t.dataset.tab) {
    ui.tab = t.dataset.tab;
    render();
  } else if (t.dataset.del) {
    if (confirm(t.dataset.confirm)) act("DELETE", t.dataset.del);
  } else if (t.dataset.act === "logout") {
    if (confirm("이 기기에서 비밀번호를 지우고 잠글까요?")) lock();
  }
});

$app.addEventListener("change", (e) => {
  const cb = e.target.closest("[data-sticker]");
  if (!cb) return;
  if (cb.checked) celebrate();
  act("PUT", "stickers", { habitId: Number(cb.dataset.sticker), date: localToday(), on: cb.checked });
});

$app.addEventListener("submit", (e) => {
  e.preventDefault();
  const f = e.target;
  const fd = new FormData(f);
  const title = String(fd.get("title") ?? "").trim();
  if (f.dataset.form === "lock") return unlock(String(fd.get("key")));
  if (!title) return;
  if (f.dataset.form === "month") act("POST", "month-goals", { month: localToday().slice(0, 7), title });
  if (f.dataset.form === "week") act("POST", "week-goals", { monthGoalId: Number(f.dataset.month), weekStart: fd.get("weekStart"), title });
  if (f.dataset.form === "habit") {
    const days = fd.getAll("days").map(Number);
    if (!days.length) return alert("요일을 하나 이상 골라 주세요.");
    act("POST", "habits", { weekGoalId: Number(f.dataset.week), title, days });
  }
});

// ── 자동 갱신: 30초마다, 화면 복귀·재연결 시. 입력 중이면 건너뜀 ──
function typing() {
  const a = document.activeElement;
  return !!a && ((a.tagName === "INPUT" && a.type !== "checkbox") || a.tagName === "SELECT");
}

async function poll() {
  if (!familyKey || document.hidden || typing()) return;
  const before = JSON.stringify(data);
  const wasOffline = ui.offline;
  try {
    data = await api("GET", "state");
  } catch (e) {
    if (e instanceof Unauthorized) return lock("비밀번호가 바뀌었어요. 다시 입력해 주세요.");
    if (ui.offline !== wasOffline) render();
    return;
  }
  if (JSON.stringify(data) !== before || wasOffline || ui.day !== localToday()) render();
}

setInterval(poll, POLL_MS);
document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
window.addEventListener("online", poll);

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
render();
if (familyKey) load();
```

- [ ] **Step 4: 아이콘 생성**

```python file=web/scripts/make_icons.py
"""PWA 아이콘 생성: 노란 바탕에 흰 별. 사용법: python scripts/make_icons.py public"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def star_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), "#f5b700")
    cx = cy = size / 2
    outer, inner = size * 0.30, size * 0.30 * 0.45  # maskable 안전 영역(가운데 80%) 안에 들어가게
    points = [
        (cx + (outer if i % 2 == 0 else inner) * math.sin(i * math.pi / 5),
         cy - (outer if i % 2 == 0 else inner) * math.cos(i * math.pi / 5))
        for i in range(10)
    ]
    ImageDraw.Draw(img).polygon(points, fill="white")
    return img


out = Path(sys.argv[1])
for name, size in [("icon-192.png", 192), ("icon-512.png", 512), ("apple-touch-icon.png", 180)]:
    star_icon(size).save(out / name)
    print("wrote", out / name)
```

Run: `cd web && python scripts/make_icons.py public` / Expected: 3개 `wrote ...`

- [ ] **Step 5: 문법 검사** — Run: `cd web && node --check public/app.js && node --check public/sw.js && npm test` / Expected: 오류 없음, 22 pass

---

### Task 4: 로컬 통합 확인 (wrangler pages dev)

**Files:**
- Create: `web/wrangler.toml`, `web/.dev.vars`(gitignore, 테스트용 비밀번호)

**Interfaces:**
- Consumes: Task 1~3 전부.

- [ ] **Step 1: wrangler 설치와 설정**

Run: `cd web && npm install -D wrangler@4`

```toml file=web/wrangler.toml
name = "sticker-planner"
pages_build_output_dir = "public"
compatibility_date = "2026-09-01"

[[d1_databases]]
binding = "DB"
database_name = "sticker-planner"
database_id = "00000000-0000-0000-0000-000000000000" # Task 5에서 `wrangler d1 create` 결과로 교체
```

`.dev.vars` (로컬 전용): `FAMILY_PASSWORD=로컬 테스트 비번`

wrangler가 compatibility_date가 너무 최신이라고 경고하면 경고가 제시하는 날짜로 바꾼다.

- [ ] **Step 2: 로컬 D1 스키마 적용 후 서버 실행**

Run: `cd web && npx wrangler d1 execute sticker-planner --local --file=schema.sql`
Run (background): `cd web && npx wrangler pages dev --port 8788`

- [ ] **Step 3: API 확인 (curl)**

```bash
K=$(python -c "import urllib.parse;print(urllib.parse.quote('로컬 테스트 비번'))")
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8788/api/state                      # 401
curl -s -H "x-family-key: $K" http://localhost:8788/api/state                                  # {"monthGoals":[],...}
curl -s -H "x-family-key: $K" -H "content-type: application/json" -d '{"month":"2026-10","title":"t"}' http://localhost:8788/api/month-goals   # 201 {"id":1}
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8788/                                # 200
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8788/manifest.webmanifest           # 200
```

D1(실제 workerd)에서 외래키 연쇄 삭제가 되는지 확인: 월 목표 → 주 목표 → 습관 → 스티커를 만든 뒤 월 목표 DELETE, state가 모두 빈 배열이어야 한다.

- [ ] **Step 4: 브라우저 확인**

Claude in Chrome(사용 가능 시)으로 http://localhost:8788 에서: 잠금 화면 → 비밀번호 → 월/주/습관(월·수·금) 추가 → 오늘 탭 표시 여부 → 체크 시 ⭐·달성률 갱신 → 스티커판 달력. 도구가 없으면 사용자에게 직접 확인을 요청한다. 확인 후 로컬 테스트 데이터는 `.wrangler/`를 지워 초기화.

---

### Task 5: 배포 (사용자 확인 후)

- [ ] **Step 1: 사용자 로그인** — 사용자가 `! cd web && npx wrangler login` 실행, `npx wrangler whoami`로 확인.
- [ ] **Step 2: D1 생성** — `npx wrangler d1 create sticker-planner` → 출력의 `database_id`를 `wrangler.toml`에 반영. `npx wrangler d1 execute sticker-planner --remote --file=schema.sql`.
- [ ] **Step 3: Pages 프로젝트 생성** — `npx wrangler pages project create sticker-planner --production-branch main`
- [ ] **Step 4: 비밀번호 등록** — 사용자가 정한 비밀번호를 `npx wrangler pages secret put FAMILY_PASSWORD --project-name sticker-planner`로 등록 (stdin 입력).
- [ ] **Step 5: 사용자 확인 후 배포** — `npx wrangler pages deploy public --project-name sticker-planner --branch main`
- [ ] **Step 6: 배포 확인** — `https://sticker-planner.pages.dev/api/state`가 비밀번호 없이 401, 비밀번호와 함께 200. 첫 페이지 200. 주소가 이미 쓰이고 있으면 Pages가 붙이는 실제 주소를 사용.
- [ ] **Step 7: 기록** — 메모리(project_planner.md)에 배포 주소·구조 기록. git 커밋 여부를 사용자에게 묻는다.
