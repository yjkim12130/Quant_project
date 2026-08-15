"""매수 타이밍 레짐 산출 — docs/regime_spec_v1.md §2~3 구현

6변수(가설 부호로 정렬: + = 매수 우호):
    rate_dir   기준금리 12개월 변화의 역부호 (인하 국면 = +)     ECOS, lag 0
    m2_yoy     M2 YoY 증가율 (유동성 확장 = +)                  ECOS, lag 2개월
    idx_mom    수도권 아파트지수 12개월 모멘텀 (상승 국면 = +)    R-ONE, lag 1개월
    supply_dem 매매수급지수 (수요 우위 = +)                      R-ONE, lag 1개월, 2012~
    sentiment  주택시장 소비심리지수 (심리 개선 = +)              R-ONE, lag 1개월, 2011~
    jr_dir     시장 전세가율 12개월 변화 (상승 = 바닥 신호 = +)   자체 DB, 2021~ (결합 검증용)
    vol_ratio  매매/전세 거래량 비율 (매매 회복 = +)              자체 DB, 2021~ (결합 검증용)

표준화: 과거 rolling 120개월 z (min 36) — 미래 정보 미사용.
하드룰: 기준금리 12개월 변화 > +1.0%p (인상 가속) → 강제 🔴 보류.
신호등: 점수의 expanding 분위(q30/q70, min 36개월) — 미래 정보 미사용.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scoring.engine import get_connection, load_sale, load_jeonse  # noqa: E402

Z_WINDOW = 120
Z_MIN = 36
HARD_RATE_HIKE = 1.0   # %p / 12개월
Q_LO, Q_HI = 0.30, 0.70

PUB_LAG = {"ecos_base_rate": 0, "ecos_m2": 2, "reb_apt_index": 1,
           "reb_supply_demand": 1, "reb_sentiment": 1}


def _load_macro(conn) -> pd.DataFrame:
    df = pd.read_sql_query("SELECT series, ym, value FROM macro_series", conn)
    wide = df.pivot(index="ym", columns="series", values="value")
    wide.index = pd.PeriodIndex(pd.to_datetime(wide.index, format="%Y%m"), freq="M")
    wide = wide.sort_index()
    # 발표 지연 반영: t월 판단에는 lag개월 전 값 사용
    for col, lag in PUB_LAG.items():
        if col in wide.columns and lag:
            wide[col] = wide[col].shift(lag)
    return wide


def _trailing_z(s: pd.Series) -> pd.Series:
    mean = s.rolling(Z_WINDOW, min_periods=Z_MIN).mean()
    std = s.rolling(Z_WINDOW, min_periods=Z_MIN).std().replace(0, np.nan)
    return (s - mean) / std


def build_supply_demand_own(conn=None) -> pd.DataFrame:
    """자체 DB 수급 변수 (2021-08~): 시장 전세가율·매매/전세 거래량 비율 (지역 전체 집계)."""
    own = conn is None
    conn = conn or get_connection()
    sale = load_sale(conn)
    jeonse = load_jeonse(conn)
    if own:
        conn.close()

    s = sale[sale["cancelled"] == 0]
    sm = s.groupby("month").agg(sale_sqm=("deal_amount", "median"), n_sale=("deal_amount", "size"),
                                sale_area=("exclusive_area", "median"))
    sm["sale_sqm"] = s.groupby("month").apply(lambda g: (g["deal_amount"] / g["exclusive_area"]).median())
    jm = jeonse.groupby("month").agg(n_jeonse=("deposit", "size"))
    jm["jeonse_sqm"] = jeonse.groupby("month").apply(lambda g: (g["deposit"] / g["exclusive_area"]).median())

    out = sm.join(jm, how="inner")
    out["market_jr"] = out["jeonse_sqm"] / out["sale_sqm"]
    out["jr_dir"] = out["market_jr"] - out["market_jr"].shift(12)
    out["vol_ratio"] = out["n_sale"] / out["n_jeonse"]
    return out[["market_jr", "jr_dir", "vol_ratio"]]


def compute_regime(conn=None, include_own_db: bool = True) -> pd.DataFrame:
    """월별 레짐 점수·신호등. 반환 컬럼: 변수별 z, score, regime(🟢/🟡/🔴), hard_rule."""
    own = conn is None
    conn = conn or get_connection()
    m = _load_macro(conn)

    v = pd.DataFrame(index=m.index)
    rate_chg12 = m["ecos_base_rate"] - m["ecos_base_rate"].shift(12)
    v["rate_dir"] = _trailing_z(-rate_chg12)
    v["m2_yoy"] = _trailing_z(m["ecos_m2"].pct_change(12) * 100)
    v["idx_mom"] = _trailing_z(m["reb_apt_index"].pct_change(12) * 100)
    if "reb_supply_demand" in m.columns:
        v["supply_dem"] = _trailing_z(m["reb_supply_demand"])
    if "reb_sentiment" in m.columns:
        v["sentiment"] = _trailing_z(m["reb_sentiment"])

    if include_own_db:
        try:
            own_sd = build_supply_demand_own(conn)
            own_sd.index = own_sd.index.astype(m.index.dtype)
            v["jr_dir"] = _trailing_z(own_sd["jr_dir"].reindex(v.index))
            v["vol_ratio"] = _trailing_z(own_sd["vol_ratio"].reindex(v.index))
        except Exception:  # noqa: BLE001 — 자체 DB 미적재 환경에서도 매크로만으로 동작
            pass
    if own:
        conn.close()

    # m2_yoy는 장기 검증(2026-08-14, regime_validation.py)에서 전방 수익률과 역방향 →
    # R-B '검증 무효 시 탈락' 원칙으로 점수에서 제외 (컬럼은 모니터링용으로 유지)
    score_cols = [c for c in v.columns if c != "m2_yoy"]
    v["score"] = v[score_cols].clip(-3, 3).mean(axis=1, skipna=True)
    v["n_vars"] = v[score_cols].notna().sum(axis=1)
    v.loc[v["n_vars"] < 2, "score"] = np.nan

    # 신호등: expanding 분위 (미래 미사용)
    lo = v["score"].expanding(Z_MIN).quantile(Q_LO).shift(1)
    hi = v["score"].expanding(Z_MIN).quantile(Q_HI).shift(1)
    v["regime"] = np.select([v["score"] >= hi, v["score"] <= lo], ["🟢 매수적기", "🔴 보류"], "🟡 중립")
    v.loc[v["score"].isna() | hi.isna(), "regime"] = "⚪ 판정불가"

    # 하드룰: 금리 인상 가속 → 강제 보류
    v["hard_rule"] = rate_chg12 > HARD_RATE_HIKE
    v.loc[v["hard_rule"] & (v["regime"] != "⚪ 판정불가"), "regime"] = "🔴 보류"
    return v


# 레짐별 rv_z 매수 임계 (R-E, 초안 — 결합 검증 후 확정)
REGIME_RV_THRESHOLD = {"🟢 매수적기": -1.0, "🟡 중립": -1.5, "🔴 보류": -2.0, "⚪ 판정불가": -1.5}


def load_raw_series(conn=None, include_own_db: bool = True) -> pd.DataFrame:
    """변수별 원시값 시계열 (앱 '매수 타이밍' 탭 표시용). 발표 지연(lag) 적용 후 값."""
    own = conn is None
    conn = conn or get_connection()
    m = _load_macro(conn)
    out = pd.DataFrame(index=m.index)
    out["base_rate"] = m["ecos_base_rate"]
    out["rate_chg12"] = m["ecos_base_rate"] - m["ecos_base_rate"].shift(12)
    out["m2_yoy"] = m["ecos_m2"].pct_change(12) * 100
    out["idx"] = m["reb_apt_index"]
    out["idx_mom12"] = m["reb_apt_index"].pct_change(12) * 100
    out["idx_dd"] = (m["reb_apt_index"] / m["reb_apt_index"].cummax() - 1) * 100
    if "reb_supply_demand" in m.columns:
        out["supply_dem"] = m["reb_supply_demand"]
    if "reb_sentiment" in m.columns:
        out["sentiment"] = m["reb_sentiment"]
    if include_own_db:
        try:
            sd = build_supply_demand_own(conn)
            sd.index = sd.index.astype(m.index.dtype)
            out["market_jr"] = sd["market_jr"].reindex(out.index) * 100
            out["jr_chg12"] = sd["jr_dir"].reindex(out.index) * 100
            out["vol_ratio"] = sd["vol_ratio"].reindex(out.index)
        except Exception:  # noqa: BLE001
            pass
    if own:
        conn.close()
    return out


if __name__ == "__main__":
    r = compute_regime()
    print(r.dropna(subset=["score"]).tail(18).round(2).to_string())
    last = r.dropna(subset=["score"]).iloc[-1]
    print(f"\n현재({r.dropna(subset=['score']).index[-1]}): {last['regime']} (score {last['score']:+.2f}, 변수 {int(last['n_vars'])}개)")
