"""
advisor_dashboard_us.py — 미국 재정·통화 모니터 조립 (Family E)
═══════════════════════════════════════════════════════════════════════
advisor_macro.py가 모은 원본 시계열을 지표 카드·파생 계산·룰 판정으로
조립한다. Family A/B와 동일하게 LLM 없이 룰 템플릿만 쓴다.

단위 주의: WALCL/WRESBAL/WTREGEN은 $M인데 RRPONTSYD만 $B다.
금액을 조합하는 계산은 반드시 to_musd()로 맞춘 뒤 수행한다.
"""
from __future__ import annotations
import json
import os
from datetime import date, datetime, timedelta
from typing import Optional

import advisor_macro as am

_HERE = os.path.dirname(os.path.abspath(__file__))
_REGISTRY_PATH = os.path.join(_HERE, "macro_series.json")

# FRED units_short 원문 → $M 배율
_UNIT_TO_MUSD = {
    "Mil. of $": 1.0, "Mil. of U.S. $": 1.0,
    "Bil. of $": 1000.0, "Bil. of US $": 1000.0,
    "$": 0.000001,
}

_RANK_LOW = 33.0
_RANK_HIGH = 66.0


def load_macro_series() -> Optional[dict]:
    """macro_series.json 로드. 없거나 손상됐으면 None."""
    if not os.path.exists(_REGISTRY_PATH):
        return None
    try:
        with open(_REGISTRY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def to_musd(value: Optional[float], unit: str) -> Optional[float]:
    """금액을 백만달러($M) 기준으로 정규화. 금액 단위가 아니면 None."""
    if not isinstance(value, (int, float)):
        return None
    mult = _UNIT_TO_MUSD.get(unit)
    return None if mult is None else value * mult


def pct_rank(values: list[float], current: float) -> Optional[float]:
    """values 안에서 current의 백분위(0~100). 자기 자신 포함 <= 비율."""
    if not values:
        return None
    le = sum(1 for v in values if v <= current)
    return round(le / len(values) * 100, 1)


def _parse(d: str) -> Optional[date]:
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def change_over(obs: list[dict], days: int) -> Optional[float]:
    """days일 전 대비 변화(절대값 차).

    관측 주기가 일/주/월/분기로 제각각이라 "N번째 앞 관측치"를 쓰면
    지표마다 기간이 달라진다. 목표 날짜에 가장 가까운 관측치를 고른다.
    """
    if len(obs) < 2:
        return None
    last_date = _parse(obs[-1]["date"])
    if last_date is None:
        return None
    target = last_date - timedelta(days=days)
    best, best_gap = None, None
    for o in obs[:-1]:
        d = _parse(o["date"])
        if d is None:
            continue
        gap = abs((d - target).days)
        if best_gap is None or gap < best_gap:
            best, best_gap = o, gap
    if best is None:
        return None
    return round(obs[-1]["value"] - best["value"], 2)


def _assess(rank: Optional[float], higher_is: str) -> str:
    """백분위 + 해석 방향 → 한 줄 판정."""
    if rank is None:
        return ""
    if higher_is == "neutral":
        return f"3년 백분위 {rank:.0f}%"
    high_is_bad = higher_is == "worse"
    if rank >= _RANK_HIGH:
        return "역사적 고점권(부담)" if high_is_bad else "역사적 고점권(양호)"
    if rank <= _RANK_LOW:
        return "역사적 저점권(양호)" if high_is_bad else "역사적 저점권(부담)"
    return "중간권"


def build_indicator(raw: dict, meta: dict) -> dict:
    """원본 시계열 1종 → 카드 렌더에 필요한 값 일체."""
    base = {
        "id": meta.get("id", ""), "label": meta.get("label", ""),
        "unit": meta.get("unit", ""), "unit_label": meta.get("unit_label", ""),
        "freq": meta.get("freq", ""),
        "latest": None, "latest_date": None,
        "chg_1m": None, "chg_1y": None, "pct_rank_3y": None,
        "assessment": "", "series": [],
    }
    status = raw.get("_status")
    obs = raw.get("observations", [])
    if status != "ok" or not obs:
        base["_status"] = status if (status and status != "ok") else "NO_DATA"
        base["_msg"] = raw.get("_msg", "")
        return base

    values = [o["value"] for o in obs]
    rank = pct_rank(values, values[-1])
    base.update({
        "_status": "ok", "_msg": "",
        "latest": obs[-1]["value"], "latest_date": obs[-1]["date"],
        "chg_1m": change_over(obs, 30), "chg_1y": change_over(obs, 365),
        "pct_rank_3y": rank,
        "assessment": _assess(rank, meta.get("higher_is", "neutral")),
        "series": obs,
    })
    return base


def build_group(raw_group: dict, meta_group: dict) -> dict:
    """그룹 1개의 지표 전체를 레지스트리 순서대로 조립."""
    indicators = [
        build_indicator(raw_group.get(m.get("id", ""), {"_status": "NO_DATA",
                                                        "observations": []}), m)
        for m in meta_group.get("indicators", [])
    ]
    ok = [i for i in indicators if i["_status"] == "ok"]
    return {
        "id": meta_group.get("id", ""), "label": meta_group.get("label", ""),
        "indicators": indicators,
        "_status": "ok" if ok else (indicators[0]["_status"] if indicators else "NO_DATA"),
    }
