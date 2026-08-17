# 일간 시황 대시보드(Family A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `advisor_app.py`의 "📰 시황 브리핑" 탭을 참고 이미지(`TECH-BRIEF LIGHT v1.2`, Family A) 수준의 10섹션 일간 시황 대시보드로 확장하고, 동일 데이터로 다운로드 가능한 정적 HTML 리포트를 함께 생성한다.

**Architecture:** 기존 `advisor_briefing.build_briefing()`(지수 대시보드 + 오재승/빈규리 해설)은 그대로 두고, 그 위에 신규 오케스트레이션 레이어 `advisor_dashboard.py`를 추가해 10섹션 dict를 조립한다. 서술형 콘텐츠(시나리오·글로벌→한국 흐름·팩트/임팩트)는 신규 룰 JSON(`impact_rules.json`)과 정량 신호(`advisor_data.compute_ojs_signals`)를 조합한 룰 템플릿으로 생성하며 LLM은 사용하지 않는다. `advisor_app.py`(Streamlit)와 신규 `advisor_report.py`(정적 HTML) 두 렌더러가 동일한 `advisor_dashboard.build_dashboard()` 출력을 소비한다.

**Tech Stack:** Python, Streamlit, yfinance(기존), stdlib `json`/`os`/`pathlib`/`datetime`(신규 코드는 외부 의존성 추가 없음).

**Spec:** `docs/superpowers/specs/2026-08-17-daily-market-dashboard-design.md`

## Global Constraints

- LLM 미사용 — 서술형 콘텐츠는 전부 룰 템플릿(스펙 §2, §3, 사용자 확정 2026-08-17).
- 신규 외부 의존성 추가 금지 — 표준 라이브러리 + 기존 `requirements.txt`만 사용. HTML은 템플릿 엔진 없이 순수 Python 문자열 포맷으로 조립(스펙 §4).
- 정적 리포트는 실제 사진 대신 아이콘/이모지 기반 카드로 단순화(스펙 §2, 사용자 승인).
- 경제 캘린더(⑧)는 무료 실시간 API가 없어 **사용자가 주기적으로 수기 갱신하는 정적 JSON**(스펙 §3⑧, 사용자 승인) — 자동 크롤링/수집 없음.
- 생성 트리거는 기존과 동일하게 온디맨드 버튼 — 자동 스케줄링 없음(스펙 §2, §8).
- Tech Dashboard 드라이버는 `usdkrw`를 제외한 7개(`sp500/nasdaq/dow/sox/vix/us10y/dxy`)만 `impact_rules.json` 드라이버로 사용한다 — `usdkrw` 자체가 이미 "한국 영향"의 결과값이라 드라이버에서 제외(스펙 §3⑥).
- 이 프로젝트는 pytest 스위트가 없음(저장소 전체 확인 완료, 기존 계획 `2026-08-16-market-briefing-agent.md`도 동일하게 확인) — 각 태스크의 "테스트" 스텝은 CLI 스모크 실행이며, 마지막 태스크만 Streamlit `AppTest`를 사용한다.
- Family B/C/D는 이번 계획에 포함하지 않는다 — `docs/superpowers/specs/2026-08-17-*-backlog-{B,C,D}.md`에 착수 전 메모로 별도 추적.

---

### Task 1: `advisor_news.py` — Tech Dashboard에 미 10년물 국채금리 추가

**Files:**
- Modify: `advisor_news.py:21-29` (`_DASHBOARD_TICKERS` 딕셔너리)

**Interfaces:**
- Produces: `get_market_dashboard()`가 반환하는 dict에 신규 키 `us10y`(값 형식은 기존 다른 키와 동일: `{"ticker": "^TNX", "price": float|None, "chg_pct": float|None}`, 실패 시 `"_status": "NO_DATA"` 추가) 추가.

- [ ] **Step 1: `_DASHBOARD_TICKERS`에 10년물 티커 추가**

`advisor_news.py:21-29`의 현재 내용:

```python
_DASHBOARD_TICKERS = {
    "sp500": "^GSPC",
    "nasdaq": "^IXIC",
    "dow": "^DJI",
    "sox": "^SOX",
    "vix": "^VIX",
    "dxy": "DX-Y.NYB",
    "usdkrw": "KRW=X",
}
```

다음으로 교체(`sox`와 `vix` 사이에 `us10y` 삽입 — Tech Dashboard 타일 순서를 S&P500/Nasdaq/Dow/SOX/VIX/10Y/DXY/USD-KRW로 맞추기 위함):

```python
_DASHBOARD_TICKERS = {
    "sp500": "^GSPC",
    "nasdaq": "^IXIC",
    "dow": "^DJI",
    "sox": "^SOX",
    "vix": "^VIX",
    "us10y": "^TNX",
    "dxy": "DX-Y.NYB",
    "usdkrw": "KRW=X",
}
```

`get_market_dashboard()` 함수 본문은 `_DASHBOARD_TICKERS`를 순회하는 구조라 변경할 필요가 없다.

- [ ] **Step 2: 스모크 테스트 실행**

Run:
```bash
python -c "
import advisor_news as an
d = an.get_market_dashboard()
print('keys:', list(d.keys()))
print('us10y:', d.get('us10y'))
assert 'us10y' in d
assert len(d) == 8
"
```

Expected: 예외 없이 실행됨. `keys`에 8개(`sp500/nasdaq/dow/sox/vix/us10y/dxy/usdkrw`)가 출력되고, `us10y`에 `ticker: "^TNX"`와 숫자 `price`(또는 `NO_DATA`)가 표시됨.

- [ ] **Step 3: Commit**

```bash
git add advisor_news.py
git commit -m "feat(advisor_news): add 10Y treasury yield to market dashboard"
```

---

### Task 2: 신규 룰/설정 JSON 3종 — `impact_rules.json` / `econ_calendar.json` / `theme_watchlist.json`

**Files:**
- Create: `impact_rules.json`
- Create: `econ_calendar.json`
- Create: `theme_watchlist.json`

**Interfaces:**
- Produces: 세 JSON 파일. Task 4(`advisor_dashboard.py`)가 각각 `load_impact_rules()`/`load_econ_calendar()`/`load_theme_watchlist()`로 읽는다. 스키마는 스펙 §4에 정의된 대로.

- [ ] **Step 1: `impact_rules.json` 작성**

`ojs_rulebook.json`/`binkyuri_rulebook.json`과 동일 위치(`Clone_Advisor/` 루트)에 생성:

