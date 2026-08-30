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


def _fake_index(levels, months, seed=0):
    """levels: {region_key: 기준 ㎡당가}. 지역마다 다른 로그정규 표류를 준다."""
    rng = np.random.default_rng(seed)
    rows = []
    for key, base in levels.items():
        drift = np.cumsum(rng.normal(0.002, 0.01, len(months)))
        for m, d in zip(months, drift):
            rows.append({"region_key": key, "region_label": key, "month": m,
                         "price": base * np.exp(d)})
    return pd.DataFrame(rows)


LEVELS7 = {"A": 3000, "B": 2500, "C": 2000, "D": 1500, "E": 1200, "F": 900, "G": 700}
MONTHS7 = pd.period_range("2018-01", "2024-12", freq="M")


def test_assign_tiers_orders_highest_price_as_tier_1():
    idx = _fake_index(LEVELS7, MONTHS7)
    t = R.assign_tiers(idx, n_tiers=3).set_index("region_key")
    assert t.loc["A", "tier"] == 1      # 가장 비싼 지역이 T1
    assert t.loc["G", "tier"] == 3      # 가장 싼 지역이 마지막 티어
    assert t["tier"].nunique() == 3


def test_assign_tiers_filters_short_history():
    idx = _fake_index(LEVELS7, MONTHS7)
    short = pd.concat([idx[idx["region_key"] != "A"],
                       idx[(idx["region_key"] == "A") & (idx["month"] < "2018-04")]])
    keys = R.assign_tiers(short, n_tiers=3, min_months=24)["region_key"].values
    assert "A" not in keys
    assert "B" in keys


def test_assign_tiers_handles_fewer_regions_than_tiers():
    idx = _fake_index({"A": 100, "B": 200}, MONTHS7)
    assert R.assign_tiers(idx, n_tiers=8)["tier"].nunique() == 2


def test_assign_tiers_empty_input_returns_empty():
    idx = _fake_index(LEVELS7, MONTHS7[:3])
    assert R.assign_tiers(idx, n_tiers=3, min_months=24).empty


def _naive_loo_median(s):
    v = s.to_numpy(dtype=float)
    return pd.Series([np.median(np.delete(v, i)) for i in range(len(v))], index=s.index)


def test_loo_median_matches_naive_implementation():
    rng = np.random.default_rng(1)
    for n in [2, 3, 4, 5, 6, 7, 12, 13, 40]:
        s = pd.Series(rng.normal(size=n))
        assert np.allclose(R._loo_median(s), _naive_loo_median(s), equal_nan=True), n


def test_loo_median_single_element_is_nan():
    assert R._loo_median(pd.Series([5.0])).isna().all()


def test_middle_region_of_odd_tier_gets_z():
    """자기포함 중위값이면 3개 티어의 가운데 지역은 ratio가 항상 1.0이라 z가 영구 NaN이 된다."""
    idx = _fake_index({"A": 3000, "B": 2500, "C": 2000}, MONTHS7)
    rv = R.region_rv(idx, R.assign_tiers(idx, n_tiers=1))
    assert rv[rv["region_key"] == "B"]["rv_z"].notna().any()


def test_no_look_ahead():
    idx = _fake_index(LEVELS7, MONTHS7)
    base = R.region_rv(idx, R.assign_tiers(idx, n_tiers=3))
    mod = idx.copy()
    mod.loc[(mod["region_key"] == "A") & (mod["month"] == MONTHS7[-1]), "price"] *= 1.5
    after = R.region_rv(mod, R.assign_tiers(mod, n_tiers=3))
    cut = MONTHS7[-1]
    b = base[(base["region_key"] == "A") & (base["month"] < cut)]["rv_z"].dropna().to_numpy()
    a = after[(after["region_key"] == "A") & (after["month"] < cut)]["rv_z"].dropna().to_numpy()
    assert np.allclose(a, b)


