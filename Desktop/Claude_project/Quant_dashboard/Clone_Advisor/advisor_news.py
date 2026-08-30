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
from urllib.parse import quote

import pandas as pd
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
    "us10y": "^TNX",
    "us30y": "^TYX",
    "dxy": "DX-Y.NYB",
    "usdkrw": "KRW=X",
}

# 장단기 스프레드 계산 전용 만기 3종. ^IRX(13주)는 Tech Dashboard KPI에는
# 올리지 않는다 — KPI에 넣으면 summarize_movers()/impact_rules 매칭 후보가
# 늘어나 기존 상위 변동 종목 선정 결과가 흔들린다.
_YIELD_CURVE_TICKERS = {
    "us3m": "^IRX",
    "us10y": "^TNX",
    "us30y": "^TYX",
}


def get_yield_curve_history(period: str = "1y") -> dict:
    """미국 국채 3개월/10년/30년 종가 히스토리를 날짜 기준으로 합쳐 반환.

    스프레드 계산은 advisor_dashboard.build_yield_curve()의 몫 — 여기선
    원본 수집만 한다(이 모듈의 설계 원칙). 3종 중 하나라도 못 받으면
    스프레드를 만들 수 없으므로 부분 성공 없이 NO_DATA로 끝낸다.
    """
    if yf is None:
        return {"_status": "NO_YFINANCE", "series": []}

    closes = {}
    for key, ticker in _YIELD_CURVE_TICKERS.items():
        try:
            close = yf.Ticker(ticker).history(period=period)["Close"].dropna()
        except Exception:
            close = None
        if close is None or close.empty:
            return {"_status": "NO_DATA", "series": [], "_msg": f"{ticker} 조회 실패"}
        closes[key] = close

    # 만기별 휴장일이 어긋난 날짜는 스프레드를 낼 수 없으므로 통째로 버린다.
    df = pd.concat(closes.values(), axis=1, keys=closes.keys()).dropna()
    if df.empty:
        return {"_status": "NO_DATA", "series": [], "_msg": "3종 공통 거래일 없음"}

    series = [
        {"date": idx.strftime("%Y-%m-%d"),
         "us3m": float(row["us3m"]), "us10y": float(row["us10y"]),
         "us30y": float(row["us30y"])}
        for idx, row in df.iterrows()
    ]
    return {"_status": "ok", "period": period, "series": series}


_RSS_PRIMARY = ("https://finance.yahoo.com/news/rssindex", "Yahoo Finance")
_RSS_FALLBACK = ("https://www.investing.com/rss/news.rss", "Investing.com")

# 빈규리(BKR) 페르소나 매칭 전용 — 코스닥 종목명은 한글이라 영문 소스로는 거의 안 걸린다.
_RSS_KR_PRIMARY = ("https://www.hankyung.com/feed/economy", "한국경제")
_RSS_KR_FALLBACK = ("https://www.yna.co.kr/rss/economy.xml", "연합뉴스")


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


def _fetch_rss(sources: tuple[tuple[str, str], ...], limit: int) -> list[dict]:
    """소스 목록을 순서대로 시도, 첫 성공(빈 결과 아님)을 반환. 전부 실패하면 []."""
    for url, label in sources:
        try:
            r = requests.get(url, headers=_HEADERS, timeout=10)
            r.raise_for_status()
            items = _parse_rss(r.text, label, limit)
            if items:
                return items
        except Exception:
            continue
    return []


def fetch_raw_headlines(limit: int = 20) -> list[dict]:
    """Yahoo Finance RSS(1차) → 실패/빈 결과 시 Investing.com RSS(폴백). 둘 다 실패하면 []."""
    return _fetch_rss((_RSS_PRIMARY, _RSS_FALLBACK), limit)


def fetch_korean_headlines(limit: int = 20) -> list[dict]:
    """한국경제 RSS(1차) → 실패/빈 결과 시 연합뉴스 RSS(폴백). 빈규리 종목매칭 전용. 둘 다 실패하면 []."""
    return _fetch_rss((_RSS_KR_PRIMARY, _RSS_KR_FALLBACK), limit)


_NEWS_RSS_LOCALE = {
    "en": "hl=en-US&gl=US&ceid=US:en",
    "ko": "hl=ko&gl=KR&ceid=KR:ko",
}


def fetch_policy_news(query: str, lang: str = "ko", limit: int = 1) -> list[dict]:
    """Google News RSS 검색 — 정책 카드 fact_state 자동 갱신 전용.

    카드별 니치한 정책 주제(예: '레버리지 ETF 규제')는 범용 헤드라인 RSS엔
    거의 안 걸리므로 카드마다 독립된 검색 쿼리로 조회한다. 실패/빈 결과면 [].
    """
    if not query:
        return []
    locale = _NEWS_RSS_LOCALE.get(lang, _NEWS_RSS_LOCALE["ko"])
    url = f"https://news.google.com/rss/search?q={quote(query)}&{locale}"
    try:
        r = requests.get(url, headers=_HEADERS, timeout=10)
        r.raise_for_status()
        # Google News RSS는 charset을 헤더에 안 주는 경우가 있어 requests가
        # ISO-8859-1로 오판, 한글 제목이 깨진다. bytes를 넘기면 ET가 XML
        # 선언의 encoding="UTF-8"을 직접 읽어 올바르게 디코딩한다.
        return _parse_rss(r.content, "Google News", limit)
    except Exception:
        return []
