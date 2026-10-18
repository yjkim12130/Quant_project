# 우리집 가계부 PWA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Streamlit 가계부를 열자마자 뜨는 Cloudflare Pages PWA로 다시 만든다(같은 시트·같은 폼·같은 화면).

**Architecture:** 정적 화면(`public/`) + Pages Function 하나(`/api/data`)가 비밀번호 확인 후 공개 시트 gviz CSV를 읽어 JSON으로 준다(60초 Cache API). 계산은 순수 함수 모듈 `public/ledger.js`에 모아 node 테스트로 검증한다. 마지막 응답을 localStorage에 두어 열자마자 그린다.

**Tech Stack:** Cloudflare Pages + Functions, 빌드 없는 ES 모듈, `node --test`, wrangler 4.

**Spec:** `Desktop/Claude_project/Ledger/docs/superpowers/specs/2026-10-18-ledger-pwa-design.md`

## Global Constraints

- 프로젝트 이름 `woorijip-ledger`, 주소 `https://woorijip-ledger.pages.dev`.
- secret 이름 `LEDGER_PASSWORD`, 요청 헤더 `X-Ledger-Key` = encodeURIComponent(비밀번호).
- 시트 ID `19wGTMH2bt6SZPQ5tbbwcOPVoCZYti1QTc7uYsPjty2w`, 시트 `Data`·`Target`. 시트 ID·폼 주소는 `src/api.js`에만.
- 오늘 = UTC+9. 금액 표기 = 정수 버림 + 천단위 쉼표.
- 구글 폼 iframe은 데이터 갱신 때 다시 그리지 않는다(입력 중 내용이 날아감).
- Streamlit 앱(`my-ledger`)은 건드리지 않는다.
- 모든 경로 기준: `Desktop/Claude_project/Ledger/web/`.

## File Structure

| 파일 | 책임 |
|---|---|
| `src/api.js` | 인증, 시트 읽기(캐시), CSV→JSON 변환 |
| `functions/api/[[path]].js` | Pages Function → `handle` 연결 |
| `public/ledger.js` | 날짜·집계·진행바·캘린더 순수 계산 |
| `public/app.js` | 로그인, 데이터 불러오기/저장, 화면 그리기 |
| `public/index.html`, `style.css` | 뼈대와 스타일 |
| `public/sw.js`, `manifest.webmanifest`, 아이콘 | PWA |
| `scripts/make_icons.py` | 아이콘 생성 |
| `scripts/check_totals.mjs` | 실데이터 월 합계 대조 |
| `tests/api.test.js`, `tests/ledger.test.js` | 테스트 |

---

### Task 1: 프로젝트 뼈대 + 서버 함수(`/api/data`)

**Files:**
- Create: `package.json`, `wrangler.toml`, `.gitignore`, `functions/api/[[path]].js`, `src/api.js`
- Test: `tests/api.test.js`

**Interfaces:**
- Produces: `handle(request, env, deps?) → Response`, `parseCsv(text) → string[][]`, `toIsoDate(s) → "YYYY-MM-DD"|null`, `toAmount(s) → number`.
- 응답 JSON: `{ fetchedAt: number(ms), formUrl, sheetUrl, targets: [{category, goal}], rows: [{timestamp, date, category, small, card, amount, payType}] }`.
- `deps = { fetch, cache }` — 테스트 주입용. 기본값 `globalThis.fetch`, `caches.default`.

- [ ] **Step 1: 뼈대 파일**

`package.json`
```json
{
  "name": "woorijip-ledger",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "node --test \"tests/*.test.js\"",
    "dev": "wrangler pages dev --port 8789",
    "deploy": "wrangler pages deploy --project-name woorijip-ledger --branch main --commit-dirty=true"
  },
  "devDependencies": { "wrangler": "^4.151.1" }
}
```
`wrangler.toml`
```toml
name = "woorijip-ledger"
pages_build_output_dir = "public"
compatibility_date = "2026-09-01"
```
`.gitignore`: `node_modules/`, `.wrangler/`, `.dev.vars`
`functions/api/[[path]].js`
```js
import { handle } from "../../src/api.js";

export const onRequest = ({ request, env }) => handle(request, env);
```

