import sqlite3
import contextlib
from typing import Generator
from config import DB_PATH


@contextlib.contextmanager
def get_conn() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_stock(code: str, name: str, market: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO stocks(code, name, market)
            VALUES(?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET name=excluded.name, market=excluded.market
            """,
            (code, name, market),
        )


def get_active_stocks() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT code, name, market FROM stocks WHERE active=1"
        ).fetchall()
    return [dict(r) for r in rows]


def insert_posts(posts: list[dict]) -> int:
    """INSERT OR IGNORE — 중복 nid 는 건너뜀. 삽입된 행 수 반환."""
    if not posts:
        return 0
    inserted = 0
    with get_conn() as conn:
        for p in posts:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO posts
                    (stock_code, nid, title, content, author, post_date, views, likes, dislikes)
                VALUES
                    (:stock_code, :nid, :title, :content, :author, :post_date, :views, :likes, :dislikes)
                """,
                p,
            )
            inserted += cur.rowcount
    return inserted


def get_posts_without_sentiment(limit: int = 200) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, stock_code, title, content
            FROM posts
            WHERE sentiment_score IS NULL AND (title IS NOT NULL OR content IS NOT NULL)
            ORDER BY id
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def update_sentiment(post_id: int, score: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE posts SET sentiment_score=? WHERE id=?", (score, post_id)
        )


def get_latest_nid(stock_code: str) -> str | None:
    """이미 저장된 가장 최신 nid (중복 크롤링 조기 종료용)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT nid FROM posts WHERE stock_code=? ORDER BY CAST(nid AS INTEGER) DESC LIMIT 1",
            (stock_code,),
        ).fetchone()
    return row["nid"] if row else None
