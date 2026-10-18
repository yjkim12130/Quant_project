import test from "node:test";
import assert from "node:assert/strict";
import {
  calendarWeeks, categorySummary, dailyTotals, daysInMonth, elapsedRatio, kstToday, manwon,
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

test("elapsedRatio: current month by today, past month full, future month zero", () => {
  const today = { year: 2026, month: 10, day: 18 };
  assert.equal(elapsedRatio(2026, 10, today), 18 / 31);
  assert.equal(elapsedRatio(2026, 9, today), 1);
  assert.equal(elapsedRatio(2025, 12, today), 1);
  assert.equal(elapsedRatio(2026, 11, today), 0);
  assert.equal(elapsedRatio(2027, 1, today), 0);
});
