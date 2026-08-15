"""저평가 스코어링 엔진 — docs/algo_spec_v1.md 구현

파이프라인 (스펙 §8):
    load_sale/load_jeonse → build_price_series(§1) → attach_groups+build_group_series(§2)
    → factor_rv/factor_jeonse/factor_overheat(§3) → combine_scores(§4)

사용 예:
    from scoring.engine import Params, run_screener
    result = run_screener()            # 최신 월 기준 랭킹 테이블
    result = run_screener(month="2026-07", params=Params(lookback_months=36))

설계 원칙:
- 그룹 정의는 make_group_key() 하나에만 존재 (Phase 5에서 학군·역세권 축으로 교체)
- 그리드서치 대상 파라미터는 Params의 4개(lookback/rv_buy_z/dd_threshold/mom_floor)를 초과하지 않음
- 시점 t 스코어는 t-1개월까지의 데이터만 사용 (신고 지연 누수 방지, 스펙 §6)
"""
from dataclasses import dataclass, field
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "realestate.db"

AREA_BAND_LABELS = ["~60", "60~85", "85~"]
AGE_BAND_LABELS = ["~10y", "10~25y", "25y~"]


@dataclass
class Params:
    # --- 그리드서치+WFV 대상 (스펙 §5, 이 4개를 초과하지 않는다) ---
    lookback_months: int = 24     # L: rv/jr z-score의 "평소" 기간
    rv_buy_z: float = -1.0        # 괴리율 매수 임계 (σ)
    dd_threshold: float = -0.10   # 과열도: 전고점 대비 조정 충분 기준
    mom_floor: float = -0.05      # 과열도: 12개월 모멘텀 하한 (하락 가속 배제)
    # --- 고정 파라미터 (확정값 또는 적재 후 실측 조정) ---
    area_bounds: tuple = (60.0, 85.0)   # 전용면적 밴드 경계 (㎡)
    age_bounds: tuple = (10, 25)        # 연식 밴드 경계 (년)
    min_group_complexes: int = 5        # 그룹 최소 단지 수 (미달 시 시군구 폴백)
    roll_window: int = 3                # 월 중위가 롤링 윈도
    ffill_limit: int = 6                # 마지막 관측 이월 한도 (초과 시 스코어링 제외)
    cancel_flag_pct: float = 0.10       # 최근 1년 해제비율 경고 임계
    min_group_z: int = 12               # z-score 계산에 필요한 최소 관측 월수


# ---------------------------------------------------------------- 데이터 로드

def get_connection(db_path=DB_PATH):
    return sqlite3.connect(db_path)


def _norm_name(s: pd.Series) -> pd.Series:
    """단지명 정규화 v1: 공백 제거만. 표기 변형 실측(체크리스트 2) 후 규칙 보강."""
    return s.astype(str).str.replace(r"\s+", "", regex=True)


def _complex_key(df: pd.DataFrame) -> pd.Series:
    """단지 식별키. apt_seq(매매 상세 API 제공)가 있으면 그걸 쓰고,
    없으면(전월세 테이블) region_code|동|정규화단지명으로 조인한다."""
    return df["region_code"].astype(str) + "|" + df["dong_name"].astype(str) + "|" + _norm_name(df["complex_name"])


def load_sale(conn) -> pd.DataFrame:
    df = pd.read_sql_query(
        "SELECT region_code, region_name, dong_name, complex_name, apt_seq, exclusive_area, "
        "       contract_date, deal_amount, build_year, cancelled "
        "FROM trades_sale", conn)
    df["month"] = pd.PeriodIndex(pd.to_datetime(df["contract_date"], errors="coerce"), freq="M")
    df["ckey"] = _complex_key(df)
    return df.dropna(subset=["month", "exclusive_area", "deal_amount"])


def load_jeonse(conn) -> pd.DataFrame:
    df = pd.read_sql_query(
        "SELECT region_code, dong_name, complex_name, exclusive_area, "
        "       contract_date, deposit, monthly_rent, build_year "
        "FROM trades_jeonse", conn)
    df = df[df["monthly_rent"].fillna(0) == 0]  # v1: 순수 전세만 (월세 전환 없음)
    df["month"] = pd.PeriodIndex(pd.to_datetime(df["contract_date"], errors="coerce"), freq="M")
    df["ckey"] = _complex_key(df)
    return df.dropna(subset=["month", "exclusive_area", "deposit"])


