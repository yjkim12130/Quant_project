# 시황 브리핑 에이전트 설계 스펙

- **날짜**: 2026-08-16
- **로드맵 위치**: P2 (자문역 인사이트 에이전트 프로젝트, [[project-advisor-agent]])
- **선행 작업**: 데이터 갱신 트랙 완료(ojs_rulebook.json v0.3, binkyuri_rulebook.json v0.2)

## 1. 배경 및 목적

사용자가 참고 이미지("해외 테크·시장 브리핑")를 제시하며 뉴스/시황 크롤링 기반 브리핑 에이전트 구축을 요청. 기존 로드맵 P2는 "오재승식 아침시황"을 RAG로 모사하는 페르소나 콘멘터리로 정의되어 있었으나, 참고 이미지는 출처가 명시된 객관적 데이터 대시보드(지수·VIX·DXY 등 + TOP 뉴스 3건)에 가까움. 브레인스토밍 결과 **객관 데이터 + 페르소나 해설을 결합**하는 하이브리드로 성격을 확정.

## 2. 성격

- 객관 데이터 섹션(Summary/Tech Dashboard/TOP News)은 출처가 명시된 사실 정보만 다룬다.
- 그 위에 **오재승 페르소나(매크로·타이밍)** 와 **빈규리 페르소나(펀더멘탈)** 해설을 각각 별도 카드로 붙인다 — 두 자문역의 관점이 원래도 분리되어 있었으므로(오재승=시황/타이밍, 빈규리=개별기업/펀더멘탈) 하나로 합치지 않는다.

## 3. 추천 범위 정책 (핵심 결정 사항)

두 페르소나의 "추천 구체성" 수준을 다르게 가져간다 — **룰북에 실제로 증거로 남아있는 행동 패턴을 따른다**:

- **오재승 = 구체적 추천 가능.** `OJS-MA-01`(200일선 눌림목), `OJS-MACD-01`, `OJS-CASH-01`(마틴게일 5분할), `OJS-DCA-01`(모으기 주문 N일 분할) 전부 `codeable: yes`이며 실측 가격 데이터(yfinance)와 결합해 "매집구간/분할비율/진입가" 같은 구체적 출력을 생성한다. 기존 `advisor_app.py`의 종목별 `ojs_hint()`를 ETF/지수 레벨로 확장하는 것과 동일한 패턴.
- **빈규리 = 해설만, 매수가·타이밍 제시 금지.** `BKR-STYLE-01`("종목소개 ≠ 투자의견")이 실제 채팅 원문에서 그녀가 분석한 모든 종목에 반복 확인된 디스클레이머다. 실제 빈규리는 펀더멘탈·해자·재무만 말하고 타이밍·가격은 항상 비워둔다(원래도 오재승이 "타이밍 문제"로 이어받는 구조). 이 프로젝트의 핵심 KPI가 "자문역 본인을 얼마나 정확히 모사하나(모사 정확도)"이므로, 실제로 안 하던 매수가/타이밍 제시를 하게 하면 페르소나 정확도가 깨진다.
- **빈규리 해설 대상 우선순위**: 헤드라인에 걸리는 종목이 여러 개일 때, `코스닥 승강제 종합분석보고서`(QIA-2026-MK-0703) 40종목 프리미엄리그 후보 리스트에 포함된 종목을 우선 코멘트 대상으로 선택한다 — 그녀가 실제로 이 리포트를 작성했고(BKR distilled_from에 이미 반영), 세미파이브·코미코 등 실제 분석 종목도 이 리스트와 겹쳤던 전례가 있다.

## 4. 컴포넌트

