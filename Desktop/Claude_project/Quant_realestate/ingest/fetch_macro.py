"""매크로 레짐용 시계열 적재 — docs/regime_spec_v1.md §2, §7-1

적재 시리즈 (macro_series 테이블, 전량 갱신 방식 — 소량이라 체크포인트 불필요):
    ecos_base_rate      한국은행 기준금리 (722Y001/0101000, 2003-01~)
    ecos_m2             M2 평잔 원계열 (161Y006/BBHA00, 2003-10~)
    reb_apt_index       부동산원 (월) 매매가격지수_아파트, 수도권 (A_2024_00045/CLS 500002, 2003-11~)
    reb_supply_demand   부동산원 (월) 매매수급동향_아파트, 수도권 (A_2024_00076/CLS 500002, 2012~)
    reb_sentiment       부동산원 주택시장 소비심리지수, 서울·경기 평균 (T232543129897499, 2011-07~)

사용법: python ingest/fetch_macro.py
"""
import sys
import time
from pathlib import Path

import pandas as pd
import requests
import yaml
import PublicDataReader as pdr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_connection  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
API_KEYS_YAML = ROOT / "config" / "api_keys.local.yaml"

MACRO_SCHEMA = """
CREATE TABLE IF NOT EXISTS macro_series (
    series TEXT NOT NULL,
    ym TEXT NOT NULL,          -- YYYYMM
    value REAL,
    fetched_at TEXT,
    PRIMARY KEY (series, ym)
);
"""

REB_URL = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"


def load_keys():
    with open(API_KEYS_YAML, encoding="utf-8") as f:
        keys = yaml.safe_load(f)
    return keys["ecos"]["api_key"], keys["r_one"]["api_key"]


def fetch_ecos(api, table, item, start="200301", end=None):
    end = end or pd.Timestamp.now().strftime("%Y%m")
    df = api.get_statistic_search(통계표코드=table, 주기="M",
                                  검색시작일자=start, 검색종료일자=end, 통계항목코드1=item)
    if df is None or df.empty:
        raise RuntimeError(f"ECOS {table}/{item} 응답 없음")
    out = df[["시점", "값"]].copy()
    out.columns = ["ym", "value"]
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    return out.dropna()


def fetch_reb(key, statbl_id, cls_ids=None, cls_names=None):
    """R-ONE 표 데이터 전체 페이징 수집 후 (ym, value)로 정리.
    cls_ids로 서버 필터 시도, 실패 시 cls_names로 클라이언트 필터."""
    rows = []
    for cls_id in (cls_ids or [None]):
        pindex = 1
        while True:
            params = {"KEY": key, "Type": "json", "pIndex": pindex, "pSize": 1000,
                      "STATBL_ID": statbl_id, "DTACYCLE_CD": "MM"}
            if cls_id:
                params["CLS_ID"] = cls_id
            r = requests.get(REB_URL, params=params, timeout=30).json()
            body = r.get("SttsApiTblData", [])
            if len(body) < 2 or "row" not in body[1]:
                break
            page = body[1]["row"]
            rows.extend(page)
            total = body[0]["head"][0]["list_total_count"]
            if pindex * 1000 >= total:
                break
            pindex += 1
            time.sleep(0.2)
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError(f"R-ONE {statbl_id} 응답 없음")
    if cls_names:
        df = df[df["CLS_NM"].isin(cls_names)]
    df = df[df["ITM_NM"] == "지수"]
    df["value"] = pd.to_numeric(df["DTA_VAL"], errors="coerce")
    out = (df.groupby("WRTTIME_IDTFR_ID")["value"].mean()  # 복수 지역(서울·경기)이면 평균
             .reset_index().rename(columns={"WRTTIME_IDTFR_ID": "ym"}))
    return out.dropna()


def upsert(conn, series, df):
    now = pd.Timestamp.utcnow().isoformat()
    conn.executemany(
        "INSERT INTO macro_series (series, ym, value, fetched_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(series, ym) DO UPDATE SET value=excluded.value, fetched_at=excluded.fetched_at",
        [(series, str(r.ym), float(r.value), now) for r in df.itertuples()])
    conn.commit()
    print(f"  {series}: {len(df)}개월 ({df['ym'].min()}~{df['ym'].max()})")


# 크로스에셋 비교용 (yfinance 월말 종가) — 자산 비교 탭
YF_ASSETS = {"asset_kospi": "^KS11", "asset_nasdaq": "^IXIC",
             "asset_gold": "GC=F", "asset_btc": "BTC-USD"}


def fetch_yf(ticker, start="2003-01-01"):
    import yfinance as yf
    px = yf.download(ticker, start=start, interval="1mo", progress=False, auto_adjust=True)
    if px is None or px.empty:
        raise RuntimeError(f"yfinance {ticker} 응답 없음")
    close = px["Close"]
    if hasattr(close, "columns"):  # 멀티컬럼 방어
        close = close.iloc[:, 0]
    out = close.dropna().reset_index()
    out.columns = ["date", "value"]
    out["ym"] = pd.to_datetime(out["date"]).dt.strftime("%Y%m")
    return out[["ym", "value"]]


def main():
    ecos_key, reb_key = load_keys()
    conn = get_connection()
    conn.executescript(MACRO_SCHEMA)

    print("ECOS 적재...")
    ecos = pdr.Ecos(service_key=ecos_key)
    upsert(conn, "ecos_base_rate", fetch_ecos(ecos, "722Y001", "0101000"))
    upsert(conn, "ecos_m2", fetch_ecos(ecos, "161Y006", "BBHA00"))

    print("R-ONE 적재...")
    upsert(conn, "reb_apt_index", fetch_reb(reb_key, "A_2024_00045", cls_ids=["500002"]))
    upsert(conn, "reb_supply_demand", fetch_reb(reb_key, "A_2024_00076", cls_ids=["500002"]))
    upsert(conn, "reb_sentiment", fetch_reb(reb_key, "T232543129897499", cls_names=["서울", "경기"]))

    print("자산 시세 적재 (yfinance)...")
    for series, ticker in YF_ASSETS.items():
        try:
            upsert(conn, series, fetch_yf(ticker))
        except Exception as e:  # noqa: BLE001 — 개별 자산 실패가 전체를 막지 않도록
            print(f"  [실패] {series}({ticker}): {e}")

    conn.close()
    print("완료")


if __name__ == "__main__":
    main()