- [ ] **Step 2: 실패하는 테스트 작성** — `tests/api.test.js`

```js
import test from "node:test";
import assert from "node:assert/strict";
import { handle, parseCsv, toAmount, toIsoDate } from "../src/api.js";

const KEY = "우리집 가계부";
const DATA_CSV = [
  '"Timestamp","소비 날짜","소비 내역(분류)","Category(small)","사용 카드","액수","일시불,할부 여부"',
  '"4/6/2026 20:47:53","4/6/2026"," 외식비(배달 포함) ","후토마끼, 김밥","그 외","10000","일시불"',
  '"10/10/2026 22:25:02","10/9/2026","외식비(배달 포함)","20000","영준 현대카드","","무이자 할부 3개월"',
  '"10/10/2026 22:26:17","","교통비","택시","그 외","abc","일시불"',
].join("\n");
const TARGET_CSV = '"Category","Monthly_Goal"\n"외식비(배달 포함)","300000"\n"교통비","100000"';

function fakeFetch(sheets = { Data: DATA_CSV, Target: TARGET_CSV }) {
  const calls = [];
  const fn = async (url) => {
    calls.push(url);
    const name = decodeURIComponent(new URL(url).searchParams.get("sheet"));
    if (!(name in sheets)) return new Response("nope", { status: 500 });
    return new Response(sheets[name], { status: 200 });
  };
  fn.calls = calls;
  return fn;
}
function fakeCache() {
  const store = new Map();
  return {
    store,
    match: async (url) => store.get(String(url))?.clone(),
    put: async (url, res) => void store.set(String(url), res),
  };
}
function setup({ env = { LEDGER_PASSWORD: KEY }, fetch = fakeFetch(), cache = fakeCache() } = {}) {
  const call = async (path = "data", key = KEY) => {
    const headers = key === null ? {} : { "x-ledger-key": encodeURIComponent(key) };
    const res = await handle(new Request("https://ledger.test/api/" + path, { headers }), env, { fetch, cache });
    return { status: res.status, data: await res.json() };
  };
  return { call, fetch, cache };
}

test("parseCsv handles quotes, commas, escaped quotes, CRLF", () => {
  assert.deepEqual(parseCsv('"a","b,c"\r\n"d ""e""",\n'), [["a", "b,c"], ['d "e"', ""]]);
});

test("toIsoDate parses M/D/YYYY and rejects junk", () => {
  assert.equal(toIsoDate("4/6/2026"), "2026-04-06");
  assert.equal(toIsoDate("10/10/2026 22:25:02"), "2026-10-10");
  assert.equal(toIsoDate("2/30/2026"), null);
  assert.equal(toIsoDate(""), null);
});

test("toAmount: numbers pass, junk and blanks become 0", () => {
  assert.equal(toAmount("73000"), 73000);
  assert.equal(toAmount(""), 0);
  assert.equal(toAmount("abc"), 0);
});

test("rejects missing or wrong password, 500 when not configured", async () => {
  assert.equal((await setup().call("data", null)).status, 401);
  assert.equal((await setup().call("data", "틀림")).status, 401);
  assert.equal((await setup({ env: {} }).call()).status, 500);
});

test("unknown path is 404", async () => {
  assert.equal((await setup().call("other")).status, 404);
});

test("returns cleaned rows and targets", async () => {
  const { status, data } = await setup().call();
  assert.equal(status, 200);
  assert.deepEqual(data.targets, [
    { category: "외식비(배달 포함)", goal: 300000 },
    { category: "교통비", goal: 100000 },
  ]);
  assert.deepEqual(data.rows[0], {
    timestamp: "4/6/2026 20:47:53", date: "2026-04-06", category: "외식비(배달 포함)",
    small: "후토마끼, 김밥", card: "그 외", amount: 10000, payType: "일시불",
  });
  assert.equal(data.rows[1].amount, 0);
  assert.equal(data.rows[2].date, null);
  assert.equal(data.rows[2].amount, 0);
  assert.match(data.formUrl, /^https:\/\/docs\.google\.com\/forms\//);
  assert.match(data.sheetUrl, /\/edit$/);
  assert.equal(typeof data.fetchedAt, "number");
});

test("second call is served from cache; fresh=1 bypasses it", async () => {
  const s = setup();
  await s.call();
  await s.call();
  assert.equal(s.fetch.calls.length, 2);
  await s.call("data?fresh=1");
  assert.equal(s.fetch.calls.length, 4);
});

test("google failure or unexpected sheet is 502", async () => {
  assert.equal((await setup({ fetch: fakeFetch({ Target: TARGET_CSV }) }).call()).status, 502);
  const html = fakeFetch({ Data: "<html>login</html>", Target: TARGET_CSV });
  assert.equal((await setup({ fetch: html }).call()).status, 502);
});
```

