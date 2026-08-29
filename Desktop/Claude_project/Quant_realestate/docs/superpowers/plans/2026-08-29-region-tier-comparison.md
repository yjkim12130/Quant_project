# 급지 비교 (Region Tier Comparison) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 비슷한 급지(장기 평균 가격대)에 속한 지역끼리 비교해 저평가된 시/구·동을 찾는 조회용 탭을 추가한다.

**Architecture:** 신규 모듈 `scoring/region_rv.py` 하나가 고정 바스켓 지역 가격지수 → 급지 티어 배정 → 급지 대비 비율 z-score를 계산하고, `app.py`가 신규 탭에서 `@st.cache_data`로 감싸 호출한다. 배치 적재 테이블 없이 앱 런타임에서 계산한다(실측 26초, 세션당 1회). `scoring/engine.py`는 수정하지 않고 밴드 정의·z 함수만 import해서 재사용한다.

**Tech Stack:** Python 3, pandas 2.2.3, numpy 1.26.4, plotly 5.22.0, streamlit 1.41.1, pytest, SQLite (`data/realestate.db`)

**Spec:** `docs/region_tier_spec_v1.md`

## Global Constraints

- **`scoring/engine.py`를 수정하지 않는다.** `Params`, `DB_PATH`, `area_band`, `AGE_BAND_LABELS`, `_trailing_z`를 import해서 쓴다. 지역 그룹핑 로직은 전부 `scoring/region_rv.py` 안에만 존재한다 (기존 원칙: "그룹 정의는 `make_group_key()` 하나에만 존재").
- **부호 관례: z가 음수면 싸다.** 단지 `rv_z`, 자산비교 탭 `asset_ratio_zscore()`와 동일하게 통일한다.
- **평활 파라미터는 `Params` 값을 그대로 쓴다**: `roll_window=3`, `ffill_limit=6`, `lookback_months=24`, `min_group_z=12`, `area_bounds=(60.0, 85.0)`, `age_bounds=(10, 25)`. 지역 지수만 다른 값을 쓰면 단지 `rv_z`와 비교가 불가능해진다.
- **기본값**: `min_weight=0.5`, `min_months=24`, `n_tiers=5`.
- **`print`문에 em-dash(—) 등 특수 유니코드를 쓰지 않는다.** Windows 콘솔이 cp949라 `UnicodeEncodeError`가 난다 (2026-08-15 확인된 제약). 문서·주석·Streamlit 문자열에는 써도 된다.
- **스코어링에 반영 금지.** 이 기능은 조회 전용이다. `scoring/engine.py`의 `combine_scores()`나 스크리너 탭의 점수·하드필터에 지역 `rv_z`를 절대 섞지 않는다 (백테스트 검증 전, 스펙 §7).
- **plotly 차트 레이아웃**은 기존 8개 차트와 동일하게 `legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)` + 넉넉한 `margin.t`를 준다.
- **git**: 홈 디렉터리(`C:\Users\yjkim`)가 저장소 루트다. `git add -A`를 절대 쓰지 말고 항상 파일 경로를 지정해서 add한다.
- 작업 시작 시점 기준 `python -m pytest tests/ -q` 는 **62 passed**다. 이 숫자가 줄어들면 회귀다.

## File Structure

| 파일 | 역할 |
|---|---|
| `scoring/region_rv.py` (신규) | 스펙 §2~4 전부. 지역키/셀 라벨 → 고정 바스켓 지수 → 티어 → 급지 대비 z → 페어 비교 → 전세가율 |
| `tests/test_region_rv.py` (신규) | 위 모듈의 단위 테스트. 합성 데이터만 쓰고 DB에 접근하지 않는다 |
| `app.py` (수정) | 탭 목록에 `🗺️ 급지 비교` 추가 + 탭 본문(로더·컨트롤·랭킹표·페어차트·산포도·읽는 법) |

`region_rv.py`는 계산만 하고 Streamlit을 import하지 않는다. 캐싱은 전부 `app.py` 쪽 래퍼가 담당한다 — 기존 `scoring/market_context.py`와 같은 분리다.

---

### Task 1: 지역키·셀 라벨·고정 바스켓 지수

**Files:**
- Create: `scoring/region_rv.py`
- Test: `tests/test_region_rv.py`

**Interfaces:**
- Consumes: `scoring.engine`의 `Params`, `DB_PATH`, `area_band`, `AGE_BAND_LABELS`, `_trailing_z`
- Produces:
  - `LEVELS = ("sgg", "dong")`, `CELL_SEP = "|"`
  - `_check_level(level) -> None` (잘못된 값이면 `ValueError`)
  - `_region_key(trades: pd.DataFrame, level: str) -> pd.Series`
  - `_region_labels(trades: pd.DataFrame, level: str) -> pd.DataFrame` — columns `region_key, region_label`
  - `_cell_labels(trades: pd.DataFrame, params: Params) -> pd.Series`
  - `_basket_index(trades, amount_col, params, min_weight) -> pd.DataFrame` — columns `month, region_key, price, w_valid, n_trades`. `trades`에는 `region_key` 컬럼이 이미 있어야 한다.

