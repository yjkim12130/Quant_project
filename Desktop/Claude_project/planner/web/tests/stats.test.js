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
