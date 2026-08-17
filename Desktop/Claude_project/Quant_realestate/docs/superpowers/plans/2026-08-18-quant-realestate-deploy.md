# Quant_realestate Streamlit Cloud 배포 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Quant_realestate 앱을 Streamlit Community Cloud에 배포해 모바일/외부에서 고정 URL로 접근 가능하게 한다.

**Architecture:** 원본 3GB 실거래 DB(`data/realestate.db`)는 로컬 전용으로 유지한다. 새 모듈 `scoring/snapshot.py`가 `resolve_db_path()` 하나로 "원본 DB가 있으면 라이브 계산, 없으면(클라우드) 경량 스냅샷 읽기"를 분기한다. `app.py`의 7개 DB 로더 함수가 이 분기점을 통해 DB 경로를 얻도록 바꾼다. 스냅샷은 원본과 같은 SQLite 포맷(새 의존성 없음)이며, 로컬에서 1회 생성해 커밋한다.

**Tech Stack:** Python, Streamlit, sqlite3, pandas (기존 스택 그대로 — 신규 의존성 없음)

**Spec:** `docs/deployment_spec_v1.md`

## Global Constraints

- git 저장소 루트가 `C:\Users\yjkim`(홈 디렉토리 전체) — 모든 커밋은 `git add "Desktop/Claude_project/Quant_realestate/<경로>"` 형태의 targeted add만 사용, `git add -A`/`git add .` 절대 금지.
- 배포 앱은 런타임에 외부 API를 호출하지 않는다 — Streamlit Cloud Secrets 설정 불필요, 새 시크릿 코드 추가 금지.
- 예산 입력은 세션 한정, 어디에도 저장 금지 (기존 원칙, 변경 없음).
- 스냅샷 DB는 `data/snapshot/cloud_snapshot.db`에 둔다 (`.gitignore`의 `data/*.db` 규칙은 한 단계 glob이라 `data/snapshot/` 하위는 걸리지 않음 — 확인 완료, 별도 `.gitignore` 수정 불필요).
- `.streamlit/config.toml`에 로컬 전용 포트(8502)를 다시 하드코딩하지 않는다 (Streamlit Cloud 헬스체크가 8501을 기대함 — ManageStock 배포 선례에서 확인된 버그).

---

### Task 1: 로컬 포트 설정을 Cloud 배포와 충돌하지 않게 분리

**Files:**
- Modify: `.streamlit/config.toml`
- Modify: `run_app.bat`

**Interfaces:**
- Consumes: 없음 (설정 파일만 수정)
- Produces: 없음 (다른 태스크가 의존하는 코드 인터페이스 아님)

같은 모노레포의 ManageStock 배포에서 `.streamlit/config.toml`의 `port = 8503` 하드코딩이 Streamlit Cloud의 헬스체크(항상 `localhost:8501` 기대)를 깨뜨린 것이 확인됐다(`docs/deployment_spec_v1.md` "알려진 함정" 참고). Quant_realestate도 `port = 8502`가 같은 방식으로 하드코딩돼 있어 동일하게 수정한다.

- [ ] **Step 1: `.streamlit/config.toml`에서 `port` 줄 제거**

`address = "0.0.0.0"`은 로컬 Tailscale/Cloudflare 터널 접속에 필요하므로 유지한다. 문제는 `port`뿐이다.

```toml
[server]
address = "0.0.0.0"
headless = false
enableCORS = false
enableXsrfProtection = false

[browser]
gatherUsageStats = false

[theme]
base = "dark"
primaryColor = "#00d084"
backgroundColor = "#0e1117"
secondaryBackgroundColor = "#1e2130"
textColor = "#fafafa"
font = "sans serif"

[client]
showErrorDetails = true
```

- [ ] **Step 2: `run_app.bat`의 streamlit 실행 커맨드에 `--server.port 8502` 추가**

기존 5번째 줄:
```bat
start "YJ-RealEstate 앱" cmd /k streamlit run app.py --server.headless true
```
다음으로 교체:
```bat
start "YJ-RealEstate 앱" cmd /k streamlit run app.py --server.headless true --server.port 8502
```
파일의 나머지 줄(cloudflared 터널 실행 등)은 그대로 둔다.

- [ ] **Step 3: 로컬에서 포트가 여전히 8502로 뜨는지 확인**

Run: `cd "C:\Users\yjkim\Desktop\Claude_project\Quant_realestate" && run_app.bat`
Expected: 콘솔에 `Local URL: http://localhost:8502` 출력. 확인 후 창을 닫는다(`Ctrl+C` 후 `exit`).

- [ ] **Step 4: 커밋**

