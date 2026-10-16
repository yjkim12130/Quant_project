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