```json
{
  "version": "0.1",
  "rules": [
    {"id": "IMPACT-SP500-UP", "driver": "sp500", "direction": "up", "threshold_pct": 0.5,
     "category": "지수", "korea_impact": "위험자산 선호 유지"},
    {"id": "IMPACT-SP500-DOWN", "driver": "sp500", "direction": "down", "threshold_pct": -0.5,
     "category": "지수", "korea_impact": "위험자산 회피 가능성"},
    {"id": "IMPACT-NASDAQ-UP", "driver": "nasdaq", "direction": "up", "threshold_pct": 0.5,
     "category": "기술주", "korea_impact": "국내 기술주 투자심리 개선"},
    {"id": "IMPACT-NASDAQ-DOWN", "driver": "nasdaq", "direction": "down", "threshold_pct": -0.5,
     "category": "기술주", "korea_impact": "국내 기술주 투자심리 위축"},
    {"id": "IMPACT-DOW-UP", "driver": "dow", "direction": "up", "threshold_pct": 0.5,
     "category": "지수", "korea_impact": "경기민감주 투자심리 우호"},
    {"id": "IMPACT-DOW-DOWN", "driver": "dow", "direction": "down", "threshold_pct": -0.5,
     "category": "지수", "korea_impact": "경기민감주 투자심리 위축"},
    {"id": "IMPACT-SOX-UP", "driver": "sox", "direction": "up", "threshold_pct": 1.0,
     "category": "반도체", "korea_impact": "국내 반도체 대형주 동반 강세 기대"},
    {"id": "IMPACT-SOX-DOWN", "driver": "sox", "direction": "down", "threshold_pct": -1.0,
     "category": "반도체", "korea_impact": "국내 반도체 대형주 차익실현 우려"},
    {"id": "IMPACT-VIX-UP", "driver": "vix", "direction": "up", "threshold_pct": 5.0,
     "category": "변동성", "korea_impact": "원화 변동성 확대 우려"},
    {"id": "IMPACT-VIX-DOWN", "driver": "vix", "direction": "down", "threshold_pct": -5.0,
     "category": "변동성", "korea_impact": "위험자산 선호 심리 개선"},
    {"id": "IMPACT-US10Y-UP", "driver": "us10y", "direction": "up", "threshold_pct": 1.0,
     "category": "금리", "korea_impact": "성장주 할인율 부담 확대"},
    {"id": "IMPACT-US10Y-DOWN", "driver": "us10y", "direction": "down", "threshold_pct": -1.0,
     "category": "금리", "korea_impact": "금리 부담 완화, 성장주 우호"},
    {"id": "IMPACT-DXY-UP", "driver": "dxy", "direction": "up", "threshold_pct": 0.3,
     "category": "환율", "korea_impact": "원화 약세 압력"},
    {"id": "IMPACT-DXY-DOWN", "driver": "dxy", "direction": "down", "threshold_pct": -0.3,
     "category": "환율", "korea_impact": "원화 강세·외국인 수급 우호"}
  ]
}
```

- [ ] **Step 2: `econ_calendar.json` 작성**

```json
{
  "_note": "무료 실시간 캘린더 API가 없어 수기 관리한다. 지난 이벤트는 주기적으로 정리하고 새 발표일이 확정되면 추가할 것 (스펙 §3⑧).",
  "events": [
    {"date": "2026-08-18", "time_kst": "21:30", "event": "미국 7월 수출입물가", "importance": 2, "source": "BLS"},
    {"date": "2026-08-19", "time_kst": "21:30", "event": "미국 신규 실업수당청구건수", "importance": 2, "source": "DOL"},
    {"date": "2026-08-21", "time_kst": "23:00", "event": "S&P Global 8월 PMI 예비치", "importance": 2, "source": "S&P Global"},
    {"date": "2026-08-22", "time_kst": "09:00", "event": "잭슨홀 심포지엄 개막", "importance": 3, "source": "Federal Reserve"},
    {"date": "2026-09-03", "time_kst": "21:30", "event": "미국 8월 ISM 제조업 PMI", "importance": 2, "source": "ISM"},
    {"date": "2026-09-05", "time_kst": "21:30", "event": "미국 8월 고용보고서(NFP)", "importance": 3, "source": "BLS"}
  ]
}
```

- [ ] **Step 3: `theme_watchlist.json` 작성**

시드 데이터는 참고 이미지(2026-08-06 인스턴스)의 실제 TOP5 예시를 그대로 사용:

```json
{
  "us_top5": [
    {"rank_seed": 1, "category": "AI 가속기", "company": "NVIDIA",
     "keywords": ["NVIDIA", "Nvidia", "AI accelerator", "GPU"]},
    {"rank_seed": 2, "category": "AI 데이터센터 네트워크", "company": "Arista Networks",
     "keywords": ["Arista"]},
    {"rank_seed": 3, "category": "전력·냉각 인프라", "company": "Vertiv",
     "keywords": ["Vertiv"]},
    {"rank_seed": 4, "category": "HBM·AI 메모리", "company": "Micron",
     "keywords": ["Micron"]},
    {"rank_seed": 5, "category": "비기술주 실적 방어", "company": "Disney",
     "keywords": ["Disney"]}
  ],
  "kr_top5": [
    {"rank_seed": 1, "category": "HBM·메모리 대형주", "company": "SK하이닉스",
     "keywords": ["SK하이닉스", "하이닉스"]},
    {"rank_seed": 2, "category": "메모리·파운드리", "company": "삼성전자",
     "keywords": ["삼성전자"]},
    {"rank_seed": 3, "category": "HBM 패키징 장비", "company": "한미반도체",
     "keywords": ["한미반도체"]},
    {"rank_seed": 4, "category": "AI 서버용 고다층 기판", "company": "이수페타시스",
     "keywords": ["이수페타시스"]},
    {"rank_seed": 5, "category": "데이터센터 전력 인프라", "company": "HD현대일렉트릭",
     "keywords": ["HD현대일렉트릭", "현대일렉트릭"]}
  ]
}
```

- [ ] **Step 4: 스모크 테스트 실행 (스키마 검증)**

Run:
```bash
python -c "
import json
with open('impact_rules.json', encoding='utf-8') as f:
    r = json.load(f)
assert len(r['rules']) == 14
assert all({'id','driver','direction','threshold_pct','category','korea_impact'} <= set(x) for x in r['rules'])

with open('econ_calendar.json', encoding='utf-8') as f:
    c = json.load(f)
assert len(c['events']) == 6
assert all({'date','time_kst','event','importance','source'} <= set(x) for x in c['events'])

with open('theme_watchlist.json', encoding='utf-8') as f:
    w = json.load(f)
assert len(w['us_top5']) == 5 and len(w['kr_top5']) == 5
assert all({'rank_seed','category','company','keywords'} <= set(x) for x in w['us_top5'] + w['kr_top5'])
print('OK — 3개 JSON 스키마 검증 통과')
"
```

Expected: `OK — 3개 JSON 스키마 검증 통과` 출력, 예외 없음.

- [ ] **Step 5: Commit**

```bash
git add impact_rules.json econ_calendar.json theme_watchlist.json
git commit -m "feat(advisor): add impact rules, econ calendar, theme watchlist config"
```

---

### Task 3: `advisor_briefing.py` — `build_briefing()`에 한국어 헤드라인 원문 노출

**Files:**
- Modify: `advisor_briefing.py:172-192` (`build_briefing()` 함수)

**Interfaces:**
- Produces: `build_briefing()` 반환 dict에 신규 키 `kr_headlines: list[dict]`(값은 기존에 내부에서만 쓰이던 `kr_raw`, 형식은 `advisor_news.fetch_korean_headlines()`와 동일) 추가. 기존 키(`dashboard`/`headlines`/`ojs`/`bkr`/`generated_at`)는 변경 없음 — 순수 추가.

이 변경의 목적: Task 4의 `advisor_dashboard.build_dashboard()`가 TOP10 카테고리(⑩) 순위 재정렬에 한국어 헤드라인이 필요한데, 지금은 `build_briefing()` 내부에서 `an.fetch_korean_headlines()`를 호출하고도 바깥으로 노출하지 않아서 다시 호출해야 한다. 반환값에 추가해 중복 네트워크 호출을 피한다.

