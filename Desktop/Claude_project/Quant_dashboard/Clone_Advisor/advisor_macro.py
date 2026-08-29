"""
advisor_macro.py — 미국 재정·통화 데이터 레이어 (Family E)
═══════════════════════════════════════════════════════════════════════
FRED(세인트루이스 연은)와 미 재무부 FiscalData에서 거시 시계열 원본만
수집한다. 파생 계산·해석은 advisor_dashboard_us.py의 몫 —
advisor_news.py와 동일한 설계 원칙(의존성 최소화, graceful degradation).

FRED는 무료 API 키가 필요하다:
    1) 환경변수 : setx FRED_API_KEY "발급키"
    2) 키 파일  : .fred_api_key 파일에 키 한 줄 저장
키가 없어도 재무부 지표는 정상 동작한다(스펙 §4).
"""
from __future__ import annotations
import os
from datetime import date, timedelta
from typing import Optional

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
_HEADERS = {"User-Agent": "Mozilla/5.0"}

_FRED_BASE = "https://api.stlouisfed.org/fred"
_TREASURY_BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"


def get_fred_key() -> Optional[str]:
    """환경변수 FRED_API_KEY 또는 .fred_api_key 파일에서 키를 읽는다."""
    key = os.environ.get("FRED_API_KEY")
    if key:
        return key.strip()
    path = os.path.join(_HERE, ".fred_api_key")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    return None


def fetch_fred_series(series_id: str, api_key: str, years: int = 3) -> dict:
    """FRED 시리즈 1종의 최근 years년 관측치를 날짜 오름차순으로 반환.

    FRED는 결측을 "." 문자열로 주므로 숫자 변환 전에 걸러낸다.
    관측 주기(일/주/월/분기)는 시리즈마다 다르며 여기선 손대지 않는다.
    """
    start = (date.today() - timedelta(days=365 * years)).isoformat()
    try:
        r = requests.get(
            f"{_FRED_BASE}/series/observations",
            params={"series_id": series_id, "api_key": api_key,
                    "file_type": "json", "observation_start": start},
            headers=_HEADERS, timeout=20)
        if r.status_code != 200:
            return {"_status": "NO_DATA", "series_id": series_id,
                    "observations": [], "_msg": f"HTTP {r.status_code}"}
        obs = []
        for o in r.json().get("observations", []):
            raw = o.get("value")
            if raw in (".", None, ""):
                continue
            try:
                obs.append({"date": o["date"], "value": float(raw)})
            except (ValueError, KeyError):
                continue
        if not obs:
            return {"_status": "NO_DATA", "series_id": series_id,
                    "observations": [], "_msg": "관측치 0건"}
        return {"_status": "ok", "series_id": series_id, "observations": obs, "_msg": ""}
    except Exception as e:
        # 키가 예외 메시지에 섞여 나가지 않도록 타입명만 남긴다.
        return {"_status": "NO_DATA", "series_id": series_id,
                "observations": [], "_msg": type(e).__name__}
