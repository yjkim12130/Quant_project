import streamlit as st
import yfinance as yf


def _fetch_single_price(ticker):
    try:
        price = yf.Ticker(ticker).fast_info["last_price"]
        return float(price) if price is not None else None
    except Exception:
        return None


def fetch_prices_uncached(tickers):
    """캐시 없는 순수 버전 — 테스트에서 직접 호출."""
    prices, failed = {}, []
    for ticker in tickers:
        price = _fetch_single_price(ticker)
        if price is None:
            failed.append(ticker)
        else:
            prices[ticker] = price
    return prices, failed


@st.cache_data(ttl=600)
def fetch_prices(tickers):
    """app.py에서 호출하는 캐시 버전. tickers는 리스트(해시 가능하도록 Streamlit이 내부 처리)."""
    return fetch_prices_uncached(tickers)


def _fetch_fx_rate_uncached():
    try:
        price = yf.Ticker("KRW=X").fast_info["last_price"]
        return float(price) if price is not None else None
    except Exception:
        return None


@st.cache_data(ttl=600)
def fetch_fx_rate():
    return _fetch_fx_rate_uncached()


def resolve_fx_rate(fetched_rate, last_known_rate):
    """fetched_rate: fetch_fx_rate()의 이번 호출 결과.
    last_known_rate: 이전에 성공적으로 조회된 마지막 환율(세션에 보관된 값).
    returns: (사용할 환율, 이번 조회가 실패해서 예전 값을 쓰는지 여부)
    """
    if fetched_rate is not None:
        return fetched_rate, False
    return last_known_rate, True
