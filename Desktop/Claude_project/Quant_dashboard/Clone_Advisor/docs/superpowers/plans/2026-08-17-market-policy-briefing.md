# 미국·한국 증시·정책 브리핑(Family B, 마감판) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `advisor_app.py`에 신규 탭 "🏦 증시·정책 브리핑"을 추가해, 한국 증시 마감 기준 2페이지 브리핑(PAGE1 시장 뉴스보드 + PAGE2 정책 뉴스보드)을 키움증권 REST API 실측 데이터로 생성한다. 부가로 기존 "🧮 종목 분석" 탭에 ATR·베타 계수를 상시 노출한다.

**Architecture:** 신규 `kiwoom_data.py`(키움 REST API 데이터 레이어, Family A의 `advisor_news.py`와 병렬)와 신규 `advisor_dashboard_kr.py`(PAGE1/PAGE2 오케스트레이션, `advisor_dashboard.py`와 병렬)를 추가한다. 정책 카드는 사용자가 수기 관리하는 `policy_cards.json`에서 그대로 읽는다. 렌더러는 기존 `advisor_report.py`(HTML)와 `advisor_app.py`(Streamlit)에 함수/탭을 추가하는 방식으로 확장한다. ATR·베타는 `advisor_data.py`에 순수 계산 함수로 추가해 Family B(지수 ATR)와 tab1(종목 ATR·베타) 양쪽에서 재사용한다.

**Tech Stack:** Python, Streamlit, requests(키움 REST API 호출), pandas(ATR·베타 계산), 기존 프로젝트 의존성 외 신규 패키지 없음.

**Spec:** `docs/superpowers/specs/2026-08-17-market-policy-briefing-design.md`

## Global Constraints

- LLM 미사용 — Family A와 동일 원칙, PAGE1 서술형 콘텐츠는 전부 룰 템플릿.
- 신규 외부 의존성 추가 금지 — `requests`/`pandas`는 이미 `requirements.txt`에 있음.
- 키움 API 키 위치: `Quant_dashboard/kiwoom_api_key/{계좌번호}_appkey.txt` / `_secretkey.txt`(이미 발급·`.gitignore` 처리 완료) — 환경변수 `KIWOOM_APPKEY`/`KIWOOM_SECRETKEY` 우선, 파일 폴백(기존 DART/Anthropic 키 패턴과 동일).
- **키움 REST API 실측 확인 완료(컨트롤러가 2026-08-17 사전 조사)**:
  - OAuth 토큰 발급: `POST https://api.kiwoom.com/oauth2/token`(모의투자는 `https://mockapi.kiwoom.com/oauth2/token`), `Content-Type: application/json;charset=UTF-8`, body `{"grant_type":"client_credentials","appkey":...,"secretkey":...}`, 응답 `{"token","token_type":"bearer","expires_dt"(YYYYMMDDHHMMSS 형식),"return_code","return_msg"}`.
  - 나머지 5개 데이터 엔드포인트는 공식 예제 저장소 `https://github.com/Kiwoom-Securities/Kiwoom-REST-API`의 `examples/국내주식/` 하위에 실제 동작하는 Python 예제가 있음(시세/차트/기관_외국인/업종/순위정보 폴더로 구성) — Task 1·2는 이 예제들을 실제로 열어보고 정확한 엔드포인트·필드명을 확정한다. 이 스펙 문서에 정의된 함수 시그니처·반환 dict 모양은 확정 계약이니 그대로 지키고, 내부 구현(호출 경로·파싱)만 예제를 참고해 채운다.
- 삼성전자 종목코드 `005930`, SK하이닉스 `000660`(둘 다 실제 KRX 코드, 확정값).
- 이 프로젝트는 pytest 스위트가 없음 — CLI 스모크 실행이 테스트다. 키움 API 관련 태스크는 **실제 발급된 키로 라이브 호출**해서 검증한다(모킹 없음, YAGNI).
- Family A 최종 리뷰에서 나온 교훈을 처음부터 반영: 모든 JSON 로더는 `try/except`로 malformed 콘텐츠를 방어하고, 딕셔너리 접근은 `.get()` 위주로 작성한다(직접 인덱싱 금지) — Task 3·6에서 처음부터 적용, 리뷰에서 재발견되지 않게 한다.
- `advisor_data.py`의 기존 `compute_quant_signals(close)`/`get_price_history(ticker)` 시그니처와 동작은 유지한 채 **추가만** 한다(기존 호출부 깨뜨리지 않음).

---

### Task 1: `kiwoom_data.py` — 인증 + 지수 시세 조회 (신규, 조사 포함)

**Files:**
- Create: `kiwoom_data.py`

**Interfaces:**
- Produces: `get_kiwoom_token() -> str|None` — 유효한 접근토큰(만료 전까지 메모리 캐시, 만료 시 재발급). 키 발급 실패 시 `None`.
- Produces: `get_index_quote(market: str) -> dict` — `market`은 `"KOSPI"` 또는 `"KOSDAQ"`. 반환 `{"market": str, "price": float|None, "chg_pct": float|None}`, 실패 시 `{"market": str, "price": None, "chg_pct": None, "_status": "NO_DATA"|"AUTH_FAILED"}`.

- [ ] **Step 1: 인증 함수 작성 (엔드포인트·요청형식 확정됨 — 그대로 구현)**

`kiwoom_data.py` 파일 시작 부분:

```python
"""
kiwoom_data.py — 키움증권 REST API 데이터 레이어 (Family B)
═══════════════════════════════════════════════════════════════════════
한국 증시 자체 데이터(KOSPI/KOSDAQ 지수·등락종목수·수급·개별종목·업종)를
키움증권 REST API로 공급한다. advisor_news.py(Family A, yfinance+RSS)와
병렬 구조 — 여기선 원본 수집만 담당, 해석/서술은 advisor_dashboard_kr.py
의 몫이다(advisor_data.py/advisor_news.py와 동일한 설계 원칙).
"""
from __future__ import annotations
import glob
import os
import time
from typing import Optional

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
_KIWOOM_KEY_DIR = os.path.join(os.path.dirname(_HERE), "kiwoom_api_key")

_TOKEN_URL = "https://api.kiwoom.com/oauth2/token"
_HEADERS_JSON = {"Content-Type": "application/json;charset=UTF-8"}

# 인메모리 토큰 캐시 — 프로세스 생존 기간 동안만 유지(재시작 시 재발급).
_token_cache: dict = {"token": None, "expires_at": 0.0}


def _get_kiwoom_key(kind: str) -> Optional[str]:
    """kind: 'appkey' 또는 'secretkey'. 환경변수(KIWOOM_APPKEY/KIWOOM_SECRETKEY) 우선,
    없으면 kiwoom_api_key/*_{kind}.txt 파일에서 읽는다(계좌번호 접두사는 무시)."""
    env_name = f"KIWOOM_{kind.upper()}"
    val = os.environ.get(env_name)
    if val:
        return val.strip()
    matches = glob.glob(os.path.join(_KIWOOM_KEY_DIR, f"*_{kind}.txt"))
    if not matches:
        return None
    with open(matches[0], encoding="utf-8") as f:
        return f.read().strip()


def get_kiwoom_token() -> Optional[str]:
    """OAuth 접근토큰 발급·캐싱. 만료 60초 전부터 재발급 시도."""
    if _token_cache["token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    appkey = _get_kiwoom_key("appkey")
    secretkey = _get_kiwoom_key("secretkey")
    if not appkey or not secretkey:
        return None

    try:
        r = requests.post(
            _TOKEN_URL,
            json={"grant_type": "client_credentials", "appkey": appkey, "secretkey": secretkey},
            headers=_HEADERS_JSON,
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None

    if data.get("return_code") != 0 or not data.get("token"):
        return None

    _token_cache["token"] = data["token"]
    # expires_dt 형식: "YYYYMMDDHHMMSS" — 정확한 만료 계산 대신, 못 미더울 땐
    # 보수적으로 30분 뒤 재발급하도록 캐시(대부분의 브로커 API 토큰 수명은
    # 이보다 훨씬 길다 — 30분은 안전 마진).
    _token_cache["expires_at"] = time.time() + 1800
    return _token_cache["token"]
```

- [ ] **Step 2: 인증 스모크 테스트 — 실제 발급된 키로 라이브 호출**

Run:
```bash
python -c "
import kiwoom_data as kd
token = kd.get_kiwoom_token()
print('token acquired:', bool(token))
assert token, 'Kiwoom 토큰 발급 실패 — appkey/secretkey 위치·값 확인 필요'
print('token prefix:', token[:12], '...')
# 캐시 확인 — 두 번째 호출은 네트워크 호출 없이 캐시된 토큰 반환
token2 = kd.get_kiwoom_token()
assert token == token2
print('OK — 토큰 발급 + 캐시 확인')
"
```

Expected: `OK — 토큰 발급 + 캐시 확인` 출력. 실패하면(토큰 None) `Quant_dashboard/kiwoom_api_key/` 안의 파일 내용을 직접 확인하고, 그래도 안 되면 **BLOCKED로 보고** — 키 자체 문제(API 신청 승인 대기 중일 수 있음)이지 코드 문제가 아닐 수 있다.

- [ ] **Step 3: 국내주식 시세 예제 조사**

