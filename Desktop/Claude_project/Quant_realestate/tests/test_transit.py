import math

import pandas as pd

from ingest.fetch_transit import normalize_route_rows, build_edges, COLUMN_MAP, shortest_minutes, nearest_station, haversine_km

RAW_SAMPLE = [
    {"LNCD_NM": "2호선", "STIN_NM": "강남", "STIN_SEQ": "1", "LAT": "37.4979", "LOT": "127.0276"},
    {"LNCD_NM": "2호선", "STIN_NM": "역삼", "STIN_SEQ": "2", "LAT": "37.5006", "LOT": "127.0364"},
    {"LNCD_NM": "신분당선", "STIN_NM": "강남", "STIN_SEQ": "1", "LAT": "37.4979", "LOT": "127.0276"},
]


def test_normalize_route_rows_maps_known_columns():
    df = normalize_route_rows(RAW_SAMPLE)
    assert list(df.columns) == ["station_name", "line_name", "seq", "lat", "lon"]
    assert len(df) == 3
    assert df.iloc[0]["station_name"] == "강남"
    assert df.iloc[0]["lat"] == 37.4979


def test_normalize_route_rows_seq_is_int():
    df = normalize_route_rows(RAW_SAMPLE)
    assert df["seq"].dtype.kind in "iu"


def test_build_edges_creates_ride_edges_between_adjacent_seq():
    nodes = normalize_route_rows(RAW_SAMPLE)
    nodes["station_id"] = nodes["line_name"] + "_" + nodes["station_name"]
    edges = build_edges(nodes)
    ride = edges[edges["edge_type"] == "ride"]
    # 2호선 강남(seq1)-역삼(seq2) 인접 → 양방향 ride edge 2개
    assert len(ride) == 2
    assert set(ride["minutes"]) == {2.0}


def test_build_edges_creates_transfer_edges_for_same_station_name():
    nodes = normalize_route_rows(RAW_SAMPLE)
    nodes["station_id"] = nodes["line_name"] + "_" + nodes["station_name"]
    edges = build_edges(nodes)
    transfer = edges[edges["edge_type"] == "transfer"]
    # 2호선 강남 <-> 신분당선 강남 환승 → 양방향 2개
    assert len(transfer) == 2
    assert set(transfer["minutes"]) == {5.0}


def test_column_map_has_expected_keys():
    # 실제 API 응답이 다르면 이 4개 키의 매핑값만 조정하면 된다 (Global Constraints 참고)
    assert set(COLUMN_MAP) == {"station_name", "line_name", "seq", "lat", "lon"}


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