- [ ] **Step 1: 테스트 파일에 합성 데이터 헬퍼와 첫 3개 테스트를 작성**

`tests/test_region_rv.py`를 새로 만든다. 9개 셀(면적 3밴드 × 연식 3밴드)이 서로 완전히 분리되도록 건축년도를 고른 것이 핵심이다 — 2020~2021년 기준으로 2015년생은 `~10y`, 2007년생은 `10~25y`, 1990년생은 `25y~`에 안정적으로 떨어진다.

```python
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
```

- [ ] **Step 2: 테스트를 돌려 실패를 확인**

Run: `python -m pytest tests/test_region_rv.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'scoring.region_rv'`

- [ ] **Step 3: `scoring/region_rv.py`를 만들고 최소 구현을 작성**

```python
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


def _basket_index(trades, amount_col, params, min_weight):
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
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest tests/test_region_rv.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: 전체 테스트로 회귀가 없는지 확인**

Run: `python -m pytest tests/ -q`
Expected: 67 passed (기존 62 + 신규 5)

- [ ] **Step 6: 커밋**

```bash
git add Desktop/Claude_project/Quant_realestate/scoring/region_rv.py Desktop/Claude_project/Quant_realestate/tests/test_region_rv.py
git commit -m "feat(realestate): add fixed-basket region price index"
```

---

### Task 2: DB에서 지역 가격지수 만들기

**Files:**
- Modify: `scoring/region_rv.py` (Task 1 코드 뒤에 이어붙임)
- Test: `tests/test_region_rv.py`

**Interfaces:**
- Consumes: Task 1의 `_region_key`, `_region_labels`, `_basket_index`, `_check_level`
- Produces:
  - `_load_trades(conn, table, amount_col, extra_where="") -> pd.DataFrame` — `month`(Period[M]) 컬럼이 붙고 결측·이상 행이 제거된 실거래
  - `region_price_index(conn, level="sgg", params=None, min_weight=0.5) -> pd.DataFrame` — columns `month, region_key, price, w_valid, n_trades, region_label`

- [ ] **Step 1: 실패하는 테스트를 작성**

`tests/test_region_rv.py` 끝에 추가한다. 실제 DB 대신 인메모리 SQLite에 최소 스키마를 만들어 쓴다 — 테스트는 `data/realestate.db`에 의존하지 않는다.

```python
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
```

- [ ] **Step 2: 테스트를 돌려 실패를 확인**

Run: `python -m pytest tests/test_region_rv.py -q`
Expected: FAIL — `AttributeError: module 'scoring.region_rv' has no attribute 'region_price_index'`

- [ ] **Step 3: 구현을 추가**

```python
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
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest tests/test_region_rv.py -q`
Expected: PASS (8 passed)

- [ ] **Step 5: 커밋**

```bash
git add Desktop/Claude_project/Quant_realestate/scoring/region_rv.py Desktop/Claude_project/Quant_realestate/tests/test_region_rv.py
git commit -m "feat(realestate): load region price index from trades DB"
```

---

### Task 3: 급지 티어 배정

**Files:**
- Modify: `scoring/region_rv.py`
- Test: `tests/test_region_rv.py`

**Interfaces:**
- Consumes: Task 2의 `region_price_index()` 출력 형태
- Produces: `assign_tiers(index, n_tiers=5, min_months=24) -> pd.DataFrame` — columns `region_key, avg_price, n_months, region_label, tier`. `tier`는 1이 최상위 가격대.

- [ ] **Step 1: 실패하는 테스트를 작성**

`tests/test_region_rv.py` 끝에 추가한다. `_fake_index()`는 Task 5·6에서도 재사용한다.

```python
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
```

- [ ] **Step 2: 테스트를 돌려 실패를 확인**

Run: `python -m pytest tests/test_region_rv.py -q -k assign_tiers`
Expected: FAIL — `AttributeError: module 'scoring.region_rv' has no attribute 'assign_tiers'`

- [ ] **Step 3: 구현을 추가**

`rank(method="first")`를 거쳐 `qcut`에 넣는 이유는 동률 가격이 있어도 분위 경계가 터지지 않게 하기 위함이다. `qcut`은 낮은 값에 0을 주므로 뒤집어서 1이 최상위가 되게 한다.

```python
def assign_tiers(index, n_tiers=5, min_months=24):
    """전 기간 평균 대표가로 지역을 n_tiers 분위로 나눈다 (스펙 §3).

    티어는 시점 고정이다 - 월마다 다시 매기면 지역이 티어를 넘나들면서 비율 z가
    무의미해진다. tier=1이 최상위 가격대.
    """
    agg = (index.groupby("region_key")
                .agg(avg_price=("price", "mean"), n_months=("price", "size")).reset_index())
    if "region_label" in index.columns:
        agg = agg.merge(index[["region_key", "region_label"]].drop_duplicates("region_key"),
                        on="region_key", how="left")
    agg = agg[agg["n_months"] >= min_months].reset_index(drop=True)
    if agg.empty:
        return agg.assign(tier=pd.Series(dtype="int64"))

    n_eff = min(int(n_tiers), agg["region_key"].nunique())
    if n_eff <= 1:
        return agg.assign(tier=1)
    # rank(first)로 동률을 풀어 분위 경계가 터지지 않게 한 뒤, qcut 방향을 뒤집어
    # 1이 최상위 가격대가 되게 한다.
    q = pd.qcut(agg["avg_price"].rank(method="first"), n_eff, labels=False, duplicates="drop")
    return agg.assign(tier=(q.max() - q + 1).astype(int))
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest tests/test_region_rv.py -q`
Expected: PASS (12 passed)

- [ ] **Step 5: 커밋**

```bash
git add Desktop/Claude_project/Quant_realestate/scoring/region_rv.py Desktop/Claude_project/Quant_realestate/tests/test_region_rv.py
git commit -m "feat(realestate): assign price tiers to regions"
```

---

### Task 4: leave-one-out 중위값과 급지 대비 z

**Files:**
- Modify: `scoring/region_rv.py`
- Test: `tests/test_region_rv.py`

**Interfaces:**
- Consumes: Task 3의 `assign_tiers()` 출력, `engine._trailing_z`
- Produces:
  - `_loo_median(s: pd.Series) -> pd.Series`
  - `region_rv(index, tiers, params=None) -> pd.DataFrame` — `index`의 컬럼 + `tier, tier_median, ratio, rv_z`

- [ ] **Step 1: 실패하는 테스트를 작성**

```python
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
```

- [ ] **Step 2: 테스트를 돌려 실패를 확인**

Run: `python -m pytest tests/test_region_rv.py -q -k "loo or region_rv or look_ahead or sign_convention or short_history"`
Expected: FAIL — `AttributeError: module 'scoring.region_rv' has no attribute '_loo_median'`

- [ ] **Step 3: 구현을 추가**

정렬 기반 leave-one-out은 실전 규모(928지역 × 247개월)에서 0.2초, 소박한 구현은 5.6초다.

```python
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
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest tests/test_region_rv.py -q`
Expected: PASS (18 passed)

- [ ] **Step 5: 커밋**

```bash
git add Desktop/Claude_project/Quant_realestate/scoring/region_rv.py Desktop/Claude_project/Quant_realestate/tests/test_region_rv.py
git commit -m "feat(realestate): add leave-one-out tier median and region rv_z"
```

---

### Task 5: 페어 비교와 전세가율

**Files:**
- Modify: `scoring/region_rv.py`
- Test: `tests/test_region_rv.py`

**Interfaces:**
- Consumes: Task 2의 `region_price_index()`/`_load_trades`/`_basket_index`, `engine._trailing_z`
- Produces:
  - `pair_ratio(index, key_a, key_b, params=None) -> pd.DataFrame` — columns `month, price_a, price_b, ratio, z`
  - `region_jeonse_ratio(conn, sale_index, level="sgg", params=None, min_weight=0.5) -> pd.DataFrame` — columns `region_key, month, jeonse_price, jeonse_ratio`

- [ ] **Step 1: 실패하는 테스트를 작성**

```python
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
```

- [ ] **Step 2: 테스트를 돌려 실패를 확인**

Run: `python -m pytest tests/test_region_rv.py -q -k "pair_ratio or jeonse"`
Expected: FAIL — `AttributeError: module 'scoring.region_rv' has no attribute 'pair_ratio'`

- [ ] **Step 3: 구현을 추가**

```python
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
    try:
        tr = _load_trades(conn, "trades_jeonse", "deposit",
                          "AND COALESCE(monthly_rent, 0) = 0")
    except Exception:  # noqa: BLE001 - 테이블 자체가 없는 중간 상태 방어
        tr = pd.DataFrame()
    if tr.empty:
        return base.assign(jeonse_price=np.nan,
                           jeonse_ratio=np.nan)[["region_key", "month",
                                                 "jeonse_price", "jeonse_ratio"]]
    tr["region_key"] = _region_key(tr, level)
    jeonse = (_basket_index(tr, "deposit", params, min_weight)
              .rename(columns={"price": "jeonse_price"})[["region_key", "month",
                                                          "jeonse_price"]])
    out = base.merge(jeonse, on=["region_key", "month"], how="left")
    out["jeonse_ratio"] = out["jeonse_price"] / out["price"]
    return out[["region_key", "month", "jeonse_price", "jeonse_ratio"]]
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `python -m pytest tests/test_region_rv.py -q`
Expected: PASS (22 passed)

