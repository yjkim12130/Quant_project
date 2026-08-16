# ManageStock 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 보유 주식/ETF를 카테고리별로 분류해 비중·수익률을 시각화하는 개인용 Streamlit 대시보드(ManageStock)를 만든다.

**Architecture:** 계산 로직(`portfolio.py`)과 데이터 접근(`data_io.py`, `market_data.py`)을 UI(`app.py`)에서 분리한다. 보유 종목은 `data/holdings.csv`에 영속 저장하고, 시세·환율은 yfinance로 새로고침 시 조회해 캐싱한다. 일별 자산 스냅샷을 `data/history.csv`에 누적해 추이 차트를 만든다.

**Tech Stack:** Python, Streamlit, pandas, yfinance, plotly, pytest

**Spec:** `docs/superpowers/specs/2026-08-16-managestock-design.md`

## Global Constraints

- 로컬 Streamlit 앱, 포트 8503 고정(8501=Quant_dashboard, 8502=Quant_realestate와 충돌 방지)
- 데이터 영속화는 CSV 파일(`data/holdings.csv`, `data/history.csv`)만 사용, DB 미사용
- 시세/환율은 yfinance, `st.cache_data(ttl=600)`로 캐싱. 실시간 아님(새로고침 시 조회)
- 베타값(레버리지 배수)은 **표시 전용** — 어떤 계산 로직에도 관여하지 않는다
- USD 보유분은 매입금액·평가금액 환산 모두에 **오늘 환율을 동일 적용** (환차익/주가수익 분리 기능 없음)
- 카테고리는 기본 6개(미국 지수 ETF/미국 개별주/미국 산업 ETF/한국 지수 ETF/한국 개별주/한국 산업 ETF) + 사용자 자유 추가
- `data/*.csv`(개인 자산 정보)는 git에 커밋하지 않는다

---

## Task 1: 프로젝트 스캐폴딩 + `categories.py`

**Files:**
- Create: `ManageStock/requirements.txt`
- Create: `ManageStock/.gitignore`
- Create: `ManageStock/.streamlit/config.toml`
- Create: `ManageStock/run_app.bat`
- Create: `ManageStock/conftest.py`
- Create: `ManageStock/data/.gitkeep`
- Create: `ManageStock/categories.py`
- Test: `ManageStock/tests/test_categories.py`

**Interfaces:**
- Produces: `DEFAULT_CATEGORIES: list[str]`, `TICKER_PRESETS: dict[str,str]`, `CATEGORY_COLORS: dict[str,str]`, `EXTRA_CATEGORY_PALETTE: list[str]`, `FALLBACK_CATEGORY_COLOR: str`, `POSITIVE_COLOR: str`, `NEGATIVE_COLOR: str`, `NEUTRAL_COLOR: str`, `TREND_COLOR: str`, `get_category_color_map(categories_present: list[str]) -> dict[str,str]`

- [ ] **Step 1: 스캐폴딩 파일 작성**

`ManageStock/requirements.txt`:
```
streamlit>=1.32
pandas>=2.0
yfinance>=0.2.40
plotly>=5.20
pytest>=7.4
```

`ManageStock/.gitignore`:
```
data/*.csv
!data/.gitkeep
__pycache__/
*.pyc
.pytest_cache/
.streamlit/secrets.toml
```

`ManageStock/.streamlit/config.toml`:
```toml
[server]
port = 8503
```

`ManageStock/run_app.bat`:
```bat
@echo off
cd /d %~dp0
streamlit run app.py
```

`ManageStock/conftest.py` (빈 파일 — pytest가 이 디렉터리를 rootdir로 인식해 `data_io`, `portfolio` 등을 테스트에서 바로 import할 수 있게 함):
```python
```

`ManageStock/data/.gitkeep` (빈 파일 — 빈 `data/` 디렉터리를 git이 추적하도록):
```
```

- [ ] **Step 2: 실패하는 테스트 작성**

```python
# ManageStock/tests/test_categories.py
import categories


def test_default_categories_all_have_colors():
    for cat in categories.DEFAULT_CATEGORIES:
        assert cat in categories.CATEGORY_COLORS


def test_default_category_colors_are_unique():
    colors = [categories.CATEGORY_COLORS[c] for c in categories.DEFAULT_CATEGORIES]
    assert len(colors) == len(set(colors))


def test_ticker_presets_contains_example_entries():
    assert categories.TICKER_PRESETS["QQQ"] == "QQQ"
    assert categories.TICKER_PRESETS["삼성전자"] == "005930.KS"


def test_get_category_color_map_uses_known_colors_for_defaults():
    color_map = categories.get_category_color_map(["한국 개별주", "미국 지수 ETF"])
    assert color_map["한국 개별주"] == categories.CATEGORY_COLORS["한국 개별주"]
    assert color_map["미국 지수 ETF"] == categories.CATEGORY_COLORS["미국 지수 ETF"]


def test_get_category_color_map_assigns_extra_palette_to_custom_categories():
    color_map = categories.get_category_color_map(["가상자산", "원자재"])
    assert color_map["가상자산"] == categories.EXTRA_CATEGORY_PALETTE[0]
    assert color_map["원자재"] == categories.EXTRA_CATEGORY_PALETTE[1]


def test_get_category_color_map_falls_back_beyond_extra_palette():
    custom = ["카테고리A", "카테고리B", "카테고리C"]
    color_map = categories.get_category_color_map(custom)
    assert color_map["카테고리C"] == categories.FALLBACK_CATEGORY_COLOR


def test_get_category_color_map_is_deterministic_regardless_of_input_order():
    map1 = categories.get_category_color_map(["가상자산", "원자재"])
    map2 = categories.get_category_color_map(["원자재", "가상자산"])
    assert map1 == map2
```