# ---------------------------------------------------------------- §1 가격 패널

def area_band(area: pd.Series, params: Params) -> pd.Series:
    lo, hi = params.area_bounds
    return pd.cut(area, bins=[-np.inf, lo, hi, np.inf], labels=AREA_BAND_LABELS, right=False)


def build_price_series(trades: pd.DataFrame, amount_col: str, params: Params) -> pd.DataFrame:
    """(단지, 면적밴드)×월 패널. 월 중위 ㎡당가 → 3개월 롤링 중위 → 이월(한도 6개월).

    반환 long-format: ckey, area_band, month, price(만원/㎡), n_trades, carried(이월 여부)
    매매는 amount_col='deal_amount'(cancelled==0만), 전세는 'deposit'.
    """
    t = trades if "cancelled" not in trades.columns else trades[trades["cancelled"] == 0]
    t = t.copy()
    t["band"] = area_band(t["exclusive_area"], params)
    t["sqm_price"] = t[amount_col] / t["exclusive_area"]

    monthly = (t.groupby(["ckey", "band", "month"], observed=True)["sqm_price"]
                 .agg(raw_price="median", n_trades="size").reset_index())

    # 벡터화: (월 × 단지·밴드) 와이드 피벗에서 롤링·이월을 일괄 처리 (단지별 루프 대비 수십 배 빠름)
    full_months = pd.period_range(monthly["month"].min(), monthly["month"].max(), freq="M")
    raw = (monthly.pivot_table(index="month", columns=["ckey", "band"], values="raw_price",
                               observed=True).reindex(full_months))
    n = (monthly.pivot_table(index="month", columns=["ckey", "band"], values="n_trades",
                             observed=True).reindex(full_months).reindex(columns=raw.columns)
         .fillna(0).astype(int))
    rolled = raw.rolling(params.roll_window, min_periods=1).median()
    filled = rolled.ffill(limit=params.ffill_limit)
    carried = filled.notna() & rolled.isna()

    def _melt(wide, name):
        s = wide.stack(["ckey", "band"], future_stack=True)
        s.name = name
        return s

    panel = pd.concat([_melt(filled, "price"), _melt(n, "n_trades"), _melt(carried, "carried")],
                      axis=1).reset_index(names=["month", "ckey", "area_band"])
    panel["carried"] = panel["carried"].fillna(False).astype(bool)
    return panel.dropna(subset=["price"]).reset_index(drop=True)


def build_complex_meta(sale: pd.DataFrame) -> pd.DataFrame:
    """단지 메타: 시군구/동/대표 건축년도/해제비율(최근 1년)."""
    recent = sale["month"] >= (sale["month"].max() - 12)
    cancel_pct = (sale[recent].groupby("ckey")["cancelled"].mean()).rename("cancel_pct_1y")
    meta = (sale.groupby("ckey")
                .agg(region_code=("region_code", "first"), region_name=("region_name", "first"),
                     dong_name=("dong_name", "first"), complex_name=("complex_name", "first"),
                     build_year=("build_year", lambda x: x.mode().iat[0] if len(x.mode()) else np.nan))
                .join(cancel_pct).reset_index())
    meta["cancel_pct_1y"] = meta["cancel_pct_1y"].fillna(0.0)
    return meta


# ---------------------------------------------------------------- §2 그룹

def age_band_at(build_year: pd.Series, month: pd.Period, params: Params) -> pd.Series:
    lo, hi = params.age_bounds
    age = month.year - build_year
    return pd.cut(age, bins=[-np.inf, lo, hi, np.inf], labels=AGE_BAND_LABELS, right=False)


