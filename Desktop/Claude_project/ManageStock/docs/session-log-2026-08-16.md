# ManageStock 개발 세션 로그 — 2026-08-16

## 개요

`MS_requirement_v1.1.txt`(주식/ETF 포트폴리오 카테고리별 비중·수익률 대시보드 요구사항)를 브레인스토밍 → 설계 스펙 → 구현 계획 → subagent-driven-development 구현 → 실사용 중 발견된 버그 수정/기능 추가까지 하루 만에 처음부터 끝까지 진행한 세션.

**최종 상태**: v1 기능 전부 동작, 로컬에서 `http://localhost:8503`으로 실행 중, pytest 38/38 통과, 커밋 13개.

---

## 1. 브레인스토밍 → 설계 스펙

`superpowers:brainstorming` 스킬(architectural 경로)로 요구사항 명확화. 주요 확정 사항:

| 항목 | 결정 |
|---|---|
| 데이터 저장 | `data/holdings.csv` 수동 입력·영속화. DB 없음 |
| 시세 | yfinance, 새로고침 시 조회(지연 시세), `st.cache_data(ttl=600)` |
| 베타값 | 표시 전용, 계산 로직 관여 안 함 |
| 통화 | USD·KRW 혼합 → 원화 합산. 환차익/주가수익 분리 기능은 **최종 제외**(매입시점 환율 기록이 번거롭다는 판단) — 오늘 환율을 매입·평가 양쪽에 동일 적용 |
| 카테고리 | 기본 6개 + 자유 추가 |
| 티커 입력 | 이름→티커 프리셋 자동입력 + 신규 종목 직접입력 |
| 추가 채택 기능 | 일별 자산 스냅샷 히스토리 → 총자산 추이 라인차트 |
| 포트 | 8503 (8501=Quant_dashboard, 8502=Quant_realestate와 충돌 방지) |

스펙 문서: `docs/superpowers/specs/2026-08-16-managestock-design.md`
(참고: 초기 요청은 fable 모델로 설계 진행이었으나 세션 중 fable 크레딧 소진 확인되어 Sonnet으로 대체 진행함)

## 2. 구현 계획

`superpowers:writing-plans`로 10개 태스크 TDD 계획 작성. dataviz 스킬로 카테고리 색상 팔레트(CVD 안전 검증된 8슬롯) 적용, 국내 관례에 맞춰 수익률 상승=빨강/하락=파랑 배색.

계획 문서: `docs/superpowers/plans/2026-08-16-managestock-implementation.md`

## 3. 구현 (subagent-driven-development)

사용자 선택으로 main 브랜치에 직접 작업(격리 워크트리 대신 — 저장소 자체가 홈 디렉터리 루트인 특이 구조라 targeted add만 사용). 태스크별 구현 서브에이전트 + 리뷰 서브에이전트 루프로 진행.

| 태스크 | 내용 | 결과 |
|---|---|---|
| 1 | 프로젝트 스캐폴딩 + `categories.py` | 리뷰 통과 |
| 2 | `data_io.py` holdings 읽기/쓰기 | 리뷰 통과 |
| 3 | `data_io.py` history.csv 스냅샷 | 리뷰 통과 |
| 4 | `portfolio.py` 종목별 지표 계산 | 리뷰 통과 |
| 5 | `portfolio.py` 카테고리 집계 + 전체 합계 | 리뷰 통과 |
| 6 | `market_data.py` 시세/환율 조회 | 리뷰 통과 |
| 7 | `app.py` 골격 + 종목관리 탭 | **수정 1회**: 프리셋 선택이 `st.form` 안에 있어 실시간 미리보기 안 되던 문제 → 폼 밖으로 이동 |
| 8 | `app.py` Tab1 대시보드 | 리뷰 통과 (계획의 curl/grep 부팅체크가 Streamlit 특성상 원천 불가능함을 발견, AppTest로 대체) |
| 9 | 자산 스냅샷 + 추이 차트 | **수정 1회**: 시세 조회 전부 실패 시 자산=0 스냅샷이 영구 저장되는 데이터 품질 버그 → 실패 시 스냅샷 자체를 안 남기도록 수정 |
| 10 | 최종 통합 검증 | 7개 항목 전부 PASS (브라우저 수동검증 단계는 AppTest 자동검증으로 대체) |

