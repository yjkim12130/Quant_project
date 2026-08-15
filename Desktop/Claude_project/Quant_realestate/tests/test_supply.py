from ingest.fetch_supply import normalize_presale_rows, COLUMN_MAP

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
