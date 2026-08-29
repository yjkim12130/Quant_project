import numpy as np
import pandas as pd
import pytest

from scoring import region_rv as R
from scoring.engine import Params

P = Params()

# 9개 셀이 서로 완전히 분리되도록 설계(면적 3밴드 x 연식 3밴드). 2020~2021년 기준
# 2015년생=~10y, 2007년생=10~25y, 1990년생=25y~ 로 밀리지 않게 떨어져 있다.
NEW, MID, OLD = 2015, 2007, 1990
NINE = [(50, NEW, 2000), (70, NEW, 2200), (100, NEW, 2400),
        (50, MID, 1400), (70, MID, 1500), (100, MID, 1600),
        (50, OLD, 800), (70, OLD, 900), (100, OLD, 1000)]


def make_trades(spec, months, region="11110", region_name="종로구", dong="가"):
    """spec: [(전용면적, 건축년도, ㎡당가, 건수 또는 i->건수 함수)] -> 합성 실거래 DataFrame"""
    rows = []
    for i, m in enumerate(months):
        for area, by, ppa, n_fn in spec:
            n = n_fn(i) if callable(n_fn) else n_fn
            for _ in range(n):
                rows.append({"region_code": region, "region_name": region_name,
                             "dong_name": dong, "exclusive_area": area,
                             "build_year": by, "month": m, "deal_amount": ppa * area})
    df = pd.DataFrame(rows)
    df["region_key"] = R._region_key(df, "sgg")
    return df


def test_fixed_basket_removes_composition_effect():
    """셀별 가격은 고정한 채 신축 셀의 거래 건수만 폭증시킨다."""
    months = pd.period_range("2020-01", "2021-12", freq="M")
    spec = [(a, b, p, (lambda i: 10 + i * 20) if b == NEW else 10) for a, b, p in NINE]
    df = make_trades(spec, months)
    idx = R._basket_index(df, "deal_amount", P, 0.5)
    naive = (df.assign(sp=df["deal_amount"] / df["exclusive_area"])
               .groupby("month")["sp"].median())
    assert naive.iloc[-1] / naive.iloc[0] - 1 > 0.10          # 단순 중위는 구성효과로 상승
    assert idx["price"].std() == pytest.approx(0, abs=1e-9)   # 바스켓은 완전히 평평


def test_weight_gate_drops_thin_months():
    """가중치 w는 전달받은 거래 전체에서 계산된다 - 그래서 한 셀뿐인 지역은 탈락한다."""
    months = pd.period_range("2020-01", "2020-06", freq="M")
    full = make_trades([(a, b, p, 10) for a, b, p in NINE], months, "11110", "종로구")
    thin = make_trades([(50, NEW, 2000, 10)], months, "11140", "중구")
    df = pd.concat([full, thin], ignore_index=True)
    strict = R._basket_index(df, "deal_amount", P, 0.5)
    assert set(strict["region_key"]) == {"11110"}
    loose = R._basket_index(df, "deal_amount", P, 0.05)
    assert set(loose["region_key"]) == {"11110", "11140"}


def test_cell_level_rolling_lifts_w_valid():
    """어떤 셀에 t월 거래가 없어도 셀 단위 롤링 덕에 w_valid가 유지된다."""
    months = pd.period_range("2020-01", "2020-06", freq="M")
    spec = [(a, b, p, (lambda i: 10 if i != 3 else 0)) for a, b, p in NINE[:3]] + \
           [(a, b, p, 10) for a, b, p in NINE[3:]]
    df = make_trades(spec, months)
    idx = R._basket_index(df, "deal_amount", P, 0.0).set_index("month")
    assert idx.loc[months[3], "w_valid"] == pytest.approx(idx.loc[months[2], "w_valid"])


def test_dong_key_separates_same_name_in_different_sgg():
    months = pd.period_range("2020-01", "2020-12", freq="M")
    a = make_trades([(x, y, z, 10) for x, y, z in NINE], months, "11110", "종로구", "중동")
    b = make_trades([(x, y, z * 2, 10) for x, y, z in NINE], months, "41190", "부천시", "중동")
    df = pd.concat([a, b], ignore_index=True)
    df["region_key"] = R._region_key(df, "dong")
    assert R._basket_index(df, "deal_amount", P, 0.5)["region_key"].nunique() == 2


def test_level_validation():
    with pytest.raises(ValueError):
        R._check_level("gu")


import sqlite3


def _memory_db(df, table="trades_sale"):
    conn = sqlite3.connect(":memory:")
    out = df.copy()
    out["contract_date"] = out["month"].dt.to_timestamp().dt.strftime("%Y-%m-15")
    cols = ["region_code", "region_name", "dong_name", "exclusive_area",
            "build_year", "contract_date"]
    if table == "trades_sale":
        out["cancelled"] = 0
        cols += ["deal_amount", "cancelled"]
    else:
        out["deposit"] = out["deal_amount"] * 0.6
        out["monthly_rent"] = 0
        cols += ["deposit", "monthly_rent"]
    out[cols].to_sql(table, conn, index=False)
    return conn


def test_region_price_index_reads_db_and_labels():
    months = pd.period_range("2020-01", "2021-12", freq="M")
    df = make_trades([(a, b, p, 10) for a, b, p in NINE], months, "11470", "양천구", "목동")
    conn = _memory_db(df)
    idx = R.region_price_index(conn, "sgg")
    assert set(idx["region_key"]) == {"11470"}
    assert idx["region_label"].iloc[0] == "양천구"
    assert len(idx) == len(months)

    idx_dong = R.region_price_index(conn, "dong")
    assert idx_dong["region_key"].iloc[0] == "11470|목동"
    assert idx_dong["region_label"].iloc[0] == "양천구 목동"
    conn.close()


def test_region_price_index_excludes_cancelled():
    months = pd.period_range("2020-01", "2020-12", freq="M")
    df = make_trades([(a, b, p, 10) for a, b, p in NINE], months, "11470", "양천구", "목동")
    conn = _memory_db(df)
    conn.execute("UPDATE trades_sale SET cancelled = 1")
    conn.commit()
    assert R.region_price_index(conn, "sgg").empty
    conn.close()


def test_region_price_index_rejects_bad_level():
    months = pd.period_range("2020-01", "2020-12", freq="M")
    conn = _memory_db(make_trades([(a, b, p, 10) for a, b, p in NINE], months))
    with pytest.raises(ValueError):
        R.region_price_index(conn, "gu")
    conn.close()
