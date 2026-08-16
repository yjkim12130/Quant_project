import pandas as pd
import data_io


def test_load_holdings_returns_empty_template_when_file_missing(tmp_path):
    path = str(tmp_path / "holdings.csv")
    df = data_io.load_holdings(path=path)
    assert list(df.columns) == data_io.HOLDINGS_COLUMNS
    assert len(df) == 0


def test_save_and_load_holdings_roundtrip(tmp_path):
    path = str(tmp_path / "holdings.csv")
    df = pd.DataFrame([
        {"ticker": "005930.KS", "name": "삼성전자", "category": "한국 개별주",
         "currency": "KRW", "quantity": 10, "avg_price": 70000.0, "beta": 1.0},
    ], columns=data_io.HOLDINGS_COLUMNS)
    data_io.save_holdings(df, path=path)
    loaded = data_io.load_holdings(path=path)
    assert loaded.iloc[0]["ticker"] == "005930.KS"
    assert loaded.iloc[0]["quantity"] == 10


def test_save_holdings_creates_parent_directory(tmp_path):
    path = str(tmp_path / "nested" / "holdings.csv")
    df = pd.DataFrame(columns=data_io.HOLDINGS_COLUMNS)
    data_io.save_holdings(df, path=path)
    assert (tmp_path / "nested" / "holdings.csv").exists()


def test_infer_currency_detects_korean_suffix():
    assert data_io.infer_currency("005930.KS") == "KRW"
    assert data_io.infer_currency("069500.KQ") == "KRW"


def test_infer_currency_defaults_to_usd():
    assert data_io.infer_currency("QQQ") == "USD"
    assert data_io.infer_currency("NVDA") == "USD"
