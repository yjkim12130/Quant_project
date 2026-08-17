# 미국·한국 증시·정책 브리핑(Family B, 마감판) 설계 스펙

- **날짜**: 2026-08-17
- **로드맵 위치**: Family A 후속 — [[project-daily-market-dashboard]] Family B, 백로그 `docs/superpowers/specs/2026-08-17-market-policy-briefing-backlog-B.md`에서 승격
- **선행 작업**: Family A 완료·배포(`advisor_dashboard.py`/`advisor_report.py`, 2026-08-17 main 병합·Streamlit Cloud 배포)

## 1. 배경 및 목적

Family A(해외 테크·시장 브리핑)는 미국 지수 중심 1페이지였다. 이번 스펙은 참고 이미지의 두 번째 계열(Family B — "미국·한국 증시·정책 브리핑", 2페이지 세트: PAGE1 한국 증시 뉴스보드 + PAGE2 정책 뉴스보드)을 구현한다. 예시 이미지에는 오전판/정오판/마감판 3개 세션이 존재했으나, 이번 스펙은 **마감판 1개만** 다룬다(사용자 결정, 2026-08-17) — 오전/정오판은 마감판이 안정화된 뒤 별도로 확장.

## 2. 성격

- Family A와 마찬가지로 **LLM 미사용, 룰 템플릿 + 실측 데이터** 원칙을 유지한다.
- Family A와 결정적으로 다른 점: **한국 시장 자체 데이터**(KOSPI/KOSDAQ 지수, 등락종목수, 외국인·기관·개인 수급, 개별종목 시세)가 필요한데 yfinance로는 지수 시세 외엔 불가능하다 → **키움증권 REST API**를 신규 데이터 소스로 도입한다(사용자 실계좌 + API 발급 완료, AppKey/SecretKey는 `Quant_dashboard/kiwoom_api_key/`에 저장·`.gitignore` 처리 완료).
- PAGE2(정책 카드 비교)는 뉴스에서 자동 추출하기엔 정성 판단(Polarity·정확도)이 많이 들어가므로 **사용자가 수기 관리하는 JSON**(`policy_cards.json`, `econ_calendar.json`과 동일 패턴)으로 채운다.
- **부가 기능**: 개별종목 분석 탭(기존 tab1, `advisor_data.py` 기반)에 ATR(절대 변동폭)과 베타 계수(시장 대비 민감도)를 상시 표시하도록 추가한다 — Family B의 지수 ATR과 계산 로직을 공유할 수 있어 이번 스펙에 함께 포함하되, PAGE1/PAGE2 파이프라인과는 독립적인 별도 변경으로 취급한다(§4, §8 참고).

## 3. 데이터 소스 — 키움증권 REST API

- **인증**: AppKey+SecretKey → OAuth 토큰 발급(POST) → 토큰 캐싱(만료 전까지 재사용, 만료 시 재발급). 정확한 엔드포인트 경로·TR(거래) 코드는 **구현 Task 1에서 실제 API 문서를 확인하며 결정**한다 — 이 스펙 작성 시점에는 확정할 수 없다(키움 REST API가 최근에 발급받은 것이라 정확한 스펙은 실제 문서 대조가 필요).
- **필요한 조회 6종**(구현 Task 1에서 각각의 정확한 TR코드/엔드포인트 확인):
  1. KOSPI/KOSDAQ 지수 시세(현재가·등락률)
  2. 등락종목수(ADR 계산용 — 상승/하락/보합 종목 수)
  3. 지수 일봉(OHLC) 히스토리(ATR 계산용, 최소 15거래일)
  4. 투자자별 매매동향(외국인/기관/개인 순매수, KOSPI·KOSDAQ 각각)
  5. 개별종목 시세(삼성전자·SK하이닉스)
  6. 업종별 등락률(업종·종목 리더십 TOP3용)
- **에러 처리**: 기존 프로젝트 관례(advisor_data.py/advisor_news.py)와 동일 — 토큰 발급 실패·개별 엔드포인트 실패는 `_status` 필드로 개별 격리, 한 곳이 실패해도 나머지 섹션은 정상 렌더링.

## 4. 섹션 스펙

### PAGE1 — 한국 증시 마감 뉴스보드 (8섹션)

