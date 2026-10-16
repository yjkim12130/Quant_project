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
