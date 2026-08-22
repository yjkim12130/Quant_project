import pandas as pd

import market_data


class _FakeFastInfo(dict):
    pass


class FakeTicker:
    def __init__(self, ticker, price_map, fail_set):
        self._ticker = ticker
        self._price_map = price_map
        self._fail_set = fail_set

    @property
    def fast_info(self):
        if self._ticker in self._fail_set:
            raise RuntimeError("network error")
        return _FakeFastInfo(last_price=self._price_map[self._ticker])


def test_fetch_prices_uncached_success(monkeypatch):
    price_map = {"QQQ": 440.0, "005930.KS": 77000.0}
    monkeypatch.setattr(market_data.yf, "Ticker", lambda t: FakeTicker(t, price_map, set()))
    prices, failed = market_data.fetch_prices_uncached(["QQQ", "005930.KS"])
    assert prices == {"QQQ": 440.0, "005930.KS": 77000.0}
    assert failed == []


def test_fetch_prices_uncached_partial_failure(monkeypatch):
    price_map = {"QQQ": 440.0}
    monkeypatch.setattr(market_data.yf, "Ticker", lambda t: FakeTicker(t, price_map, {"BADTICKER"}))
    prices, failed = market_data.fetch_prices_uncached(["QQQ", "BADTICKER"])
    assert prices == {"QQQ": 440.0}
    assert failed == ["BADTICKER"]


def test_resolve_fx_rate_uses_fetched_value():
    rate, is_stale = market_data.resolve_fx_rate(1320.0, 1300.0)
    assert rate == 1320.0
    assert is_stale is False


def test_resolve_fx_rate_falls_back_when_fetch_fails():
    rate, is_stale = market_data.resolve_fx_rate(None, 1300.0)
    assert rate == 1300.0
    assert is_stale is True


def test_resolve_fx_rate_returns_none_when_never_fetched():
    rate, is_stale = market_data.resolve_fx_rate(None, None)
    assert rate is None
    assert is_stale is True


class FakeHistoryTicker:
    """history()를 가진 가짜 Ticker. history_map에 없으면 예외, None이면 빈 프레임."""

    def __init__(self, ticker, history_map):
        self._ticker = ticker
        self._history_map = history_map

    def history(self, period=None, auto_adjust=None):
        if self._ticker not in self._history_map:
            raise RuntimeError("network error")
        frame = self._history_map[self._ticker]
        return pd.DataFrame(columns=["High", "Low", "Close"]) if frame is None else frame


def _bars(n):
    return pd.DataFrame(
        [(101.0, 99.0, 100.0)] * n, columns=["High", "Low", "Close"]
    )


def test_fetch_ohlc_history_uncached_returns_frame_per_ticker(monkeypatch):
    history_map = {"QQQM": _bars(200), "TSLA": _bars(150)}
    monkeypatch.setattr(market_data.yf, "Ticker", lambda t: FakeHistoryTicker(t, history_map))
    result = market_data.fetch_ohlc_history_uncached(["QQQM", "TSLA"])
    assert set(result) == {"QQQM", "TSLA"}
    assert len(result["TSLA"]) == 150


def test_fetch_ohlc_history_uncached_omits_ticker_that_raises(monkeypatch):
    history_map = {"QQQM": _bars(200)}
    monkeypatch.setattr(market_data.yf, "Ticker", lambda t: FakeHistoryTicker(t, history_map))
    result = market_data.fetch_ohlc_history_uncached(["QQQM", "BADTICKER"])
    assert set(result) == {"QQQM"}


def test_fetch_ohlc_history_uncached_omits_empty_history(monkeypatch):
    history_map = {"QQQM": _bars(200), "0190M0.KS": None}
    monkeypatch.setattr(market_data.yf, "Ticker", lambda t: FakeHistoryTicker(t, history_map))
    result = market_data.fetch_ohlc_history_uncached(["QQQM", "0190M0.KS"])
    assert set(result) == {"QQQM"}