| # | 섹션 | 생성 방식 |
|---|------|-----------|
| ① KEY THEMES | 아래 KPI 중 변동폭 상위 항목을 짧은 태그로 요약(Family A `summarize_movers` 패턴 재사용) |
| ② 오늘의 결론(3줄) | KOSPI/KOSDAQ 등락 + 외국인 수급 방향 + 핵심 이슈 1개를 문장 템플릿으로 조합 |
| ③ 마감 KPI 6개 | KOSPI·KOSDAQ 지수, 삼성전자·SK하이닉스 시세, 외국인 KOSPI 순매수, USD/KRW(기존 Family A `advisor_news` 재사용) |
| ④ 시장 변동성 지표 | **ADR**(KOSPI/KOSDAQ 각각, 등락종목수 기반 상승/하락 비율) + **ATR**(KOSPI/KOSDAQ 지수 14일) + **수급 해부**(외국인/개인/기관 × KOSPI/KOSDAQ 순매수) — 사용자 추가 요청(2026-08-17) |
| ⑤ 업종·종목 리더십 | 업종별 등락률 상위/하위 + 상승·약세 종목 TOP3 |
| ⑥ 가격→수급→촉발요인→지속성 | Family A `apply_impact_rules` 패턴을 한국 시장 드라이버(KOSPI 등락·외국인 수급·업종 리더십)로 재구성한 4열 테이블 |
| ⑦ 오늘 시나리오 | Family A `generate_scenarios`와 동일한 BULL/BASE/BEAR 룰 매칭, 입력만 KOSPI 레짐 + 외국인 수급 방향으로 교체 |
| ⑧ 오늘 하루 코멘트 | 위 KPI·수급·시나리오를 종합한 3~4문장 텍스트 요약(템플릿) |

### PAGE2 — 정책 뉴스보드 (4섹션)

| # | 섹션 | 생성 방식 |
|---|------|-----------|
| ① 핵심요약 3개 | `policy_cards.json`에서 상위 3개 카드의 요약 필드 그대로 표시 |
| ② 정책카드 비교(미국4+한국4) | `policy_cards.json` 8개 카드(사실상태/향후방향/한국시장영향/polarity/정확도)를 그대로 렌더링 — 자동 생성 없음, 사용자가 채운 값 그대로 |
| ③ 미·한 연결경로 4개 | `policy_cards.json`의 각 카드에 딸린 `korea_link` 필드를 4개 추려 표시 |
| ④ 체크포인트 8개 | `policy_cards.json`의 각 카드에 딸린 `checkpoint` 필드를 모아 표시 |

## 5. 컴포넌트

### `kiwoom_data.py` (신규)
- `get_kiwoom_token() -> str|None`: AppKey/SecretKey로 OAuth 토큰 발급·캐싱. 키 위치는 `Quant_dashboard/kiwoom_api_key/{계좌번호}_appkey.txt`/`_secretkey.txt`(환경변수 우선 폴백은 기존 관례상 추가 가능하나, 키움은 계좌 연동형이라 파일 우선).
- `get_index_quote(code: str) -> dict`: KOSPI/KOSDAQ 지수 시세.
- `get_advance_decline(code: str) -> dict`: 등락종목수(ADR 계산용).
- `get_index_ohlc_history(code: str, days: int = 20) -> list[dict]`: 지수 일봉(ATR 계산용). 각 항목 `{"date", "open", "high", "low", "close"}` — `advisor_data.compute_atr()`이 요구하는 high/low/close 세 시리즈를 여기서 뽑아 넘긴다.
- `get_investor_flow(code: str) -> dict`: 외국인/기관/개인 순매수.
- `get_stock_quote(code: str) -> dict`: 개별종목 시세.
- `get_sector_returns() -> list[dict]`: 업종별 등락률.
- 모든 함수는 실패 시 `{"_status": "NO_DATA"|"AUTH_FAILED", ...}` 반환(기존 패턴 준수), 예외를 던지지 않는다.

### `policy_cards.json` (신규)
- 구조: `{"cards": [{"id", "country": "US"|"KR", "title", "fact_state", "outlook", "korea_impact", "polarity", "accuracy", "korea_link", "checkpoint"}, ...]}`, 미국 4개+한국 4개 총 8개.
- `econ_calendar.json`과 동일하게 **사용자가 주기적으로 수기 갱신**.