- [ ] **Step 3: 실패 확인** — `npm test` → `Cannot find module '../src/api.js'`

- [ ] **Step 4: 구현** — `src/api.js`

```js
// /api/data 처리. env.LEDGER_PASSWORD: 가계부 비밀번호(Cloudflare secret)
// 공개 구글 시트를 gviz CSV로 읽어 JSON으로 준다. 시트·폼 주소는 서버에만 둔다.
const SHEET_ID = "19wGTMH2bt6SZPQ5tbbwcOPVoCZYti1QTc7uYsPjty2w";
const FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScygQkv9LyeZmUMSE3kKdW1Nba2GvZ3UM3QlxKaHnO-wc8NFw/viewform?embedded=true";
const SHEET_URL = `https://docs.google.com/spreadsheets/d/${SHEET_ID}/edit`;
const CACHE_SECONDS = 60;
const csvUrl = (name) => `https://docs.google.com/spreadsheets/d/${SHEET_ID}/gviz/tq?tqx=out:csv&sheet=${encodeURIComponent(name)}`;

class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

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

// ── CSV ───────────────────────────────────────────────
export function parseCsv(text) {
  const rows = [];
  let row = [], field = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c !== '"') field += c;
      else if (text[i + 1] === '"') { field += '"'; i++; }
      else quoted = false;
    } else if (c === '"') quoted = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field); rows.push(row); row = []; field = "";
    } else field += c;
  }
  if (field !== "" || row.length) { row.push(field); rows.push(row); }
  return rows;
}

function records(text, required) {
  const [header = [], ...rows] = parseCsv(text);
  const names = header.map((h) => h.trim());
  if (!required.every((c) => names.includes(c))) throw new HttpError(502, "unexpected sheet format");
  return rows
    .filter((r) => r.some((v) => v.trim() !== ""))
    .map((r) => Object.fromEntries(names.map((n, i) => [n, r[i] ?? ""])));
}

// 시트 날짜는 M/D/YYYY(구글 폼 기본). 해석 못 하면 null — pandas errors="coerce"와 같다.
export function toIsoDate(s) {
  const m = /^\s*(\d{1,2})\/(\d{1,2})\/(\d{4})(\s|$)/.exec(s);
  if (!m) return null;
  const [y, mo, d] = [Number(m[3]), Number(m[1]), Number(m[2])];
  const dt = new Date(Date.UTC(y, mo - 1, d));
  if (dt.getUTCMonth() !== mo - 1 || dt.getUTCDate() !== d) return null;
  return dt.toISOString().slice(0, 10);
}

// 숫자가 아니면 0 — pandas to_numeric(errors="coerce").fillna(0)과 같다.
export function toAmount(s) {
  const t = String(s).trim();
  const n = t === "" ? 0 : Number(t);
  return Number.isFinite(n) ? n : 0;
}

// ── 시트 읽기(60초 캐시) ───────────────────────────────
async function readSheet(name, { fetch, cache, fresh }) {
  const url = csvUrl(name);
  if (!fresh && cache) {
    const hit = await cache.match(url);
    if (hit) return { text: await hit.text(), fetchedAt: Number(hit.headers.get("x-fetched-at")) };
  }
  let res;
  try {
    res = await fetch(url);
  } catch {
    throw new HttpError(502, "sheet fetch failed");
  }
  if (!res.ok) throw new HttpError(502, "sheet fetch failed");
  const text = await res.text();
  const fetchedAt = Date.now();
  if (cache) {
    const headers = { "cache-control": `max-age=${CACHE_SECONDS}`, "x-fetched-at": String(fetchedAt) };
    await cache.put(url, new Response(text, { headers }));
  }
  return { text, fetchedAt };
}