```bash
cd /c/Users/yjkim
git add "Desktop/Claude_project/Quant_realestate/.streamlit/config.toml" "Desktop/Claude_project/Quant_realestate/run_app.bat"
git commit -m "fix(realestate): move local port pin out of config.toml

Streamlit Cloud health-checks localhost:8501; a hardcoded port in
config.toml breaks that (same bug hit ManageStock's deploy). Local
port now comes from the run command instead."
```

---

### Task 2: `scoring/snapshot.py` — DB 경로 분기 + 스냅샷 내보내기/읽기

**Files:**
- Create: `scoring/snapshot.py`
- Modify: `tests/conftest.py` (공유 fixture 추가)
- Create: `tests/test_snapshot.py`

**Interfaces:**
- Consumes: `scoring.engine.DB_PATH`, `scoring.engine.Params`, `scoring.engine.build_scored_panel`, `scoring.market_context.own_apt_index`, `scoring.market_context.leading_apt_index` (기존 함수, 시그니처 변경 없음)
- Produces (Task 3·4가 사용):
  - `scoring.snapshot.RAW_DB_PATH: Path`
  - `scoring.snapshot.SNAPSHOT_DB_PATH: Path` (`data/snapshot/cloud_snapshot.db`)
  - `scoring.snapshot.resolve_db_path() -> Path`
  - `scoring.snapshot.export_snapshot(params: Params = None, out_path: Path = SNAPSHOT_DB_PATH) -> Path`
  - `scoring.snapshot.load_panel_snapshot(conn) -> tuple[pd.DataFrame, pd.DataFrame]` (df, totals — `build_scored_panel()`과 동일 컬럼·dtype)
  - `tests/conftest.py`의 `fixture_raw_db(tmp_path)` pytest fixture → 최소 실거래+macro 데이터가 든 임시 DB 경로(Path) 반환

먼저 `tests/conftest.py`에 여러 테스트 파일이 재사용할 최소 픽스처 DB를 추가한다(Task 3도 이 fixture를 그대로 쓴다).

- [ ] **Step 1: `tests/conftest.py`에 `fixture_raw_db` 추가**

```python
import sys
from pathlib import Path
import sqlite3

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest.db import SCHEMA  # noqa: E402

MACRO_SCHEMA = """
CREATE TABLE IF NOT EXISTS macro_series (
    series TEXT NOT NULL, ym TEXT NOT NULL, value REAL, fetched_at TEXT,
    PRIMARY KEY (series, ym)
);
"""


@pytest.fixture
def fixture_raw_db(tmp_path):
    """최소 실거래(3개 단지 x 3개월, 강남구 동일 그룹) + macro_series 3개월치가 든 임시 DB.
    scoring/snapshot.py의 내보내기/읽기 라운드트립, app.py 스냅샷 모드 스모크테스트가 공유한다."""
    path = tmp_path / "raw.db"
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.executescript(MACRO_SCHEMA)

    sale_rows = []
    for month in ["2021-01", "2021-02", "2021-03"]:
        for ckey in range(3):
            sale_rows.append((
                "11680", "강남구", "역삼동", f"테스트단지{ckey}", f"seq{ckey}",
                70.0, f"{month}-15", 100000 + ckey * 500, 5, 2015, 0,
            ))
    conn.executemany(
        "INSERT INTO trades_sale (region_code, region_name, dong_name, complex_name, apt_seq, "
        "exclusive_area, contract_date, deal_amount, floor, build_year, cancelled) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)", sale_rows)

    macro_rows = []
    for i, month in enumerate(["202101", "202102", "202103"]):
        macro_rows.append(("ecos_base_rate", month, 1.0))
        macro_rows.append(("ecos_m2", month, 3000.0 + i * 10))
        macro_rows.append(("reb_apt_index", month, 100.0 + i))
    conn.executemany(
        "INSERT INTO macro_series (series, ym, value) VALUES (?,?,?)", macro_rows)
    conn.commit()
    conn.close()
    return path
```

- [ ] **Step 2: 실패하는 테스트 작성 — `resolve_db_path()`**

`tests/test_snapshot.py` 새 파일:

```python
import sqlite3

import pandas as pd
import pytest

from scoring.engine import Params, build_scored_panel
from scoring.snapshot import export_snapshot, load_panel_snapshot, resolve_db_path


def test_resolve_db_path_prefers_raw_when_present(tmp_path, monkeypatch):
    raw = tmp_path / "raw.db"
    raw.write_text("")
    snap = tmp_path / "snap.db"
    monkeypatch.setattr("scoring.snapshot.RAW_DB_PATH", raw)
    monkeypatch.setattr("scoring.snapshot.SNAPSHOT_DB_PATH", snap)
    assert resolve_db_path() == raw


def test_resolve_db_path_falls_back_to_snapshot_when_raw_missing(tmp_path, monkeypatch):
    raw = tmp_path / "does_not_exist.db"
    snap = tmp_path / "snap.db"
    monkeypatch.setattr("scoring.snapshot.RAW_DB_PATH", raw)
    monkeypatch.setattr("scoring.snapshot.SNAPSHOT_DB_PATH", snap)
    assert resolve_db_path() == snap
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `cd "C:\Users\yjkim\Desktop\Claude_project\Quant_realestate" && python -m pytest tests/test_snapshot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scoring.snapshot'`