- [ ] **Step 1: 반환 dict에 `kr_headlines` 추가**

`advisor_briefing.py:172-192`의 현재 내용:

```python
def build_briefing() -> dict:
    """시황 브리핑 전체 파이프라인 실행.

    영문 원문(TOP News/오재승용)과 한국어 원문(빈규리 매칭용)은 서로 다른
    풀이다 — advisor_news.fetch_raw_headlines() vs .fetch_korean_headlines().
    """
    dashboard = an.get_market_dashboard()
    raw = an.fetch_raw_headlines()
    headlines = select_top_headlines(raw)
    top = headlines.get("top", [])
    kr_raw = an.fetch_korean_headlines()
    ojs = generate_ojs_commentary(dashboard, top)
    bkr = generate_bkr_commentary(dashboard, kr_raw)
    return {
        "dashboard": dashboard,
        "headlines": headlines,
        "ojs": ojs,
        "bkr": bkr,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
```

다음으로 교체(반환 dict에 `"kr_headlines": kr_raw,` 한 줄만 추가):

```python
def build_briefing() -> dict:
    """시황 브리핑 전체 파이프라인 실행.

    영문 원문(TOP News/오재승용)과 한국어 원문(빈규리 매칭용)은 서로 다른
    풀이다 — advisor_news.fetch_raw_headlines() vs .fetch_korean_headlines().
    """
    dashboard = an.get_market_dashboard()
    raw = an.fetch_raw_headlines()
    headlines = select_top_headlines(raw)
    top = headlines.get("top", [])
    kr_raw = an.fetch_korean_headlines()
    ojs = generate_ojs_commentary(dashboard, top)
    bkr = generate_bkr_commentary(dashboard, kr_raw)
    return {
        "dashboard": dashboard,
        "headlines": headlines,
        "ojs": ojs,
        "bkr": bkr,
        "kr_headlines": kr_raw,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
```

- [ ] **Step 2: 스모크 테스트 실행**

Run:
```bash
python -c "
import advisor_briefing as ab
r = ab.build_briefing()
print('keys:', sorted(r.keys()))
assert 'kr_headlines' in r
assert isinstance(r['kr_headlines'], list)
print('kr_headlines count:', len(r['kr_headlines']))
"
```

Expected: 예외 없이 실행됨. `keys`에 `kr_headlines`가 포함되고, `kr_headlines count`가 0 이상의 정수로 출력됨(RSS 소스 장애 시 0도 정상).

- [ ] **Step 3: Commit**

```bash
git add advisor_briefing.py
git commit -m "feat(advisor_briefing): expose kr_headlines from build_briefing"
```

---

### Task 4: `advisor_dashboard.py` — 10섹션 오케스트레이션 (신규)

**Files:**
- Create: `advisor_dashboard.py`

**Interfaces:**
- Consumes: `advisor_briefing.build_briefing() -> dict`(Task 3, 이제 `kr_headlines` 포함)
- Consumes: `advisor_news._DASHBOARD_TICKERS`(간접, `advisor_briefing.build_briefing()`을 통해)
- Produces: `TECH_LABELS: dict[str, str]` — Tech Dashboard 8개 키 → 표시 라벨 순서 있는 딕셔너리(Task 5/6이 렌더링 순서를 여기서 가져온다).
- Produces: `summarize_movers(dashboard: dict, top_n: int = 3) -> list[dict]` — 각 항목 `{"key": str, "label": str, "chg_pct": float, "text": str}`.
- Produces: `load_impact_rules() -> dict|None`, `apply_impact_rules(dashboard: dict, rules: list[dict]) -> dict` — `{"_status": "ok"|"NO_DRIVER", "driver"?: str, "chg_pct"?: float, "flow": list[dict], "fact_impact": list[dict]}`.
- Produces: `generate_scenarios(ojs_signals: dict, vix_price: float|None) -> list[dict]` — 정확히 3개, 각 `{"id": "BULL"|"BASE"|"BEAR", "label": str, "text": str, "likely": bool}`, `likely=True`는 정확히 1개.
- Produces: `load_econ_calendar(as_of: date|None = None, days_ahead: int = 7) -> list[dict]`.
- Produces: `load_theme_watchlist() -> dict|None`, `rank_theme_watchlist(watchlist: dict, headlines: list[dict], kr_headlines: list[dict]) -> dict` — `{"us_top5": list[dict], "kr_top5": list[dict]}`.
- Produces: `build_dashboard() -> dict` — 키: `summary`, `must_know`, `tech_dashboard`, `todays_action`, `top_news`, `impact_flow`, `fact_impact`, `scenarios`, `calendar`, `top10`, `bkr`, `generated_at`.

- [ ] **Step 1: 파일 작성**

