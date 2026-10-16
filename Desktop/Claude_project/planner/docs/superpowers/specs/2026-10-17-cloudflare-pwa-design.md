# 칭찬스티커 플래너 — Cloudflare PWA 설계 (2026-10-17)

기존 Streamlit 앱(`planner/app.py`)을 PC가 꺼져도 동작하는 공유 웹앱으로 옮긴다.
Streamlit 앱은 그대로 두고, 새 앱은 `planner/web/`에 만든다. 기존 데이터는 옮기지 않는다.

## 결정 사항
- 가족이 **플래너 하나를 함께** 쓴다 (사용자 구분 없음).
- 접근 제어: **가족 비밀번호** 하나. Cloudflare secret `FAMILY_PASSWORD`.
- 호스팅: Cloudflare Pages(정적 PWA) + Pages Functions(`/api/*`) + D1. 주소는 `*.pages.dev`.

## 데이터 (D1, 기존 SQLite 스키마와 동일)
- month_goal(id, month 'YYYY-MM', title)
- week_goal(id, month_goal_id, week_start 월요일 'YYYY-MM-DD', title)
- habit(id, week_goal_id, title, days '0123456' — 월=0 … 일=6)
- sticker(habit_id, date) PK(habit_id, date)
- 상위 삭제 시 하위·스티커 연쇄 삭제 (FK ON DELETE CASCADE — D1은 외래키를 기본으로 강제)

## API (모두 헤더 `X-Family-Key` = encodeURIComponent(비밀번호) 필요, 틀리면 401 — 한글 비밀번호도 헤더로 보내기 위해 인코딩)
- GET  /api/state → { monthGoals, weekGoals, habits, stickers } (전체 데이터; 규모가 작아 한 번에)
- POST /api/month-goals {month, title}
- POST /api/week-goals {monthGoalId, weekStart, title}
- POST /api/habits {weekGoalId, title, days:[0..6]} — days 비면 400
- DELETE /api/{month-goals|week-goals|habits}/:id
- PUT /api/stickers {habitId, date, on} — on=true 중복 무시
- 입력 검증 실패 → 400, 없는 경로 → 404

## 계산 (stats.js — stats.py 이식, 동일 규칙)
- 습관 칸 = week_start부터 7일 중 days 요일, 날짜 ≤ 오늘
- 달성률 = 받은 스티커 ÷ 칸 수
- 연속 달성일: 할 일 없는 날은 건너뜀, 오늘 미완이면 어제부터, 지정 요일을 놓치면 끊김
- 날짜는 기기 로컬 시간 기준

## 화면 (탭 3개 + 잠금 화면)
- 잠금: 비밀번호 입력 → GET /api/state로 검증 → localStorage 저장. 설정에 로그아웃
- 오늘 / 목표 설정(요일 선택 포함) / 스티커판(월 달력, 주별 막대, 월 목표별 진행)
- 갱신: 동작 직후, 화면 복귀(visibilitychange) 시, 열려 있는 동안 30초마다
- 오프라인: 앱 셸은 서비스워커 캐시, API 실패 시 "인터넷 연결 필요" 배너와 체크 비활성화

## PWA
manifest.webmanifest(이름, 아이콘, standalone), sw.js(앱 셸 캐시, /api는 캐시하지 않음)

## 테스트
- stats.js: test_stats.py 케이스 이식 (node --test)
- API: node:sqlite 기반 가짜 D1로 핸들러 단위 테스트 (인증, 연쇄 삭제, 요일, 스티커 중복)
- 배포 전 `wrangler pages dev`로 로컬 확인

## 배포
사용자: `npx wrangler login`, 가족 비밀번호 결정.
Claude: D1 생성·스키마 적용, secret 등록, `wrangler pages deploy`. 공개 배포 직전 사용자 확인.

## 범위 밖
가족원별 계정, 오프라인 체크 후 동기화, 알림, 커스텀 도메인, 요청 횟수 제한.