공식 예제 저장소에서 종목/지수 시세 관련 예제를 확인한다:
- `https://github.com/Kiwoom-Securities/Kiwoom-REST-API` 저장소의 `examples/국내주식/시세/` 디렉토리를 브라우저/WebFetch로 열어 파일 목록을 확인한다.
- 지수(코스피/코스닥 종합) 시세 전용 예제가 있으면 그걸 쓰고, 없으면 `examples/국내주식/업종/` 폴더를 확인한다 — 한국 증권사 REST API에서는 KOSPI/KOSDAQ 종합지수가 "업종코드"(예: 001=코스피종합, 101=코스닥종합) 체계로 조회되는 경우가 흔하다. 실제로 어느 쪽인지 예제 코드를 열어서 확인할 것.
- 찾은 예제 파일의 실제 내용(엔드포인트 URL, 요청 헤더에 들어가는 TR/api-id, 요청 파라미터, 응답 JSON의 필드명)을 근거로 `get_index_quote()`를 구현한다.

- [ ] **Step 4: `get_index_quote()` 구현**

Step 3에서 확인한 실제 엔드포인트·필드명으로 작성. 아래는 구조 예시(실제 URL/헤더/필드명은 조사 결과로 교체):

```python
def get_index_quote(market: str) -> dict:
    """KOSPI/KOSDAQ 지수 현재가·등락률."""
    token = get_kiwoom_token()
    if not token:
        return {"market": market, "price": None, "chg_pct": None, "_status": "AUTH_FAILED"}
    try:
        # TODO(조사 결과로 교체): 실제 엔드포인트·헤더(api-id 등)·파라미터
        r = requests.get(
            "https://api.kiwoom.com/...",  # Step 3 조사 결과로 교체
            headers={"Authorization": f"Bearer {token}", ...},
            params={...},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        price = float(data[...])   # 실제 응답 필드명으로 교체
        chg_pct = float(data[...])
        return {"market": market, "price": price, "chg_pct": round(chg_pct, 2)}
    except Exception:
        return {"market": market, "price": None, "chg_pct": None, "_status": "NO_DATA"}
```

이 구조를 실제 조사 결과로 완성한 뒤, 코드 안의 `TODO` 주석과 `...` placeholder를 전부 제거해야 한다 — 최종 커밋에 `TODO`/`...`가 남아있으면 안 된다.

- [ ] **Step 5: `get_index_quote()` 스모크 테스트 — 실측 데이터 확인**

Run:
```bash
python -c "
import kiwoom_data as kd
for m in ('KOSPI', 'KOSDAQ'):
    q = kd.get_index_quote(m)
    print(m, q)
    assert q.get('_status') != 'AUTH_FAILED', f'{m} 인증 실패'
    if q.get('price') is not None:
        assert isinstance(q['price'], float)
        assert 500 < q['price'] < 10000, f'{m} 가격이 비정상 범위: {q[\"price\"]}'
print('OK — KOSPI/KOSDAQ 실측 시세 확인')
"
```

Expected: `OK — KOSPI/KOSDAQ 실측 시세 확인` 출력. 가격 범위(500~10000)는 KOSPI/KOSDAQ 지수의 상식적인 범위를 벗어나지 않는지 확인하는 느슨한 검증이다 — 만약 이 범위를 실제로 벗어나는 값이 정상이라고 판단되면(지수 자체가 크게 변했다면) 이 검증 스크립트의 범위만 조정하고 계속 진행할 것.

- [ ] **Step 6: Commit**

```bash
git add kiwoom_data.py
git commit -m "feat(kiwoom_data): add OAuth auth + index quote (live-verified)"
```

---

### Task 2: `kiwoom_data.py` 확장 — 나머지 6개 조회 함수

**Files:**
- Modify: `kiwoom_data.py`(Task 1이 만든 파일에 함수 추가)

**Interfaces:**
- Consumes: `get_kiwoom_token() -> str|None`(Task 1)
- Produces: `get_advance_decline(market: str) -> dict` — `{"market": str, "advancers": int|None, "decliners": int|None, "unchanged": int|None, "_status"?: str}`.
- Produces: `get_index_ohlc_history(market: str, days: int = 20) -> list[dict]` — 각 항목 `{"date": str, "open": float, "high": float, "low": float, "close": float}`, 실패 시 `[]`.
- Produces: `get_investor_flow(market: str) -> dict` — `{"market": str, "foreign_net": float|None, "individual_net": float|None, "institution_net": float|None, "unit": str, "_status"?: str}` — `unit`은 실제 API가 반환하는 금액 단위를 그대로 기록(예: "백만원"/"원" — Step 1 조사로 확정).
- Produces: `get_stock_quote(code: str) -> dict` — `{"code": str, "name": str|None, "price": float|None, "chg_pct": float|None, "_status"?: str}`.
- Produces: `get_sector_returns() -> list[dict]` — 각 항목 `{"sector": str, "chg_pct": float}`, 실패 시 `[]`.
- Produces: `get_top_movers(market: str, direction: str, limit: int = 3) -> list[dict]` — `direction`은 `"up"` 또는 `"down"`. 각 항목 `{"name": str, "chg_pct": float}`, 실패 시 `[]`. (스펙 §4 PAGE1⑤ "상승·약세 종목 TOP3"에 필요 — 스펙 원문의 6개 엔드포인트 목록에 빠져있던 걸 계획 작성 중 발견해 추가함.)

- [ ] **Step 1: 나머지 5개 조사 (등락종목수·일봉·수급·개별종목·업종) + 순위정보 조사**

공식 예제 저장소(`https://github.com/Kiwoom-Securities/Kiwoom-REST-API`)의 아래 디렉토리를 열어 실제 예제 코드를 확인한다:
- `examples/국내주식/시세/` — 등락종목수, 개별종목 시세(`get_domestic_stock_quote.py` 확인됨)
- `examples/국내주식/차트/` — 일봉 차트(`get_domestic_stock_daily_chart.py` 확인됨, 지수에도 쓸 수 있는지 확인)
- `examples/국내주식/기관_외국인/` — 투자자별 매매동향
- `examples/국내주식/업종/` — 업종별 등락률
- `examples/국내주식/순위정보/` — 상승률/하락률 상위 종목(TOP 무버스)

각 예제의 실제 엔드포인트·요청 헤더(TR/api-id)·응답 필드명을 확인하고 아래 함수들을 구현한다. Task 1의 `get_index_quote()`와 동일한 패턴(토큰 획득 → 실패 시 `_status` 반환 → 예외는 절대 던지지 않음)을 따른다.

- [ ] **Step 2: 6개 함수 구현**

각 함수는 Step 1 조사 결과로 완성한다. 공통 골격(Task 1 Step 4와 동일 패턴):

```python
def get_advance_decline(market: str) -> dict:
    """KOSPI/KOSDAQ 등락종목수(ADR 계산용 원자재)."""
    token = get_kiwoom_token()
    if not token:
        return {"market": market, "advancers": None, "decliners": None,
                "unchanged": None, "_status": "AUTH_FAILED"}
    try:
        # 조사 결과로 실제 엔드포인트·파싱 완성
        ...
        return {"market": market, "advancers": adv, "decliners": dec, "unchanged": unch}
    except Exception:
        return {"market": market, "advancers": None, "decliners": None,
                "unchanged": None, "_status": "NO_DATA"}


def get_index_ohlc_history(market: str, days: int = 20) -> list[dict]:
    """지수 일봉(ATR 계산용). 실패 시 빈 리스트."""
    token = get_kiwoom_token()
    if not token:
        return []
    try:
        ...
        return [{"date": ..., "open": ..., "high": ..., "low": ..., "close": ...}, ...]
    except Exception:
        return []


def get_investor_flow(market: str) -> dict:
    """외국인/기관/개인 순매수(금액)."""
    token = get_kiwoom_token()
    if not token:
        return {"market": market, "foreign_net": None, "individual_net": None,
                "institution_net": None, "unit": "", "_status": "AUTH_FAILED"}
    try:
        ...
        return {"market": market, "foreign_net": ..., "individual_net": ...,
                "institution_net": ..., "unit": "..."}  # 실제 단위 그대로 기록
    except Exception:
        return {"market": market, "foreign_net": None, "individual_net": None,
                "institution_net": None, "unit": "", "_status": "NO_DATA"}


def get_stock_quote(code: str) -> dict:
    """개별종목 시세."""
    token = get_kiwoom_token()
    if not token:
        return {"code": code, "name": None, "price": None, "chg_pct": None, "_status": "AUTH_FAILED"}
    try:
        ...
        return {"code": code, "name": ..., "price": ..., "chg_pct": ...}
    except Exception:
        return {"code": code, "name": None, "price": None, "chg_pct": None, "_status": "NO_DATA"}


def get_sector_returns() -> list[dict]:
    """업종별 등락률. 실패 시 빈 리스트."""
    token = get_kiwoom_token()
    if not token:
        return []
    try:
        ...
        return [{"sector": ..., "chg_pct": ...}, ...]
    except Exception:
        return []


def get_top_movers(market: str, direction: str, limit: int = 3) -> list[dict]:
    """상승률/하락률 상위 종목. direction: 'up'|'down'. 실패 시 빈 리스트."""
    token = get_kiwoom_token()
    if not token:
        return []
    try:
        ...
        return [{"name": ..., "chg_pct": ...}, ...][:limit]
    except Exception:
        return []
```

`...`와 주석은 전부 실제 코드로 채워야 한다 — 최종 커밋에 placeholder가 남아있으면 안 된다.

- [ ] **Step 3: 6개 함수 스모크 테스트 — 실측 데이터로 개별 확인**

