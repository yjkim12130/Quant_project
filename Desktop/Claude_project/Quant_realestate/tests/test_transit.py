import math
import sqlite3

import pandas as pd

from ingest.db import SCHEMA
from ingest.fetch_transit import (
    build_edges, shortest_minutes, nearest_station, haversine_km,
    parse_station_composition, _normalize_station_name, compute_transit_times,
    load_stations, MIN_LAT, ride_minutes_for, AVG_SPEED_KMH,
)

# 강남/역삼 좌표는 test_haversine_km_known_pair와 동일(실측 약 0.8km) — ride edge 소요시간이
# 역간 실거리 기반으로 계산되므로(build_edges) 실제 좌표를 써야 한다.
NODES_SAMPLE = pd.DataFrame([
    {"line_name": "2호선", "station_name": "강남", "seq": 1, "lat": 37.4979, "lon": 127.0276},
    {"line_name": "2호선", "station_name": "역삼", "seq": 2, "lat": 37.5006, "lon": 127.0364},
    {"line_name": "신분당선", "station_name": "강남", "seq": 1, "lat": 37.4979, "lon": 127.0276},
])


def _with_station_id(df):
    df = df.copy()
    df["station_id"] = df["line_name"] + "_" + df["station_name"]
    return df


def test_build_edges_creates_ride_edges_between_adjacent_seq():
    nodes = _with_station_id(NODES_SAMPLE)
    edges = build_edges(nodes)
    ride = edges[edges["edge_type"] == "ride"]
    # 2호선 강남(seq1)-역삼(seq2) 인접 → 양방향 ride edge 2개, 소요시간은 실거리 기반
    expected = ride_minutes_for(37.4979, 127.0276, 37.5006, 127.0364)
    assert len(ride) == 2
    assert set(ride["minutes"]) == {expected}


def test_ride_minutes_for_matches_distance_over_speed():
    d = haversine_km(37.4979, 127.0276, 37.5006, 127.0364)
    assert ride_minutes_for(37.4979, 127.0276, 37.5006, 127.0364) == d / AVG_SPEED_KMH * 60


def test_ride_minutes_for_floors_very_short_hops():
    """역간거리가 극단적으로 짧아도(같은 좌표) 최소 소요시간(MIN_RIDE_MINUTES)은 보장된다."""
    assert ride_minutes_for(37.5, 127.0, 37.5, 127.0) == 1.0


def test_ride_minutes_for_suburban_line_takes_longer_than_flat_2min():
    """역간거리가 넓은 광역철도/경전철 근사 — 2026-08-16 발견된 문제(교외 노선이 고정 2분
    모델에서 비현실적으로 빠르게 나옴)의 회귀 방지. 6km 구간이면 flat 2분보다 훨씬 오래 걸려야 함."""
    minutes = ride_minutes_for(37.2, 127.2, 37.25, 127.2)  # 약 5.6km
    assert minutes > 8.0


def test_build_edges_bridges_known_line_boundary():
    """LINE_BOUNDARY_BRIDGES에 등록된 경계역 쌍(남태령/선바위)은 노선번호·역명이 달라도
    ride edge로 이어져야 한다 — 2026-08-16 발견: 4호선과 안산과천선이 실제로는 환승 없이
    직결 운행되는데 노선번호가 갈리고 경계역 이름도 달라 그래프가 끊겨 있었음(과천시 소요시간이
    143분짜리 우회로로 잘못 계산되는 사고로 이어짐)."""
    nodes = pd.DataFrame([
        {"line_name": "4호선", "station_name": "남태령", "seq": 1,
         "lat": 37.4638, "lon": 126.9886, "station_id": "4호선_남태령"},
        {"line_name": "안산과천선", "station_name": "선바위", "seq": 1,
         "lat": 37.4482, "lon": 126.9979, "station_id": "안산과천선_선바위"},
    ])
    edges = build_edges(nodes)
    ride = edges[edges["edge_type"] == "ride"]
    bridged = ride[(ride["from_id"] == "4호선_남태령") & (ride["to_id"] == "안산과천선_선바위")]
    assert len(bridged) == 1
    expected = ride_minutes_for(37.4638, 126.9886, 37.4482, 126.9979)
    assert bridged.iloc[0]["minutes"] == expected


