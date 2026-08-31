"""지역(급지) 레벨 백테스트 — docs/region_tier_spec_v1.md §7 구현

단지 백테스트(backtest/event_study.py)와 같은 질문을 지역 단위로 묻는다:
급지 대비 저평가(rv_z가 음수)로 찍힌 지역이 이후 실제로 같은 급지의 다른 지역보다
더 올랐는가?

방법론:
- 시점 t 시그널 -> t+1개월 진입(신고지연 반영) -> h개월 보유 -> 수익률
- 벤치마크 = 그 지역이 속한 급지의 leave-one-out 중위가 수익률.
  라이브 화면에서 ratio의 분모로 쓰는 값과 같은 계열이라 해석이 일관된다.
- 순열검정: 같은 이벤트 월 분포에서 무작위 지역을 뽑았을 때 대비 유의한가

look-ahead 차단 (이 백테스트의 존재 이유):
  assign_tiers는 라이브에서 전 기간 평균으로 급지를 정한다. 그대로 백테스트에 쓰면
  2010년 시그널을 2026년 가격으로 만든 급지로 평가하게 된다. 그래서 번인 구간
  (기본 2006-01~2010-12)의 데이터로만 티어를 정해 고정하고, 번인 이후 월만 평가한다.
  진단을 위해 전 기간 티어(누수 포함) 버전도 함께 돌려 격차를 보고한다 - 격차가 크면
  결과의 상당 부분이 사후 지식이었다는 뜻이다.

비용 모델은 없다. "구를 산다"는 거래가 존재하지 않으므로 취득세·중개보수를 붙이는 것이
의미가 없다. 급지 대비 초과수익만 본다.

사용법:
    python backtest/region_event_study.py                    # 구 단위 전체 리포트
    python backtest/region_event_study.py --level dong       # 동 단위
    python backtest/region_event_study.py --horizon 24
"""
import argparse
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scoring.engine import DB_PATH, Params  # noqa: E402
from scoring.region_rv import (assign_tiers, region_price_index, region_rv)  # noqa: E402

ENTRY_LAG = 1                 # 시그널 후 진입까지 지연 (개월)
DEFAULT_HORIZONS = (12, 24, 36)
BURN_IN_END = "2010-12"       # 이 월까지의 데이터로만 티어를 정하고, 이후를 평가한다
DEFAULT_THRESHOLDS = (-0.5, -1.0, -1.5, -2.0, -2.5)


def prepare(rv: pd.DataFrame, horizons=DEFAULT_HORIZONS) -> pd.DataFrame:
    """지역 시계열에 전방 수익률·급지 전방 수익률·초과수익 컬럼 추가.

    rv: region_rv() 출력 (region_key, month, price, tier, tier_median, rv_z ...)
    """
    df = rv.sort_values(["region_key", "month"]).copy()
    g = df.groupby("region_key", observed=True)
    df["entry_price"] = g["price"].shift(-ENTRY_LAG)
    df["entry_gprice"] = g["tier_median"].shift(-ENTRY_LAG)
    for h in horizons:
        exit_p = g["price"].shift(-(ENTRY_LAG + h))
        exit_gp = g["tier_median"].shift(-(ENTRY_LAG + h))
        df[f"fwd_{h}"] = exit_p / df["entry_price"] - 1
        df[f"gfwd_{h}"] = exit_gp / df["entry_gprice"] - 1
        df[f"excess_{h}"] = df[f"fwd_{h}"] - df[f"gfwd_{h}"]
    return df


def after_burn_in(df: pd.DataFrame, burn_in_end=BURN_IN_END) -> pd.DataFrame:
    """번인 구간을 평가에서 제외한다. 그 구간 데이터로 티어를 정했기 때문."""
    return df[df["month"] > pd.Period(burn_in_end, freq="M")]


