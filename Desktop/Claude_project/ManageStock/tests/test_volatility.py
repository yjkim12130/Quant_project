import pandas as pd
import pytest

import volatility


def _ohlc(rows):
    """rows: list of (high, low, close)"""
    return pd.DataFrame(rows, columns=["High", "Low", "Close"])


def _flat_ohlc(bars, close=100.0, half_range=1.0):
    """종가가 매일 close로 동일하고 고저폭이 일정한 봉.
    prev_close == close 이므로 TR = max(2*hr, hr, hr) = 2*hr → ATR% = 2*hr/close 로 창 길이와 무관."""
    return _ohlc([(close + half_range, close - half_range, close)] * bars)


# --- true_range ---

def test_true_range_uses_intraday_range_when_it_is_largest():
    df = _ohlc([(110, 90, 100), (105, 95, 100)])
    assert volatility.true_range(df).iloc[-1] == pytest.approx(10.0)


def test_true_range_uses_gap_from_previous_close_when_it_is_largest():
    """전일종가 100에서 갭상승한 봉: 일중폭 5보다 |고가-전일종가| 30이 크다."""
    df = _ohlc([(110, 90, 100), (130, 125, 128)])
    assert volatility.true_range(df).iloc[-1] == pytest.approx(30.0)


def test_true_range_is_undefined_for_first_bar():
    df = _ohlc([(110, 90, 100), (105, 95, 100)])
    assert pd.isna(volatility.true_range(df).iloc[0])


# --- atr_pct ---

def test_atr_pct_averages_true_range_and_divides_by_last_close():
    df = _ohlc([(110, 90, 100), (105, 95, 100), (130, 125, 128)])
    # TR = [NaN, 10, 30] → 평균 20, 최종종가 128
    assert volatility.atr_pct(df, window=2) == pytest.approx(20.0 / 128.0)


def test_atr_pct_returns_none_when_bars_insufficient_for_window():
    """창이 126이면 TR이 126개 필요하므로 최소 127봉이 있어야 한다."""
    assert volatility.atr_pct(_flat_ohlc(126), window=126) is None
    assert volatility.atr_pct(_flat_ohlc(127), window=126) is not None


def test_atr_pct_returns_none_for_empty_frame():
    assert volatility.atr_pct(_ohlc([]), window=14) is None


# --- compute_atr_betas ---

def _benchmark_with_regime_shift():
    """앞 100봉은 고저폭 1(TR=2), 뒤 100봉은 고저폭 5(TR=10).
    ATR%(63) = 10/100 = 0.10, ATR%(126) = (26*2 + 100*10)/126/100 ≈ 0.08349 로 창마다 다르다."""
    calm = [(101.0, 99.0, 100.0)] * 100
    wild = [(105.0, 95.0, 100.0)] * 100
    return _ohlc(calm + wild)


def test_compute_atr_betas_gives_benchmark_itself_one():
    histories = {"QQQM": _flat_ohlc(200, half_range=1.0)}
    result = volatility.compute_atr_betas(histories)
    assert result["QQQM"]["beta"] == pytest.approx(1.0)


def test_compute_atr_betas_scales_with_relative_volatility():
    histories = {
        "QQQM": _flat_ohlc(200, half_range=1.0),   # ATR% = 2/100
        "QLD": _flat_ohlc(200, half_range=2.0),    # ATR% = 4/100 → 2배
    }
    assert volatility.compute_atr_betas(histories)["QLD"]["beta"] == pytest.approx(2.0)


def test_compute_atr_betas_uses_target_window_when_history_is_long():
    histories = {"QQQM": _flat_ohlc(200), "TSLA": _flat_ohlc(200, half_range=3.0)}
    result = volatility.compute_atr_betas(histories)
    assert result["TSLA"]["window"] == volatility.ATR_TARGET_WINDOW
    assert result["TSLA"]["provisional"] is False


def test_compute_atr_betas_shortens_window_for_recently_listed_ticker():
    histories = {"QQQM": _flat_ohlc(200), "0190M0.KS": _flat_ohlc(70, half_range=1.0)}
    result = volatility.compute_atr_betas(histories)
    assert result["0190M0.KS"]["window"] == 69
    assert result["0190M0.KS"]["provisional"] is True


def test_compute_atr_betas_measures_benchmark_over_the_same_shortened_window():
    """신규 상장 종목을 짧은 창으로 재면 기준(QQQM)도 같은 창으로 재야 한다.
    아니면 서로 다른 시장 국면을 비교하게 된다."""
    histories = {
        "QQQM": _benchmark_with_regime_shift(),          # ATR%(63)=0.10, ATR%(126)≈0.08349
        "NEW": _flat_ohlc(64, close=100.0, half_range=5.0),  # ATR% = 10/100 = 0.10
    }
    result = volatility.compute_atr_betas(histories)
    assert result["NEW"]["window"] == 63
    assert result["NEW"]["beta"] == pytest.approx(1.0)  # 126일 창을 썼다면 약 1.198이 된다


def test_compute_atr_betas_excludes_ticker_below_min_window():
    histories = {"QQQM": _flat_ohlc(200), "TOONEW": _flat_ohlc(40)}
    assert "TOONEW" not in volatility.compute_atr_betas(histories)


def test_compute_atr_betas_returns_empty_when_benchmark_missing():
    assert volatility.compute_atr_betas({"TSLA": _flat_ohlc(200)}) == {}


def test_compute_atr_betas_returns_empty_when_benchmark_history_too_short():
    histories = {"QQQM": _flat_ohlc(40), "TSLA": _flat_ohlc(200)}
    assert volatility.compute_atr_betas(histories) == {}


def test_compute_atr_betas_returns_empty_when_benchmark_has_zero_volatility():
    """기준 종목의 변동성이 0이면 나눌 수가 없으므로 전 종목을 계산하지 않는다."""
    histories = {"QQQM": _flat_ohlc(200, half_range=0.0), "TSLA": _flat_ohlc(200)}
    assert volatility.compute_atr_betas(histories) == {}


# --- tickers_needed: 기준 종목이 보유목록에 없어도 반드시 함께 조회해야 한다 ---

def test_tickers_needed_appends_benchmark_when_absent():
    assert volatility.tickers_needed(["TSLA", "QQQ"]) == ["TSLA", "QQQ", volatility.ATR_BENCHMARK]


def test_tickers_needed_does_not_duplicate_benchmark():
    result = volatility.tickers_needed(["TSLA", volatility.ATR_BENCHMARK])
    assert result.count(volatility.ATR_BENCHMARK) == 1


def test_tickers_needed_removes_duplicate_holdings():
    """같은 종목을 부부가 따로 보유하면 티커가 중복으로 들어온다."""
    result = volatility.tickers_needed(["TSLA", "TSLA", "QQQ"])
    assert result == ["TSLA", "QQQ", volatility.ATR_BENCHMARK]


def test_beta_map_extracts_plain_ticker_to_beta_mapping():
    atr_info = {"QQQM": {"beta": 1.0, "window": 126, "provisional": False},
                "TSLA": {"beta": 2.5, "window": 69, "provisional": True}}
    assert volatility.beta_map(atr_info) == {"QQQM": 1.0, "TSLA": 2.5}


def test_beta_map_of_empty_info_is_empty():
    assert volatility.beta_map({}) == {}


def test_provisional_tickers_lists_only_shortened_windows():
    atr_info = {"QQQM": {"beta": 1.0, "window": 126, "provisional": False},
                "TSLA": {"beta": 2.5, "window": 69, "provisional": True}}
    assert volatility.provisional_tickers(atr_info) == ["TSLA"]
