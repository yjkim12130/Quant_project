"""
advisor_data.py — 개별기업 분석 에이전트 데이터 연동 레이어 (P1 착수)
═══════════════════════════════════════════════════════════════════════
빈규리식 종목카드(stock card)를 위한 raw 데이터 공급기.

  · 한국(KOSPI/KOSDAQ)
        종목코드  : 네이버 종목검색 자동완성 (키 불필요)
        시세/밸류 : yfinance  (.KS / .KQ 서픽스)
        재무제표  : DART OpenAPI fnlttSinglAcntAll  (★ API 키 필요)
  · 미국/글로벌
        시세·재무 : yfinance

설계 원칙
  - 의존성 최소화: requests + yfinance + 표준 라이브러리(zipfile/io/xml)만 사용.
  - graceful degradation: DART 키가 없으면 재무는 비우고 시세/밸류만 채운다.
    (→ 에이전트가 "DART 미연동" 상태를 카드에 명시하고 계속 동작)
  - 캐싱: DART corpCode 매핑은 corpcode.xml 로 1회만 내려받아 재사용.

DART API 키 발급(무료): https://opendart.fss.or.kr → 인증키 신청
  사용법(둘 중 하나):
    1) 환경변수      :  setx DART_API_KEY "발급키"     (PowerShell, 새 셸부터 적용)
    2) 키 파일       :  .dart_api_key 파일에 키 한 줄 저장

CLI:
    python advisor_data.py 와이제이링크
    python advisor_data.py AAPL --us
"""
from __future__ import annotations
import io
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from datetime import date
from typing import Optional

import pandas as pd
import requests

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_HERE = os.path.dirname(os.path.abspath(__file__))
_CORPCODE_CACHE = os.path.join(_HERE, "corpcode.xml")


# ─────────────────────────────────────────────────────────────────────
# DART API 키 로딩
# ─────────────────────────────────────────────────────────────────────
def get_dart_key() -> Optional[str]:
    """환경변수 DART_API_KEY 또는 .dart_api_key 파일에서 키를 읽는다."""
    key = os.environ.get("DART_API_KEY")
    if key:
        return key.strip()
    path = os.path.join(_HERE, ".dart_api_key")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    return None


# ─────────────────────────────────────────────────────────────────────
# 1) 한국 종목코드 해석 (네이버 자동완성 — 키 불필요)
# ─────────────────────────────────────────────────────────────────────
def resolve_kr_code(name: str) -> Optional[dict]:
    """한글 종목명 → {code, name, market}. 실패 시 None."""
    try:
        r = requests.get(
            "https://ac.stock.naver.com/ac",
            params={"q": name, "target": "stock"},
            headers=_HEADERS, timeout=10,
        )
        items = r.json().get("items", [])
        if not items:
            return None
        it = items[0]
        return {"code": it["code"], "name": it["name"], "market": it.get("typeCode", "")}
    except Exception:
        return None


def yf_ticker_for(code: str, market: str) -> str:
    """KRX 코드 + 시장 → yfinance 티커."""
    return f"{code}.{'KQ' if market.upper() == 'KOSDAQ' else 'KS'}"


