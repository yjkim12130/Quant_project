# 시황 브리핑 에이전트 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `advisor_app.py`에 온디맨드 "📰 시황 브리핑" 탭을 추가해, 객관 시장 데이터(지수/VIX/DXY)와 뉴스 헤드라인을 오재승(구체적 매크로·타이밍 추천)·빈규리(펀더멘탈 해설, 매수가 없음) 두 페르소나 관점으로 각각 보여준다.

**Architecture:** 데이터 레이어(`advisor_news.py`, yfinance+RSS)와 LLM 오케스트레이션 레이어(`advisor_briefing.py`, Claude 구조화 출력)를 신규 분리하고, 기존 `advisor_data.py`(OJS 정량신호)·`advisor_llm.py`(Claude 클라이언트 패턴)를 재사용한다. `advisor_app.py`는 기존 단일 화면을 `st.tabs()`로 감싸고 신규 탭 하나를 추가한다.

**Tech Stack:** Python, Streamlit, yfinance, requests, stdlib `xml.etree`(RSS 파싱), anthropic SDK(기존 `advisor_llm.py` 패턴 재사용).

**Spec:** `docs/superpowers/specs/2026-08-16-market-briefing-agent-design.md`

## Global Constraints

- 신규 의존성 추가 금지 — RSS는 stdlib `xml.etree`로 파싱(spec §4).
- 오재승 해설 = 구체적 추천 가능(codeable 룰 기반 숫자는 코드가 계산, LLM은 서술만). 빈규리 해설 = 해자·재무 서술만, 매수가·타이밍 필드 자체를 스키마에 두지 않는다(spec §3).
- 빈규리 해설 대상 종목은 코스닥 승강제 40종목 리스트(QIA-2026-MK-0703) 매칭 우선(spec §3).
- RSS 1차 소스 `https://finance.yahoo.com/news/rssindex`, 실패 시 `https://www.investing.com/rss/news.rss` 폴백(spec §4).
- 캐시 TTL 1800초(spec §4).
- 이 프로젝트는 기존에 pytest 스위트가 없음(전체 저장소 확인 완료) — 기존 관행(CLI 스모크 실행 + Streamlit `AppTest`)을 그대로 따른다. 아래 각 태스크의 "테스트" 스텝은 pytest가 아니라 CLI/AppTest 스모크 검증이다.
- git 커밋은 이번 라운드는 사용자가 명시적으로 생략 요청 — 각 태스크 끝에 커밋 스텝을 넣지 않는다. 변경사항은 작업 트리에 그대로 남겨둔다.
- MVP 오재승 해설 대상 티커는 `QQQ`(나스닥100 ETF)로 고정 — 오재승 방 이름("퀀텀 매크로 적립식 미국 ETF")과 일치하는 가장 표준적인 대상. 사용자가 이 가정에 이견이 있으면 리뷰 시 알려줄 것.

---

### Task 1: `advisor_news.py` — 시황 데이터 + 뉴스 원문 수집

**Files:**
- Create: `advisor_news.py`

**Interfaces:**
- Produces: `get_market_dashboard() -> dict` — 키 `sp500/nasdaq/dow/sox/vix/dxy/usdkrw`, 각 값 `{"ticker": str, "price": float|None, "chg_pct": float|None}` (실패 시 `"_status": "NO_DATA"` 추가). yfinance 미설치 시 최상위 `{"_status": "NO_YFINANCE"}`.
- Produces: `fetch_raw_headlines(limit: int = 20) -> list[dict]` — 각 항목 `{"title": str, "link": str, "source": str, "published": str}`. 두 RSS 모두 실패하면 빈 리스트.

- [ ] **Step 1: 파일 작성**

