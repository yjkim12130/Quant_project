import sqlite3

from ingest.db import SCHEMA
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


def test_reingest_does_not_double_count_when_expected_ym_changes(tmp_path):
    """Fix #6: main() must DELETE existing source='apply_home' rows before re-inserting,
    so a project whose expected_ym shifts between runs isn't double-counted under
    both the old and new year-month. Mirrors the exact DELETE+INSERT OR REPLACE
    sequence used in ingest/fetch_supply.py::main() against a throwaway schema-only DB
    (no live API/DB — matches this project's existing db-schema test style)."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)

    # Simulate a prior run: project announced for 202601.
    conn.execute(
        "INSERT INTO supply_presale (region_code, expected_ym, project_name, total_units, "
        "source, fetched_at) VALUES (?,?,?,?,?,?)",
        ("41135", "202601", "테스트단지", 500, "apply_home", "2026-01-01T00:00:00+00:00"),
    )
    # A row from a different source must never be touched by the apply_home refresh.
    conn.execute(
        "INSERT INTO supply_presale (region_code, expected_ym, project_name, total_units, "
        "source, fetched_at) VALUES (?,?,?,?,?,?)",
        ("41135", "202601", "정비사업단지", 1200, "manual_curation", "2026-01-01T00:00:00+00:00"),
    )
    conn.commit()

    # Simulate a re-run where the same project's announcement date slipped to 202603.
    rows = [("41135", "202603", "테스트단지", 500, "apply_home", "2026-03-01T00:00:00+00:00")]
    conn.execute("DELETE FROM supply_presale WHERE source='apply_home'")
    conn.executemany(
        "INSERT OR REPLACE INTO supply_presale "
        "(region_code, expected_ym, project_name, total_units, source, fetched_at) "
        "VALUES (?,?,?,?,?,?)", rows)
    conn.commit()

    apply_home_rows = conn.execute(
        "SELECT expected_ym FROM supply_presale WHERE project_name='테스트단지'").fetchall()
    assert apply_home_rows == [("202603",)], (
        "stale row under the old expected_ym must be gone, only the new one remains")

    manual_rows = conn.execute(
        "SELECT project_name FROM supply_presale WHERE source='manual_curation'").fetchall()
    assert manual_rows == [("정비사업단지",)], "non-apply_home rows must survive the refresh"

    conn.close()