```python
"""
advisor_dashboard.py — 일간 시황 대시보드 10섹션 오케스트레이션 (Family A)
═══════════════════════════════════════════════════════════════════════
advisor_briefing.build_briefing()이 만드는 원시 데이터(지수 8종·헤드라인·
오재승/빈규리 해설)를 참고 이미지(TECH-BRIEF LIGHT v1.2) 10섹션 구조로
조립한다. 서술형 콘텐츠(시나리오·Global→Korea Impact Flow·Fact/Impact)는
LLM 없이 룰 템플릿(impact_rules.json + 정량 신호)만으로 생성한다
(설계 스펙 §2 — 2026-08-17 사용자 확정).

advisor_app.py(Streamlit)와 advisor_report.py(정적 HTML) 두 렌더러가
build_dashboard()의 출력을 그대로 소비한다 — 렌더러마다 데이터를 다시
계산하지 않는다.
"""
from __future__ import annotations
import json
import os
from datetime import date, timedelta
from typing import Optional

import advisor_briefing as ab

_HERE = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────────────────────────────
# Tech Dashboard 표시 순서/라벨 — 참고 이미지 순서(S&P500/Nasdaq/Dow/SOX/
# VIX/10Y/DXY/USD-KRW)와 동일. advisor_report.py도 이 순서를 그대로 쓴다.
# ─────────────────────────────────────────────────────────────────────
TECH_LABELS: dict[str, str] = {
    "sp500": "S&P 500",
    "nasdaq": "Nasdaq",
    "dow": "Dow",
    "sox": "SOX(반도체)",
    "vix": "VIX",
    "us10y": "美 10년물",
    "dxy": "DXY",
    "usdkrw": "USD/KRW",
}

_VIX_CALM = 15.0
_VIX_STRESS = 25.0


# ─────────────────────────────────────────────────────────────────────
# ①② Today's Summary / 오늘 반드시 알아야 할 3가지 — 변동폭 상위 N개
# ─────────────────────────────────────────────────────────────────────
def summarize_movers(dashboard: dict, top_n: int = 3) -> list[dict]:
    """Tech Dashboard 중 |chg_pct| 상위 top_n개를 문장 카드로 변환."""
    rows = []
    for key, entry in dashboard.items():
        if key.startswith("_") or not isinstance(entry, dict):
            continue
        chg = entry.get("chg_pct")
        if chg is None:
            continue
        rows.append((abs(chg), key, chg))
    rows.sort(key=lambda t: t[0], reverse=True)

    out = []
    for _, key, chg in rows[:top_n]:
        label = TECH_LABELS.get(key, key.upper())
        direction = "상승" if chg >= 0 else "하락"
        out.append({
            "key": key,
            "label": label,
            "chg_pct": chg,
            "text": f"{label} {chg:+.2f}%로 {direction}",
        })
    return out


# ─────────────────────────────────────────────────────────────────────
# ⑥⑨ Global → Korea Impact Flow / Fact-Impact — 드라이버→한국영향 매핑
# ─────────────────────────────────────────────────────────────────────
_IMPACT_RULES_PATH = os.path.join(_HERE, "impact_rules.json")


def load_impact_rules() -> Optional[dict]:
    """impact_rules.json 로드. 없으면 None."""
    if not os.path.exists(_IMPACT_RULES_PATH):
        return None
    with open(_IMPACT_RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def apply_impact_rules(dashboard: dict, rules: list[dict]) -> dict:
    """Tech Dashboard 변동을 impact_rules.json과 매칭해 flow/fact_impact 생성.

    드라이버별로 방향(up/down)이 일치하고 |chg_pct|가 threshold_pct 이상인
    룰만 후보로 삼는다. 가장 변동폭이 큰 드라이버 1개를 flow의 핵심으로,
    상위 4개까지를 fact_impact 표로 반환한다.
    """
    candidates = []
    for r in rules:
        entry = dashboard.get(r["driver"])
        if not isinstance(entry, dict):
            continue
        chg = entry.get("chg_pct")
        if chg is None:
            continue
        direction = "up" if chg >= 0 else "down"
        if direction != r["direction"]:
            continue
        if abs(chg) < abs(r["threshold_pct"]):
            continue
        candidates.append((abs(chg), r, chg))

    if not candidates:
        return {"_status": "NO_DRIVER", "flow": [], "fact_impact": []}

    candidates.sort(key=lambda t: t[0], reverse=True)
    _, top_rule, top_chg = candidates[0]

    flow = [
        {"step": "글로벌 요인", "label": top_rule["category"]},
        {"step": "미국 시장 반응", "label": f"{top_rule['driver'].upper()} {top_chg:+.2f}%"},
        {"step": "한국 전달 경로", "label": top_rule["korea_impact"]},
        {"step": "핵심 확인", "label": "USD/KRW · 외국인 수급"},
    ]
    fact_impact = [
        {"fact": f"{r['driver'].upper()} {chg:+.2f}%", "impact": r["korea_impact"]}
        for _, r, chg in candidates[:4]
    ]
    return {"_status": "ok", "driver": top_rule["driver"], "chg_pct": top_chg,
            "flow": flow, "fact_impact": fact_impact}


# ─────────────────────────────────────────────────────────────────────
# ⑦ 오늘 시나리오 — OJS 정량 신호(그물망 배열/MACD) + VIX 레벨 룰 매칭
# ─────────────────────────────────────────────────────────────────────
def generate_scenarios(ojs_signals: dict, vix_price: Optional[float]) -> list[dict]:
    """advisor_data.compute_ojs_signals() 출력 + VIX로 BULL/BASE/BEAR 중 유력 선택.

    ojs_signals가 비어 있거나(_status 있음) 판단 근거가 부족하면 BASE로 수렴한다.
    """
    arrangement = ojs_signals.get("net_arrangement", "") if ojs_signals else ""
    macd_state = ojs_signals.get("macd_state", "") if ojs_signals else ""
    bullish = arrangement.startswith("정배열") or "무릎" in macd_state
    bearish = arrangement.startswith("역배열") or "어깨" in macd_state
    calm = isinstance(vix_price, (int, float)) and vix_price < _VIX_CALM
    stressed = isinstance(vix_price, (int, float)) and vix_price > _VIX_STRESS

    if bullish and calm:
        likely = "BULL"
    elif bearish and stressed:
        likely = "BEAR"
    else:
        likely = "BASE"

    return [
        {"id": "BULL", "label": "🐂 BULL", "likely": likely == "BULL",
         "text": "그물망 정배열·MACD 무릎 신호 유지 + VIX 안정 시 상승 추세 연장"},
        {"id": "BASE", "label": "⚖️ BASE", "likely": likely == "BASE",
         "text": "현재 그물망 배열·변동성 수준이 유지되는 흐름"},
        {"id": "BEAR", "label": "🐻 BEAR", "likely": likely == "BEAR",
         "text": "그물망 역배열·MACD 어깨 신호 전환 + VIX 급등 시 조정 국면"},
    ]


# ─────────────────────────────────────────────────────────────────────
# ⑧ 오늘·이번주 일정 — 사용자가 수기 갱신하는 정적 JSON
# ─────────────────────────────────────────────────────────────────────
_CALENDAR_PATH = os.path.join(_HERE, "econ_calendar.json")


def load_econ_calendar(as_of: Optional[date] = None, days_ahead: int = 7) -> list[dict]:
    """as_of(기본값 오늘) 기준 향후 days_ahead일 내 이벤트만 날짜순으로 반환."""
    as_of = as_of or date.today()
    if not os.path.exists(_CALENDAR_PATH):
        return []
    with open(_CALENDAR_PATH, encoding="utf-8") as f:
        data = json.load(f)
    end = as_of + timedelta(days=days_ahead)
    out = []
    for e in data.get("events", []):
        try:
            d = date.fromisoformat(e["date"])
        except (KeyError, ValueError):
            continue
        if as_of <= d <= end:
            out.append(e)
    out.sort(key=lambda e: e["date"])
    return out


# ─────────────────────────────────────────────────────────────────────
# ⑩ 수혜 가능 카테고리·관찰기업 TOP10 — 시드 5개를 헤드라인 매칭으로 재정렬
# ─────────────────────────────────────────────────────────────────────
_WATCHLIST_PATH = os.path.join(_HERE, "theme_watchlist.json")


def load_theme_watchlist() -> Optional[dict]:
    """theme_watchlist.json 로드. 없으면 None."""
    if not os.path.exists(_WATCHLIST_PATH):
        return None
    with open(_WATCHLIST_PATH, encoding="utf-8") as f:
        return json.load(f)


def _count_matches(keywords: list[str], headlines: list[dict]) -> int:
    text = " ".join(h.get("title", "") for h in headlines)
    return sum(text.count(kw) for kw in keywords)


def rank_theme_watchlist(watchlist: dict, headlines: list[dict],
                          kr_headlines: list[dict]) -> dict:
    """오늘 헤드라인(영문+한글) 키워드 매칭 건수로 us_top5/kr_top5를 재정렬.

    매칭 0건인 항목들은 동점 처리되어 rank_seed(시드 순서)를 그대로 유지한다.
    """
    combined = list(headlines) + list(kr_headlines)
    out: dict = {}
    for key in ("us_top5", "kr_top5"):
        items = watchlist.get(key, [])
        scored = [
            (_count_matches(item.get("keywords", []), combined),
             item.get("rank_seed", 99), item)
            for item in items
        ]
        scored.sort(key=lambda t: (-t[0], t[1]))
        out[key] = [item for _, _, item in scored]
    return out


# ─────────────────────────────────────────────────────────────────────
# 오케스트레이션
# ─────────────────────────────────────────────────────────────────────
def build_dashboard() -> dict:
    """advisor_briefing.build_briefing() + 룰 템플릿 → 10섹션 dict."""
    briefing = ab.build_briefing()
    dashboard = briefing["dashboard"]

    movers = summarize_movers(dashboard, top_n=3)

    rules_data = load_impact_rules()
    rules = rules_data.get("rules", []) if rules_data else []
    impact = apply_impact_rules(dashboard, rules)

    ojs = briefing["ojs"]
    ojs_signals = ojs.get("signals", {}) if ojs.get("_status") == "ok" else {}
    vix_price = dashboard.get("vix", {}).get("price") if isinstance(dashboard.get("vix"), dict) else None
    scenarios = generate_scenarios(ojs_signals, vix_price)

    calendar = load_econ_calendar()

    watchlist = load_theme_watchlist()
    kr_headlines = briefing.get("kr_headlines", [])
    top10 = (rank_theme_watchlist(watchlist, briefing["headlines"].get("top", []), kr_headlines)
             if watchlist else {"us_top5": [], "kr_top5": []})

    return {
        "summary": movers,
        "must_know": movers,
        "tech_dashboard": dashboard,
        "todays_action": ojs,
        "top_news": briefing["headlines"].get("top", []),
        "impact_flow": impact.get("flow", []),
        "fact_impact": impact.get("fact_impact", []),
        "scenarios": scenarios,
        "calendar": calendar,
        "top10": top10,
        "bkr": briefing["bkr"],
        "generated_at": briefing["generated_at"],
    }
```