### `advisor_news.py` (신규, `advisor_data.py`와 병렬)
- `get_market_dashboard() -> dict`: S&P500(^GSPC)/Nasdaq(^IXIC)/Dow(^DJI)/반도체지수(^SOX)/VIX(^VIX)/DXY(DX-Y.NYB)/원달러(KRW=X)를 yfinance `fast_info`로 조회. 기존 `get_quote()`의 `.info` rate-limit 함정 회피 패턴(fast_info 우선 + 실패 시 `NO_DATA`) 재사용.
- `fetch_raw_headlines(limit=20) -> list[dict]`: Yahoo Finance 마켓뉴스 RSS(`https://finance.yahoo.com/news/rssindex`)를 1차 소스로 stdlib `xml.etree`로 파싱. `{title, link, source, published}`. 신규 의존성 추가 없음. 1차 소스 응답 실패/빈 결과 시 Investing.com RSS(`https://www.investing.com/rss/news.rss`)로 폴백.

### `advisor_briefing.py` (신규)
- `select_top_headlines(raw_headlines) -> list[dict]`: Claude로 원본 중 핵심 3건 + 중요 이유 1줄 선별(구조화 출력, `advisor_llm.py`의 `output_config.format` 패턴 재사용).
- `generate_ojs_commentary(dashboard, top_headlines) -> dict`: OJS 룰북 philosophy/rules를 시스템 프롬프트로 주입. 매크로·타이밍 해설 + `codeable=yes` 룰 기반 구체적 신호(매집구간/분할비율/진입가 후보)를 함께 반환.
- `generate_bkr_commentary(dashboard, top_headlines, kosdaq_list) -> dict`: 헤드라인에 걸리는 종목/섹터를 BKR 룰(해자·성장·스크리닝) 관점에서 해설. `kosdaq_list`(40종목) 포함 종목 우선. 매수가·타이밍 필드 없음 — 디스클레이머 고정 포함.
- `build_briefing() -> dict`: 위 4개 함수 오케스트레이션, 최종 결과 dict 반환.

### `advisor_app.py`
- 새 탭 "📰 시황 브리핑" 추가. "브리핑 생성" 버튼 → `build_briefing()` 호출 → 카드 렌더링: ① Summary ② Tech Dashboard(수치 그리드) ③ TOP News(3건, 출처 링크) ④-A 오재승 해설(구체적 신호 포함) ④-B 빈규리 해설(디스클레이머 포함, 매수가 없음). `@st.cache_data(ttl=1800)`.

## 5. 데이터 흐름

```
버튼 클릭
  ├─ get_market_dashboard()      [객관 수치]
  └─ fetch_raw_headlines()       [원본 뉴스]
       └─ select_top_headlines() [LLM 선별, 핵심 3건]
            ├─ generate_ojs_commentary(dashboard, top3)  → 구체적 신호 포함
            └─ generate_bkr_commentary(dashboard, top3, kosdaq_40list) → 해설만
                 └─ build_briefing() → Streamlit 렌더링
```

## 6. 에러 처리

- RSS 소스 다운: `fetch_raw_headlines()`가 빈 리스트 반환 → 앱은 "뉴스 소스 일시 장애" 경고, Tech Dashboard는 독립적으로 정상 표시(부분 실패 허용).
- LLM 키 없음: `advisor_llm.py`의 `llm_available()` graceful 패턴 재사용 → 해설 섹션만 "LLM 키 필요" 안내, 나머지는 정상 표시.
- yfinance rate-limit: 기존 교훈대로 `fast_info` 우선, 실패 시 `NO_DATA` 상태 표시.

## 7. 테스트

- 기존 방식대로 Streamlit `AppTest`로 새 탭 렌더링에 예외/에러 없는지 확인.
- RSS/LLM은 실제 소스로 스모크테스트(모킹은 과설계라 생략 — YAGNI).

## 8. Out of Scope (향후 고도화 후보, 이번 스펙에 미포함)

- 코스닥 승강제 40종목 전체에 대한 빈규리식 개별 딥다이브 배치 분석(기존 `advisor_app.py` 종목카드 기능을 40종목에 반복 적용) — 이번 브리핑 에이전트와는 별도 작업, 사용자가 명시적으로 요청할 때 별도 스펙으로 진행.
- 매일 자동 생성(스케줄링) — 이번 MVP는 온디맨드 버튼 트리거만.
- 뉴스 소스 다각화(유료 API 등) — 이번엔 무료/공개 RSS로 시작.