- [ ] **Step 4: `scoring/snapshot.py` 최소 구현 — 경로 분기만**

```python
"""클라우드 배포용 경량 스냅샷 — 원본 3GB DB에서 계산된 결과물만 추출.

로컬(원본 DB 있음)은 항상 라이브 계산, 클라우드(원본 DB 없음)는 이 스냅샷만 읽는다.
resolve_db_path() 하나가 앱 전체의 분기점이며, app.py의 모든 DB 로더가 이걸 통해 경로를 얻는다.
"""
from pathlib import Path

from scoring.engine import DB_PATH as RAW_DB_PATH  # noqa: F401 (재수출 — app.py가 import)

SNAPSHOT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "snapshot" / "cloud_snapshot.db"


def resolve_db_path() -> Path:
    """원본 DB가 로컬에 있으면 그걸, 없으면(클라우드 환경) 스냅샷을 반환한다."""
    return RAW_DB_PATH if RAW_DB_PATH.exists() else SNAPSHOT_DB_PATH
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/test_snapshot.py -v`
Expected: 2 passed

- [ ] **Step 6: 실패하는 테스트 작성 — `export_snapshot`/`load_panel_snapshot` 라운드트립**

`tests/test_snapshot.py`에 추가:

```python
def test_export_snapshot_round_trips_panel_dtypes(fixture_raw_db, tmp_path, monkeypatch):
    out_path = tmp_path / "snapshot" / "cloud_snapshot.db"
    monkeypatch.setattr("scoring.snapshot.RAW_DB_PATH", fixture_raw_db)

    params = Params()
    live_df, live_totals = build_scored_panel(params, db_path=fixture_raw_db)

    export_snapshot(params=params, out_path=out_path)
    assert out_path.exists()

    conn = sqlite3.connect(out_path)
    try:
        snap_df, snap_totals = load_panel_snapshot(conn)
    finally:
        conn.close()

    assert isinstance(snap_df["month"].dtype, pd.PeriodDtype)
    assert snap_df["carried"].dtype == bool
    assert snap_df["buy_zone"].dtype == bool
    assert sorted(snap_df.columns) == sorted(live_df.columns)
    assert len(snap_df) == len(live_df)
    assert sorted(snap_totals.columns) == sorted(live_totals.columns)
    assert len(snap_totals) == len(live_totals)


def test_export_snapshot_copies_small_tables(fixture_raw_db, tmp_path, monkeypatch):
    conn = sqlite3.connect(fixture_raw_db)
    conn.execute(
        "INSERT INTO complex_coords (ckey, region_code, lat, lon) VALUES ('c1', '11680', 37.5, 127.0)")
    conn.commit()
    conn.close()
    out_path = tmp_path / "snapshot" / "cloud_snapshot.db"
    monkeypatch.setattr("scoring.snapshot.RAW_DB_PATH", fixture_raw_db)

    export_snapshot(out_path=out_path)

    out_conn = sqlite3.connect(out_path)
    coords = pd.read_sql_query("SELECT * FROM complex_coords", out_conn)
    out_conn.close()
    assert len(coords) == 1
    assert coords.iloc[0]["ckey"] == "c1"


def test_export_snapshot_embeds_asset_indices_in_macro_series(fixture_raw_db, tmp_path, monkeypatch):
    out_path = tmp_path / "snapshot" / "cloud_snapshot.db"
    monkeypatch.setattr("scoring.snapshot.RAW_DB_PATH", fixture_raw_db)

    export_snapshot(out_path=out_path)

    out_conn = sqlite3.connect(out_path)
    series = pd.read_sql_query(
        "SELECT DISTINCT series FROM macro_series", out_conn)["series"].tolist()
    out_conn.close()
    assert "own_apt_index" in series
    assert "leading_apt_index" in series


def test_export_snapshot_raises_when_raw_db_missing(tmp_path, monkeypatch):
    monkeypatch.setattr("scoring.snapshot.RAW_DB_PATH", tmp_path / "nope.db")
    with pytest.raises(FileNotFoundError):
        export_snapshot(out_path=tmp_path / "out.db")
```

- [ ] **Step 7: 테스트 실패 확인**

Run: `python -m pytest tests/test_snapshot.py -v`
Expected: FAIL — `ImportError: cannot import name 'export_snapshot'` (또는 `load_panel_snapshot`)

