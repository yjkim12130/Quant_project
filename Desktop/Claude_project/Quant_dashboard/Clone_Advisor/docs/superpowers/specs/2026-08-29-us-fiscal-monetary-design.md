# Family E — 🇺🇸 미국 재정·통화 모니터 설계 스펙

- **날짜**: 2026-08-29
- **로드맵 위치**: Family A(해외 시황)/B(한국 증시·정책) 완료 후 추가되는 세 번째 브리핑 계열. 시장 *가격*이 아니라 그 배경인 **재정·통화·신용 상태**를 본다.
- **선행 작업**: 미국 국채 금리 곡선 섹션(③-1, 2026-08-29 구현 완료) — `advisor_news.get_yield_curve_history()` / `advisor_dashboard.build_yield_curve()`
- **네이밍 주의**: Family C/D는 이미 백로그 문서가 존재한다(C=하방 위험 브리핑, D=한국 ADR 인포그래픽). 이번 계열은 **Family E**로 부른다.

## 1. 배경 및 목적

사용자 요청(2026-08-29): *"기업 신용(spread) 지표, 그리고 미국의 통화량 및 부채량도 추가해줘. 전체적으로 미국의 재정, 통화 상태를 최대한 자세하게 알고싶어."*

기존 대시보드는 지수·환율·금리 같은 **가격**만 본다. 가격이 왜 그렇게 움직이는지의 배경(유동성이 풀리는가 조여지는가, 신용이 벌어지는가, 재정이 지속가능한가)은 전혀 다루지 않는다. 이 스펙은 그 층을 추가한다.

## 2. 성격

- **LLM 미사용, 룰 템플릿만** — Family A/B와 동일 원칙. 숫자는 코드가 계산, 문장은 템플릿이 조립.
- 산출물 2가지 — ① Streamlit 신규 탭 `🇺🇸 재정·통화`(온디맨드 버튼) ② 정적 HTML 리포트(`render_html_us()`).
- **갱신 주기가 기존 계열과 다르다.** Family A/B는 일간 마감 데이터지만 여기는 월간·분기 시리즈가 섞인다. 그래서 별도 탭으로 분리했다(사용자 결정, 2026-08-29) — 시황 탭 로딩을 느리게 만들지 않기 위함.

### 백로그 Family C와의 관계

백로그 C(하방 위험 브리핑)의 지표 목록에 이미 `HY OAS`·`LQD OAS`·`국채 2/10/30Y`가 포함되어 있다. **이번에 만드는 `advisor_macro.py`의 FRED 클라이언트와 신용 스프레드 수집은 C 착수 시 그대로 재사용한다.** C는 위험등급 게이지·전염경로 다이어그램·OODA 프레임이라는 별개 산출물이므로 통합하지 않고, 데이터 레이어만 공유한다.

## 3. 아키텍처

기존 2개 계열과 동일한 `데이터 레이어 → 조립 → 2개 렌더러` 3단 구조를 반복한다.

| 계열 | 데이터 | 조립 | 렌더러 |
|---|---|---|---|
| A (해외 시황) | `advisor_news.py` | `advisor_dashboard.py` | tab2 + `render_html()` |
| B (한국 증시) | `kiwoom_data.py` | `advisor_dashboard_kr.py` | tab3 + `render_html_kr()` |
| **E (재정·통화)** | **`advisor_macro.py`** 신규 | **`advisor_dashboard_us.py`** 신규 | **tab4** 신규 + **`render_html_us()`** 신규 |

신규 파일 3개(`advisor_macro.py`, `advisor_dashboard_us.py`, `macro_series.json`), 기존 수정 3개(`advisor_app.py`, `advisor_report.py`, `.gitignore`).

## 4. 데이터 소스

사전 검증 결과(2026-08-29 실측):

| 소스 | 상태 | 비고 |
|---|---|---|
| 미 재무부 FiscalData | ✅ 키 불필요, 0.9초 응답 | `debt_to_penny`는 **일간** 총부채 — FRED(분기)보다 정확 |
| FRED API (`api.stlouisfed.org`) | ⚠️ 동작하나 **무료 키 필요** | 키 없으면 `400 Variable api_key is not set` |
| FRED 키 없는 CSV (`fred.stlouisfed.org`) | ❌ 타임아웃(40초 재시도도 실패) | 이 경로는 쓰지 않는다 |

**소스 분담 결정**: 재무부는 **총부채만**, 나머지는 전부 FRED.

근거 — 재무부 `interest_expense`는 국채 종류별(Notes/Bonds/TIPS…)로 쪼개져 있어 합산이 필요하고, `mts_table_1`은 한 `record_date` 안에 회계연도 전체 월이 `classification_desc`("October"/"August")로 들어있는 비시계열 형태다. 같은 값을 FRED에서 깔끔한 단일 시리즈로 받을 수 있으므로 파싱 복잡도를 감수할 이유가 없다. 부수 효과로 **FRED 키가 없어도 총부채 카드는 살아 있다.**

