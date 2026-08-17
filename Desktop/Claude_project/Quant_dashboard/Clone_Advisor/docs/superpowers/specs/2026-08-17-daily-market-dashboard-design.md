# 일간 시황 대시보드(Family A) 설계 스펙

- **날짜**: 2026-08-17
- **로드맵 위치**: P2 후속 — 시황 브리핑 에이전트(P2, `advisor_briefing.py`/`advisor_news.py`)가 생성하는 원시 데이터·페르소나 코멘트를, 참고 이미지 수준의 시각화된 일간 대시보드로 렌더링하는 레이어
- **선행 작업**: P2 시황 브리핑 에이전트 완료(2026-08-16, `advisor_briefing.py`·`advisor_news.py` 머지 완료)
- **참고 자료**: 사용자 제공 예시 이미지 12장(`RecentData/시황/`) — 리버스엔지니어링 결과 4개 템플릿 계열(A/B/C/D) 확인. 이번 스펙은 **Family A(해외 테크·시장 브리핑, `TECH-BRIEF LIGHT v1.2`)만** 대상. B(미·한 증시·정책 2페이지 세트)/C(하방 위험 모니터)/D(ADR 심리 인포그래픽)는 사용자가 명시적으로 후속 스펙으로 분리하기로 결정(2026-08-17).

## 1. 배경 및 목적

기존 P2는 온디맨드 버튼 → 지수 7종 + 뉴스 3건 + 오재승/빈규리 텍스트 코멘트 정도의 단순 카드 렌더링까지만 구현되어 있다. 사용자가 제시한 참고 이미지는 10개 섹션으로 구성된 인포그래픽형 일간 대시보드로, 기존 구현보다 훨씬 풍부하다. 이 스펙은 그 격차를 메워 미국·한국 주식투자자가 매일 확인할 수 있는 시각화된 대시보드를 만드는 것이 목적이다.

## 2. 성격

- 대상 템플릿: Family A(미국 지수 중심 1페이지, "Global→Korea Impact Flow"로 한국 투자자와 연결). 실제 예시 3개 인스턴스(8/6·8/7·8/8)에서 스켈레톤(10섹션 구성)이 완전히 고정되어 있음을 확인 — 데이터/테마만 매일 바뀜.
- **LLM 미사용, 룰 템플릿만 사용**(사용자 결정, 2026-08-17) — 기존 P2의 "숫자는 코드가 계산, 문장은 템플릿이 조립" 원칙을 그대로 확장. `advisor_briefing.py`가 2026-08-16에 이미 Anthropic API 의존성을 제거하고 룰 템플릿으로 전환한 것과 동일선상.
- 산출물은 **2가지**(사용자 결정): ① Streamlit 라이브 대시보드(기존 "📰 시황 브리핑" 탭 확장, 온디맨드 버튼 트리거 유지) ② 정적 HTML 리포트(`reports/YYYY-MM-DD_briefing.html`, 다운로드 가능) — 둘 다 동일한 10섹션 dict를 소비하는 별도 렌더러.
- 정적 리포트는 원본 이미지의 실제 사진(뉴스 관련 스톡 사진 등)은 재현하지 않고 **아이콘/이모지 기반 카드**로 단순화(사용자 승인, 2026-08-17) — 레이아웃·색상·섹션 구조·수치는 동일하게 재현.

## 3. 섹션 스펙 (10개)

원본 이미지 섹션 번호와 1:1 대응. "생성 방식" 열은 룰 템플릿의 구체적 근거를 명시한다.

