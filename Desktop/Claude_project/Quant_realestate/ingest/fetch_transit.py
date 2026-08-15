"""지하철 노선/역 그래프 구성 + 단지→업무지구 소요시간 계산.

노선 데이터 출처: 국가철도공단이 레일포털(data.kric.go.kr)에 공개하는 정적 표준데이터.
(당초 계획한 TAGO 실시간 API 15041666은 data.go.kr에서 "API 유형: LINK"로 등록된
데이터셋 — 즉 apis.data.go.kr 표준 게이트웨이가 실제로 없고 레일포털 정적 파일에
링크만 걸려있어 호출 자체가 불가능함을 확인하고 폐기함, 2026-08-15.)

- 역사정보: data.go.kr/data/15013205/standard.do → 역명·위경도·환승여부
- 노선정보: data.go.kr/data/15013203/standard.do → 정거장구성(노선별 역 순서)
두 파일 모두 다운로드가 세션/JS 기반이라 URL로 직접 받을 수 없다 — 브라우저로 다운로드해
data/raw/transit/ 에 저장할 것(이 디렉터리는 .gitignore의 data/raw/ 패턴에 포함됨).

노선번호(총 46종)가 두 파일 사이의 유일하게 안정적인 조인 키다 — 노선명은 파일마다 표기가
다르다(예: 역사정보 "2호선" vs 노선정보 "수도권  도시철도 2호선"). 정거장구성은 "코드-역명"을
쉼표(드물게 "+", 신분당선 1건)로 이어붙인 문자열이며, 하나의 노선번호가 여러 구간(정거장구성
행)으로 나뉘기도 한다(예: 1호선 노선번호 I4101 아래 "경부선"·"수도권 광역철도 1호선" 두 구간이
따로 존재 — 실제로 여러 운영 노선이 합쳐져 하나의 서비스를 이루는 경우). 이런 구간은 파일에 나온
순서대로 seq를 이어붙여 하나의 연속 노선으로 취급한다 — 구간 경계에서 실제로는 인접하지 않는
역 사이에 가짜 ride edge가 하나 생길 수 있으나, ride 소요시간이 역간 실거리 기반(아래 참고)이라
이런 비정상적으로 먼 "인접" 쌍은 자동으로 큰 값이 매겨져 다익스트라가 알아서 기피한다(2026-08-16
확인: 경의중앙선 I4108 노선에 좌표 오류로 보이는 190km짜리 "인접" 구간이 있었는데, 예전 고정
2분 모델에서는 2분짜리 웜홀 지름길이 될 뻔했음 — 거리 기반 전환으로 부수적으로 해소됨).
반대로 노선번호가 서로 다른 지선(예: 2호선 본선 S1102 vs 성수지선 S1121)은 각자 별도로 seq를
매겨 ride edge를 만들고, 분기역은 역명이 같으므로 transfer edge로 자연스럽게 이어진다.

소요시간은 정밀 실측이 아니라 근사다: 동일 노선 인접역은 역간 실거리(haversine) ÷ AVG_SPEED_KMH
(표정속도, 기본 34km/h — 전체 역간거리 중앙값 1.14km 기준 역산한 값)로 환산하고, 환승은
TRANSFER_MINUTES(기본 5분) 고정값을 쓴다. 2026-08-16까지는 인접역도 고정 2분이었으나, 역간격이
넓은 광역철도/경전철(경강선·에버라인 등)에서 실제보다 훨씬 빠르게 나오는 문제가 있어(용인 처인구
남단 초월·이천역 경유 시 강남까지 23~29분으로 비현실적으로 계산됨, 실사용 검토 중 발견) 거리
기반으로 교체함. 촘촘한 도심 구간은 기존 2분 근사와 거의 같은 값이 나와 회귀는 없음.

사용법:
    python ingest/fetch_transit.py --smoke-test    # DB 반영 없이 파싱 결과만 요약 출력
    python ingest/fetch_transit.py                 # 노선/역 적재 + 그래프 구성 + 소요시간 계산
"""
import math
import re
import sys
from pathlib import Path

import heapq
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_connection  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATION_XLSX = ROOT / "data" / "raw" / "transit" / "전체_도시철도역사정보_20260630.xlsx"
ROUTE_XLSX = ROOT / "data" / "raw" / "transit" / "전체_도시철도노선정보_20260630.xlsx"