- [ ] **Step 2: `summarize_movers` 단위 테스트**

Run:
```bash
python -c "
import advisor_dashboard as adb
dashboard = {
    'sp500': {'chg_pct': 0.2}, 'sox': {'chg_pct': -1.4}, 'vix': {'chg_pct': -4.2},
    'usdkrw': {'chg_pct': 0.1},
}
movers = adb.summarize_movers(dashboard, top_n=3)
print(movers)
assert movers[0]['key'] == 'vix'
assert movers[1]['key'] == 'sox'
assert len(movers) == 3
print('OK')
"
```

Expected: `OK` 출력, `movers[0]['key']`가 변동폭이 가장 큰 `vix`.

- [ ] **Step 3: `apply_impact_rules` 단위 테스트**

Run:
```bash
python -c "
import advisor_dashboard as adb
dashboard = {
    'sox': {'ticker': '^SOX', 'price': 100, 'chg_pct': -2.0},
    'vix': {'ticker': '^VIX', 'price': 20, 'chg_pct': 1.0},
}
rules = adb.load_impact_rules()['rules']
result = adb.apply_impact_rules(dashboard, rules)
print(result)
assert result['_status'] == 'ok'
assert result['driver'] == 'sox'
assert len(result['flow']) == 4
assert len(result['fact_impact']) >= 1
empty = adb.apply_impact_rules({}, rules)
assert empty['_status'] == 'NO_DRIVER'
print('OK')
"
```

Expected: `OK` 출력. `sox`가 `-2.0%`로 임계값(-1.0%)을 넘는 유일한 큰 변동이라 `driver == 'sox'`.

- [ ] **Step 4: `generate_scenarios` 단위 테스트 (3가지 케이스)**

Run:
```bash
python -c "
import advisor_dashboard as adb

bull = adb.generate_scenarios(
    {'net_arrangement': '정배열(빨강)', 'macd_state': 'osc 음→양 전환 — 무릎(매수만)'}, 12.0)
assert [s for s in bull if s['likely']][0]['id'] == 'BULL', bull

bear = adb.generate_scenarios(
    {'net_arrangement': '역배열(파랑)', 'macd_state': 'osc 양→음 전환 — 어깨(매도만)'}, 30.0)
assert [s for s in bear if s['likely']][0]['id'] == 'BEAR', bear

base = adb.generate_scenarios({}, None)
assert [s for s in base if s['likely']][0]['id'] == 'BASE', base

for scenarios in (bull, bear, base):
    assert len(scenarios) == 3
    assert sum(1 for s in scenarios if s['likely']) == 1

print('OK — BULL/BASE/BEAR 룰 매트릭스 검증 통과')
"
```

Expected: `OK — BULL/BASE/BEAR 룰 매트릭스 검증 통과` 출력.

- [ ] **Step 5: `load_econ_calendar` 단위 테스트 (고정 날짜)**

Run:
```bash
python -c "
import advisor_dashboard as adb
from datetime import date
events = adb.load_econ_calendar(as_of=date(2026, 8, 17))
print([e['event'] for e in events])
assert events, 'expected seeded events within 7 days of 2026-08-17'
assert all(e['date'] <= '2026-08-24' for e in events)
print('OK')
"
```

Expected: `OK` 출력. `date.today()`가 실제 로컬 시스템 시각을 쓰기 때문에 `as_of`를 명시적으로 고정해서 시드 데이터와 무관하게 결정적으로 검증한다.

- [ ] **Step 6: `rank_theme_watchlist` 단위 테스트**

Run:
```bash
python -c "
import advisor_dashboard as adb
wl = adb.load_theme_watchlist()
headlines = [{'title': 'NVIDIA posts record AI chip demand'}]
kr_headlines = [{'title': 'SK하이닉스 HBM 공급 확대'}]
ranked = adb.rank_theme_watchlist(wl, headlines, kr_headlines)
print('us top1:', ranked['us_top5'][0]['company'])
print('kr top1:', ranked['kr_top5'][0]['company'])
assert ranked['us_top5'][0]['company'] == 'NVIDIA'
assert ranked['kr_top5'][0]['company'] == 'SK하이닉스'
assert len(ranked['us_top5']) == 5 and len(ranked['kr_top5']) == 5
print('OK')
"
```

Expected: `OK` 출력. 키워드가 매칭된 종목이 각 리스트 1위로 재정렬됨.

- [ ] **Step 7: `build_dashboard()` 통합 스모크 테스트**

Run:
```bash
python -c "
import advisor_dashboard as adb
d = adb.build_dashboard()
print('keys:', sorted(d.keys()))
expected = {'summary','must_know','tech_dashboard','todays_action','top_news',
            'impact_flow','fact_impact','scenarios','calendar','top10','bkr','generated_at'}
assert set(d.keys()) == expected, d.keys()
assert len(d['scenarios']) == 3
assert len(d['top10']['us_top5']) == 5
assert len(d['top10']['kr_top5']) == 5
print('generated_at:', d['generated_at'])
print('OK — build_dashboard() 예외 없이 실행됨')
"
```

Expected: `OK — build_dashboard() 예외 없이 실행됨` 출력. yfinance/RSS 응답 상태와 무관하게(부분 실패 허용) 예외가 발생하지 않아야 한다.

- [ ] **Step 8: Commit**

```bash
git add advisor_dashboard.py
git commit -m "feat(advisor_dashboard): add 10-section rule-template orchestration"
```

---

### Task 5: `advisor_report.py` — 정적 HTML 리포트 렌더러 (신규)

**Files:**
- Create: `advisor_report.py`
- Modify: `.gitignore:6-11` (`reports/` 추가)