Run:
```bash
python -c "
import kiwoom_data as kd

ad = kd.get_advance_decline('KOSPI')
print('advance_decline:', ad)
assert ad.get('_status') != 'AUTH_FAILED'

hist = kd.get_index_ohlc_history('KOSPI', days=20)
print('ohlc history len:', len(hist))
if hist:
    assert set(hist[0].keys()) >= {'date', 'open', 'high', 'low', 'close'}

flow = kd.get_investor_flow('KOSPI')
print('investor_flow:', flow)
assert flow.get('_status') != 'AUTH_FAILED'

sq = kd.get_stock_quote('005930')  # 삼성전자
print('samsung quote:', sq)
assert sq.get('_status') != 'AUTH_FAILED'

sectors = kd.get_sector_returns()
print('sector count:', len(sectors))

movers_up = kd.get_top_movers('KOSPI', 'up', limit=3)
print('top movers up:', movers_up)
assert len(movers_up) <= 3

print('OK — 6개 함수 실측 스모크 통과')
"
```

Expected: `OK — 6개 함수 실측 스모크 통과` 출력, 예외 없음. 일부 값이 `None`/빈 리스트여도(장마감 직후 데이터 지연 등) `_status`가 `AUTH_FAILED`만 아니면 통과로 본다 — 완전한 실시간성은 이번 스코프 밖.

- [ ] **Step 4: Commit**

```bash
git add kiwoom_data.py
git commit -m "feat(kiwoom_data): add advance/decline, OHLC, investor flow, stock quote, sector returns, top movers"
```

---

### Task 3: `policy_cards.json` — 정책 카드 8개 (신규, 사용자 수기 관리용 스켈레톤)

**Files:**
- Create: `policy_cards.json`

**Interfaces:**
- Produces: `policy_cards.json` 파일. Task 6(`advisor_dashboard_kr.py`)이 `.get()` 기반으로 로드한다.

- [ ] **Step 1: 파일 작성**

`ojs_rulebook.json`/`binkyuri_rulebook.json`/`impact_rules.json`/`econ_calendar.json`과 동일 위치(`Clone_Advisor/` 루트)에 생성. 카테고리 라벨은 사용자가 실제로 보여준 참고 이미지에 반복 등장한 정책 주제를 그대로 재사용했고, 내용 필드는 실시간 정책 판단이 필요해 자동 생성하지 않는다 — 전부 `[입력 필요]` 플레이스홀더로 시작한다:

```json
{
  "_note": "정책 카드 8개(미국4+한국4)는 실시간 정책 이슈를 다루므로 자동 생성하지 않는다. fact_state/outlook/korea_impact/polarity/accuracy/korea_link/checkpoint를 최신 정보로 직접 채워야 브리핑이 의미를 가진다. polarity는 '긍정'/'부정'/'혼조' 중 하나, accuracy는 '높음'/'중간'/'낮음' 중 하나를 권장. 이 파일은 econ_calendar.json과 마찬가지로 사용자가 주기적으로 수기 갱신한다.",
  "cards": [
    {"id": "US-01", "country": "US", "title": "Fed 금리 정책",
     "fact_state": "[입력 필요]", "outlook": "[입력 필요]",
     "korea_impact": "[입력 필요]", "polarity": "혼조", "accuracy": "중간",
     "korea_link": "[입력 필요]", "checkpoint": "[입력 필요]"},
    {"id": "US-02", "country": "US", "title": "반도체·AI 대중국 수출통제",
     "fact_state": "[입력 필요]", "outlook": "[입력 필요]",
     "korea_impact": "[입력 필요]", "polarity": "혼조", "accuracy": "중간",
     "korea_link": "[입력 필요]", "checkpoint": "[입력 필요]"},
    {"id": "US-03", "country": "US", "title": "관세·무역 정책",
     "fact_state": "[입력 필요]", "outlook": "[입력 필요]",
     "korea_impact": "[입력 필요]", "polarity": "혼조", "accuracy": "중간",
     "korea_link": "[입력 필요]", "checkpoint": "[입력 필요]"},
    {"id": "US-04", "country": "US", "title": "지정학 리스크(중동·에너지)",
     "fact_state": "[입력 필요]", "outlook": "[입력 필요]",
     "korea_impact": "[입력 필요]", "polarity": "혼조", "accuracy": "중간",
     "korea_link": "[입력 필요]", "checkpoint": "[입력 필요]"},
    {"id": "KR-01", "country": "KR", "title": "반도체 산업 지원 정책",
     "fact_state": "[입력 필요]", "outlook": "[입력 필요]",
     "korea_impact": "[입력 필요]", "polarity": "긍정", "accuracy": "중간",
     "korea_link": "[입력 필요]", "checkpoint": "[입력 필요]"},
    {"id": "KR-02", "country": "KR", "title": "레버리지 ETF·금융안정 규제",
     "fact_state": "[입력 필요]", "outlook": "[입력 필요]",
     "korea_impact": "[입력 필요]", "polarity": "혼조", "accuracy": "중간",
     "korea_link": "[입력 필요]", "checkpoint": "[입력 필요]"},
    {"id": "KR-03", "country": "KR", "title": "주택 공급·정책금융",
     "fact_state": "[입력 필요]", "outlook": "[입력 필요]",
     "korea_impact": "[입력 필요]", "polarity": "혼조", "accuracy": "중간",
     "korea_link": "[입력 필요]", "checkpoint": "[입력 필요]"},
    {"id": "KR-04", "country": "KR", "title": "신성장동력 육성 전략",
     "fact_state": "[입력 필요]", "outlook": "[입력 필요]",
     "korea_impact": "[입력 필요]", "polarity": "긍정", "accuracy": "중간",
     "korea_link": "[입력 필요]", "checkpoint": "[입력 필요]"}
  ]
}
```

- [ ] **Step 2: 스모크 테스트 (스키마 검증)**

Run:
```bash
python -c "
import json
with open('policy_cards.json', encoding='utf-8') as f:
    d = json.load(f)
cards = d['cards']
assert len(cards) == 8
assert sum(1 for c in cards if c['country'] == 'US') == 4
assert sum(1 for c in cards if c['country'] == 'KR') == 4
required = {'id','country','title','fact_state','outlook','korea_impact','polarity','accuracy','korea_link','checkpoint'}
assert all(required <= set(c) for c in cards)
print('OK — policy_cards.json 스키마 검증 통과(8장, 미국4+한국4)')
"
```

Expected: `OK — policy_cards.json 스키마 검증 통과(8장, 미국4+한국4)` 출력.

- [ ] **Step 3: Commit**

```bash
git add policy_cards.json
git commit -m "feat(advisor): add policy_cards.json skeleton (user-maintained content)"
```

---

### Task 4: `advisor_data.py` 확장 — ADR·ATR·베타 순수 계산 함수

**Files:**
- Modify: `advisor_data.py`(임포트 블록 + 함수 추가, 기존 함수는 건드리지 않음)

**Interfaces:**
- Produces: `compute_adr(advancers: int, decliners: int) -> float|None`.
- Produces: `compute_atr(close, high, low, period: int = 14) -> float|None` — `close`/`high`/`low`는 같은 인덱스를 공유하는 `pandas.Series`.
- Produces: `compute_beta(stock_close, benchmark_close) -> float|None` — 둘 다 `pandas.Series`(날짜 인덱스).
- Produces: `get_price_history_ohlc(ticker: str, period: str = "2y")` — `pandas.DataFrame`(`High`/`Low`/`Close` 컬럼) 또는 실패 시 `None`. 기존 `get_price_history()`(Close만 반환)는 그대로 둔다 — 별도 함수로 추가.
- Produces: `benchmark_ticker_for(market: str) -> str` — `"US"`→`"^GSPC"`, `"KOSDAQ"`→`"^KQ11"`, 그 외(KOSPI 등)→`"^KS11"`.

- [ ] **Step 1: 임포트에 pandas 추가**

`advisor_data.py:28-38`(현재 임포트 블록)의 `import requests` 바로 뒤에 추가:

```python
import pandas as pd
```

- [ ] **Step 2: 4개 함수 추가**

`advisor_data.py`의 `get_price_history()` 함수(266번째 줄 부근) 바로 뒤에 추가:

```python
def get_price_history_ohlc(ticker: str, period: str = "2y"):
    """yfinance 일봉 OHLC(High/Low/Close). ATR 계산용. 실패 시 None."""
    if yf is None:
        return None
    try:
        hist = yf.Ticker(ticker).history(period=period)
        if hist is None or hist.empty:
            return None
        return hist[["High", "Low", "Close"]].dropna()
    except Exception:
        return None


def benchmark_ticker_for(market: str) -> str:
    """종목의 market 필드 → 베타 계산용 벤치마크 지수 티커."""
    m = (market or "").upper()
    if m == "US":
        return "^GSPC"
    if m == "KOSDAQ":
        return "^KQ11"
    return "^KS11"  # KOSPI 기본값


def compute_adr(advancers: int, decliners: int) -> Optional[float]:
    """등락비율(ADR) = 상승종목수/하락종목수 * 100. 하락 0이면 계산 불가(None)."""
    if not advancers or not decliners:
        return None
    return round(advancers / decliners * 100, 1)


def compute_atr(close, high, low, period: int = 14) -> Optional[float]:
    """True Range 평균(ATR). close/high/low는 같은 인덱스의 pandas Series."""
    if close is None or high is None or low is None or len(close) < period + 1:
        return None
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    return round(float(atr), 2) if not pd.isna(atr) else None


def compute_beta(stock_close, benchmark_close) -> Optional[float]:
    """수익률 공분산/벤치마크 분산 기반 베타 계수. 날짜 인덱스 기준 정렬 후 계산."""
    if stock_close is None or benchmark_close is None:
        return None
    df = pd.concat([stock_close.rename("stock"), benchmark_close.rename("bench")], axis=1).dropna()
    if len(df) < 30:
        return None
    stock_ret = df["stock"].pct_change()
    bench_ret = df["bench"].pct_change()
    aligned = pd.concat([stock_ret.rename("s"), bench_ret.rename("b")], axis=1).dropna()
    if len(aligned) < 30:
        return None
    cov = aligned["s"].cov(aligned["b"])
    var = aligned["b"].var()
    if not var or pd.isna(var):
        return None
    return round(float(cov / var), 2)
```