AVG_SPEED_KMH = 34.0  # 서울 지하철 평균 표정속도(정차 포함) 근사 — 역간거리 haversine 환산용
MIN_RIDE_MINUTES = 1.0  # 역간거리가 극단적으로 짧아도 정차/가속 오버헤드 최소 보장
TRANSFER_MINUTES = 5.0

# 원본 XLSX는 전국(부산/대구/광주/대전 도시철도 포함) 데이터다. transfer edge는 역명이 같으면
# 무조건 잇는데(같은 이름=같은 역이라는 가정), 지방 도시에도 서울과 같은 역명이 흔해서
# (예: "신흥"이 성남 8호선과 대구 1호선 양쪽에 존재) 필터링 없이 그래프를 만들면 성남↔대구를
# "환승 5분"으로 잘못 잇는 경로가 다익스트라 최단경로로 뽑히는 사고가 났다(2026-08-16 실사용 중
# 발견 — 성남 중원구→판교 44분이 실제로는 이 경유로 계산된 값이었음). 위도 36.5는 지방 도시철도
# (최북단 대전 36.39)와 수도권 관련 노선(최남단 장항선 36.77) 사이의 빈 구간이라 안전한 경계.
MIN_LAT = 36.5

# 값은 역사정보 파일의 정규화된 역명(괄호 부기명·끝 "역" 제거 후) 기준.
# 동탄: GTX-A 동탄역은 이 "도시철도" 데이터셋에 없음(경부선 "서동탄역"만 존재, 다른 역) —
# 데이터셋 갱신 시 다시 확인할 것.
TARGET_STATIONS = {
    "강남": "강남", "종로": "종각", "여의도": "여의도", "판교": "판교", "동탄": "동탄",
}

# 노선번호가 다르지만 실제로는 환승 없이 한 열차로 직결 운행되는 경계역 쌍(수동 확인 필요 —
# 자동 판별 불가). 2026-08-16 거리기반 소요시간 도입 후 30개 지역 전수검증 중 발견: 4호선
# (서울교통공사, ~남태령)과 안산과천선(코레일, 선바위~)이 물리적으로 하나의 연속 선로인데
# 노선번호도 다르고 경계역 이름도 달라(남태령/선바위, 1.81km) ride edge도 transfer edge도 안
# 생겨 그래프가 끊겨 있었음 — 과천시 소요시간이 안산선→서해선→1호선→7호선→2호선을 거치는
# 143분짜리 완전히 잘못된 우회로로 계산되는 사고로 이어짐(실제 정부과천청사~강남 30분대).
# 전체 46개 노선 끝점을 <2km 거리로 스캔하면 후보가 9쌍 더 있으나(청량리/신설동, 서울역 인근
# 클러스터 등) 대부분 진짜 직결이 아니라 그냥 가까운 별개 역이라 확신 없이는 추가하지 않음 —
# 잘못 이으면 새 웜홀 버그가 된다. 여기 목록은 실제 노선도로 개별 확인된 것만 추가할 것.
LINE_BOUNDARY_BRIDGES = [
    ("남태령", "선바위"),
]


def _normalize_station_name(name):
    """역명 표기 통일: 괄호 부기명 제거 + 끝 '역' 접미사 제거."""
    name = re.sub(r"\(.*?\)", "", str(name)).strip()
    if name.endswith("역") and len(name) > 1:
        name = name[:-1]
    return name


def parse_station_composition(text):
    """'A01-서울,A02-공덕,...' 또는 '신사+D05-논현+...' → 순서대로 정규화된 역명 리스트."""
    if not isinstance(text, str) or not text.strip():
        return []
    tokens = text.split(",") if "," in text else text.split("+")
    names = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        parts = token.split("-", 1)
        name = parts[1].strip() if len(parts) == 2 else token
        names.append(_normalize_station_name(name))
    return names