def make_group_key(panel_month: pd.DataFrame, month: pd.Period, params: Params) -> pd.Series:
    """v1 그룹키: (법정동, 면적밴드, 연식밴드) → 단지 수 미달 시 (시군구, 면적밴드, 연식밴드) 폴백
    → 그래도 미달 시 NaN(스코어링 제외).

    ※ 그룹 정의는 이 함수에만 존재한다. Phase 5에서 학군·역세권 축으로 교체할 때 여기만 수정.
    panel_month: 특정 월의 패널 + 메타 조인 결과 (dong_name/region_code/build_year/area_band 필요)
    """
    ab = age_band_at(panel_month["build_year"], month, params).astype(str)
    fine = panel_month["region_code"].astype(str) + "|" + panel_month["dong_name"].astype(str) \
        + "|" + panel_month["area_band"].astype(str) + "|" + ab
    coarse = panel_month["region_code"].astype(str) + "|*|" + panel_month["area_band"].astype(str) + "|" + ab

    n_fine = fine.map(fine.value_counts())
    n_coarse = coarse.map(coarse.value_counts())
    key = fine.where(n_fine >= params.min_group_complexes,
                     coarse.where(n_coarse >= params.min_group_complexes))
    return key


def attach_groups(panel: pd.DataFrame, meta: pd.DataFrame, params: Params) -> pd.DataFrame:
    """패널 각 월 단면에 그룹키·그룹 중위가를 붙인다."""
    df = panel.merge(meta, on="ckey", how="left")
    parts = []
    for month, g in df.groupby("month"):
        g = g.copy()
        g["group_key"] = make_group_key(g, month, params)
        g["group_price"] = g.groupby("group_key")["price"].transform("median")
        g["group_n"] = g.groupby("group_key")["price"].transform("size")
        parts.append(g)
    return pd.concat(parts, ignore_index=True)


# ---------------------------------------------------------------- §3 팩터

def _trailing_z(s: pd.Series, lookback: int, min_periods: int) -> pd.Series:
    """자기 역사 대비 z-score. 현재값은 통계에서 제외(shift 1)해 look-ahead 방지."""
    mean = s.shift(1).rolling(lookback, min_periods=min_periods).mean()
    std = s.shift(1).rolling(lookback, min_periods=min_periods).std()
    std = std.replace(0, np.nan)  # 변동 없는 시계열(이월 연속 등)에서 inf 방지
    return (s - mean) / std


def factor_rv(df: pd.DataFrame, params: Params) -> pd.DataFrame:
    """Factor1: ratio = 단지가/그룹 중위가의 자기 역사 대비 z-score (스펙 §3, C3)."""
    df = df.sort_values("month")
    df["ratio"] = df["price"] / df["group_price"]
    df["rv_z"] = (df.groupby(["ckey", "area_band"], observed=True)["ratio"]
                    .transform(lambda s: _trailing_z(s, params.lookback_months, params.min_group_z)))
    return df


def factor_jeonse(df: pd.DataFrame, jeonse_panel: pd.DataFrame, params: Params) -> pd.DataFrame:
    """Factor2: 전세가율의 자기 역사 대비 z-score (E2). 전세 데이터 없으면 중립(NaN→0)."""
    jp = jeonse_panel.rename(columns={"price": "jeonse_price"})[["ckey", "area_band", "month", "jeonse_price"]]
    df = df.merge(jp, on=["ckey", "area_band", "month"], how="left")
    df["jeonse_ratio"] = df["jeonse_price"] / df["price"]
    df = df.sort_values("month")
    df["jr_z"] = (df.groupby(["ckey", "area_band"], observed=True)["jeonse_ratio"]
                    .transform(lambda s: _trailing_z(s, params.lookback_months, params.min_group_z)))
    return df


def factor_overheat(df: pd.DataFrame, params: Params) -> pd.DataFrame:
    """Factor3: 전고점 DD + 12개월 모멘텀 (D1+D2). dd 단독 사용 금지 — 매수구간은 AND 조건."""
    df = df.sort_values("month")
    grp = df.groupby(["ckey", "area_band"], observed=True)["price"]
    df["dd"] = df["price"] / grp.transform("cummax") - 1
    df["mom12"] = grp.transform(lambda s: s / s.shift(12) - 1)
    df["buy_zone"] = (df["dd"] < params.dd_threshold) & (df["mom12"] > params.mom_floor)
    return df


# ---------------------------------------------------------------- §4 결합