- [ ] **Step 8: `export_snapshot`/`load_panel_snapshot` 구현**

`scoring/snapshot.py`를 아래 전체 내용으로 교체(Step 4의 내용 포함):

```python
"""클라우드 배포용 경량 스냅샷 — 원본 3GB DB에서 계산된 결과물만 추출.

로컬(원본 DB 있음)은 항상 라이브 계산, 클라우드(원본 DB 없음)는 이 스냅샷만 읽는다.
resolve_db_path() 하나가 앱 전체의 분기점이며, app.py의 모든 DB 로더가 이걸 통해 경로를 얻는다.
"""
import sqlite3
from pathlib import Path

import pandas as pd

from scoring.engine import DB_PATH as RAW_DB_PATH, Params, build_scored_panel
from scoring.market_context import leading_apt_index, own_apt_index

SNAPSHOT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "snapshot" / "cloud_snapshot.db"

# 원본에 이미 존재하는 소형 독립 테이블 — 재계산 없이 그대로 복사
COPY_TABLES = [
    "macro_series", "complex_coords", "station_node",
    "station_edge", "complex_transit_time", "supply_presale",
]


def resolve_db_path() -> Path:
    """원본 DB가 로컬에 있으면 그걸, 없으면(클라우드 환경) 스냅샷을 반환한다."""
    return RAW_DB_PATH if RAW_DB_PATH.exists() else SNAPSHOT_DB_PATH


def _copy_small_tables(raw_conn, out_conn) -> None:
    for table in COPY_TABLES:
        try:
            df = pd.read_sql_query(f"SELECT * FROM {table}", raw_conn)
        except Exception:
            continue  # 원본에 아직 없는 테이블(예: 미적재)은 건너뜀
        df.to_sql(table, out_conn, index=False, if_exists="replace")


def _export_asset_indices(raw_conn, out_conn) -> None:
    """own_apt_index/leading_apt_index를 macro_series와 같은 (series, ym, value) 형식으로
    스냅샷의 macro_series에 추가 행으로 저장한다. app.py의 load_assets()는 macro_series를
    피벗만 하면 두 지수를 별도 분기 없이 함께 얻는다(원본 DB에서는 라이브 계산으로 대체)."""
    rows = []
    for series_name, s in (("own_apt_index", own_apt_index(raw_conn)),
                            ("leading_apt_index", leading_apt_index(raw_conn))):
        if s.empty:
            continue
        for period, value in s.items():
            rows.append((series_name, period.strftime("%Y%m"), float(value)))
    if rows:
        pd.DataFrame(rows, columns=["series", "ym", "value"]).to_sql(
            "macro_series", out_conn, index=False, if_exists="append")


def _export_panel(out_conn, params: Params) -> None:
    df, totals = build_scored_panel(params, db_path=RAW_DB_PATH)

    df_out = df.copy()
    df_out["month"] = df_out["month"].astype(str)
    df_out["area_band"] = df_out["area_band"].astype(str)
    for col in ("carried", "buy_zone"):
        if col in df_out.columns:
            df_out[col] = df_out[col].astype(int)
    df_out.to_sql("panel", out_conn, index=False, if_exists="replace")

    totals_out = totals.copy()
    totals_out["area_band"] = totals_out["area_band"].astype(str)
    totals_out.to_sql("panel_totals", out_conn, index=False, if_exists="replace")


def export_snapshot(params: Params = None, out_path: Path = SNAPSHOT_DB_PATH) -> Path:
    """원본 DB(RAW_DB_PATH)를 읽어 out_path에 경량 스냅샷을 만든다. 로컬(원본 DB 있는 환경)에서만
    실행 가능 — 데이터 갱신 시마다 재실행 후 out_path를 커밋한다."""
    if not RAW_DB_PATH.exists():
        raise FileNotFoundError(f"원본 DB가 없습니다: {RAW_DB_PATH} (배치 적재 먼저 실행)")
    params = params or Params()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        out_path.unlink()

    raw_conn = sqlite3.connect(RAW_DB_PATH)
    out_conn = sqlite3.connect(out_path)
    try:
        _copy_small_tables(raw_conn, out_conn)
        _export_asset_indices(raw_conn, out_conn)
        _export_panel(out_conn, params)
        out_conn.commit()
    finally:
        raw_conn.close()
        out_conn.close()
    return out_path


def load_panel_snapshot(conn):
    """스냅샷 DB에서 panel/panel_totals를 build_scored_panel()과 동일한 dtype으로 복원해 반환한다."""
    df = pd.read_sql_query("SELECT * FROM panel", conn)
    df["month"] = pd.PeriodIndex(df["month"], freq="M")
    for col in ("carried", "buy_zone"):
        if col in df.columns:
            df[col] = df[col].astype(bool)
    totals = pd.read_sql_query("SELECT * FROM panel_totals", conn)
    return df, totals
```