# ─────────────────────────────────────────────────────────────────────
# 2) 시세·밸류에이션 (yfinance — 키 불필요)
# ─────────────────────────────────────────────────────────────────────
def get_quote(ticker: str) -> dict:
    """
    yfinance에서 시세/밸류/규모 핵심 필드를 추려서 반환.

    안정성: 시세·시총·52주는 `fast_info`(스크래핑 없음 → rate-limit에 강함)에서,
    서술·밸류(이름/섹터/PER/매출/마진)는 `.info`(스크래핑 → 간헐 실패)에서 best-effort로.
    `.info`가 비어도 핵심 시세는 살아남는다. 둘 다 실패하면 _status="NO_DATA".
    """
    if yf is None:
        return {"ticker": ticker, "_status": "NO_YFINANCE"}
    t = yf.Ticker(ticker)
    out: dict = {"ticker": ticker, "_status": "ok"}

    # 1) fast_info — 신뢰도 높은 시세/규모
    fi: dict = {}
    try:
        fi = dict(t.fast_info)
    except Exception:
        fi = {}
    price = fi.get("lastPrice")
    if price is None:  # history 폴백
        try:
            h = t.history(period="5d")["Close"].dropna()
            if not h.empty:
                price = float(h.iloc[-1])
        except Exception:
            pass
    out.update({
        "price": price,
        "currency": fi.get("currency"),
        "market_cap": fi.get("marketCap"),
        "shares": fi.get("shares"),
        "wk52_high": fi.get("yearHigh"),
        "wk52_low": fi.get("yearLow"),
    })

    # 2) info — 서술/밸류 (best-effort, 실패해도 무시)
    info: dict = {}
    try:
        info = t.info or {}
    except Exception:
        info = {}
    g = info.get
    out.update({
        "name": g("longName") or g("shortName"),
        "per": g("trailingPE"), "forward_per": g("forwardPE"),
        "pbr": g("priceToBook"),
        "sector": g("sector"), "industry": g("industry"),
        "revenue_ttm": g("totalRevenue"),
        "profit_margin": g("profitMargins"),
    })
    # info로 보강(fast_info 결측 시)
    if out["price"] is None:
        out["price"] = g("currentPrice") or g("regularMarketPrice")
    if out["market_cap"] is None:
        out["market_cap"] = g("marketCap")
    if out["wk52_high"] is None:
        out["wk52_high"] = g("fiftyTwoWeekHigh")
    if out["wk52_low"] is None:
        out["wk52_low"] = g("fiftyTwoWeekLow")
    if not out.get("name"):
        out["name"] = ticker

    if out["price"] is None:
        out["_status"] = "NO_DATA"
    return out


# ─────────────────────────────────────────────────────────────────────
# 3) DART 재무제표 (★ API 키 필요)
# ─────────────────────────────────────────────────────────────────────
def _ensure_corpcode(api_key: str) -> str:
    """corpCode 매핑(zip→xml)을 1회 내려받아 캐시. 캐시 경로 반환."""
    if os.path.exists(_CORPCODE_CACHE) and os.path.getsize(_CORPCODE_CACHE) > 0:
        return _CORPCODE_CACHE
    r = requests.get(
        "https://opendart.fss.or.kr/api/corpCode.xml",
        params={"crtfc_key": api_key}, headers=_HEADERS, timeout=30,
    )
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        xml_bytes = z.read(z.namelist()[0])
    with open(_CORPCODE_CACHE, "wb") as f:
        f.write(xml_bytes)
    return _CORPCODE_CACHE


def get_corp_code(stock_code: str, api_key: str) -> Optional[str]:
    """KRX 6자리 코드 → DART 8자리 corp_code."""
    path = _ensure_corpcode(api_key)
    tree = ET.parse(path)
    for node in tree.getroot().iter("list"):
        sc = (node.findtext("stock_code") or "").strip()
        if sc == stock_code:
            return (node.findtext("corp_code") or "").strip()
    return None


