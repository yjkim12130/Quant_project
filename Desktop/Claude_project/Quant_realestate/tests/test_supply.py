import sqlite3
from unittest.mock import patch, MagicMock

from ingest.db import SCHEMA
from ingest.fetch_supply import (
    normalize_presale_rows, COLUMN_MAP, match_region_code, fetch_raw_presale,
    parse_sigungu_from_address,
)

RAW_SAMPLE = [
    {"HOUSE_NM": "테스트아파트", "MVN_PREARNGE_YM": "202612", "TOT_SUPLY_HSHLDCO": "850",
     "HSSPLY_ADRES": "서울특별시 강남구 역삼동 123-4"},
]


def test_normalize_presale_rows_maps_known_columns():
    df = normalize_presale_rows(RAW_SAMPLE)
    assert list(df.columns) == ["project_name", "expected_ym", "total_units", "region_hint"]
    assert df.iloc[0]["project_name"] == "테스트아파트"
    assert df.iloc[0]["expected_ym"] == "202612"
    assert df.iloc[0]["total_units"] == 850
    assert df.iloc[0]["region_hint"] == "강남구"


def test_column_map_has_expected_keys():
    assert set(COLUMN_MAP) == {"project_name", "expected_ym", "total_units", "region_hint"}


def test_fetch_raw_presale_paginates_odcloud_flat_response():
    """odcloud 응답은 {"data": [...], "totalCount": N} 평평한 구조다 (옛 apis.data.go.kr의
    response.body.items.item 중첩 구조가 아님 — 2026-08-16 실제 엔드포인트 교체 후 확인).
    totalCount보다 적게 모였으면 다음 페이지를 계속 가져와야 한다."""
    page1 = MagicMock(status_code=200)
    page1.json.return_value = {"data": [{"HOUSE_NM": "A"}], "totalCount": 2, "page": 1, "perPage": 1}
    page2 = MagicMock(status_code=200)
    page2.json.return_value = {"data": [{"HOUSE_NM": "B"}], "totalCount": 2, "page": 2, "perPage": 1}

    with patch("ingest.fetch_supply.requests.get", side_effect=[page1, page2]) as mock_get:
        rows = fetch_raw_presale("dummy-key", per_page=1)

    assert rows == [{"HOUSE_NM": "A"}, {"HOUSE_NM": "B"}]
    assert mock_get.call_count == 2
    first_params = mock_get.call_args_list[0].kwargs["params"]
    assert first_params == {"serviceKey": "dummy-key", "page": 1, "perPage": 1}


def test_fetch_raw_presale_stops_on_empty_data():
    empty = MagicMock(status_code=200)
    empty.json.return_value = {"data": [], "totalCount": 0, "page": 1, "perPage": 1000}

    with patch("ingest.fetch_supply.requests.get", return_value=empty):
        rows = fetch_raw_presale("dummy-key")

    assert rows == []


def test_normalize_presale_rows_drops_nan_date_not_string_nan():
    """Fix #1: NaN dates must be dropped, not converted to string 'nan'."""
    raw = [
        {"HOUSE_NM": "정상아파트", "MVN_PREARNGE_YM": "202612", "TOT_SUPLY_HSHLDCO": "100",
         "HSSPLY_ADRES": "서울특별시 강남구 역삼동 123-4"},
        {"HOUSE_NM": "문제아파트", "MVN_PREARNGE_YM": None, "TOT_SUPLY_HSHLDCO": "200",
         "HSSPLY_ADRES": "서울특별시 강남구 역삼동 123-4"},
    ]
    df = normalize_presale_rows(raw)
    # After normalization, only the row with valid date should remain (row with None should be dropped)
    assert len(df) == 1
    assert df.iloc[0]["project_name"] == "정상아파트"
    assert df.iloc[0]["expected_ym"] == "202612"
    # Verify the "nan" string doesn't exist in the dataframe
    assert not (df["expected_ym"] == "nan").any()


def test_parse_sigungu_from_address_city_with_gu():
    """구가 설치된 시(수원/성남/안양/용인 등)는 '시 구' 결합형으로 반환해야 regions.yaml과 맞는다."""
    assert parse_sigungu_from_address("경기도 성남시 분당구 삼평동 123") == "성남시 분당구"
    assert parse_sigungu_from_address("경기도 수원시 영통구 이의동 45") == "수원시 영통구"


def test_parse_sigungu_from_address_seoul_gu():
    assert parse_sigungu_from_address("서울특별시 서대문구 홍은동 355번지 일원") == "서대문구"


def test_parse_sigungu_from_address_city_without_gu():
    """구 없는 시(과천/오산/시흥 등)는 시 단독으로 반환."""
    assert parse_sigungu_from_address("경기도 과천시 별양동 1") == "과천시"


def test_parse_sigungu_from_address_out_of_scope_city_returns_unmatched_name():
    """분석 대상 밖 지역도 파싱 자체는 되지만(진주시), match_region_code 단계에서 걸러진다."""
    assert parse_sigungu_from_address("경상남도 진주시 이현동 10-1번지 외 13필지") == "진주시"


def test_parse_sigungu_from_address_malformed_returns_none():
    assert parse_sigungu_from_address("") is None
    assert parse_sigungu_from_address(None) is None
    assert parse_sigungu_from_address("단일토큰") is None


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
