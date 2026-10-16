import sqlite3
from datetime import date

import pytest

import db

MON = date(2026, 10, 5)


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    yield c
    c.close()


def test_goal_hierarchy_round_trip(conn):
    m = db.add_month_goal(conn, "2026-10", "체중 2kg 감량")
    w = db.add_week_goal(conn, m, MON, "운동 4회")
    h = db.add_habit(conn, w, "30분 걷기")
    assert [g["title"] for g in db.list_month_goals(conn, "2026-10")] == ["체중 2kg 감량"]
    assert [g["title"] for g in db.list_week_goals(conn, m)] == ["운동 4회"]
    assert db.list_week_goals(conn, m)[0]["week_start"] == MON
    assert [x["id"] for x in db.list_habits(conn, w)] == [h]


def test_habits_for_date_only_within_week(conn):
    m = db.add_month_goal(conn, "2026-10", "m")
    w = db.add_week_goal(conn, m, MON, "w")
    h = db.add_habit(conn, w, "h")
    assert [x["id"] for x in db.habits_for_date(conn, date(2026, 10, 11))] == [h]
    assert db.habits_for_date(conn, date(2026, 10, 12)) == []
    assert db.habits_for_date(conn, date(2026, 10, 4)) == []


def test_set_sticker_toggles(conn):
    m = db.add_month_goal(conn, "2026-10", "m")
    h = db.add_habit(conn, db.add_week_goal(conn, m, MON, "w"), "h")
    db.set_sticker(conn, h, MON, True)
    db.set_sticker(conn, h, MON, True)  # 중복 체크해도 1장
    assert db.all_stickers(conn) == {(h, MON)}
    db.set_sticker(conn, h, MON, False)
    assert db.all_stickers(conn) == set()


def test_delete_month_goal_cascades(conn):
    m = db.add_month_goal(conn, "2026-10", "m")
    w = db.add_week_goal(conn, m, MON, "w")
    h = db.add_habit(conn, w, "h")
    db.set_sticker(conn, h, MON, True)
    db.delete_month_goal(conn, m)
    assert db.all_habits(conn) == []
    assert db.all_stickers(conn) == set()


def test_all_habits_includes_week_start_and_month_goal(conn):
    m = db.add_month_goal(conn, "2026-10", "m")
    h = db.add_habit(conn, db.add_week_goal(conn, m, MON, "w"), "h")
    [row] = db.all_habits(conn)
    assert (row["id"], row["week_start"], row["month_goal_id"]) == (h, MON, m)


def test_habit_days_default_all_and_custom(conn):
    m = db.add_month_goal(conn, "2026-10", "m")
    w = db.add_week_goal(conn, m, MON, "w")
    db.add_habit(conn, w, "매일")
    db.add_habit(conn, w, "운동", days=[4, 0, 2])
    assert [h["days"] for h in db.list_habits(conn, w)] == [(0, 1, 2, 3, 4, 5, 6), (0, 2, 4)]
    assert [h["days"] for h in db.all_habits(conn)] == [(0, 1, 2, 3, 4, 5, 6), (0, 2, 4)]


def test_habits_for_date_filters_by_weekday(conn):
    m = db.add_month_goal(conn, "2026-10", "m")
    w = db.add_week_goal(conn, m, MON, "w")
    db.add_habit(conn, w, "매일")
    db.add_habit(conn, w, "운동", days=[0, 2, 4])
    assert [h["title"] for h in db.habits_for_date(conn, MON)] == ["매일", "운동"]
    assert [h["title"] for h in db.habits_for_date(conn, date(2026, 10, 6))] == ["매일"]


def test_connect_migrates_old_db_without_days(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE month_goal (id INTEGER PRIMARY KEY, month TEXT NOT NULL, title TEXT NOT NULL);
        CREATE TABLE week_goal (id INTEGER PRIMARY KEY, month_goal_id INTEGER NOT NULL,
            week_start TEXT NOT NULL, title TEXT NOT NULL);
        CREATE TABLE habit (id INTEGER PRIMARY KEY, week_goal_id INTEGER NOT NULL, title TEXT NOT NULL);
        CREATE TABLE sticker (habit_id INTEGER NOT NULL, date TEXT NOT NULL, PRIMARY KEY (habit_id, date));
        INSERT INTO month_goal VALUES (1, '2026-10', 'm');
        INSERT INTO week_goal VALUES (1, 1, '2026-10-05', 'w');
        INSERT INTO habit VALUES (1, 1, '옛 습관');
    """)
    old.commit()
    old.close()
    c = db.connect(path)
    assert [h["days"] for h in db.all_habits(c)] == [(0, 1, 2, 3, 4, 5, 6)]
    c.close()
