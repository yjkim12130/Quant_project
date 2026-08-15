"""SQLite 연결 및 스키마 — 모든 ingest 스크립트(fetch_trades/fetch_buildings/fetch_finance)가 공유"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "realestate.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades_sale (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region_code TEXT NOT NULL,
    region_name TEXT,
    dong_name TEXT,
    complex_name TEXT,
    apt_seq TEXT,
    jibun TEXT,
    exclusive_area REAL,
    contract_date TEXT,
    deal_amount INTEGER,
    floor INTEGER,
    build_year INTEGER,
    road_name TEXT,
    cancelled INTEGER DEFAULT 0,
    fetched_at TEXT,
    UNIQUE(region_code, dong_name, complex_name, jibun, exclusive_area, contract_date, deal_amount, floor)
);

CREATE TABLE IF NOT EXISTS trades_jeonse (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region_code TEXT NOT NULL,
    region_name TEXT,
    dong_name TEXT,
    complex_name TEXT,
    jibun TEXT,
    exclusive_area REAL,
    contract_date TEXT,
    deposit INTEGER,
    monthly_rent INTEGER,
    floor INTEGER,
    build_year INTEGER,
    contract_type TEXT,
    fetched_at TEXT,
    UNIQUE(region_code, dong_name, complex_name, jibun, exclusive_area, contract_date, deposit, monthly_rent, floor)
);

CREATE TABLE IF NOT EXISTS ingest_checkpoint (
    source TEXT NOT NULL,
    region_code TEXT NOT NULL,
    year_month TEXT NOT NULL,
    status TEXT NOT NULL,
    row_count INTEGER DEFAULT 0,
    error TEXT,
    fetched_at TEXT,
    PRIMARY KEY (source, region_code, year_month)
);

CREATE INDEX IF NOT EXISTS idx_sale_complex ON trades_sale(complex_name, region_code);
CREATE INDEX IF NOT EXISTS idx_sale_date ON trades_sale(contract_date);
CREATE INDEX IF NOT EXISTS idx_jeonse_complex ON trades_jeonse(complex_name, region_code);
CREATE INDEX IF NOT EXISTS idx_jeonse_date ON trades_jeonse(contract_date);

CREATE TABLE IF NOT EXISTS complex_coords (
    ckey TEXT PRIMARY KEY,
    region_code TEXT,
    address_used TEXT,
    lat REAL,
    lon REAL,
    geocoded_at TEXT
);

CREATE TABLE IF NOT EXISTS station_node (
    station_id TEXT PRIMARY KEY,
    station_name TEXT NOT NULL,
    line_name TEXT NOT NULL,
    seq INTEGER,
    lat REAL,
    lon REAL
);

CREATE TABLE IF NOT EXISTS station_edge (
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    minutes REAL NOT NULL,
    edge_type TEXT NOT NULL,
    PRIMARY KEY (from_id, to_id)
);

CREATE TABLE IF NOT EXISTS complex_transit_time (
    ckey TEXT NOT NULL,
    dest TEXT NOT NULL,
    minutes REAL,
    nearest_station TEXT,
    calculated_at TEXT,
    PRIMARY KEY (ckey, dest)
);

CREATE TABLE IF NOT EXISTS supply_presale (
    region_code TEXT NOT NULL,
    expected_ym TEXT NOT NULL,
    project_name TEXT,
    total_units INTEGER,
    source TEXT,
    fetched_at TEXT,
    PRIMARY KEY (region_code, expected_ym, project_name)
);
"""


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def is_done(conn, source, region_code, year_month):
    row = conn.execute(
        "SELECT status FROM ingest_checkpoint WHERE source=? AND region_code=? AND year_month=?",
        (source, region_code, year_month),
    ).fetchone()
    return row is not None and row[0] == "done"


def mark_checkpoint(conn, source, region_code, year_month, status, row_count=0, error=None):
    conn.execute(
        """INSERT INTO ingest_checkpoint (source, region_code, year_month, status, row_count, error, fetched_at)
           VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
           ON CONFLICT(source, region_code, year_month)
           DO UPDATE SET status=excluded.status, row_count=excluded.row_count,
                         error=excluded.error, fetched_at=excluded.fetched_at""",
        (source, region_code, year_month, status, row_count, error),
    )
    conn.commit()