```python
"""
advisor_news.py — 시황 브리핑 데이터 레이어 (P2)
═══════════════════════════════════════════════════════════════════════
객관적 시장 데이터(지수·VIX·DXY 등)와 뉴스 헤드라인 원문을 공급한다.
페르소나 해설·헤드라인 선별 등 LLM 해석은 advisor_briefing.py의 몫 —
여기선 원본 수집만 담당한다(advisor_data.py와 동일한 설계 원칙:
의존성 최소화, graceful degradation).
"""
from __future__ import annotations
import xml.etree.ElementTree as ET

import requests

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

_HEADERS = {"User-Agent": "Mozilla/5.0"}

_DASHBOARD_TICKERS = {
    "sp500": "^GSPC",
    "nasdaq": "^IXIC",
    "dow": "^DJI",
    "sox": "^SOX",
    "vix": "^VIX",
    "dxy": "DX-Y.NYB",
    "usdkrw": "KRW=X",
}

_RSS_PRIMARY = ("https://finance.yahoo.com/news/rssindex", "Yahoo Finance")
_RSS_FALLBACK = ("https://www.investing.com/rss/news.rss", "Investing.com")


def get_market_dashboard() -> dict:
    """주요 지수/VIX/DXY/원달러를 fast_info로 조회. 종목별 실패는 개별 _status로."""
    if yf is None:
        return {"_status": "NO_YFINANCE"}
    out: dict = {}
    for key, ticker in _DASHBOARD_TICKERS.items():
        try:
            fi = dict(yf.Ticker(ticker).fast_info)
            price = fi.get("lastPrice")
            prev = fi.get("previousClose") or fi.get("regularMarketPreviousClose")
            chg_pct = ((price / prev - 1) * 100) if (price and prev) else None
            out[key] = {
                "ticker": ticker,
                "price": price,
                "chg_pct": round(chg_pct, 2) if chg_pct is not None else None,
            }
        except Exception:
            out[key] = {"ticker": ticker, "price": None, "chg_pct": None, "_status": "NO_DATA"}
    return out


def _parse_rss(xml_text: str, source_label: str, limit: int) -> list[dict]:
    """RSS 2.0 <item> 목록 → [{title, link, source, published}]."""
    out: list[dict] = []
    root = ET.fromstring(xml_text)
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        if not title:
            continue
        out.append({"title": title, "link": link, "source": source_label, "published": pub})
        if len(out) >= limit:
            break
    return out


def fetch_raw_headlines(limit: int = 20) -> list[dict]:
    """Yahoo Finance RSS(1차) → 실패/빈 결과 시 Investing.com RSS(폴백). 둘 다 실패하면 []."""
    for url, label in (_RSS_PRIMARY, _RSS_FALLBACK):
        try:
            r = requests.get(url, headers=_HEADERS, timeout=10)
            r.raise_for_status()
            items = _parse_rss(r.text, label, limit)
            if items:
                return items
        except Exception:
            continue
    return []
```

- [ ] **Step 2: 스모크 테스트 실행**

Run:
```bash
python -c "
import advisor_news as an
d = an.get_market_dashboard()
print('dashboard keys:', list(d.keys()))
print('sp500:', d.get('sp500'))
h = an.fetch_raw_headlines(limit=5)
print('headlines:', len(h))
if h:
    print('sample:', h[0])
"
```

Expected: 예외 없이 실행됨. `dashboard keys`에 `sp500/nasdaq/dow/sox/vix/dxy/usdkrw` 7개가 있고 각 값에 `price`(숫자 또는 None)가 있음. `headlines`가 0~5 범위이고, 0보다 크면 `sample`에 `title/link/source/published` 키가 모두 존재함.

---

### Task 2: `advisor_briefing.py` — LLM 페르소나 해설 오케스트레이션

**Files:**
- Create: `advisor_briefing.py`

**Interfaces:**
- Consumes: `advisor_news.get_market_dashboard() -> dict`, `advisor_news.fetch_raw_headlines(limit) -> list[dict]` (Task 1)
- Consumes: `advisor_data.get_price_history(ticker) -> pandas.Series|None`, `advisor_data.compute_ojs_signals(close) -> dict`, `advisor_data.evaluate_ojs_rules(ojs) -> list[dict]`, `advisor_data.load_ojs_rulebook() -> dict|None`, `advisor_data.load_rulebook() -> dict|None` (기존 `advisor_data.py`)
- Consumes: `advisor_llm.llm_available() -> tuple[bool, str]`, `advisor_llm.get_anthropic_key() -> str|None`, `advisor_llm.MODEL: str`, `advisor_llm.anthropic` (모듈 참조, 기존 `advisor_llm.py`)
- Produces: `select_top_headlines(raw_headlines: list[dict], limit: int = 3) -> dict` — `{"_status": "ok"|"NO_HEADLINES"|"UNAVAILABLE"|"AUTH_ERROR"|"RATE_LIMIT"|"API_ERROR"|"PARSE_ERROR"|"ERROR", "top": list[dict], "_msg"?: str}`. `top`의 각 항목 `{"title","link","source","why"}`.
- Produces: `generate_ojs_commentary(dashboard: dict, top_headlines: list[dict], target_ticker: str = "QQQ") -> dict` — `{"_status": ..., "target": str, "signals": dict, "active_rules": list[dict], "commentary": str, "action": str}` (성공 시) 또는 에러 dict.
- Produces: `generate_bkr_commentary(dashboard: dict, top_headlines: list[dict]) -> dict` — `{"_status": "ok", "focus_stock": str, "commentary": str, "disclaimer": str}` 또는 `{"_status": "NO_FOCUS_STOCK", "_msg": str}` 또는 에러 dict.
- Produces: `build_briefing() -> dict` — `{"dashboard": dict, "headlines": dict, "ojs": dict, "bkr": dict, "generated_at": str}`.