**Interfaces:**
- Consumes: `advisor_dashboard.TECH_LABELS: dict[str, str]`(Task 4)
- Consumes: `advisor_dashboard.build_dashboard() -> dict`(Task 4, 반환 스키마는 Task 4 Interfaces 참고)
- Produces: `render_html(dashboard: dict) -> str` — 독립 실행형 HTML 문자열(외부 리소스 참조 없음).
- Produces: `save_report(html: str, as_of: date|None = None) -> Path` — `reports/YYYY-MM-DD_briefing.html`에 저장, 저장된 `Path` 반환.

- [ ] **Step 1: 파일 작성**

```python
"""
advisor_report.py — 일간 시황 대시보드 정적 HTML 리포트 (Family A)
═══════════════════════════════════════════════════════════════════════
advisor_dashboard.build_dashboard()의 10섹션 dict를 참고 이미지 스타일의
독립 실행형 HTML 문서로 렌더링한다. 실제 뉴스 관련 스톡 사진은 재현하지
않고 아이콘/이모지 카드로 단순화한다(설계 스펙 §2 — 2026-08-17 사용자
승인). 외부 템플릿 엔진 의존성 없이 순수 Python 문자열 포맷으로 조립한다.
"""
from __future__ import annotations
import os
from datetime import date
from pathlib import Path
from typing import Optional

import advisor_dashboard as adb

_HERE = os.path.dirname(os.path.abspath(__file__))

_CSS = """
body { background:#0d1117; color:#d6dde8; font-family:'Segoe UI',sans-serif; margin:0; padding:24px; }
.header { background:#0b2a5c; color:#fff; padding:20px 24px; border-radius:12px; margin-bottom:16px; }
.header h1 { margin:0 0 4px; font-size:22px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-bottom:20px; }
.card { background:#1a1d26; border:1px solid #2e3650; border-radius:12px; padding:14px 16px; }
.card h3 { margin:0 0 6px; font-size:14px; color:#8899aa; }
.card .val { font-size:20px; font-weight:700; }
.up { color:#00d084; } .down { color:#ff4444; }
.section-title { font-size:16px; font-weight:700; margin:24px 0 10px; border-bottom:1px solid #2e3650; padding-bottom:6px; }
table { width:100%; border-collapse:collapse; }
th, td { text-align:left; padding:8px 10px; border-bottom:1px solid #2e3650; font-size:13px; }
.flow { display:flex; gap:8px; flex-wrap:wrap; }
.flow .step { flex:1; min-width:140px; background:#1a1d26; border:1px solid #2e3650; border-radius:10px; padding:10px 12px; }
.scenario { display:flex; gap:10px; }
.scenario .box { flex:1; background:#1a1d26; border:1px solid #2e3650; border-radius:10px; padding:12px; }
.scenario .likely { border-color:#00d084; }
.footer { margin-top:24px; font-size:12px; color:#8899aa; }
"""


def _fmt_pct(v) -> str:
    return f"{v:+.2f}%" if isinstance(v, (int, float)) else "—"


def _tech_dashboard_html(dash: dict) -> str:
    if dash.get("_status") == "NO_YFINANCE":
        return "<p>yfinance 미설치로 시황 데이터를 가져올 수 없습니다.</p>"
    cards = []
    for key, label in adb.TECH_LABELS.items():
        v = dash.get(key, {}) if isinstance(dash.get(key), dict) else {}
        price = v.get("price")
        chg = v.get("chg_pct")
        cls = "up" if isinstance(chg, (int, float)) and chg >= 0 else "down"
        price_txt = f"{price:,.2f}" if isinstance(price, (int, float)) else "—"
        cards.append(
            f'<div class="card"><h3>{label}</h3>'
            f'<div class="val">{price_txt}</div>'
            f'<div class="{cls}">{_fmt_pct(chg)}</div></div>'
        )
    return f'<div class="grid">{"".join(cards)}</div>'


def _summary_html(movers: list[dict]) -> str:
    if not movers:
        return "<p>변동 데이터가 없습니다.</p>"
    items = "".join(f"<li>{m['text']}</li>" for m in movers)
    return f"<ul>{items}</ul>"


def _must_know_html(movers: list[dict]) -> str:
    if not movers:
        return "<p>변동 데이터가 없습니다.</p>"
    cards = "".join(
        f'<div class="card"><h3>0{i+1}. {m["label"]}</h3>'
        f'<div class="val">{_fmt_pct(m["chg_pct"])}</div></div>'
        for i, m in enumerate(movers)
    )
    return f'<div class="grid">{cards}</div>'


def _action_html(action: dict) -> str:
    if action.get("_status") != "ok":
        return f'<p>Today\'s Action 생성 실패 [{action.get("_status")}]: {action.get("_msg", "")}</p>'
    return f'<p>{action["commentary"]}</p><p><b>💡 {action["action"]}</b></p>'


def _news_html(items: list[dict]) -> str:
    if not items:
        return "<p>오늘 선별된 헤드라인이 없습니다.</p>"
    rows = "".join(
        f'<li><b>[{it["source"]}]</b> <a href="{it["link"]}">{it["title"]}</a></li>'
        for it in items
    )
    return f"<ul>{rows}</ul>"


def _flow_html(flow: list[dict]) -> str:
    if not flow:
        return "<p>오늘은 뚜렷한 드라이버가 없습니다(임계값 미달).</p>"
    steps = "".join(f'<div class="step"><b>{s["step"]}</b><br>{s["label"]}</div>' for s in flow)
    return f'<div class="flow">{steps}</div>'


def _scenarios_html(scenarios: list[dict]) -> str:
    boxes = "".join(
        f'<div class="box{" likely" if sc["likely"] else ""}">'
        f'<b>{sc["label"]}{" ⭐" if sc["likely"] else ""}</b><p>{sc["text"]}</p></div>'
        for sc in scenarios
    )
    return f'<div class="scenario">{boxes}</div>'


def _calendar_html(events: list[dict]) -> str:
    if not events:
        return "<p>등록된 일정이 없습니다.</p>"
    rows = "".join(
        f'<tr><td>{e["date"]}</td><td>{e["time_kst"]}</td><td>{e["event"]}</td>'
        f'<td>{"★" * int(e.get("importance", 1))}</td><td>{e["source"]}</td></tr>'
        for e in events
    )
    return (
        "<table><tr><th>날짜</th><th>시각(KST)</th><th>이벤트</th><th>중요도</th><th>발표처</th></tr>"
        f"{rows}</table>"
    )


def _fact_impact_html(rows: list[dict]) -> str:
    if not rows:
        return "<p>오늘은 뚜렷한 팩트/임팩트가 없습니다.</p>"
    body = "".join(f'<tr><td>{r["fact"]}</td><td>{r["impact"]}</td></tr>' for r in rows)
    return f"<table><tr><th>Fact</th><th>Impact</th></tr>{body}</table>"


def _top10_html(top10: dict) -> str:
    def _col(items: list[dict]) -> str:
        if not items:
            return "<p>—</p>"
        rows = "".join(
            f"<li>{i+1}. <b>{it['category']}</b> — {it['company']}</li>"
            for i, it in enumerate(items)
        )
        return f"<ol style='list-style:none;padding-left:0;'>{rows}</ol>"

    return (
        '<div class="grid" style="grid-template-columns:1fr 1fr;">'
        f'<div class="card"><h3>🇺🇸 미국 TOP5</h3>{_col(top10.get("us_top5", []))}</div>'
        f'<div class="card"><h3>🇰🇷 한국 TOP5</h3>{_col(top10.get("kr_top5", []))}</div>'
        "</div>"
    )


def render_html(dashboard: dict) -> str:
    """advisor_dashboard.build_dashboard() 출력 → 독립 실행형 HTML 문자열."""
    sections = [
        ("① Today's Summary", _summary_html(dashboard["summary"])),
        ("② 오늘 반드시 알아야 할 3가지", _must_know_html(dashboard["must_know"])),
        ("③ Tech Dashboard", _tech_dashboard_html(dashboard["tech_dashboard"])),
        ("④ Today's Action", _action_html(dashboard["todays_action"])),
        ("⑤ TOP NEWS", _news_html(dashboard["top_news"])),
        ("⑥ Global → Korea Impact Flow", _flow_html(dashboard["impact_flow"])),
        ("⑦ 오늘 시나리오", _scenarios_html(dashboard["scenarios"])),
        ("⑧ 오늘·이번주 일정", _calendar_html(dashboard["calendar"])),
        ("⑨ Fact / Impact", _fact_impact_html(dashboard["fact_impact"])),
        ("⑩ 수혜 가능 카테고리 · 관찰기업 TOP10", _top10_html(dashboard["top10"])),
    ]
    body = "".join(f'<div class="section-title">{title}</div>{html}' for title, html in sections)
    return (
        "<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'>"
        f"<title>해외 테크·시장 브리핑 {dashboard.get('generated_at', '')[:10]}</title>"
        f"<style>{_CSS}</style></head><body>"
        '<div class="header"><h1>해외 테크·시장 브리핑</h1>'
        f'<div>생성 시각: {dashboard.get("generated_at", "")}</div></div>'
        f"{body}"
        '<div class="footer">본 자료는 정보 제공 목적이며 투자 권유가 아닙니다.</div>'
        "</body></html>"
    )


def save_report(html: str, as_of: Optional[date] = None) -> Path:
    """reports/YYYY-MM-DD_briefing.html로 저장, 저장된 Path 반환."""
    as_of = as_of or date.today()
    out_dir = Path(_HERE) / "reports"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{as_of.isoformat()}_briefing.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
```