| # | 섹션 | 생성 방식 |
|---|------|-----------|
| ① Today's Summary (3카드) | Tech Dashboard 8개 지표 중 `\|chg_pct\|` 상위 3개를 골라 문장 템플릿(`"{name} {sign}{pct}%로 {label}"`)에 삽입 |
| ② 오늘 반드시 알아야 할 3가지 | ①과 동일 원본 데이터, 카드 포맷(01/02/03 숫자 배지 + 짧은 라벨)만 다르게 재사용 — 별도 계산 없음 |
| ③ Tech Dashboard (8타일) | `advisor_news.get_market_dashboard()`에 10Y 국채(`^TNX`) 추가 → 기존 7개(S&P500/Nasdaq/Dow/SOX/VIX/DXY/USD-KRW)에서 8개로 확장 |
| ④ Today's Action | **신규 코드 없음** — 기존 `advisor_briefing.generate_ojs_commentary()`의 `action`/`commentary` 필드를 그대로 사용 |
| ⑤ TOP NEWS (3카드, 무슨일/왜중요/시장영향) | 무슨일=헤드라인 원문(기존 `select_top_headlines()`). 왜중요/시장영향=헤드라인 텍스트에 대한 키워드 매칭(예: "Fed"/"CPI"/"rate"→금리 태그, 반도체 티커명→SOX 연동 태그) 결과를 고정 문장 템플릿에 삽입. 실제 기사 본문 분석이 아니므로 원본 이미지보다 해설 깊이는 얕음(사용자 승인) |
| ⑥ Global → Korea Impact Flow (4단계) | 신규 `impact_rules.json`: Tech Dashboard 중 `\|chg_pct\|`가 가장 큰 드라이버 1개를 골라 (드라이버, 방향) → 한국영향 문구로 매핑. 4단계 카드(글로벌 요인 → 미국 시장 반응 → 한국 전달 경로 → 핵심 확인)로 조립 |
| ⑦ 오늘 시나리오 (BULL/BASE/BEAR) | 기존 `advisor_data.compute_ojs_signals()`(레짐/RSI14/MA200 이격) + Tech Dashboard의 VIX 레벨을 조합해 룰 매칭 → 3개 시나리오 카드 중 하나를 "가장 유력"으로 표시 |
| ⑧ 오늘·이번주 일정 | 신규 `econ_calendar.json`(CPI/PPI/고용보고서/FOMC 등 정기 발표일 목록) — **사용자가 주기적으로 수기 갱신 필요**(무료 실시간 캘린더 API 없음, 사용자 승인). `as_of` 기준 향후 7일 이벤트만 필터링해 표시 |
| ⑨ Fact / Impact (표) | ⑥과 동일한 `impact_rules.json` 재사용, 상위 3~4개 드라이버를 표 형태(사실/영향)로 나열 |
| ⑩ 수혜 가능 카테고리·관찰기업 TOP10 (미국5+한국5) | 신규 `theme_watchlist.json`(카테고리·대표기업 시드 데이터, 원본 이미지 예시 내용을 초기값으로 사용) — 오늘 헤드라인(영문+한글)에서 카테고리별 키워드 매칭 건수로 순위만 동적 재정렬, 동률 시 시드 순서 유지 |

## 4. 컴포넌트

### `advisor_news.py` (수정)
- `_DASHBOARD_TICKERS`에 `"us10y": "^TNX"` 추가. `get_market_dashboard()` 로직 변경 없음(딕셔너리 확장만으로 8개 지표 자동 반영).

### `impact_rules.json` (신규, `Clone_Advisor/` 루트 — `ojs_rulebook.json`/`binkyuri_rulebook.json`과 동일 위치)
- 구조: `{"version": "0.1", "rules": [{"id", "driver", "direction", "threshold_pct", "korea_impact", "category"}, ...]}`
- 드라이버: sp500/nasdaq/dow/sox/vix/us10y/dxy 각각 상승/하락 2방향 — 약 12~14개 룰.

### `econ_calendar.json` (신규, 동일 위치)
- 구조: `{"events": [{"date", "time_kst", "event", "importance", "source"}, ...]}`
- 사용자가 주기적으로 직접 갱신하는 것을 전제로 한다.

### `theme_watchlist.json` (신규, 동일 위치)
- 구조: `{"us_top5": [{"rank_seed", "category", "company", "keywords": [...]}, ...], "kr_top5": [...]}`
- 초기 시드 데이터는 원본 이미지 예시(NVIDIA/Arista Networks/Vertiv/Micron/Disney, SK하이닉스/삼성전자/한미반도체/이수페타시스/HD현대일렉트릭)를 그대로 사용.