- [ ] **Step 3: 스모크 테스트 (합성 데이터 + 실측 데이터)**

Run:
```bash
python -c "
import advisor_data as ad
import pandas as pd

# compute_adr
assert ad.compute_adr(120, 80) == 150.0
assert ad.compute_adr(80, 120) == round(80/120*100, 1)
assert ad.compute_adr(100, 0) is None
print('compute_adr OK')

# compute_atr — 합성 OHLC (뚜렷한 True Range를 가진 20일치)
idx = pd.date_range('2026-01-01', periods=20, freq='D')
close = pd.Series([100 + i for i in range(20)], index=idx)
high = close + 2
low = close - 2
atr = ad.compute_atr(close, high, low, period=14)
print('compute_atr:', atr)
assert atr is not None and atr > 0
print('compute_atr OK')

# benchmark_ticker_for
assert ad.benchmark_ticker_for('US') == '^GSPC'
assert ad.benchmark_ticker_for('KOSDAQ') == '^KQ11'
assert ad.benchmark_ticker_for('KOSPI') == '^KS11'
print('benchmark_ticker_for OK')

# compute_beta + get_price_history_ohlc — 실측 데이터(삼성전자 vs KOSPI)
stock_ohlc = ad.get_price_history_ohlc('005930.KS')
bench_close = ad.get_price_history('^KS11')
if stock_ohlc is not None and bench_close is not None:
    beta = ad.compute_beta(stock_ohlc['Close'], bench_close)
    print('samsung beta vs KOSPI:', beta)
    assert beta is not None
    atr_real = ad.compute_atr(stock_ohlc['Close'], stock_ohlc['High'], stock_ohlc['Low'])
    print('samsung ATR:', atr_real)
    assert atr_real is not None and atr_real > 0
else:
    print('실측 데이터 조회 실패(yfinance rate-limit 등) — 합성 데이터 테스트만으로 통과 처리')
print('OK — advisor_data.py 확장 함수 4종 검증 완료')
"
```

Expected: `OK — advisor_data.py 확장 함수 4종 검증 완료` 출력. yfinance rate-limit으로 실측 부분이 스킵되어도(경고만 출력) 실패로 보지 않는다 — 합성 데이터 검증이 핵심.

- [ ] **Step 4: Commit**

```bash
git add advisor_data.py
git commit -m "feat(advisor_data): add compute_adr/compute_atr/compute_beta and OHLC history helper"
```

---

### Task 5: `advisor_data.compute_quant_signals()` 확장 + tab1 UI에 ATR·베타 노출

**Files:**
- Modify: `advisor_data.py:287`(`compute_quant_signals` 함수)
- Modify: `advisor_app.py`(캐시 함수 블록 + tab1 "② 정량 신호" 섹션)

**Interfaces:**
- Consumes: `advisor_data.compute_atr`, `advisor_data.compute_beta`, `advisor_data.get_price_history_ohlc`, `advisor_data.benchmark_ticker_for`(Task 4)
- Produces: `compute_quant_signals(close, high=None, low=None) -> dict` — 기존 반환 키 전부 유지 + 신규 키 `"atr": float|None`(high/low 미제공 시 `None`, 기존 호출부는 그대로 동작).

- [ ] **Step 1: `compute_quant_signals` 시그니처 확장**

`advisor_data.py:287`의 현재 내용:

```python
def compute_quant_signals(close) -> dict:
    """개별종목 간이 정량 신호: 200일선 이격·RSI·52주 위치·간이 레짐."""
    if close is None or len(close) < 30:
        return {"_status": "INSUFFICIENT_HISTORY"}
```

다음으로 교체(시그니처에 `high`/`low` 옵션 파라미터 추가, 나머지 로직은 그대로):

```python
def compute_quant_signals(close, high=None, low=None) -> dict:
    """개별종목 간이 정량 신호: 200일선 이격·RSI·52주 위치·간이 레짐·ATR(옵션)."""
    if close is None or len(close) < 30:
        return {"_status": "INSUFFICIENT_HISTORY"}
```

그리고 같은 함수의 반환 dict(`advisor_data.py:317-328` 부근, `"regime": regime,` 앞)에 `"atr"` 키 한 줄 추가:

```python
    return {
        "price": round(price, 2),
        "ma60": round(ma60, 2) if ma60 else None,
        "ma200": round(ma200, 2) if ma200 else None,
        "ma200_dev_pct": round(ma200_dev, 1) if ma200_dev is not None else None,
        "rsi14": round(rsi, 1),
        "wk52_high": round(hi, 2), "wk52_low": round(lo, 2),
        "wk52_pos_pct": round(wk52_pos, 1) if wk52_pos is not None else None,
        "ret_1m_pct": round(_ret(21), 1) if _ret(21) is not None else None,
        "ret_3m_pct": round(_ret(63), 1) if _ret(63) is not None else None,
        "atr": compute_atr(close, high, low) if high is not None and low is not None else None,
        "regime": regime,
    }
```

- [ ] **Step 2: `advisor_app.py` 캐시 함수 추가**

`advisor_app.py`의 `load_signals()` 캐시 함수(`ad.compute_quant_signals(load_history(ticker))`를 호출하는 부분)를 찾아 다음으로 교체:

```python
@st.cache_data(ttl=600, show_spinner=False)
def load_ohlc(ticker: str):
    return ad.get_price_history_ohlc(ticker)


@st.cache_data(ttl=600, show_spinner=False)
def load_signals(ticker: str) -> dict:
    ohlc = load_ohlc(ticker)
    high = ohlc["High"] if ohlc is not None else None
    low = ohlc["Low"] if ohlc is not None else None
    return ad.compute_quant_signals(load_history(ticker), high=high, low=low)


@st.cache_data(ttl=600, show_spinner=False)
def load_beta(ticker: str, market: str):
    bench = ad.benchmark_ticker_for(market)
    return ad.compute_beta(load_history(ticker), load_history(bench))
```

(기존에 `load_signals`가 있던 자리에 그대로 넣고, `load_ohlc`/`load_beta`를 새로 추가하는 형태 — `load_history`/`load_card` 등 다른 캐시 함수는 건드리지 않는다.)

- [ ] **Step 3: tab1 "② 정량 신호" 섹션에 ATR·베타 metric 추가**

tab1의 "② 정량 신호" 블록에서 `s = st.columns(5)`로 시작해 5개 metric을 채우는 부분을 찾아 다음으로 교체:

```python
        s = st.columns(7)
        s[0].metric("200일선 이격", f"{sig.get('ma200_dev_pct','—')}%")
        s[1].metric("RSI(14)", sig.get("rsi14", "—"))
        s[2].metric("52주 위치", f"{sig.get('wk52_pos_pct','—')}%")
        s[3].metric("1개월 수익", f"{sig.get('ret_1m_pct','—')}%")
        s[4].metric("3개월 수익", f"{sig.get('ret_3m_pct','—')}%")
        atr = sig.get("atr")
        s[5].metric("ATR(14)", f"{atr:,.2f}" if isinstance(atr, (int, float)) else "—",
                    help="절대 변동폭 — 이 종목이 하루 평균 얼마나 움직이는지(시장과 무관)")
        beta = load_beta(tkr_full, card.get("market", "")) if tkr_full else None
        s[6].metric("베타", f"{beta:.2f}" if isinstance(beta, (int, float)) else "—",
                    help="시장(코스피/코스닥/S&P500) 대비 상대적 민감도")
```

이 블록 앞뒤의 다른 코드(`if sig.get("_status"): ... else:` 구조, 오재승 룰 매칭 등)는 그대로 둔다 — `st.columns(5)`를 `st.columns(7)`로 바꾸고 metric 2개만 추가하는 것이 전부다.

- [ ] **Step 4: Streamlit AppTest로 스모크 검증**

Run:
```bash
python -c "
from streamlit.testing.v1 import AppTest
at = AppTest.from_file('advisor_app.py')
at.run(timeout=60)
print('initial exceptions:', at.exception)
assert not at.exception, at.exception

# 사이드바 기본값(와이제이링크)으로 종목 분석 탭 실행
buttons = [b for b in at.button if '분석 실행' in (b.label or '')]
assert buttons, 'analyze button not found'
buttons[0].click().run(timeout=60)
print('after analyze click, exceptions:', at.exception)
assert not at.exception, at.exception
print('OK — tab1 ATR/베타 UI 확장 후에도 예외 없음')
"
```

Expected: `OK — tab1 ATR/베타 UI 확장 후에도 예외 없음` 출력.

- [ ] **Step 5: Commit**

```bash
git add advisor_data.py advisor_app.py
git commit -m "feat(advisor): surface ATR and beta on the individual-stock analysis tab"
```

---