- [ ] **Step 3: 테스트 실행해서 실패 확인**

Run (ManageStock 디렉터리에서): `python -m pytest tests/test_categories.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'categories'`

- [ ] **Step 4: `categories.py` 구현**

```python
# ManageStock/categories.py
DEFAULT_CATEGORIES = [
    "미국 지수 ETF",
    "미국 개별주",
    "미국 산업 ETF",
    "한국 지수 ETF",
    "한국 개별주",
    "한국 산업 ETF",
]

TICKER_PRESETS = {
    "QQQ": "QQQ",
    "QLD": "QLD",
    "엔비디아": "NVDA",
    "테슬라": "TSLA",
    "구글": "GOOGL",
    "KODEX 200": "069500.KS",
    "KODEX 레버리지": "122630.KS",
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "현대차": "005380.KS",
    "네이버": "035420.KS",
}

# dataviz 스킬 검증 완료 팔레트(8슬롯 순서 고정, CVD 안전) 중 1~6번 슬롯을 기본 카테고리에 고정 배정.
CATEGORY_COLORS = {
    "미국 지수 ETF": "#2a78d6",
    "미국 개별주": "#eb6834",
    "미국 산업 ETF": "#1baf7a",
    "한국 지수 ETF": "#eda100",
    "한국 개별주": "#e87ba4",
    "한국 산업 ETF": "#008300",
}
EXTRA_CATEGORY_PALETTE = ["#4a3aa7", "#e34948"]  # 7~8번 슬롯, 사용자 추가 카테고리용
FALLBACK_CATEGORY_COLOR = "#898781"  # 9번째 이후 카테고리는 팔레트 규칙상 "Other" 취급

# 수익률 바차트용 (국내 관례: 상승=빨강, 하락=파랑)
POSITIVE_COLOR = "#e34948"
NEGATIVE_COLOR = "#2a78d6"
NEUTRAL_COLOR = "#898781"

# 자산 추이 라인차트용 (단일 시리즈, sequential 기본 hue)
TREND_COLOR = "#2a78d6"


def get_category_color_map(categories_present):
    """categories_present: list[str] (중복 가능) -> dict[str, str] 카테고리별 색상.
    기본 6개 카테고리는 항상 고정 색상, 그 외는 알파벳/가나다 순으로 EXTRA_CATEGORY_PALETTE를
    소진한 뒤 FALLBACK_CATEGORY_COLOR로 폴백한다(호출 순서가 바뀌어도 색이 안정적으로 유지됨)."""
    colors = dict(CATEGORY_COLORS)
    custom = sorted({c for c in categories_present if c not in colors})
    for i, cat in enumerate(custom):
        if i < len(EXTRA_CATEGORY_PALETTE):
            colors[cat] = EXTRA_CATEGORY_PALETTE[i]
        else:
            colors[cat] = FALLBACK_CATEGORY_COLOR
    return colors
```

- [ ] **Step 5: 테스트 실행해서 통과 확인**

Run: `python -m pytest tests/test_categories.py -v`
Expected: PASS (7개 테스트 전부)

- [ ] **Step 6: 커밋**

```bash
git add ManageStock/requirements.txt ManageStock/.gitignore ManageStock/.streamlit/config.toml ManageStock/run_app.bat ManageStock/conftest.py ManageStock/data/.gitkeep ManageStock/categories.py ManageStock/tests/test_categories.py
git commit -m "chore: ManageStock 프로젝트 스캐폴딩 + 카테고리/티커프리셋/색상 정의"
```

---

## Task 2: `data_io.py` — holdings.csv 읽기/쓰기

**Files:**
- Create: `ManageStock/data_io.py`
- Test: `ManageStock/tests/test_data_io.py`

**Interfaces:**
- Consumes: (없음, 독립 모듈)
- Produces: `HOLDINGS_COLUMNS: list[str]`, `HOLDINGS_PATH: str`, `load_holdings(path=HOLDINGS_PATH) -> pd.DataFrame`, `save_holdings(df, path=HOLDINGS_PATH) -> None`, `infer_currency(ticker: str) -> str`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# ManageStock/tests/test_data_io.py
import pandas as pd
import data_io


def test_load_holdings_returns_empty_template_when_file_missing(tmp_path):
    path = str(tmp_path / "holdings.csv")
    df = data_io.load_holdings(path=path)
    assert list(df.columns) == data_io.HOLDINGS_COLUMNS
    assert len(df) == 0


def test_save_and_load_holdings_roundtrip(tmp_path):
    path = str(tmp_path / "holdings.csv")
    df = pd.DataFrame([
        {"ticker": "005930.KS", "name": "삼성전자", "category": "한국 개별주",
         "currency": "KRW", "quantity": 10, "avg_price": 70000.0, "beta": 1.0},
    ], columns=data_io.HOLDINGS_COLUMNS)
    data_io.save_holdings(df, path=path)
    loaded = data_io.load_holdings(path=path)
    assert loaded.iloc[0]["ticker"] == "005930.KS"
    assert loaded.iloc[0]["quantity"] == 10


def test_save_holdings_creates_parent_directory(tmp_path):
    path = str(tmp_path / "nested" / "holdings.csv")
    df = pd.DataFrame(columns=data_io.HOLDINGS_COLUMNS)
    data_io.save_holdings(df, path=path)
    assert (tmp_path / "nested" / "holdings.csv").exists()


def test_infer_currency_detects_korean_suffix():
    assert data_io.infer_currency("005930.KS") == "KRW"
    assert data_io.infer_currency("069500.KQ") == "KRW"