- [ ] **Step 9: 테스트 통과 확인**

Run: `python -m pytest tests/test_snapshot.py -v`
Expected: 6 passed

- [ ] **Step 10: 전체 스위트 회귀 확인**

Run: `python -m pytest tests/ -q`
Expected: 기존 62개 + 신규 6개 = 68 passed

- [ ] **Step 11: 커밋**

```bash
cd /c/Users/yjkim
git add "Desktop/Claude_project/Quant_realestate/scoring/snapshot.py" \
        "Desktop/Claude_project/Quant_realestate/tests/conftest.py" \
        "Desktop/Claude_project/Quant_realestate/tests/test_snapshot.py"
git commit -m "feat(realestate): add scoring/snapshot.py for cloud deploy

resolve_db_path() branches between the live 3GB raw DB and a
precomputed lightweight snapshot. export_snapshot() builds the
snapshot; load_panel_snapshot() restores build_scored_panel()'s
exact dtypes (Period month, bool carried/buy_zone) on read."
```

---

### Task 3: `app.py` 로더를 `resolve_db_path()`로 연결

**Files:**
- Modify: `app.py`
- Create: `tests/test_app_snapshot_mode.py`

**Interfaces:**
- Consumes: Task 2의 `scoring.snapshot.RAW_DB_PATH`/`SNAPSHOT_DB_PATH`/`resolve_db_path()`/`export_snapshot()`/`load_panel_snapshot()`, `tests/conftest.py`의 `fixture_raw_db` fixture
- Produces: 없음 (app.py의 기존 로더 함수 시그니처·반환 타입은 그대로 — 내부 구현만 교체)

app.py에서 DB에 접근하는 로더 7개(`load_panel`, `load_regime`, `load_raw`, `load_assets`, `load_transit_times`, `load_complex_coords`, `load_supply`)를 전부 `scoring.engine.DB_PATH` 하드코딩 대신 `resolve_db_path()`로 바꾼다. `load_panel`과 `load_assets`만 원본/스냅샷 분기 로직이 다르고(스냅샷 전용 함수 호출), 나머지 5개는 그냥 connection 대상 경로만 바뀐다.

- [ ] **Step 1: `load_panel()` 수정**

`app.py`의 기존:
```python
@st.cache_data(ttl=3600, show_spinner="시세 패널·팩터 계산 중 (최초 1회, 1~2분)...")
def load_panel():
    params = Params()
    df, totals = build_scored_panel(params)
    return df, totals, params
```
다음으로 교체:
```python
@st.cache_data(ttl=3600, show_spinner="시세 패널·팩터 계산 중 (최초 1회, 1~2분)...")
def load_panel():
    from scoring.snapshot import RAW_DB_PATH, load_panel_snapshot, resolve_db_path
    params = Params()
    db_path = resolve_db_path()
    if db_path == RAW_DB_PATH:
        df, totals = build_scored_panel(params)
    else:
        import sqlite3
        conn = sqlite3.connect(db_path)
        try:
            df, totals = load_panel_snapshot(conn)
        finally:
            conn.close()
    return df, totals, params
```

- [ ] **Step 2: `load_regime()`/`load_raw()` 수정**

기존:
```python
@st.cache_data(ttl=3600, show_spinner="레짐 산출 중...")
def load_regime():
    r = compute_regime()
    return r.dropna(subset=["score"])
```
```python
@st.cache_data(ttl=3600, show_spinner="변수 원시값 로딩...")
def load_raw():
    return load_raw_series()
```
다음으로 교체:
```python
@st.cache_data(ttl=3600, show_spinner="레짐 산출 중...")
def load_regime():
    import sqlite3
    from scoring.snapshot import resolve_db_path
    conn = sqlite3.connect(resolve_db_path())
    try:
        r = compute_regime(conn=conn)
    finally:
        conn.close()
    return r.dropna(subset=["score"])
```
```python
@st.cache_data(ttl=3600, show_spinner="변수 원시값 로딩...")
def load_raw():
    import sqlite3
    from scoring.snapshot import resolve_db_path
    conn = sqlite3.connect(resolve_db_path())
    try:
        return load_raw_series(conn=conn)
    finally:
        conn.close()
```

- [ ] **Step 3: `load_assets()` 수정**