- [ ] **Step 5: 전체 테스트로 회귀가 없는지 확인**

Run: `python -m pytest tests/ -q`
Expected: 84 passed

- [ ] **Step 6: 커밋**

```bash
git add Desktop/Claude_project/Quant_realestate/scoring/region_rv.py Desktop/Claude_project/Quant_realestate/tests/test_region_rv.py
git commit -m "feat(realestate): add pair comparison and region jeonse ratio"
```

---

### Task 6: 실데이터 스모크 진입점

**Files:**
- Modify: `scoring/region_rv.py` (파일 끝에 `__main__` 블록 추가)

**Interfaces:**
- Consumes: Task 2~5의 모든 공개 함수
- Produces: `python -m scoring.region_rv` 실행 시 티어 배정과 저평가 상위 지역, 사용자 예시 페어를 콘솔에 출력

- [ ] **Step 1: `__main__` 블록을 추가**

콘솔이 cp949라 `print`에 특수 유니코드를 쓰지 않는다. `sys.stdout.reconfigure`로 한글 출력이 깨지지 않게 한다.

```python
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
```

- [ ] **Step 2: 시군구 레벨로 실행해 결과를 확인**

Run: `python -m scoring.region_rv sgg`

Expected (2026-08-29 실측 기준값 - 데이터가 갱신되면 숫자는 달라질 수 있으나 방향은 유지되어야 한다):
- `regions=68`, 기간 `2006-01~2026-07`, 소요 25~30초
- 랭킹 가능 68 / 68
- T1에 강남구·서초구·송파구·용산구·성동구·성남시 분당구·과천시가 포함
- `분당구 / 양천구 : 현재 1.552배, 전체평균 1.246배, z +1.40`
- `과천시 / 분당구 : 현재 1.271배, 전체평균 1.339배, z -1.55`

