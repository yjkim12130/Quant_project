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


def test_load_history_returns_empty_template_when_missing(tmp_path):
    path = str(tmp_path / "history.csv")
    df = data_io.load_history(path=path)
    assert list(df.columns) == data_io.HISTORY_COLUMNS
    assert len(df) == 0


def test_append_snapshot_creates_rows(tmp_path):
    path = str(tmp_path / "history.csv")
    data_io.append_snapshot("2026-08-16", {"한국 개별주": 700000.0, "TOTAL": 700000.0}, path=path)
    df = data_io.load_history(path=path)
    assert len(df) == 2
    assert set(df["category"]) == {"한국 개별주", "TOTAL"}


def test_append_snapshot_overwrites_same_date(tmp_path):
    path = str(tmp_path / "history.csv")
    data_io.append_snapshot("2026-08-16", {"TOTAL": 100.0}, path=path)
    data_io.append_snapshot("2026-08-16", {"TOTAL": 200.0}, path=path)
    df = data_io.load_history(path=path)
    assert len(df) == 1
    assert df.iloc[0]["value_krw"] == 200.0


def test_append_snapshot_keeps_previous_dates(tmp_path):
    path = str(tmp_path / "history.csv")
    data_io.append_snapshot("2026-08-15", {"TOTAL": 100.0}, path=path)
    data_io.append_snapshot("2026-08-16", {"TOTAL": 110.0}, path=path)
    df = data_io.load_history(path=path)
    assert len(df) == 2
    assert set(df["date"]) == {"2026-08-15", "2026-08-16"}