기존:
```python
@st.cache_data(ttl=3600, show_spinner="자산 시계열 로딩...")
def load_assets():
    import sqlite3
    from scoring.engine import DB_PATH
    from scoring.market_context import leading_apt_index, own_apt_index
    conn = sqlite3.connect(DB_PATH)
    m = pd.read_sql_query("SELECT series, ym, value FROM macro_series", conn)
    wide = m.pivot(index="ym", columns="series", values="value")
    wide.index = pd.PeriodIndex(pd.to_datetime(wide.index, format="%Y%m"), freq="M")
    wide = wide.sort_index()
    own = own_apt_index(conn)
    leading = leading_apt_index(conn)
    conn.close()
    if not own.empty:
        wide = wide.join(own, how="outer")
    if not leading.empty:
        wide = wide.join(leading, how="outer")
    return wide.sort_index()
```
다음으로 교체:
```python
@st.cache_data(ttl=3600, show_spinner="자산 시계열 로딩...")
def load_assets():
    import sqlite3
    from scoring.snapshot import RAW_DB_PATH, resolve_db_path
    from scoring.market_context import leading_apt_index, own_apt_index
    db_path = resolve_db_path()
    conn = sqlite3.connect(db_path)
    m = pd.read_sql_query("SELECT series, ym, value FROM macro_series", conn)
    wide = m.pivot(index="ym", columns="series", values="value")
    wide.index = pd.PeriodIndex(pd.to_datetime(wide.index, format="%Y%m"), freq="M")
    wide = wide.sort_index()
    if db_path == RAW_DB_PATH:
        own = own_apt_index(conn)
        leading = leading_apt_index(conn)
        if not own.empty:
            wide = wide.join(own, how="outer")
        if not leading.empty:
            wide = wide.join(leading, how="outer")
    # 스냅샷 모드에서는 own_apt_index/leading_apt_index가 이미 macro_series에
    # 별도 series 행으로 들어있어(scoring/snapshot.py 참고) 위 피벗만으로 충분하다.
    conn.close()
    return wide.sort_index()
```

- [ ] **Step 4: `load_transit_times()`/`load_complex_coords()`/`load_supply()` 수정**

세 함수 모두 같은 패턴 — `from scoring.engine import DB_PATH` + `sqlite3.connect(DB_PATH)`를 `from scoring.snapshot import resolve_db_path` + `sqlite3.connect(resolve_db_path())`로 교체한다.

`load_transit_times()`:
```python
@st.cache_data(ttl=3600, show_spinner=False)
def load_transit_times():
    import sqlite3
    from scoring.snapshot import resolve_db_path
    conn = sqlite3.connect(resolve_db_path())
    try:
        t = pd.read_sql_query(
            "SELECT ckey, dest, minutes, nearest_station FROM complex_transit_time", conn)
    except Exception:
        t = pd.DataFrame(columns=["ckey", "dest", "minutes", "nearest_station"])
    conn.close()
    return t
```

`load_complex_coords()`:
```python
@st.cache_data(ttl=3600, show_spinner=False)
def load_complex_coords():
    import sqlite3
    from scoring.snapshot import resolve_db_path
    conn = sqlite3.connect(resolve_db_path())
    try:
        c = pd.read_sql_query("SELECT ckey, region_code, lat, lon FROM complex_coords", conn)
    except Exception:
        c = pd.DataFrame(columns=["ckey", "region_code", "lat", "lon"])
    conn.close()
    return c
```

`load_supply()`:
```python
@st.cache_data(ttl=3600, show_spinner=False)
def load_supply():
    import sqlite3
    from scoring.snapshot import resolve_db_path
    from scoring.market_context import load_supply_by_region_year
    conn = sqlite3.connect(resolve_db_path())
    out = load_supply_by_region_year(conn)
    conn.close()
    return out
```

- [ ] **Step 5: 로컬에서 기존 라이브 경로가 그대로 동작하는지 회귀 확인**

원본 DB가 있는 그대로의 로컬 환경에서:
Run: `cd "C:\Users\yjkim\Desktop\Claude_project\Quant_realestate" && run_app.bat`
Expected: 8개 탭 전부 이전과 동일하게 로딩됨(사이드바 레짐 배지, 스크리너 표, 단지 상세 차트 등). 확인 후 종료.

- [ ] **Step 6: 실패하는 테스트 작성 — 스냅샷 모드 스모크테스트**

`tests/test_app_snapshot_mode.py` 새 파일:

```python
from pathlib import Path

from streamlit.testing.v1 import AppTest

from scoring.snapshot import export_snapshot

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")


def test_app_boots_without_exception_in_snapshot_mode(fixture_raw_db, tmp_path, monkeypatch):
    snapshot_path = tmp_path / "snapshot" / "cloud_snapshot.db"
    monkeypatch.setattr("scoring.snapshot.RAW_DB_PATH", fixture_raw_db)
    export_snapshot(out_path=snapshot_path)

    monkeypatch.setattr("scoring.snapshot.RAW_DB_PATH", tmp_path / "does_not_exist.db")
    monkeypatch.setattr("scoring.snapshot.SNAPSHOT_DB_PATH", snapshot_path)

    at = AppTest.from_file(APP_PATH, default_timeout=60)
    at.run()

    assert not at.exception
```

