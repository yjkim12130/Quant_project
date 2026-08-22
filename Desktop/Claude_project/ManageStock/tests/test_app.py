from unittest.mock import patch

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import data_io


def _split_ownership_holdings():
    """같은 TSLA를 남편(3주 @200) / 아내(2주 @250)가 따로 보유."""
    return pd.DataFrame([
        {"ticker": "TSLA", "name": "테슬라", "category": "미국 개별주", "currency": "USD",
         "quantity": 3, "avg_price": 200.0, "beta": 1.0, "owner": "남편"},
        {"ticker": "TSLA", "name": "테슬라", "category": "미국 개별주", "currency": "USD",
         "quantity": 2, "avg_price": 250.0, "beta": 1.0, "owner": "아내"},
    ], columns=data_io.HOLDINGS_COLUMNS)


def _synthetic_bars(bars, half_range):
    """종가 100 고정, 고저폭 일정 → ATR% = 2*half_range/100 으로 창 길이와 무관하게 확정적."""
    return pd.DataFrame(
        [(100.0 + half_range, 100.0 - half_range, 100.0)] * bars,
        columns=["High", "Low", "Close"],
    )


@pytest.fixture
def app():
    """yfinance 네트워크 호출과 실제 data/*.csv 쓰기를 차단한 채 app.py를 실행한다."""
    histories = {
        "QQQM": _synthetic_bars(200, half_range=1.0),  # 기준 종목
        "TSLA": _synthetic_bars(200, half_range=2.0),  # 기준의 정확히 2배 변동성
    }
    with patch("market_data.fetch_ohlc_history", return_value=histories), \
         patch("market_data.fetch_prices", return_value=({"TSLA": 300.0}, [])), \
         patch("market_data.fetch_fx_rate", return_value=1300.0), \
         patch("data_io.load_holdings", return_value=_split_ownership_holdings()), \
         patch("data_io.append_snapshot"), \
         patch("data_io.load_history", return_value=pd.DataFrame(columns=data_io.HISTORY_COLUMNS)), \
         patch("data_io.load_category_colors", return_value={}):
        yield AppTest.from_file("app.py", default_timeout=60).run()


def _merged_frame(app):
    for element in app.dataframe:
        if "owners" in list(element.value.columns):
            return element.value
    raise AssertionError("합산 표(owners 컬럼을 가진 dataframe)를 찾지 못했습니다")


def test_app_runs_without_exception(app):
    assert not app.exception


def test_app_exposes_merge_tab(app):
    assert "합산 보기" in [tab.label for tab in app.tabs]


def test_merge_tab_renders_one_row_per_ticker(app):
    assert len(_merged_frame(app)) == 1


def test_merge_tab_shows_combined_quantity_and_weighted_avg_price(app):
    row = _merged_frame(app).iloc[0]
    assert row["quantity"] == pytest.approx(5.0)
    assert row["avg_price"] == pytest.approx(220.0)
    assert row["owners"] == "남편, 아내"


def test_management_tab_offers_owner_selector(app):
    assert "소유자" in [selectbox.label for selectbox in app.selectbox]


def test_owner_selector_lists_default_owners(app):
    owner_selectbox = next(sb for sb in app.selectbox if sb.label == "소유자")
    assert "남편" in owner_selectbox.options and "아내" in owner_selectbox.options


def test_merge_table_exposes_atr_beta(app):
    assert "atr_beta" in list(_merged_frame(app).columns)


def test_atr_beta_reflects_relative_volatility_against_benchmark(app):
    """TSLA 합성 일봉은 기준(QQQM)의 정확히 2배 변동폭으로 만들었다."""
    assert _merged_frame(app).iloc[0]["atr_beta"] == pytest.approx(2.0)