def test_infer_currency_defaults_to_usd():
    assert data_io.infer_currency("QQQ") == "USD"
    assert data_io.infer_currency("NVDA") == "USD"
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `python -m pytest tests/test_data_io.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'data_io'`

- [ ] **Step 3: `data_io.py` 구현 (holdings 부분)**

```python
# ManageStock/data_io.py
import os
import pandas as pd

HOLDINGS_COLUMNS = ["ticker", "name", "category", "currency", "quantity", "avg_price", "beta"]
HOLDINGS_PATH = os.path.join("data", "holdings.csv")


def load_holdings(path=HOLDINGS_PATH):
    if not os.path.exists(path):
        return pd.DataFrame(columns=HOLDINGS_COLUMNS)
    return pd.read_csv(
        path,
        dtype={"ticker": str, "name": str, "category": str, "currency": str},
    )


def save_holdings(df, path=HOLDINGS_PATH):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    df.to_csv(path, index=False, columns=HOLDINGS_COLUMNS)


def infer_currency(ticker):
    if ticker.upper().endswith((".KS", ".KQ")):
        return "KRW"
    return "USD"
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `python -m pytest tests/test_data_io.py -v`
Expected: PASS (5개 테스트 전부)

- [ ] **Step 5: 커밋**

```bash
git add ManageStock/data_io.py ManageStock/tests/test_data_io.py
git commit -m "feat: holdings.csv 읽기/쓰기 + 통화 자동판별"
```

---

## Task 3: `data_io.py` — history.csv 스냅샷

**Files:**
- Modify: `ManageStock/data_io.py`
- Modify: `ManageStock/tests/test_data_io.py`

**Interfaces:**
- Consumes: (없음)
- Produces: `HISTORY_COLUMNS: list[str]`, `HISTORY_PATH: str`, `load_history(path=HISTORY_PATH) -> pd.DataFrame`, `append_snapshot(date: str, category_values: dict[str,float], path=HISTORY_PATH) -> None`

- [ ] **Step 1: 실패하는 테스트 추가**

```python
# ManageStock/tests/test_data_io.py 에 추가

def test_load_history_returns_empty_template_when_missing(tmp_path):
    path = str(tmp_path / "history.csv")
    df = data_io.load_history(path=path)
    assert list(df.columns) == data_io.HISTORY_COLUMNS
    assert len(df) == 0


def test_append_snapshot_creates_rows(tmp_path):
    path = str(tmp_path / "history.csv")
    data_io.append_snapshot("2026-08-16", {"한국 개별주": 700000.0, "TOTAL": 700000.0}, path=path)
    df = data_io.load_history(path=path)
    assert len(df) == 2
    assert set(df["category"]) == {"한국 개별주", "TOTAL"}


def test_append_snapshot_overwrites_same_date(tmp_path):
    path = str(tmp_path / "history.csv")
    data_io.append_snapshot("2026-08-16", {"TOTAL": 100.0}, path=path)
    data_io.append_snapshot("2026-08-16", {"TOTAL": 200.0}, path=path)
    df = data_io.load_history(path=path)
    assert len(df) == 1
    assert df.iloc[0]["value_krw"] == 200.0


def test_append_snapshot_keeps_previous_dates(tmp_path):
    path = str(tmp_path / "history.csv")
    data_io.append_snapshot("2026-08-15", {"TOTAL": 100.0}, path=path)
    data_io.append_snapshot("2026-08-16", {"TOTAL": 110.0}, path=path)
    df = data_io.load_history(path=path)
    assert len(df) == 2
    assert set(df["date"]) == {"2026-08-15", "2026-08-16"}
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `python -m pytest tests/test_data_io.py -v -k history`
Expected: FAIL — `AttributeError: module 'data_io' has no attribute 'load_history'`

- [ ] **Step 3: `data_io.py`에 history 함수 추가**

