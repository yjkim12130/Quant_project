"""급지(지역 티어) 상대평가 - docs/region_tier_spec_v1.md 구현.

파이프라인 (스펙 §2~4):
    region_price_index(§2) -> assign_tiers(§3) -> region_rv(§4)
    페어 비교는 pair_ratio(§4.1), 전세가율은 region_jeonse_ratio(표시 전용).

설계 원칙:
- engine.py는 건드리지 않는다. 밴드 정의와 z 함수만 가져다 쓴다.
- 이 모듈은 계산만 한다. Streamlit 캐싱은 app.py가 감싼다.
- 조회 전용이다. 스크리너 점수에 절대 섞지 않는다 (스펙 §7).
"""
import numpy as np
import pandas as pd

from scoring.engine import AGE_BAND_LABELS, DB_PATH, Params, _trailing_z, area_band

LEVELS = ("sgg", "dong")
CELL_SEP = "|"


def _check_level(level):
    if level not in LEVELS:
        raise ValueError(f"level은 {LEVELS} 중 하나여야 합니다: {level!r}")


def _region_key(trades: pd.DataFrame, level: str) -> pd.Series:
    """지역 식별키. dong 레벨은 시군구코드까지 붙인다 - '중동'처럼 시군구를 넘어
    중복되는 동명을 단독으로 키에 쓰면 서로 다른 동이 하나로 합쳐진다."""
    _check_level(level)
    code = trades["region_code"].astype(str)
    if level == "sgg":
        return code
    return code + CELL_SEP + trades["dong_name"].astype(str)


def _region_labels(trades: pd.DataFrame, level: str) -> pd.DataFrame:
    """region_key -> 화면 표시명("양천구" / "양천구 목동")."""
    _check_level(level)
    name = trades["region_name"].astype(str)
    label = name if level == "sgg" else name + " " + trades["dong_name"].astype(str)
    return (pd.DataFrame({"region_key": _region_key(trades, level), "region_label": label})
              .drop_duplicates("region_key").reset_index(drop=True))


def _cell_labels(trades: pd.DataFrame, params: Params) -> pd.Series:
    """면적밴드|연식밴드 (3x3 = 9셀). engine.area_band를 그대로 쓰고, 연식은 행마다
    계약월이 달라 engine.age_band_at(스칼라 month 전용)을 못 쓰므로 벡터로 계산한다."""
    ab = area_band(trades["exclusive_area"], params).astype(str)
    age = trades["month"].dt.year - trades["build_year"]
    lo, hi = params.age_bounds
    gb = pd.cut(age, bins=[-np.inf, lo, hi, np.inf], labels=AGE_BAND_LABELS,
                right=False).astype(str)
    return ab + CELL_SEP + gb


def _basket_index(trades, amount_col, params, min_weight=0.5):
    """고정 바스켓 지역 대표가 (스펙 §2.2).

    연산 순서가 중요하다: 셀 집계 -> 셀 단위 롤링/이월 -> 게이트 -> 가중합.
    대표가를 먼저 만들고 나중에 롤링하면 그 달 관측된 셀만으로 만든 오염된 값을
    평활하게 된다.

    trades에는 region_key 컬럼이 이미 있어야 한다.
    반환: month, region_key, price(만원/㎡), w_valid, n_trades
    """
    t = trades.copy()
    t["sqm_price"] = t[amount_col] / t["exclusive_area"]
    t["cell"] = _cell_labels(t, params)

    # 가중치는 전 지역 공통 상수여야 한다 - 지역마다 다른 구성에서 오는 왜곡을
    # 없애는 것이 목적이므로 지역별/월별로 다시 계산하면 안 된다.
    w = t.groupby("cell").size()
    w = w / w.sum()

    cell = (t.groupby(["region_key", "month", "cell"], observed=True)
              .agg(p=("sqm_price", "median"), n=("sqm_price", "size")).reset_index())
    months = pd.period_range(cell["month"].min(), cell["month"].max(), freq="M")

    # 벡터화 필수: groupby.apply(가중평균)으로 짜면 동 단위가 50초까지 늘어난다.
    piv = (cell.pivot_table(index="month", columns=["region_key", "cell"], values="p",
                            observed=True).reindex(months))
    rolled = (piv.rolling(params.roll_window, min_periods=1).median()
                 .ffill(limit=params.ffill_limit))
    wv = pd.Series(rolled.columns.get_level_values("cell"), index=rolled.columns).map(w).values
    num = (rolled.fillna(0) * wv).T.groupby(level=0).sum().T
    den = (rolled.notna() * wv).T.groupby(level=0).sum().T
    price = (num / den).where(den >= min_weight)

    n_trades = (cell.pivot_table(index="month", columns="region_key", values="n",
                                 aggfunc="sum", observed=True)
                    .reindex(months).reindex(columns=price.columns).fillna(0).astype(int))
    out = pd.concat([price.stack(future_stack=True).rename("price"),
                     den.stack(future_stack=True).rename("w_valid"),
                     n_trades.stack(future_stack=True).rename("n_trades")], axis=1)
    return (out.reset_index(names=["month", "region_key"])
               .dropna(subset=["price"]).reset_index(drop=True))