- [ ] **Step 1: 파일 작성**

```python
"""
advisor_briefing.py — 시황 브리핑 LLM 오케스트레이션 (P2)
═══════════════════════════════════════════════════════════════════════
advisor_news.py가 모은 원본(시황 수치·뉴스 헤드라인)을 바탕으로:
  1) 오늘 핵심 뉴스 3건 선별(select_top_headlines)
  2) 오재승 페르소나 해설 — 구체적 추천 포함(generate_ojs_commentary)
  3) 빈규리 페르소나 해설 — 해자/재무 서술만, 매수가·타이밍 없음(generate_bkr_commentary)
를 생성한다. Claude 클라이언트 사용 패턴(구조화 출력, 프롬프트 캐싱,
에러 분류)은 advisor_llm.py와 동일하게 맞춘다.

정책(설계 스펙 §3 — 반드시 준수):
  · 오재승 = 구체적 추천 가능. 숫자(매집구간/분할비율/이격 등)는 반드시
    advisor_data.py의 codeable 룰(compute_ojs_signals/evaluate_ojs_rules)이
    계산하고, LLM은 그 숫자를 근거로 서술만 한다(숫자를 새로 만들지 않음).
  · 빈규리 = 해자·재무 서술만. 매수가·목표가·타이밍 필드는 출력 스키마에
    아예 존재하지 않는다(BKR-STYLE-01 — 실제 빈규리는 이런 언급을 한 적이 없음).
  · 빈규리 해설 대상 종목은 코스닥 승강제 40종목 후보군(KOSDAQ_PREMIUM_CANDIDATES)
    매칭 우선.
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import Optional

import advisor_data as ad
import advisor_llm as al
import advisor_news as an

# ─────────────────────────────────────────────────────────────────────
# 코스닥 승강제 프리미엄리그 예상 수혜주 40종목
# 출처: 코스닥 승강제 종합분석보고서(QIA-2026-MK-0703, 빈규리 작성, 2026-07-03)
# ─────────────────────────────────────────────────────────────────────
KOSDAQ_PREMIUM_CANDIDATES = [
    "리노공업", "ISC", "피에스케이", "HPSP", "코미코", "테스", "고영",
    "하나마이크론", "동진쎄미켐", "주성엔지니어링", "티씨케이", "티에스이",
    "두산테스나", "기가비스", "하나머티리얼즈", "티엘비", "프로텍", "심텍",
    "삼현", "에스피지", "원익머트리얼즈", "동성화인텍", "에코프로비엠",
    "비즈로셀", "LS마린솔루션", "세미파이브", "가온칩스", "에스엠", "휴젤",
    "파마리서치", "클래시스", "에스티팜", "엘앤씨바이오", "인바디", "티앤엘",
    "실리콘투", "피엔티", "RFHIC", "비에이치아이", "파크시스템스",
]

_OJS_TARGET_TICKER = "QQQ"  # MVP 고정 대상: 오재승 방 "미국 ETF 적립" 테마와 일치


# ─────────────────────────────────────────────────────────────────────
# 공통 Claude 호출 헬퍼 (advisor_llm.py의 에러 분류 패턴 재사용)
# ─────────────────────────────────────────────────────────────────────
def _call_claude(system: str, user: str, schema: dict, max_tokens: int) -> dict:
    """성공 시 {"_status":"ok", **parsed_json}, 실패 시 에러 dict."""
    client = al.anthropic.Anthropic(api_key=al.get_anthropic_key())
    try:
        resp = client.messages.create(
            model=al.MODEL,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            system=[{
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
    except al.anthropic.AuthenticationError:
        return {"_status": "AUTH_ERROR", "_msg": "API 키가 유효하지 않습니다."}
    except al.anthropic.RateLimitError:
        return {"_status": "RATE_LIMIT", "_msg": "요청이 많습니다. 잠시 후 재시도하세요."}
    except al.anthropic.APIStatusError as e:
        return {"_status": "API_ERROR", "_msg": f"{e.status_code}: {e.message}"}
    except Exception as e:  # 네트워크 등
        return {"_status": "ERROR", "_msg": str(e)[:200]}

    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"_status": "PARSE_ERROR", "_msg": text[:200]}
    return {"_status": "ok", **data}


# ─────────────────────────────────────────────────────────────────────
# 1) 핵심 뉴스 3건 선별
# ─────────────────────────────────────────────────────────────────────
_TOP_SCHEMA = {
    "type": "object",
    "properties": {
        "top": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "link": {"type": "string"},
                    "source": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["title", "link", "source", "why"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["top"],
    "additionalProperties": False,
}


def select_top_headlines(raw_headlines: list[dict], limit: int = 3) -> dict:
    """뉴스 원문 목록 → 오늘 핵심 limit건 + 왜 중요한지 1줄."""
    if not raw_headlines:
        return {"_status": "NO_HEADLINES", "top": []}
    ok, why = al.llm_available()
    if not ok:
        return {"_status": "UNAVAILABLE", "_msg": why, "top": []}

    system = (
        "당신은 시장 브리핑 에디터입니다. 주어진 뉴스 원문 목록에서 오늘 시장에 "
        f"가장 중요한 {limit}건을 고르고, 각각 왜 중요한지 1줄로 씁니다. "
        "title/link/source는 원문 그대로 복사하고 절대 새로 만들지 않습니다."
    )
    user = f"[뉴스 원문 목록]\n{json.dumps(raw_headlines, ensure_ascii=False)}"
    result = _call_claude(system, user, _TOP_SCHEMA, max_tokens=1500)
    if result["_status"] != "ok":
        result.setdefault("top", [])
    return result


# ─────────────────────────────────────────────────────────────────────
# 2) 오재승 해설 — 구체적 추천 포함
# ─────────────────────────────────────────────────────────────────────
_OJS_SCHEMA = {
    "type": "object",
    "properties": {
        "commentary": {"type": "string"},
        "action": {"type": "string"},
    },
    "required": ["commentary", "action"],
    "additionalProperties": False,
}


def generate_ojs_commentary(dashboard: dict, top_headlines: list[dict],
                            target_ticker: str = _OJS_TARGET_TICKER) -> dict:
    """오재승 페르소나: 매크로·타이밍 해설 + 구체적 action(매집구간/분할비율 등)."""
    ok, why = al.llm_available()
    if not ok:
        return {"_status": "UNAVAILABLE", "_msg": why}

    close = ad.get_price_history(target_ticker)
    signals = ad.compute_ojs_signals(close) if close is not None else {"_status": "INSUFFICIENT_HISTORY"}
    rules = ad.evaluate_ojs_rules(signals) if not signals.get("_status") else []

    ojs_rb = ad.load_ojs_rulebook()
    philosophy = " ".join(ojs_rb.get("philosophy", [])) if ojs_rb else ""

    system = (
        "당신은 '오재승 자문역'의 매크로·타이밍 판단기준(철학·룰북)을 이식받은 해설 엔진입니다. "
        "핵심은 말투 모사가 아니라 그의 실제 판단 논리(어떤 신호에서 왜 그렇게 판단하는지)를 "
        "재현하는 것입니다.\n"
        f"철학: {philosophy}\n"
        "오늘의 시장 데이터·정량 신호·핵심 뉴스를 아래 활성 룰에 대입해 2~3문장 해설을 쓰고, "
        "마지막에 action 한 줄(구체적 매집구간·분할비율·진입 판단)을 씁니다. "
        "action은 반드시 아래 제공된 정량 신호의 숫자만 근거로 사용하고 새로운 숫자를 만들지 않습니다."
    )
    user = (
        f"[대상] {target_ticker}\n"
        f"[정량 신호] {json.dumps(signals, ensure_ascii=False)}\n"
        f"[활성 룰] {json.dumps(rules, ensure_ascii=False)}\n"
        f"[오늘 시장 대시보드] {json.dumps(dashboard, ensure_ascii=False)}\n"
        f"[오늘 핵심 뉴스] {json.dumps(top_headlines, ensure_ascii=False)}\n"
        "위 정보로 해설과 action을 JSON으로 반환하세요."
    )
    result = _call_claude(system, user, _OJS_SCHEMA, max_tokens=2000)
    if result["_status"] == "ok":
        result["target"] = target_ticker
        result["signals"] = signals
        result["active_rules"] = rules
    return result


# ─────────────────────────────────────────────────────────────────────
# 3) 빈규리 해설 — 해설만, 매수가·타이밍 없음
# ─────────────────────────────────────────────────────────────────────
_BKR_SCHEMA = {
    "type": "object",
    "properties": {
        "commentary": {"type": "string"},
        "disclaimer": {"type": "string"},
    },
    "required": ["commentary", "disclaimer"],
    "additionalProperties": False,
}


def _pick_bkr_focus(top_headlines: list[dict]) -> Optional[str]:
    """헤드라인 제목에서 코스닥 승강제 40종목 후보군과 일치하는 첫 종목명."""
    for h in top_headlines:
        title = h.get("title", "")
        for name in KOSDAQ_PREMIUM_CANDIDATES:
            if name in title:
                return name
    return None


def generate_bkr_commentary(dashboard: dict, top_headlines: list[dict]) -> dict:
    """빈규리 페르소나: 해자·재무 서술만. 매수가/타이밍 필드 자체가 스키마에 없음."""
    focus = _pick_bkr_focus(top_headlines)
    if not focus:
        return {"_status": "NO_FOCUS_STOCK",
                "_msg": "오늘 헤드라인에 코스닥승강제 후보군 종목이 없습니다."}

    ok, why = al.llm_available()
    if not ok:
        return {"_status": "UNAVAILABLE", "_msg": why}

    bkr_rb = ad.load_rulebook()
    philosophy = " ".join(bkr_rb.get("philosophy", [])) if bkr_rb else ""

    system = (
        "당신은 '빈규리 CPA' 자문역의 펀더멘탈 판단기준(사업·해자·재무를 보는 기준)을 이식받은 "
        "해설 엔진입니다. 핵심은 말투 모사가 아니라 그녀가 실제로 어떤 근거로 종목을 평가하는지 "
        "그 분석 논리를 재현하는 것입니다.\n"
        f"철학: {philosophy}\n"
        "사업·해자·재무 관점으로만 2~3문장 해설을 씁니다. "
        "절대 금지: 매수가, 목표가, 매수 시점, 진입 타이밍 등 구체적 가격·타이밍 언급. "
        "실제 빈규리는 이런 언급을 한 적이 없고(BKR-STYLE-01), "
        "늘 '종목 소개이지 투자의견이 아니다'로 마무리합니다."
    )
    user = (
        f"[오늘 헤드라인에서 발견된 종목] {focus}\n"
        f"[오늘 시장 대시보드] {json.dumps(dashboard, ensure_ascii=False)}\n"
        f"[오늘 핵심 뉴스] {json.dumps(top_headlines, ensure_ascii=False)}\n"
        "위 정보로 해설과 disclaimer를 JSON으로 반환하세요."
    )
    result = _call_claude(system, user, _BKR_SCHEMA, max_tokens=1500)
    if result["_status"] == "ok":
        result["focus_stock"] = focus
    return result


# ─────────────────────────────────────────────────────────────────────
# 4) 오케스트레이션
# ─────────────────────────────────────────────────────────────────────
def build_briefing() -> dict:
    """시황 브리핑 전체 파이프라인 실행."""
    dashboard = an.get_market_dashboard()
    raw = an.fetch_raw_headlines()
    headlines = select_top_headlines(raw)
    top = headlines.get("top", [])
    ojs = generate_ojs_commentary(dashboard, top)
    bkr = generate_bkr_commentary(dashboard, top)
    return {
        "dashboard": dashboard,
        "headlines": headlines,
        "ojs": ojs,
        "bkr": bkr,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
```