전체 브랜치 최종 리뷰(opus)는 **세션 사용 한도(usage limit)로 중단, 미완료**. 개별 태스크 10개는 전부 리뷰 통과했고 통합검증도 버그 없이 끝나 리스크는 낮다고 판단, 사용자 요청으로 세션 마무리. SDD 워크스페이스(`~/.superpowers/sdd/2026-08-16-managestock-implementation/`)는 삭제하지 않고 보존 — 추후 최종 리뷰만 이어서 실행 가능.

## 4. 실사용 중 발견/추가된 것

구현 완료 후 사용자가 실제로 웹에서 써보다 발견한 이슈와 요청 기능:

### 버그 수정: 빈 행 크래시
- **증상**: `종목 관리` 탭 그리드에서 `+`로 행을 추가했다가 값을 안 채우고 저장 → 앱이 `TypeError: sequence item 0: expected str instance, float found`로 죽음
- **근본 원인**: `systematic-debugging` 스킬로 추적 — 빈 티커(NaN)가 시세 조회 실패 목록에 들어갔다가 경고 메시지 `", ".join()`에서 문자열이 아닌 값과 충돌
- **수정**: `data_io.drop_incomplete_holdings()` 추가(TDD), 대시보드 로드 시 + 종목관리 저장 시 양쪽에서 필터링

### 기능 추가: 카테고리 색상 직접 선택
- `종목 관리` 탭 하단에 카테고리별 `st.color_picker` 추가
- `data/category_colors.csv`에 영속 저장
- `categories.get_category_color_map(..., overrides=...)`로 자동배정 색상 위에 사용자 선택 우선 적용
- 비중 파이차트에만 적용(수익률 바차트는 상승/하락 고정색, 추이차트는 단일 시리즈라 대상 아님)

## 5. 커밋 히스토리 (전체 13개, 최신순)

```
0a5b5ac fix: 보유종목 빈 행 크래시 방지 + 카테고리 색상 직접 선택 기능
53bb8c4 docs: 원본 요구사항 문서 + 구현 계획 문서 추가
e8ea63e fix: 시세 조회 전부 실패 시 자산 스냅샷을 기록하지 않도록 이동
e3c9b0c feat: 일별 자산 스냅샷 저장 + 총자산 추이 라인차트
953ecfc feat: 포트폴리오 대시보드 탭(메트릭/비중 파이차트/수익률 바차트/상세테이블)
48b8f44 fix: 프리셋 선택박스를 폼 밖으로 이동해 티커/통화 실시간 미리보기 반영
4950f62 feat: Streamlit 앱 골격 + 종목 관리 탭(추가/수정/삭제)
7022160 feat: yfinance 시세/환율 조회 + 캐시 래퍼 + 환율 폴백 로직
c8ba284 feat: 카테고리별 비중/수익률 집계 + 전체 합계 계산
8a2f980 feat: 종목별 평가금액/매입금액/수익률 계산 로직
76c4d7c feat: history.csv 일별 자산 스냅샷 누적 기능
d6c0530 feat: holdings.csv 읽기/쓰기 + 통화 자동판별
c94aed0 chore: ManageStock 프로젝트 스캐폴딩 + 카테고리/티커프리셋/색상 정의
```

## 6. 파일 구조 (최종)

```
ManageStock/
  app.py                  # Streamlit 진입점 (Tab1: 대시보드, Tab2: 종목 관리)
  portfolio.py             # 순수 계산 함수 (평가금액/수익률/카테고리 집계)
  data_io.py                # holdings/history/category_colors CSV 읽기·쓰기
  market_data.py             # yfinance 시세+환율 조회, 캐시+폴백
  categories.py               # 카테고리 상수, 티커 프리셋, 색상 팔레트
  data/                        # holdings.csv, history.csv, category_colors.csv (gitignore)
  tests/                        # pytest 38개
  docs/superpowers/specs/        # 설계 스펙
  docs/superpowers/plans/         # 구현 계획
  .streamlit/config.toml           # port 8503
  run_app.bat                       # 실행 스크립트
```

## 7. 남은 일

- 전체 브랜치 최종 리뷰(가장 상위 모델) 미완료 — 다음 세션에서 "최종 리뷰 마저 해줘"로 재개 가능
- 스펙 부록에 "TBD 구현 시 검증 필요"로 표시된 국내 테마 ETF 티커 프리셋(TIGER/KODEX 나스닥100 레버리지, KODEX 미국우주항공, BOTZ류 등) 아직 실제 확인 안 됨 — 필요 시 직접 티커 입력으로 우회 가능
- 증권사 API 자동연동, 배당 추적, 다중 포트폴리오는 스펙상 v1 범위 밖으로 명시

---

*세션 종료 전 기록. 프로젝트 메모리: `project_managestock.md` 참고.*
