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

from scoring.engine import AGE_BAND_LABELS, AREA_BAND_LABELS, DB_PATH, Params, _trailing_z, area_band

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


def _basket_index(trades, amount_col, params, min_weight=0.5, weights=None):
    """고정 바스켓 지역 대표가 (스펙 §2.2).

    연산 순서가 중요하다: 셀 집계 -> 셀 단위 롤링/이월 -> 게이트 -> 가중합.
    대표가를 먼저 만들고 나중에 롤링하면 그 달 관측된 셀만으로 만든 오염된 값을
    평활하게 된다.

    trades에는 region_key 컬럼이 이미 있어야 한다.
    weights: 미리 계산된 셀 가중치(Series, index="면적밴드|연식밴드"). None이면
    전달받은 trades 자체에서 계산한다(매매 기본 동작). 전세가율처럼 "매매와 같은
    바스켓"을 다른 표본(전세)에 적용해야 할 때는 반드시 지정해야 한다 - 지정하지
    않으면 전세 거래 구성으로 가중치를 다시 계산해버려서, 매매와 다른 바스켓이 되고
    "같은 고정 바스켓" 전제가 깨진다.
    반환: month, region_key, price(만원/㎡), w_valid, n_trades
    """
    t = trades.copy()
    t["sqm_price"] = t[amount_col] / t["exclusive_area"]
    t["cell"] = _cell_labels(t, params)

    if weights is not None:
        w = weights
    else:
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


def _sale_cell_weights(conn, params):
    """매매 셀 가중치 벡터를 trades_sale에서 직접 집계한다 (region_jeonse_ratio가
    "매매와 같은 고정 바스켓"을 전세에 적용하려 빌려온다).

    9행짜리 SQL GROUP BY라 매매 전체(400만+행)를 다시 DataFrame으로 읽어 들이지
    않고도 정확한 가중치를 얻는다. area_band()/age_band_at()와 똑같은 경계
    (area_bounds, age_bounds)를 SQL CASE로 재현하고, 연식은 _cell_labels와 동일하게
    "계약월 연도 - 건축연도"로 계산한다(trades_sale.contract_date는 SQLite가 그대로
    파싱하는 ISO 포맷이라 strftime으로 연도만 뽑으면 된다).

    반환: Series, index="면적밴드|연식밴드"(CELL_SEP), 합계 1. trades_sale에 유효한
    행이 하나도 없으면 None(호출부가 자체 계산으로 폴백).
    """
    a_lo, a_hi = params.area_bounds
    g_lo, g_hi = params.age_bounds
    al, am, ah = AREA_BAND_LABELS
    gl, gm, gh = AGE_BAND_LABELS
    q = f"""
        SELECT
          CASE WHEN exclusive_area < {a_lo} THEN '{al}'
               WHEN exclusive_area < {a_hi} THEN '{am}'
               ELSE '{ah}' END AS area_band,
          CASE WHEN (CAST(strftime('%Y', contract_date) AS INTEGER) - build_year) < {g_lo}
                 THEN '{gl}'
               WHEN (CAST(strftime('%Y', contract_date) AS INTEGER) - build_year) < {g_hi}
                 THEN '{gm}'
               ELSE '{gh}' END AS age_band,
          COUNT(*) AS n
        FROM trades_sale
        WHERE cancelled = 0 AND exclusive_area > 0
          AND build_year IS NOT NULL AND contract_date IS NOT NULL
        GROUP BY area_band, age_band
    """
    df = pd.read_sql_query(q, conn)
    if df.empty or df["n"].sum() == 0:
        return None
    w = pd.Series(df["n"].to_numpy(dtype=float),
                 index=(df["area_band"] + CELL_SEP + df["age_band"]).to_numpy())
    return w / w.sum()


def _load_trades(conn, table, amount_col, extra_where=""):
    """실거래 로드 + month(Period) 부여. 결측 build_year/면적 0 이하 행을 제거한다."""
    q = (f"SELECT region_code, region_name, dong_name, exclusive_area, build_year, "
         f"contract_date, {amount_col} FROM {table} WHERE 1=1 {extra_where}")
    df = pd.read_sql_query(q, conn)
    df["month"] = pd.PeriodIndex(pd.to_datetime(df["contract_date"], errors="coerce"), freq="M")
    df = df.dropna(subset=["month", "exclusive_area", "build_year", amount_col])
    return df[df["exclusive_area"] > 0]


def region_price_index(conn, level="sgg", params=None, min_weight=0.5):
    """지역 고정 바스켓 가격지수 (스펙 §2). level은 'sgg'(시군구) 또는 'dong'(법정동).

    반환: month, region_key, price, w_valid, n_trades, region_label
    """
    _check_level(level)
    params = params or Params()
    trades = _load_trades(conn, "trades_sale", "deal_amount", "AND cancelled = 0")
    if trades.empty:
        return pd.DataFrame(columns=["month", "region_key", "price", "w_valid",
                                     "n_trades", "region_label"])
    trades["region_key"] = _region_key(trades, level)
    idx = _basket_index(trades, "deal_amount", params, min_weight)
    return idx.merge(_region_labels(trades, level), on="region_key", how="left")


