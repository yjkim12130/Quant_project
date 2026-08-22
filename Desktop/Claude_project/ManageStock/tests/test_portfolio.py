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


# --- merge_by_ticker: 계좌/부부 분리 기록을 종목 단위로 합산 ---

def _split_ownership_holdings():
    """같은 TSLA를 남편(3주 @200) / 아내(2주 @250)가 따로 보유."""
    return pd.DataFrame([
        {"ticker": "TSLA", "name": "테슬라", "category": "미국 개별주", "currency": "USD",
         "quantity": 3, "avg_price": 200.0, "beta": 1.0, "owner": "남편"},
        {"ticker": "TSLA", "name": "테슬라", "category": "미국 개별주", "currency": "USD",
         "quantity": 2, "avg_price": 250.0, "beta": 1.0, "owner": "아내"},
        {"ticker": "005930.KS", "name": "삼성전자", "category": "한국 개별주", "currency": "KRW",
         "quantity": 10, "avg_price": 70000.0, "beta": 1.0, "owner": "남편"},
    ])


def _split_ownership_metrics():
    return portfolio.compute_holding_metrics(
        _split_ownership_holdings(),
        {"TSLA": 300.0, "005930.KS": 77000.0},
        fx_rate=1300.0,
    )


def _merged_row(metrics_df, ticker):
    merged = portfolio.merge_by_ticker(metrics_df)
    return merged[merged["ticker"] == ticker].iloc[0]


def test_merge_by_ticker_sums_quantity():
    row = _merged_row(_split_ownership_metrics(), "TSLA")
    assert row["quantity"] == pytest.approx(5.0)


def test_merge_by_ticker_uses_quantity_weighted_average_price():
    """(3*200 + 2*250) / 5 = 220 — 단순평균 225가 아니다."""
    row = _merged_row(_split_ownership_metrics(), "TSLA")
    assert row["avg_price"] == pytest.approx(220.0)


def test_merge_by_ticker_sums_krw_amounts():
    row = _merged_row(_split_ownership_metrics(), "TSLA")
    assert row["value_krw"] == pytest.approx(5 * 300.0 * 1300.0)
    assert row["cost_krw"] == pytest.approx((3 * 200.0 + 2 * 250.0) * 1300.0)
    assert row["pnl_krw"] == pytest.approx(row["value_krw"] - row["cost_krw"])


def test_merge_by_ticker_return_pct_matches_weighted_average_price():
    row = _merged_row(_split_ownership_metrics(), "TSLA")
    assert row["return_pct"] == pytest.approx((300.0 / 220.0 - 1) * 100)


def test_merge_by_ticker_lists_owners_in_order():
    row = _merged_row(_split_ownership_metrics(), "TSLA")
    assert row["owners"] == "남편, 아내"


def test_merge_by_ticker_keeps_current_price_and_beta():
    row = _merged_row(_split_ownership_metrics(), "TSLA")
    assert row["current_price"] == pytest.approx(300.0)
    assert row["beta"] == pytest.approx(1.0)


def test_merge_by_ticker_single_owner_row_passes_through():
    row = _merged_row(_split_ownership_metrics(), "005930.KS")
    assert row["quantity"] == pytest.approx(10.0)
    assert row["avg_price"] == pytest.approx(70000.0)
    assert row["owners"] == "남편"


def test_merge_by_ticker_collapses_to_one_row_per_ticker():
    merged = portfolio.merge_by_ticker(_split_ownership_metrics())
    assert len(merged) == 2
    assert list(merged["ticker"]).count("TSLA") == 1


def test_merge_by_ticker_sorted_by_value_desc():
    merged = portfolio.merge_by_ticker(_split_ownership_metrics())
    assert list(merged["value_krw"]) == sorted(merged["value_krw"], reverse=True)


def test_merge_by_ticker_separates_same_ticker_with_different_currency():
    """통화가 섞이면 평단가를 합칠 수 없으므로 행을 나눠야 한다."""
    holdings = pd.DataFrame([
        {"ticker": "TSLA", "name": "테슬라", "category": "미국 개별주", "currency": "USD",
         "quantity": 3, "avg_price": 200.0, "beta": 1.0, "owner": "남편"},
        {"ticker": "TSLA", "name": "테슬라", "category": "미국 개별주", "currency": "KRW",
         "quantity": 2, "avg_price": 260000.0, "beta": 1.0, "owner": "아내"},
    ])
    metrics = portfolio.compute_holding_metrics(holdings, {"TSLA": 300.0}, fx_rate=1300.0)
    merged = portfolio.merge_by_ticker(metrics)
    assert len(merged) == 2
    assert set(merged["currency"]) == {"USD", "KRW"}


def test_merge_by_ticker_joins_differing_categories():
    holdings = _split_ownership_holdings()
    holdings.loc[1, "category"] = "미국 성장주"
    metrics = portfolio.compute_holding_metrics(
        holdings, {"TSLA": 300.0, "005930.KS": 77000.0}, fx_rate=1300.0
    )
    row = _merged_row(metrics, "TSLA")
    assert row["category"] == "미국 개별주, 미국 성장주"


def test_merge_by_ticker_empty_input_does_not_crash():
    empty = _split_ownership_metrics().iloc[0:0]
    merged = portfolio.merge_by_ticker(empty)
    assert len(merged) == 0


def test_merge_by_ticker_zero_quantity_does_not_divide_by_zero():
    holdings = pd.DataFrame([
        {"ticker": "TSLA", "name": "테슬라", "category": "미국 개별주", "currency": "USD",
         "quantity": 0, "avg_price": 200.0, "beta": 1.0, "owner": "남편"},
    ])
    metrics = portfolio.compute_holding_metrics(holdings, {"TSLA": 300.0}, fx_rate=1300.0)
    row = _merged_row(metrics, "TSLA")
    assert row["avg_price"] == pytest.approx(0.0)
    assert row["return_pct"] == pytest.approx(0.0)


# --- atr_beta 전파 ---

def test_compute_holding_metrics_maps_atr_beta():
    df = portfolio.compute_holding_metrics(
        _sample_holdings(), {"005930.KS": 77000.0, "QQQ": 440.0}, fx_rate=1300.0,
        atr_betas={"QQQ": 1.01},
    )
    assert df[df["ticker"] == "QQQ"].iloc[0]["atr_beta"] == pytest.approx(1.01)


def test_compute_holding_metrics_atr_beta_is_nan_when_not_computed():
    """조회 실패·상장 3개월 미만이면 값이 없어야 한다(0이 아니라 NaN)."""
    df = portfolio.compute_holding_metrics(
        _sample_holdings(), {"005930.KS": 77000.0, "QQQ": 440.0}, fx_rate=1300.0,
        atr_betas={"QQQ": 1.01},
    )
    assert pd.isna(df[df["ticker"] == "005930.KS"].iloc[0]["atr_beta"])


def test_compute_holding_metrics_atr_beta_defaults_to_nan_without_argument():
    df = portfolio.compute_holding_metrics(
        _sample_holdings(), {"005930.KS": 77000.0, "QQQ": 440.0}, fx_rate=1300.0
    )
    assert df["atr_beta"].isna().all()


def test_merge_by_ticker_carries_atr_beta():
    """atr_beta는 티커 단위 값이라 부부 합산 후에도 그대로 유지돼야 한다."""
    metrics = portfolio.compute_holding_metrics(
        _split_ownership_holdings(), {"TSLA": 300.0, "005930.KS": 77000.0}, fx_rate=1300.0,
        atr_betas={"TSLA": 2.48},
    )
    assert _merged_row(metrics, "TSLA")["atr_beta"] == pytest.approx(2.48)