- [ ] **Step 2: 스모크 테스트 실행 (LLM 키 유무 무관하게 예외 없이 동작해야 함)**

Run:
```bash
python -c "
import advisor_briefing as ab
r = ab.build_briefing()
print('dashboard keys:', list(r['dashboard'].keys()))
print('headlines status:', r['headlines']['_status'])
print('ojs status:', r['ojs']['_status'])
print('bkr status:', r['bkr']['_status'])
print('generated_at:', r['generated_at'])
"
```

Expected: 예외 없이 실행됨.
- `ANTHROPIC_API_KEY` 미설정 시: `headlines status`/`ojs status`/`bkr status` 전부 `UNAVAILABLE`.
- 키 설정 시: `headlines status`가 `ok`이면 `ojs status`는 `ok`, `bkr status`는 `ok` 또는 (헤드라인에 코스닥승강제 40종목이 안 걸리면) `NO_FOCUS_STOCK`.
- `bkr status`가 `ok`일 때 결과에 `commentary`/`disclaimer`만 있고 가격·타이밍 관련 키가 전혀 없는지 육안 확인.

---

### Task 3: `advisor_app.py` — "📰 시황 브리핑" 탭 추가

**Files:**
- Modify: `advisor_app.py:14-22` (imports), `advisor_app.py:60-74` (캐시 함수 블록), `advisor_app.py:162-375` (메인 콘텐츠를 탭으로 감싸기)