export async function handle(request, env, deps = {}) {
  const fetch = deps.fetch ?? globalThis.fetch;
  const cache = deps.cache ?? globalThis.caches?.default;
  try {
    if (!env.LEDGER_PASSWORD) return json({ error: "server not configured" }, 500);
    const key = request.headers.get("x-ledger-key") ?? "";
    if (!(await sameSecret(key, encodeURIComponent(env.LEDGER_PASSWORD)))) return json({ error: "unauthorized" }, 401);

    const url = new URL(request.url);
    if (request.method !== "GET" || url.pathname.replace(/\/+$/, "") !== "/api/data") return json({ error: "not found" }, 404);

    const opts = { fetch, cache, fresh: url.searchParams.get("fresh") === "1" };
    const [data, target] = await Promise.all([readSheet("Data", opts), readSheet("Target", opts)]);
    const targets = records(target.text, ["Category", "Monthly_Goal"]).map((r) => ({
      category: r.Category.trim(),
      goal: toAmount(r.Monthly_Goal),
    }));
    const rows = records(data.text, ["소비 날짜", "소비 내역(분류)", "액수"]).map((r) => ({
      timestamp: r["Timestamp"] ?? "",
      date: toIsoDate(r["소비 날짜"]),
      category: r["소비 내역(분류)"].trim(),
      small: r["Category(small)"] ?? "",
      card: r["사용 카드"] ?? "",
      amount: toAmount(r["액수"]),
      payType: r["일시불,할부 여부"] ?? "",
    }));
    return json({ fetchedAt: Math.min(data.fetchedAt, target.fetchedAt), formUrl: FORM_URL, sheetUrl: SHEET_URL, targets, rows });
  } catch (e) {
    if (e instanceof HttpError) return json({ error: e.message }, e.status);
    console.error(e);
    return json({ error: "server error" }, 500);
  }
}
```

- [ ] **Step 5: 통과 확인** — `npm test` → 전부 PASS
- [ ] **Step 6: 커밋** — `feat(ledger-pwa): /api/data 서버 함수(인증·시트 캐시·CSV 변환)`

---

### Task 2: 계산 모듈 `public/ledger.js`

**Files:**
- Create: `public/ledger.js`
- Test: `tests/ledger.test.js`

**Interfaces:**
- Consumes: Task 1의 `rows`/`targets` 모양.
- Produces:
  - `kstToday(now?: Date) → {year, month, day}`
  - `daysInMonth(year, month) → number`
  - `won(n) → string` (버림 + 쉼표)
  - `categorySummary(targets, rows, year, month) → [{category, goal, actual}]`
  - `progress(goal, actual, elapsedRatio) → {plan, status: "saving"|"over"|"unset", green, red, marker, label, detail}`
  - `monthDetail(rows, year, month) → rows + {cumulative}` (날짜순, 같은 날은 원래 순서)
  - `dailyTotals(detail) → Map<day, sum>`
  - `calendarWeeks(year, month) → number[][]` (월요일 시작, 빈칸 0)
  - `manwon(amount) → string`
  - `shiftMonth(year, month, delta) → {year, month}`
  - `yearOptions(rows, thisYear, selYear) → number[]` (내림차순)

- [ ] **Step 1: 실패하는 테스트** — `tests/ledger.test.js`

```js
import test from "node:test";
import assert from "node:assert/strict";
import {
  calendarWeeks, categorySummary, dailyTotals, daysInMonth, kstToday, manwon,
  monthDetail, progress, shiftMonth, won, yearOptions,
} from "../public/ledger.js";

const row = (date, category, amount, small = "") => ({ timestamp: "", date, category, small, card: "", amount, payType: "" });

test("kstToday shifts UTC by 9 hours", () => {
  assert.deepEqual(kstToday(new Date("2026-10-31T15:30:00Z")), { year: 2026, month: 11, day: 1 });
  assert.deepEqual(kstToday(new Date("2026-10-31T14:59:00Z")), { year: 2026, month: 10, day: 31 });
});

