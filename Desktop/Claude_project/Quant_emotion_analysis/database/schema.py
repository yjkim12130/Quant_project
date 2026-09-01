import sqlite3
from config import DB_PATH


DDL = """
CREATE TABLE IF NOT EXISTS stocks (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    market      TEXT NOT NULL CHECK(market IN ('KOSPI', 'KOSDAQ', 'NASDAQ')),
    active      INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS posts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code      TEXT NOT NULL,
    nid             TEXT NOT NULL,
    title           TEXT,
    content         TEXT,
    author          TEXT,
    post_date       TEXT,
    views           INTEGER DEFAULT 0,
    likes           INTEGER DEFAULT 0,
    dislikes        INTEGER DEFAULT 0,
    sentiment_score REAL,                   -- Phase 2에서 채워짐 (-1.0 ~ 1.0)
    crawled_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(stock_code, nid),
    FOREIGN KEY(stock_code) REFERENCES stocks(code)
);

CREATE INDEX IF NOT EXISTS idx_posts_stock_date ON posts(stock_code, post_date);
CREATE INDEX IF NOT EXISTS idx_posts_sentiment  ON posts(stock_code, sentiment_score);
"""


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(DDL)
    conn.commit()
    conn.close()