def load_route_sequences(route_xlsx=ROUTE_XLSX):
    """노선번호별로 정거장구성 순서를 이어붙여 (노선번호, 정규화역명) -> seq 매핑 생성.

    반환: (seq_map, label_fallback_code) — label_fallback_code는 {노선정보 노선명: 노선번호}로,
    노선정보 안에서 그 노선명을 쓰는 노선번호가 정확히 하나뿐인 것만 담는다(역사정보 쪽 노선번호가
    노선정보에 아예 없는 고아 코드일 때만 쓰는 안전한 대체 조회용 — load_stations 참고. 애매하게
    여러 코드가 같은 노선명을 공유하는 경우(예: "수도권 도시철도 2호선"이 본선/지선 여러 코드에
    걸쳐 있는 경우)는 뺀다, 잘못 합치면 지선을 본선인 것처럼 이어붙이게 된다).
    """
    if not route_xlsx.exists():
        raise FileNotFoundError(
            f"{route_xlsx} 가 없습니다. data.go.kr/data/15013203/standard.do 에서 "
            "'전체_도시철도노선정보' XLSX를 다운로드해 위 경로에 저장하세요."
        )
    df = pd.read_excel(route_xlsx)
    seq_map = {}
    counters = {}
    for row in df.itertuples():
        code = row.노선번호
        counter = counters.get(code, 0)
        for name in parse_station_composition(row.정거장구성):
            key = (code, name)
            if key not in seq_map:
                seq_map[key] = counter
            counter += 1
        counters[code] = counter

    codes_per_label = df.groupby("노선명")["노선번호"].unique()
    label_fallback_code = {label: codes[0] for label, codes in codes_per_label.items() if len(codes) == 1}
    return seq_map, label_fallback_code


def load_stations(station_xlsx=STATION_XLSX, route_xlsx=ROUTE_XLSX):
    """역사정보 + 노선정보 결합 -> station_name/line_code/line_label/seq/lat/lon DataFrame."""
    if not station_xlsx.exists():
        raise FileNotFoundError(
            f"{station_xlsx} 가 없습니다. data.go.kr/data/15013205/standard.do 에서 "
            "'전체_도시철도역사정보' XLSX를 다운로드해 위 경로에 저장하세요."
        )
    df = pd.read_excel(station_xlsx)
    out = pd.DataFrame({
        "station_name": df["역사명"].map(_normalize_station_name),
        "line_code": df["노선번호"],
        "line_label": df["노선명"],
        "lat": pd.to_numeric(df["역위도"], errors="coerce"),
        "lon": pd.to_numeric(df["역경도"], errors="coerce"),
    }).dropna(subset=["station_name", "line_code", "lat", "lon"])
    out = out[out["lat"] >= MIN_LAT]  # 지방 도시철도 배제(동명역 오환승 방지, 위 MIN_LAT 주석 참고)

    seq_map, label_fallback_code = load_route_sequences(route_xlsx)

    def _resolve(row):
        key = (row["line_code"], row["station_name"])
        if key in seq_map:
            return row["line_code"], seq_map[key]
        # 노선번호가 노선정보에 아예 없는 고아 코드인 경우에만: 노선명이 노선정보에서 유일한
        # 노선번호에만 대응되면 그 코드로 대체 조회(위 load_route_sequences 설명 참고).
        alt_code = label_fallback_code.get(row["line_label"])
        if alt_code is not None:
            alt_key = (alt_code, row["station_name"])
            if alt_key in seq_map:
                return alt_code, seq_map[alt_key]
        return row["line_code"], None

    resolved = out.apply(_resolve, axis=1, result_type="expand")
    out["line_code"], out["seq"] = resolved[0], resolved[1]
    return out


def ride_minutes_for(lat1, lon1, lat2, lon2):
    """인접역 소요시간 = 역간 실거리(haversine) ÷ AVG_SPEED_KMH. 모듈 docstring 참고."""
    dist_km = haversine_km(lat1, lon1, lat2, lon2)
    return max(MIN_RIDE_MINUTES, dist_km / AVG_SPEED_KMH * 60)