값이 크게 다르면 멈추고 원인을 보고한다. 특히 T1에 외곽 지역이 섞이면 티어 방향이 뒤집힌 것이다.

- [ ] **Step 2b: |z| > 3 인 지역이 데이터 버그가 아닌지 확인**

2026-08-29 실측에서 관악구가 `rv_z = -4.87`로 나온다. 이건 버그가 아니라 **배수가 유난히
안정적이던 지역이라 σ가 작아서** 생기는 정상 동작이다(스펙 §6 "z 과대표시 주의"). 다음으로
확인한다.

```bash
python -c "
import sqlite3, sys
sys.stdout.reconfigure(encoding='utf-8')
from scoring.region_rv import region_price_index, assign_tiers, region_rv
conn = sqlite3.connect('data/realestate.db')
idx = region_price_index(conn, 'sgg')
rv = region_rv(idx, assign_tiers(idx))
g = rv[rv.region_label == '관악구'].sort_values('month').tail(25)
print('ratio 평균 %.4f  std %.5f' % (g.ratio.head(24).mean(), g.ratio.head(24).std()))
print('최신 ratio %.3f  rv_z %.2f  w_valid %.2f' % (g.ratio.iloc[-1], g.rv_z.iloc[-1], g.w_valid.iloc[-1]))
conn.close()"
```

Expected: `ratio 평균 1.0483 std 0.01651`, `최신 ratio 0.968 rv_z -4.87 w_valid 1.00`.
`w_valid`가 1.00이면 9셀이 전부 관측된 정상 달이라는 뜻이므로 데이터 문제가 아니다.
반대로 `w_valid`가 게이트 언저리(0.5~0.6)면서 z가 극단이면 그건 얇은 표본 문제이니 보고한다.

- [ ] **Step 3: 동 레벨로 실행해 커버리지를 확인**

Run: `python -m scoring.region_rv dong`

Expected: `regions=928`, 랭킹 가능 **611 / 928** 근처. 소요 30~40초. 랭킹 가능 수가 900을 넘으면 게이트가 동작하지 않는 것이고, 300 아래면 게이트가 과하게 걸린 것이다.

- [ ] **Step 4: 커밋**

```bash
git add Desktop/Claude_project/Quant_realestate/scoring/region_rv.py
git commit -m "feat(realestate): add region_rv smoke entrypoint"
```

---

### Task 7: 급지 비교 탭 - 로더·컨트롤·랭킹표

**Files:**
- Modify: `app.py:103-105` (탭 목록), `app.py` (TabA 블록 끝 ~ TabS 시작 사이에 신규 섹션 삽입)

**Interfaces:**
- Consumes: `scoring.region_rv`의 `region_price_index`, `assign_tiers`, `region_rv`, `region_jeonse_ratio`
- Produces: `load_region_index(level)`, `load_region_jeonse(level)` 캐시 로더와 `tabR` 탭 변수

- [ ] **Step 1: 탭 목록에 신규 탭을 추가**

`app.py:103-105`를 다음으로 교체한다.

