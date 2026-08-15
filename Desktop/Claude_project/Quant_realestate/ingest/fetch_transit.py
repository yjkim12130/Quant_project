"""지하철 노선/역 그래프 구성 + 단지→업무지구 소요시간 계산.

노선 데이터 출처: 국가철도공단_도시철도 전체노선정보 (data.go.kr/data/15041666).
원본 응답 필드명은 COLUMN_MAP 하나로만 이 코드에 반영된다 — 실제 응답이 아래 기본값과
다르면 COLUMN_MAP 값만 고치면 된다(Global Constraints 참고). 최초 실행 전
`python ingest/fetch_transit.py --smoke-test` 로 원본 응답 1페이지를 출력해 확인할 것.

소요시간은 정밀 실측이 아니라 "동일 노선 인접역 = RIDE_MINUTES(기본 2분), 환승 = TRANSFER_MINUTES
(기본 5분)" 근사다 (오차 ±5~10분 수준, market_context_spec_v1.md §3.2 확정 사항 — 순위 비교용으로는
충분하다는 전제).

사용법:
    python ingest/fetch_transit.py --smoke-test    # 원본 응답 1페이지 출력만
    python ingest/fetch_transit.py                 # 노선/역 적재 + 그래프 구성 + 소요시간 계산
"""
import math
import sys
import time
from pathlib import Path

import heapq
import pandas as pd
import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_connection  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
API_KEYS_YAML = ROOT / "config" / "api_keys.local.yaml"

TAGO_ROUTE_URL = "http://apis.data.go.kr/1613000/UrbanRailroadInfoService/getUrbanRailroadInfo"

# 원본 API 필드명 → 표준 컬럼명. 국토교통부 표준데이터셋 명세 기준 1차 추정값 —
# 스모크테스트(--smoke-test) 응답과 다르면 이 4개 값만 실제 필드명으로 교체.
COLUMN_MAP = {
    "station_name": "STIN_NM",
    "line_name": "LNCD_NM",
    "seq": "STIN_SEQ",
    "lat": "LAT",
    "lon": "LOT",
}

RIDE_MINUTES = 2.0
TRANSFER_MINUTES = 5.0

TARGET_STATIONS = {
    "강남": "강남역", "종로": "종각역", "여의도": "여의도역", "판교": "판교역", "동탄": "동탄역",
}


def load_tago_key():
    with open(API_KEYS_YAML, encoding="utf-8") as f:
        keys = yaml.safe_load(f) or {}
    key = (keys.get("tago") or {}).get("api_key", "")
    if not key:
        raise ValueError("api_keys.local.yaml 의 tago.api_key 가 비어있습니다.")
    return key


