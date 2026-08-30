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
import advisor_news as an

_HERE = os.path.dirname(os.path.abspath(__file__))

# ─────────────────────────────────────────────────────────────────────
# Tech Dashboard 표시 순서/라벨 — 참고 이미지 순서(S&P500/Nasdaq/Dow/SOX/
# VIX/10Y/30Y/DXY/USD-KRW)와 동일. advisor_report.py도 이 순서를 그대로 쓴다.
# ─────────────────────────────────────────────────────────────────────
TECH_LABELS: dict[str, str] = {
    "sp500": "S&P 500",
    "nasdaq": "Nasdaq",
    "dow": "Dow",
    "sox": "SOX(반도체)",
    "vix": "VIX",
    "us10y": "美 10년물",
    "us30y": "美 30년물",
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
# ③-1 미국 국채 금리 곡선 — 장단기 스프레드 2종(bp)
# ─────────────────────────────────────────────────────────────────────
# 10Y-3M은 뉴욕연준 침체확률 모형이 쓰는 공식 스프레드고, 30Y-10Y는 이번에
# 추가한 30년물로 보는 장기구간 기울기다. 야후에 2년물 인덱스 티커가 없어
# 교과서적 10Y-2Y 대신 이 조합을 쓴다(2026-08-29 사용자 확정).
SPREAD_LABELS: dict[str, str] = {
    "t10y3m": "10년-3개월",
    "t30y10y": "30년-10년",
}

_TRADING_DAYS_1M = 21
_TRADING_DAYS_3M = 63
# 1개월 변화가 이 폭 미만이면 방향을 붙이지 않는다 — bp를 정수로
# 표기하므로 "+0bp인데 스티프닝" 같은 모순을 막는다.
_FLAT_BP = 1.0

_EMPTY_YIELD_CURVE = {"series": [], "latest": {}, "chg_1m": {}, "chg_3m": {},
                      "inverted": None, "text": ""}


def _spread_change(series: list[dict], lookback: int) -> dict:
    """lookback 거래일 전 대비 스프레드 변화(bp). 이력이 짧으면 가장 오래된 값 기준."""
    if len(series) < 2:
        return {}
    past = series[-min(lookback + 1, len(series))]
    return {k: round(series[-1][k] - past[k], 1) for k in SPREAD_LABELS}


def _yield_curve_text(latest: dict, chg_1m: dict, inverted: bool) -> str:
    """룰 템플릿 한 줄 요약 — LLM 미사용(설계 스펙 §2)."""
    d10 = chg_1m.get("t10y3m")
    if inverted:
        state = "장단기 금리 역전(경기 침체 경고 구간)"
    elif not isinstance(d10, (int, float)) or abs(d10) < _FLAT_BP:
        state = "기울기 횡보"
    elif d10 > 0:
        state = "스티프닝(장단기 차 확대)"
    else:
        state = "플래트닝(장단기 차 축소)"

    parts = []
    for key, label in SPREAD_LABELS.items():
        value = latest.get(key)
        if not isinstance(value, (int, float)):
            continue
        delta = chg_1m.get(key)
        delta_txt = f"(1개월 {delta:+.0f}bp)" if isinstance(delta, (int, float)) else ""
        parts.append(f"{label} {value:+.0f}bp{delta_txt}")
    return f"{' · '.join(parts)} — {state}" if parts else state


def build_yield_curve(raw: dict) -> dict:
    """advisor_news.get_yield_curve_history() 출력 → 스프레드 시계열·추세 요약.

    금리는 % 단위(예: 4.25)로 오므로 스프레드는 bp(×100)로 환산한다.
    수집 실패는 그대로 전파해 렌더러가 섹션만 접고 나머지는 살리게 한다.
    """
    status = raw.get("_status")
    if status != "ok" or not raw.get("series"):
        return {"_status": status if status != "ok" else "NO_DATA",
                "_msg": raw.get("_msg", ""), **_EMPTY_YIELD_CURVE}

    series = [
        {"date": r["date"],
         "t10y3m": round((r["us10y"] - r["us3m"]) * 100, 1),
         "t30y10y": round((r["us30y"] - r["us10y"]) * 100, 1)}
        for r in raw["series"]
    ]
    latest = {k: series[-1][k] for k in SPREAD_LABELS}
    chg_1m = _spread_change(series, _TRADING_DAYS_1M)
    chg_3m = _spread_change(series, _TRADING_DAYS_3M)
    inverted = latest["t10y3m"] < 0

    return {"_status": "ok", "series": series, "latest": latest,
            "chg_1m": chg_1m, "chg_3m": chg_3m, "inverted": inverted,
            "text": _yield_curve_text(latest, chg_1m, inverted)}


# ─────────────────────────────────────────────────────────────────────
# ⑥⑨ Global → Korea Impact Flow / Fact-Impact — 드라이버→한국영향 매핑
# ─────────────────────────────────────────────────────────────────────
_IMPACT_RULES_PATH = os.path.join(_HERE, "impact_rules.json")


def load_impact_rules() -> Optional[dict]:
    """impact_rules.json 로드. 없거나 손상됐으면 None."""
    if not os.path.exists(_IMPACT_RULES_PATH):
        return None
    try:
        with open(_IMPACT_RULES_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def apply_impact_rules(dashboard: dict, rules: list[dict]) -> dict:
    """Tech Dashboard 변동을 impact_rules.json과 매칭해 flow/fact_impact 생성.

    드라이버별로 방향(up/down)이 일치하고 |chg_pct|가 threshold_pct 이상인
    룰만 후보로 삼는다. 가장 변동폭이 큰 드라이버 1개를 flow의 핵심으로,
    상위 4개까지를 fact_impact 표로 반환한다.
    """
    candidates = []
    for r in rules:
        driver = r.get("driver")
        direction_rule = r.get("direction")
        threshold_pct = r.get("threshold_pct")
        if driver is None or direction_rule is None or threshold_pct is None:
            continue  # 필수 키 누락 — 매칭 불가, 건너뜀
        entry = dashboard.get(driver)
        if not isinstance(entry, dict):
            continue
        chg = entry.get("chg_pct")
        if chg is None:
            continue
        direction = "up" if chg >= 0 else "down"
        if direction != direction_rule:
            continue
        if abs(chg) < abs(threshold_pct):
            continue
        candidates.append((abs(chg), r, chg))

    if not candidates:
        return {"_status": "NO_DRIVER", "flow": [], "fact_impact": []}

    candidates.sort(key=lambda t: t[0], reverse=True)
    _, top_rule, top_chg = candidates[0]
    top_driver = top_rule.get("driver", "")

    flow = [
        {"step": "글로벌 요인", "label": top_rule.get("category", "")},
        {"step": "미국 시장 반응", "label": f"{top_driver.upper()} {top_chg:+.2f}%"},
        {"step": "한국 전달 경로", "label": top_rule.get("korea_impact", "")},
        {"step": "핵심 확인", "label": "USD/KRW · 외국인 수급"},
    ]
    fact_impact = [
        {"fact": f"{r.get('driver', '').upper()} {chg:+.2f}%", "impact": r.get("korea_impact", "")}
        for _, r, chg in candidates[:4]
    ]
    return {"_status": "ok", "driver": top_driver, "chg_pct": top_chg,
            "flow": flow, "fact_impact": fact_impact}


# ─────────────────────────────────────────────────────────────────────
# ⑦ 오늘 시나리오 — OJS 정량 신호(그물망 배열/MACD) + VIX 레벨 룰 매칭
# ─────────────────────────────────────────────────────────────────────
def generate_scenarios(ojs_signals: dict, vix_price: Optional[float]) -> list[dict]:
    """advisor_data.compute_ojs_signals() 출력 + VIX로 BULL/BASE/BEAR 중 유력 선택.

    ojs_signals가 비어 있거나(_status 있음) 판단 근거가 부족하면 BASE로 수렴한다.
    """
    arrangement = ojs_signals.get("net_arrangement", "")
    macd_state = ojs_signals.get("macd_state", "")
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
    try:
        with open(_CALENDAR_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
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
    """theme_watchlist.json 로드. 없거나 손상됐으면 None."""
    if not os.path.exists(_WATCHLIST_PATH):
        return None
    try:
        with open(_WATCHLIST_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


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

    yield_curve = build_yield_curve(an.get_yield_curve_history())

    calendar = load_econ_calendar()

    watchlist = load_theme_watchlist()
    kr_headlines = briefing.get("kr_headlines", [])
    top_headlines = briefing["headlines"].get("top", [])
    top10 = (rank_theme_watchlist(watchlist, top_headlines, kr_headlines)
             if watchlist else {"us_top5": [], "kr_top5": []})

    return {
        "summary": movers,
        "must_know": list(movers),
        "tech_dashboard": dashboard,
        "yield_curve": yield_curve,
        "todays_action": ojs,
        "top_news": top_headlines,
        "impact_flow": impact.get("flow", []),
        "fact_impact": impact.get("fact_impact", []),
        "scenarios": scenarios,
        "calendar": calendar,
        "top10": top10,
        "bkr": briefing["bkr"],
        "generated_at": briefing["generated_at"],
        # RSS 완전 장애 시그널 — 캐시 무효화 게이트(advisor_app.py)와 TOP NEWS
        # 섹션이 "헤드라인 0건"과 "RSS 응답 없음"을 구분할 수 있도록 전달한다
        # (select_top_headlines()가 성공 시 "ok", 실패 시 "NO_HEADLINES"를 반환).
        "news_status": briefing["headlines"].get("_status"),
        "news_msg": briefing["headlines"].get("_msg"),
    }
