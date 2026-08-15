"""청약홈 분양 예정분 적재 — 한국부동산원_청약홈 분양정보 조회 서비스
(data.go.kr/data/15098547). 지역 매칭은 API가 반환하는 지역명을 regions.yaml의
시군구명과 문자열 매칭한다(완전 일치 아니면 스킵 — 매칭 실패 건수를 로그로 남긴다).

원본 필드명은 COLUMN_MAP 하나로만 반영된다 — 실제 응답이 다르면 이 값만 수정.
최초 실행 전 `python ingest/fetch_supply.py --smoke-test` 로 원본 응답을 확인할 것.

사용법:
    python ingest/fetch_supply.py --smoke-test
    python ingest/fetch_supply.py
"""
import sys
import time
from pathlib import Path

import pandas as pd
import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_connection  # noqa: E402
from fetch_trades import load_regions  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
API_KEYS_YAML = ROOT / "config" / "api_keys.local.yaml"
REGIONS_YAML = ROOT / "config" / "regions.yaml"

APPLY_HOME_URL = "http://apis.data.go.kr/1613000/AptLttotPblancInfoService/getAPTLttotPblancDetail"

# 원본 API 필드명 → 표준 컬럼명. 실제 응답이 다르면 이 값만 수정.
COLUMN_MAP = {
    "project_name": "HOUSE_NM",
    "expected_ym": "RCRIT_PBLANC_DE",   # YYYYMMDD -> YYYYMM으로 변환
    "total_units": "TOT_SUPLY_HSHLDCO",
    "region_hint": "SUBSCRPT_AREA_CODE_NM",
}


def load_apply_home_key():
    with open(API_KEYS_YAML, encoding="utf-8") as f:
        keys = yaml.safe_load(f) or {}
    key = (keys.get("apply_home") or {}).get("api_key", "")
    if not key:
        raise ValueError("api_keys.local.yaml 의 apply_home.api_key 가 비어있습니다.")
    return key


def normalize_presale_rows(raw):
    df = pd.DataFrame(raw)
    out = pd.DataFrame({std: df[orig] for std, orig in COLUMN_MAP.items()})
    # Preserve nullness through date truncation — NaN must stay NaN, not become string "nan"
    raw_date = out["expected_ym"]
    out["expected_ym"] = raw_date.astype(str).str[:6]
    out.loc[raw_date.isna(), "expected_ym"] = pd.NA
    out["total_units"] = pd.to_numeric(out["total_units"], errors="coerce")
    return out.dropna(subset=["project_name", "expected_ym", "total_units"])


def fetch_raw_presale(api_key, num_of_rows=1000):
    """전 페이지 수집. 반환은 원본 dict 리스트(정규화 전)."""
    rows, page = [], 1
    while True:
        r = requests.get(APPLY_HOME_URL, params={
            "serviceKey": api_key, "_type": "json",
            "numOfRows": num_of_rows, "page": page,
        }, timeout=30)
        r.raise_for_status()
        body = r.json()["response"]["body"]
        items = body.get("items") or {}
        page_rows = items.get("item") or []
        if isinstance(page_rows, dict):  # 결과 1건일 때 dict로 오는 API가 있음
            page_rows = [page_rows]
        if not page_rows:
            break
        rows.extend(page_rows)
        if len(rows) >= int(body.get("totalCount", 0)):
            break
        page += 1
        time.sleep(0.2)
    return rows


def match_region_code(region_hint, region_rows):
    """지역 매칭: API 지역명을 regions.yaml 시군구명과 정확히 일치(exact match) 검사.
    정확히 일치하지 않으면 None 반환 (매칭 실패)."""
    hint_str = str(region_hint).strip()
    for r in region_rows:
        if r["name"] == hint_str:
            return r["code"]
    return None


def main():
    import argparse
    ap = argparse.ArgumentParser(description="청약홈 분양 예정분 적재")
    ap.add_argument("--smoke-test", action="store_true")
    args = ap.parse_args()

    api_key = load_apply_home_key()
    if args.smoke_test:
        r = requests.get(APPLY_HOME_URL, params={
            "serviceKey": api_key, "_type": "json", "numOfRows": 5, "page": 1,
        }, timeout=30)
        print(r.text[:2000])
        return

    raw = fetch_raw_presale(api_key)
    df = normalize_presale_rows(raw)

    all_regions = load_regions("all")
    df["region_code"] = df["region_hint"].apply(lambda h: match_region_code(h, all_regions))
    matched = df.dropna(subset=["region_code"])
    unmatched_n = len(df) - len(matched)

    conn = get_connection()
    now = pd.Timestamp.now("UTC").isoformat()
    rows = [(r.region_code, r.expected_ym, r.project_name, int(r.total_units), "apply_home", now)
            for r in matched.itertuples()]
    conn.execute("DELETE FROM supply_presale WHERE source='apply_home'")
    conn.executemany(
        "INSERT OR REPLACE INTO supply_presale "
        "(region_code, expected_ym, project_name, total_units, source, fetched_at) "
        "VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    print(f"완료: {len(rows)}건 적재 / 지역 매칭 실패 {unmatched_n}건")
    conn.close()


if __name__ == "__main__":
    main()
