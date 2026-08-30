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

import pandas as pd

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
        (f"KOSPI {kospi.get('price','—')}({kospi_chg:+.2f}%)" if isinstance(kospi_chg, (int, float))
         else "KOSPI 시세 조회 실패"),
        (f"KOSDAQ {kosdaq.get('price','—')}({kosdaq_chg:+.2f}%)" if isinstance(kosdaq_chg, (int, float))
         else "KOSDAQ 시세 조회 실패"),
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
        "price_driver": (f"KOSPI {kospi_chg:+.2f}%" if isinstance(kospi_chg, (int, float))
                          else "KOSPI 데이터 없음"),
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


def refresh_policy_card_news(cards: list[dict]) -> list[dict]:
    """카드별 policy_cards.json의 "query"로 Google News를 조회해
    fact_state/source_url만 덮어쓴다. outlook/korea_impact/polarity/accuracy/
    korea_link/checkpoint는 판단이 필요한 수기 필드라 건드리지 않는다.
    카드별 조회는 서로 독립이라 한 카드가 실패해도 나머지는 영향받지 않고,
    실패한 카드는 기존 값을 그대로 유지한다.
    """
    out = []
    for c in cards:
        updated = dict(c)
        query = c.get("query", "")
        lang = "en" if c.get("country") == "US" else "ko"
        news = an.fetch_policy_news(query, lang=lang)
        if news:
            updated["fact_state"] = news[0].get("title", updated.get("fact_state", ""))
            updated["source_url"] = news[0].get("link", "")
        out.append(updated)
    return out


# ─────────────────────────────────────────────────────────────────────
# 오케스트레이션
# ─────────────────────────────────────────────────────────────────────
def build_briefing_kr() -> dict:
    return {
        "page1": build_page1(),
        "page2": build_page2(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
