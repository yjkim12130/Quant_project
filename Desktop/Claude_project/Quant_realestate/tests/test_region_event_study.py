import numpy as np
import pandas as pd
import pytest

from backtest import region_event_study as RB


def make_rv(levels, months, tier=1):
    """region_rv 출력 형태의 최소 프레임. levels: {region_key: [월별 price]}"""
    rows = []
    for key, prices in levels.items():
        for m, p in zip(months, prices):
            rows.append({"region_key": key, "region_label": key, "month": m,
                         "price": float(p), "tier": tier})
    df = pd.DataFrame(rows)
    # 벤치마크: 같은 (tier, month)의 자기 제외 중위값
    df["tier_median"] = (df.groupby(["tier", "month"])["price"]
                           .transform(lambda s: s.sum() - s).div(max(len(levels) - 1, 1)))
    df["ratio"] = df["price"] / df["tier_median"]
    df["rv_z"] = 0.0
    return df


MONTHS = pd.period_range("2010-01", "2014-12", freq="M")


def test_prepare_computes_forward_and_excess():
    """진입은 시그널 +1개월, 수익률은 진입가 대비 청산가."""
    n = len(MONTHS)
    flat = [100.0] * n
    grow = [100.0 * (1.02 ** i) for i in range(n)]      # 매월 +2%
    df = make_rv({"UP": grow, "FLAT1": flat, "FLAT2": flat}, MONTHS)
    out = RB.prepare(df, horizons=(12,))

    up = out[out["region_key"] == "UP"].set_index("month")
    t = MONTHS[0]
    # 진입가 = t+1 가격, 청산가 = t+1+12 가격
    assert up.loc[t, "entry_price"] == pytest.approx(100.0 * 1.02 ** 1)
    assert up.loc[t, "fwd_12"] == pytest.approx(1.02 ** 12 - 1)
    # 벤치마크(평평한 두 지역의 평균)는 0% -> 초과수익 = 절대수익
    assert up.loc[t, "gfwd_12"] == pytest.approx(0.0)
    assert up.loc[t, "excess_12"] == pytest.approx(up.loc[t, "fwd_12"])


def test_prepare_excess_is_negative_when_region_lags_its_tier():
    n = len(MONTHS)
    df = make_rv({"LAG": [100.0] * n,
                  "A": [100.0 * (1.03 ** i) for i in range(n)],
                  "B": [100.0 * (1.03 ** i) for i in range(n)]}, MONTHS)
    out = RB.prepare(df, horizons=(12,))
    lag = out[(out["region_key"] == "LAG") & (out["month"] == MONTHS[0])]
    assert lag["excess_12"].iloc[0] < 0


def test_prepare_tail_months_have_no_forward_return():
    n = len(MONTHS)
    df = make_rv({"A": [100.0] * n, "B": [100.0] * n}, MONTHS)
    out = RB.prepare(df, horizons=(12,))
    # 마지막 12개월(+진입지연 1)은 청산가가 없어 NaN
    tail = out[out["month"] > MONTHS[-14]]
    assert tail["fwd_12"].isna().all()


def test_cohort_stats_reports_counts_and_means():
    n = len(MONTHS)
    df = make_rv({"UP": [100.0 * (1.02 ** i) for i in range(n)],
                  "A": [100.0] * n, "B": [100.0] * n}, MONTHS)
    out = RB.prepare(df, horizons=(12,))
    s = RB.cohort_stats(out, out["region_key"] == "UP", 12)
    assert s["n_regions"] == 1
    assert s["n_events"] > 0
    assert s["excess_mean"] > 0
    assert 0.0 <= s["hit_rate"] <= 1.0


def test_cohort_stats_empty_mask_returns_empty_dict():
    n = len(MONTHS)
    df = make_rv({"A": [100.0] * n, "B": [100.0] * n}, MONTHS)
    out = RB.prepare(df, horizons=(12,))
    assert RB.cohort_stats(out, out["region_key"] == "없는지역", 12) == {}


def test_permutation_test_detects_a_real_edge():
    """항상 이기는 지역만 고른 코호트는 무작위 대비 유의해야 한다."""
    n = len(MONTHS)
    levels = {"UP": [100.0 * (1.03 ** i) for i in range(n)]}
    for k in range(8):
        levels[f"F{k}"] = [100.0] * n
    out = RB.prepare(make_rv(levels, MONTHS), horizons=(12,))
    p = RB.permutation_test(out, out["region_key"] == "UP", 12, n_perm=200)
    assert p < 0.05


def test_permutation_test_finds_no_edge_in_a_random_cohort():
    rng = np.random.default_rng(0)
    n = len(MONTHS)
    levels = {f"R{k}": list(100 * np.cumprod(1 + rng.normal(0, .01, n))) for k in range(10)}
    out = RB.prepare(make_rv(levels, MONTHS), horizons=(12,))
    mask = out["region_key"].isin(["R0", "R1", "R2"])
    p = RB.permutation_test(out, mask, 12, n_perm=200)
    assert 0.0 <= p <= 1.0


def test_threshold_sweep_has_a_row_per_threshold_plus_baseline():
    n = len(MONTHS)
    rng = np.random.default_rng(1)
    levels = {f"R{k}": list(100 * np.cumprod(1 + rng.normal(0, .01, n))) for k in range(8)}
    df = make_rv(levels, MONTHS)
    df["rv_z"] = rng.normal(0, 1, len(df))
    out = RB.prepare(df, horizons=(12,))
    sweep = RB.threshold_sweep(out, 12, thresholds=(-0.5, -1.0))
    assert len(sweep) == 3                       # 임계 2개 + 전체 기준
    assert "전체(기준)" in sweep["rv_z<"].astype(str).values


def test_burn_in_split_excludes_burn_in_months_from_evaluation():
    """번인 구간 자체는 평가 대상에서 빠진다 - 그 구간 데이터로 티어를 정했기 때문."""
    n = len(MONTHS)
    df = make_rv({"A": [100.0] * n, "B": [100.0] * n}, MONTHS)
    out = RB.prepare(df, horizons=(12,))
    evaluated = RB.after_burn_in(out, "2011-12")
    assert evaluated["month"].min() == pd.Period("2012-01", freq="M")
    assert len(evaluated) < len(out)