```python
# ManageStock/data_io.py 끝에 추가

HISTORY_COLUMNS = ["date", "category", "value_krw"]
HISTORY_PATH = os.path.join("data", "history.csv")


def load_history(path=HISTORY_PATH):
    if not os.path.exists(path):
        return pd.DataFrame(columns=HISTORY_COLUMNS)
    return pd.read_csv(path, dtype={"date": str, "category": str})


def append_snapshot(date, category_values, path=HISTORY_PATH):
    """category_values: dict[str, float] — 카테고리명(또는 'TOTAL') -> 원화환산 평가금액.
    같은 date로 재호출하면 해당 날짜 행을 덮어쓴다(하루 여러 번 실행해도 중복 누적 안 됨)."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    new_rows = pd.DataFrame(
        [{"date": date, "category": cat, "value_krw": val} for cat, val in category_values.items()],
        columns=HISTORY_COLUMNS,
    )
    existing = load_history(path)
    existing = existing[existing["date"] != date]
    combined = pd.concat([existing, new_rows], ignore_index=True)
    combined.to_csv(path, index=False, columns=HISTORY_COLUMNS)
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `python -m pytest tests/test_data_io.py -v`
Expected: PASS (9개 테스트 전부)

- [ ] **Step 5: 커밋**

```bash
git add ManageStock/data_io.py ManageStock/tests/test_data_io.py
git commit -m "feat: history.csv 일별 자산 스냅샷 누적 기능"
```

---

## Task 4: `portfolio.py` — 종목별 지표 계산

**Files:**
- Create: `ManageStock/portfolio.py`
- Test: `ManageStock/tests/test_portfolio.py`

**Interfaces:**
- Consumes: `data_io.HOLDINGS_COLUMNS`(형태 참고용, import는 불필요)
- Produces: `compute_holding_metrics(holdings_df: pd.DataFrame, prices: dict[str,float], fx_rate: float) -> pd.DataFrame` (원본 컬럼 + `current_price, value_krw, cost_krw, pnl_krw, return_pct`)

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# ManageStock/tests/test_portfolio.py
import pandas as pd
import pytest
import portfolio


def _sample_holdings():
    return pd.DataFrame([
        {"ticker": "005930.KS", "name": "삼성전자", "category": "한국 개별주",
         "currency": "KRW", "quantity": 10, "avg_price": 70000.0, "beta": 1.0},
        {"ticker": "QQQ", "name": "QQQ", "category": "미국 지수 ETF",
         "currency": "USD", "quantity": 5, "avg_price": 400.0, "beta": 1.0},
    ])


def test_compute_holding_metrics_krw_holding():
    df = portfolio.compute_holding_metrics(_sample_holdings(), {"005930.KS": 77000.0, "QQQ": 440.0}, fx_rate=1300.0)
    row = df[df["ticker"] == "005930.KS"].iloc[0]
    assert row["value_krw"] == pytest.approx(770000.0)
    assert row["cost_krw"] == pytest.approx(700000.0)
    assert row["pnl_krw"] == pytest.approx(70000.0)
    assert row["return_pct"] == pytest.approx(10.0)


def test_compute_holding_metrics_usd_holding_applies_fx_both_sides():
    df = portfolio.compute_holding_metrics(_sample_holdings(), {"005930.KS": 77000.0, "QQQ": 440.0}, fx_rate=1300.0)
    row = df[df["ticker"] == "QQQ"].iloc[0]
    assert row["value_krw"] == pytest.approx(5 * 440.0 * 1300.0)
    assert row["cost_krw"] == pytest.approx(5 * 400.0 * 1300.0)
    assert row["return_pct"] == pytest.approx(10.0)  # 환율 상쇄, 달러 기준 가격변동률과 동일


def test_compute_holding_metrics_missing_price_yields_nan():
    df = portfolio.compute_holding_metrics(_sample_holdings(), {"005930.KS": 77000.0}, fx_rate=1300.0)
    row = df[df["ticker"] == "QQQ"].iloc[0]
    assert pd.isna(row["current_price"])
    assert pd.isna(row["value_krw"])
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `python -m pytest tests/test_portfolio.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'portfolio'`

- [ ] **Step 3: `portfolio.py` 구현**

```python
# ManageStock/portfolio.py
def compute_holding_metrics(holdings_df, prices, fx_rate):
    """holdings_df: data_io.HOLDINGS_COLUMNS 형태의 DataFrame
    prices: dict[str, float] — ticker -> 현재가(해당 종목 통화 기준)
    fx_rate: float — 오늘의 KRW/USD 환율
    returns: 원본 컬럼 + current_price, value_krw, cost_krw, pnl_krw, return_pct
    가격 조회 실패(ticker가 prices에 없음)한 종목은 current_price 이하 전부 NaN이 된다.
    """
    df = holdings_df.copy()
    df["current_price"] = df["ticker"].map(prices)
    multiplier = df["currency"].map({"USD": fx_rate, "KRW": 1.0}).fillna(1.0)
    df["value_krw"] = df["quantity"] * df["current_price"] * multiplier
    df["cost_krw"] = df["quantity"] * df["avg_price"] * multiplier
    df["pnl_krw"] = df["value_krw"] - df["cost_krw"]
    df["return_pct"] = (df["current_price"] / df["avg_price"] - 1) * 100
    return df
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `python -m pytest tests/test_portfolio.py -v`
Expected: PASS (3개 테스트 전부)

- [ ] **Step 5: 커밋**

```bash
git add ManageStock/portfolio.py ManageStock/tests/test_portfolio.py
git commit -m "feat: 종목별 평가금액/매입금액/수익률 계산 로직"
```

---

## Task 5: `portfolio.py` — 카테고리 집계 + 전체 합계

**Files:**
- Modify: `ManageStock/portfolio.py`
- Modify: `ManageStock/tests/test_portfolio.py`

**Interfaces:**
- Consumes: `compute_holding_metrics()`의 출력 DataFrame (Task 4)
- Produces: `aggregate_by_category(metrics_df: pd.DataFrame) -> pd.DataFrame` (`category, value_krw, cost_krw, weight_pct, return_pct`, `value_krw` 내림차순 정렬), `compute_totals(metrics_df: pd.DataFrame) -> dict` (`total_value_krw, total_cost_krw, total_pnl_krw, total_return_pct`)

- [ ] **Step 1: 실패하는 테스트 추가**