def test_short_history_region_is_dropped_not_crashing():
    idx = _fake_index(LEVELS7, MONTHS7)
    tiny = _fake_index({"Z": 1000}, MONTHS7[:3])
    combined = pd.concat([idx, tiny], ignore_index=True)
    rv = R.region_rv(combined, R.assign_tiers(combined, n_tiers=3, min_months=24))
    assert "Z" not in rv["region_key"].values


def test_rv_z_sign_convention_negative_is_cheap():
    """한 지역만 가격을 떨어뜨리면 그 지역의 최신 rv_z가 음수여야 한다."""
    idx = _fake_index(LEVELS7, MONTHS7)
    cheap = idx.copy()
    tail = cheap["month"] >= MONTHS7[-6]
    cheap.loc[(cheap["region_key"] == "D") & tail, "price"] *= 0.8
    rv = R.region_rv(cheap, R.assign_tiers(cheap, n_tiers=3))
    last = rv[(rv["region_key"] == "D") & (rv["month"] == MONTHS7[-1])]
    assert last["rv_z"].iloc[0] < 0


def test_pair_ratio_is_scale_invariant():
    idx = _fake_index(LEVELS7, MONTHS7)
    p1 = R.pair_ratio(idx, "A", "B")
    scaled = idx.copy()
    scaled.loc[scaled["region_key"] == "A", "price"] *= 7.0
    p2 = R.pair_ratio(scaled, "A", "B")
    assert np.allclose(p1["z"].dropna(), p2["z"].dropna())     # z는 곱셈 상수에 불변
    assert np.allclose(p2["ratio"], p1["ratio"] * 7.0)         # 비율 자체는 7배


def test_pair_ratio_uses_only_overlapping_months():
    idx = _fake_index(LEVELS7, MONTHS7)
    trimmed = idx[~((idx["region_key"] == "B") & (idx["month"] < "2020-01"))]
    p = R.pair_ratio(trimmed, "A", "B")
    assert p["month"].min() == pd.Period("2020-01", freq="M")


def test_region_jeonse_ratio_joins_to_sale_index():
    months = pd.period_range("2020-01", "2021-12", freq="M")
    df = make_trades([(a, b, p, 10) for a, b, p in NINE], months, "11470", "양천구", "목동")
    conn = _memory_db(df, "trades_sale")
    jeonse = df.copy()
    jeonse["deposit"] = jeonse["deal_amount"] * 0.6
    jeonse["monthly_rent"] = 0
    jeonse["contract_date"] = jeonse["month"].dt.to_timestamp().dt.strftime("%Y-%m-15")
    jeonse[["region_code", "region_name", "dong_name", "exclusive_area", "build_year",
            "contract_date", "deposit", "monthly_rent"]].to_sql("trades_jeonse", conn,
                                                                index=False)
    sale_index = R.region_price_index(conn, "sgg")
    out = R.region_jeonse_ratio(conn, sale_index, "sgg")
    assert len(out) == len(sale_index)
    assert out["jeonse_ratio"].dropna().round(3).eq(0.6).all()
    conn.close()


def test_region_jeonse_ratio_excludes_monthly_rent():
    months = pd.period_range("2020-01", "2021-12", freq="M")
    df = make_trades([(a, b, p, 10) for a, b, p in NINE], months, "11470", "양천구", "목동")
    conn = _memory_db(df, "trades_sale")
    jeonse = df.copy()
    jeonse["deposit"] = jeonse["deal_amount"] * 0.6
    jeonse["monthly_rent"] = 50            # 전부 월세 -> 전세가율은 전부 NaN
    jeonse["contract_date"] = jeonse["month"].dt.to_timestamp().dt.strftime("%Y-%m-15")
    jeonse[["region_code", "region_name", "dong_name", "exclusive_area", "build_year",
            "contract_date", "deposit", "monthly_rent"]].to_sql("trades_jeonse", conn,
                                                                index=False)
    out = R.region_jeonse_ratio(conn, R.region_price_index(conn, "sgg"), "sgg")
    assert out["jeonse_ratio"].isna().all()
    conn.close()
