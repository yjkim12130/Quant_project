import textwrap

import pandas as pd

from scoring.market_context import load_redevelopment


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