def build_edges(nodes, transfer_minutes=TRANSFER_MINUTES):
    edges = []
    # 동일 노선 인접역(seq 차이 1) -> ride edge 양방향, 소요시간은 역간 실거리 기반
    for _, line_df in nodes.groupby("line_name"):
        line_df = line_df.sort_values("seq")
        ids = line_df["station_id"].tolist()
        lats = line_df["lat"].tolist()
        lons = line_df["lon"].tolist()
        for i in range(len(ids) - 1):
            minutes = ride_minutes_for(lats[i], lons[i], lats[i + 1], lons[i + 1])
            edges.append((ids[i], ids[i + 1], minutes, "ride"))
            edges.append((ids[i + 1], ids[i], minutes, "ride"))
    # 동일 역명, 다른 노선 -> transfer edge 양방향 (전 쌍 조합)
    for _, name_df in nodes.groupby("station_name"):
        ids = name_df["station_id"].unique().tolist()
        for i in range(len(ids)):
            for j in range(len(ids)):
                if i != j:
                    edges.append((ids[i], ids[j], transfer_minutes, "transfer"))
    # 수동 확인된 노선 경계 직결 구간(LINE_BOUNDARY_BRIDGES) -> ride edge 양방향, 실거리 기반
    for name_a, name_b in LINE_BOUNDARY_BRIDGES:
        rows_a = nodes[nodes["station_name"] == name_a]
        rows_b = nodes[nodes["station_name"] == name_b]
        for _, ra in rows_a.iterrows():
            for _, rb in rows_b.iterrows():
                minutes = ride_minutes_for(ra["lat"], ra["lon"], rb["lat"], rb["lon"])
                edges.append((ra["station_id"], rb["station_id"], minutes, "ride"))
                edges.append((rb["station_id"], ra["station_id"], minutes, "ride"))
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

    if coords.empty:
        print("[경고] complex_coords가 비어있어(지오코딩 미완료) 소요시간 계산을 건너뜁니다.")
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


def _build_nodes_and_edges():
    stations = load_stations()
    missing_seq = int(stations["seq"].isna().sum())
    nodes = stations.dropna(subset=["seq"]).copy()
    nodes["seq"] = nodes["seq"].astype(int)
    nodes["station_id"] = nodes["line_code"] + "_" + nodes["station_name"]
    nodes = nodes.drop_duplicates("station_id")
    # ride edge는 노선번호(line_code) 단위로 끊어야 서로 다른 지선이 잘못 이어붙지 않는다.
    edge_nodes = nodes.rename(columns={"line_code": "line_name"})
    edges = build_edges(edge_nodes)
    return stations, nodes, edges, missing_seq


def main():
    import argparse
    ap = argparse.ArgumentParser(description="지하철 노선/역 적재 + 그래프 구성")
    ap.add_argument("--smoke-test", action="store_true", help="DB 반영 없이 파싱 결과만 요약 출력")
    args = ap.parse_args()

    if args.smoke_test:
        stations, nodes, edges, missing_seq = _build_nodes_and_edges()
        print(f"역사정보 원본 {len(stations)}행 -> seq 매칭 {len(nodes)}개 / 미매칭(제외) {missing_seq}개")
        print(f"엣지 {len(edges)}개")
        missing = [name for name in TARGET_STATIONS.values()
                   if name not in nodes["station_name"].values]
        if missing:
            print(f"[경고] 목표 업무지구 대표역이 노선 데이터에 없음: {missing}")
        return

    stations, nodes, edges, missing_seq = _build_nodes_and_edges()

    conn = get_connection()
    conn.execute("DELETE FROM station_node")
    conn.execute("DELETE FROM station_edge")
    conn.executemany(
        "INSERT INTO station_node (station_id, station_name, line_name, seq, lat, lon) VALUES (?,?,?,?,?,?)",
        nodes[["station_id", "station_name", "line_label", "seq", "lat", "lon"]].itertuples(index=False, name=None))
    conn.executemany(
        "INSERT INTO station_edge (from_id, to_id, minutes, edge_type) VALUES (?,?,?,?)",
        edges.itertuples(index=False, name=None))
    conn.commit()
    print(f"완료: 역 {len(nodes)}개 / 엣지 {len(edges)}개 (노선정보와 seq 미매칭으로 제외된 역 {missing_seq}개)")

    missing = [name for name in TARGET_STATIONS.values()
               if name not in nodes["station_name"].values]
    if missing:
        print(f"[경고] 목표 업무지구 대표역이 노선 데이터에 없음: {missing} - "
              "역명 표기가 다를 수 있으니 station_node 테이블을 확인하세요.")
    compute_transit_times(conn)
    conn.close()


if __name__ == "__main__":
    main()