### `advisor_dashboard_kr.py` (신규)
- `build_page1() -> dict`: PAGE1 8섹션 dict. `kiwoom_data.py`로 원시 데이터를 받아 `advisor_data.compute_adr(advancers: int, decliners: int, unchanged: int = 0) -> float`(§6의 `compute_atr`과 같은 위치, 등락종목수 → ADR 비율 계산하는 순수 함수)와 `advisor_data.compute_atr()`(§6)을 호출해 지표를 만들고, Family A 패턴(`summarize_movers`류)을 한국 시장 드라이버에 맞게 재구성한 자체 함수들과 결합한다.
- `build_page2() -> dict`: PAGE2 4섹션 dict. `policy_cards.json` 로드·재구성만, 계산 로직 없음.
- `build_briefing_kr() -> dict`: `{"page1": ..., "page2": ..., "generated_at": ...}`.

### 렌더러
- Streamlit: `advisor_app.py`에 신규 탭 "🏦 증시·정책 브리핑" 추가(Family A 탭과 동일하게 온디맨드 버튼).
- 정적 HTML: 기존 `advisor_report.py`에 `render_html_kr(briefing: dict) -> str` 함수 추가(같은 파일, PAGE1/PAGE2 2단 레이아웃만 다르고 CSS·이스케이핑 규칙은 재사용).

## 6. 부가 기능 — 개별종목 ATR·베타 (tab1)

Family B의 PAGE1/PAGE2 파이프라인과는 독립적인 변경. 기존 "🧮 종목 분석" 탭(`advisor_app.py` tab1, `advisor_data.py` 기반)에 다음을 추가:

- `advisor_data.py`에 `compute_atr(close: pandas.Series, high: pandas.Series, low: pandas.Series, period: int = 14) -> float|None` 추가 — True Range 평균, Family B의 지수 ATR과 동일 함수 재사용(지수든 개별종목이든 OHLC만 있으면 계산 가능). 기존 `get_price_history(ticker)`는 종가(Close)만 반환하므로, tab1에서 이 함수를 쓰려면 high/low도 받아오도록 확장하거나(예: `get_price_history`가 내부적으로 쓰는 yfinance `history()` 호출이 이미 OHLC를 다 갖고 있으므로 버리지 않고 반환) 별도 조회 경로가 필요 — 구현 시 결정.
- `advisor_data.py`에 `compute_beta(stock_close: pandas.Series, benchmark_close: pandas.Series) -> float|None` 추가 — 수익률 공분산/벤치마크 분산. 벤치마크는 종목의 `market` 필드 기준: 한국 KOSPI 종목→`^KS11`, KOSDAQ 종목→`^KQ11`, 미국 종목→`^GSPC`.
- `compute_quant_signals()`(또는 별도 신규 함수)의 반환 dict에 `atr`/`beta` 키 추가.
- `advisor_app.py` tab1의 "② 정량 신호" 섹션에 ATR·베타 metric 2개 추가.

## 7. 에러 처리

- 키움 API 토큰 발급 실패 → PAGE1 전체가 아니라 개별 섹션이 "데이터 조회 실패" 안내로 대체(각 섹션이 독립적으로 `_status` 체크).
- `policy_cards.json` 로드 실패/malformed → Family A의 malformed-JSON 교훈을 그대로 적용(try/except, `.get()` 기반 접근, 빈 리스트로 폴백) — Family A 최종 리뷰에서 발견된 패턴을 처음부터 반영.
- ADR/ATR 계산에 필요한 히스토리가 부족하면(신규 상장 등 예외 상황) 해당 지표만 "—"로 표시, 나머지 KPI는 정상 표시.

## 8. Out of Scope

- 오전판/정오판 세션(마감판 안정화 후 별도 스펙).
- "다음 브리핑 비교용 기준선"(전회 실행 결과와 diff) — 상태 저장이 필요한 신규 개념이라 이번엔 제외.
- Family C(하방위험 모니터)/D(ADR 심리 인포그래픽 단독 페이지) — 백로그 유지. 단, 이번 스펙의 ADR/ATR 계산 로직(`compute_adr`/`compute_atr`)은 Family D 착수 시 그대로 재사용 가능.
- 키움 API의 정확한 TR코드/엔드포인트 확정 — 구현 Task 1에서 실제 문서 대조로 해결(§3).