def _xsection_z(s: pd.Series) -> pd.Series:
    return (s - s.mean()) / s.std() if s.std() and not np.isnan(s.std()) else s * 0


def combine_scores(df: pd.DataFrame, params: Params, month=None) -> pd.DataFrame:
    """스펙 §4: 하드필터 → 핵심 2팩터 동일가중 → (Phase 5: 보너스).

    반환: 지정 월(기본 최신)의 단면 랭킹 테이블. score 낮을수록(음수) 저평가.
    """
    if month is None:
        month = df["month"].max()
    x = df[df["month"] == pd.Period(month, freq="M")].copy()

    # 하드필터: 유동성(가격 존재는 패널 구성에서 보장), 해제 플래그는 제외가 아닌 경고
    x["cancel_flag"] = x["cancel_pct_1y"] > params.cancel_flag_pct

    # 핵심 2팩터: rv_z(낮을수록 저평가) + 과열도(-dd 클수록 조정 충분, buy_zone 가점)
    oh_score = _xsection_z(x["dd"])  # dd 음수가 클수록(많이 빠질수록) 낮은 값
    x["score"] = _xsection_z(x["rv_z"]) + oh_score
    # jr_z는 보조 표시(스코어 편입은 Factor2 커버리지 실측 후) — 중립 0 처리 컬럼 유지
    x["jr_z_display"] = x["jr_z"].fillna(0.0)

    x["signal"] = np.select(
        [x["rv_z"] < params.rv_buy_z, x["rv_z"] > -params.rv_buy_z],
        ["🟢 저평가", "🔴 고평가"], default="🟡 중립")
    x.loc[x["rv_z"].isna(), "signal"] = "⚪ 데이터부족"

    cols = ["ckey", "complex_name", "dong_name", "region_code", "region_name", "area_band", "build_year",
            "price", "group_price", "group_n", "ratio", "rv_z", "jeonse_ratio", "jr_z_display",
            "dd", "mom12", "buy_zone", "cancel_flag", "n_trades", "carried", "signal", "score"]
    return x[[c for c in cols if c in x.columns]].sort_values("score")


# ---------------------------------------------------------------- 진입점

def recent_totals(sale: pd.DataFrame, params: Params, window_months: int = 6) -> pd.DataFrame:
    """단지×면적밴드별 최근 N개월 매매 총액 중위(만원)·대표 전용면적 — 예산 매칭/표시용."""
    t = sale[sale["cancelled"] == 0].copy()
    t = t[t["month"] >= t["month"].max() - (window_months - 1)]
    t["band"] = area_band(t["exclusive_area"], params)
    out = (t.groupby(["ckey", "band"], observed=True)
             .agg(recent_total=("deal_amount", "median"), rep_area=("exclusive_area", "median"))
             .reset_index().rename(columns={"band": "area_band"}))
    return out


def build_scored_panel(params: Params = None, db_path=DB_PATH):
    """전체 시계열 팩터 패널 + 부가 테이블. 앱(Tab2 히스토리)과 백테스트가 공유하는 진입점.

    반환: (df, sale_totals) — df는 §1~3 적용된 long 패널, sale_totals는 최근 총액 표.
    """
    params = params or Params()
    conn = get_connection(db_path)
    try:
        sale = load_sale(conn)
        jeonse = load_jeonse(conn)
    finally:
        conn.close()

    panel = build_price_series(sale, "deal_amount", params)
    jeonse_panel = build_price_series(jeonse, "deposit", params)
    meta = build_complex_meta(sale)

    df = attach_groups(panel, meta, params)
    df = factor_rv(df, params)
    df = factor_jeonse(df, jeonse_panel, params)
    df = factor_overheat(df, params)
    return df, recent_totals(sale, params)


def run_screener(month=None, params: Params = None, db_path=DB_PATH) -> pd.DataFrame:
    params = params or Params()
    df, totals = build_scored_panel(params, db_path)
    out = combine_scores(df, params, month=month)
    return out.merge(totals, on=["ckey", "area_band"], how="left")


if __name__ == "__main__":
    result = run_screener()
    print(f"스크리너 결과: {len(result)}개 (단지×면적밴드)")
    print(result.head(20).to_string(index=False))
