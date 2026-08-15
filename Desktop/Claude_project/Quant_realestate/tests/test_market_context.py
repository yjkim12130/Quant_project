import sqlite3
import textwrap

import pandas as pd

from scoring.market_context import load_redevelopment, load_supply_by_region_year


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
