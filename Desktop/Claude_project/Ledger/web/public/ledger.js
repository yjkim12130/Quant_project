// 가계부 계산(순수 함수). 규칙은 Streamlit 앱(my-ledger/app.py)과 같다.
export function kstToday(now = new Date()) {
  const d = new Date(now.getTime() + 9 * 3600 * 1000);
  return { year: d.getUTCFullYear(), month: d.getUTCMonth() + 1, day: d.getUTCDate() };
}

export const daysInMonth = (year, month) => new Date(Date.UTC(year, month, 0)).getUTCDate();

// 계획선 위치: 이번 달은 오늘까지, 지난 달은 말일 기준(1), 아직 안 온 달은 0.
export function elapsedRatio(year, month, today) {
  const sel = year * 12 + month, cur = today.year * 12 + today.month;
  if (sel < cur) return 1;
  if (sel > cur) return 0;
  return today.day / daysInMonth(year, month);
}

export const won =(n) => (Math.trunc(n) || 0).toLocaleString("en-US");

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
