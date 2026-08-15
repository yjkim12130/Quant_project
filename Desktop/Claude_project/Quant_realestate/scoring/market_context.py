"""시장환경 지표(공급·교통·자산비교) 집계 — market_context_spec_v1.md 구현.

app.py는 이 모듈의 함수만 호출한다(DB/YAML 직접 접근 금지 — scoring/engine.py 관례와 동일).
"""
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
MANUAL_CATALYSTS_YAML = ROOT / "config" / "manual_catalysts.yaml"


def _load_yaml():
    with open(MANUAL_CATALYSTS_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_redevelopment():
    rows = _load_yaml().get("redevelopment") or []
    if not rows:
        return pd.DataFrame(columns=["region_code", "complex_name", "stage",
                                      "expected_units", "expected_year"])
    return pd.DataFrame(rows)


def load_supply_by_region_year(conn):
    """Load and aggregate presale (자동) and redevelopment (수동) supply data.

    Returns DataFrame with columns: region_code, year, presale_units, redevelopment_units
    """
    # Load presale data from DB, with defensive handling for missing table
    try:
        presale = pd.read_sql_query(
            "SELECT region_code, expected_ym, total_units FROM supply_presale", conn)
    except Exception:
        presale = pd.DataFrame(columns=["region_code", "expected_ym", "total_units"])

    # Extract year and aggregate presale by region and year
    if not presale.empty:
        presale["year"] = presale["expected_ym"].str[:4].astype(int)
        presale_agg = (presale.groupby(["region_code", "year"])["total_units"].sum()
                              .rename("presale_units").reset_index())
        presale_agg["presale_units"] = presale_agg["presale_units"].astype(int)
    else:
        presale_agg = pd.DataFrame(columns=["region_code", "year", "presale_units"])
        presale_agg = presale_agg.astype({"presale_units": "int"})

    # Load and aggregate redevelopment data
    redev = load_redevelopment()
    if redev.empty:
        redev_agg = pd.DataFrame(columns=["region_code", "year", "redevelopment_units"])
        redev_agg = redev_agg.astype({"redevelopment_units": "int"})
    else:
        redev_agg = (redev.groupby(["region_code", "expected_year"])["expected_units"].sum()
                          .rename("redevelopment_units")
                          .reset_index().rename(columns={"expected_year": "year"}))
        redev_agg["redevelopment_units"] = redev_agg["redevelopment_units"].astype(int)

    # Merge presale and redevelopment data
    out = pd.merge(presale_agg, redev_agg, on=["region_code", "year"], how="outer")
    out["presale_units"] = out["presale_units"].fillna(0).astype(int)
    out["redevelopment_units"] = out["redevelopment_units"].fillna(0).astype(int)
    return out.sort_values(["region_code", "year"]).reset_index(drop=True)