- [ ] **Step 7: 테스트 실행 (수정 전이면 실패, 이미 Step 1~4를 마쳤다면 이 시점엔 통과가 정상)**

Run: `python -m pytest tests/test_app_snapshot_mode.py -v`
Expected: PASS. 만약 Step 1~4를 아직 안 했다면(플랜을 순서대로 안 밟은 경우) `no such table: trades_sale` 류 예외로 FAIL — Step 1~4부터 완료할 것.

- [ ] **Step 8: 전체 스위트 회귀 확인**

Run: `python -m pytest tests/ -q`
Expected: 이전 68개 + 신규 1개 = 69 passed

- [ ] **Step 9: 커밋**

```bash
cd /c/Users/yjkim
git add "Desktop/Claude_project/Quant_realestate/app.py" \
        "Desktop/Claude_project/Quant_realestate/tests/test_app_snapshot_mode.py"
git commit -m "feat(realestate): route app.py DB loaders through resolve_db_path()

All 7 loaders now resolve the DB path via scoring.snapshot instead
of hardcoding the raw 3GB DB — load_panel/load_assets branch to
snapshot-backed data when the raw DB is absent (cloud), everything
else just points its connection at whichever path resolves."
```

---

### Task 4: 실제 스냅샷 생성·검증·커밋

**Files:**
- Create: `scripts/export_snapshot.py`
- Create (데이터 산출물): `data/snapshot/cloud_snapshot.db`

**Interfaces:**
- Consumes: Task 2의 `scoring.snapshot.export_snapshot()`
- Produces: `data/snapshot/cloud_snapshot.db` (Task 5가 push하는 실제 배포 데이터)

- [ ] **Step 1: CLI 래퍼 작성**

```python
"""로컬에서 실행: 원본 3GB DB를 클라우드 배포용 경량 스냅샷으로 내보낸다.

사용법: python scripts/export_snapshot.py
데이터를 다시 적재(ingest/fetch_trades.py 등)한 뒤에는 반드시 이 스크립트를 재실행하고
data/snapshot/cloud_snapshot.db를 다시 커밋·푸시해야 배포된 앱에 반영된다.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scoring.snapshot import SNAPSHOT_DB_PATH, export_snapshot  # noqa: E402

if __name__ == "__main__":
    out = export_snapshot()
    size_mb = out.stat().st_size / (1024 * 1024)
    print(f"스냅샷 생성 완료: {out} ({size_mb:.1f} MB)")
    if size_mb > 100:
        print("⚠️ 100MB 초과 — GitHub 단일 파일 제한. docs/deployment_spec_v1.md의 "
              "트리밍 가이드를 참고해 재추출을 검토하세요.")
```

- [ ] **Step 2: 실제 원본 DB로 실행**

Run: `cd "C:\Users\yjkim\Desktop\Claude_project\Quant_realestate" && python scripts/export_snapshot.py`
Expected: 1~2분 내 완료, `스냅샷 생성 완료: ...cloud_snapshot.db (N.N MB)` 출력. N이 100 초과면 경고 문구가 함께 출력됨.

- [ ] **Step 3: 크기 확인 및 임계값 판단**

Run: `ls -la data/snapshot/`
- 50MB 이하: 그대로 진행(Step 4로).
- 50~100MB: 진행 가능 — 다음 세션에서 트리밍 여부를 판단해도 됨.
- 100MB 초과: `Params`를 그리드서치 기본값 그대로 두되, `export_snapshot()` 호출 전 `scoring/engine.py`의 `load_sale`/`load_jeonse`가 만드는 `trades`를 트레일링 N개월로 자르는 옵션이 필요 — 이 경우 별도 후속 태스크로 분리(현재 태스크 완료 처리하지 않고 사용자에게 보고).

- [ ] **Step 4: 스냅샷이 실제로 로컬 클라우드-시뮬레이션에서 동작하는지 수동 확인**

`data/realestate.db`를 임시로 다른 이름으로 바꿔 원본이 "없는" 상태를 재현한다(3GB 파일이므로 이동이 아니라 이름만 바꿔 시간 절약):

Run (PowerShell): `Rename-Item "data\realestate.db" "realestate.db.bak"`
Run: `run_app.bat`
Expected: 스피너 문구가 "시세 패널·팩터 계산 중 (최초 1회, 1~2분)..."이 아니라 즉시(수 초 내) 로딩 완료됨 — 스냅샷을 읽었다는 신호. 8개 탭 전부 에러 없이 로딩되는지 확인(특히 TabA 자산비교 — own/leading 지수가 표시되는지).
Run (PowerShell, 원복): `Rename-Item "data\realestate.db.bak" "realestate.db"`

