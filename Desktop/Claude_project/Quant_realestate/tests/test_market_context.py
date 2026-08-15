import sqlite3
import textwrap

import numpy as np
import pandas as pd
import pytest

from scoring.market_context import asset_ratio_zscore, load_planned_transit, load_redevelopment, load_supply_by_region_year


def test_load_redevelopment_parses_yaml(tmp_path, monkeypatch):
    yaml_path = tmp_path / "manual_catalysts.yaml"
    yaml_path.write_text(textwrap.dedent("""
        redevelopment:
          - region_code: "11680"
            complex_name: "테스트 재건축"
            stage: "관리처분"
            expected_units: 1500
            expected_year: 2028
        transit_planned: []
    """), encoding="utf-8")
    monkeypatch.setattr("scoring.market_context.MANUAL_CATALYSTS_YAML", yaml_path)

    df = load_redevelopment()
    assert len(df) == 1
    assert df.iloc[0]["region_code"] == "11680"
    assert df.iloc[0]["expected_units"] == 1500


def test_load_redevelopment_empty_when_section_missing(tmp_path, monkeypatch):
    yaml_path = tmp_path / "manual_catalysts.yaml"
    yaml_path.write_text("transit_planned: []\n", encoding="utf-8")
    monkeypatch.setattr("scoring.market_context.MANUAL_CATALYSTS_YAML", yaml_path)

    df = load_redevelopment()
    assert df.empty


def test_load_supply_by_region_year_combines_presale_and_redevelopment(tmp_path, monkeypatch):
    yaml_path = tmp_path / "manual_catalysts.yaml"
    yaml_path.write_text(textwrap.dedent("""
        redevelopment:
          - region_code: "11680"
            complex_name: "테스트 재건축"
            stage: "착공"
            expected_units: 500
            expected_year: 2027
        transit_planned: []
    """), encoding="utf-8")
    monkeypatch.setattr("scoring.market_context.MANUAL_CATALYSTS_YAML", yaml_path)

    conn = sqlite3.connect(str(tmp_path / "test.db"))
    conn.execute("""
        CREATE TABLE supply_presale (
            region_code TEXT, expected_ym TEXT, project_name TEXT,
            total_units INTEGER, source TEXT, fetched_at TEXT
        )
    """)
    conn.execute(
        "INSERT INTO supply_presale VALUES ('11680', '202703', 'A단지', 300, 'apply_home', '')")
    conn.commit()

    out = load_supply_by_region_year(conn)
    row = out[(out["region_code"] == "11680") & (out["year"] == 2027)].iloc[0]
    assert row["presale_units"] == 300
    assert row["redevelopment_units"] == 500


def test_load_supply_by_region_year_handles_missing_presale_table(tmp_path, monkeypatch):
    yaml_path = tmp_path / "manual_catalysts.yaml"
    yaml_path.write_text(textwrap.dedent("""
        redevelopment:
          - region_code: "11680"
            complex_name: "테스트 재건축"
            stage: "착공"
            expected_units: 500
            expected_year: 2027
        transit_planned: []
    """), encoding="utf-8")
    monkeypatch.setattr("scoring.market_context.MANUAL_CATALYSTS_YAML", yaml_path)

    # Create DB without supply_presale table
    conn = sqlite3.connect(str(tmp_path / "test.db"))

    # Should not raise even though supply_presale table doesn't exist
    out = load_supply_by_region_year(conn)

    # Should return redevelopment data
    row = out[(out["region_code"] == "11680") & (out["year"] == 2027)].iloc[0]
    assert row["redevelopment_units"] == 500
    assert row["presale_units"] == 0


def test_load_planned_transit_parses_yaml(tmp_path, monkeypatch):
    yaml_path = tmp_path / "manual_catalysts.yaml"
    yaml_path.write_text(textwrap.dedent("""
        redevelopment: []
        transit_planned:
          - line_name: "GTX-A"
            stations: ["동탄", "판교"]
            stage: "공사중"
            expected_open_year: 2026
    """), encoding="utf-8")
    monkeypatch.setattr("scoring.market_context.MANUAL_CATALYSTS_YAML", yaml_path)

    df = load_planned_transit()
    assert len(df) == 1
    assert df.iloc[0]["line_name"] == "GTX-A"
    assert "동탄" in df.iloc[0]["stations"]


def test_load_planned_transit_empty_when_section_missing(tmp_path, monkeypatch):
    yaml_path = tmp_path / "manual_catalysts.yaml"
    yaml_path.write_text("redevelopment: []\n", encoding="utf-8")
    monkeypatch.setattr("scoring.market_context.MANUAL_CATALYSTS_YAML", yaml_path)

    df = load_planned_transit()
    assert df.empty
    assert list(df.columns) == ["line_name", "stations", "stage", "expected_open_year"]


def test_load_planned_transit_handles_multiple_entries(tmp_path, monkeypatch):
    yaml_path = tmp_path / "manual_catalysts.yaml"
    yaml_path.write_text(textwrap.dedent("""
        redevelopment: []
        transit_planned:
          - line_name: "GTX-A"
            stations: ["동탄", "판교"]
            stage: "공사중"
            expected_open_year: 2026
          - line_name: "GTX-C"
            stations: ["하남", "여주"]
            stage: "착공"
            expected_open_year: 2027
    """), encoding="utf-8")
    monkeypatch.setattr("scoring.market_context.MANUAL_CATALYSTS_YAML", yaml_path)

    df = load_planned_transit()
    assert len(df) == 2
    assert df.iloc[0]["line_name"] == "GTX-A"
    assert df.iloc[1]["line_name"] == "GTX-C"


def test_asset_ratio_zscore_matches_manual_calc():
    idx = pd.period_range("2020-01", periods=24, freq="M")
    rng = np.random.RandomState(0)
    apt = pd.Series(100 + rng.randn(24).cumsum(), index=idx)
    kospi = pd.Series(100 + rng.randn(24).cumsum(), index=idx)
    assets = pd.DataFrame({"reb_apt_index": apt, "asset_kospi": kospi})

    result = asset_ratio_zscore(assets)

    ratio = apt / kospi
    expected = (ratio.iloc[-1] - ratio.mean()) / ratio.std()
    assert result["asset_kospi"] == pytest.approx(expected)


def test_asset_ratio_zscore_skips_missing_columns():
    idx = pd.period_range("2020-01", periods=12, freq="M")
    assets = pd.DataFrame({"reb_apt_index": pd.Series(range(12), index=idx, dtype=float)})
    result = asset_ratio_zscore(assets)
    assert result == {}