def test_build_edges_does_not_bridge_unregistered_station_pairs():
    """LINE_BOUNDARY_BRIDGES에 없는 노선 경계는(예: 청량리/신설동처럼 실제로는 별개 역) 여전히
    이어지지 않아야 한다 — 확인 안 된 쌍을 자동으로 잇지 않는다는 설계 의도의 회귀 방지."""
    nodes = pd.DataFrame([
        {"line_name": "1호선", "station_name": "청량리", "seq": 1,
         "lat": 37.5803, "lon": 127.0468, "station_id": "1호선_청량리"},
        {"line_name": "우이신설선", "station_name": "신설동", "seq": 1,
         "lat": 37.5758, "lon": 127.0246, "station_id": "우이신설선_신설동"},
    ])
    edges = build_edges(nodes)
    assert len(edges) == 0


def test_build_edges_creates_transfer_edges_for_same_station_name():
    nodes = _with_station_id(NODES_SAMPLE)
    edges = build_edges(nodes)
    transfer = edges[edges["edge_type"] == "transfer"]
    # 2호선 강남 <-> 신분당선 강남 환승 → 양방향 2개
    assert len(transfer) == 2
    assert set(transfer["minutes"]) == {5.0}


def test_normalize_station_name_strips_suffix_and_parenthesis():
    assert _normalize_station_name("강남역") == "강남"
    assert _normalize_station_name("양재(서초구청)") == "양재"
    assert _normalize_station_name("역") == "역"  # 한 글자뿐이면 그대로 둠


def test_parse_station_composition_comma_delimited_with_code_prefix():
    names = parse_station_composition("A01-서울,A02-공덕,A03-홍대입구")
    assert names == ["서울", "공덕", "홍대입구"]


def test_parse_station_composition_plus_delimited():
    # 신분당선처럼 콤마 없이 '+'로만 이어붙은 경우
    names = parse_station_composition("신사+D05-논현+D06-신논현")
    assert names == ["신사", "논현", "신논현"]


def test_parse_station_composition_normalizes_station_suffix():
    names = parse_station_composition("100-양촌역, 101-구래역")
    assert names == ["양촌", "구래"]


def test_parse_station_composition_empty_or_nan():
    assert parse_station_composition("") == []
    assert parse_station_composition(float("nan")) == []


def test_shortest_minutes_multi_hop_path():
    """다익스트라가 여러 홉을 거쳐 최단 경로를 계산하는지 확인.

    그래프:
    A -2min-> B -3min-> C
    A -10min-> D -1min-> C

    A에서 C로 가는 최단 경로는 A->B->C(5분), 아니라 A->D->C(11분)가 아님.
    """
    adj = {
        "A": [("B", 2.0), ("D", 10.0)],
        "B": [("C", 3.0)],
        "D": [("C", 1.0)],
    }
    result = shortest_minutes(adj, "A", ["C"])
    assert result["C"] == 5.0, f"Expected 5.0 (A->B->C), got {result['C']}"


def test_shortest_minutes_start_in_targets():
    """시작점이 타겟에 포함되면 0.0을 반환해야 함."""
    adj = {
        "A": [("B", 2.0)],
        "B": [("C", 3.0)],
    }
    result = shortest_minutes(adj, "A", ["A", "B", "C"])
    assert result["A"] == 0.0, f"Expected start_id to have 0.0, got {result['A']}"
    assert result["B"] == 2.0, f"Expected 2.0 for B, got {result['B']}"
    assert result["C"] == 5.0, f"Expected 5.0 for C, got {result['C']}"


def test_shortest_minutes_weighted_dijkstra_vs_bfs():
    """가중 다익스트라 동작 확인: hop 수가 적으면 무조건 선택하지 않고 가중치로 비교.

    그래프:
    A -100min-> C             (1 hop, 100분 — 비싼 직접 경로)
    A -1min-> B -1min-> C     (2 hops, 2분 — 싼 다중홉 경로)

    순진한 BFS/hop-counting 알고리즘: 1-hop 경로 A->C(100분)를 먼저 발견해서 고정
    (재방문 없음) → 결과 100.0 (틀림)

    가중 다익스트라: 누적 가중치로 거리를 추적하고 재완화(relax)하므로 2-hop 경로
    A->B->C(2분)를 발견하고 더 싼 경로임을 인식해서 업데이트 → 결과 2.0 (맞음)

    이 그래프에서 두 알고리즘은 다른 답을 줌. 올바른 다익스트라는 2.0을 반환.
    """
    adj = {
        "A": [("B", 1.0), ("C", 100.0)],
        "B": [("C", 1.0)],
    }
    result = shortest_minutes(adj, "A", ["C"])
    assert result["C"] == 2.0, f"Expected 2.0 (2-hop path A->B->C), got {result['C']}"