**Interfaces:**
- Consumes: `advisor_briefing.build_briefing() -> dict` (Task 2)

- [ ] **Step 1: import 추가**

`advisor_app.py:20-21` (현재 `import advisor_data as ad` / `import advisor_llm as al` 바로 아래)에 추가:

```python
import advisor_briefing as ab
```

- [ ] **Step 2: 캐시 함수 추가**

`advisor_app.py:70-74`(`load_ojs` 함수 정의 끝) 바로 뒤에 추가:

```python
@st.cache_data(ttl=1800, show_spinner=False)
def load_briefing() -> dict:
    return ab.build_briefing()
```

- [ ] **Step 3: 메인 콘텐츠를 탭으로 감싸기**

`advisor_app.py`의 다음 두 지점을 확인:
- 현재 162번째 줄 부근 `# 메인` 주석 블록(`# ════...` 구분선 + `# 메인` + `# ════...`)
- 파일 마지막 줄(현재 376번째 줄, `"v9.3과 독립 — 안정화 후 v9.4 트랙 merge 예정")`)

이 사이(`if not (go or name):`부터 파일 끝까지, 현재 165~375행)의 **기존 코드 내용을 한 글자도 바꾸지 말고** 다음과 같이 처리한다:

1. `# 메인` 주석 블록 바로 뒤, `if not (go or name):` 줄 바로 앞에 아래 두 줄을 삽입:

```python
tab1, tab2 = st.tabs(["🧮 종목 분석", "📰 시황 브리핑"])

with tab1:
```

2. 그 다음부터 기존 파일 마지막 줄(`"v9.3과 독립 — 안정화 후 v9.4 트랙 merge 예정")`)까지 **모든 줄을 4칸 들여쓰기** 한다(즉 `with tab1:` 블록 안으로 들어가도록). 내용 자체는 전혀 바꾸지 않는다.
3. 들여쓰기된 기존 코드 마지막 줄 다음(파일 맨 끝)에, 새 탭 콘텐츠를 추가:

```python

with tab2:
    st.caption("오재승(매크로·타이밍) × 빈규리(펀더멘탈) 페르소나 해설 결합 · 온디맨드 생성")
    if st.button("📰 브리핑 생성", type="primary"):
        with st.spinner("시황 데이터 수집 + 페르소나 해설 생성 중…"):
            st.session_state["briefing"] = load_briefing()

    briefing = st.session_state.get("briefing")
    if not briefing:
        st.info("위 버튼을 눌러 오늘의 시황 브리핑을 생성하세요.")
    else:
        st.caption(f"생성 시각: {briefing['generated_at']}")

        st.markdown("### ① Tech Dashboard")
        dash = briefing["dashboard"]
        if dash.get("_status") == "NO_YFINANCE":
            st.warning("yfinance 미설치로 시황 데이터를 가져올 수 없습니다.")
        else:
            _labels = {"sp500": "S&P500", "nasdaq": "Nasdaq", "dow": "Dow",
                      "sox": "SOX(반도체)", "vix": "VIX", "dxy": "DXY", "usdkrw": "USD/KRW"}
            _cols = st.columns(len(_labels))
            for i, (k, label) in enumerate(_labels.items()):
                v = dash.get(k, {})
                price = v.get("price")
                chg = v.get("chg_pct")
                _cols[i].metric(
                    label,
                    f"{price:,.2f}" if isinstance(price, (int, float)) else "—",
                    delta=f"{chg}%" if chg is not None else None,
                )

        st.markdown("### ② TOP News")
        hl = briefing["headlines"]
        if hl.get("_status") not in ("ok",):
            st.warning(f"뉴스 선별 실패 [{hl.get('_status')}]: {hl.get('_msg','')}")
        elif not hl.get("top"):
            st.info("오늘 선별된 헤드라인이 없습니다.")
        else:
            for item in hl["top"]:
                st.markdown(f"**[{item['source']}]** [{item['title']}]({item['link']})")
                st.caption(item["why"])

        st.markdown("### ③ 🔵 오재승 해설 — 매크로·타이밍")
        ojs = briefing["ojs"]
        if ojs.get("_status") == "ok":
            st.markdown(ojs["commentary"])
            st.success(f"💡 {ojs['action']}")
            with st.expander("근거 신호"):
                st.json(ojs.get("signals", {}))
        else:
            st.warning(f"오재승 해설 생성 실패 [{ojs.get('_status')}]: {ojs.get('_msg','')}")

        st.markdown("### ④ 🟣 빈규리 해설 — 펀더멘탈")
        bkr = briefing["bkr"]
        if bkr.get("_status") == "ok":
            st.markdown(f"**{bkr['focus_stock']}**")
            st.markdown(bkr["commentary"])
            st.caption(bkr["disclaimer"])
        elif bkr.get("_status") == "NO_FOCUS_STOCK":
            st.info(bkr.get("_msg", "오늘은 해당되는 종목이 없습니다."))
        else:
            st.warning(f"빈규리 해설 생성 실패 [{bkr.get('_status')}]: {bkr.get('_msg','')}")
```