```python
tab0, tabT, tabA, tabR, tabS, tabTr, tab1, tab2, tab3 = st.tabs(
    ["📖 가이드", "⏱️ 매수 타이밍", "🌐 자산 비교", "🗺️ 급지 비교", "🏗️ 공급", "🚇 교통",
     "🔍 저평가 스크리너", "🏢 단지 상세", "🧪 백테스트"])
```

- [ ] **Step 2: 앱을 띄워 탭이 늘어났는지 확인**

Run: `streamlit run app.py --server.headless true`
Expected: 브라우저 `localhost:8502`에서 탭이 9개, `🗺️ 급지 비교`는 아직 빈 화면. 확인 후 Ctrl+C.

- [ ] **Step 3: 캐시 로더와 탭 본문(컨트롤 + 랭킹표)을 작성**

`# ---------------------------------------------------------------- TabS 공급` 주석 바로 위에 삽입한다.

```python
# ---------------------------------------------------------------- TabR 급지 비교

REGION_LEVELS = {"구 단위 (시군구 68개)": "sgg", "동 단위 (법정동 928개)": "dong"}


@st.cache_data(ttl=3600, show_spinner="지역 가격지수 계산 중 (최초 1회, 30초 내외)...")
def load_region_index(level):
    import sqlite3
    from scoring.engine import DB_PATH
    from scoring.region_rv import region_price_index
    conn = sqlite3.connect(DB_PATH)
    try:
        return region_price_index(conn, level)
    except Exception:  # noqa: BLE001 - 테이블 부재 등 중간 상태에서도 앱이 죽지 않게
        return pd.DataFrame(columns=["month", "region_key", "price", "w_valid",
                                     "n_trades", "region_label"])
    finally:
        conn.close()


@st.cache_data(ttl=3600, show_spinner="전세가율 계산 중...")
def load_region_jeonse(level):
    """전세는 654만 행이라 무겁다. 사용자가 전세가율을 켤 때만 호출한다."""
    import sqlite3
    from scoring.engine import DB_PATH
    from scoring.region_rv import region_jeonse_ratio
    idx = load_region_index(level)
    if idx.empty:
        return pd.DataFrame(columns=["region_key", "month", "jeonse_price", "jeonse_ratio"])
    conn = sqlite3.connect(DB_PATH)
    try:
        return region_jeonse_ratio(conn, idx, level)
    except Exception:  # noqa: BLE001
        return pd.DataFrame(columns=["region_key", "month", "jeonse_price", "jeonse_ratio"])
    finally:
        conn.close()


with tabR:
    try:
        from scoring.region_rv import assign_tiers, pair_ratio, region_rv as compute_region_rv

        st.markdown("##### 비슷한 급지끼리 비교 - 같은 급지에서 평소보다 싸진 곳 찾기")
        c1, c2 = st.columns([2, 1])
        level_label = c1.radio("비교 단위", list(REGION_LEVELS), horizontal=True)
        level = REGION_LEVELS[level_label]
        n_tiers = c2.slider("급지 개수", 3, 8, 5)

        r_idx = load_region_index(level)
        if r_idx.empty:
            st.warning("지역 가격지수를 계산할 데이터가 없습니다. 실거래 적재 상태를 확인하세요.")
        else:
            r_tiers = assign_tiers(r_idx, n_tiers=n_tiers)
            total = r_idx["region_key"].nunique()
            st.caption(f"{level_label.split()[0]} 단위: 전체 {total}개 중 **{len(r_tiers)}개** "
                       f"랭킹 가능 (거래가 희소해 대표가를 못 만드는 지역은 제외됩니다)")

            rv = compute_region_rv(r_idx, r_tiers)
            latest = rv["month"].max()
            snap = rv[rv["month"] == latest].copy()

            # 12개월 모멘텀 - 표시 전용
            mom = (r_idx.sort_values("month").groupby("region_key")["price"]
                        .apply(lambda s: s.iloc[-1] / s.iloc[-13] - 1 if len(s) > 12 else np.nan)
                        .rename("mom12").reset_index())
            snap = snap.merge(mom, on="region_key", how="left")
            n_months = (r_idx.groupby("region_key")["price"].size()
                             .rename("n_months").reset_index())
            snap = snap.merge(n_months, on="region_key", how="left")

            show_jr = st.checkbox("전세가율 함께 보기 (추가 로딩 30초)", value=False)
            if show_jr:
                jr = load_region_jeonse(level)
                jr_last = jr[jr["month"] == latest][["region_key", "jeonse_ratio"]]
                snap = snap.merge(jr_last, on="region_key", how="left")

            tier_opts = sorted(r_tiers["tier"].unique())
            sel_tier = st.selectbox(
                "급지 선택", tier_opts, format_func=lambda t: (
                    f"T{t} - {', '.join(r_tiers[r_tiers['tier'] == t].sort_values('avg_price', ascending=False)['region_label'].head(4))} 등"))

            table = snap[snap["tier"] == sel_tier].sort_values("rv_z")
            cols = {"region_label": "지역", "price": "대표가(만원/㎡)", "rv_z": "급지대비 z",
                    "ratio": "급지대비 배수", "mom12": "12개월 모멘텀", "n_months": "관측월수"}
            if show_jr:
                cols["jeonse_ratio"] = "전세가율"
            view = table[[c for c in cols if c in table.columns]].rename(columns=cols)
            st.dataframe(
                view.style.format({"대표가(만원/㎡)": "{:,.0f}", "급지대비 z": "{:+.2f}",
                                   "급지대비 배수": "{:.3f}", "12개월 모멘텀": "{:+.1%}",
                                   "전세가율": "{:.1%}"}, na_rep="-"),
                hide_index=True, use_container_width=True)

            cheap = table[table["rv_z"] < -1.0]["region_label"].head(3).tolist()
            msg = (f"기준월 {latest}. T{sel_tier} 급지 {len(table)}개 지역 중 "
                   f"급지 대비 -1σ보다 싸진 곳은 {len(table[table['rv_z'] < -1.0])}곳입니다. ")
            msg += (f"가장 싼 쪽부터 <b>{', '.join(cheap)}</b>. " if cheap
                    else "지금은 -1σ를 넘는 곳이 없습니다. ")
            msg += ("z는 '이 지역이 같은 급지 평균 대비 평소보다 얼마나 싸졌는가'이지 "
                    "'절대적으로 싸다'가 아닙니다. 아직 백테스트로 검증되지 않은 지표입니다.")
            _ai_box(msg)
    except Exception as e:  # noqa: BLE001
        st.error(f"급지 비교 탭 오류: {e}")
        st.exception(e)
```

