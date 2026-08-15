"""청약홈 분양 예정분 적재 — 한국부동산원_청약홈 분양정보 조회 서비스
(data.go.kr/data/15098547). 지역 매칭은 API가 반환하는 지역명을 regions.yaml의
시군구명과 문자열 매칭한다(완전 일치 아니면 스킵 — 매칭 실패 건수를 로그로 남긴다).

**2026-08-16 실데이터로 재확인해 필드 2개를 교체함(승인 전엔 totalCount:0이라 확인 불가했음)**:
- 지역: `SUBSCRPT_AREA_CODE_NM`은 "서울"/"경기"/"경남" 같은 **광역시도급**이라 regions.yaml의
  시군구명("강남구", "성남시 분당구" 등)과 완전일치가 애초에 불가능했음(매칭 100% 실패).
  대신 `HSSPLY_ADRES`(공급위치 전체주소, 예: "경기도 성남시 분당구 ...")를
  `parse_sigungu_from_address()`로 파싱해 "시 구" 또는 "구"/"시" 단독 후보를 뽑아 매칭한다.
- 날짜: `RCRIT_PBLANC_DE`(모집공고일)를 쓰고 있었는데 UI엔 "입주예정"으로 표시 중이라 최대
  ~6년까지 괴리(모집공고 2026-08 vs 실제 입주 2032-03 사례 확인). 진짜 입주예정월인
  `MVN_PREARNGE_YM`(이미 YYYYMM 형식)로 교체.

엔드포인트는 apis.data.go.kr가 아니라 **api.odcloud.kr**다(PublicDataReader 패키지의
Reb.get_meta_dict()에서 확인 — data.go.kr 상세페이지엔 정확한 요청주소가 안 나와 있었음).
당초 작성돼 있던 apis.data.go.kr/1613000/... URL은 TAGO 때와 같은 이유로 라이브 검증 없이
추정된 잘못된 값이었음(2026-08-16 확인). odcloud 응답은 `{"data": [...], "totalCount": N,
"page": N, "perPage": N}` 형태의 평평한 구조로, 옛 apis.data.go.kr의 `response.body.items.item`
중첩 구조와 다르다.

원본 필드명은 COLUMN_MAP 하나로만 반영된다 — 실제 응답이 다르면 이 값만 수정.
최초 실행 전 `python ingest/fetch_supply.py --smoke-test` 로 원본 응답을 확인할 것.

사용법:
    python ingest/fetch_supply.py --smoke-test
    python ingest/fetch_supply.py
"""
import re
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

APPLY_HOME_URL = "https://api.odcloud.kr/api/ApplyhomeInfoDetailSvc/v1/getAPTLttotPblancDetail"

# 원본 API 필드명 → 표준 컬럼명. 실제 응답이 다르면 이 값만 수정.
COLUMN_MAP = {
    "project_name": "HOUSE_NM",
    "expected_ym": "MVN_PREARNGE_YM",   # 입주예정월, 이미 YYYYMM 형식
    "total_units": "TOT_SUPLY_HSHLDCO",
    "region_hint": "HSSPLY_ADRES",       # 공급위치 전체주소 -> parse_sigungu_from_address()로 파싱
}


def load_apply_home_key():
    with open(API_KEYS_YAML, encoding="utf-8") as f:
        keys = yaml.safe_load(f) or {}
    key = (keys.get("apply_home") or {}).get("api_key", "")
    if not key:
        raise ValueError("api_keys.local.yaml 의 apply_home.api_key 가 비어있습니다.")
    return key


def parse_sigungu_from_address(address):
    """HSSPLY_ADRES(공급위치 전체주소, 예: '경기도 성남시 분당구 ...', '서울특별시 강남구 ...')에서
    regions.yaml 명명 규칙과 맞는 시군구 후보 문자열을 뽑는다.

    주소는 항상 '{시도} {시/자치구} [{구}] {동} ...' 순서다. 두 번째 토큰이 '시'로 끝나고
    세 번째 토큰이 '구'로 끝나면 구가 설치된 시(수원/성남/안양/용인 등) -> "시 구" 결합형으로
    반환(regions.yaml이 이 형식). 그 외 두 번째 토큰이 구/시/군으로 끝나면 단독 반환
    (서울 자치구, 구 없는 시/군). 매칭 실패는 None -> match_region_code()가 걸러낸다."""
    tokens = str(address).split()
    if len(tokens) < 2:
        return None
    city_or_gu = tokens[1]
    if city_or_gu.endswith("시") and len(tokens) >= 3 and tokens[2].endswith("구"):
        return f"{city_or_gu} {tokens[2]}"
    if city_or_gu.endswith(("구", "시", "군")):
        return city_or_gu
    return None


def normalize_presale_rows(raw):
    df = pd.DataFrame(raw)
    out = pd.DataFrame({std: df[orig] for std, orig in COLUMN_MAP.items()})
    # Preserve nullness through date truncation — NaN must stay NaN, not become string "nan"
    raw_date = out["expected_ym"]
    out["expected_ym"] = raw_date.astype(str).str[:6]
    out.loc[raw_date.isna(), "expected_ym"] = pd.NA
    out["total_units"] = pd.to_numeric(out["total_units"], errors="coerce")
    out["region_hint"] = out["region_hint"].apply(parse_sigungu_from_address)
    return out.dropna(subset=["project_name", "expected_ym", "total_units"])


def fetch_raw_presale(api_key, per_page=1000):
    """전 페이지 수집. 반환은 원본 dict 리스트(정규화 전).

    odcloud 응답은 {"data": [...], "totalCount": N} 평평한 구조 — 옛 apis.data.go.kr의
    response.body.items.item 중첩 구조와 다르다.
    """
    rows, page = [], 1
    while True:
        r = requests.get(APPLY_HOME_URL, params={
            "serviceKey": api_key, "page": page, "perPage": per_page,
        }, timeout=30)
        r.raise_for_status()
        body = r.json()
        page_rows = body.get("data") or []
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
            "serviceKey": api_key, "page": 1, "perPage": 5,
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
