import numpy as np


def compute_holding_metrics(holdings_df, prices, fx_rate):
    """holdings_df: data_io.HOLDINGS_COLUMNS 형태의 DataFrame
    prices: dict[str, float] — ticker -> 현재가(해당 종목 통화 기준)
    fx_rate: float — 오늘의 KRW/USD 환율
    returns: 원본 컬럼 + current_price, value_krw, cost_krw, pnl_krw, return_pct
    가격 조회 실패(ticker가 prices에 없음)한 종목은 current_price 이하 전부 NaN이 된다.
    """
    df = holdings_df.copy()
    df["current_price"] = df["ticker"].map(prices)
    multiplier = df["currency"].map({"USD": fx_rate, "KRW": 1.0}).fillna(1.0)
    df["value_krw"] = df["quantity"] * df["current_price"] * multiplier
    df["cost_krw"] = df["quantity"] * df["avg_price"] * multiplier
    df["pnl_krw"] = df["value_krw"] - df["cost_krw"]
    df["return_pct"] = (df["current_price"] / df["avg_price"] - 1) * 100
    return df


def aggregate_by_category(metrics_df):
    grouped = metrics_df.groupby("category", as_index=False)[["value_krw", "cost_krw"]].sum()
    total_value = grouped["value_krw"].sum()
    grouped["weight_pct"] = (grouped["value_krw"] / total_value * 100) if total_value else 0.0
    grouped["return_pct"] = np.where(
        grouped["cost_krw"] != 0,
        (grouped["value_krw"] / grouped["cost_krw"] - 1) * 100,
        0.0,
    )
    return grouped.sort_values("value_krw", ascending=False).reset_index(drop=True)


def compute_totals(metrics_df):
    total_value = metrics_df["value_krw"].sum()
    total_cost = metrics_df["cost_krw"].sum()
    total_pnl = total_value - total_cost
    total_return = ((total_value / total_cost - 1) * 100) if total_cost else 0.0
    return {
        "total_value_krw": total_value,
        "total_cost_krw": total_cost,
        "total_pnl_krw": total_pnl,
        "total_return_pct": total_return,
    }