- [ ] **Step 4: 앱을 띄워 랭킹표를 눈으로 확인**

Run: `streamlit run app.py --server.headless true`

Expected:
- 구 단위: "전체 68개 중 68개 랭킹 가능"
- T1을 고르면 강남구·서초구·송파구·용산구·성동구·분당구·과천시 등이 나오고 `급지대비 z` 오름차순 정렬
- 동 단위로 바꾸면 "전체 928개 중 611개 랭킹 가능" 근처
- 전세가율 체크박스를 켜면 추가 로딩 후 컬럼이 하나 늘어남

확인 후 Ctrl+C.

- [ ] **Step 5: 기존 탭이 안 깨졌는지 확인**

같은 실행에서 `🔍 저평가 스크리너`, `🏢 단지 상세`, `🌐 자산 비교` 탭을 한 번씩 열어 에러가 없는지 본다.

- [ ] **Step 6: 커밋**

```bash
git add Desktop/Claude_project/Quant_realestate/app.py
git commit -m "feat(realestate): add region tier comparison tab with ranking table"
```

---

### Task 8: 급지 비교 탭 - 페어 차트·산포도·읽는 법

**Files:**
- Modify: `app.py` (Task 7에서 만든 `with tabR:` 블록 끝, `_ai_box(msg)` 다음)

**Interfaces:**
- Consumes: Task 7의 `r_idx`, `r_tiers`, `snap`, `latest`, `level_label`, `pair_ratio`

- [ ] **Step 1: 페어 차트를 추가**

Task 7의 `_ai_box(msg)` 바로 다음(같은 `else:` 블록 안)에 이어 붙인다.

```python
            st.divider()
            st.markdown("##### 두 지역 직접 비교")
            label2key = dict(zip(r_tiers["region_label"], r_tiers["region_key"]))
            names = sorted(label2key)
            d1, d2 = st.columns(2)
            def _pick(col, title, default):
                i = names.index(default) if default in names else 0
                return col.selectbox(title, names, index=i)
            name_a = _pick(d1, "지역 A", next((n for n in names if "분당" in n), names[0]))
            name_b = _pick(d2, "지역 B", next((n for n in names if "양천" in n), names[-1]))

            pr = pair_ratio(r_idx, label2key[name_a], label2key[name_b])
            if len(pr) < 13:
                st.info("두 지역이 겹치는 기간이 짧아 비교 차트를 그릴 수 없습니다.")
            else:
                mu, sd = pr["ratio"].mean(), pr["ratio"].std()
                x = pr["month"].dt.to_timestamp()
                figp = go.Figure()
                figp.add_trace(go.Scatter(x=x, y=pr["ratio"], name=f"{name_a} / {name_b}",
                                          line=dict(color=ACCENT, width=2.5)))
                figp.add_hline(y=mu, line=dict(color="#888", dash="dash"),
                               annotation_text=f"평균 {mu:.3f}배")
                for k, dash in [(1, "dot"), (-1, "dot")]:
                    figp.add_hline(y=mu + k * sd, line=dict(color="#bbb", dash=dash))
                figp.update_layout(
                    title=f"{name_a} / {name_b} 대표가 배수", height=420,
                    margin=dict(t=110, b=0), yaxis=dict(title="배수"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                xanchor="left", x=0))
                st.plotly_chart(figp, use_container_width=True)

                cur, z = pr["ratio"].iloc[-1], pr["z"].iloc[-1]
                if pd.isna(z):
                    verdict = "관측 기간이 짧아 z를 낼 수 없습니다."
                elif z > 0:
                    verdict = (f"<b>{name_a}</b>가 평소보다 비싸졌습니다 "
                               f"(뒤집어 보면 {name_b}가 상대적으로 싸진 것)")
                else:
                    verdict = f"<b>{name_a}</b>가 {name_b} 대비 평소보다 싸졌습니다"
                _ai_box(f"{name_a}/{name_b} 현재 <b>{cur:.3f}배</b>, 전체 기간 평균 "
                        f"{mu:.3f}배 (±1σ = {mu - sd:.3f}~{mu + sd:.3f}). "
                        f"z {z:+.2f} - {verdict}.")
```

