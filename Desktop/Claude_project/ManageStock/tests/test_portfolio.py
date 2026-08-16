import pandas as pd
import pytest
import portfolio


def _sample_holdings():
    return pd.DataFrame([
        {"ticker": "005930.KS", "name": "삼성전자", "category": "한국 개별주",
         "currency": "KRW", "quantity": 10, "avg_price": 70000.0, "beta": 1.0},
        {"ticker": "QQQ", "name": "QQQ", "category": "미국 지수 ETF",
         "currency": "USD", "quantity": 5, "avg_price": 400.0, "beta": 1.0},
    ])


def test_compute_holding_metrics_krw_holding():
    df = portfolio.compute_holding_metrics(_sample_holdings(), {"005930.KS": 77000.0, "QQQ": 440.0}, fx_rate=1300.0)
    row = df[df["ticker"] == "005930.KS"].iloc[0]
    assert row["value_krw"] == pytest.approx(770000.0)
    assert row["cost_krw"] == pytest.approx(700000.0)
    assert row["pnl_krw"] == pytest.approx(70000.0)
    assert row["return_pct"] == pytest.approx(10.0)


def test_compute_holding_metrics_usd_holding_applies_fx_both_sides():
    df = portfolio.compute_holding_metrics(_sample_holdings(), {"005930.KS": 77000.0, "QQQ": 440.0}, fx_rate=1300.0)
    row = df[df["ticker"] == "QQQ"].iloc[0]
    assert row["value_krw"] == pytest.approx(5 * 440.0 * 1300.0)
    assert row["cost_krw"] == pytest.approx(5 * 400.0 * 1300.0)
    assert row["return_pct"] == pytest.approx(10.0)  # 환율 상쇄, 달러 기준 가격변동률과 동일


def test_compute_holding_metrics_missing_price_yields_nan():
    df = portfolio.compute_holding_metrics(_sample_holdings(), {"005930.KS": 77000.0}, fx_rate=1300.0)
    row = df[df["ticker"] == "QQQ"].iloc[0]
    assert pd.isna(row["current_price"])
    assert pd.isna(row["value_krw"])