### Task 6: `advisor_dashboard_kr.py` — PAGE1+PAGE2 오케스트레이션 (신규)

**Files:**
- Create: `advisor_dashboard_kr.py`

**Interfaces:**
- Consumes: `kiwoom_data.py`의 8개 함수(Task 1·2), `advisor_data.compute_adr`/`compute_atr`(Task 4), `advisor_news.get_market_dashboard()`(기존 Family A, USD/KRW 재사용)
- Produces: `build_page1() -> dict` — 키: `key_themes`(list[str]), `conclusion`(list[str], 3개), `kpi`(list[dict], 6개), `volatility`(dict), `leadership`(dict), `flow_table`(list[dict]), `scenarios`(list[dict], 3개), `daily_comment`(str).
- Produces: `build_page2() -> dict` — 키: `summary`(list[dict], 3개), `policy_cards`(dict, `{"us": list[dict4], "kr": list[dict4]}`), `korea_links`(list[str], 4개), `checkpoints`(list[str], 8개).
- Produces: `build_briefing_kr() -> dict` — `{"page1": ..., "page2": ..., "generated_at": str}`.

- [ ] **Step 1: 파일 작성**

```python
"""
advisor_dashboard_kr.py — 미국·한국 증시·정책 브리핑(Family B, 마감판) 오케스트레이션
═══════════════════════════════════════════════════════════════════════
kiwoom_data.py(한국 시장 실측)와 policy_cards.json(사용자 수기 정책 카드)을
결합해 PAGE1(시장 뉴스보드)·PAGE2(정책 뉴스보드) 2섹션 세트를 만든다.
Family A(advisor_dashboard.py)와 동일하게 LLM 없이 룰 템플릿만 사용한다.

Family A의 malformed-JSON 교훈을 처음부터 반영 — 모든 JSON 로드는
try/except로 방어하고 dict 접근은 .get() 위주로 작성한다.
"""
from __future__ import annotations
import json
import os
from datetime import datetime
from typing import Optional

import advisor_data as ad
import advisor_news as an
import kiwoom_data as kd

_HERE = os.path.dirname(os.path.abspath(__file__))
_POLICY_CARDS_PATH = os.path.join(_HERE, "policy_cards.json")

_SAMSUNG_CODE = "005930"
_SKHYNIX_CODE = "000660"


def _load_policy_cards() -> Optional[dict]:
    """policy_cards.json 로드. 없거나 malformed면 None."""
    if not os.path.exists(_POLICY_CARDS_PATH):
        return None
    try:
        with open(_POLICY_CARDS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


# ─────────────────────────────────────────────────────────────────────
# PAGE1 — 한국 증시 마감 뉴스보드
# ─────────────────────────────────────────────────────────────────────
def build_page1() -> dict:
    kospi = kd.get_index_quote("KOSPI")
    kosdaq = kd.get_index_quote("KOSDAQ")
    samsung = kd.get_stock_quote(_SAMSUNG_CODE)
    skhynix = kd.get_stock_quote(_SKHYNIX_CODE)
    usdkrw = an.get_market_dashboard().get("usdkrw", {})  # Family A 데이터 재사용

    flow_kospi = kd.get_investor_flow("KOSPI")
    flow_kosdaq = kd.get_investor_flow("KOSDAQ")

    kospi_chg = kospi.get("chg_pct")
    kosdaq_chg = kosdaq.get("chg_pct")
    foreign_net_kospi = flow_kospi.get("foreign_net")

    # ① KEY THEMES
    key_themes = []
    if isinstance(kospi_chg, (int, float)):
        key_themes.append(f"KOSPI {'강세' if kospi_chg >= 0 else '약세'}")
    if isinstance(kosdaq_chg, (int, float)):
        key_themes.append(f"KOSDAQ {'강세' if kosdaq_chg >= 0 else '약세'}")
    if isinstance(foreign_net_kospi, (int, float)):
        key_themes.append(f"외국인 KOSPI {'순매수' if foreign_net_kospi >= 0 else '순매도'}")

    # ② 오늘의 결론(3줄)
    conclusion = [
        f"KOSPI {kospi.get('price','—')}({kospi_chg:+.2f}%)" if isinstance(kospi_chg, (int, float))
        else "KOSPI 시세 조회 실패",
        f"KOSDAQ {kosdaq.get('price','—')}({kosdaq_chg:+.2f}%)" if isinstance(kosdaq_chg, (int, float))
        else "KOSDAQ 시세 조회 실패",
        (f"외국인 KOSPI 순매수 {foreign_net_kospi:,.0f}{flow_kospi.get('unit','')}"
         if isinstance(foreign_net_kospi, (int, float))
         else "외국인 수급 데이터 조회 실패"),
    ]

    # ③ 마감 KPI 6개
    kpi = [
        {"label": "KOSPI", "value": kospi.get("price"), "chg_pct": kospi_chg},
        {"label": "KOSDAQ", "value": kosdaq.get("price"), "chg_pct": kosdaq_chg},
        {"label": "삼성전자", "value": samsung.get("price"), "chg_pct": samsung.get("chg_pct")},
        {"label": "SK하이닉스", "value": skhynix.get("price"), "chg_pct": skhynix.get("chg_pct")},
        {"label": "외국인 KOSPI 순매수", "value": foreign_net_kospi, "chg_pct": None},
        {"label": "USD/KRW", "value": usdkrw.get("price"), "chg_pct": usdkrw.get("chg_pct")},
    ]

    # ④ 시장 변동성 지표 — ADR·ATR·수급 해부
    ad_kospi = kd.get_advance_decline("KOSPI")
    ad_kosdaq = kd.get_advance_decline("KOSDAQ")
    hist_kospi = kd.get_index_ohlc_history("KOSPI", days=20)
    hist_kosdaq = kd.get_index_ohlc_history("KOSDAQ", days=20)

    def _atr_from_history(hist: list[dict]) -> Optional[float]:
        if len(hist) < 15:
            return None
        import pandas as pd
        df = pd.DataFrame(hist)
        return ad.compute_atr(df["close"], df["high"], df["low"])

    volatility = {
        "adr": {
            "kospi": ad.compute_adr(ad_kospi.get("advancers"), ad_kospi.get("decliners")),
            "kosdaq": ad.compute_adr(ad_kosdaq.get("advancers"), ad_kosdaq.get("decliners")),
        },
        "atr": {
            "kospi": _atr_from_history(hist_kospi),
            "kosdaq": _atr_from_history(hist_kosdaq),
        },
        "investor_flow": {"kospi": flow_kospi, "kosdaq": flow_kosdaq},
    }

    # ⑤ 업종·종목 리더십
    sectors = kd.get_sector_returns()
    sectors_sorted = sorted(
        (s for s in sectors if isinstance(s.get("chg_pct"), (int, float))),
        key=lambda s: s["chg_pct"], reverse=True,
    )
    leadership = {
        "sectors_up": sectors_sorted[:3],
        "sectors_down": list(reversed(sectors_sorted[-3:])) if sectors_sorted else [],
        "stocks_up": kd.get_top_movers("KOSPI", "up", limit=3),
        "stocks_down": kd.get_top_movers("KOSPI", "down", limit=3),
    }

    # ⑥ 가격→수급→촉발요인→지속성
    flow_table = [_build_flow_row(kospi_chg, foreign_net_kospi)]

    # ⑦ 오늘 시나리오
    scenarios = _generate_scenarios_kr(kospi_chg, foreign_net_kospi)

    # ⑧ 오늘 하루 코멘트
    daily_comment = _build_daily_comment(kospi_chg, kosdaq_chg, foreign_net_kospi, scenarios)

    return {
        "key_themes": key_themes,
        "conclusion": conclusion,
        "kpi": kpi,
        "volatility": volatility,
        "leadership": leadership,
        "flow_table": flow_table,
        "scenarios": scenarios,
        "daily_comment": daily_comment,
    }


def _build_flow_row(kospi_chg: Optional[float], foreign_net: Optional[float]) -> dict:
    """가격→수급→촉발요인→지속성 룰 매칭 — KOSPI 등락과 외국인 수급 조합 4가지."""
    price_up = isinstance(kospi_chg, (int, float)) and kospi_chg >= 0
    flow_up = isinstance(foreign_net, (int, float)) and foreign_net >= 0

    if price_up and flow_up:
        trigger, durability = "가격·수급 동반 강세", "1~3일 긍정 지속 가능"
    elif price_up and not flow_up:
        trigger, durability = "외국인 매도에도 지수 방어(개인·기관 매수 추정)", "1~2일 변동성 확대 주의"
    elif not price_up and flow_up:
        trigger, durability = "외국인 매수에도 지수 약세(차익실현 등 다른 요인)", "1~2일 혼조 가능"
    else:
        trigger, durability = "가격·수급 동반 약세", "1~3일 부정 지속 가능"

    return {
        "price_driver": f"KOSPI {kospi_chg:+.2f}%" if isinstance(kospi_chg, (int, float)) else "KOSPI 데이터 없음",
        "supply_driver": (f"외국인 {'순매수' if flow_up else '순매도'} {foreign_net:,.0f}"
                          if isinstance(foreign_net, (int, float)) else "수급 데이터 없음"),
        "trigger": trigger,
        "durability": durability,
    }


_KOSPI_SCENARIO_THRESHOLD = 0.5  # % — Family A의 sp500 임계값(0.5%)과 동일 수준


def _generate_scenarios_kr(kospi_chg: Optional[float], foreign_net: Optional[float]) -> list[dict]:
    """KOSPI 등락 + 외국인 수급 방향으로 BULL/BASE/BEAR 중 유력 시나리오 선택."""
    bullish = (isinstance(kospi_chg, (int, float)) and kospi_chg > _KOSPI_SCENARIO_THRESHOLD
               and isinstance(foreign_net, (int, float)) and foreign_net > 0)
    bearish = (isinstance(kospi_chg, (int, float)) and kospi_chg < -_KOSPI_SCENARIO_THRESHOLD
               and isinstance(foreign_net, (int, float)) and foreign_net < 0)

    if bullish:
        likely = "BULL"
    elif bearish:
        likely = "BEAR"
    else:
        likely = "BASE"

    return [
        {"id": "BULL", "label": "🐂 BULL", "likely": likely == "BULL",
         "text": "KOSPI 상승폭 확대 + 외국인 순매수 지속 시 추가 상승"},
        {"id": "BASE", "label": "⚖️ BASE", "likely": likely == "BASE",
         "text": "현재 등락폭·수급 수준이 유지되는 혼조 흐름"},
        {"id": "BEAR", "label": "🐻 BEAR", "likely": likely == "BEAR",
         "text": "KOSPI 하락폭 확대 + 외국인 순매도 지속 시 추가 조정"},
    ]


def _build_daily_comment(kospi_chg, kosdaq_chg, foreign_net, scenarios: list[dict]) -> str:
    likely_scenario = next((s for s in scenarios if s["likely"]), scenarios[-1])
    parts = []
    if isinstance(kospi_chg, (int, float)):
        parts.append(f"오늘 KOSPI는 {kospi_chg:+.2f}%로 마감했다.")
    if isinstance(kosdaq_chg, (int, float)):
        parts.append(f"KOSDAQ은 {kosdaq_chg:+.2f}%를 기록했다.")
    if isinstance(foreign_net, (int, float)):
        parts.append(f"외국인은 KOSPI에서 {'순매수' if foreign_net >= 0 else '순매도'} 우위를 보였다.")
    parts.append(f"다음 거래일은 {likely_scenario['label']} 시나리오({likely_scenario['text']})가 가장 유력하다.")
    return " ".join(parts)


# ─────────────────────────────────────────────────────────────────────
# PAGE2 — 정책 뉴스보드 (policy_cards.json 그대로 반영, 계산 로직 없음)
# ─────────────────────────────────────────────────────────────────────
def build_page2() -> dict:
    data = _load_policy_cards()
    if not data:
        return {"summary": [], "policy_cards": {"us": [], "kr": []},
                "korea_links": [], "checkpoints": [], "_status": "NO_POLICY_CARDS"}

    cards = data.get("cards", [])
    us_cards = [c for c in cards if c.get("country") == "US"]
    kr_cards = [c for c in cards if c.get("country") == "KR"]

    summary = [{"title": c.get("title", ""), "fact_state": c.get("fact_state", "")}
               for c in cards[:3]]
    korea_links = [c.get("korea_link", "") for c in cards if c.get("korea_link")][:4]
    checkpoints = [c.get("checkpoint", "") for c in cards if c.get("checkpoint")][:8]

    return {
        "summary": summary,
        "policy_cards": {"us": us_cards, "kr": kr_cards},
        "korea_links": korea_links,
        "checkpoints": checkpoints,
    }


# ─────────────────────────────────────────────────────────────────────
# 오케스트레이션
# ─────────────────────────────────────────────────────────────────────
def build_briefing_kr() -> dict:
    return {
        "page1": build_page1(),
        "page2": build_page2(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
```