test("daysInMonth handles leap years", () => {
  assert.equal(daysInMonth(2028, 2), 29);
  assert.equal(daysInMonth(2026, 2), 28);
  assert.equal(daysInMonth(2026, 10), 31);
});

test("won truncates and adds commas", () => {
  assert.equal(won(1234567.9), "1,234,567");
  assert.equal(won(-0.4), "0");
});

test("categorySummary follows target order and ignores unknown categories and other months", () => {
  const targets = [{ category: "교통비", goal: 100000 }, { category: "외식비", goal: 300000 }];
  const rows = [row("2026-10-01", "외식비", 1000), row("2026-10-02", "외식비", 500), row("2026-09-30", "교통비", 9),
    row("2026-10-03", "기타", 7), row(null, "교통비", 3)];
  assert.deepEqual(categorySummary(targets, rows, 2026, 10), [
    { category: "교통비", goal: 100000, actual: 0 },
    { category: "외식비", goal: 300000, actual: 1500 },
  ]);
});

test("progress: saving", () => {
  const p = progress(100000, 30000, 0.5);
  assert.equal(p.status, "saving");
  assert.equal(p.plan, 50000);
  assert.equal(p.green, 30);
  assert.equal(p.red, 0);
  assert.equal(p.marker, 50);
  assert.equal(p.label, "계획대비 절약중");
  assert.equal(p.detail, "20,000원 여유");
});

test("progress: over, red capped at 120% total", () => {
  const p = progress(100000, 70000, 0.5);
  assert.equal(p.status, "over");
  assert.equal(p.green, 50);
  assert.equal(p.red, 20);
  assert.equal(p.detail, "20,000원 초과");
  assert.equal(progress(100000, 500000, 0.5).red, 70);
});

test("progress: unset budget", () => {
  assert.deepEqual(progress(0, 5000, 0.5), { plan: 0, status: "unset", green: 0, red: 0, marker: 0, label: "예산 미설정", detail: "-" });
});

test("monthDetail sorts by date (stable) and adds cumulative", () => {
  const rows = [row("2026-10-05", "a", 100, "1"), row("2026-10-01", "b", 10, "2"), row("2026-10-05", "c", 1, "3"), row("2026-11-01", "d", 5)];
  const d = monthDetail(rows, 2026, 10);
  assert.deepEqual(d.map((r) => r.small), ["2", "1", "3"]);
  assert.deepEqual(d.map((r) => r.cumulative), [10, 110, 111]);
  assert.deepEqual([...dailyTotals(d)], [[1, 10], [5, 101]]);
});

test("calendarWeeks starts on Monday like Python calendar.monthcalendar", () => {
  const w = calendarWeeks(2026, 10); // 2026-10-01은 목요일
  assert.deepEqual(w[0], [0, 0, 0, 1, 2, 3, 4]);
  assert.deepEqual(w.at(-1), [26, 27, 28, 29, 30, 31, 0]);
  assert.equal(w.length, 5);
});

test("manwon formats like the Streamlit app", () => {
  assert.equal(manwon(93000), "9.3만");
  assert.equal(manwon(100000), "10만");
  assert.equal(manwon(5000), "0.5만");
});

test("shiftMonth crosses years", () => {
  assert.deepEqual(shiftMonth(2026, 1, -1), { year: 2025, month: 12 });
  assert.deepEqual(shiftMonth(2026, 12, 1), { year: 2027, month: 1 });
});

test("yearOptions merges recorded, current and selected years, descending", () => {
  const rows = [row("2025-03-01", "a", 1), row("2026-01-01", "a", 1), row(null, "a", 1)];
  assert.deepEqual(yearOptions(rows, 2026, 2023), [2026, 2025, 2023]);
});
```

- [ ] **Step 2: 실패 확인** — `npm test` → `Cannot find module '../public/ledger.js'`

- [ ] **Step 3: 구현** — `public/ledger.js`

```js
// 가계부 계산(순수 함수). 규칙은 Streamlit 앱(my-ledger/app.py)과 같다.
export function kstToday(now = new Date()) {
  const d = new Date(now.getTime() + 9 * 3600 * 1000);
  return { year: d.getUTCFullYear(), month: d.getUTCMonth() + 1, day: d.getUTCDate() };
}

