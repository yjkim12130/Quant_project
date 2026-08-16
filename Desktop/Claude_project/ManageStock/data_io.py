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


CATEGORY_COLORS_COLUMNS = ["category", "color"]
CATEGORY_COLORS_PATH = os.path.join("data", "category_colors.csv")


def load_category_colors(path=CATEGORY_COLORS_PATH):
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path, dtype={"category": str, "color": str})
    return dict(zip(df["category"], df["color"]))


def save_category_colors(colors, path=CATEGORY_COLORS_PATH):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    df = pd.DataFrame(list(colors.items()), columns=CATEGORY_COLORS_COLUMNS)
    df.to_csv(path, index=False, columns=CATEGORY_COLORS_COLUMNS)


def drop_incomplete_holdings(df):
    """ticker/name/category 중 하나라도 비어있는 행을 제거한다.
    returns (정제된 DataFrame, 제거된 행 수)."""
    required = ["ticker", "name", "category"]
    filled = df[required].fillna("").astype(str).apply(lambda s: s.str.strip())
    valid_mask = (filled != "").all(axis=1)
    cleaned = df[valid_mask].reset_index(drop=True)
    dropped = len(df) - len(cleaned)
    return cleaned, dropped


HISTORY_COLUMNS = ["date", "category", "value_krw"]
HISTORY_PATH = os.path.join("data", "history.csv")


def load_history(path=HISTORY_PATH):
    if not os.path.exists(path):
        return pd.DataFrame(columns=HISTORY_COLUMNS)
    return pd.read_csv(path, dtype={"date": str, "category": str})


def append_snapshot(date, category_values, path=HISTORY_PATH):
    """category_values: dict[str, float] — 카테고리명(또는 'TOTAL') -> 원화환산 평가금액.
    같은 date로 재호출하면 해당 날짜 행을 덮어쓴다(하루 여러 번 실행해도 중복 누적 안 됨)."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    new_rows = pd.DataFrame(
        [{"date": date, "category": cat, "value_krw": val} for cat, val in category_values.items()],
        columns=HISTORY_COLUMNS,
    )
    existing = load_history(path)
    existing = existing[existing["date"] != date]
    combined = pd.concat([existing, new_rows], ignore_index=True)
    combined.to_csv(path, index=False, columns=HISTORY_COLUMNS)