def cohort_stats(df: pd.DataFrame, mask: pd.Series, h: int) -> dict:
    """시그널 코호트의 h개월 성과 요약."""
    col_abs, col_ex = f"fwd_{h}", f"excess_{h}"
    sub = df.loc[mask].dropna(subset=[col_ex])
    if sub.empty:
        return {}
    return {
        "n_events": len(sub),
        "n_regions": sub["region_key"].nunique(),
        "abs_mean": sub[col_abs].mean(),
        "excess_mean": sub[col_ex].mean(),
        "excess_median": sub[col_ex].median(),
        "hit_rate": (sub[col_ex] > 0).mean(),
    }


def permutation_test(df: pd.DataFrame, mask: pd.Series, h: int, n_perm: int = 500,
                     seed: int = 42) -> float:
    """같은 이벤트 월 분포에서 무작위 지역을 뽑아 코호트 평균 초과수익과 비교. p-value."""
    col = f"excess_{h}"
    valid = df.dropna(subset=[col])
    cohort = valid[mask.reindex(valid.index, fill_value=False)]
    if cohort.empty:
        return np.nan
    obs = cohort[col].mean()
    month_counts = cohort.groupby("month").size()
    rng = np.random.default_rng(seed)
    by_month = {m: g[col].to_numpy() for m, g in valid.groupby("month")
                if m in month_counts.index}
    sims = np.empty(n_perm)
    for i in range(n_perm):
        draws = [rng.choice(by_month[m], size=min(k, len(by_month[m])), replace=False)
                 for m, k in month_counts.items() if m in by_month]
        sims[i] = np.concatenate(draws).mean() if draws else np.nan
    return float(np.nanmean(sims >= obs))   # H1: 코호트가 무작위보다 높다


def threshold_sweep(df: pd.DataFrame, h: int, thresholds=DEFAULT_THRESHOLDS) -> pd.DataFrame:
    """rv_z 임계 스윕. 임계가 깊을수록 초과수익이 커지면 신호가 단조적이라는 근거."""
    keys = ("n_events", "n_regions", "excess_mean", "excess_median", "hit_rate")
    rows = []
    for th in thresholds:
        s = cohort_stats(df, df["rv_z"] < th, h)
        if s:
            rows.append({"rv_z<": th, **{k: s[k] for k in keys}})
    base = cohort_stats(df, df["rv_z"].notna(), h)
    if base:
        rows.append({"rv_z<": "전체(기준)", **{k: base[k] for k in keys}})
    return pd.DataFrame(rows)


def build_panel(level="sgg", n_tiers=5, burn_in_end=BURN_IN_END, params=None, db_path=DB_PATH):
    """번인 티어와 전기간 티어 두 벌의 rv 패널을 만든다.

    반환: dict(index=지역 지수, burn_in=번인 티어 패널, full=전기간 티어 패널,
              tiers_burn_in=..., tiers_full=...)
    """
    params = params or Params()
    conn = sqlite3.connect(db_path)
    try:
        idx = region_price_index(conn, level, params)
    finally:
        conn.close()
    tiers_bi = assign_tiers(idx, n_tiers=n_tiers, as_of=burn_in_end)
    tiers_full = assign_tiers(idx, n_tiers=n_tiers)
    return {
        "index": idx,
        "tiers_burn_in": tiers_bi,
        "tiers_full": tiers_full,
        "burn_in": region_rv(idx, tiers_bi, params),
        "full": region_rv(idx, tiers_full, params),
    }


