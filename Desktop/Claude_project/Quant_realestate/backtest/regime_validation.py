"""레짐 장기 검증 — docs/regime_spec_v1.md §4-1 (지수 레벨, 2003~) + §4-2 (결합, 5년)

질문:
1. 레짐 신호등(🟢/🟡/🔴)별로 이후 수도권 아파트지수 12/24개월 수익률이 실제로 달랐는가?
2. 각 레짐 변수가 개별적으로 전방 지수 수익률과 상관이 있는가? (가설 부호 확인)
3. (결합) 🟢 레짐에서 산 rv_z 시그널 vs 🔴 레짐에서 산 시그널의 단지 초과·절대수익 차이는?

통과 기준: 🟢 전방 수익률 > 🔴 전방 수익률, 순열검정 p<0.05.

사용법: python backtest/regime_validation.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sstats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scoring.engine import get_connection, Params, build_scored_panel  # noqa: E402
from scoring.regime import compute_regime, _load_macro  # noqa: E402
from backtest.event_study import prepare  # noqa: E402

HORIZONS = (12, 24)


def load_index(conn) -> pd.Series:
    m = _load_macro(conn)
    return m["reb_apt_index"]


def forward_returns(idx: pd.Series, h: int) -> pd.Series:
    return idx.shift(-h) / idx - 1


def perm_pvalue(a: np.ndarray, b: np.ndarray, n=2000, seed=42) -> float:
    """H1: mean(a) > mean(b). 라벨 셔플 순열검정."""
    obs = a.mean() - b.mean()
    pool = np.concatenate([a, b])
    rng = np.random.default_rng(seed)
    cnt = 0
    for _ in range(n):
        rng.shuffle(pool)
        if pool[:len(a)].mean() - pool[len(a):].mean() >= obs:
            cnt += 1
    return cnt / n


def validate_long(regime: pd.DataFrame, idx: pd.Series):
    print("=" * 70)
    print("§4-1 장기 검증: 레짐별 이후 수도권 아파트지수 수익률 (2003~)")
    print("=" * 70)
    for h in HORIZONS:
        fwd = forward_returns(idx, h).reindex(regime.index)
        df = pd.DataFrame({"regime": regime["regime"], "fwd": fwd}).dropna()
        df = df[df["regime"] != "⚪ 판정불가"]
        g = df.groupby("regime")["fwd"].agg(["count", "mean", "median",
                                             lambda s: (s > 0).mean()])
        g.columns = ["개월수", "평균", "중위", "양(+)비율"]
        print(f"\n[{h}개월 후 지수 수익률]  (검증 표본 {len(df)}개월)")
        print((g.assign(평균=lambda d: (d['평균'] * 100).round(2),
                        중위=lambda d: (d['중위'] * 100).round(2),
                        **{'양(+)비율': lambda d: (d['양(+)비율'] * 100).round(1)})).to_string())
        green = df.loc[df["regime"].str.contains("매수적기"), "fwd"].to_numpy()
        red = df.loc[df["regime"].str.contains("보류"), "fwd"].to_numpy()
        if len(green) > 5 and len(red) > 5:
            p = perm_pvalue(green, red)
            print(f"🟢 vs 🔴 격차: {(green.mean() - red.mean()) * 100:+.2f}%p, 순열검정 p={p:.4f}"
                  f" {'→ 통과' if p < 0.05 else '→ 미달'}")


def validate_variables(regime: pd.DataFrame, idx: pd.Series):
    print("\n" + "=" * 70)
    print("변수별 개별 검증: 변수 z(t) ↔ 이후 지수 수익률 상관 (가설: 전부 양(+)이어야 정합)")
    print("=" * 70)
    var_cols = [c for c in ["rate_dir", "m2_yoy", "idx_mom", "supply_dem", "sentiment",
                            "jr_dir", "vol_ratio"] if c in regime.columns]
    rows = []
    for h in HORIZONS:
        fwd = forward_returns(idx, h).reindex(regime.index)
        for c in var_cols:
            d = pd.DataFrame({"x": regime[c], "y": fwd}).dropna()
            if len(d) >= 24:
                rho = sstats.spearmanr(d["x"], d["y"]).statistic
                rows.append({"변수": c, "h": h, "n": len(d), "Spearman": round(rho, 3),
                             "가설(+)": "✅" if rho > 0 else "❌ 역방향"})
    print(pd.DataFrame(rows).pivot_table(index="변수", columns="h",
                                         values="Spearman").round(3).to_string())
    rev = [r for r in rows if r["가설(+)"].startswith("❌")]
    if rev:
        uniq = sorted({r['변수'] for r in rev})
        print(f"⚠️ 가설 역방향 변수: {uniq} — 탈락 또는 부호 재검토 (R-B 조건부 채택 원칙)")


def validate_combined(regime: pd.DataFrame):
    print("\n" + "=" * 70)
    print("§4-2 결합 검증: 레짐별 rv_z 시그널 코호트의 단지 수익률 (2021~, 5년)")
    print("=" * 70)
    params = Params()
    df, _ = build_scored_panel(params)
    df = prepare(df, (12,))
    df = df.merge(regime[["regime"]], left_on="month", right_index=True, how="left")
    sig = df[(df["rv_z"] < params.rv_buy_z)].dropna(subset=["excess_12", "regime"])
    g = sig.groupby("regime")[["fwd_12", "excess_12"]].agg(["count", "mean"])
    print("(rv_z 시그널 이벤트를 진입 시점 레짐으로 분류)")
    print((g * 100).round(2).to_string())
    print("해석: 절대수익(fwd)이 레짐 간 크게 다르면 레짐 게이트 가치 있음. "
          "초과수익(excess)은 그룹 대비라 레짐과 무관한 게 정상 (선택 효과와 타이밍 효과의 분리 확인).")


def main():
    conn = get_connection()
    regime = compute_regime(conn, include_own_db=True)
    idx = load_index(conn)
    conn.close()
    validate_long(regime, idx)
    validate_variables(regime, idx)
    validate_combined(regime)


if __name__ == "__main__":
    main()
