import numpy as np
import pandas as pd


def compute_holding_metrics(holdings_df, prices, fx_rate, atr_betas=None):
    """holdings_df: data_io.HOLDINGS_COLUMNS 형태의 DataFrame
    prices: dict[str, float] — ticker -> 현재가(해당 종목 통화 기준)
    fx_rate: float — 오늘의 KRW/USD 환율
    atr_betas: dict[str, float] — ticker -> ATR 기반 상대 변동성. 계산 못 한 종목은 NaN이 된다.
    returns: 원본 컬럼 + current_price, atr_beta, value_krw, cost_krw, pnl_krw, return_pct
    가격 조회 실패(ticker가 prices에 없음)한 종목은 current_price 이하 전부 NaN이 된다.
    """
    df = holdings_df.copy()
    df["current_price"] = df["ticker"].map(prices)
    df["atr_beta"] = df["ticker"].map(atr_betas or {})
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


MERGED_COLUMNS = [
    "ticker", "name", "owners", "category", "currency", "quantity", "avg_price",
    "current_price", "value_krw", "cost_krw", "pnl_krw", "return_pct", "beta", "atr_beta",
]


def _join_unique(series):
    """등장 순서를 유지하며 중복 없이 이어붙인다."""
    return ", ".join(dict.fromkeys(series.fillna("").astype(str)))


def merge_by_ticker(metrics_df):
    """계좌/소유자가 달라 여러 행으로 기록된 같은 종목을 한 행으로 합친다.

    avg_price는 수량가중평균(해당 종목 통화 기준)이라 부부 합산 평단가가 된다.
    통화가 섞인 티커는 평단가를 합칠 수 없으므로 (ticker, currency)로 나눠 별도 행이 된다.
    """
    if metrics_df.empty:
        return pd.DataFrame(columns=MERGED_COLUMNS)

    df = metrics_df.copy()
    df["_cost_native"] = df["quantity"] * df["avg_price"]

    merged = df.groupby(["ticker", "currency"], sort=False, dropna=False).agg(
        name=("name", "first"),
        owners=("owner", _join_unique),
        category=("category", _join_unique),
        quantity=("quantity", "sum"),
        _cost_native=("_cost_native", "sum"),
        current_price=("current_price", "first"),
        value_krw=("value_krw", "sum"),
        cost_krw=("cost_krw", "sum"),
        beta=("beta", "first"),
        atr_beta=("atr_beta", "first"),
    ).reset_index()

    merged["avg_price"] = np.where(
        merged["quantity"] != 0, merged["_cost_native"] / merged["quantity"], 0.0
    )
    merged["pnl_krw"] = merged["value_krw"] - merged["cost_krw"]
    merged["return_pct"] = np.where(
        merged["cost_krw"] != 0, (merged["value_krw"] / merged["cost_krw"] - 1) * 100, 0.0
    )
    return (
        merged.sort_values("value_krw", ascending=False)
        .reset_index(drop=True)[MERGED_COLUMNS]
    )