- [ ] **Step 2: `.gitignore`에 `reports/` 추가**

`.gitignore:6-11`의 현재 내용:

```
# ── 캐시 / 생성물 ───────────────────────────────────────────
corpcode.xml
__pycache__/
*.pyc
.streamlit/secrets.toml
```

다음으로 교체(`reports/` 한 줄 추가):

```
# ── 캐시 / 생성물 ───────────────────────────────────────────
corpcode.xml
__pycache__/
*.pyc
.streamlit/secrets.toml
reports/
```

- [ ] **Step 3: 스모크 테스트 실행 (실제 `build_dashboard()` 출력으로 렌더링)**

Run:
```bash
python -c "
import advisor_dashboard as adb
import advisor_report as ar

d = adb.build_dashboard()
html = ar.render_html(d)
assert html.startswith('<!DOCTYPE html>')
for marker in (\"①\", \"②\", \"③\", \"④\", \"⑤\", \"⑥\", \"⑦\", \"⑧\", \"⑨\", \"⑩\"):
    assert marker in html, f'missing section marker {marker}'
print('html length:', len(html))

path = ar.save_report(html)
print('saved to:', path)
assert path.exists()
assert path.read_text(encoding='utf-8') == html
print('OK — 10섹션 마커 전부 존재, 파일 저장 확인')
"
```

Expected: `OK — 10섹션 마커 전부 존재, 파일 저장 확인` 출력. `reports/YYYY-MM-DD_briefing.html` 파일이 실제로 생성됨(테스트 후 수동으로 열어 육안 확인 권장 — 카드 그리드·색상·10섹션이 참고 이미지와 같은 순서로 보이는지).

- [ ] **Step 4: Commit**

```bash
git add advisor_report.py .gitignore
git commit -m "feat(advisor_report): add static HTML dashboard renderer"
```

---

### Task 6: `advisor_app.py` — "📰 시황 브리핑" 탭을 10섹션 대시보드로 확장

**Files:**
- Modify: `advisor_app.py:23-25` (imports)
- Modify: `advisor_app.py:80-82` (`load_briefing` 캐시 함수 → `load_dashboard`로 교체)
- Modify: `advisor_app.py:181-253` (tab2 본문 전체 교체)

**Interfaces:**
- Consumes: `advisor_dashboard.build_dashboard() -> dict`(Task 4), `advisor_dashboard.TECH_LABELS`(Task 4), `advisor_report.render_html(dashboard) -> str`(Task 5), `advisor_report.save_report(html) -> Path`(Task 5)

- [ ] **Step 1: import 추가**

`advisor_app.py:23-25`의 현재 내용:

```python
import advisor_data as ad
import advisor_llm as al
import advisor_briefing as ab
```

다음으로 교체:

```python
import advisor_data as ad
import advisor_llm as al
import advisor_briefing as ab
import advisor_dashboard as adb
import advisor_report as ar
```

- [ ] **Step 2: 캐시 함수 교체**

`advisor_app.py:80-82`의 현재 내용:

```python
@st.cache_data(ttl=1800, show_spinner=False)
def load_briefing() -> dict:
    return ab.build_briefing()
```

다음으로 교체(더 이상 쓰이지 않는 `load_briefing`을 `load_dashboard`로 대체 — tab2가 이제 `advisor_dashboard.build_dashboard()`를 직접 쓴다):

```python
@st.cache_data(ttl=1800, show_spinner=False)
def load_dashboard() -> dict:
    return adb.build_dashboard()
```

- [ ] **Step 3: tab2 본문을 10섹션 대시보드로 교체**

`advisor_app.py:181-253`(`with tab2:`부터 `with tab1:` 바로 앞줄까지)의 현재 내용 전체를 다음으로 교체:

```python
with tab2:
    st.caption("일간 시황 대시보드 · 오재승(매크로·타이밍) × 빈규리(펀더멘탈) · 온디맨드 생성")
    if st.button("📰 브리핑 생성", type="primary"):
        with st.spinner("시황 데이터 수집 + 대시보드 조립 중…"):
            result = load_dashboard()
            st.session_state["dashboard"] = result

            # 실패 상태가 30분 TTL 캐시에 그대로 굳어버리면 재클릭해도 같은
            # 실패가 반복 반환된다 — RSS 장애/yfinance rate-limit 등 "깨끗하지
            # 않은" 결과일 때만 캐시를 비워 다음 클릭이 재시도되게 한다.
            # NO_FOCUS_STOCK(빈규리 후보군이 오늘 뉴스에 없음)은 정상적인
            # 결정론적 결과이지 실패가 아니므로 캐시를 비우지 않는다.
            ojs_clean = result.get("todays_action", {}).get("_status") == "ok"
            bkr_clean = result.get("bkr", {}).get("_status") in ("ok", "NO_FOCUS_STOCK")
            dash_clean = result.get("tech_dashboard", {}).get("_status") != "NO_YFINANCE"
            if not (ojs_clean and bkr_clean and dash_clean):
                load_dashboard.clear()

    dboard = st.session_state.get("dashboard")
    if not dboard:
        st.info("위 버튼을 눌러 오늘의 시황 대시보드를 생성하세요.")
    else:
        st.caption(f"생성 시각: {dboard['generated_at']}")

        report_html = ar.render_html(dboard)
        ar.save_report(report_html)
        st.download_button(
            "📥 리포트 다운로드 (HTML)",
            data=report_html,
            file_name=f"{dboard['generated_at'][:10]}_briefing.html",
            mime="text/html",
        )

        st.markdown("### ① Today's Summary")
        for m in dboard["summary"]:
            st.markdown(f"- {m['text']}")

        st.markdown("### ② 오늘 반드시 알아야 할 3가지")
        must_know = dboard["must_know"]
        if must_know:
            mk_cols = st.columns(len(must_know))
            for i, m in enumerate(must_know):
                mk_cols[i].metric(f"0{i+1}. {m['label']}", f"{m['chg_pct']:+.2f}%")

        st.markdown("### ③ Tech Dashboard")
        dash = dboard["tech_dashboard"]
        if dash.get("_status") == "NO_YFINANCE":
            st.warning("yfinance 미설치로 시황 데이터를 가져올 수 없습니다.")
        else:
            _cols = st.columns(len(adb.TECH_LABELS))
            for i, (k, label) in enumerate(adb.TECH_LABELS.items()):
                v = dash.get(k, {}) if isinstance(dash.get(k), dict) else {}
                price = v.get("price")
                chg = v.get("chg_pct")
                _cols[i].metric(
                    label,
                    f"{price:,.2f}" if isinstance(price, (int, float)) else "—",
                    delta=f"{chg}%" if chg is not None else None,
                )

        st.markdown("### ④ Today's Action")
        action = dboard["todays_action"]
        if action.get("_status") == "ok":
            st.markdown(action["commentary"])
            st.success(f"💡 {action['action']}")
            with st.expander("근거 신호"):
                st.json(action.get("signals", {}))
        else:
            st.warning(f"Today's Action 생성 실패 [{action.get('_status')}]: {action.get('_msg','')}")

        st.markdown("### ⑤ TOP NEWS")
        if not dboard["top_news"]:
            st.info("오늘 선별된 헤드라인이 없습니다.")
        else:
            for item in dboard["top_news"]:
                st.markdown(f"**[{item['source']}]** [{item['title']}]({item['link']})")

        st.markdown("### ⑥ Global → Korea Impact Flow")
        flow = dboard["impact_flow"]
        if not flow:
            st.info("오늘은 뚜렷한 드라이버가 없습니다(임계값 미달).")
        else:
            flow_cols = st.columns(len(flow))
            for i, step in enumerate(flow):
                flow_cols[i].markdown(f"**{step['step']}**\n\n{step['label']}")

        st.markdown("### ⑦ 오늘 시나리오")
        sc_cols = st.columns(3)
        for i, sc in enumerate(dboard["scenarios"]):
            with sc_cols[i]:
                st.markdown(f"**{sc['label']}**" + (" ⭐ 가장 유력" if sc["likely"] else ""))
                st.caption(sc["text"])

        st.markdown("### ⑧ 오늘·이번주 일정")
        if not dboard["calendar"]:
            st.info("등록된 일정이 없습니다.")
        else:
            st.table(dboard["calendar"])

        st.markdown("### ⑨ Fact / Impact")
        if not dboard["fact_impact"]:
            st.info("오늘은 뚜렷한 팩트/임팩트가 없습니다.")
        else:
            st.table(dboard["fact_impact"])

        st.markdown("### ⑩ 수혜 가능 카테고리 · 관찰기업 TOP10")
        t1, t2 = st.columns(2)
        with t1:
            st.markdown("**🇺🇸 미국 TOP5**")
            for i, item in enumerate(dboard["top10"].get("us_top5", [])):
                st.markdown(f"{i+1}. **{item['category']}** — {item['company']}")
        with t2:
            st.markdown("**🇰🇷 한국 TOP5**")
            for i, item in enumerate(dboard["top10"].get("kr_top5", [])):
                st.markdown(f"{i+1}. **{item['category']}** — {item['company']}")

        st.markdown("### 🟣 빈규리 해설 — 펀더멘탈")
        bkr = dboard["bkr"]
        if bkr.get("_status") == "ok":
            st.markdown(f"**{bkr['focus_stock']}**")
            st.markdown(bkr["commentary"])
            st.caption(bkr["disclaimer"])
        elif bkr.get("_status") == "NO_FOCUS_STOCK":
            st.info(bkr.get("_msg", "오늘은 해당되는 종목이 없습니다."))
        else:
            st.warning(f"빈규리 해설 생성 실패 [{bkr.get('_status')}]: {bkr.get('_msg','')}")

```

주의: 이 블록 바로 다음 줄(기존 파일의 255번째 줄)에 있던 `with tab1:`은 그대로 남겨둔다 — 교체 대상은 `with tab2:`부터 `with tab1:` 바로 앞줄까지만이다.

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

Expected: 두 번의 `print`가 모두 `None`(예외 없음)을 출력하고 마지막 줄에 `OK — no exceptions in either tab`이 출력됨.

- [ ] **Step 5: Commit**

```bash
git add advisor_app.py
git commit -m "feat(advisor_app): expand briefing tab to 10-section daily dashboard"
```

---

## Self-Review 결과 (계획 작성자 자체 점검)

- **스펙 커버리지**: 스펙 §3의 10개 섹션 전부 Task 4(`advisor_dashboard.py`)의 필드 + Task 6(Streamlit)/Task 5(HTML) 렌더링에 1:1 매핑됨 — ①②summarize_movers, ③Task1(us10y)+TECH_LABELS, ④기존 generate_ojs_commentary 재사용(신규 코드 없음, 스펙과 일치), ⑤기존 select_top_headlines 재사용, ⑥⑨apply_impact_rules, ⑦generate_scenarios, ⑧load_econ_calendar, ⑩rank_theme_watchlist. 스펙 §4 컴포넌트 목록(신규 3개 JSON, `advisor_dashboard.py`, `advisor_report.py`, `advisor_app.py` 수정) 전부 태스크로 존재. 스펙 §6 에러 처리(JSON 로드 실패 시 `_status`/빈 리스트, `us10y` 실패 시 개별 `NO_DATA`, 일정 없음은 에러 아님)를 Task 4/5/6 전반에 반영. 스펙 §8 Out of Scope(Family B/C/D, LLM, 자동 캘린더 수집, 스케줄링)는 계획에 포함하지 않음 확인.
- **플레이스홀더 스캔**: TBD/TODO/"적절히 처리" 류 없음. 모든 스텝에 실행 가능한 실제 코드·명령이 포함됨.
- **타입 일관성**: `build_dashboard()`가 반환하는 12개 키(`summary/must_know/tech_dashboard/todays_action/top_news/impact_flow/fact_impact/scenarios/calendar/top10/bkr/generated_at`)를 Task 5(`render_html`)와 Task 6(Streamlit 렌더링)이 정확히 동일한 이름으로 참조하는지 확인 완료 — 필드명 불일치 없음. `TECH_LABELS`는 Task 4에서 정의되고 Task 5/6이 동일 딕셔너리를 import해서 쓰므로 Tech Dashboard 순서·라벨이 두 렌더러 간 어긋나지 않음. `generate_scenarios` 반환 항목의 `id/label/text/likely` 키를 Task 5/6 모두 동일하게 사용.