- [ ] **Step 4: Streamlit AppTest로 스모크 검증**

Run:
```bash
python -c "
from streamlit.testing.v1 import AppTest
at = AppTest.from_file('advisor_app.py')
at.run(timeout=60)
print('exceptions after initial run:', at.exception)
assert not at.exception, at.exception

buttons = [b for b in at.button if '브리핑 생성' in (b.label or '')]
assert buttons, 'briefing button not found'
buttons[0].click().run(timeout=120)
print('exceptions after briefing click:', at.exception)
assert not at.exception, at.exception
print('OK — no exceptions in either tab')
"
```

Expected: 두 번의 `print`가 모두 `None`(예외 없음)을 출력하고 마지막 줄에 `OK — no exceptions in either tab`이 출력됨. `ANTHROPIC_API_KEY`가 없어도 예외 없이 "LLM 키 필요" 계열 경고만 표시되며 통과해야 한다(Task 2의 graceful degradation 덕분).

---

## Self-Review 결과 (계획 작성자 자체 점검)

- **스펙 커버리지**: §3(추천 범위 정책) → Task 2 docstring+시스템 프롬프트+스키마로 강제. §4(컴포넌트) → Task 1/2/3에 1:1 매핑. §5(데이터 흐름) → `build_briefing()`이 그대로 구현. §6(에러 처리) → `_call_claude` 공통 에러 분류 + RSS 폴백 + `NO_YFINANCE`/`NO_DATA` 개별 처리. §7(테스트) → 각 태스크 CLI/AppTest 스모크 스텝. §8(Out of Scope) → 계획에 미포함 확인(스케줄링·40종목 배치·유료API 없음).
- **플레이스홀더 스캔**: TBD/TODO 없음. 모든 스텝에 실행 가능한 코드/명령 포함.
- **타입 일관성**: `generate_ojs_commentary`/`generate_bkr_commentary`/`select_top_headlines` 모두 `_call_claude` 반환 형식(`{"_status", ...}`)을 그대로 확장해서 사용 — 필드명 불일치 없음 확인. `advisor_app.py`가 참조하는 키(`dashboard`, `headlines.top[].{title,link,source,why}`, `ojs.{commentary,action,signals}`, `bkr.{focus_stock,commentary,disclaimer}`)가 Task 2 반환 구조와 정확히 일치.
