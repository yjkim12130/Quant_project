"""시장환경 지표(공급·교통·자산비교) 집계 — market_context_spec_v1.md 구현.

app.py는 이 모듈의 함수만 호출한다(DB/YAML 직접 접근 금지 — scoring/engine.py 관례와 동일).
"""
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
MANUAL_CATALYSTS_YAML = ROOT / "config" / "manual_catalysts.yaml"


def _load_yaml():
    with open(MANUAL_CATALYSTS_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_redevelopment():
    rows = _load_yaml().get("redevelopment") or []
    if not rows:
        return pd.DataFrame(columns=["region_code", "complex_name", "stage",
                                      "expected_units", "expected_year"])
    return pd.DataFrame(rows)


def load_planned_transit():
    rows = _load_yaml().get("transit_planned") or []
    if not rows:
        return pd.DataFrame(columns=["line_name", "stations", "stage", "expected_open_year"])
    return pd.DataFrame(rows)


def load_supply_by_region_year(conn):
    """Load and aggregate presale (자동) and redevelopment (수동) supply data.

    Returns DataFrame with columns: region_code, year, presale_units, redevelopment_units
    """
    # Load presale data from DB, with defensive handling for missing table
    try:
        presale = pd.read_sql_query(
            "SELECT region_code, expected_ym, total_units FROM supply_presale", conn)
    except Exception:
        presale = pd.DataFrame(columns=["region_code", "expected_ym", "total_units"])

    # Extract year and aggregate presale by region and year
    if not presale.empty:
        presale["year"] = presale["expected_ym"].str[:4].astype(int)
        presale_agg = (presale.groupby(["region_code", "year"])["total_units"].sum()
                              .rename("presale_units").reset_index())
        presale_agg["presale_units"] = presale_agg["presale_units"].astype(int)
    else:
        presale_agg = pd.DataFrame(columns=["region_code", "year", "presale_units"])
        presale_agg = presale_agg.astype({"presale_units": "int"})

    # Load and aggregate redevelopment data
    redev = load_redevelopment()
    if redev.empty:
        redev_agg = pd.DataFrame(columns=["region_code", "year", "redevelopment_units"])
        redev_agg = redev_agg.astype({"redevelopment_units": "int"})
    else:
        redev_agg = (redev.groupby(["region_code", "expected_year"])["expected_units"].sum()
                          .rename("redevelopment_units")
                          .reset_index().rename(columns={"expected_year": "year"}))
        redev_agg["redevelopment_units"] = redev_agg["redevelopment_units"].astype(int)

    # Merge presale and redevelopment data
    out = pd.merge(presale_agg, redev_agg, on=["region_code", "year"], how="outer")
    out["presale_units"] = out["presale_units"].fillna(0).astype(int)
    out["redevelopment_units"] = out["redevelopment_units"].fillna(0).astype(int)
    return out.sort_values(["region_code", "year"]).reset_index(drop=True)


def own_apt_index(conn):
    """이 프로젝트가 추적하는 30개 지역(서울 남부 11개구+경기 남부 11개시)의 자체 실거래
    기반 아파트가격지수. reb_apt_index(부동산원 수도권 지수)는 서울+인천+경기 전체(외곽 포함)
    평균이라 관심 지역 실제 상승률과 크게 다를 수 있음(2026-08-16 확인: 같은 5년 구간에
    reb_apt_index +1.0% vs 강남구 단독 자체실거래 중위 +65.3%) — 자산비교 탭에 공식지수와
    병기해서 보여주기 위한 보조 지수다.

    월별 중위 ㎡당가(cancelled=0만)에 scoring/engine.py와 동일한 3개월 롤링 중위(Params.
    roll_window 기본값)를 적용한 뒤 첫 관측월=100으로 정규화. 롤링 없이 raw 월중위만 쓰면
    그 달 어떤 지역·단지가 몇 건 거래됐는지에 따라 구성 노이즈가 커서(실측: 무보정 시 전월대비
    ±10%p대로 출렁임) 30개 지역을 한 숫자로 풀링하는 이 지수의 취지(추세 비교)에 안 맞았음.
    trades_sale 적재 범위(2021-08~)만 존재해 reb_apt_index(2003~)만큼 긴 추세는 못 보여준다
    — 반드시 라벨로 구분해서 표시할 것(장기추세는 공식지수, 최근 체감비교는 이 지수).

    Returns: pd.Series, index=PeriodIndex(freq='M'), name='own_apt_index'. 데이터 없으면 빈 Series.
    """
    df = pd.read_sql_query(
        "SELECT contract_date, deal_amount, exclusive_area FROM trades_sale WHERE cancelled=0", conn)
    if df.empty:
        return pd.Series(name="own_apt_index", dtype=float)
    df["ym"] = df["contract_date"].str[:7]
    df["sqm_price"] = df["deal_amount"] / df["exclusive_area"]
    monthly = df.groupby("ym")["sqm_price"].median().sort_index()
    monthly.index = pd.PeriodIndex(pd.to_datetime(monthly.index, format="%Y-%m"), freq="M")
    rolled = monthly.rolling(3, min_periods=1).median()
    return (rolled / rolled.iloc[0] * 100).rename("own_apt_index")


ASSET_COMPARE_COLS = ["asset_kospi", "asset_nasdaq", "asset_gold", "asset_btc"]


def asset_ratio_zscore(assets):
    """reb_apt_index / 각 자산 비율의 자기 역사 대비 z-score(최신값). 음수 = 부동산이 해당
    자산 대비 역사적으로 싸다(rv_z와 동일한 부호 관례). 컬럼 없으면 결과에서 제외."""
    if "reb_apt_index" not in assets.columns:
        return {}
    out = {}
    for col in ASSET_COMPARE_COLS:
        if col not in assets.columns:
            continue
        ratio = (assets["reb_apt_index"] / assets[col]).dropna()
        if len(ratio) < 2 or ratio.std() == 0:
            continue
        out[col] = (ratio.iloc[-1] - ratio.mean()) / ratio.std()
    return out