def test_shortest_minutes_unreachable_target():
    """도달 불가능한 타겟의 경우 NaN을 반환해야 함."""
    adj = {
        "A": [("B", 2.0)],
        "B": [("C", 3.0)],
    }
    result = shortest_minutes(adj, "A", ["X"])
    import math
    assert math.isnan(result["X"]), f"Expected NaN for unreachable target, got {result['X']}"


def test_shortest_minutes_empty_targets():
    """빈 타겟 리스트의 경우 빈 딕셔너리를 반환해야 함."""
    adj = {
        "A": [("B", 2.0)],
    }
    result = shortest_minutes(adj, "A", [])
    assert result == {}, f"Expected empty dict, got {result}"


def test_haversine_km_zero_distance():
    assert haversine_km(37.5, 127.0, 37.5, 127.0) == 0.0


def test_haversine_km_known_pair():
    # 강남역(37.4979,127.0276) ~ 역삼역(37.5006,127.0364) 실측 약 0.8km
    d = haversine_km(37.4979, 127.0276, 37.5006, 127.0364)
    assert 0.5 < d < 1.2


def test_nearest_station_picks_closest():
    stations = pd.DataFrame({
        "station_id": ["A", "B"], "lat": [37.50, 37.60], "lon": [127.03, 127.10],
    })
    result = nearest_station(37.501, 127.031, stations)
    assert result == "A"


def test_nearest_station_safe_with_non_unique_index():
    """인덱스가 고유하지 않은 DataFrame에서도 scalar 문자열을 반환하는지 확인.

    pd.concat이나 필터링으로 인해 중복된 인덱스를 가진 DataFrame을 전달해도
    nearest_station이 안전하게 동작해야 한다.
    """
    # 중복된 인덱스를 가진 DataFrame 생성 (pd.concat 시뮬레이션)
    stations = pd.DataFrame({
        "station_id": ["A", "B", "C"], "lat": [37.50, 37.60, 37.70], "lon": [127.03, 127.10, 127.15],
    })
    stations.index = [0, 0, 1]  # 중복된 인덱스

    result = nearest_station(37.501, 127.031, stations)

    # 결과가 scalar 문자열인지 확인
    assert isinstance(result, str), f"Expected str, got {type(result)}"
    assert result == "A", f"Expected 'A', got {result}"


def test_compute_transit_times_safe_with_empty_complex_coords(tmp_path):
    """complex_coords가 비어있어도(지오코딩 미완료) 예외 없이 건너뛰어야 한다.

    pandas는 빈 DataFrame에 .apply(axis=1)를 걸면 결과 타입 추론을 위해 함수를
    한 번 특이하게 호출하면서 DataFrame을 반환할 수 있어, 단일 컬럼 대입이
    ValueError로 깨지는 경우가 있다 — 카카오 지오코딩 API 키를 아직 발급받지
    못해 complex_coords가 0행인 현재 상태에서 실제로 재현된 버그.
    """
    conn = sqlite3.connect(tmp_path / "test.db")
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT INTO station_node (station_id, station_name, line_name, seq, lat, lon) VALUES (?,?,?,?,?,?)",
        [("2호선_강남", "강남", "2호선", 1, 37.4979, 127.0276)])
    conn.commit()

    compute_transit_times(conn)  # 예외 없이 종료되어야 함

    assert conn.execute("SELECT COUNT(*) FROM complex_transit_time").fetchone()[0] == 0
    conn.close()