# DART 보고서 코드: 1분기 11013 / 반기 11012 / 3분기 11014 / 사업보고서 11011
def get_dart_financials(corp_code: str, year: int, reprt: str, api_key: str,
                        fs_div: str = "CFS") -> Optional[dict]:
    """DART 단일회사 전체 재무제표 → 핵심 계정 + 파생지표."""
    r = requests.get(
        "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json",
        params={"crtfc_key": api_key, "corp_code": corp_code,
                "bsns_year": str(year), "reprt_code": reprt, "fs_div": fs_div},
        headers=_HEADERS, timeout=20,
    )
    data = r.json()
    if data.get("status") != "000":
        return {"_error": f"DART {data.get('status')}: {data.get('message')}"}

    # 계정의 한글 표시명(account_nm)은 회사·업종마다 다르다(실측 2026-08-16):
    #   매출액(삼성전자) / 영업수익(헥토파이낸셜) — 둘 다 account_id는 ifrs-full_Revenue
    #   영업이익 / 영업이익(손실)(와이제이링크) — 둘 다 dart_OperatingIncomeLoss
    #   당기순이익 / 분기순이익(삼성전자 1Q) / 당기순이익(손실) — 셋 다 ifrs-full_ProfitLoss
    # account_id(DART/XBRL 표준계정코드)는 한글 라벨과 무관하게 고정이라 회사 간에
    # 안정적으로 매칭된다. sj_div(재무제표 종류)로 손익계산서/재무상태표만 보고,
    # account_detail == "-"로 자본변동표 등의 세부 breakdown 행을 제외해
    # 같은 account_id의 다른 금액과 섞이지 않게 한다. 한글 라벨 매칭은 방어적
    # 폴백으로만 남긴다.
    _TAGS = {
        "revenue": (("ifrs-full_Revenue",), ("IS", "CIS"),
                    ("매출액", "영업수익", "수익(매출액)")),
        "operating_income": (("dart_OperatingIncomeLoss",), ("IS", "CIS"),
                             ("영업이익", "영업이익(손실)")),
        "net_income": (("ifrs-full_ProfitLoss",), ("IS", "CIS"),
                       ("당기순이익", "당기순이익(손실)", "분기순이익", "반기순이익")),
        "assets": (("ifrs-full_Assets",), ("BS",), ("자산총계",)),
        "liabilities": (("ifrs-full_Liabilities",), ("BS",), ("부채총계",)),
        "equity": (("ifrs-full_Equity",), ("BS",), ("자본총계",)),
    }

    def _to_float(raw) -> Optional[float]:
        raw = (raw or "").replace(",", "")
        try:
            return float(raw)
        except ValueError:
            return None

    def _find(key: str) -> Optional[float]:
        ids, sj_divs, names = _TAGS[key]
        for it in data["list"]:
            if (it.get("account_id") in ids and it.get("sj_div") in sj_divs
                    and it.get("account_detail", "-") == "-"):
                v = _to_float(it.get("thstrm_amount"))
                if v is not None:
                    return v
        for it in data["list"]:  # 폴백: 한글 라벨 매칭
            if it.get("account_nm") in names:
                v = _to_float(it.get("thstrm_amount"))
                if v is not None:
                    return v
        return None

    rev = _find("revenue")
    op = _find("operating_income")
    net = _find("net_income")
    assets = _find("assets")
    liab = _find("liabilities")
    equity = _find("equity")
    return {
        "year": year, "reprt": reprt, "fs_div": fs_div,
        "revenue": rev, "operating_income": op, "net_income": net,
        "assets": assets, "liabilities": liab, "equity": equity,
        "op_margin": (op / rev) if (op and rev) else None,
        "debt_ratio": (liab / equity) if (liab and equity) else None,
    }


# ─────────────────────────────────────────────────────────────────────
# 3.5) 가격 히스토리 기반 정량 신호 (독립 앱용 — v9.3 미의존)
#      v9.3은 지수 레짐 엔진. 여기선 개별종목용 '간이' 신호를 자체 계산한다.
# ─────────────────────────────────────────────────────────────────────
def get_price_history(ticker: str, period: str = "2y"):
    """yfinance 일봉 종가 시리즈(pandas Series). 실패 시 None."""
    if yf is None:
        return None
    try:
        hist = yf.Ticker(ticker).history(period=period)
        if hist is None or hist.empty:
            return None
        return hist["Close"].dropna()
    except Exception:
        return None


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