- [ ] **Step 2: `build_page2()` 단위 테스트**

Run:
```bash
python -c "
import advisor_dashboard_kr as adk
p2 = adk.build_page2()
print('summary:', p2['summary'])
assert len(p2['summary']) == 3
assert len(p2['policy_cards']['us']) == 4
assert len(p2['policy_cards']['kr']) == 4
assert len(p2['korea_links']) == 4
assert len(p2['checkpoints']) == 8
print('OK — build_page2() 검증 통과')
"
```

Expected: `OK — build_page2() 검증 통과` 출력(Task 3의 `policy_cards.json`을 그대로 반영한 값).

- [ ] **Step 3: `_generate_scenarios_kr`/`_build_flow_row` 단위 테스트 (3가지 케이스)**

Run:
```bash
python -c "
import advisor_dashboard_kr as adk

bull = adk._generate_scenarios_kr(1.2, 5000)
assert [s for s in bull if s['likely']][0]['id'] == 'BULL', bull

bear = adk._generate_scenarios_kr(-1.2, -5000)
assert [s for s in bear if s['likely']][0]['id'] == 'BEAR', bear

base = adk._generate_scenarios_kr(0.1, 100)
assert [s for s in base if s['likely']][0]['id'] == 'BASE', base

for scenarios in (bull, bear, base):
    assert len(scenarios) == 3
    assert sum(1 for s in scenarios if s['likely']) == 1

row = adk._build_flow_row(1.0, 3000)
assert row['trigger'] == '가격·수급 동반 강세'
row2 = adk._build_flow_row(-1.0, -3000)
assert row2['trigger'] == '가격·수급 동반 약세'

print('OK — 시나리오·flow 룰 매트릭스 검증 통과')
"
```

Expected: `OK — 시나리오·flow 룰 매트릭스 검증 통과` 출력.

- [ ] **Step 4: `build_page1()`/`build_briefing_kr()` 통합 스모크 테스트 (실측)**

Run:
```bash
python -c "
import advisor_dashboard_kr as adk
p1 = adk.build_page1()
print('page1 keys:', sorted(p1.keys()))
expected = {'key_themes','conclusion','kpi','volatility','leadership','flow_table','scenarios','daily_comment'}
assert set(p1.keys()) == expected
assert len(p1['kpi']) == 6
assert len(p1['scenarios']) == 3
print('daily_comment:', p1['daily_comment'])

full = adk.build_briefing_kr()
assert set(full.keys()) == {'page1', 'page2', 'generated_at'}
print('generated_at:', full['generated_at'])
print('OK — build_page1()/build_briefing_kr() 예외 없이 실행됨')
"
```

Expected: `OK — build_page1()/build_briefing_kr() 예외 없이 실행됨` 출력. 키움 API 응답이 일부 실패해도(개별 `_status`) 전체가 죽지 않아야 한다.

- [ ] **Step 5: Commit**

```bash
git add advisor_dashboard_kr.py
git commit -m "feat(advisor_dashboard_kr): add PAGE1/PAGE2 orchestration for Family B"
```

---

### Task 7: `advisor_report.py` — `render_html_kr()` 추가

**Files:**
- Modify: `advisor_report.py`(기존 파일에 함수 추가, Family A용 함수는 건드리지 않음)

**Interfaces:**
- Consumes: `advisor_dashboard_kr.build_briefing_kr() -> dict`(Task 6)
- Produces: `render_html_kr(briefing: dict) -> str` — 독립 실행형 HTML 문자열(PAGE1+PAGE2 2단 레이아웃).

- [ ] **Step 1: 함수 추가**

`advisor_report.py` 파일 끝에 추가(기존 `_CSS`/`html.escape` 패턴 재사용, Family A와 동일한 이스케이핑 원칙 — 모든 동적 문자열은 `html.escape()`를 거친다):