export const daysInMonth = (year, month) => new Date(Date.UTC(year, month, 0)).getUTCDate();

export const won = (n) => (Math.trunc(n) || 0).toLocaleString("en-US");

const inMonth = (r, year, month) =>
  r.date !== null && Number(r.date.slice(0, 4)) === year && Number(r.date.slice(5, 7)) === month;

// Target 순서대로, Target에 없는 분류는 빠진다(app.py의 left merge).
export function categorySummary(targets, rows, year, month) {
  const sums = new Map();
  for (const r of rows) if (inMonth(r, year, month)) sums.set(r.category, (sums.get(r.category) ?? 0) + r.amount);
  return targets.map((t) => ({ category: t.category, goal: t.goal, actual: sums.get(t.category) ?? 0 }));
}

// 진행바: 초록 = 쓴 만큼(계획 안쪽), 빨강 = 계획을 넘은 만큼(전체 120%까지), marker = 오늘까지 계획선.
export function progress(goal, actual, elapsedRatio) {
  const plan = goal * elapsedRatio;
  if (!(goal > 0)) return { plan: 0, status: "unset", green: 0, red: 0, marker: 0, label: "예산 미설정", detail: "-" };
  const actualPct = (actual / goal) * 100;
  const planPct = (plan / goal) * 100;
  const diff = plan - actual;
  if (actual <= plan) {
    return { plan, status: "saving", green: Math.min(actualPct, 100), red: 0, marker: planPct,
      label: "계획대비 절약중", detail: `${won(diff)}원 여유` };
  }
  return { plan, status: "over", green: Math.min(planPct, 100), red: Math.min(Math.max(actualPct - planPct, 0), 120 - planPct),
    marker: planPct, label: "계획대비 과소비중", detail: `${won(Math.abs(diff))}원 초과` };
}

export function monthDetail(rows, year, month) {
  let cumulative = 0;
  return rows
    .filter((r) => inMonth(r, year, month))
    .sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0))
    .map((r) => ({ ...r, cumulative: (cumulative += r.amount) }));
}

export function dailyTotals(detail) {
  const totals = new Map();
  for (const r of detail) {
    const day = Number(r.date.slice(8, 10));
    totals.set(day, (totals.get(day) ?? 0) + r.amount);
  }
  return totals;
}

export function calendarWeeks(year, month) {
  const lead = (new Date(Date.UTC(year, month - 1, 1)).getUTCDay() + 6) % 7; // 월요일 = 0
  const cells = [...Array(lead).fill(0), ...Array.from({ length: daysInMonth(year, month) }, (_, i) => i + 1)];
  while (cells.length % 7) cells.push(0);
  const weeks = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
  return weeks;
}

export const manwon = (amount) => `${(amount / 10000).toFixed(1)}만`.replace(".0만", "만");

export function shiftMonth(year, month, delta) {
  const index = year * 12 + (month - 1) + delta;
  return { year: Math.floor(index / 12), month: (index % 12) + 1 };
}

export function yearOptions(rows, thisYear, selYear) {
  const years = new Set([thisYear, selYear]);
  for (const r of rows) if (r.date !== null) years.add(Number(r.date.slice(0, 4)));
  return [...years].sort((a, b) => b - a);
}
```

- [ ] **Step 4: 통과 확인** — `npm test` → 전부 PASS
- [ ] **Step 5: 커밋** — `feat(ledger-pwa): 집계·진행바·캘린더 계산 모듈`

---

### Task 3: 실데이터 월 합계 대조

**Files:**
- Create: `scripts/check_totals.mjs`

**Interfaces:**
- Consumes: `handle`(Task 1), `monthDetail`(Task 2). 실제 `fetch` 사용, 캐시 없음.

- [ ] **Step 1: 스크립트**

```js
// 실제 시트로 월 합계를 Streamlit 앱 기준값과 대조한다. 사용법: node scripts/check_totals.mjs
import { handle } from "../src/api.js";
import { monthDetail } from "../public/ledger.js";