def assign_tiers(index, n_tiers=5, min_months=24, as_of=None):
    """지역을 n_tiers 분위로 나눈다 (스펙 §3).

    티어는 시점 고정이다 - 월마다 다시 매기면 지역이 티어를 넘나들면서 비율 z가
    무의미해진다. tier=1이 최상위 가격대.

    분위를 나누는 기준은 "전 기간 평균 명목가"가 아니라 "월별 전지역 중위가 대비 상대
    수준의 전 기간 평균"이다(디플레이션). 명목가를 그대로 쓰면 관측 시작월이 늦은 지역
    (예: 2015년 이후 최초 거래된 신도시)은 그 구간의 전국 명목가 수준이 이미 높아진
    뒤라서, 실제 가격 수준과 무관하게 더 비싼 티어로 밀려 올라간다(나라 전체 ㎡당가가
    2006년 대비 2026년에 약 3배가 됐으므로 이 효과가 작지 않다). avg_price 컬럼 자체는
    화면에 그대로 노출되는 실제 만원/㎡ 값이라 디플레이션하지 않고 그대로 둔다 - 분위
    산정에만 디플레이션 평균을 쓴다.

    as_of를 주면 그 월까지의 관측만으로 티어를 정한다. 라이브 화면은 as_of=None(전 기간)을
    쓰지만, 백테스트에서 전 기간 티어를 쓰면 "2010년 시그널을 2026년 가격으로 만든 급지로
    평가하는" look-ahead가 된다. rv_z 자체는 _trailing_z의 shift(1) 덕에 누수가 없으므로
    티어 배정이 유일한 오염원이고, 이 인자가 그걸 막는다.
    """
    idx = index.copy()
    if as_of is not None:
        idx = idx[idx["month"] <= pd.Period(as_of, freq="M")]
        if idx.empty:
            empty = pd.DataFrame(columns=["region_key", "avg_price", "n_months", "tier"])
            return empty.astype({"tier": "int64"})
    idx["deflated"] = idx["price"] / idx.groupby("month")["price"].transform("median")
    agg = (idx.groupby("region_key")
              .agg(avg_price=("price", "mean"), avg_deflated=("deflated", "mean"),
                   n_months=("price", "size")).reset_index())
    if "region_label" in index.columns:
        agg = agg.merge(index[["region_key", "region_label"]].drop_duplicates("region_key"),
                        on="region_key", how="left")
    agg = agg[agg["n_months"] >= min_months].reset_index(drop=True)
    if agg.empty:
        agg["tier"] = pd.Series(dtype="int64")
        return agg.drop(columns=["avg_deflated"])

    n_eff = min(int(n_tiers), agg["region_key"].nunique())
    if n_eff <= 1:
        agg["tier"] = 1
        return agg.drop(columns=["avg_deflated"])
    # rank(first)로 동률을 풀어 분위 경계가 터지지 않게 한 뒤, qcut 방향을 뒤집어
    # 1이 최상위 가격대가 되게 한다.
    q = pd.qcut(agg["avg_deflated"].rank(method="first"), n_eff, labels=False, duplicates="drop")
    agg["tier"] = (q.max() - q + 1).astype(int)
    return agg.drop(columns=["avg_deflated"])


def _loo_median(s: pd.Series) -> pd.Series:
    """자기 자신을 뺀 중위값 (스펙 §4).

    자기포함 중위값을 쓰면 티어 구성원이 홀수일 때 정중앙 지역의 ratio가 매월 정확히
    1.0로 고정되고 표준편차 0 -> rv_z가 영구 NaN이 된다.

    정렬 기반 O(n log n). n개 중 하나를 빼면 남은 n-1개의 중위값은 정렬된 배열에서
    제거된 원소의 위치에 따라 두세 가지 값 중 하나로 결정된다.
    """
    v = s.to_numpy(dtype=float)
    n = len(v)
    if n <= 1:
        return pd.Series(np.nan, index=s.index)
    order = np.argsort(v, kind="stable")
    sv = v[order]
    rank = np.empty(n, dtype=int)
    rank[order] = np.arange(n)
    k = n // 2
    if n % 2 == 0:          # n-1이 홀수 -> 남은 것의 중위는 단일 원소
        out = np.where(rank < k, sv[k], sv[k - 1])
    else:                   # n-1이 짝수 -> 두 원소의 평균
        lo = (sv[k] + sv[k + 1]) / 2 if k + 1 < n else np.nan
        hi = (sv[k - 1] + sv[k]) / 2
        mid = (sv[k - 1] + sv[k + 1]) / 2 if k + 1 < n else np.nan
        out = np.where(rank < k, lo, np.where(rank > k, hi, mid))
    return pd.Series(out, index=s.index)


