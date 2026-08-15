import pandas as pd

from ingest.fetch_supply import normalize_presale_rows, COLUMN_MAP, match_region_code

RAW_SAMPLE = [
    {"HOUSE_NM": "테스트아파트", "RCRIT_PBLANC_DE": "20261201", "TOT_SUPLY_HSHLDCO": "850",
     "SUBSCRPT_AREA_CODE_NM": "서울"},
]


def test_normalize_presale_rows_maps_known_columns():
    df = normalize_presale_rows(RAW_SAMPLE)
    assert list(df.columns) == ["project_name", "expected_ym", "total_units", "region_hint"]
    assert df.iloc[0]["project_name"] == "테스트아파트"
    assert df.iloc[0]["expected_ym"] == "202612"
    assert df.iloc[0]["total_units"] == 850


def test_column_map_has_expected_keys():
    assert set(COLUMN_MAP) == {"project_name", "expected_ym", "total_units", "region_hint"}


def test_normalize_presale_rows_drops_nan_date_not_string_nan():
    """Fix #1: NaN dates must be dropped, not converted to string 'nan'."""
    raw = [
        {"HOUSE_NM": "정상아파트", "RCRIT_PBLANC_DE": "20261201", "TOT_SUPLY_HSHLDCO": "100",
         "SUBSCRPT_AREA_CODE_NM": "서울"},
        {"HOUSE_NM": "문제아파트", "RCRIT_PBLANC_DE": None, "TOT_SUPLY_HSHLDCO": "200",
         "SUBSCRPT_AREA_CODE_NM": "서울"},
    ]
    df = normalize_presale_rows(raw)
    # After normalization, only the row with valid date should remain (row with None should be dropped)
    assert len(df) == 1
    assert df.iloc[0]["project_name"] == "정상아파트"
    assert df.iloc[0]["expected_ym"] == "202612"
    # Verify the "nan" string doesn't exist in the dataframe
    assert not (df["expected_ym"] == "nan").any()


def test_match_region_code_exact_match_only():
    """Fix #2: match_region_code must do exact string matching, not substring.
    성남시 entries should NOT match a hint of just '성남' or '성남시'.
    Substring matching would incorrectly match the first 성남* entry."""
    region_rows = [
        {"code": "41131", "name": "성남시 수정구"},
        {"code": "41133", "name": "성남시 중원구"},
        {"code": "41135", "name": "성남시 분당구"},
    ]

    # Exact matches should work
    assert match_region_code("성남시 수정구", region_rows) == "41131"
    assert match_region_code("성남시 분당구", region_rows) == "41135"

    # Substring matches should NOT work (this was the bug)
    assert match_region_code("성남", region_rows) is None
    assert match_region_code("성남시", region_rows) is None
    assert match_region_code("수정구", region_rows) is None

    # Non-existent exact match should return None
    assert match_region_code("서울 강남구", region_rows) is None


def test_match_region_code_with_whitespace():
    """Exact match should handle whitespace correctly after stripping."""
    region_rows = [
        {"code": "11680", "name": "강남구"},
    ]

    # Exact match with spaces stripped
    assert match_region_code("강남구", region_rows) == "11680"
    assert match_region_code("  강남구  ", region_rows) == "11680"

    # Still no substring matching
    assert match_region_code("강남", region_rows) is None
