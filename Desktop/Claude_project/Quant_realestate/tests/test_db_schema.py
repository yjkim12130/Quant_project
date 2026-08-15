import sqlite3

from ingest.db import SCHEMA

NEW_TABLES = {
    "complex_coords", "station_node", "station_edge",
    "complex_transit_time", "supply_presale",
}


def test_schema_creates_new_tables(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    existing = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    missing = NEW_TABLES - existing
    assert not missing, f"누락된 테이블: {missing}"
    conn.close()


def test_complex_coords_ckey_is_primary_key(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    cols = conn.execute("PRAGMA table_info(complex_coords)").fetchall()
    pk_cols = [c[1] for c in cols if c[5] == 1]  # c[5] = pk 순번(1부터), 0이면 아님
    assert pk_cols == ["ckey"]
    conn.close()