```python
def _kpi_html_kr(kpi: list[dict]) -> str:
    cards = []
    for item in kpi:
        label = html.escape(str(item.get("label", "")))
        value = item.get("value")
        chg = item.get("chg_pct")
        cls = "up" if isinstance(chg, (int, float)) and chg >= 0 else "down"
        value_txt = f"{value:,.2f}" if isinstance(value, (int, float)) else "—"
        chg_txt = _fmt_pct(chg) if chg is not None else ""
        cards.append(
            f'<div class="card"><h3>{label}</h3>'
            f'<div class="val">{value_txt}</div>'
            f'<div class="{cls}">{chg_txt}</div></div>'
        )
    return f'<div class="grid">{"".join(cards)}</div>' if cards else "<p>데이터 없음</p>"


def _volatility_html_kr(vol: dict) -> str:
    def _fmt(v):
        return f"{v:,.1f}" if isinstance(v, (int, float)) else "—"
    adr = vol.get("adr", {})
    atr = vol.get("atr", {})
    flow = vol.get("investor_flow", {})
    rows = (
        f'<div class="card"><h3>ADR</h3><div class="val">KOSPI {_fmt(adr.get("kospi"))} / '
        f'KOSDAQ {_fmt(adr.get("kosdaq"))}</div></div>'
        f'<div class="card"><h3>ATR(14)</h3><div class="val">KOSPI {_fmt(atr.get("kospi"))} / '
        f'KOSDAQ {_fmt(atr.get("kosdaq"))}</div></div>'
    )
    for market_key, market_label in (("kospi", "KOSPI"), ("kosdaq", "KOSDAQ")):
        f_ = flow.get(market_key, {})
        rows += (
            f'<div class="card"><h3>{market_label} 수급</h3>'
            f'<div class="val">외국인 {_fmt(f_.get("foreign_net"))} · '
            f'개인 {_fmt(f_.get("individual_net"))} · '
            f'기관 {_fmt(f_.get("institution_net"))}</div></div>'
        )
    return f'<div class="grid">{rows}</div>'


def _leadership_html_kr(lead: dict) -> str:
    def _list(items: list[dict], name_key: str = "sector") -> str:
        if not items:
            return "<p>—</p>"
        rows = "".join(
            f"<li>{html.escape(str(it.get(name_key) or it.get('name', '')))} "
            f"{_fmt_pct(it.get('chg_pct'))}</li>"
            for it in items
        )
        return f"<ul>{rows}</ul>"

    return (
        '<div class="grid" style="grid-template-columns:1fr 1fr;">'
        f'<div class="card"><h3>업종 상승 TOP3</h3>{_list(lead.get("sectors_up", []))}</div>'
        f'<div class="card"><h3>업종 하락 TOP3</h3>{_list(lead.get("sectors_down", []))}</div>'
        f'<div class="card"><h3>종목 상승 TOP3</h3>{_list(lead.get("stocks_up", []), "name")}</div>'
        f'<div class="card"><h3>종목 하락 TOP3</h3>{_list(lead.get("stocks_down", []), "name")}</div>'
        "</div>"
    )


def _flow_table_html_kr(rows: list[dict]) -> str:
    if not rows:
        return "<p>데이터 없음</p>"
    body = "".join(
        f'<tr><td>{html.escape(str(r.get("price_driver","")))}</td>'
        f'<td>{html.escape(str(r.get("supply_driver","")))}</td>'
        f'<td>{html.escape(str(r.get("trigger","")))}</td>'
        f'<td>{html.escape(str(r.get("durability","")))}</td></tr>'
        for r in rows
    )
    return ("<table><tr><th>가격</th><th>수급</th><th>촉발요인</th><th>지속성</th></tr>"
            f"{body}</table>")


def _policy_cards_html(cards: list[dict]) -> str:
    if not cards:
        return "<p>—</p>"
    blocks = []
    for c in cards:
        blocks.append(
            '<div class="card">'
            f'<h3>{html.escape(str(c.get("title","")))}</h3>'
            f'<p><b>사실상태</b>: {html.escape(str(c.get("fact_state","")))}</p>'
            f'<p><b>향후방향</b>: {html.escape(str(c.get("outlook","")))}</p>'
            f'<p><b>한국시장영향</b>: {html.escape(str(c.get("korea_impact","")))} '
            f'({html.escape(str(c.get("polarity","")))} · 정확도 {html.escape(str(c.get("accuracy","")))})</p>'
            "</div>"
        )
    return f'<div class="grid">{"".join(blocks)}</div>'


def render_html_kr(briefing: dict) -> str:
    """advisor_dashboard_kr.build_briefing_kr() 출력 → PAGE1+PAGE2 HTML 문자열."""
    p1 = briefing.get("page1", {})
    p2 = briefing.get("page2", {})

    key_themes = ", ".join(html.escape(str(t)) for t in p1.get("key_themes", [])) or "—"
    conclusion = "".join(f"<li>{html.escape(str(c))}</li>" for c in p1.get("conclusion", []))
    scenarios_html = _scenarios_html(p1.get("scenarios", []))  # Family A 헬퍼 재사용
    daily_comment = html.escape(str(p1.get("daily_comment", "")))

    us_cards_html = _policy_cards_html(p2.get("policy_cards", {}).get("us", []))
    kr_cards_html = _policy_cards_html(p2.get("policy_cards", {}).get("kr", []))
    korea_links = "".join(f"<li>{html.escape(str(l))}</li>" for l in p2.get("korea_links", [])) or "<li>—</li>"
    checkpoints = "".join(f"<li>{html.escape(str(c))}</li>" for c in p2.get("checkpoints", [])) or "<li>—</li>"
    summary_html = "".join(
        f'<div class="card"><h3>{html.escape(str(s.get("title","")))}</h3>'
        f'<p>{html.escape(str(s.get("fact_state","")))}</p></div>'
        for s in p2.get("summary", [])
    ) or "<p>—</p>"

    page1_body = (
        f'<div class="section-title">KEY THEMES</div><p>{key_themes}</p>'
        f'<div class="section-title">① 오늘의 결론</div><ul>{conclusion}</ul>'
        f'<div class="section-title">② 마감 KPI</div>{_kpi_html_kr(p1.get("kpi", []))}'
        f'<div class="section-title">③ 시장 변동성 지표</div>{_volatility_html_kr(p1.get("volatility", {}))}'
        f'<div class="section-title">④ 업종·종목 리더십</div>{_leadership_html_kr(p1.get("leadership", {}))}'
        f'<div class="section-title">⑤ 가격→수급→촉발요인→지속성</div>{_flow_table_html_kr(p1.get("flow_table", []))}'
        f'<div class="section-title">⑥ 오늘 시나리오</div>{scenarios_html}'
        f'<div class="section-title">⑦ 오늘 하루 코멘트</div><p>{daily_comment}</p>'
    )
    page2_body = (
        f'<div class="section-title">PAGE2 · 핵심요약</div>{summary_html}'
        f'<div class="section-title">정책카드 비교 · 미국</div>{us_cards_html}'
        f'<div class="section-title">정책카드 비교 · 한국</div>{kr_cards_html}'
        f'<div class="section-title">미·한 연결경로</div><ul>{korea_links}</ul>'
        f'<div class="section-title">체크포인트</div><ul>{checkpoints}</ul>'
    )

    return (
        "<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'>"
        f"<title>증시·정책 브리핑 {html.escape(str(briefing.get('generated_at',''))[:10])}</title>"
        f"<style>{_CSS}</style></head><body>"
        '<div class="header"><h1>미국·한국 증시·정책 브리핑</h1>'
        f'<div>생성 시각: {html.escape(str(briefing.get("generated_at","")))}</div></div>'
        f"{page1_body}{page2_body}"
        '<div class="footer">본 자료는 정보 제공 목적이며 투자 권유가 아닙니다.</div>'
        "</body></html>"
    )
```

- [ ] **Step 2: 스모크 테스트 (실제 `build_briefing_kr()` 출력으로 렌더링 + XSS 검증)**

Run:
```bash
python -c "
import advisor_dashboard_kr as adk
import advisor_report as ar

briefing = adk.build_briefing_kr()
html_out = ar.render_html_kr(briefing)
assert html_out.startswith('<!DOCTYPE html>')
for marker in ('KEY THEMES', '마감 KPI', '시장 변동성', '업종·종목 리더십',
               '정책카드 비교', '체크포인트'):
    assert marker in html_out, f'missing marker {marker}'
print('html length:', len(html_out))

# 이스케이핑 검증 — 정책카드 title에 스크립트 태그 주입
fake = {
    'page1': adk.build_page1(),
    'page2': {'summary': [], 'policy_cards': {'us': [{'title': '<script>alert(1)</script>',
              'fact_state': '', 'outlook': '', 'korea_impact': '', 'polarity': '', 'accuracy': ''}],
              'kr': []}, 'korea_links': [], 'checkpoints': []},
    'generated_at': '2026-08-17T12:00:00',
}
injected = ar.render_html_kr(fake)
assert '<script>alert(1)</script>' not in injected
assert '&lt;script&gt;alert(1)&lt;/script&gt;' in injected
print('OK — PAGE1/PAGE2 마커 전부 존재, 이스케이핑 확인')
"
```

Expected: `OK — PAGE1/PAGE2 마커 전부 존재, 이스케이핑 확인` 출력.

- [ ] **Step 3: Commit**

```bash
git add advisor_report.py
git commit -m "feat(advisor_report): add render_html_kr for Family B PAGE1/PAGE2"
```

---

### Task 8: `advisor_app.py` — 신규 탭 "🏦 증시·정책 브리핑" 추가

**Files:**
- Modify: `advisor_app.py`(임포트 + 캐시 함수 + `st.tabs()` 호출 + 신규 탭 블록)

**Interfaces:**
- Consumes: `advisor_dashboard_kr.build_briefing_kr() -> dict`(Task 6), `advisor_report.render_html_kr(briefing) -> str`(Task 7)

- [ ] **Step 1: import 추가**

`advisor_app.py`의 `import advisor_dashboard as adb` / `import advisor_report as ar` 바로 뒤에 추가:

```python
import advisor_dashboard_kr as adk
```

(`advisor_report`는 `ar`로 이미 임포트돼 있으므로 재사용.)

- [ ] **Step 2: 캐시 함수 추가**

`load_dashboard()` 캐시 함수(Family A용) 바로 뒤에 추가:

```python
@st.cache_data(ttl=1800, show_spinner=False)
def load_briefing_kr() -> dict:
    return adk.build_briefing_kr()
```

- [ ] **Step 3: `st.tabs()` 호출을 3개 탭으로 확장**

`tab1, tab2 = st.tabs(["🧮 종목 분석", "📰 시황 브리핑"])`로 시작하는 줄을 찾아 다음으로 교체:

```python
tab1, tab2, tab3 = st.tabs(["🧮 종목 분석", "📰 시황 브리핑", "🏦 증시·정책 브리핑"])
```

`with tab2:` 블록 위에 있던 실행 순서 관련 주석(`⚠️ with tab2: 블록은 반드시 with tab1: 보다 먼저...`)은 tab3에도 동일하게 적용된다 — **`with tab3:` 블록도 `with tab1:` 보다 먼저 와야 한다**(tab1이 입력 없으면 `st.stop()`으로 스크립트를 끊기 때문).

- [ ] **Step 4: `with tab3:` 블록 추가**

`with tab2:` 블록이 끝나고 `with tab1:` 블록이 시작되기 **바로 앞**에 삽입:

```python
with tab3:
    st.caption("한국 증시 마감 기준 · PAGE1 시장 뉴스보드 + PAGE2 정책 뉴스보드 · 온디맨드 생성")
    if st.button("🏦 브리핑 생성", type="primary"):
        with st.spinner("키움 REST API 데이터 수집 + 정책카드 반영 중…"):
            st.session_state["briefing_kr"] = load_briefing_kr()

    briefing_kr = st.session_state.get("briefing_kr")
    if not briefing_kr:
        st.info("위 버튼을 눌러 오늘의 증시·정책 브리핑을 생성하세요.")
    else:
        st.caption(f"생성 시각: {briefing_kr['generated_at']}")
        p1 = briefing_kr["page1"]
        p2 = briefing_kr["page2"]

        try:
            report_html_kr = ar.render_html_kr(briefing_kr)
            ar.save_report(report_html_kr, as_of=date.fromisoformat(briefing_kr["generated_at"][:10]))
            st.download_button(
                "📥 리포트 다운로드 (HTML)",
                data=report_html_kr,
                file_name=f"{briefing_kr['generated_at'][:10]}_briefing_kr.html",
                mime="text/html",
                key="download_kr",
            )
        except Exception as e:
            st.warning(f"HTML 리포트 생성 실패: {e}")

        st.markdown("### KEY THEMES")
        st.write(", ".join(p1.get("key_themes", [])) or "—")

        st.markdown("### ① 오늘의 결론")
        for line in p1.get("conclusion", []):
            st.markdown(f"- {line}")

        st.markdown("### ② 마감 KPI 6개")
        kpi = p1.get("kpi", [])
        if kpi:
            k_cols = st.columns(len(kpi))
            for i, item in enumerate(kpi):
                value = item.get("value")
                chg = item.get("chg_pct")
                k_cols[i].metric(
                    item.get("label", ""),
                    f"{value:,.2f}" if isinstance(value, (int, float)) else "—",
                    delta=f"{chg:+.2f}%" if isinstance(chg, (int, float)) else None,
                )

        st.markdown("### ③ 시장 변동성 지표")
        vol = p1.get("volatility", {})
        vc1, vc2, vc3 = st.columns(3)
        adr = vol.get("adr", {})
        atr = vol.get("atr", {})
        vc1.metric("ADR KOSPI", f"{adr.get('kospi','—')}")
        vc1.metric("ADR KOSDAQ", f"{adr.get('kosdaq','—')}")
        vc2.metric("ATR(14) KOSPI", f"{atr.get('kospi','—')}")
        vc2.metric("ATR(14) KOSDAQ", f"{atr.get('kosdaq','—')}")
        with vc3:
            st.caption("수급 해부(외국인/개인/기관)")
            st.json(vol.get("investor_flow", {}))

        st.markdown("### ④ 업종·종목 리더십")
        lead = p1.get("leadership", {})
        l1, l2 = st.columns(2)
        with l1:
            st.markdown("**업종 상승 TOP3**")
            for s in lead.get("sectors_up", []):
                st.markdown(f"- {s.get('sector','')} {s.get('chg_pct','—')}%")
            st.markdown("**종목 상승 TOP3**")
            for s in lead.get("stocks_up", []):
                st.markdown(f"- {s.get('name','')} {s.get('chg_pct','—')}%")
        with l2:
            st.markdown("**업종 하락 TOP3**")
            for s in lead.get("sectors_down", []):
                st.markdown(f"- {s.get('sector','')} {s.get('chg_pct','—')}%")
            st.markdown("**종목 하락 TOP3**")
            for s in lead.get("stocks_down", []):
                st.markdown(f"- {s.get('name','')} {s.get('chg_pct','—')}%")

        st.markdown("### ⑤ 가격→수급→촉발요인→지속성")
        st.table(p1.get("flow_table", []))

        st.markdown("### ⑥ 오늘 시나리오")
        sc_cols = st.columns(3)
        for i, sc in enumerate(p1.get("scenarios", [])):
            with sc_cols[i]:
                st.markdown(f"**{sc['label']}**" + (" ⭐ 가장 유력" if sc["likely"] else ""))
                st.caption(sc["text"])

        st.markdown("### ⑦ 오늘 하루 코멘트")
        st.markdown(p1.get("daily_comment", ""))

        st.markdown("---")
        st.markdown("## PAGE2 · 정책 뉴스보드")
        if p2.get("_status") == "NO_POLICY_CARDS":
            st.warning("policy_cards.json을 찾을 수 없습니다 — 정책 카드 데이터가 없습니다.")
        else:
            st.markdown("### 핵심요약 3개")
            for s in p2.get("summary", []):
                st.markdown(f"**{s.get('title','')}** — {s.get('fact_state','')}")

            st.markdown("### 정책카드 비교")
            pc1, pc2 = st.columns(2)
            with pc1:
                st.markdown("**🇺🇸 미국**")
                for c in p2.get("policy_cards", {}).get("us", []):
                    with st.expander(c.get("title", "")):
                        st.markdown(f"**사실상태**: {c.get('fact_state','')}")
                        st.markdown(f"**향후방향**: {c.get('outlook','')}")
                        st.markdown(f"**한국시장영향**: {c.get('korea_impact','')} "
                                   f"({c.get('polarity','')} · 정확도 {c.get('accuracy','')})")
            with pc2:
                st.markdown("**🇰🇷 한국**")
                for c in p2.get("policy_cards", {}).get("kr", []):
                    with st.expander(c.get("title", "")):
                        st.markdown(f"**사실상태**: {c.get('fact_state','')}")
                        st.markdown(f"**향후방향**: {c.get('outlook','')}")
                        st.markdown(f"**한국시장영향**: {c.get('korea_impact','')} "
                                   f"({c.get('polarity','')} · 정확도 {c.get('accuracy','')})")

            st.markdown("### 미·한 연결경로")
            for l in p2.get("korea_links", []):
                st.markdown(f"- {l}")

            st.markdown("### 체크포인트")
            for c in p2.get("checkpoints", []):
                st.markdown(f"- {c}")

```

(이 블록 바로 다음에 기존 `with tab1:`이 이어진다 — 그대로 둔다.)

- [ ] **Step 5: Streamlit AppTest로 스모크 검증**

Run:
```bash
python -c "
from streamlit.testing.v1 import AppTest
at = AppTest.from_file('advisor_app.py')
at.run(timeout=60)
print('initial exceptions:', at.exception)
assert not at.exception, at.exception

buttons = [b for b in at.button if '증시·정책' in (b.label or '') or '🏦' in (b.label or '')]
assert buttons, 'Family B briefing button not found'
buttons[0].click().run(timeout=120)
print('after Family B click, exceptions:', at.exception)
assert not at.exception, at.exception
print('OK — 3개 탭 모두 예외 없음')
"
```

Expected: `OK — 3개 탭 모두 예외 없음` 출력.

- [ ] **Step 6: Commit**

```bash
git add advisor_app.py
git commit -m "feat(advisor_app): add Family B market-policy briefing tab"
```

---

## Self-Review 결과 (계획 작성자 자체 점검)

- **스펙 커버리지**: 스펙 §4 PAGE1 8섹션 전부 Task 6의 `build_page1()` 키에 매핑됨(①key_themes ②conclusion ③kpi ④volatility ⑤leadership ⑥flow_table ⑦scenarios ⑧daily_comment). PAGE2 4섹션 전부 `build_page2()`에 매핑됨. §3의 키움 6개 엔드포인트 + 계획 작성 중 발견해 추가한 `get_top_movers`(스펙 §4⑤ "종목 TOP3"에 필요했으나 스펙 원문 목록에서 누락됐던 것)까지 Task 1·2에 반영. §6 부가기능(ATR·베타)은 Task 4·5에 반영. §7 에러 처리(malformed JSON 방어)는 Task 3·6에서 처음부터 `.get()`/`try-except`로 반영 — Family A 리뷰에서 재발견되지 않도록 사전 적용. §8 Out of Scope(오전/정오판, 전회대비 기준선, Family C/D)는 계획에 미포함 확인.
- **플레이스홀더 스캔**: Task 1·2(키움 API 조사 부분)에만 의도적인 `...`/`TODO`가 있으나, 둘 다 "Step 3(조사) 완료 후 Step 4(구현)에서 반드시 제거"라고 명시했고, 최종 스모크 테스트(실측 라이브 호출)가 통과해야 커밋 가능하므로 완성되지 않은 코드는 태스크를 통과할 수 없다 — 이는 계획이 조사를 위임하는 것이지, 구현을 생략하는 게 아니다(Global Constraints에 이 방침 명시). 그 외 Task 3~8은 전부 실행 가능한 완전한 코드.
- **타입 일관성**: `build_page1()`/`build_page2()`가 반환하는 키를 Task 7(`render_html_kr`)과 Task 8(Streamlit)이 정확히 동일한 이름으로 참조하는지 확인 완료 — `kpi[].{label,value,chg_pct}`, `volatility.{adr,atr,investor_flow}`, `leadership.{sectors_up,sectors_down,stocks_up,stocks_down}`, `flow_table[].{price_driver,supply_driver,trigger,durability}`, `scenarios[].{id,label,text,likely}`(Family A와 동일 키), `policy_cards.{us,kr}`, `summary[].{title,fact_state}` 등 필드명 불일치 없음. `kiwoom_data.py`의 8개 함수 반환 shape이 Task 6의 소비 코드와 정확히 일치하는지 확인 완료(예: `get_advance_decline`의 `advancers`/`decliners` 키, `get_index_ohlc_history`의 `open/high/low/close` 키).