def region_rv(index, tiers, params=None):
    """급지 대비 저평가 (스펙 §4). rv_z가 음수면 같은 급지 대비 평소보다 싸다.

    반환: index의 컬럼 + tier, tier_median, ratio, rv_z
    """
    params = params or Params()
    df = index.merge(tiers[["region_key", "tier"]], on="region_key", how="inner")
    if df.empty:
        return df.assign(tier_median=np.nan, ratio=np.nan, rv_z=np.nan)
    df["tier_median"] = df.groupby(["tier", "month"], observed=True)["price"].transform(_loo_median)
    df["ratio"] = df["price"] / df["tier_median"]
    df = df.sort_values(["region_key", "month"]).reset_index(drop=True)
    df["rv_z"] = (df.groupby("region_key", observed=True)["ratio"]
                    .transform(lambda s: _trailing_z(s, params.lookback_months,
                                                     params.min_group_z)))
    return df


def pair_ratio(index, key_a, key_b, params=None):
    """두 지역 직접 비교 (스펙 §4.1). 티어가 달라도 비교 가능하다.

    반환: month, price_a, price_b, ratio, z
    """
    params = params or Params()
    a = index[index["region_key"] == key_a].set_index("month")["price"].rename("price_a")
    b = index[index["region_key"] == key_b].set_index("month")["price"].rename("price_b")
    out = pd.concat([a, b], axis=1).dropna().sort_index()
    if out.empty:
        return out.assign(ratio=np.nan, z=np.nan).reset_index(names="month")
    out["ratio"] = out["price_a"] / out["price_b"]
    out["z"] = _trailing_z(out["ratio"], params.lookback_months, params.min_group_z)
    return out.reset_index(names="month")


def region_jeonse_ratio(conn, sale_index, level="sgg", params=None, min_weight=0.5):
    """지역 전세가율 (표시 전용). 매매와 같은 고정 바스켓을 전세 보증금에 적용한 뒤
    sale_index의 매매 대표가로 나눈다. 순수 전세(월세 0)만 쓰고, trades_jeonse는
    2011-01부터라 그 이전 월은 NaN이 된다.

    반환: region_key, month, jeonse_price, jeonse_ratio
    """
    _check_level(level)
    params = params or Params()
    base = sale_index[["region_key", "month", "price"]].copy()
    has_table = pd.read_sql_query(
        "SELECT COUNT(*) n FROM sqlite_master WHERE type='table' AND name='trades_jeonse'",
        conn).iat[0, 0]
    if has_table:
        tr = _load_trades(conn, "trades_jeonse", "deposit",
                          "AND COALESCE(monthly_rent, 0) = 0")
    else:
        tr = pd.DataFrame()
    if tr.empty:
        return base.assign(jeonse_price=np.nan,
                           jeonse_ratio=np.nan)[["region_key", "month",
                                                 "jeonse_price", "jeonse_ratio"]]
    tr["region_key"] = _region_key(tr, level)
    sale_w = _sale_cell_weights(conn, params)
    jeonse = (_basket_index(tr, "deposit", params, min_weight, weights=sale_w)
              .rename(columns={"price": "jeonse_price"})[["region_key", "month",
                                                          "jeonse_price"]])
    out = base.merge(jeonse, on=["region_key", "month"], how="left")
    out["jeonse_ratio"] = out["jeonse_price"] / out["price"]
    return out[["region_key", "month", "jeonse_price", "jeonse_ratio"]]


if __name__ == "__main__":
    import sqlite3
    import sys
    import time

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    level = sys.argv[1] if len(sys.argv) > 1 else "sgg"
    conn = sqlite3.connect(DB_PATH)
    t0 = time.time()
    idx = region_price_index(conn, level)
    print("[%s] index %.1fs rows=%d regions=%d %s~%s"
          % (level, time.time() - t0, len(idx), idx["region_key"].nunique(),
             idx["month"].min(), idx["month"].max()))

    tiers = assign_tiers(idx)
    print("\n[티어 배정] 랭킹 가능 %d / 전체 %d"
          % (len(tiers), idx["region_key"].nunique()))
    for tv, g in tiers.sort_values("avg_price", ascending=False).groupby("tier"):
        head = ", ".join(g.sort_values("avg_price", ascending=False)["region_label"].head(8))
        print("  T%d (%d개): %s" % (tv, len(g), head))

    rv = region_rv(idx, tiers)
    last = rv[rv["month"] == rv["month"].max()]
    print("\n[%s 급지 대비 저평가 상위 10]" % rv["month"].max())
    cols = ["region_label", "tier", "price", "tier_median", "ratio", "rv_z"]
    print(last.sort_values("rv_z")[cols].head(10)
              .to_string(index=False, float_format=lambda x: "%.2f" % x))

    if level == "sgg":
        key = dict(zip(idx["region_label"], idx["region_key"]))
        def _find(sub):
            hits = [v for v in key if sub in v]
            return (key[hits[0]], hits[0]) if hits else (None, None)
        for a_sub, b_sub in [("분당", "양천"), ("과천", "분당")]:
            (ka, la), (kb, lb) = _find(a_sub), _find(b_sub)
            if ka and kb:
                pr = pair_ratio(idx, ka, kb)
                print("\n%s / %s : 현재 %.3f배, 전체평균 %.3f배, z %+.2f"
                      % (la, lb, pr["ratio"].iloc[-1], pr["ratio"].mean(), pr["z"].iloc[-1]))
    conn.close()