def test_load_stations_excludes_non_capital_area_lines(tmp_path):
    """지방 도시철도(부산/대구/광주/대전 등)는 제외되어야 한다.

    실사용 중 발견된 버그: 원본 XLSX가 전국 데이터라 "신흥"·"교대"·"중앙로" 같은 역명이
    성남/대구 등 여러 도시에 중복 존재한다. 필터링 없이 그래프를 만들면 build_edges의
    transfer edge(역명 일치 시 무조건 연결)가 성남↔대구를 "환승 5분"으로 잘못 이어서
    성남 중원구→판교 소요시간이 대구를 경유한 44분으로 계산되는 사고가 났다.
    MIN_LAT(36.5, 대전 36.39와 장항선 36.77 사이의 빈 구간) 기준으로 걸러내면
    지방 노선은 완전히 빠져야 한다.
    """
    station_df = pd.DataFrame([
        # 대구 1호선 "신흥" — 지방, 제외되어야 함
        {"역사명": "신흥", "노선번호": "S3001", "노선명": "대구 도시철도 1호선",
         "역위도": 35.85, "역경도": 128.6},
        # 성남 8호선 "신흥" — 수도권, 남아야 함
        {"역사명": "신흥", "노선번호": "S1108", "노선명": "8호선",
         "역위도": 37.44, "역경도": 127.15},
    ])
    route_df = pd.DataFrame([
        {"노선번호": "S3001", "노선명": "대구 도시철도 1호선", "정거장구성": "1-신흥"},
        {"노선번호": "S1108", "노선명": "8호선", "정거장구성": "1-신흥"},
    ])
    station_xlsx = tmp_path / "station.xlsx"
    route_xlsx = tmp_path / "route.xlsx"
    station_df.to_excel(station_xlsx, index=False)
    route_df.to_excel(route_xlsx, index=False)

    stations = load_stations(station_xlsx=station_xlsx, route_xlsx=route_xlsx)

    assert (stations["lat"] >= MIN_LAT).all()
    assert "S3001" not in stations["line_code"].values
    assert "S1108" in stations["line_code"].values


def test_load_stations_recovers_orphan_line_code_via_unique_label(tmp_path):
    """역사정보의 노선번호가 노선정보에 아예 없는 '고아 코드'인데, 노선명이 노선정보에서
    유일한 노선번호에만 대응되면 그 코드로 대체 조회해 seq를 살려야 한다.

    실사용 중 발견: 역사정보의 분당선 역 36개 전부가 노선정보에 없는 코드 "I4105"를 달고
    있었고, 노선정보의 분당선 정거장구성은 실제로는 "I28K1" 아래 있었다. 이 보정이 없으면
    복정역(8호선↔분당선 환승역)의 분당선 쪽이 그래프에서 통째로 빠져, 성남 중원구→판교
    소요시간이 훨씬 먼 우회 경로(3호선·신분당선 환승)로 계산되는 부작용이 있었다.
    """
    station_df = pd.DataFrame([
        {"역사명": "복정", "노선번호": "I4105", "노선명": "분당선", "역위도": 37.4698, "역경도": 127.1266},
    ])
    route_df = pd.DataFrame([
        {"노선번호": "I28K1", "노선명": "수인선", "정거장구성": "1-고색"},
        {"노선번호": "I28K1", "노선명": "분당선", "정거장구성": "1-수서,2-복정,3-가천대"},
    ])
    station_xlsx = tmp_path / "station.xlsx"
    route_xlsx = tmp_path / "route.xlsx"
    station_df.to_excel(station_xlsx, index=False)
    route_df.to_excel(route_xlsx, index=False)

    stations = load_stations(station_xlsx=station_xlsx, route_xlsx=route_xlsx)

    row = stations.iloc[0]
    assert row["line_code"] == "I28K1", "고아 코드 I4105는 노선명 매칭으로 I28K1로 대체돼야 한다"
    # 같은 코드(I28K1)의 두 구간(수인선 1개 역 + 분당선)이 이어붙어 seq가 누적된다:
    # 고색=0(수인선 구간) -> 수서=1, 복정=2, 가천대=3(분당선 구간)
    assert row["seq"] == 2


def test_load_stations_does_not_fallback_when_label_ambiguous(tmp_path):
    """같은 노선명을 쓰는 노선번호가 노선정보에 둘 이상이면(예: 2호선 본선/지선) 대체 조회를
    하지 않아야 한다 — 잘못 합치면 지선을 본선인 것처럼 이어붙이게 된다."""
    station_df = pd.DataFrame([
        {"역사명": "용답", "노선번호": "ORPHAN", "노선명": "2호선", "역위도": 37.57, "역경도": 127.05},
    ])
    route_df = pd.DataFrame([
        {"노선번호": "S1102", "노선명": "2호선", "정거장구성": "1-강남,2-역삼"},
        {"노선번호": "S1121", "노선명": "2호선", "정거장구성": "1-용답,2-신답"},
    ])
    station_xlsx = tmp_path / "station.xlsx"
    route_xlsx = tmp_path / "route.xlsx"
    station_df.to_excel(station_xlsx, index=False)
    route_df.to_excel(route_xlsx, index=False)

    stations = load_stations(station_xlsx=station_xlsx, route_xlsx=route_xlsx)

    row = stations.iloc[0]
    assert row["line_code"] == "ORPHAN"
    assert pd.isna(row["seq"])
