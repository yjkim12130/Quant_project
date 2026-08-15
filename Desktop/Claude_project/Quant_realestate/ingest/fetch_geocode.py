"""단지 좌표 지오코딩 — 카카오로컬 API.

trades_sale의 고유 단지(ckey)마다 도로명주소 → 지번주소 → 단지명 키워드 순으로 좌표를
조회해 complex_coords 테이블에 적재한다. 일회성 배치이며, 신규 단지가 생기면 재실행해도
이미 적재된 ckey는 건너뛴다(pending_complexes가 complex_coords에 없는 것만 반환).

사용법:
    python ingest/fetch_geocode.py --limit 20      # 스모크테스트
    python ingest/fetch_geocode.py                 # 전체 배치
"""
import sys
import time
from pathlib import Path

import pandas as pd
import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_connection  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scoring.engine import _complex_key  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
API_KEYS_YAML = ROOT / "config" / "api_keys.local.yaml"

KAKAO_ADDR_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
CALL_INTERVAL_SEC = 0.1


def geocode_query(row, prefer):
    if prefer == "road":
        return f"{row['region_name']} {row['dong_name']} {row['road_name']}"
    if prefer == "jibun":
        return f"{row['region_name']} {row['dong_name']} {row['jibun']}"
    return f"{row['region_name']} {row['dong_name']} {row['complex_name']}"


def parse_kakao_address(data):
    docs = data.get("documents") or []
    if not docs:
        return None
    addr = docs[0]["address"]
    return (float(addr["y"]), float(addr["x"]))


def parse_kakao_keyword(data):
    docs = data.get("documents") or []
    if not docs:
        return None
    return (float(docs[0]["y"]), float(docs[0]["x"]))


def load_kakao_key():
    with open(API_KEYS_YAML, encoding="utf-8") as f:
        keys = yaml.safe_load(f) or {}
    key = (keys.get("kakao") or {}).get("rest_api_key", "")
    if not key:
        raise ValueError("api_keys.local.yaml 의 kakao.rest_api_key 가 비어있습니다.")
    return key


def geocode_one(session, api_key, row):
    """도로명 → 지번 → 키워드(단지명) 순으로 시도. 성공 시 (lat, lon, 사용한 쿼리), 실패 시 None."""
    headers = {"Authorization": f"KakaoAK {api_key}"}
    attempts = []
    if row.get("road_name"):
        attempts.append(("road", KAKAO_ADDR_URL, parse_kakao_address))
    if row.get("jibun"):
        attempts.append(("jibun", KAKAO_ADDR_URL, parse_kakao_address))
    attempts.append(("keyword", KAKAO_KEYWORD_URL, parse_kakao_keyword))

    for prefer, url, parser in attempts:
        query = geocode_query(row, prefer)
        res = session.get(url, headers=headers, params={"query": query}, timeout=10)
        res.raise_for_status()
        result = parser(res.json())
        if result:
            return result[0], result[1], query
        time.sleep(CALL_INTERVAL_SEC)
    return None


def pending_complexes(conn):
    df = pd.read_sql_query(
        "SELECT region_code, region_name, dong_name, complex_name, road_name, jibun "
        "FROM trades_sale", conn)
    df["ckey"] = _complex_key(df)
    df = df.sort_values("road_name", na_position="last").drop_duplicates("ckey")
    done = pd.read_sql_query("SELECT ckey FROM complex_coords", conn)["ckey"]
    return df[~df["ckey"].isin(done)].reset_index(drop=True)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="단지 좌표 지오코딩(카카오로컬)")
    ap.add_argument("--limit", type=int, default=None, help="스모크테스트용 처리 건수 제한")
    args = ap.parse_args()

    api_key = load_kakao_key()
    conn = get_connection()
    pending = pending_complexes(conn)
    if args.limit:
        pending = pending.head(args.limit)
    print(f"지오코딩 대상: {len(pending)}개 단지")

    session = requests.Session()
    ok = fail = 0
    now = pd.Timestamp.now("UTC").isoformat()
    for row in pending.to_dict("records"):
        try:
            result = geocode_one(session, api_key, row)
        except Exception as e:  # noqa: BLE001 — 개별 실패가 배치 전체를 막지 않음
            print(f"  [실패] {row['ckey']}: {e}")
            fail += 1
            continue
        if result is None:
            print(f"  [미발견] {row['ckey']} ({row['complex_name']})")
            fail += 1
            continue
        lat, lon, query = result
        conn.execute(
            "INSERT OR REPLACE INTO complex_coords (ckey, region_code, address_used, lat, lon, geocoded_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (row["ckey"], row["region_code"], query, lat, lon, now),
        )
        conn.commit()
        ok += 1
        if ok % 50 == 0:
            print(f"  진행: 성공 {ok} / 실패 {fail}")
        time.sleep(CALL_INTERVAL_SEC)

    print(f"완료: 성공 {ok} / 실패 {fail}")
    conn.close()


if __name__ == "__main__":
    main()
