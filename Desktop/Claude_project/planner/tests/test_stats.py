from datetime import date

from stats import daily_counts, streak, summary, week_start

MON = date(2026, 10, 5)  # 월요일
ALL = tuple(range(7))
MWF = (0, 2, 4)


def test_week_start_returns_monday():
    assert week_start(date(2026, 10, 7)) == MON
    assert week_start(MON) == MON
    assert week_start(date(2026, 10, 11)) == MON


def test_summary_counts_only_days_up_to_today():
    habits = [(1, MON, ALL), (2, MON, ALL)]
    stickers = {(1, MON), (2, MON), (1, date(2026, 10, 6))}
    earned, possible, rate = summary(habits, stickers, MON, date(2026, 10, 11), today=date(2026, 10, 6))
    assert (earned, possible) == (3, 4)
    assert rate == 0.75


def test_summary_ignores_days_outside_habit_week():
    habits = [(1, MON, ALL)]
    earned, possible, _ = summary(habits, set(), date(2026, 10, 1), date(2026, 10, 31), today=date(2026, 10, 31))
    assert possible == 7


def test_summary_ignores_stickers_outside_slots():
    habits = [(1, MON, ALL)]
    stickers = {(1, date(2026, 10, 20))}
    earned, possible, _ = summary(habits, stickers, date(2026, 10, 1), date(2026, 10, 31), today=date(2026, 10, 31))
    assert earned == 0


def test_summary_rate_zero_when_nothing_possible():
    assert summary([], set(), MON, MON, today=MON) == (0, 0, 0.0)


def test_daily_counts():
    habits = [(1, MON, ALL), (2, MON, ALL)]
    stickers = {(1, MON)}
    counts = daily_counts(habits, stickers, MON, date(2026, 10, 6), today=date(2026, 10, 6))
    assert counts == {MON: (1, 2), date(2026, 10, 6): (0, 2)}


def test_streak_counts_back_from_today_when_today_complete():
    habits = [(1, MON, ALL)]
    stickers = {(1, MON), (1, date(2026, 10, 6)), (1, date(2026, 10, 7))}
    assert streak(habits, stickers, today=date(2026, 10, 7)) == 3


def test_streak_starts_yesterday_when_today_incomplete():
    habits = [(1, MON, ALL)]
    stickers = {(1, MON), (1, date(2026, 10, 6))}
    assert streak(habits, stickers, today=date(2026, 10, 7)) == 2


def test_streak_breaks_on_partial_day():
    habits = [(1, MON, ALL), (2, MON, ALL)]
    stickers = {(1, MON), (2, MON), (1, date(2026, 10, 6))}
    assert streak(habits, stickers, today=date(2026, 10, 6)) == 1
    assert streak(habits, {(1, MON), (2, MON)}, today=MON) == 1  # 첫 주 이전으로는 세지 않음


def test_summary_counts_only_scheduled_weekdays():
    habits = [(1, MON, MWF)]
    stickers = {(1, MON), (1, date(2026, 10, 7)), (1, date(2026, 10, 9))}
    assert summary(habits, stickers, MON, date(2026, 10, 11), today=date(2026, 10, 11)) == (3, 3, 1.0)


def test_daily_counts_skips_unscheduled_days():
    counts = daily_counts([(1, MON, MWF)], set(), MON, date(2026, 10, 7), today=date(2026, 10, 7))
    assert counts == {MON: (0, 1), date(2026, 10, 7): (0, 1)}


def test_streak_skips_days_without_scheduled_habits():
    habits = [(1, MON, MWF)]
    stickers = {(1, MON), (1, date(2026, 10, 7))}
    assert streak(habits, stickers, today=date(2026, 10, 8)) == 2  # 목(없음) → 수 → 화(없음) → 월


def test_streak_still_breaks_on_missed_scheduled_day():
    habits = [(1, MON, MWF)]
    stickers = {(1, date(2026, 10, 7))}
    assert streak(habits, stickers, today=date(2026, 10, 8)) == 1
