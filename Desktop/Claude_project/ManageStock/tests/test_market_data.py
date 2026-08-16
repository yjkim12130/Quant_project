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
