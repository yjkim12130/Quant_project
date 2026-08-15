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
