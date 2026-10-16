"""SQLite 저장소: 월 목표 → 주 목표 → 일일 습관 → 스티커."""
import sqlite3
from datetime import date, timedelta
from pathlib import Path

SCHEMA = """
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
"""


def connect(path) -> sqlite3.Connection:
    conn = sqlite3.connect(Path(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    # 요일 지정 기능 이전에 만든 DB: 기존 습관은 매일(월~일)로 유지
    if "days" not in {r["name"] for r in conn.execute("PRAGMA table_info(habit)")}:
        with conn:
            conn.execute("ALTER TABLE habit ADD COLUMN days TEXT NOT NULL DEFAULT '0123456'")
    return conn


def _insert(conn, sql, params) -> int:
    with conn:
        return conn.execute(sql, params).lastrowid


def _rows(conn, sql, params=()):
    rows = [dict(r) for r in conn.execute(sql, params)]
    for r in rows:
        if "week_start" in r:
            r["week_start"] = date.fromisoformat(r["week_start"])
        if "days" in r:
            r["days"] = tuple(int(c) for c in r["days"])
    return rows


def add_month_goal(conn, month: str, title: str) -> int:
    return _insert(conn, "INSERT INTO month_goal (month, title) VALUES (?, ?)", (month, title))


def add_week_goal(conn, month_goal_id: int, week_start: date, title: str) -> int:
    return _insert(conn, "INSERT INTO week_goal (month_goal_id, week_start, title) VALUES (?, ?, ?)",
                   (month_goal_id, week_start.isoformat(), title))


def add_habit(conn, week_goal_id: int, title: str, days=range(7)) -> int:
    """days: 체크할 요일 번호(월=0 … 일=6)."""
    return _insert(conn, "INSERT INTO habit (week_goal_id, title, days) VALUES (?, ?, ?)",
                   (week_goal_id, title, "".join(str(d) for d in sorted(set(days)))))


def _delete(conn, table: str, id_: int):
    with conn:
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (id_,))


def delete_month_goal(conn, id_: int):
    _delete(conn, "month_goal", id_)


def delete_week_goal(conn, id_: int):
    _delete(conn, "week_goal", id_)


def delete_habit(conn, id_: int):
    _delete(conn, "habit", id_)


def list_month_goals(conn, month: str):
    return _rows(conn, "SELECT * FROM month_goal WHERE month = ? ORDER BY id", (month,))


def list_week_goals(conn, month_goal_id: int):
    return _rows(conn, "SELECT * FROM week_goal WHERE month_goal_id = ? ORDER BY week_start, id",
                 (month_goal_id,))


def list_habits(conn, week_goal_id: int):
    return _rows(conn, "SELECT * FROM habit WHERE week_goal_id = ? ORDER BY id", (week_goal_id,))


_HABIT_JOIN = """
SELECT h.id, h.title, h.days, w.id AS week_goal_id, w.title AS week_title, w.week_start,
       m.id AS month_goal_id, m.title AS month_title
FROM habit h JOIN week_goal w ON h.week_goal_id = w.id JOIN month_goal m ON w.month_goal_id = m.id
"""


def all_habits(conn):
    return _rows(conn, _HABIT_JOIN + " ORDER BY h.id")


def habits_for_date(conn, d: date):
    lo = (d - timedelta(days=6)).isoformat()
    rows = _rows(conn, _HABIT_JOIN + " WHERE w.week_start BETWEEN ? AND ? ORDER BY h.id",
                 (lo, d.isoformat()))
    return [r for r in rows if d.weekday() in r["days"]]


def set_sticker(conn, habit_id: int, d: date, on: bool):
    with conn:
        if on:
            conn.execute("INSERT OR IGNORE INTO sticker (habit_id, date) VALUES (?, ?)",
                         (habit_id, d.isoformat()))
        else:
            conn.execute("DELETE FROM sticker WHERE habit_id = ? AND date = ?", (habit_id, d.isoformat()))


def all_stickers(conn) -> set:
    return {(r["habit_id"], date.fromisoformat(r["date"])) for r in conn.execute("SELECT * FROM sticker")}
