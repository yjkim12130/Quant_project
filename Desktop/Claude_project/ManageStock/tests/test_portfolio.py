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


def _sample_metrics():
    holdings = _sample_holdings()
    return portfolio.compute_holding_metrics(holdings, {"005930.KS": 77000.0, "QQQ": 440.0}, fx_rate=1300.0)


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


def test_aggregate_by_category_weight_and_return():
    df = portfolio.aggregate_by_category(_sample_metrics())
    total_value = 770000.0 + 5 * 440.0 * 1300.0
    krw_row = df[df["category"] == "한국 개별주"].iloc[0]
    assert krw_row["weight_pct"] == pytest.approx(770000.0 / total_value * 100)
    assert krw_row["return_pct"] == pytest.approx(10.0)


def test_aggregate_by_category_sorted_by_value_desc():
    df = portfolio.aggregate_by_category(_sample_metrics())
    assert list(df["value_krw"]) == sorted(df["value_krw"], reverse=True)


def test_aggregate_by_category_empty_input_does_not_crash():
    empty = _sample_metrics().iloc[0:0]
    df = portfolio.aggregate_by_category(empty)
    assert len(df) == 0


def test_compute_totals():
    totals = portfolio.compute_totals(_sample_metrics())
    expected_value = 770000.0 + 5 * 440.0 * 1300.0
    expected_cost = 700000.0 + 5 * 400.0 * 1300.0
    assert totals["total_value_krw"] == pytest.approx(expected_value)
    assert totals["total_cost_krw"] == pytest.approx(expected_cost)
    assert totals["total_pnl_krw"] == pytest.approx(expected_value - expected_cost)
    assert totals["total_return_pct"] == pytest.approx(10.0)


def test_compute_totals_empty_input_returns_zeros():
    empty = _sample_metrics().iloc[0:0]
    totals = portfolio.compute_totals(empty)
    assert totals["total_value_krw"] == 0.0
    assert totals["total_return_pct"] == 0.0