**주의**: 이 Step은 원본 3GB 파일을 다루므로 반드시 `Rename-Item`(이동 아님, 같은 드라이브 내 이름 변경이라 즉시 완료)만 쓰고, 확인 후 즉시 원복한다. 실행 전후로 `Test-Path data\realestate.db`로 존재 확인할 것.

- [ ] **Step 5: 커밋 (코드 + 생성된 스냅샷 데이터)**

```bash
cd /c/Users/yjkim
git add "Desktop/Claude_project/Quant_realestate/scripts/export_snapshot.py" \
        "Desktop/Claude_project/Quant_realestate/data/snapshot/cloud_snapshot.db"
git status --porcelain -- "Desktop/Claude_project/Quant_realestate"
git commit -m "feat(realestate): generate cloud snapshot from live data

First real export from the 3GB raw DB — this is the data the
Streamlit Cloud deployment will actually read (no raw DB there)."
```

`git status --porcelain` 결과가 위 두 경로 외 다른 파일을 포함하지 않는지 커밋 전 반드시 확인한다(저장소 루트가 홈 디렉토리 전체이므로).

---

### Task 5: GitHub 푸시 + Streamlit Community Cloud 등록 (수동)

**Files:** 없음 (배포 조작, 코드 변경 아님)

**Interfaces:**
- Consumes: Task 1~4에서 커밋된 전체 내용
- Produces: 공개 배포 URL (`https://<앱이름>.streamlit.app`)

- [ ] **Step 1: 원격 푸시**

```bash
cd /c/Users/yjkim
git push origin main
```
Expected: `github.com/yjkim12130/Quant_project`의 `main` 브랜치에 Task 1~4의 커밋들이 반영됨.

- [ ] **Step 2: Streamlit Community Cloud에서 앱 등록 (브라우저 작업, 사용자 직접 진행)**

1. https://share.streamlit.io 접속 → GitHub 계정으로 로그인(이미 연동돼 있으면 스킵)
2. "New app" 클릭
3. Repository: `yjkim12130/Quant_project`, Branch: `main`
4. Main file path: `Desktop/Claude_project/Quant_realestate/app.py`
5. "Deploy!" 클릭 → 빌드 로그에서 `requirements.txt`가 `Desktop/Claude_project/Quant_realestate/requirements.txt`에서 정상 설치되는지 확인 (Streamlit Cloud는 main file과 같은 디렉토리의 requirements.txt를 자동으로 찾는다)

- [ ] **Step 3: 첫 배포 확인**

빌드 완료 후 앱 URL 접속 → 8개 탭이 스냅샷 데이터로 정상 로딩되는지 확인(로컬 Step 4에서 확인한 것과 동일한 체크리스트: 사이드바 레짐 배지, 스크리너 표, TabA 자산비교의 own/leading 지수, 단지 상세 차트).

- [ ] **Step 4: 모바일 접속 확인**

같은 앱 URL을 휴대폰 브라우저(Wi-Fi 끄고 모바일 데이터로, "집 아닌 곳" 조건 재현)에서 열어 정상 표시되는지 확인.

- [ ] **Step 5: 향후 데이터 갱신 워크플로 기록**

이후 실거래 데이터를 다시 적재하고 싶을 때:
1. 로컬 배치 적재 재실행 (`ingest/fetch_trades.py` 등)
2. `python scripts/export_snapshot.py`
3. `git add "Desktop/Claude_project/Quant_realestate/data/snapshot/cloud_snapshot.db"` → 커밋 → `git push`
4. Streamlit Cloud가 push를 감지해 자동 재배포 (수 분 소요)

이 워크플로를 사용자에게 안내하고 태스크 완료.

---

## Self-Review Notes

- **Spec coverage**: 스펙의 아키텍처(스냅샷 분기)·데이터 갱신 워크플로·Git 안전수칙·ManageStock 함정 대응·검증 기준 전부 태스크로 매핑됨. "예산 정보 저장 금지"는 코드 변경 대상이 아니라(기존 동작 유지) 별도 태스크 불필요 — Global Constraints에 명시.
- **크기 트리밍 로직**: 100MB 초과 시나리오는 실측 전에는 확정할 수 없어 Task 4 Step 3에서 조건부 후속 결정으로 남겨둠(placeholder 아님 — 실측 후 판단 가능한 명확한 기준 제시).
- **타입 일관성**: `resolve_db_path()`/`RAW_DB_PATH`/`SNAPSHOT_DB_PATH`/`export_snapshot()`/`load_panel_snapshot()` 이름이 Task 2~4 전체에서 동일하게 사용됨.