```python
# ManageStock/tests/test_portfolio.py 에 추가

def _sample_metrics():
    holdings = _sample_holdings()
    return portfolio.compute_holding_metrics(holdings, {"005930.KS": 77000.0, "QQQ": 440.0}, fx_rate=1300.0)


def test_aggregate_by_category_weight_and_return():
    df = portfolio.aggregate_by_category(_sample_metrics())
    total_value = 770000.0 + 5 * 440.0 * 1300.0
    krw_row = df[df["category"] == "한국 개별주"].iloc[0]
    assert krw_row["weight_pct"] == pytest.approx(770000.0 / total_value * 100)
    assert krw_row["return_pct"] == pytest.approx(10.0)


def test_aggregate_by_category_sorted_by_value_desc():
    df = portfolio.aggregate_by_category(_sample_metrics())
    assert list(df["value_krw"]) == sorted(df["value_krw"], reverse=True)


def test_aggregate_by_category_empty_input_does_not_crash():
    empty = _sample_metrics().iloc[0:0]
    df = portfolio.aggregate_by_category(empty)
    assert len(df) == 0


def test_compute_totals():
    totals = portfolio.compute_totals(_sample_metrics())
    expected_value = 770000.0 + 5 * 440.0 * 1300.0
    expected_cost = 700000.0 + 5 * 400.0 * 1300.0
    assert totals["total_value_krw"] == pytest.approx(expected_value)
    assert totals["total_cost_krw"] == pytest.approx(expected_cost)
    assert totals["total_pnl_krw"] == pytest.approx(expected_value - expected_cost)
    assert totals["total_return_pct"] == pytest.approx(10.0)


def test_compute_totals_empty_input_returns_zeros():
    empty = _sample_metrics().iloc[0:0]
    totals = portfolio.compute_totals(empty)
    assert totals["total_value_krw"] == 0.0
    assert totals["total_return_pct"] == 0.0
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `python -m pytest tests/test_portfolio.py -v -k "aggregate or totals"`
Expected: FAIL — `AttributeError: module 'portfolio' has no attribute 'aggregate_by_category'`

- [ ] **Step 3: `portfolio.py`에 집계 함수 추가**

```python
# ManageStock/portfolio.py 끝에 추가
import numpy as np


def aggregate_by_category(metrics_df):
    grouped = metrics_df.groupby("category", as_index=False)[["value_krw", "cost_krw"]].sum()
    total_value = grouped["value_krw"].sum()
    grouped["weight_pct"] = (grouped["value_krw"] / total_value * 100) if total_value else 0.0
    grouped["return_pct"] = np.where(
        grouped["cost_krw"] != 0,
        (grouped["value_krw"] / grouped["cost_krw"] - 1) * 100,
        0.0,
    )
    return grouped.sort_values("value_krw", ascending=False).reset_index(drop=True)


def compute_totals(metrics_df):
    total_value = metrics_df["value_krw"].sum()
    total_cost = metrics_df["cost_krw"].sum()
    total_pnl = total_value - total_cost
    total_return = ((total_value / total_cost - 1) * 100) if total_cost else 0.0
    return {
        "total_value_krw": total_value,
        "total_cost_krw": total_cost,
        "total_pnl_krw": total_pnl,
        "total_return_pct": total_return,
    }
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `python -m pytest tests/test_portfolio.py -v`
Expected: PASS (8개 테스트 전부)

- [ ] **Step 5: 커밋**

```bash
git add ManageStock/portfolio.py ManageStock/tests/test_portfolio.py
git commit -m "feat: 카테고리별 비중/수익률 집계 + 전체 합계 계산"
```

---

## Task 6: `market_data.py` — 시세/환율 조회

**Files:**
- Create: `ManageStock/market_data.py`
- Test: `ManageStock/tests/test_market_data.py`

**Interfaces:**
- Consumes: (없음, `yfinance` 외부 라이브러리만 사용)
- Produces: `fetch_prices_uncached(tickers: list[str]) -> tuple[dict[str,float], list[str]]`, `fetch_prices(tickers: list[str]) -> tuple[dict[str,float], list[str]]` (`st.cache_data` 래핑), `fetch_fx_rate() -> float | None` (`st.cache_data` 래핑), `resolve_fx_rate(fetched_rate: float | None, last_known_rate: float | None) -> tuple[float | None, bool]`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
# ManageStock/tests/test_market_data.py
import market_data


class _FakeFastInfo(dict):
    pass


class FakeTicker:
    def __init__(self, ticker, price_map, fail_set):
        self._ticker = ticker
        self._price_map = price_map
        self._fail_set = fail_set

    @property
    def fast_info(self):
        if self._ticker in self._fail_set:
            raise RuntimeError("network error")
        return _FakeFastInfo(last_price=self._price_map[self._ticker])


def test_fetch_prices_uncached_success(monkeypatch):
    price_map = {"QQQ": 440.0, "005930.KS": 77000.0}
    monkeypatch.setattr(market_data.yf, "Ticker", lambda t: FakeTicker(t, price_map, set()))
    prices, failed = market_data.fetch_prices_uncached(["QQQ", "005930.KS"])
    assert prices == {"QQQ": 440.0, "005930.KS": 77000.0}
    assert failed == []


def test_fetch_prices_uncached_partial_failure(monkeypatch):
    price_map = {"QQQ": 440.0}
    monkeypatch.setattr(market_data.yf, "Ticker", lambda t: FakeTicker(t, price_map, {"BADTICKER"}))
    prices, failed = market_data.fetch_prices_uncached(["QQQ", "BADTICKER"])
    assert prices == {"QQQ": 440.0}
    assert failed == ["BADTICKER"]


def test_resolve_fx_rate_uses_fetched_value():
    rate, is_stale = market_data.resolve_fx_rate(1320.0, 1300.0)
    assert rate == 1320.0
    assert is_stale is False


def test_resolve_fx_rate_falls_back_when_fetch_fails():
    rate, is_stale = market_data.resolve_fx_rate(None, 1300.0)
    assert rate == 1300.0
    assert is_stale is True


def test_resolve_fx_rate_returns_none_when_never_fetched():
    rate, is_stale = market_data.resolve_fx_rate(None, None)
    assert rate is None
    assert is_stale is True
```

- [ ] **Step 2: 테스트 실행해서 실패 확인**

Run: `python -m pytest tests/test_market_data.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'market_data'`

- [ ] **Step 3: `market_data.py` 구현**

```python
# ManageStock/market_data.py
import streamlit as st
import yfinance as yf