def run_region_backtest(level="sgg", n_tiers=5, horizons=DEFAULT_HORIZONS, n_perm=500,
                        burn_in_end=BURN_IN_END, params=None, panel=None, db_path=DB_PATH):
    """번인 티어(주 결과)와 전기간 티어(look-ahead 진단)를 모두 산출."""
    params = params or Params()
    panel = panel or build_panel(level, n_tiers, burn_in_end, params, db_path)

    out = {"level": level, "n_tiers": n_tiers, "horizons": list(horizons),
           "burn_in_end": burn_in_end, "variants": {}, "panel": panel}

    for name in ("burn_in", "full"):
        df = after_burn_in(prepare(panel[name], horizons), burn_in_end)
        v = {"df": df, "cohorts": {}, "sweep": {}, "pvalue": {}}
        signal = df["rv_z"] < params.rv_buy_z
        for h in horizons:
            v["cohorts"][h] = {
                f"rv_z<{params.rv_buy_z}": cohort_stats(df, signal, h),
                "전체(기준)": cohort_stats(df, df["rv_z"].notna(), h),
            }
            v["sweep"][h] = threshold_sweep(df, h)
            v["pvalue"][h] = permutation_test(df, signal, h, n_perm)
        out["variants"][name] = v
    return out


def print_report(res: dict):
    pct = lambda v: f"{v * 100:+.1f}%"  # noqa: E731
    lv = "시군구" if res["level"] == "sgg" else "법정동"
    bi = res["variants"]["burn_in"]
    fu = res["variants"]["full"]
    n_bi = len(res["panel"]["tiers_burn_in"])
    n_fu = len(res["panel"]["tiers_full"])

    print(f"\n{'=' * 74}")
    print(f"지역 레벨 백테스트 - {lv} {res['n_tiers']}급지 "
          f"(진입: 시그널 +{ENTRY_LAG}개월)")
    print(f"티어 산정: 번인 ~{res['burn_in_end']} ({n_bi}개 지역) / "
          f"전기간 ({n_fu}개 지역, look-ahead 진단용)")
    print(f"평가 구간: {res['burn_in_end']} 이후")
    print("=" * 74)

    for h in res["horizons"]:
        print(f"\n[보유 {h}개월]")
        print(f"{'티어 산정':<12}{'코호트':<16}{'이벤트':>8}{'지역':>6}"
              f"{'절대평균':>10}{'초과평균':>10}{'초과중위':>10}{'승률':>8}")
        for label, v in (("번인(주결과)", bi), ("전기간(진단)", fu)):
            for name, s in v["cohorts"][h].items():
                if s:
                    print(f"{label:<12}{name:<16}{s['n_events']:>8,}{s['n_regions']:>6}"
                          f"{pct(s['abs_mean']):>10}{pct(s['excess_mean']):>10}"
                          f"{pct(s['excess_median']):>10}{s['hit_rate'] * 100:>7.1f}%")

        pb, pf = bi["pvalue"][h], fu["pvalue"][h]
        print(f"\n순열검정 p-value: 번인={pb:.3f} / 전기간={pf:.3f}")

        sb = bi["cohorts"][h].get(f"rv_z<-1.0", {})
        sf = fu["cohorts"][h].get(f"rv_z<-1.0", {})
        if sb and sf:
            gap = (sf["excess_mean"] - sb["excess_mean"]) * 100
            print(f"look-ahead 격차: 전기간 초과평균이 번인보다 {gap:+.1f}%p "
                  f"({'사후 지식 기여분' if gap > 0 else '오히려 낮음'})")

        print(f"\n임계 스윕 (번인 티어):")
        print(bi["sweep"][h].round(3).to_string(index=False))

    print(f"\n※ 벤치마크는 소속 급지의 leave-one-out 중위가. 비용 모델 없음"
          f"(지역 자체를 매매하는 거래가 없으므로).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", choices=("sgg", "dong"), default="sgg")
    ap.add_argument("--n-tiers", type=int, default=5)
    ap.add_argument("--horizon", type=int, default=None)
    ap.add_argument("--n-perm", type=int, default=500)
    ap.add_argument("--burn-in-end", default=BURN_IN_END)
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    horizons = (args.horizon,) if args.horizon else DEFAULT_HORIZONS
    res = run_region_backtest(level=args.level, n_tiers=args.n_tiers, horizons=horizons,
                              n_perm=args.n_perm, burn_in_end=args.burn_in_end)
    print_report(res)


if __name__ == "__main__":
    main()