## 5. 시리즈 레지스트리 — `macro_series.json` (신규)

`impact_rules.json`·`econ_calendar.json`·`theme_watchlist.json`과 동일 위치(`Clone_Advisor/` 루트), 동일 관례(코드 수정 없이 지표 추가 가능).

```json
{
  "version": "0.1",
  "groups": [
    {"id": "credit", "label": "기업 신용 스프레드", "indicators": [...]},
    {"id": "liquidity", "label": "통화량·유동성", "indicators": [...]},
    {"id": "fiscal", "label": "연방 재정", "indicators": [...]},
    {"id": "rates", "label": "정책금리·실질금리", "indicators": [...]}
  ]
}
```

지표 항목 스키마: `{"id", "label", "source": "fred"|"treasury", "series_id", "unit", "freq", "higher_is": "worse"|"better"|"neutral"}`

`higher_is`는 백분위 해석 방향을 정한다(HY OAS는 높을수록 나쁨, 지준은 높을수록 좋음).

| 그룹 | id | 시리즈 | 단위 | 주기 |
|---|---|---|---|---|
| **credit** | hy_oas | `BAMLH0A0HYM2` 하이일드 OAS | % | 일간 |
| | ig_oas | `BAMLC0A0CM` 투자등급 OAS | % | 일간 |
| **liquidity** | m2 | `M2SL` M2 통화량 | $B | 월간 |
| | fed_assets | `WALCL` 연준 총자산 | $M | 주간 |
| | rrp | `RRPONTSYD` 역레포 잔액 | $B | 일간 |
| | reserves | `WRESBAL` 지급준비금 | $B | 주간 |
| | tga | `WTREGEN` 재무부 일반계정 | $B | 주간 |
| **fiscal** | debt_total | `debt_to_penny` 연방 총부채 (재무부) | $ | **일간** |
| | debt_gdp | `GFDEGDQ188S` 부채/GDP | % | 분기 |
| | deficit | `MTSDS133FMS` 월간 재정수지 | $M | 월간 |
| | interest | `A091RC1Q027SBEA` 연방 이자지급 | $B SAAR | 분기 |
| **rates** | effr | `DFF` 실효 연방기금금리 | % | 일간 |
| | bei5y | `T5YIE` 5년 기대인플레이션 | % | 일간 |
| | real10y | `DFII10` 10년 TIPS 실질금리 | % | 일간 |

총 14지표(FRED 13 + 재무부 1).

> **리스크**: FRED 시리즈 ID는 키가 없어 사전 검증하지 못했다. 레지스트리가 JSON이라 ID 오류는 코드 수정 없이 고칠 수 있고, 지표별 `_status`가 독립이라 하나가 404여도 나머지는 렌더된다. 첫 라이브 실행 시 14종 전부 확인하는 것을 검증 계획에 포함한다.

## 6. 모듈 인터페이스

### `advisor_macro.py` (신규) — 원본 수집만

Family A의 `advisor_news.py`와 같은 역할. 계산·해석은 하지 않는다.

```python
def get_fred_key() -> Optional[str]
    """환경변수 FRED_API_KEY → .fred_api_key 파일 순. (advisor_data.get_dart_key() 복제)"""

def fetch_fred_series(series_id: str, api_key: str, years: int = 3) -> dict
    """→ {"_status": "ok"|"NO_DATA", "series_id", "observations": [{"date","value"}], "_msg"}
    observation_start를 years년 전으로 잘라 응답 크기를 줄인다."""

def fetch_debt_to_penny(years: int = 3) -> dict
    """→ {"_status", "observations": [{"date","total","public","intragov"}]}"""

def collect_macro(registry: dict, years: int = 3) -> dict
    """레지스트리 순회 → {group_id: {indicator_id: <위 dict>}}.
    FRED 키가 없으면 source=="fred" 지표는 전부 _status="NO_FRED_KEY",
    재무부 지표는 정상 수집."""
```

### `advisor_dashboard_us.py` (신규) — 조립·파생·판정

```python
def load_macro_series() -> Optional[dict]      # macro_series.json, malformed면 None
def build_indicator(raw: dict, meta: dict) -> dict
def build_group(raw_group: dict, meta_group: dict) -> dict
def build_briefing_us() -> dict                # 오케스트레이션
```

`build_indicator()` 반환 스키마:

```python
{"id", "label", "unit", "freq", "_status",
 "latest_date", "latest",
 "chg_1m", "chg_1y",          # 절대 변화
 "pct_rank_3y",               # 최근 3년 백분위(0~100)
 "assessment",                # "역사적 고점권" 등 higher_is 반영 판정
 "series": [{"date", "value"}]}
```