def _fetch_single_price(ticker):
    try:
        price = yf.Ticker(ticker).fast_info["last_price"]
        return float(price) if price is not None else None
    except Exception:
        return None


def fetch_prices_uncached(tickers):
    """캐시 없는 순수 버전 — 테스트에서 직접 호출."""
    prices, failed = {}, []
    for ticker in tickers:
        price = _fetch_single_price(ticker)
        if price is None:
            failed.append(ticker)
        else:
            prices[ticker] = price
    return prices, failed


@st.cache_data(ttl=600)
def fetch_prices(tickers):
    """app.py에서 호출하는 캐시 버전. tickers는 리스트(해시 가능하도록 Streamlit이 내부 처리)."""
    return fetch_prices_uncached(tickers)


def _fetch_fx_rate_uncached():
    try:
        price = yf.Ticker("KRW=X").fast_info["last_price"]
        return float(price) if price is not None else None
    except Exception:
        return None


@st.cache_data(ttl=600)
def fetch_fx_rate():
    return _fetch_fx_rate_uncached()


def resolve_fx_rate(fetched_rate, last_known_rate):
    """fetched_rate: fetch_fx_rate()의 이번 호출 결과.
    last_known_rate: 이전에 성공적으로 조회된 마지막 환율(세션에 보관된 값).
    returns: (사용할 환율, 이번 조회가 실패해서 예전 값을 쓰는지 여부)
    """
    if fetched_rate is not None:
        return fetched_rate, False
    return last_known_rate, True
```

- [ ] **Step 4: 테스트 실행해서 통과 확인**

Run: `python -m pytest tests/test_market_data.py -v`
Expected: PASS (5개 테스트 전부)

- [ ] **Step 5: 커밋**

```bash
git add ManageStock/market_data.py ManageStock/tests/test_market_data.py
git commit -m "feat: yfinance 시세/환율 조회 + 캐시 래퍼 + 환율 폴백 로직"
```

---

## Task 7: `app.py` 골격 + Tab2 종목 관리

**Files:**
- Create: `ManageStock/app.py`

**Interfaces:**
- Consumes: `categories.DEFAULT_CATEGORIES`, `categories.TICKER_PRESETS`, `data_io.HOLDINGS_COLUMNS`, `data_io.load_holdings()`, `data_io.save_holdings()`, `data_io.infer_currency()`
- Produces: (Streamlit 앱 진입점, 다른 모듈이 import하지 않음)

- [ ] **Step 1: `app.py` 골격 + Tab2 작성**

```python
# ManageStock/app.py
import pandas as pd
import streamlit as st

import categories
import data_io

st.set_page_config(page_title="ManageStock", layout="wide")
st.title("ManageStock — 포트폴리오 대시보드")

tab1, tab2 = st.tabs(["포트폴리오 대시보드", "종목 관리"])

