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


def test_drop_incomplete_holdings_removes_fully_blank_row():
    df = pd.DataFrame([
        {"ticker": "QQQ", "name": "QQQ", "category": "미국 지수 ETF",
         "currency": "USD", "quantity": 5, "avg_price": 400.0, "beta": 1.0},
        {"ticker": None, "name": None, "category": None,
         "currency": None, "quantity": None, "avg_price": None, "beta": None},
    ], columns=data_io.HOLDINGS_COLUMNS)
    cleaned, dropped = data_io.drop_incomplete_holdings(df)
    assert len(cleaned) == 1
    assert dropped == 1
    assert cleaned.iloc[0]["ticker"] == "QQQ"


def test_drop_incomplete_holdings_removes_row_missing_one_required_field():
    df = pd.DataFrame([
        {"ticker": "QQQ", "name": "QQQ", "category": "",
         "currency": "USD", "quantity": 5, "avg_price": 400.0, "beta": 1.0},
    ], columns=data_io.HOLDINGS_COLUMNS)
    cleaned, dropped = data_io.drop_incomplete_holdings(df)
    assert len(cleaned) == 0
    assert dropped == 1


def test_load_category_colors_returns_empty_dict_when_missing(tmp_path):
    path = str(tmp_path / "category_colors.csv")
    colors = data_io.load_category_colors(path=path)
    assert colors == {}


def test_save_and_load_category_colors_roundtrip(tmp_path):
    path = str(tmp_path / "category_colors.csv")
    data_io.save_category_colors({"한국 개별주": "#ff0000", "암호화폐": "#00ff00"}, path=path)
    colors = data_io.load_category_colors(path=path)
    assert colors == {"한국 개별주": "#ff0000", "암호화폐": "#00ff00"}


def test_save_category_colors_overwrites_previous_file(tmp_path):
    path = str(tmp_path / "category_colors.csv")
    data_io.save_category_colors({"한국 개별주": "#ff0000"}, path=path)
    data_io.save_category_colors({"암호화폐": "#00ff00"}, path=path)
    colors = data_io.load_category_colors(path=path)
    assert colors == {"암호화폐": "#00ff00"}


def test_drop_incomplete_holdings_keeps_all_valid_rows():
    df = pd.DataFrame([
        {"ticker": "QQQ", "name": "QQQ", "category": "미국 지수 ETF",
         "currency": "USD", "quantity": 5, "avg_price": 400.0, "beta": 1.0},
        {"ticker": "005930.KS", "name": "삼성전자", "category": "한국 개별주",
         "currency": "KRW", "quantity": 10, "avg_price": 70000.0, "beta": 1.0},
    ], columns=data_io.HOLDINGS_COLUMNS)
    cleaned, dropped = data_io.drop_incomplete_holdings(df)
    assert len(cleaned) == 2
    assert dropped == 0


# --- owner 컬럼 (부부/계좌 분리 기록 → 합산 보기) ---

def _legacy_holdings_csv(tmp_path):
    """owner 컬럼이 없던 시절의 CSV. 기존 사용자 파일 및 예전 백업본과 동일한 형태."""
    path = str(tmp_path / "holdings.csv")
    legacy_columns = ["ticker", "name", "category", "currency", "quantity", "avg_price", "beta"]
    pd.DataFrame([
        {"ticker": "TSLA", "name": "테슬라", "category": "미국 개별주",
         "currency": "USD", "quantity": 3, "avg_price": 200.0, "beta": 1.0},
    ], columns=legacy_columns).to_csv(path, index=False)
    return path


def test_holdings_columns_includes_owner():
    assert "owner" in data_io.HOLDINGS_COLUMNS


def test_load_holdings_backfills_owner_for_legacy_csv(tmp_path):
    df = data_io.load_holdings(path=_legacy_holdings_csv(tmp_path))
    assert list(df.columns) == data_io.HOLDINGS_COLUMNS
    assert df.iloc[0]["owner"] == data_io.DEFAULT_OWNER


def test_load_holdings_preserves_existing_owner(tmp_path):
    path = str(tmp_path / "holdings.csv")
    pd.DataFrame([
        {"ticker": "TSLA", "name": "테슬라", "category": "미국 개별주", "currency": "USD",
         "quantity": 3, "avg_price": 200.0, "beta": 1.0, "owner": "남편"},
    ], columns=data_io.HOLDINGS_COLUMNS).to_csv(path, index=False)
    df = data_io.load_holdings(path=path)
    assert df.iloc[0]["owner"] == "남편"


def test_load_holdings_fills_blank_owner_with_default(tmp_path):
    """owner 컬럼은 있지만 값이 비어있는 행(에디터에서 새 행 추가 후 미입력)도 기본값으로 채운다."""
    path = str(tmp_path / "holdings.csv")
    pd.DataFrame([
        {"ticker": "TSLA", "name": "테슬라", "category": "미국 개별주", "currency": "USD",
         "quantity": 3, "avg_price": 200.0, "beta": 1.0, "owner": ""},
    ], columns=data_io.HOLDINGS_COLUMNS).to_csv(path, index=False)
    df = data_io.load_holdings(path=path)
    assert df.iloc[0]["owner"] == data_io.DEFAULT_OWNER


def test_save_holdings_accepts_dataframe_without_owner(tmp_path):
    """예전 백업 CSV를 복원할 때 owner가 없어도 KeyError 없이 저장돼야 한다."""
    path = str(tmp_path / "holdings.csv")
    legacy_columns = ["ticker", "name", "category", "currency", "quantity", "avg_price", "beta"]
    df = pd.DataFrame([
        {"ticker": "TSLA", "name": "테슬라", "category": "미국 개별주",
         "currency": "USD", "quantity": 3, "avg_price": 200.0, "beta": 1.0},
    ], columns=legacy_columns)
    data_io.save_holdings(df, path=path)
    reloaded = data_io.load_holdings(path=path)
    assert reloaded.iloc[0]["owner"] == data_io.DEFAULT_OWNER


def test_missing_required_columns_accepts_legacy_backup_without_owner():
    """owner 도입 전에 받아둔 백업 CSV도 복원 가능해야 한다."""
    legacy_columns = ["ticker", "name", "category", "currency", "quantity", "avg_price", "beta"]
    df = pd.DataFrame(columns=legacy_columns)
    assert data_io.missing_required_columns(df) == []


def test_missing_required_columns_accepts_current_schema():
    df = pd.DataFrame(columns=data_io.HOLDINGS_COLUMNS)
    assert data_io.missing_required_columns(df) == []


def test_missing_required_columns_reports_genuinely_missing_ones():
    df = pd.DataFrame(columns=["ticker", "name"])
    assert data_io.missing_required_columns(df) == ["avg_price", "beta", "category", "currency", "quantity"]