- [ ] **Step 2: 앱을 띄워 페어 차트를 확인**

Run: `streamlit run app.py --server.headless true`
Expected: 구 단위 기본값에서 `성남시 분당구 / 양천구` 차트가 뜨고, 현재 배수 약 1.55, 평균 약 1.25, z 약 +1.40. 해석 카드가 "분당구가 평소보다 비싸졌습니다"로 나온다. Ctrl+C.

- [ ] **Step 3: 산포도와 읽는 법을 추가**

Step 1에서 붙인 코드 바로 다음에 이어 붙인다.

```python
            st.divider()
            st.markdown("##### 급지 지도 - 가격대와 저평가 정도를 한눈에")
            sc = snap.dropna(subset=["rv_z"])
            figs = go.Figure()
            for tv in sorted(sc["tier"].unique()):
                g = sc[sc["tier"] == tv]
                figs.add_trace(go.Scatter(
                    x=g["price"], y=g["rv_z"], mode="markers", name=f"T{tv}",
                    marker=dict(size=9, opacity=0.8),
                    text=g["region_label"], customdata=g[["n_months"]],
                    hovertemplate="%{text}<br>대표가 %{x:,.0f}만원/㎡<br>"
                                  "급지대비 z %{y:+.2f}<br>관측 %{customdata[0]}개월<extra></extra>"))
            figs.add_hline(y=-1.0, line=dict(color=RED, dash="dot"),
                           annotation_text="-1σ")
            figs.update_layout(
                title=f"{latest} 기준 - 아래쪽일수록 같은 급지 대비 싸진 지역",
                height=520, margin=dict(t=110, b=0),
                xaxis=dict(title="대표가 (만원/㎡)"), yaxis=dict(title="급지 대비 z"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02,
                            xanchor="left", x=0))
            st.plotly_chart(figs, use_container_width=True)

            with st.expander("📖 읽는 법"):
                st.markdown(f"""
- **급지(티어)**: 전 기간 평균 ㎡당가로 지역을 {n_tiers}등분한 것. **티어 자체는 신호가 아닙니다** -
  T5에 있다고 싼 게 아니고 T1에 있다고 비싼 게 아닙니다. 어느 지역과 비교할지를 정할 뿐입니다.
  티어는 시점 고정입니다(월마다 다시 매기면 비교 대상이 흔들려 z가 무의미해집니다).
- **급지 대비 z**: 이 지역 대표가 ÷ 같은 급지의 다른 지역들 중위값. 그 배수가 자기 역사(24개월)
  대비 몇 σ 떨어져 있는지. **음수 = 같은 급지 안에서 평소보다 싸졌다.** 스크리너의 단지 `rv_z`,
  자산 비교 탭의 z와 부호 관례가 같습니다. 계산에 현재값을 넣지 않아(shift 1) 미래 정보 누수가
  없습니다.
- ⚠️ **z가 큰 것과 많이 싼 것은 다릅니다.** z의 분모는 그 지역 배수의 24개월 표준편차라,
  **평소 급지 평균에 딱 붙어 있던 지역은 σ가 작아 작은 이탈도 큰 z로 찍힙니다.** 그래서 표에
  `급지대비 배수`를 함께 실었습니다 — z가 -4σ라도 배수가 1.05에서 0.97로 내려온 정도라면
  "역사적으로 이례적"이긴 해도 "많이 싸다"는 아닙니다. 두 숫자를 같이 보세요.
- **대표가(고정 바스켓)**: 그냥 그 달 거래의 중위 ㎡당가를 쓰면, 신축 대단지가 입주한 달에는
  가격이 안 올랐어도 지역 평균이 뛰어 보입니다. 그래서 면적 3밴드 × 연식 3밴드 = 9칸으로 나눠
  각각 중위가를 낸 뒤, **모든 지역에 똑같은 가중치**로 합칩니다. "모든 지역이 똑같은 구성의
  아파트를 가졌다면" 기준이라 지역 간 비교가 공정해집니다.
  - 다만 **칸 안의 변화는 못 잡습니다.** 예를 들어 `~10년` 칸 안에서 2016년생과 갓 입주한
    2025년생의 거래 비중이 바뀌는 것은 그대로 남습니다.
- **랭킹에서 빠지는 지역**: 9칸 중 절반 이상이 거래된 달이 24개월 이상이어야 랭킹에 오릅니다.
  동 단위는 거래가 희소해 3분의 1가량이 빠집니다. **빠졌다는 건 "저평가가 아니다"가 아니라
  "판단할 데이터가 없다"는 뜻입니다.**
- **전세가율**: 같은 고정 바스켓을 전세 보증금에 적용한 값 ÷ 매매 대표가. 순수 전세(월세 0)만
  씁니다. 전세 실거래는 2011년부터라 그 이전은 비어 있습니다.
- **데이터**: 국토교통부 실거래가 - 매매 2006-01~, 전세 2011-01~ (해제 거래 제외).
- ⚠️ **이 지표는 아직 백테스트로 검증되지 않았습니다.** 단지 스크리너의 `rv_z`는 그룹 대비
  초과수익 +7.3%p(12개월, p<0.001)까지 확인하고 쓰는 반면, 지역 레벨 z는 같은 검증을 거치지
  않았습니다. 그래서 스크리너 점수에 섞지 않고 조회 전용으로만 둡니다.
""")
```