### `advisor_dashboard.py` (신규 — 10섹션 오케스트레이션)
- `summarize_movers(dashboard, top_n=3) -> list[dict]`: ①/② 공용.
- `apply_impact_rules(dashboard, rules) -> dict`: ⑥ flow 4단계 + ⑨ fact/impact 리스트 반환.
- `generate_scenarios(ojs_signals, vix) -> list[dict]`: ⑦ BULL/BASE/BEAR 3개.
- `load_econ_calendar(as_of=None) -> list[dict]`: ⑧.
- `rank_theme_watchlist(watchlist, headlines, kr_headlines) -> dict`: ⑩ us_top5/kr_top5 재정렬.
- `build_dashboard() -> dict`: `advisor_briefing.build_briefing()` 호출 + 위 함수 조합, 10섹션 최종 dict 반환 (`summary`, `must_know`, `tech_dashboard`, `todays_action`, `top_news`, `impact_flow`, `scenarios`, `calendar`, `fact_impact`, `top10`, `meta`).

### `advisor_report.py` (신규 — 정적 HTML 렌더러)
- `render_html(dashboard: dict) -> str`: 10섹션 HTML 문자열 조립. 외부 템플릿 엔진 의존성 없이 순수 Python 문자열 포맷(기존 프로젝트 스타일과 동일). 카드 그리드·색상(상승 초록/하락 빨강/네이비 헤더) CSS는 `<style>` 인라인.
- `save_report(html: str, as_of: date | None = None) -> Path`: `reports/YYYY-MM-DD_briefing.html` 저장.

### `advisor_app.py` (수정)
- 기존 tab2("📰 시황 브리핑") 렌더링을 `build_dashboard()` 기반 10섹션 카드 레이아웃으로 확장.
- "📥 리포트 다운로드(HTML)" 버튼 추가 — `st.download_button(data=render_html(...), file_name=f"{date}_briefing.html")`.

## 5. 데이터 흐름

```
버튼 클릭
  └─ advisor_briefing.build_briefing()      [기존, 변경 없음]
       ├─ dashboard (8지표, us10y 추가)
       ├─ headlines (top3, 영문)
       ├─ ojs (오재승 해설 + action)
       └─ bkr (빈규리 해설)
            └─ advisor_dashboard.build_dashboard()
                 ├─ summarize_movers(dashboard)        → ①②
                 ├─ apply_impact_rules(dashboard, impact_rules.json) → ⑥⑨
                 ├─ generate_scenarios(ojs.signals, vix) → ⑦
                 ├─ load_econ_calendar()                → ⑧
                 ├─ rank_theme_watchlist(..., headlines, kr_raw) → ⑩
                 └─ 10섹션 dict
                      ├─ advisor_app.py: Streamlit 카드 렌더링
                      └─ advisor_report.render_html() → save_report() → 다운로드 버튼
```

## 6. 에러 처리

- 각 신규 JSON(`impact_rules.json`/`econ_calendar.json`/`theme_watchlist.json`) 로드 실패 시 해당 섹션만 `_status: "CONFIG_MISSING"`으로 표시, 나머지 섹션은 정상 렌더링(기존 부분 실패 허용 원칙 유지).
- `us10y`(`^TNX`) 조회 실패는 기존 `get_market_dashboard()`의 개별 `_status: "NO_DATA"` 패턴을 그대로 따름 — 나머지 7개 지표는 영향 없음.
- 일정(⑧)이 비어 있으면(향후 7일 내 등록된 이벤트 없음) "등록된 일정 없음" 안내로 대체, 에러 아님.

## 7. 테스트

- 기존 방식대로 Streamlit `AppTest`로 확장된 tab2 렌더링에 예외/에러 없는지 확인.
- `advisor_report.render_html()`은 실제 `build_dashboard()` 출력으로 스모크테스트(HTML 파싱 가능 여부, 10섹션 마커 존재 확인).
- JSON 룰 파일 3종은 로드 시 스키마 검증(필수 키 존재) 테스트.

## 8. Out of Scope (후속 스펙으로 분리, 사용자 확정 2026-08-17)

- **Family B**(미·한 증시·정책 2페이지 세트, 오전/정오/마감 세션별 반복 생성) — 별도 스펙.
- **Family C**(미국 증시 하방 위험 모니터, 이벤트 트리거형) — 별도 스펙.
- **Family D**(한국 증시 ADR 심리 인포그래픽) — 별도 스펙.
- LLM 기반 서술 생성(뉴스 본문 심층 분석, 시나리오 확률 추정 등) — 이번엔 룰 템플릿만.
- 경제 캘린더 자동 수집(무료 API/크롤링) — 이번엔 수기 JSON 갱신.
- 매일 자동 스케줄 생성 — 이번에도 온디맨드 버튼 유지(기존 P2 결정과 동일).
