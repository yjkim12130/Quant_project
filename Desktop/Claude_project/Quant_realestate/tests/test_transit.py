import pandas as pd

from ingest.fetch_transit import normalize_route_rows, build_edges, COLUMN_MAP, shortest_minutes

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
    """가중 다익스트라 동작 확인: hop 수가 적어도 가중치가 크면 더 오래 걸린 경로를 버림.

    그래프:
    A -100min-> B -1min-> C  (2 hops, 101분)
    A -50min-> D -50min-> C  (2 hops, 100분)
    A -99min-> C             (1 hop, 99분) <- 최단

    BFS라면 1-hop 경로를 항상 선택할 수 없으므로 가중치를 제대로 고려해야 함.
    """
    adj = {
        "A": [("B", 100.0), ("D", 50.0), ("C", 99.0)],
        "B": [("C", 1.0)],
        "D": [("C", 50.0)],
    }
    result = shortest_minutes(adj, "A", ["C"])
    assert result["C"] == 99.0, f"Expected 99.0 (direct A->C), got {result['C']}"


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