def fetch_raw_routes(api_key, num_of_rows=1000):
    """전 페이지 수집. 반환은 원본 dict 리스트(정규화 전)."""
    rows, page = [], 1
    while True:
        r = requests.get(TAGO_ROUTE_URL, params={
            "serviceKey": api_key, "_type": "json",
            "numOfRows": num_of_rows, "pageNo": page,
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


def normalize_route_rows(raw):
    df = pd.DataFrame(raw)
    out = pd.DataFrame({std: df[orig] for std, orig in COLUMN_MAP.items()})
    out["seq"] = pd.to_numeric(out["seq"], errors="coerce").astype("Int64")
    out["lat"] = pd.to_numeric(out["lat"], errors="coerce")
    out["lon"] = pd.to_numeric(out["lon"], errors="coerce")
    return out.dropna(subset=["station_name", "line_name", "seq", "lat", "lon"])


def build_edges(nodes, ride_minutes=RIDE_MINUTES, transfer_minutes=TRANSFER_MINUTES):
    edges = []
    # 동일 노선 인접역(seq 차이 1) -> ride edge 양방향
    for _, line_df in nodes.groupby("line_name"):
        line_df = line_df.sort_values("seq")
        ids = line_df["station_id"].tolist()
        for a, b in zip(ids[:-1], ids[1:]):
            edges.append((a, b, ride_minutes, "ride"))
            edges.append((b, a, ride_minutes, "ride"))
    # 동일 역명, 다른 노선 -> transfer edge 양방향 (전 쌍 조합)
    for _, name_df in nodes.groupby("station_name"):
        ids = name_df["station_id"].unique().tolist()
        for i in range(len(ids)):
            for j in range(len(ids)):
                if i != j:
                    edges.append((ids[i], ids[j], transfer_minutes, "transfer"))
    return pd.DataFrame(edges, columns=["from_id", "to_id", "minutes", "edge_type"]).drop_duplicates(
        subset=["from_id", "to_id"])


def shortest_minutes(adj, start_id, target_ids):
    """다익스트라. adj: {station_id: [(neighbor_id, minutes), ...]}. 반환: {target_id: minutes}."""
    dist = {start_id: 0.0}
    pq = [(0.0, start_id)]
    remaining = set(target_ids) - {start_id}
    found = {t: 0.0 for t in target_ids if t == start_id}
    while pq and remaining:
        d, node = heapq.heappop(pq)
        if d > dist.get(node, float("inf")):
            continue
        for neighbor, w in adj.get(node, []):
            nd = d + w
            if nd < dist.get(neighbor, float("inf")):
                dist[neighbor] = nd
                heapq.heappush(pq, (nd, neighbor))
        if node in remaining:
            found[node] = d
            remaining.discard(node)
    for t in target_ids:
        found.setdefault(t, dist.get(t, float("nan")))
    return found


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_station(lat, lon, stations):
    """stations: station_id/lat/lon 컬럼 DataFrame. 가장 가까운 station_id 반환."""
    stations = stations.reset_index(drop=True)
    d = stations.apply(lambda s: haversine_km(lat, lon, s["lat"], s["lon"]), axis=1)
    return stations.loc[d.idxmin(), "station_id"]


def compute_transit_times(conn):
    """complex_coords 전체에 대해 5개 업무지구까지 소요시간 계산 후 complex_transit_time 적재."""
    coords = pd.read_sql_query("SELECT ckey, lat, lon FROM complex_coords WHERE lat IS NOT NULL", conn)
    stations = pd.read_sql_query("SELECT station_id, station_name, lat, lon FROM station_node", conn)
    edges = pd.read_sql_query("SELECT from_id, to_id, minutes FROM station_edge", conn)

    adj = {}
    for r in edges.itertuples():
        adj.setdefault(r.from_id, []).append((r.to_id, r.minutes))

    target_ids = {}
    for dest, station_name in TARGET_STATIONS.items():
        matches = stations[stations["station_name"] == station_name]
        if matches.empty:
            print(f"[경고] 목적지 역 '{station_name}'({dest}) 이 station_node에 없어 건너뜁니다.")
            continue
        target_ids[dest] = matches.iloc[0]["station_id"]

    if not target_ids:
        print("[경고] 매칭된 목적지 역이 없어 소요시간 계산을 건너뜁니다.")
        conn.execute("DELETE FROM complex_transit_time")
        conn.commit()
        return

    coords["nearest_id"] = coords.apply(
        lambda r: nearest_station(r["lat"], r["lon"], stations), axis=1)

    # 동일 최근접역을 공유하는 단지가 많으므로 역 단위로 한 번만 다익스트라 실행
    cache = {}
    now = pd.Timestamp.now("UTC").isoformat()
    rows = []
    for start_id in coords["nearest_id"].unique():
        if start_id not in cache:
            cache[start_id] = shortest_minutes(adj, start_id, set(target_ids.values()))
        result = cache[start_id]
        id_to_dest = {v: k for k, v in target_ids.items()}
        for target_id, minutes in result.items():
            dest = id_to_dest[target_id]
            for ckey in coords.loc[coords["nearest_id"] == start_id, "ckey"]:
                nearest_name = stations.loc[stations["station_id"] == start_id, "station_name"].iloc[0]
                rows.append((ckey, dest, minutes, nearest_name, now))

    conn.execute("DELETE FROM complex_transit_time")
    conn.executemany(
        "INSERT INTO complex_transit_time (ckey, dest, minutes, nearest_station, calculated_at) "
        "VALUES (?,?,?,?,?)", rows)
    conn.commit()
    print(f"완료: {coords['ckey'].nunique()}개 단지 x {len(target_ids)}개 목적지 = {len(rows)}행")


def main():
    import argparse
    ap = argparse.ArgumentParser(description="지하철 노선/역 적재 + 그래프 구성")
    ap.add_argument("--smoke-test", action="store_true", help="원본 응답 1페이지만 출력하고 종료")
    args = ap.parse_args()

    api_key = load_tago_key()
    if args.smoke_test:
        raw = requests.get(TAGO_ROUTE_URL, params={
            "serviceKey": api_key, "_type": "json", "numOfRows": 5, "pageNo": 1,
        }, timeout=30)
        print(raw.text[:2000])
        return

    raw = fetch_raw_routes(api_key)
    nodes = normalize_route_rows(raw)
    nodes["station_id"] = nodes["line_name"] + "_" + nodes["station_name"]
    nodes = nodes.drop_duplicates("station_id")
    edges = build_edges(nodes)

    conn = get_connection()
    conn.execute("DELETE FROM station_node")
    conn.execute("DELETE FROM station_edge")
    conn.executemany(
        "INSERT INTO station_node (station_id, station_name, line_name, seq, lat, lon) VALUES (?,?,?,?,?,?)",
        nodes[["station_id", "station_name", "line_name", "seq", "lat", "lon"]].itertuples(index=False, name=None))
    conn.executemany(
        "INSERT INTO station_edge (from_id, to_id, minutes, edge_type) VALUES (?,?,?,?)",
        edges.itertuples(index=False, name=None))
    conn.commit()
    print(f"완료: 역 {len(nodes)}개 / 엣지 {len(edges)}개")

    missing = [name for name in TARGET_STATIONS.values()
               if name not in nodes["station_name"].values]
    if missing:
        print(f"[경고] 목표 업무지구 대표역이 노선 데이터에 없음: {missing} — "
              "역명 표기가 다를 수 있으니 station_node 테이블을 확인하세요.")
    compute_transit_times(conn)
    conn.close()


if __name__ == "__main__":
    main()