## 7. 파생 계산

원시값만 나열하면 "$40조"가 큰지 작은지 알 수 없다. 아래를 추가로 계산한다.

| 파생 | 산식 | 목적 |
|---|---|---|
| M2 YoY | `(M2[t] / M2[t-12개월] - 1) * 100` | 잔액보다 증감이 의미 있음 |
| QT 진행도 | `WALCL` 역대 피크 대비 감축액·감축률 | 양적긴축이 어디까지 왔나 |
| HY−IG 차 | `hy_oas - ig_oas` (bp) | 신용 차별화 정도 |
| 순유동성 | `WALCL - RRPONTSYD - WTREGEN` | 실제 시장에 남는 유동성 |
| 3년 백분위 | 최근 3년 관측치 중 현재값의 백분위 | "역사적으로 높다/낮다" 판정 근거 |

**종합 판정 3줄**(룰 템플릿, 상단 요약):
- **유동성**: 순유동성 3개월 변화 + M2 YoY 부호 → 완화 / 중립 / 긴축
- **신용**: HY OAS 3년 백분위 → 안정(<33) / 경계(33–66) / 스트레스(>66)
- **재정**: 부채/GDP 추세 + 이자지급 YoY → 지속가능 / 부담 가중

## 8. 키·캐시·에러 처리

**키** — `advisor_data.get_dart_key()`를 그대로 복제. `.gitignore`에 `.fred_api_key` 추가(기존 `.dart_api_key`·`.anthropic_api_key` 옆).

**캐시** — 월간·분기 시리즈에 Family A/B의 30분 TTL은 낭비다. `@st.cache_data(ttl=21600)` **6시간**. 새로고침 1회당 FRED 13콜 + 재무부 1콜.

**에러 격리** — `_status`를 **지표별·그룹별로 독립**으로 단다.
- 키 없음 → 4개 그룹 중 credit/liquidity/rates는 통째로 `NO_FRED_KEY` 안내, fiscal 그룹은 FRED 3종이 접히고 재무부 총부채만 표시
- 개별 시리즈 404 → 그 카드만 `—`, 같은 그룹 나머지는 정상
- 재무부 장애 → fiscal 그룹의 총부채만 실패, FRED 재정 지표 3종은 정상

## 9. 렌더링

### Streamlit tab4 `🇺🇸 재정·통화`
1. 온디맨드 `🇺🇸 브리핑 생성` 버튼 (Family A/B 관례)
2. 상단 **종합 판정 3줄** — 유동성/신용/재정
3. 그룹별 4개 섹션 — 각각 지표 metric 카드 행 + plotly 추세 차트
   - 차트는 금리 곡선(③-1)에서 쓴 `plotly_dark` + `#161922` 팔레트 재사용
   - 단위가 다른 지표를 한 차트에 겹치지 않는다(%와 $B 혼합 금지) — 그룹 내에서도 단위별로 차트를 나눈다
4. `📥 리포트 다운로드 (HTML)`

**`with tab4:` 블록은 `with tab1:` 보다 먼저 실행되어야 한다** — tab1이 `st.stop()`으로 스크립트를 중단시키므로(기존 주석 d4a28c7 참조). tab2/tab3와 같은 위치에 둔다.

### `advisor_report.render_html_us()`
자립형 HTML이라 plotly를 심을 수 없다(③-1과 동일 제약). 카드 + 최근 관측치 표로 대체하고 기존 `.grid`/`.card`/`.up`/`.down` CSS를 재사용한다.

## 10. 검증 계획

이 프로젝트엔 테스트 스위트가 없다(`verify/`는 별개 용도). Family A/B와 동일하게 실제 호출로 검증한다.

1. **키 없는 경로** — `.fred_api_key`를 임시로 치운 상태에서 탭이 뜨고, FRED 그룹은 안내 문구, 총부채 카드는 정상인지
2. **키 있는 경로** — **14개 시리즈 전부** `_status="ok"`인지 개별 확인(§5 리스크 대응)
3. **파생 검산** — M2 YoY·QT 진행도·순유동성·백분위를 원시값으로 손검산
4. **렌더러** — `render_html_us()` 출력 HTML에 4개 그룹이 모두 들어가는지, plotly figure가 단위 혼합 없이 생성되는지
5. **앱 부팅** — 헤드리스 기동 후 HTTP 200, 로그에 예외 없음

## 11. 범위 밖 (YAGNI)

- 백로그 Family C의 위험등급 게이지·전염경로·OODA 프레임 — C 스펙의 몫
- `impact_rules.json`에 신용/유동성 드라이버 추가 — 시황 탭 ⑥⑨의 별도 건
- 과거 시점 재현(as-of 조회), 지표 알림/임계값 푸시
- 한국 재정·통화 대응 지표
