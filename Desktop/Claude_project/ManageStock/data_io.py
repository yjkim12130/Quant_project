import os
import pandas as pd

HOLDINGS_COLUMNS = ["ticker", "name", "category", "currency", "quantity", "avg_price", "beta"]
HOLDINGS_PATH = os.path.join("data", "holdings.csv")


def load_holdings(path=HOLDINGS_PATH):
    if not os.path.exists(path):
        return pd.DataFrame(columns=HOLDINGS_COLUMNS)
    return pd.read_csv(
        path,
        dtype={"ticker": str, "name": str, "category": str, "currency": str},
    )


def save_holdings(df, path=HOLDINGS_PATH):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    df.to_csv(path, index=False, columns=HOLDINGS_COLUMNS)


def infer_currency(ticker):
    if ticker.upper().endswith((".KS", ".KQ")):
        return "KRW"
    return "USD"
