# 칭찬스티커 플래너 — 설계 (2026-10-07)

요구사항 원문: `requirement.txt`

## 데이터 (SQLite `planner.db`)
- month_goal(id, month 'YYYY-MM', title)
- week_goal(id, month_goal_id → month_goal, week_start 월요일 날짜, title)
- habit(id, week_goal_id → week_goal, title) — week_start부터 7일간 매일 체크 대상
- sticker(habit_id → habit, date) — PK(habit_id, date). 체크 = 1장
- 상위 목표 삭제 시 하위 항목·스티커 연쇄 삭제

## 달성률
달성률 = 받은 스티커 ÷ 받을 수 있었던 스티커.
받을 수 있었던 스티커 = (습관, 날짜) 칸 중 기간 안 ∩ 습관의 주 안 ∩ 날짜 ≤ 오늘.
연속 달성일(streak): 오늘부터 거꾸로, 그날 모든 습관을 지킨 날이 이어지는 일수.
오늘이 아직 미완이면 어제부터 센다. 습관이 없는 날에서 끊긴다.

## 화면 (탭 3개)
1. 오늘 — 체크박스, 오늘/주/월 달성률, streak
2. 목표 설정 — 월 → 주 → 일 추가·삭제
3. 스티커판 — 월 달력(⭐), 주별 달성률 차트, 월 목표별 달성률

## 파일
app.py(UI) · db.py(저장) · stats.py(순수 계산) · tests/ · requirements.txt
실행 포트 8504 (8503은 advisor_app 사용 중). 로그인·알림·배포는 범위 밖.
