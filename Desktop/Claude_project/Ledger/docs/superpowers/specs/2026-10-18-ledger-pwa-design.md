# 우리집 가계부 PWA 전환 설계 (2026-10-18)

## 배경

Streamlit Cloud 가계부(`my-ledger`)는 열 때마다 2~3분을 기다려야 한다.
원인은 데이터가 아니다(시트 383행·49KB, 읽기 1.6초). 무료 플랜의 절전에서 깨어나며
서버를 새로 띄우고, 쓰지도 않는 `st-gsheets-connection`까지 다시 설치하기 때문이다.
서버가 잠들지 않는 Cloudflare Pages PWA로 옮긴다.

## 목표 / 비목표

- 목표: 열자마자(1초 안) 마지막 데이터가 보이고, 1~2초 안에 최신으로 바뀐다.
- 목표: 화면 3개를 지금 앱과 같은 내용·규칙으로 다시 만든다.
- 비목표: 입력 방식 변경(구글 폼 그대로), 시트 비공개 전환, 데이터 이전, 새 기능.
- Streamlit 앱은 새 앱 확인 전까지 그대로 둔다.

## 구조

`Desktop/Claude_project/Ledger/web/`. `planner/web`과 같은 구성(빌드 없는 HTML/JS, `node --test`).

```
web/
  public/        index.html, style.css, app.js(화면), ledger.js(계산), sw.js, manifest, 아이콘
  src/api.js     /api/data 처리
  functions/api/[[path]].js   → src/api.js 연결
  tests/         ledger.test.js, api.test.js
  wrangler.toml  name = "woorijip-ledger"
```

- 주소: `https://woorijip-ledger.pages.dev` (`our-ledger`는 남이 쓰는 중).
- `GET /api/data`
  - 헤더 `X-Ledger-Key` = encodeURIComponent(비밀번호), Pages secret `LEDGER_PASSWORD`와 상수시간 비교.
    틀리면 401, secret 미설정이면 500.
  - 서버에서 gviz CSV 두 장(`Data`, `Target`)을 받아 CSV 파싱(따옴표 안 쉼표 처리) 후 JSON 반환:
    `{ fetchedAt, targets: [{category, goal}], rows: [{timestamp, date, category, small, card, amount, payType}] }`
  - `date`는 `M/D/YYYY` → `YYYY-MM-DD`, 해석 불가면 `null`. `amount`는 숫자가 아니면 0 (pandas `to_numeric(...).fillna(0)`과 동일).
    분류 문자열은 앞뒤 공백 제거.
  - 구글 응답은 Cache API로 60초 캐시. `?fresh=1`이면 캐시를 건너뛴다(새로고침 버튼).
  - 구글 읽기 실패 시 502.
- 시트 ID와 폼 주소는 서버 코드(`src/api.js`)에만 둔다. 폼 iframe 주소는 인증 후 응답에 담아 준다.

## 빠르게 열기

- 서비스워커가 앱 파일을 저장(앱 파일은 네트워크 우선, 실패 시 저장본).
- 마지막 `/api/data` 응답을 localStorage에 저장 → 열자마자 그걸로 그리고, 바로 최신을 받아 다시 그린다.
- 상단 상태줄: "갱신 중…" / "방금 갱신" / "N분 전 데이터 · 최신 아님"(실패 시).
- 비밀번호는 localStorage에 기억. 401이면 저장 데이터와 비밀번호를 지우고 다시 묻는다.

## 화면 (지금 앱과 같은 규칙)

오늘 = 한국 시간(UTC+9) 기준 날짜.

1. **💰 소비 입력**: 구글 폼 iframe(높이 1500).
2. **📊 실시간 대시보드** (이번 달)
   - Target 순서대로 분류별 이번 달 합계(Target에 없는 분류는 제외). 세로 막대그래프(SVG).
   - 분류별 카드: `경과비율 = 오늘 일 / 이번 달 일수`, `누적계획 = 목표 × 경과비율`.
     - 목표 > 0, 실제 ≤ 계획: 초록 = min(실제/목표%, 100), "계획대비 절약중 (N원 여유)".
     - 목표 > 0, 실제 > 계획: 초록 = min(계획%, 100), 빨강 = min(max(실제% − 계획%, 0), 120 − 계획%), "계획대비 과소비중 (N원 초과)".
     - 목표 = 0: 막대 없음, "예산 미설정 (-)".
     - 파란 세로선 = 계획% 위치. 금액은 정수 내림 + 천단위 쉼표.
   - "N월 총 지출" = 위 분류 합계의 합.
3. **📜 전체 내역 및 관리**
   - ◀ 연도 선택 · 월 선택 ▶ (기본 이번 달, ◀▶는 해를 넘어 이동). 연도 목록 = 기록된 연도 ∪ 올해 ∪ 선택 연도, 내림차순.
   - 그 달 행을 날짜순(같은 날은 원래 순서) 정렬한 표 + "누적 총액" 열(가로 스크롤).
   - "YYYY년 M월 총 지출" = 그 달 전체 합(분류 무관).
   - 캘린더: 월요일 시작, 일별 합계를 만원 단위(`9.3만`, `.0만`은 `만`), 0이면 `-`, 오늘 강조.
   - "🗑️ 구글 시트에서 수정/삭제하기" 링크.
- 🔄 새로고침 버튼(`?fresh=1`).

## 검증

- `ledger.js` 단위 테스트: 진행바 3가지 경우, 만원 표기, 캘린더 배치, 월 이동, 정렬·누적.
- `api.js` 테스트: CSV 파싱(따옴표·쉼표·빈칸), 날짜 변환, 인증 401/500, 캐시 우회.
- 실데이터 대조: 월 합계 2026-04 10,130,856 / 05 4,178,946 / 06 1,609,026 / 07 2,574,127.
- 배포 후 Streamlit 앱과 같은 달 화면 비교, 첫 화면 표시 시간 측정.

## 사용자 작업

Cloudflare 대시보드 → woorijip-ledger → 설정 → 변수 및 비밀에 `LEDGER_PASSWORD` 등록.