def _rsi(close, window: int = 14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(window).mean()
    loss = (-delta.clip(upper=0)).rolling(window).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def compute_quant_signals(close, high=None, low=None) -> dict:
    """개별종목 간이 정량 신호: 200일선 이격·RSI·52주 위치·간이 레짐·ATR(옵션)."""
    if close is None or len(close) < 30:
        return {"_status": "INSUFFICIENT_HISTORY"}
    price = float(close.iloc[-1])
    ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
    ma60 = float(close.rolling(60).mean().iloc[-1]) if len(close) >= 60 else None
    rsi = float(_rsi(close).iloc[-1])
    hi = float(close.tail(252).max())
    lo = float(close.tail(252).min())
    wk52_pos = (price - lo) / (hi - lo) * 100 if hi > lo else None
    ma200_dev = (price / ma200 - 1) * 100 if ma200 else None

    # 간이 레짐 (독립 앱 자체 규칙 — v9.3 정밀 레짐과 별개)
    if ma200 is None:
        regime = "데이터 부족"
    elif price >= ma200 and rsi >= 55:
        regime = "강세(Bull)"
    elif price >= ma200:
        regime = "정배열 눌림" if rsi < 45 else "중립↑"
    elif rsi <= 35:
        regime = "약세 과매도"
    else:
        regime = "약세(Bear)"

    def _ret(days):
        if len(close) > days:
            return (price / float(close.iloc[-1 - days]) - 1) * 100
        return None

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


# ─────────────────────────────────────────────────────────────────────
# 3.6) 오재승 타이밍 신호 (OJS-* 7룰용 — 전부 가격/밸류 데이터로 정량 계산)
#      그물망 12MA · 무릎어깨 MACD · 주도주 PSR · 만수르 분할 (v9.3 미의존)
# ─────────────────────────────────────────────────────────────────────
def _ema(series, span: int):
    return series.ewm(span=span, adjust=False).mean()


def compute_ojs_signals(close, quant: Optional[dict] = None) -> dict:
    """
    오재승 기술적 매매 7룰을 정량 신호로 산출.
      · 그물망(OJS-NET-01): 20~75일 5일간격 12 MA 배열/수렴·발산/색전환(first-flip)
      · 무릎어깨 MACD(OJS-MACD-01): osc 0선 첫 반전 → 그 방향만
      · 주도주(OJS-LEAD-01): PSR = 시총/매출, PSR<1 + 높은 PER 후보
      · 만수르(OJS-CASH-01): 고점 대비 낙폭을 -10% 스텝으로 환산한 분할 단계
    """
    if close is None or len(close) < 80:
        return {"_status": "INSUFFICIENT_HISTORY"}
    price = float(close.iloc[-1])

    # ── 그물망 차트: 20·25·…·75일 (5일 간격, 12개 리본) ──
    periods = list(range(20, 76, 5))  # [20,25,...,75] → 12개

    def _arr_at(offset: int) -> tuple[list, str]:
        vals = []
        for p in periods:
            s = close.rolling(p).mean()
            if len(s) > offset and not _is_nan(s.iloc[-1 - offset]):
                vals.append(float(s.iloc[-1 - offset]))
        if len(vals) < len(periods):
            return vals, "mix"
        if vals == sorted(vals, reverse=True):
            return vals, "bull"   # 정배열(빨강): 짧은 MA가 위
        if vals == sorted(vals):
            return vals, "bear"   # 역배열(파랑)
        return vals, "mix"

    ma_vals, cur = _arr_at(0)
    _, prev5 = _arr_at(5)
    arrangement = {"bull": "정배열(빨강)", "bear": "역배열(파랑)", "mix": "혼조"}[cur]
    first_flip = None
    if prev5 != "bull" and cur == "bull":
        first_flip = "파랑→빨강 전환 — 바닥주 첫 매수 자리(OJS-NET-01)"
    elif prev5 != "bear" and cur == "bear":
        first_flip = "빨강→파랑 전환 — 분할 매도 시작 신호(OJS-NET-01)"
    ribbon_spread = ((max(ma_vals) - min(ma_vals)) / price * 100) if ma_vals else None
    converging = ribbon_spread is not None and ribbon_spread < 3.0  # 수렴=횡보

    # ── 무릎어깨 MACD: osc = (EMA12−EMA26) − signal(EMA9) ──
    macd_line = _ema(close, 12) - _ema(close, 26)
    signal = macd_line.ewm(span=9, adjust=False).mean()
    osc = macd_line - signal
    osc_now, osc_prev = float(osc.iloc[-1]), float(osc.iloc[-2])
    if osc_prev <= 0 < osc_now:
        macd_state = "osc 음→양 전환 — 무릎(매수만)"
    elif osc_prev >= 0 > osc_now:
        macd_state = "osc 양→음 전환 — 어깨(매도만)"
    elif osc_now > 0:
        macd_state = "osc 양(+) 유지 — 상승 구간"
    else:
        macd_state = "osc 음(−) 유지 — 하락 구간"

    # ── 주도주 PSR × PER ──
    psr = per = None
    if quant:
        mc, rev = quant.get("market_cap"), quant.get("revenue_ttm")
        if mc and rev:
            psr = mc / rev
        per = quant.get("per")
    psr_lead = psr is not None and psr < 1.0

    # ── 만수르 분할 단계: 52주 고점 대비 낙폭 → -10% 스텝(0~5) ──
    hi = float(close.tail(252).max())
    drawdown = (price / hi - 1) * 100 if hi > 0 else 0.0
    mansur_step = min(5, max(0, int(abs(drawdown) // 10)))

    return {
        "price": round(price, 2),
        "net_arrangement": arrangement,
        "net_spread_pct": round(ribbon_spread, 2) if ribbon_spread is not None else None,
        "net_converging": converging,
        "net_first_flip": first_flip,
        "macd_osc": round(osc_now, 4),
        "macd_state": macd_state,
        "psr": round(psr, 2) if psr is not None else None,
        "per": round(per, 1) if isinstance(per, (int, float)) else None,
        "psr_lead_candidate": psr_lead,
        "drawdown_from_high_pct": round(drawdown, 1),
        "mansur_step": mansur_step,
        "periods": periods,
    }


def _is_nan(x) -> bool:
    try:
        return x != x
    except Exception:
        return False


_OJS_RULEBOOK_PATH = os.path.join(_HERE, "ojs_rulebook.json")


def load_ojs_rulebook() -> Optional[dict]:
    """ojs_rulebook.json 로드. 없으면 None."""
    if not os.path.exists(_OJS_RULEBOOK_PATH):
        return None
    with open(_OJS_RULEBOOK_PATH, encoding="utf-8") as f:
        return json.load(f)


def evaluate_ojs_rules(ojs: dict) -> list[dict]:
    """compute_ojs_signals 출력 → OJS 7룰 자동 매칭(활성/대기 + 근거)."""
    if not ojs or ojs.get("_status"):
        return []
    out: list[dict] = []

    flip = ojs.get("net_first_flip")
    out.append({
        "id": "OJS-NET-01", "name": "그물망 차트 (12 MA 리본)",
        "active": bool(flip),
        "note": flip or f"{ojs.get('net_arrangement')} · "
                f"리본폭 {ojs.get('net_spread_pct')}% "
                f"({'수렴=횡보' if ojs.get('net_converging') else '발산=추세'})",
    })

    ms = ojs.get("macd_state", "")
    out.append({
        "id": "OJS-MACD-01", "name": "무릎어깨 MACD",
        "active": ("전환" in ms),
        "note": f"{ms} (osc {ojs.get('macd_osc')})",
    })

    lead = ojs.get("psr_lead_candidate")
    psr, per = ojs.get("psr"), ojs.get("per")
    out.append({
        "id": "OJS-LEAD-01", "name": "주도주 발굴 (PSR×PER)",
        "active": bool(lead),
        "note": (f"PSR {psr} {'< 1 → 10배 후보 출발점' if lead else '(1배 이상)'}"
                 + (f" · PER {per}" if per is not None else "")) if psr is not None
                else "PSR 산출 불가(매출 데이터 없음)",
    })

    step = ojs.get("mansur_step", 0)
    dd = ojs.get("drawdown_from_high_pct")
    out.append({
        "id": "OJS-CASH-01", "name": "만수르 기법 (피라미딩 분할)",
        "active": step >= 1,
        "note": (f"고점 대비 {dd}% → {step}/5 분할 매집 구간"
                 if step >= 1 else f"고점 대비 {dd}% — 분할 진입 전(관망)"),
    })
    return out


# ─────────────────────────────────────────────────────────────────────
# 4) 종목카드 조립 (빈규리식 프레임의 정량 슬롯 채우기)
# ─────────────────────────────────────────────────────────────────────
def build_stock_card(name: str, *, us: bool = False, frame: str = "binkyuri",
                     year: Optional[int] = None, reprt: str = "11013") -> dict:
    """
    종목명/티커 → 정량 슬롯이 채워진 종목카드(dict).
    정성(사업/해자/결론)은 RAG 에이전트가 별도로 채운다(여기선 quant 슬롯만).
    """
    card: dict = {
        "name": name, "analyst_frame": frame,
        "as_of": date.today().isoformat(),
        "quant": {}, "financials": {}, "sources": [],
    }

    if us:
        card["ticker"] = name
        card["market"] = "US"
        card["quant"] = get_quote(name)
        card["sources"].append("yfinance")
        return card

    # 한국 종목
    meta = resolve_kr_code(name)
    if not meta:
        card["_error"] = f"종목코드 해석 실패: {name}"
        return card
    card["ticker"] = meta["code"]
    card["market"] = meta["market"]
    tkr = yf_ticker_for(meta["code"], meta["market"])
    card["quant"] = get_quote(tkr)
    card["sources"].append("naver(code)")
    card["sources"].append("yfinance(quote)")

    api_key = get_dart_key()
    if not api_key:
        card["financials"] = {"_status": "DART_KEY_MISSING",
                              "_hint": "환경변수 DART_API_KEY 또는 .dart_api_key 파일 설정"}
        return card

    corp = get_corp_code(meta["code"], api_key)
    if not corp:
        card["financials"] = {"_status": "CORP_CODE_NOT_FOUND"}
        return card
    yr = year or (date.today().year)
    fin = get_dart_financials(corp, yr, reprt, api_key)
    # 분기 데이터가 아직 없으면 직전 연도 사업보고서로 폴백
    if fin and fin.get("_error") and reprt != "11011":
        fin = get_dart_financials(corp, yr - 1, "11011", api_key)
    card["financials"] = fin or {}
    card["corp_code"] = corp
    card["sources"].append("DART(financials)")
    return card


# ─────────────────────────────────────────────────────────────────────
# 5) 빈규리 룰북 적용 (정량 코딩 가능 룰만 자동 평가)
# ─────────────────────────────────────────────────────────────────────
_RULEBOOK_PATH = os.path.join(_HERE, "binkyuri_rulebook.json")


def load_rulebook() -> Optional[dict]:
    """binkyuri_rulebook.json 로드. 없으면 None."""
    if not os.path.exists(_RULEBOOK_PATH):
        return None
    with open(_RULEBOOK_PATH, encoding="utf-8") as f:
        return json.load(f)


def apply_rulebook(card: dict) -> dict:
    """
    종목카드에 빈규리 룰북의 '정량 코딩 가능(codeable=yes)' 룰을 자동 평가해 붙인다.
    정성 룰(해자·진위판별 등)은 RAG 에이전트 몫이라 여기선 평가하지 않고 목록만 남긴다.
    """
    rb = load_rulebook()
    if not rb:
        card["rulebook"] = {"_status": "RULEBOOK_MISSING"}
        return card

    q = card.get("quant", {})
    fin = card.get("financials", {})
    matched: list[dict] = []

    # BKR-FIN-01: 분기 모멘텀 + 미반영 = 저평가 (성장률은 DART, 보조로 yfinance 마진)
    op_margin = fin.get("op_margin") if isinstance(fin, dict) else None
    margin = q.get("profit_margin")
    if op_margin is not None or margin is not None:
        matched.append({
            "id": "BKR-FIN-01",
            "auto": True,
            "note": f"op_margin={op_margin}, profit_margin={margin} (성장률은 DART 분기 연동 시 정밀)",
        })

    # BKR-STYLE-01: 종목소개 디스클레이머 (항상 부착)
    matched.append({"id": "BKR-STYLE-01", "auto": True,
                    "note": "본 카드는 투자의견이 아닌 종목 소개입니다."})

    pending = [r["id"] for r in rb["rules"]
               if r.get("codeable") in ("no", "partial")]
    card["rulebook"] = {
        "version": rb.get("version"),
        "auto_matched": matched,                 # 코드가 평가한 룰
        "rag_pending": pending,                  # RAG/뉴스 정성 판정 대기 룰
        "frame": rb.get("analysis_frame"),
    }
    return card


# ─────────────────────────────────────────────────────────────────────
def main(argv: list[str]) -> int:
    # Windows 콘솔(cp949)에서 한글·기호(—) 출력 시 UnicodeEncodeError 방지
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if not argv:
        print("usage: python advisor_data.py <종목명|티커> [--us]")
        return 1
    us = "--us" in argv
    name = next(a for a in argv if not a.startswith("--"))
    card = build_stock_card(name, us=us)
    card = apply_rulebook(card)
    print(json.dumps(card, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
