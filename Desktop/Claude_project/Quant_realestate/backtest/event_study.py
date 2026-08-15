"""매수시그널 전략 백테스트 (event study) — docs/algo_spec_v1.md §6 구현

질문 두 개에 답한다:
1. 팩터(rv_z, jr_z, dd, mom12)가 예측력 있는 변수인가 → 월별 IC(Spearman) 분석
2. 임계값을 어디에 둬야 하나 → rv_z 임계 스윕별 초과수익

방법론:
- 시점 t 시그널 → t+1개월 진입(신고지연 반영) → h개월 보유 → 수익률
- 벤치마크 = 소속 그룹 중위가의 동일 기간 수익률 → 초과수익(excess) = 단지 - 그룹
  ("5년 상승장에서 아무거나 사도 올랐다" 착시 제거)
- 순열검정: 같은 이벤트 월에서 무작위 단지를 뽑았을 때 대비 시그널 코호트가 유의하게 나은가

사용법:
    python backtest/event_study.py                 # 전체 리포트
    python backtest/event_study.py --horizon 24    # 특정 보유기간만
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sstats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scoring.engine import Params, build_scored_panel  # noqa: E402

ENTRY_LAG = 1          # 시그널 후 진입까지 지연 (개월) — 신고지연·의사결정 시차
DEFAULT_HORIZONS = (12, 24, 36)
FACTORS = ["rv_z", "jr_z", "dd", "mom12"]

# 단순 비용 모델 (스펙 G4): 절대수익률에서 차감. 그룹 대비 초과수익엔 영향 없음(양쪽 동일 적용 가정).
BUY_COST_PCT = 0.019   # 취득세 1.1%(6억~9억 1주택 근사) + 중개보수 0.4% + 법무 등 0.4%
SELL_COST_PCT = 0.004  # 중개보수 (양도세는 보유기간·비과세 여부 따라 별도 — v1 미반영 명시)


def prepare(df: pd.DataFrame, horizons=DEFAULT_HORIZONS) -> pd.DataFrame:
    """(ckey, band) 시계열에 전방 수익률·그룹 전방 수익률·초과수익 컬럼 추가."""
    df = df.sort_values(["ckey", "area_band", "month"]).copy()
    g = df.groupby(["ckey", "area_band"], observed=True)
    # 진입가: t+LAG 시점 가격
    df["entry_price"] = g["price"].shift(-ENTRY_LAG)
    df["entry_gprice"] = g["group_price"].shift(-ENTRY_LAG)
    for h in horizons:
        exit_p = g["price"].shift(-(ENTRY_LAG + h))
        exit_gp = g["group_price"].shift(-(ENTRY_LAG + h))
        df[f"fwd_{h}"] = exit_p / df["entry_price"] - 1
        df[f"gfwd_{h}"] = exit_gp / df["entry_gprice"] - 1
        df[f"excess_{h}"] = df[f"fwd_{h}"] - df[f"gfwd_{h}"]
    return df


def cohort_stats(df: pd.DataFrame, mask: pd.Series, h: int) -> dict:
    """시그널 코호트의 h개월 성과 요약."""
    col_abs, col_ex = f"fwd_{h}", f"excess_{h}"
    sub = df.loc[mask].dropna(subset=[col_ex])
    if sub.empty:
        return {}
    return {
        "n_events": len(sub),
        "n_complexes": sub["ckey"].nunique(),
        "abs_mean": sub[col_abs].mean(), "abs_median": sub[col_abs].median(),
        "excess_mean": sub[col_ex].mean(), "excess_median": sub[col_ex].median(),
        "hit_rate": (sub[col_ex] > 0).mean(),
        "abs_mean_after_cost": sub[col_abs].mean() - BUY_COST_PCT - SELL_COST_PCT,
    }


def permutation_test(df: pd.DataFrame, mask: pd.Series, h: int, n_perm: int = 500,
                     seed: int = 42) -> float:
    """같은 이벤트 월 분포에서 무작위 단지를 뽑아 코호트 평균 초과수익을 비교. p-value 반환."""
    col = f"excess_{h}"
    valid = df.dropna(subset=[col])
    cohort = valid[mask.reindex(valid.index, fill_value=False)]
    if cohort.empty:
        return np.nan
    obs = cohort[col].mean()
    month_counts = cohort.groupby("month").size()
    rng = np.random.default_rng(seed)
    by_month = {m: g[col].to_numpy() for m, g in valid.groupby("month") if m in month_counts.index}
    sims = np.empty(n_perm)
    for i in range(n_perm):
        draws = [rng.choice(by_month[m], size=min(k, len(by_month[m])), replace=False)
                 for m, k in month_counts.items()]
        sims[i] = np.concatenate(draws).mean()
    return float((sims >= obs).mean())  # H1: 코호트가 무작위보다 높다


def factor_ic(df: pd.DataFrame, h: int) -> pd.DataFrame:
    """월별 크로스섹션 Spearman IC (팩터값 t ↔ 초과수익 t~t+h). Fama-MacBeth 방식 평균/유의성.

    부호 해석: rv_z·dd는 낮을수록 좋다는 가설 → IC가 음수면 가설 방향과 일치.
    """
    import warnings
    col = f"excess_{h}"
    rows = []
    for f in FACTORS:
        ics = []
        for m, g in df.dropna(subset=[f, col]).groupby("month"):
            if len(g) >= 30:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")  # 상수 입력 월은 NaN으로 걸러짐
                    ic = sstats.spearmanr(g[f], g[col]).statistic
                if not np.isnan(ic):
                    ics.append(ic)
        if len(ics) >= 6:
            ics = np.array(ics)
            t_stat = ics.mean() / (ics.std(ddof=1) / np.sqrt(len(ics)))
            rows.append({"factor": f, "months": len(ics), "mean_IC": ics.mean(),
                         "IC_tstat": t_stat, "pct_negative": (ics < 0).mean()})
    return pd.DataFrame(rows)


def threshold_sweep(df: pd.DataFrame, h: int,
                    thresholds=(-0.5, -1.0, -1.5, -2.0, -2.5)) -> pd.DataFrame:
    """rv_z 임계 스윕: 임계 아래 코호트의 초과수익 — '가중치/임계 어디에 둘까'의 근거."""
    rows = []
    for th in thresholds:
        s = cohort_stats(df, df["rv_z"] < th, h)
        if s:
            rows.append({"rv_z<": th, **{k: s[k] for k in
                                         ("n_events", "excess_mean", "excess_median", "hit_rate")}})
    # 비교 기준: 전체 유니버스
    base = cohort_stats(df, df["rv_z"].notna(), h)
    if base:
        rows.append({"rv_z<": "전체(기준)", **{k: base[k] for k in
                                            ("n_events", "excess_mean", "excess_median", "hit_rate")}})
    return pd.DataFrame(rows)


def run_backtest(params: Params = None, horizons=DEFAULT_HORIZONS, n_perm=500, df=None):
    """전체 백테스트. df에 build_scored_panel 결과를 넘기면 재계산 생략(앱에서 캐시 재사용).

    반환: dict(prepared df, 시그널별 성과, IC, 스윕, p-value)"""
    params = params or Params()
    if df is None:
        df, _ = build_scored_panel(params)
    df = prepare(df, horizons)

    signal_rv = df["rv_z"] < params.rv_buy_z
    signal_full = signal_rv & df["buy_zone"].fillna(False)

    results = {"params": params, "horizons": list(horizons), "df": df,
               "cohorts": {}, "ic": {}, "sweep": {}, "pvalue": {}}
    for h in horizons:
        results["cohorts"][h] = {
            f"rv_z<{params.rv_buy_z}": cohort_stats(df, signal_rv, h),
            "rv_z+매수구간": cohort_stats(df, signal_full, h),
            "전체(기준)": cohort_stats(df, df["rv_z"].notna(), h),
        }
        results["ic"][h] = factor_ic(df, h)
        results["sweep"][h] = threshold_sweep(df, h)
        results["pvalue"][h] = {
            f"rv_z<{params.rv_buy_z}": permutation_test(df, signal_rv, h, n_perm),
            "rv_z+매수구간": permutation_test(df, signal_full, h, n_perm),
        }
    return results


def print_report(results: dict):
    pct = lambda v: f"{v * 100:+.1f}%"  # noqa: E731
    for h in results["horizons"]:
        print(f"\n{'=' * 72}\n보유기간 {h}개월 (진입: 시그널 +{ENTRY_LAG}개월)\n{'=' * 72}")
        print(f"{'코호트':<18}{'이벤트':>8}{'절대평균':>10}{'초과평균':>10}{'초과중위':>10}{'승률':>8}")
        for name, s in results["cohorts"][h].items():
            if s:
                print(f"{name:<18}{s['n_events']:>8,}{pct(s['abs_mean']):>10}"
                      f"{pct(s['excess_mean']):>10}{pct(s['excess_median']):>10}"
                      f"{s['hit_rate'] * 100:>7.1f}%")
        pv = results["pvalue"][h]
        print(f"\n순열검정 p-value (무작위 대비 우위): " +
              ", ".join(f"{k}={v:.3f}" for k, v in pv.items() if not np.isnan(v)))
        ic = results["ic"][h]
        if len(ic):
            print(f"\n팩터 IC (음수 = '낮을수록 초과수익' 방향, |t|>2 유의):")
            print(ic.round(3).to_string(index=False))
        print(f"\nrv_z 임계 스윕:")
        print(results["sweep"][h].round(3).to_string(index=False))
    print(f"\n※ 절대수익률 세후 근사: 매수비용 {BUY_COST_PCT:.1%} + 매도비용 {SELL_COST_PCT:.1%} 차감"
          f" (양도세 미반영 — 보유기간·1주택 여부 따라 별도). 초과수익은 비용 중립.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--horizon", type=int, default=None, help="특정 보유기간(개월)만")
    ap.add_argument("--n-perm", type=int, default=500)
    args = ap.parse_args()
    horizons = (args.horizon,) if args.horizon else DEFAULT_HORIZONS
    results = run_backtest(horizons=horizons, n_perm=args.n_perm)
    print_report(results)


if __name__ == "__main__":
    main()
