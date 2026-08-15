import pandas as pd

from ingest.fetch_transit import normalize_route_rows, build_edges, COLUMN_MAP

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