- [ ] **Step 4: 앱을 띄워 산포도와 읽는 법을 확인**

Run: `streamlit run app.py --server.headless true`

Expected:
- 산포도에 티어별 색이 다른 점들이 뜨고, hover에 지역명·대표가·z·관측월수가 나온다
- `-1σ` 빨간 점선이 보인다
- 읽는 법 expander가 펼쳐진다
- 좁은 창으로 줄여도 차트 제목과 범례가 겹치지 않는다

Ctrl+C.

- [ ] **Step 5: 전체 테스트와 기존 탭을 최종 확인**

Run: `python -m pytest tests/ -q`
Expected: 84 passed

- [ ] **Step 6: 커밋**

```bash
git add Desktop/Claude_project/Quant_realestate/app.py
git commit -m "feat(realestate): add pair chart, tier scatter, and reading guide"
```

---

### Task 9: 스펙 구현 현황 기록

**Files:**
- Modify: `docs/region_tier_spec_v1.md` (파일 끝에 §11 추가)

기존 스펙들(`market_context_spec_v1.md` §8)이 구현 후 실측 현황을 덧붙이는 관례를 따른다.

- [ ] **Step 1: 실제 실행 결과를 기록**

`docs/region_tier_spec_v1.md` 끝에 추가한다. 대괄호 부분은 Task 6~8에서 실제로 관측한 값으로 채운다.

```markdown
## 11. 구현 현황 (2026-08-29)

`docs/superpowers/plans/2026-08-29-region-tier-comparison.md` 9-Task 실행 완료.

- 신규: `scoring/region_rv.py`, `tests/test_region_rv.py`(22개 테스트). 전체 84개 통과.
- `app.py`에 `🗺️ 급지 비교` 탭 추가(자산 비교 탭 뒤). 기존 탭 무손상 확인.
- 실측: 시군구 지수 [실제]초 / 68개 지역 전부 랭킹 가능, 동 지수 [실제]초 / [실제] of 928 랭킹 가능.
- 사용자 예시 검수: 분당구/양천구 현재 [실제]배 vs 평균 [실제]배 (z [실제]),
  과천시/분당구 현재 [실제]배 vs 평균 [실제]배 (z [실제]).
- T1 구성: [실제 목록]
- 미해결/후속: 지역 레벨 백테스트 검증(§7), `market_context.own_apt_index()` docstring의
  "2021-08~" 표기 정정(§2.1).
```

- [ ] **Step 2: 커밋**

```bash
git add Desktop/Claude_project/Quant_realestate/docs/region_tier_spec_v1.md
git commit -m "docs(realestate): record region tier implementation status"
```

---

## 완료 기준

1. `python -m pytest tests/ -q` → 84 passed (기존 62 + 신규 22)
2. `python -m scoring.region_rv sgg` → 68개 지역 전부 랭킹 가능, T1에 강남·서초·송파·용산·성동·분당·과천 포함
3. `python -m scoring.region_rv dong` → 611 / 928 근처
4. `streamlit run app.py` → 9개 탭, `🗺️ 급지 비교`에서 구/동 토글·랭킹표·페어차트·산포도·읽는 법이 모두 동작하고 기존 탭이 안 깨짐
5. `scoring/engine.py`가 수정되지 않았음 (`git diff --stat`으로 확인)
