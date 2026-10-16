"""달성률·연속 달성일 계산 (DB와 무관한 순수 함수).

habits: [(habit_id, week_start, days)] — 각 습관은 week_start부터 7일 중
        days(요일 번호, 월=0 … 일=6)에 해당하는 날만 체크 대상
stickers: {(habit_id, date)}
"""
from datetime import date, timedelta


def week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _days(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def daily_counts(habits, stickers, start: date, end: date, today: date) -> dict:
    """기간 내 각 날짜(오늘까지)의 (받은 스티커, 받을 수 있었던 스티커)."""
    counts = {}
    for d in _days(start, min(end, today)):
        active = [hid for hid, ws, days in habits
                  if ws <= d < ws + timedelta(days=7) and d.weekday() in days]
        if active:
            counts[d] = (sum((hid, d) in stickers for hid in active), len(active))
    return counts


def summary(habits, stickers, start: date, end: date, today: date):
    counts = daily_counts(habits, stickers, start, end, today).values()
    earned = sum(e for e, _ in counts)
    possible = sum(p for _, p in counts)
    return earned, possible, (earned / possible if possible else 0.0)


def streak(habits, stickers, today: date) -> int:
    """모든 습관을 지킨 날이 이어진 일수.

    할 일이 없는 날은 건너뛴다(끊기지도, 세지도 않음). 오늘이 미완이면 어제부터 센다.
    """
    if not habits:
        return 0
    earliest = min(ws for _, ws, _ in habits)
    counts = daily_counts(habits, stickers, earliest, today, today)
    n = 0
    for d in sorted(counts, reverse=True):
        earned, possible = counts[d]
        if earned == possible:
            n += 1
        elif d != today:
            break
    return n
