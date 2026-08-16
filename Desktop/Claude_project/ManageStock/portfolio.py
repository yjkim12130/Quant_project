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
