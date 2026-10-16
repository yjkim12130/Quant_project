"""칭찬스티커 플래너 — 월 → 주 → 일 목표, 매일 체크하면 ⭐."""
import calendar
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

import db
from stats import daily_counts, streak, summary, week_start

st.set_page_config(page_title="칭찬스티커 플래너", page_icon="⭐", layout="centered")


@st.cache_resource
def get_conn():
    return db.connect(Path(__file__).parent / "planner.db")


conn = get_conn()
today = date.today()
month_key = today.strftime("%Y-%m")
month_start = today.replace(day=1)
month_end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
WEEKDAYS = "월화수목금토일"


def load():
    habits = db.all_habits(conn)
    return habits, [(h["id"], h["week_start"], h["days"]) for h in habits], db.all_stickers(conn)


def on_toggle(habit_id, d, key):
    checked = st.session_state[key]
    db.set_sticker(conn, habit_id, d, checked)
    if checked:
        st.session_state["celebrate"] = True


st.title("⭐ 칭찬스티커 플래너")
tab_today, tab_goals, tab_board = st.tabs(["오늘", "목표 설정", "스티커판"])

# ── 오늘 ──────────────────────────────────────────────
with tab_today:
    habits, slots, stickers = load()
    ws = week_start(today)
    c1, c2, c3, c4 = st.columns(4)
    for col, label, (start, end) in [
        (c1, "오늘", (today, today)),
        (c2, "이번 주", (ws, ws + timedelta(days=6))),
        (c3, "이번 달", (month_start, month_end)),
    ]:
        earned, possible, rate = summary(slots, stickers, start, end, today)
        col.metric(label, f"{rate:.0%}", f"⭐ {earned}/{possible}", delta_color="off")
        col.progress(rate)
    c4.metric("연속 달성", f"🔥 {streak(slots, stickers, today)}일")

    st.subheader(f"{today:%m월 %d일} 할 일")
    todays = db.habits_for_date(conn, today)
    if not todays:
        st.info("오늘 할 습관이 없어요. '목표 설정' 탭에서 이번 주 목표와 일일 습관을 추가하세요.")
    for h in todays:
        key = f"chk_{h['id']}_{today}"
        done = (h["id"], today) in stickers
        st.checkbox(f"{'⭐ ' if done else ''}{h['title']}  ·  _{h['week_title']}_",
                    value=done, key=key, on_change=on_toggle, args=(h["id"], today, key))
    if todays and all((h["id"], today) in stickers for h in todays):
        st.success("오늘 목표를 모두 달성했어요! 정말 잘했어요 👏")
    if st.session_state.pop("celebrate", False):
        st.balloons()

# ── 목표 설정 ─────────────────────────────────────────
with tab_goals:
    st.caption(f"{today:%Y년 %m월} 목표")
    with st.form("add_month", clear_on_submit=True):
        title = st.text_input("새 월 목표", placeholder="예: 체중 2kg 감량")
        if st.form_submit_button("월 목표 추가") and title.strip():
            db.add_month_goal(conn, month_key, title.strip())
            st.rerun()

    weeks = sorted({week_start(month_start + timedelta(days=i))
                    for i in range((month_end - month_start).days + 1)})
    for m in db.list_month_goals(conn, month_key):
        with st.expander(f"🎯 {m['title']}", expanded=True):
            for w in db.list_week_goals(conn, m["id"]):
                st.markdown(f"**📅 {w['week_start']:%m/%d}주 — {w['title']}**")
                for h in db.list_habits(conn, w["id"]):
                    a, b = st.columns([6, 1])
                    when = "매일" if len(h["days"]) == 7 else "·".join(WEEKDAYS[d] for d in h["days"])
                    a.write(f"　• {h['title']}  ({when})")
                    if b.button("삭제", key=f"del_h{h['id']}"):
                        db.delete_habit(conn, h["id"])
                        st.rerun()
                with st.form(f"add_habit_{w['id']}", clear_on_submit=True):
                    t = st.text_input("일일 습관", placeholder="예: 운동 가기")
                    days = st.multiselect("요일", range(7), default=list(range(7)),
                                          format_func=lambda d: WEEKDAYS[d])
                    if st.form_submit_button("습관 추가") and t.strip():
                        if days:
                            db.add_habit(conn, w["id"], t.strip(), days)
                            st.rerun()
                        else:
                            st.warning("요일을 하나 이상 골라 주세요.")
                if st.button("이 주 목표 삭제", key=f"del_w{w['id']}"):
                    db.delete_week_goal(conn, w["id"])
                    st.rerun()
                st.divider()
            with st.form(f"add_week_{m['id']}", clear_on_submit=True):
                a, b = st.columns([1, 2])
                wk = a.selectbox("주", weeks, index=weeks.index(week_start(today)),
                                 format_func=lambda d: f"{d:%m/%d}주")
                t = b.text_input("주 목표", placeholder="예: 운동 4회")
                if st.form_submit_button("주 목표 추가") and t.strip():
                    db.add_week_goal(conn, m["id"], wk, t.strip())
                    st.rerun()
            if st.button("이 월 목표 삭제", key=f"del_m{m['id']}", type="secondary"):
                db.delete_month_goal(conn, m["id"])
                st.rerun()

# ── 스티커판 ─────────────────────────────────────────
with tab_board:
    habits, slots, stickers = load()
    counts = daily_counts(slots, stickers, month_start, month_end, today)
    earned, possible, rate = summary(slots, stickers, month_start, month_end, today)
    st.subheader(f"{today:%m}월 스티커판 — ⭐ {earned}장 ({rate:.0%})")

    cells = "".join(f"<div class='hd'>{d}</div>" for d in WEEKDAYS)
    cells += "<div></div>" * month_start.weekday()
    for day in range(1, month_end.day + 1):
        d = month_start.replace(day=day)
        e, p = counts.get(d, (0, 0))
        cls = "full" if p and e == p else ("today" if d == today else "")
        stars = "⭐" * e + "<span class='empty'>☆</span>" * (p - e)
        cells += f"<div class='cell {cls}'><b>{day}</b><div>{stars}</div></div>"
    st.markdown(
        """<style>
        .cal{display:grid;grid-template-columns:repeat(7,1fr);gap:4px}
        .cal .hd{text-align:center;font-weight:600;opacity:.7}
        .cal .cell{border:1px solid rgba(128,128,128,.3);border-radius:8px;min-height:64px;padding:4px;font-size:13px;word-break:break-all}
        .cal .full{background:rgba(255,200,0,.18);border-color:#f5b700}
        .cal .today{border:2px solid #4c8bf5}
        .cal .empty{opacity:.35}
        </style>""" + f"<div class='cal'>{cells}</div>",
        unsafe_allow_html=True,
    )

    st.subheader("주별 달성률")
    rows = []
    for wk in weeks:
        e, p, r = summary(slots, stickers, wk, wk + timedelta(days=6), today)
        if p:
            rows.append({"주": f"{wk:%m/%d}주", "달성률(%)": round(r * 100)})
    if rows:
        st.bar_chart(pd.DataFrame(rows).set_index("주"))
    else:
        st.caption("아직 기록이 없어요.")

    st.subheader("월 목표별 달성률")
    for m in db.list_month_goals(conn, month_key):
        m_slots = [(h["id"], h["week_start"], h["days"]) for h in habits if h["month_goal_id"] == m["id"]]
        e, p, r = summary(m_slots, stickers, month_start, month_end, today)
        st.write(f"🎯 {m['title']} — ⭐ {e}/{p}")
        st.progress(r)