const EXPECTED = { "2026-04": 10130856, "2026-05": 4178946, "2026-06": 1609026, "2026-07": 2574127 };
const env = { LEDGER_PASSWORD: "check" };
const req = new Request("https://local/api/data", { headers: { "x-ledger-key": "check" } });
const res = await handle(req, env, { fetch, cache: null });
const data = await res.json();
if (!res.ok) throw new Error(JSON.stringify(data));

let failed = 0;
for (const [ym, want] of Object.entries(EXPECTED)) {
  const [y, m] = ym.split("-").map(Number);
  const got = monthDetail(data.rows, y, m).reduce((s, r) => s + r.amount, 0);
  const ok = got === want;
  if (!ok) failed++;
  console.log(`${ym}  ${got.toLocaleString("en-US")}  ${ok ? "OK" : `기대 ${want.toLocaleString("en-US")}`}`);
}
console.log(`rows=${data.rows.length} targets=${data.targets.length}`);
process.exit(failed ? 1 : 0);
```

- [ ] **Step 2: 실행** — `node scripts/check_totals.mjs` → 4개 월 모두 `OK`. 하나라도 다르면 파싱 규칙(날짜·액수)을 pandas 동작과 비교해 고친다.
- [ ] **Step 3: 커밋** — `test(ledger-pwa): 실데이터 월 합계 대조 스크립트`

---

### Task 4: 화면(PWA)

**Files:**
- Create: `public/index.html`, `public/style.css`, `public/app.js`, `public/sw.js`, `public/manifest.webmanifest`, `scripts/make_icons.py`, 아이콘 3개

**Interfaces:**
- Consumes: `/api/data` 응답(Task 1), `ledger.js` 함수 전부(Task 2).
- localStorage 키: `ledgerKey`(비밀번호), `ledgerData`(마지막 응답).

화면 규칙은 스펙 "화면" 절 그대로. 구현 요점:
- `index.html`에 고정 뼈대: 헤더(제목·🔄)·상태줄·탭 3개·섹션 3개. 폼 섹션의 `<iframe>`은 `src`가 바뀔 때만 설정한다.
- 대시보드·전체 내역 섹션만 `innerHTML`로 다시 그린다. 모든 시트 문자열은 `esc()`로 이스케이프.
- 분류별 막대그래프는 가로 막대(분류 이름이 길어 폰에서 세로 라벨이 안 읽힘).
- 상태줄: 불러오는 중 "갱신 중…", 성공 "HH:MM 갱신", 실패 "N분 전 데이터 · 최신 아님".
- 앱이 다시 보일 때(`visibilitychange`) 마지막 갱신이 60초 넘었으면 다시 불러온다.
- 401 → 비밀번호·저장 데이터 지우고 로그인 화면("비밀번호가 맞지 않아요").

- [ ] **Step 1: 아이콘** — `python scripts/make_icons.py public` (초록 바탕 흰 막대그래프)
- [ ] **Step 2: index.html / style.css / manifest / sw.js 작성** (sw는 planner와 같은 네트워크 우선, `/api/` 제외, 캐시 이름 `ledger-v1`)
- [ ] **Step 3: app.js 작성**
- [ ] **Step 4: 로컬 확인** — `.dev.vars`에 `LEDGER_PASSWORD=test` 후 `npm run dev`, Edge headless로 3개 탭 스크린샷, 모바일 폭(390px) 가로 스크롤 없음 확인
- [ ] **Step 5: 커밋** — `feat(ledger-pwa): 화면·PWA`

---

### Task 5: 배포

- [ ] **Step 1:** `npx wrangler pages project create woorijip-ledger --production-branch main`
- [ ] **Step 2:** `npm run deploy`
- [ ] **Step 3:** 사용자가 `LEDGER_PASSWORD` 등록 → 재배포(비밀은 다음 배포부터 적용)
- [ ] **Step 4:** 실기기 확인: 첫 화면 시간, Streamlit 앱과 같은 달 수치 비교
- [ ] **Step 5:** 메모리(`project_ledger.md`) 갱신