with tab2:
    st.subheader("종목 추가")
    preset_names = ["직접 입력"] + sorted(categories.TICKER_PRESETS.keys())
    with st.form("add_holding_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            preset_choice = st.selectbox("종목 (프리셋)", preset_names)
            if preset_choice == "직접 입력":
                name = st.text_input("종목명")
                ticker = st.text_input("티커 (예: 005930.KS, QQQ)")
            else:
                name = preset_choice
                ticker = categories.TICKER_PRESETS[preset_choice]
                st.text_input("티커", value=ticker, disabled=True)

            category_choice = st.selectbox("카테고리", categories.DEFAULT_CATEGORIES + ["직접 입력"])
            category = st.text_input("새 카테고리명") if category_choice == "직접 입력" else category_choice
        with col2:
            quantity = st.number_input("수량", min_value=0.0, step=1.0)
            avg_price = st.number_input("평단가", min_value=0.0, step=1.0)
            beta = st.number_input("베타(레버리지 배수)", min_value=0.0, value=1.0, step=0.5)
            inferred_currency = data_io.infer_currency(ticker) if ticker else "USD"
            currency = st.radio("통화", ["KRW", "USD"], index=0 if inferred_currency == "KRW" else 1, horizontal=True)

        submitted = st.form_submit_button("추가")
        if submitted:
            if not ticker or not name or not category:
                st.error("종목명, 티커, 카테고리는 필수입니다.")
            else:
                holdings = data_io.load_holdings()
                new_row = pd.DataFrame([{
                    "ticker": ticker, "name": name, "category": category,
                    "currency": currency, "quantity": quantity,
                    "avg_price": avg_price, "beta": beta,
                }], columns=data_io.HOLDINGS_COLUMNS)
                holdings = pd.concat([holdings, new_row], ignore_index=True)
                data_io.save_holdings(holdings)
                st.success(f"{name} 추가 완료")

    st.subheader("보유 종목 수정 / 삭제")
    st.caption("그리드에 없는 새 카테고리는 위 '종목 추가' 폼에서 등록해주세요.")
    holdings_df = data_io.load_holdings()
    known_categories = sorted(set(categories.DEFAULT_CATEGORIES) | set(holdings_df["category"].dropna()))
    edited_df = st.data_editor(
        holdings_df,
        num_rows="dynamic",
        column_config={
            "currency": st.column_config.SelectboxColumn("통화", options=["KRW", "USD"]),
            "category": st.column_config.SelectboxColumn("카테고리", options=known_categories),
        },
        key="holdings_editor",
        use_container_width=True,
    )
    if st.button("변경사항 저장"):
        data_io.save_holdings(edited_df)
        st.success("저장 완료")
        st.rerun()
```

- [ ] **Step 2: 앱이 정상 기동하는지 헤드리스로 확인**

Run (ManageStock 디렉터리에서, bash):
```bash
streamlit run app.py --server.headless true --server.port 8503 &
APP_PID=$!
for i in $(seq 1 10); do
  curl -sf http://localhost:8503 > /dev/null && break
  sleep 1
done
curl -sf http://localhost:8503 > /dev/null && echo "BOOT OK" || echo "BOOT FAILED"
kill $APP_PID
```
Expected: `BOOT OK` 출력 (import 에러나 최상위 예외 없이 기동)

- [ ] **Step 3: 커밋**

```bash
git add ManageStock/app.py
git commit -m "feat: Streamlit 앱 골격 + 종목 관리 탭(추가/수정/삭제)"
```

---

## Task 8: `app.py` — Tab1 포트폴리오 대시보드

**Files:**
- Modify: `ManageStock/app.py`

**Interfaces:**
- Consumes: `market_data.fetch_prices()`, `market_data.fetch_fx_rate()`, `market_data.resolve_fx_rate()`, `portfolio.compute_holding_metrics()`, `portfolio.aggregate_by_category()`, `portfolio.compute_totals()`, `categories.get_category_color_map()`, `categories.POSITIVE_COLOR`, `categories.NEGATIVE_COLOR`
- Produces: (앱 진입점, 변경 없음)

- [ ] **Step 1: import 추가 + Tab1 구현**

`app.py` 상단 import 블록을 다음으로 교체:
```python
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import categories
import data_io
import market_data
import portfolio
```

`with tab1:` 블록 작성 (`with tab2:` 블록 앞, 즉 파일에서 tab2보다 먼저 오는 위치에 삽입):
```python
with tab1:
    holdings_df = data_io.load_holdings()
    if holdings_df.empty:
        st.info("종목 관리 탭에서 보유 종목을 먼저 등록해주세요.")
    else:
        tickers = holdings_df["ticker"].tolist()
        prices, failed_tickers = market_data.fetch_prices(tickers)
        fetched_fx = market_data.fetch_fx_rate()
        last_fx = st.session_state.get("last_fx_rate")
        fx_rate, fx_is_stale = market_data.resolve_fx_rate(fetched_fx, last_fx)
        if fx_rate is not None:
            st.session_state["last_fx_rate"] = fx_rate

        if failed_tickers:
            st.warning("시세 조회 실패: " + ", ".join(failed_tickers))

        if fx_rate is None:
            st.error("환율 조회 실패 — USD 종목 금액을 계산할 수 없습니다.")
        else:
            if fx_is_stale:
                st.caption(f"⚠️ 환율 조회 실패, 마지막 확인 환율 사용: {fx_rate:,.2f} KRW/USD")
            else:
                st.metric("현재 환율 (USD/KRW)", f"{fx_rate:,.2f}")

            metrics_df = portfolio.compute_holding_metrics(holdings_df, prices, fx_rate)
            valid_df = metrics_df.dropna(subset=["value_krw"])

            totals = portfolio.compute_totals(valid_df)
            col1, col2, col3 = st.columns(3)
            col1.metric("총평가금액", f"{totals['total_value_krw']:,.0f} 원")
            col2.metric("총손익금", f"{totals['total_pnl_krw']:,.0f} 원")
            col3.metric("총수익률", f"{totals['total_return_pct']:.2f} %")

            category_df = portfolio.aggregate_by_category(valid_df)

            if category_df.empty:
                st.warning("시세를 조회할 수 있는 종목이 없어 차트를 표시할 수 없습니다.")
            else:
                color_map = categories.get_category_color_map(category_df["category"].tolist())

                pie = px.pie(
                    category_df, names="category", values="value_krw",
                    color="category", color_discrete_map=color_map,
                    title="카테고리별 비중",
                )
                pie.update_traces(textinfo="percent+label")
                st.plotly_chart(pie, use_container_width=True)

                bar_colors = [
                    categories.POSITIVE_COLOR if v >= 0 else categories.NEGATIVE_COLOR
                    for v in category_df["return_pct"]
                ]
                bar = go.Figure(go.Bar(
                    x=category_df["return_pct"], y=category_df["category"],
                    orientation="h", marker_color=bar_colors,
                ))
                bar.update_layout(title="카테고리별 수익률 (%)", xaxis_title="수익률 (%)", yaxis_title=None)
                st.plotly_chart(bar, use_container_width=True)

            display_df = metrics_df.copy()
            display_df["시세조회"] = display_df["current_price"].apply(lambda v: "실패" if pd.isna(v) else "정상")
            st.dataframe(
                display_df[[
                    "category", "name", "ticker", "currency", "quantity", "avg_price",
                    "current_price", "value_krw", "pnl_krw", "return_pct", "beta", "시세조회",
                ]],
                use_container_width=True,
            )
```

- [ ] **Step 2: 샘플 데이터로 헤드리스 기동 확인**

Run (ManageStock 디렉터리에서, bash):
```bash
mkdir -p data
cat > data/holdings.csv <<'EOF'
ticker,name,category,currency,quantity,avg_price,beta
QQQ,QQQ,미국 지수 ETF,USD,5,400.0,1.0
005930.KS,삼성전자,한국 개별주,KRW,10,70000.0,1.0
EOF

streamlit run app.py --server.headless true --server.port 8503 &
APP_PID=$!
for i in $(seq 1 10); do
  curl -sf http://localhost:8503 > /dev/null && break
  sleep 1
done
curl -sf http://localhost:8503 | grep -q "ManageStock" && echo "BOOT OK" || echo "BOOT FAILED"
kill $APP_PID
```
Expected: `BOOT OK` 출력 (실제 네트워크로 yfinance 조회가 이루어지므로 이 단계에서 시세 조회 실패가 나도 앱이 죽지 않는지까지 확인하는 것이 핵심)

- [ ] **Step 3: 커밋**

```bash
git add ManageStock/app.py
git commit -m "feat: 포트폴리오 대시보드 탭(메트릭/비중 파이차트/수익률 바차트/상세테이블)"
```

---

## Task 9: 자산 스냅샷 통합 + 추이 라인차트

**Files:**
- Modify: `ManageStock/app.py`

**Interfaces:**
- Consumes: `data_io.append_snapshot()`, `data_io.load_history()`, `categories.TREND_COLOR`
- Produces: (앱 진입점, 변경 없음)

- [ ] **Step 1: import에 `datetime` 추가, 스냅샷 저장 + 추이 차트 삽입**

`app.py` 상단 import에 추가:
```python
import datetime
```

Task 8에서 작성한 `category_df = portfolio.aggregate_by_category(valid_df)` 다음, `if category_df.empty:` 블록 이전에 삽입:
```python
            today = datetime.date.today().isoformat()
            snapshot_values = dict(zip(category_df["category"], category_df["value_krw"]))
            snapshot_values["TOTAL"] = totals["total_value_krw"]
            data_io.append_snapshot(today, snapshot_values)
```

상세 종목 테이블(`st.dataframe(...)`) 다음에 추이 차트 추가:
```python
            history_df = data_io.load_history()
            total_history = history_df[history_df["category"] == "TOTAL"].sort_values("date")
            if len(total_history) < 2:
                st.info("데이터가 쌓이면 자산 추이가 표시됩니다.")
            else:
                trend = go.Figure(go.Scatter(
                    x=total_history["date"], y=total_history["value_krw"],
                    mode="lines+markers",
                    line=dict(color=categories.TREND_COLOR, width=2),
                ))
                trend.update_layout(title="총자산 추이 (KRW)", xaxis_title=None, yaxis_title="평가금액 (원)")
                st.plotly_chart(trend, use_container_width=True)
```

- [ ] **Step 2: 스냅샷이 실제로 쌓이는지 확인**

Run (ManageStock 디렉터리에서, bash — Task 8에서 만든 `data/holdings.csv`가 있는 상태로):
```bash
rm -f data/history.csv
python -c "
import data_io
data_io.append_snapshot('2026-08-15', {'TOTAL': 1000000.0})
data_io.append_snapshot('2026-08-16', {'TOTAL': 1050000.0})
df = data_io.load_history()
assert len(df) == 2, df
print('HISTORY OK')
"
```
Expected: `HISTORY OK` 출력

- [ ] **Step 3: 커밋**

```bash
git add ManageStock/app.py
git commit -m "feat: 일별 자산 스냅샷 저장 + 총자산 추이 라인차트"
```

---

## Task 10: 최종 통합 검증

**Files:**
- (코드 변경 없음 — 수동 검증만)

**Interfaces:**
- Consumes: 전체 앱
- Produces: (없음)

- [ ] **Step 1: 클린 상태에서 `run_app.bat`으로 앱 기동**

Run (PowerShell, ManageStock 디렉터리에서):
```powershell
Remove-Item data\holdings.csv, data\history.csv -ErrorAction SilentlyContinue
Start-Process -FilePath ".\run_app.bat"
```
Expected: 브라우저가 열리며 `http://localhost:8503`에서 "ManageStock — 포트폴리오 대시보드" 타이틀과 "종목 관리 탭에서 보유 종목을 먼저 등록해주세요." 안내가 보인다.

- [ ] **Step 2: 브라우저에서 종목 추가 흐름 확인**

"종목 관리" 탭 → 프리셋에서 "삼성전자" 선택 → 카테고리 "한국 개별주" → 수량 10, 평단가 70000 입력 → "추가" 클릭.
Expected: "삼성전자 추가 완료" 메시지, 아래 데이터 에디터에 새 행이 나타남.

- [ ] **Step 3: 포트폴리오 대시보드 탭에서 반영 확인**

"포트폴리오 대시보드" 탭으로 전환.
Expected: 상단에 총평가금액/총손익금/총수익률/환율 메트릭이 표시되고, 카테고리별 비중 파이차트에 "한국 개별주" 100%가 나타나며, 상세 테이블에 삼성전자 행이 보인다.

- [ ] **Step 4: 영속성 확인**

브라우저 탭을 새로고침(F5)한 뒤, 앱 프로세스를 완전히 종료했다가 `run_app.bat`으로 재기동.
Expected: 종목 관리 탭에 삼성전자가 여전히 남아있음 (`data/holdings.csv`에서 로드됨).

- [ ] **Step 5: 데이터 에디터에서 수정/삭제 확인**

"종목 관리" 탭에서 수량을 20으로 수정 → "변경사항 저장" 클릭 → 포트폴리오 대시보드에서 평가금액이 2배로 바뀌었는지 확인. 이어서 데이터 에디터에서 행을 삭제하고 저장 → 대시보드가 "종목을 먼저 등록해주세요" 안내로 돌아가는지 확인.

- [ ] **Step 6: 전체 테스트 스위트 최종 확인**

Run: `python -m pytest tests/ -v`
Expected: 모든 테스트 PASS (categories 7개 + data_io 9개 + portfolio 8개 + market_data 5개 = 29개)

- [ ] **Step 7: 최종 커밋(필요 시)**

수동 검증 중 발견된 수정 사항이 있다면 해당 파일만 targeted add로 커밋. 문제 없었다면 이 태스크는 커밋 없이 종료.
