# 시장환경 지표(공급·교통·자산비교) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Quant_realestate 대시보드에 공급(🏗️)·교통(🚇)·자산군비교(🌐 확장) 3개 조회용 지표를 추가한다.

**Architecture:** 기존 `ingest/`(배치 적재) → `data/realestate.db`(SQLite) → `scoring/`(순수 계산) → `app.py`(Streamlit 조회)
파이프라인을 그대로 따른다. 신규 외부 API 3개(카카오로컬·국가철도공단·청약홈)를 위한 신규 ingest 스크립트
3개, DB 테이블 5개, `scoring/market_context.py`(신규 계산 모듈), `config/manual_catalysts.yaml`(수동
큐레이션)을 추가하고, `app.py`에 신규 탭 2개 + 기존 탭 2개(단지상세·자산비교) 수정을 가한다.

**Tech Stack:** Python, SQLite, pandas, requests, PyYAML, Streamlit, Plotly, pytest(신규 도입 — 순수 로직 함수에만 적용)

**Spec:** `docs/market_context_spec_v1.md`

## Global Constraints

- git 저장소 루트가 `C:\Users\yjkim` 홈 디렉터리 전체다 — 커밋 시 `Quant_realestate/` 하위 경로만 지정해서
  targeted add로 커밋한다. **`git add -A`/`git add .` 절대 금지.**
- git commit author identity(user.email/user.name)가 미설정 상태다. 이 플랜의 각 태스크 말미 커밋 스텝은
  최초 실행 시 `Author identity unknown` 에러로 막힐 수 있다 — 발생하면 사용자에게 `git config user.email`/
  `user.name` 설정을 요청하고, **자동으로 설정하지 않는다.**
- 이 프로젝트는 **pytest를 쓰지 않는다** (기존 검증은 `scoring/diagnostics.py`류 실측 리포트 스크립트).
  이 플랜은 순수 로직 함수(그래프 최단경로, z-score 계산, YAML 집계 등)에 한해 **처음으로 pytest를 도입**한다
  (`requirements.txt`에 `pytest>=8.0` 추가, Task 1에서). 외부 API를 직접 호출하는 ingest 코드는 목킹하지
  않고, 기존 `ingest/fetch_trades.py`의 `verify_api_response()`와 동일한 패턴 — **1건 실호출로 키/응답 검증
  후 배치 진행** — 을 따른다. 각 신규 ingest 스크립트의 첫 실행은 반드시 소량 스모크테스트로 시작한다.
- API 키는 `config/api_keys.local.yaml`에만 채운다 (`.gitignore` 등록됨, 커밋 금지). `api_keys.example.yaml`에는
  발급처 URL 주석 + 빈 값만 추가한다.
- 신규 DB 테이블은 기존 `data/realestate.db`에 추가한다 (신규 DB 파일 아님). 스키마는 `ingest/db.py`의
  `SCHEMA` 문자열에 追加한다 (`CREATE TABLE IF NOT EXISTS` — 기존 관례).
- `ckey`(단지 식별키)는 `scoring/engine.py`의 `_complex_key()` = `region_code|dong_name|정규화단지명` 이다.
  **`apt_seq`가 아니다** — `apt_seq`는 결측이 많아 이 프로젝트에서 실제로는 안 쓰인다(engine.py 62번째 줄
  docstring은 예전 의도이고 실제 구현은 항상 composite key). 지오코딩·교통시간 테이블은 전부 `ckey`로 조인한다.
- Streamlit 포트는 8502 고정 (`.streamlit/config.toml`, Quant_dashboard의 8501과 충돌 방지). 신규 코드에서
  포트 변경 금지.
- 외부 API(청약홈/카카오로컬/국가철도공단) 응답 필드명은 라이브 호출 전까지 100% 확정할 수 없다. 각 파싱
  함수는 원본 필드명을 표준 컬럼명으로 매핑하는 `COLUMN_MAP` 딕셔너리 하나를 통해서만 원본 스키마에
  의존하도록 설계했다 — 실제 응답이 문서와 다르면 **해당 태스크의 COLUMN_MAP만 수정**하면 된다(전체 로직
  변경 불필요). 각 태스크의 Step 1은 이 매핑을 검증하는 스모크테스트다.

---

## 확인된 외부 서비스 (2026-08-15 조사)

| 용도 | 서비스명 | 링크 |
|---|---|---|
| 청약홈 분양정보 | 한국부동산원_청약홈 분양정보 조회 서비스 | https://www.data.go.kr/data/15098547/openapi.do |
| 카카오 지오코딩 | 카카오로컬 주소검색/키워드검색 API | https://developers.kakao.com (앱 등록 → REST API 키) |
| 지하철 노선/역 | 국가철도공단_도시철도 전체노선정보 | https://www.data.go.kr/data/15041666/openapi.do |

3개 모두 활용신청/앱등록이 필요하며, 이 플랜의 Task 2/4/9 착수 전 사용자가 직접 신청해야 한다
(기존 프로젝트도 Phase 0에서 동일하게 진행됨 — data.go.kr 활용신청은 자동승인, 카카오 디벨로퍼스는 즉시
발급, 승인까지 최대 1시간 지연 가능하니 각 태스크 스모크테스트 전 여유를 두고 신청할 것).

---

## Task 1: DB 스키마 확장 + API 키 슬롯 + pytest 도입

**Files:**
- Modify: `ingest/db.py` (SCHEMA 문자열에 5개 테이블 추가)
- Modify: `config/api_keys.example.yaml` (3개 서비스 슬롯 추가)
- Modify: `requirements.txt` (`pytest>=8.0` 추가)
- Create: `tests/conftest.py`
- Create: `tests/test_db_schema.py`

**Interfaces:**
- Produces: `complex_coords(ckey, region_code, address_used, lat, lon, geocoded_at)`,
  `station_node(station_id, station_name, line_name, seq, lat, lon)`,
  `station_edge(from_id, to_id, minutes, edge_type)`,
  `complex_transit_time(ckey, dest, minutes, nearest_station, calculated_at)`,
  `supply_presale(region_code, expected_ym, project_name, total_units, source, fetched_at)`
  — 이후 모든 태스크가 이 5개 테이블 이름/컬럼명을 그대로 사용한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/conftest.py`:
```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

`tests/test_db_schema.py`:
```python
import sqlite3

from ingest.db import SCHEMA

NEW_TABLES = {
    "complex_coords", "station_node", "station_edge",
    "complex_transit_time", "supply_presale",
}


def test_schema_creates_new_tables(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    existing = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    missing = NEW_TABLES - existing
    assert not missing, f"누락된 테이블: {missing}"
    conn.close()


def test_complex_coords_ckey_is_primary_key(tmp_path):
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    cols = conn.execute("PRAGMA table_info(complex_coords)").fetchall()
    pk_cols = [c[1] for c in cols if c[5] == 1]  # c[5] = pk 순번(1부터), 0이면 아님
    assert pk_cols == ["ckey"]
    conn.close()
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `cd Quant_realestate && python -m pytest tests/test_db_schema.py -v`
Expected: FAIL (`AssertionError: 누락된 테이블: {...}` — 5개 테이블 전부 미존재)

- [ ] **Step 3: `ingest/db.py`의 `SCHEMA`에 추가**

`ingest/db.py`의 `SCHEMA = """..."""` 문자열 끝(기존 인덱스 정의 다음)에 추가:

```sql

CREATE TABLE IF NOT EXISTS complex_coords (
    ckey TEXT PRIMARY KEY,
    region_code TEXT,
    address_used TEXT,
    lat REAL,
    lon REAL,
    geocoded_at TEXT
);

CREATE TABLE IF NOT EXISTS station_node (
    station_id TEXT PRIMARY KEY,
    station_name TEXT NOT NULL,
    line_name TEXT NOT NULL,
    seq INTEGER,
    lat REAL,
    lon REAL
);

CREATE TABLE IF NOT EXISTS station_edge (
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    minutes REAL NOT NULL,
    edge_type TEXT NOT NULL,  -- 'ride'(동일노선 인접역) | 'transfer'(환승, 동일역명 타노선)
    PRIMARY KEY (from_id, to_id)
);

CREATE TABLE IF NOT EXISTS complex_transit_time (
    ckey TEXT NOT NULL,
    dest TEXT NOT NULL,  -- '강남' | '종로' | '여의도' | '판교' | '동탄'
    minutes REAL,
    nearest_station TEXT,
    calculated_at TEXT,
    PRIMARY KEY (ckey, dest)
);

CREATE TABLE IF NOT EXISTS supply_presale (
    region_code TEXT NOT NULL,
    expected_ym TEXT NOT NULL,  -- YYYYMM
    project_name TEXT,
    total_units INTEGER,
    source TEXT,
    fetched_at TEXT,
    PRIMARY KEY (region_code, expected_ym, project_name)
);
"""
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `python -m pytest tests/test_db_schema.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: API 키 슬롯 + pytest 의존성 추가**

`config/api_keys.example.yaml` 끝에 추가:
```yaml

apply_home:
  # https://www.data.go.kr/data/15098547/openapi.do — 한국부동산원_청약홈 분양정보 조회 서비스
  api_key: ""

kakao:
  # https://developers.kakao.com → 애플리케이션 추가 → 앱 키의 "REST API 키"
  # (지도 API 별도 활성화 불필요 — 로컬/주소 검색은 REST API 키만 있으면 됨)
  rest_api_key: ""

tago:
  # https://www.data.go.kr/data/15041666/openapi.do — 국가철도공단_도시철도 전체노선정보
  api_key: ""
```

`requirements.txt` 끝에 추가:
```
pytest>=8.0
```

- [ ] **Step 6: 커밋**

```bash
git add ingest/db.py config/api_keys.example.yaml requirements.txt tests/conftest.py tests/test_db_schema.py
git commit -m "feat: 시장환경 지표용 DB 스키마 5종 + API 키 슬롯 3종 + pytest 도입"
```

---

## Task 2: 카카오 지오코딩 (`ingest/fetch_geocode.py`)

사용자 액션 필요: 카카오 디벨로퍼스에서 앱 등록 후 REST API 키를 `config/api_keys.local.yaml`의
`kakao.rest_api_key`에 채워야 이 태스크의 Step 7(스모크테스트) 진행 가능.

**Files:**
- Create: `ingest/fetch_geocode.py`
- Test: `tests/test_geocode.py`

**Interfaces:**
- Consumes (Task 1): `complex_coords` 테이블
- Consumes: `scoring.engine._complex_key`
- Produces: `geocode_query(row: dict) -> str`, `parse_kakao_address(data: dict) -> tuple[float, float] | None`,
  `parse_kakao_keyword(data: dict) -> tuple[float, float] | None` — Task 4(교통)가 `complex_coords`를
  읽을 때 이 태스크가 채운 `(lat, lon)` 값을 그대로 소비한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_geocode.py`:
```python
from ingest.fetch_geocode import geocode_query, parse_kakao_address, parse_kakao_keyword


def test_geocode_query_prefers_road_name():
    row = {"region_name": "강남구", "dong_name": "역삼동", "road_name": "테헤란로 123",
           "jibun": "123-45", "complex_name": "래미안역삼"}
    assert geocode_query(row, prefer="road") == "강남구 역삼동 테헤란로 123"


def test_geocode_query_falls_back_to_jibun():
    row = {"region_name": "강남구", "dong_name": "역삼동", "road_name": None,
           "jibun": "123-45", "complex_name": "래미안역삼"}
    assert geocode_query(row, prefer="jibun") == "강남구 역삼동 123-45"


def test_geocode_query_keyword_uses_complex_name():
    row = {"region_name": "강남구", "dong_name": "역삼동", "road_name": None,
           "jibun": None, "complex_name": "래미안역삼"}
    assert geocode_query(row, prefer="keyword") == "강남구 역삼동 래미안역삼"


def test_parse_kakao_address_returns_lat_lon():
    # 카카오 주소검색 API: address.x=경도, address.y=위도 (문자열)
    data = {"documents": [{"address": {"x": "127.123", "y": "37.456"}}]}
    assert parse_kakao_address(data) == (37.456, 127.123)


def test_parse_kakao_address_empty_returns_none():
    assert parse_kakao_address({"documents": []}) is None


def test_parse_kakao_keyword_returns_lat_lon():
    # 카카오 키워드검색 API: documents[0].x=경도, documents[0].y=위도 (address 중첩 없음)
    data = {"documents": [{"x": "127.111", "y": "37.222"}]}
    assert parse_kakao_keyword(data) == (37.222, 127.111)


def test_parse_kakao_keyword_empty_returns_none():
    assert parse_kakao_keyword({"documents": []}) is None
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python -m pytest tests/test_geocode.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'ingest.fetch_geocode'`)

- [ ] **Step 3: 최소 구현 — 순수 함수 부분**

`ingest/fetch_geocode.py`:
```python
"""단지 좌표 지오코딩 — 카카오로컬 API.

trades_sale의 고유 단지(ckey)마다 도로명주소 → 지번주소 → 단지명 키워드 순으로 좌표를
조회해 complex_coords 테이블에 적재한다. 일회성 배치이며, 신규 단지가 생기면 재실행해도
이미 적재된 ckey는 건너뛴다(pending_complexes가 complex_coords에 없는 것만 반환).

사용법:
    python ingest/fetch_geocode.py --limit 20      # 스모크테스트
    python ingest/fetch_geocode.py                 # 전체 배치
"""
import sys
import time
from pathlib import Path

import pandas as pd
import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_connection  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scoring.engine import _complex_key  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
API_KEYS_YAML = ROOT / "config" / "api_keys.local.yaml"

KAKAO_ADDR_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
CALL_INTERVAL_SEC = 0.1


def geocode_query(row, prefer):
    if prefer == "road":
        return f"{row['region_name']} {row['dong_name']} {row['road_name']}"
    if prefer == "jibun":
        return f"{row['region_name']} {row['dong_name']} {row['jibun']}"
    return f"{row['region_name']} {row['dong_name']} {row['complex_name']}"


def parse_kakao_address(data):
    docs = data.get("documents") or []
    if not docs:
        return None
    addr = docs[0]["address"]
    return (float(addr["y"]), float(addr["x"]))


def parse_kakao_keyword(data):
    docs = data.get("documents") or []
    if not docs:
        return None
    return (float(docs[0]["y"]), float(docs[0]["x"]))


def load_kakao_key():
    with open(API_KEYS_YAML, encoding="utf-8") as f:
        keys = yaml.safe_load(f) or {}
    key = (keys.get("kakao") or {}).get("rest_api_key", "")
    if not key:
        raise ValueError("api_keys.local.yaml 의 kakao.rest_api_key 가 비어있습니다.")
    return key


def geocode_one(session, api_key, row):
    """도로명 → 지번 → 키워드(단지명) 순으로 시도. 성공 시 (lat, lon, 사용한 쿼리), 실패 시 None."""
    headers = {"Authorization": f"KakaoAK {api_key}"}
    attempts = []
    if row.get("road_name"):
        attempts.append(("road", KAKAO_ADDR_URL, parse_kakao_address))
    if row.get("jibun"):
        attempts.append(("jibun", KAKAO_ADDR_URL, parse_kakao_address))
    attempts.append(("keyword", KAKAO_KEYWORD_URL, parse_kakao_keyword))

    for prefer, url, parser in attempts:
        query = geocode_query(row, prefer)
        res = session.get(url, headers=headers, params={"query": query}, timeout=10)
        res.raise_for_status()
        result = parser(res.json())
        if result:
            return result[0], result[1], query
        time.sleep(CALL_INTERVAL_SEC)
    return None


def pending_complexes(conn):
    df = pd.read_sql_query(
        "SELECT region_code, region_name, dong_name, complex_name, road_name, jibun "
        "FROM trades_sale", conn)
    df["ckey"] = _complex_key(df)
    df = df.sort_values("road_name", na_position="last").drop_duplicates("ckey")
    done = pd.read_sql_query("SELECT ckey FROM complex_coords", conn)["ckey"]
    return df[~df["ckey"].isin(done)].reset_index(drop=True)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="단지 좌표 지오코딩(카카오로컬)")
    ap.add_argument("--limit", type=int, default=None, help="스모크테스트용 처리 건수 제한")
    args = ap.parse_args()

    api_key = load_kakao_key()
    conn = get_connection()
    pending = pending_complexes(conn)
    if args.limit:
        pending = pending.head(args.limit)
    print(f"지오코딩 대상: {len(pending)}개 단지")

    session = requests.Session()
    ok = fail = 0
    now = pd.Timestamp.utcnow().isoformat()
    for row in pending.to_dict("records"):
        try:
            result = geocode_one(session, api_key, row)
        except Exception as e:  # noqa: BLE001 — 개별 실패가 배치 전체를 막지 않음
            print(f"  [실패] {row['ckey']}: {e}")
            fail += 1
            continue
        if result is None:
            print(f"  [미발견] {row['ckey']} ({row['complex_name']})")
            fail += 1
            continue
        lat, lon, query = result
        conn.execute(
            "INSERT OR REPLACE INTO complex_coords (ckey, region_code, address_used, lat, lon, geocoded_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (row["ckey"], row["region_code"], query, lat, lon, now),
        )
        conn.commit()
        ok += 1
        if ok % 50 == 0:
            print(f"  진행: 성공 {ok} / 실패 {fail}")
        time.sleep(CALL_INTERVAL_SEC)

    print(f"완료: 성공 {ok} / 실패 {fail}")
    conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `python -m pytest tests/test_geocode.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: 커밋 (순수 로직)**

```bash
git add ingest/fetch_geocode.py tests/test_geocode.py
git commit -m "feat: 카카오로컬 지오코딩 쿼리 생성/응답 파싱 함수 + 테스트"
```

- [ ] **Step 6: 사용자 액션 대기 — 카카오 REST API 키 발급**

카카오 디벨로퍼스(https://developers.kakao.com)에서 애플리케이션 생성 후 REST API 키를
`config/api_keys.local.yaml`의 `kakao.rest_api_key`에 채워달라고 사용자에게 요청. 키가 없으면
Step 7 진행 불가 — 이 스텝은 실행자가 사용자 응답을 기다려야 한다.

- [ ] **Step 7: 스모크테스트 (실 API 호출, 20건)**

Run: `python ingest/fetch_geocode.py --limit 20`
Expected: "완료: 성공 N / 실패 M" 출력, N이 대부분(예: 18/20 이상). 실패가 많으면(예: 절반 이상)
`geocode_one`의 쿼리 조합이나 카카오 키 상태를 재점검 — 배치 전체 실행 전에 여기서 잡아야 한다.

- [ ] **Step 8: 전체 배치 실행 + 커밋**

Run: `python ingest/fetch_geocode.py` (수천 건, 완료까지 수 분~수십 분 — CALL_INTERVAL_SEC 0.1초 기준
5,000건이면 약 8분)

```bash
git add -A -- ingest/fetch_geocode.py  # 코드 변경 없으면 이 커밋 스킵 (DB는 git 추적 대상 아님)
```

DB 데이터는 커밋 대상이 아니므로(`data/realestate.db`는 `.gitignore` 확인 필요 — Task 1에서 이미
존재하는 `.gitignore` 정책을 따른다) 이 스텝은 코드 변경이 없으면 커밋 생략.

---

## Task 3: 지하철 노선/역 데이터 적재 (`ingest/fetch_transit.py` — 그래프 구성부)

사용자 액션 필요: data.go.kr에서 "국가철도공단_도시철도 전체노선정보" 활용신청 후 인증키를
`config/api_keys.local.yaml`의 `tago.api_key`에 채워야 Step 6(스모크테스트) 진행 가능.

**Files:**
- Create: `ingest/fetch_transit.py`
- Test: `tests/test_transit.py`

**Interfaces:**
- Produces: `station_node`, `station_edge` 테이블 (Task 1 스키마)
- Produces: `TARGET_STATIONS = {"강남": "강남역", "종로": "종각역", "여의도": "여의도역", "판교": "판교역", "동탄": "동탄역"}`
  — Task 5(단지상세 반영)·Task 6(교통 탭)가 이 딕셔너리의 키(목적지 표시명)를 그대로 사용한다.
- Produces: `normalize_route_rows(raw: list[dict]) -> pd.DataFrame` (columns: station_name, line_name, seq, lat, lon)
- Produces: `build_edges(nodes: pd.DataFrame, ride_minutes=2.0, transfer_minutes=5.0) -> pd.DataFrame`
  (columns: from_id, to_id, minutes, edge_type)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_transit.py`:
```python
import pandas as pd

from ingest.fetch_transit import normalize_route_rows, build_edges, COLUMN_MAP

RAW_SAMPLE = [
    {"LNCD_NM": "2호선", "STIN_NM": "강남", "STIN_SEQ": "1", "LAT": "37.4979", "LOT": "127.0276"},
    {"LNCD_NM": "2호선", "STIN_NM": "역삼", "STIN_SEQ": "2", "LAT": "37.5006", "LOT": "127.0364"},
    {"LNCD_NM": "신분당선", "STIN_NM": "강남", "STIN_SEQ": "1", "LAT": "37.4979", "LOT": "127.0276"},
]


def test_normalize_route_rows_maps_known_columns():
    df = normalize_route_rows(RAW_SAMPLE)
    assert list(df.columns) == ["station_name", "line_name", "seq", "lat", "lon"]
    assert len(df) == 3
    assert df.iloc[0]["station_name"] == "강남"
    assert df.iloc[0]["lat"] == 37.4979


def test_normalize_route_rows_seq_is_int():
    df = normalize_route_rows(RAW_SAMPLE)
    assert df["seq"].dtype.kind in "iu"


def test_build_edges_creates_ride_edges_between_adjacent_seq():
    nodes = normalize_route_rows(RAW_SAMPLE)
    nodes["station_id"] = nodes["line_name"] + "_" + nodes["station_name"]
    edges = build_edges(nodes)
    ride = edges[edges["edge_type"] == "ride"]
    # 2호선 강남(seq1)-역삼(seq2) 인접 → 양방향 ride edge 2개
    assert len(ride) == 2
    assert set(ride["minutes"]) == {2.0}


def test_build_edges_creates_transfer_edges_for_same_station_name():
    nodes = normalize_route_rows(RAW_SAMPLE)
    nodes["station_id"] = nodes["line_name"] + "_" + nodes["station_name"]
    edges = build_edges(nodes)
    transfer = edges[edges["edge_type"] == "transfer"]
    # 2호선 강남 <-> 신분당선 강남 환승 → 양방향 2개
    assert len(transfer) == 2
    assert set(transfer["minutes"]) == {5.0}


def test_column_map_has_expected_keys():
    # 실제 API 응답이 다르면 이 4개 키의 매핑값만 조정하면 된다 (Global Constraints 참고)
    assert set(COLUMN_MAP) == {"station_name", "line_name", "seq", "lat", "lon"}
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python -m pytest tests/test_transit.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'ingest.fetch_transit'`)

- [ ] **Step 3: 최소 구현**

`ingest/fetch_transit.py`:
```python
"""지하철 노선/역 그래프 구성 + 단지→업무지구 소요시간 계산.

노선 데이터 출처: 국가철도공단_도시철도 전체노선정보 (data.go.kr/data/15041666).
원본 응답 필드명은 COLUMN_MAP 하나로만 이 코드에 반영된다 — 실제 응답이 아래 기본값과
다르면 COLUMN_MAP 값만 고치면 된다(Global Constraints 참고). 최초 실행 전
`python ingest/fetch_transit.py --smoke-test` 로 원본 응답 1페이지를 출력해 확인할 것.

소요시간은 정밀 실측이 아니라 "동일 노선 인접역 = RIDE_MINUTES(기본 2분), 환승 = TRANSFER_MINUTES
(기본 5분)" 근사다 (오차 ±5~10분 수준, market_context_spec_v1.md §3.2 확정 사항 — 순위 비교용으로는
충분하다는 전제).

사용법:
    python ingest/fetch_transit.py --smoke-test    # 원본 응답 1페이지 출력만
    python ingest/fetch_transit.py                 # 노선/역 적재 + 그래프 구성 + 소요시간 계산
"""
import sys
import time
from pathlib import Path

import heapq
import pandas as pd
import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_connection  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
API_KEYS_YAML = ROOT / "config" / "api_keys.local.yaml"

TAGO_ROUTE_URL = "http://apis.data.go.kr/1613000/UrbanRailroadInfoService/getUrbanRailroadInfo"

# 원본 API 필드명 → 표준 컬럼명. 국토교통부 표준데이터셋 명세 기준 1차 추정값 —
# 스모크테스트(--smoke-test) 응답과 다르면 이 4개 값만 실제 필드명으로 교체.
COLUMN_MAP = {
    "station_name": "STIN_NM",
    "line_name": "LNCD_NM",
    "seq": "STIN_SEQ",
    "lat": "LAT",
    "lon": "LOT",
}

RIDE_MINUTES = 2.0
TRANSFER_MINUTES = 5.0

TARGET_STATIONS = {
    "강남": "강남역", "종로": "종각역", "여의도": "여의도역", "판교": "판교역", "동탄": "동탄역",
}


def load_tago_key():
    with open(API_KEYS_YAML, encoding="utf-8") as f:
        keys = yaml.safe_load(f) or {}
    key = (keys.get("tago") or {}).get("api_key", "")
    if not key:
        raise ValueError("api_keys.local.yaml 의 tago.api_key 가 비어있습니다.")
    return key


def fetch_raw_routes(api_key, num_of_rows=1000):
    """전 페이지 수집. 반환은 원본 dict 리스트(정규화 전)."""
    rows, page = [], 1
    while True:
        r = requests.get(TAGO_ROUTE_URL, params={
            "serviceKey": api_key, "_type": "json",
            "numOfRows": num_of_rows, "pageNo": page,
        }, timeout=30)
        r.raise_for_status()
        body = r.json()["response"]["body"]
        items = body.get("items") or {}
        page_rows = items.get("item") or []
        if isinstance(page_rows, dict):  # 결과 1건일 때 dict로 오는 API가 있음
            page_rows = [page_rows]
        if not page_rows:
            break
        rows.extend(page_rows)
        if len(rows) >= int(body.get("totalCount", 0)):
            break
        page += 1
        time.sleep(0.2)
    return rows


def normalize_route_rows(raw):
    df = pd.DataFrame(raw)
    out = pd.DataFrame({std: df[orig] for std, orig in COLUMN_MAP.items()})
    out["seq"] = pd.to_numeric(out["seq"], errors="coerce").astype("Int64")
    out["lat"] = pd.to_numeric(out["lat"], errors="coerce")
    out["lon"] = pd.to_numeric(out["lon"], errors="coerce")
    return out.dropna(subset=["station_name", "line_name", "seq", "lat", "lon"])


def build_edges(nodes, ride_minutes=RIDE_MINUTES, transfer_minutes=TRANSFER_MINUTES):
    edges = []
    # 동일 노선 인접역(seq 차이 1) -> ride edge 양방향
    for _, line_df in nodes.groupby("line_name"):
        line_df = line_df.sort_values("seq")
        ids = line_df["station_id"].tolist()
        for a, b in zip(ids[:-1], ids[1:]):
            edges.append((a, b, ride_minutes, "ride"))
            edges.append((b, a, ride_minutes, "ride"))
    # 동일 역명, 다른 노선 -> transfer edge 양방향 (전 쌍 조합)
    for _, name_df in nodes.groupby("station_name"):
        ids = name_df["station_id"].unique().tolist()
        for i in range(len(ids)):
            for j in range(len(ids)):
                if i != j:
                    edges.append((ids[i], ids[j], transfer_minutes, "transfer"))
    return pd.DataFrame(edges, columns=["from_id", "to_id", "minutes", "edge_type"]).drop_duplicates(
        subset=["from_id", "to_id"])


def shortest_minutes(adj, start_id, target_ids):
    """다익스트라. adj: {station_id: [(neighbor_id, minutes), ...]}. 반환: {target_id: minutes}."""
    dist = {start_id: 0.0}
    pq = [(0.0, start_id)]
    remaining = set(target_ids) - {start_id}
    found = {t: 0.0 for t in target_ids if t == start_id}
    while pq and remaining:
        d, node = heapq.heappop(pq)
        if d > dist.get(node, float("inf")):
            continue
        for neighbor, w in adj.get(node, []):
            nd = d + w
            if nd < dist.get(neighbor, float("inf")):
                dist[neighbor] = nd
                heapq.heappush(pq, (nd, neighbor))
        if node in remaining:
            found[node] = d
            remaining.discard(node)
    for t in target_ids:
        found.setdefault(t, dist.get(t, float("nan")))
    return found


def main():
    import argparse
    ap = argparse.ArgumentParser(description="지하철 노선/역 적재 + 그래프 구성")
    ap.add_argument("--smoke-test", action="store_true", help="원본 응답 1페이지만 출력하고 종료")
    args = ap.parse_args()

    api_key = load_tago_key()
    if args.smoke_test:
        raw = requests.get(TAGO_ROUTE_URL, params={
            "serviceKey": api_key, "_type": "json", "numOfRows": 5, "pageNo": 1,
        }, timeout=30)
        print(raw.text[:2000])
        return

    raw = fetch_raw_routes(api_key)
    nodes = normalize_route_rows(raw)
    nodes["station_id"] = nodes["line_name"] + "_" + nodes["station_name"]
    nodes = nodes.drop_duplicates("station_id")
    edges = build_edges(nodes)

    conn = get_connection()
    conn.execute("DELETE FROM station_node")
    conn.execute("DELETE FROM station_edge")
    conn.executemany(
        "INSERT INTO station_node (station_id, station_name, line_name, seq, lat, lon) VALUES (?,?,?,?,?,?)",
        nodes[["station_id", "station_name", "line_name", "seq", "lat", "lon"]].itertuples(index=False, name=None))
    conn.executemany(
        "INSERT INTO station_edge (from_id, to_id, minutes, edge_type) VALUES (?,?,?,?)",
        edges.itertuples(index=False, name=None))
    conn.commit()
    print(f"완료: 역 {len(nodes)}개 / 엣지 {len(edges)}개")

    missing = [name for name in TARGET_STATIONS.values()
               if name not in nodes["station_name"].values]
    if missing:
        print(f"[경고] 목표 업무지구 대표역이 노선 데이터에 없음: {missing} — "
              "역명 표기가 다를 수 있으니 station_node 테이블을 확인하세요.")
    conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `python -m pytest tests/test_transit.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: 커밋**

```bash
git add ingest/fetch_transit.py tests/test_transit.py
git commit -m "feat: 지하철 노선 그래프 구성(정규화/엣지생성/다익스트라) + 테스트"
```

- [ ] **Step 6: 사용자 액션 대기 — TAGO 인증키 발급 후 스모크테스트**

data.go.kr에서 "국가철도공단_도시철도 전체노선정보" 활용신청 완료 후 `config/api_keys.local.yaml`의
`tago.api_key`에 키를 채워달라고 사용자에게 요청. 키 확보 후:

Run: `python ingest/fetch_transit.py --smoke-test`
Expected: JSON 응답 출력. `COLUMN_MAP`에 지정한 4개 필드(`STIN_NM`, `LNCD_NM`, `STIN_SEQ`, `LAT`, `LOT`)가
실제 응답에 그 이름 그대로 있는지 확인. 다르면 `COLUMN_MAP` 값을 실제 필드명으로 수정 후 이 스텝 재실행.

- [ ] **Step 7: 전체 적재 실행**

Run: `python ingest/fetch_transit.py`
Expected: "완료: 역 N개 / 엣지 M개" 출력, `[경고]` 줄이 없어야 함(있으면 대표역 이름 표기 차이 — station_node
테이블에서 실제 표기 확인 후 `TARGET_STATIONS` 값을 코드에서 맞게 수정하고 재실행).

---

## Task 4: 단지→업무지구 소요시간 계산 (`ingest/fetch_transit.py` — 배치 계산부 추가)

**Files:**
- Modify: `ingest/fetch_transit.py` (nearest_station + 배치 계산 함수 추가)
- Modify: `tests/test_transit.py` (nearest_station 테스트 추가)

**Interfaces:**
- Consumes: Task 2의 `complex_coords`, Task 3의 `station_node`/`station_edge`/`shortest_minutes`/`TARGET_STATIONS`
- Produces: `complex_transit_time` 테이블 완전 채움. `nearest_station(lat, lon, stations) -> str`
  — Task 6(교통 탭)이 단지 상세 화면에서 "최근접역: {name}" 표시에 재사용한다.

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_transit.py`에 추가:
```python
import math

from ingest.fetch_transit import nearest_station, haversine_km


def test_haversine_km_zero_distance():
    assert haversine_km(37.5, 127.0, 37.5, 127.0) == 0.0


def test_haversine_km_known_pair():
    # 강남역(37.4979,127.0276) ~ 역삼역(37.5006,127.0364) 실측 약 0.8km
    d = haversine_km(37.4979, 127.0276, 37.5006, 127.0364)
    assert 0.5 < d < 1.2


def test_nearest_station_picks_closest():
    stations = pd.DataFrame({
        "station_id": ["A", "B"], "lat": [37.50, 37.60], "lon": [127.03, 127.10],
    })
    result = nearest_station(37.501, 127.031, stations)
    assert result == "A"
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python -m pytest tests/test_transit.py -v`
Expected: FAIL (`ImportError: cannot import name 'nearest_station'`)

- [ ] **Step 3: 구현 추가**

`ingest/fetch_transit.py`에 추가 (기존 `shortest_minutes` 함수 뒤):
```python
def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_station(lat, lon, stations):
    """stations: station_id/lat/lon 컬럼 DataFrame. 가장 가까운 station_id 반환."""
    d = stations.apply(lambda s: haversine_km(lat, lon, s["lat"], s["lon"]), axis=1)
    return stations.loc[d.idxmin(), "station_id"]


def compute_transit_times(conn):
    """complex_coords 전체에 대해 5개 업무지구까지 소요시간 계산 후 complex_transit_time 적재."""
    coords = pd.read_sql_query("SELECT ckey, lat, lon FROM complex_coords WHERE lat IS NOT NULL", conn)
    stations = pd.read_sql_query("SELECT station_id, station_name, lat, lon FROM station_node", conn)
    edges = pd.read_sql_query("SELECT from_id, to_id, minutes FROM station_edge", conn)

    adj = {}
    for r in edges.itertuples():
        adj.setdefault(r.from_id, []).append((r.to_id, r.minutes))

    target_ids = {}
    for dest, station_name in TARGET_STATIONS.items():
        matches = stations[stations["station_name"] == station_name]
        if matches.empty:
            print(f"[경고] 목적지 역 '{station_name}'({dest}) 이 station_node에 없어 건너뜁니다.")
            continue
        target_ids[dest] = matches.iloc[0]["station_id"]

    coords["nearest_id"] = coords.apply(
        lambda r: nearest_station(r["lat"], r["lon"], stations), axis=1)

    # 동일 최근접역을 공유하는 단지가 많으므로 역 단위로 한 번만 다익스트라 실행
    cache = {}
    now = pd.Timestamp.utcnow().isoformat()
    rows = []
    for start_id in coords["nearest_id"].unique():
        if start_id not in cache:
            cache[start_id] = shortest_minutes(adj, start_id, set(target_ids.values()))
        result = cache[start_id]
        id_to_dest = {v: k for k, v in target_ids.items()}
        for target_id, minutes in result.items():
            dest = id_to_dest[target_id]
            for ckey in coords.loc[coords["nearest_id"] == start_id, "ckey"]:
                nearest_name = stations.loc[stations["station_id"] == start_id, "station_name"].iloc[0]
                rows.append((ckey, dest, minutes, nearest_name, now))

    conn.execute("DELETE FROM complex_transit_time")
    conn.executemany(
        "INSERT INTO complex_transit_time (ckey, dest, minutes, nearest_station, calculated_at) "
        "VALUES (?,?,?,?,?)", rows)
    conn.commit()
    print(f"완료: {coords['ckey'].nunique()}개 단지 x {len(target_ids)}개 목적지 = {len(rows)}행")
```

`main()` 함수 끝(`conn.close()` 직전)에 추가:
```python
    compute_transit_times(conn)
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `python -m pytest tests/test_transit.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: 커밋**

```bash
git add ingest/fetch_transit.py tests/test_transit.py
git commit -m "feat: 최근접역 매칭 + 단지-업무지구 소요시간 배치 계산"
```

- [ ] **Step 6: 전체 배치 재실행 (소요시간 계산 포함)**

Run: `python ingest/fetch_transit.py`
Expected: Task 3 Step 7과 동일 출력 + "완료: N개 단지 x 5개 목적지 = M행" 추가 출력.

---

## Task 5: 단지 상세 탭(tab2)에 소요시간 반영

**Files:**
- Modify: `app.py` (tab2 블록, `C:\Users\yjkim\Desktop\Claude_project\Quant_realestate\app.py:429-497`)

**Interfaces:**
- Consumes: `complex_transit_time` 테이블 (`ckey, dest, minutes, nearest_station`)

- [ ] **Step 1: `app.py`에 로더 함수 추가**

`app.py`의 `load_assets()` 함수 정의 뒤(약 270번째 줄, `with tabA:` 앞)에 추가:
```python
@st.cache_data(ttl=3600, show_spinner=False)
def load_transit_times():
    import sqlite3
    from scoring.engine import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    t = pd.read_sql_query(
        "SELECT ckey, dest, minutes, nearest_station FROM complex_transit_time", conn)
    conn.close()
    return t


TRANSIT_DEST_ORDER = ["강남", "종로", "여의도", "판교", "동탄"]
```

- [ ] **Step 2: tab2에 소요시간 블록 추가**

`app.py:451`(`m4.metric("12M 모멘텀", ...)` 다음 줄) 뒤에 추가:
```python
            transit = load_transit_times()
            cx_transit = transit[transit["ckey"] == ckey]
            if not cx_transit.empty:
                st.markdown("###### 🚇 업무지구별 소요시간 (역 기반 근사)")
                cols = st.columns(len(TRANSIT_DEST_ORDER))
                for col, dest in zip(cols, TRANSIT_DEST_ORDER):
                    row = cx_transit[cx_transit["dest"] == dest]
                    if row.empty:
                        col.metric(dest, "—")
                    else:
                        col.metric(dest, f"{row.iloc[0]['minutes']:.0f}분")
                st.caption(f"최근접역: {cx_transit.iloc[0]['nearest_station']} · "
                          "오차 ±5~10분 수준 근사치(순위 비교용)")
```

- [ ] **Step 3: 수동 확인 (Streamlit UI)**

Run: `streamlit run app.py` (또는 `run_app.bat`), 브라우저에서 `http://localhost:8502` 접속 →
"🏢 단지 상세" 탭 → 아무 단지 선택 → "🚇 업무지구별 소요시간" 블록이 5개 metric으로 표시되는지 확인.
Task 4까지 완료되지 않았으면(데이터 없음) 빈 화면 대신 아무 것도 렌더링되지 않아야 함(`if not
cx_transit.empty` 가드) — 에러 없이 넘어가는지 확인.

- [ ] **Step 4: 커밋**

```bash
git add app.py
git commit -m "feat: 단지 상세 탭에 업무지구별 소요시간 표시"
```

---

## Task 6: 신규 교통 탭 (🚇)

**Files:**
- Modify: `app.py` (탭 정의 + 신규 탭 블록)

**Interfaces:**
- Consumes: `load_transit_times()`(Task 5), `complex_coords`, `TRANSIT_DEST_ORDER`(Task 5)

- [ ] **Step 1: 탭 정의에 교통 탭 추가**

`app.py:100-101`:
```python
tab0, tabT, tabA, tab1, tab2, tab3 = st.tabs(
    ["📖 가이드", "⏱️ 매수 타이밍", "🌐 자산 비교", "🔍 저평가 스크리너", "🏢 단지 상세", "🧪 백테스트"])
```
을 다음으로 교체:
```python
tab0, tabT, tabA, tabS, tabTr, tab1, tab2, tab3 = st.tabs(
    ["📖 가이드", "⏱️ 매수 타이밍", "🌐 자산 비교", "🏗️ 공급", "🚇 교통",
     "🔍 저평가 스크리너", "🏢 단지 상세", "🧪 백테스트"])
```

- [ ] **Step 2: 지역별 소요시간 집계 함수 + 탭 블록 추가**

`app.py`의 `with tab1:` 정의(약 355번째 줄) 앞에 추가:
```python
# ---------------------------------------------------------------- TabTr 교통


with tabTr:
    try:
        st.markdown("##### 업무지구별 소요시간 — 역 기반 근사 (오차 ±5~10분)")
        transit = load_transit_times()
        coords = load_complex_coords()
        merged = transit.merge(
            coords[["ckey", "region_code"]], on="ckey", how="left")
        region_map = load_region_map()
        merged["region_name"] = merged["region_code"].map(region_map)

        sel_region = st.selectbox("지역 (시군구)", sorted(region_map.values()), index=None,
                                  placeholder="지역을 선택하세요", key="transit_region")
        if sel_region:
            sub = merged[merged["region_name"] == sel_region]
            agg = (sub.groupby("dest")["minutes"].median()
                      .reindex(TRANSIT_DEST_ORDER).reset_index())
            fig = go.Figure(go.Bar(x=agg["dest"], y=agg["minutes"], marker_color=ACCENT,
                                   text=agg["minutes"].round(0), textposition="outside"))
            fig.update_layout(title=f"{sel_region} 대표 소요시간(중위값, 분)", height=380,
                              margin=dict(t=40, b=0), yaxis_title="분")
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"표본 {sub['ckey'].nunique()}개 단지 기준 중위값")
    except Exception as e:  # noqa: BLE001
        st.error(f"교통 탭 오류: {e}")
        st.exception(e)


```

`app.py` 상단 import 구역(`import streamlit as st` 다음 줄)에 `import yaml` 추가하고, `ROOT` 상수가
없으면 `st.set_page_config` 앞에 `ROOT = Path(__file__).resolve().parent` 추가.

`load_transit_times()` 정의 뒤(Task 5 Step 1)에 추가:
```python
@st.cache_data(ttl=3600, show_spinner=False)
def load_complex_coords():
    import sqlite3
    from scoring.engine import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    c = pd.read_sql_query("SELECT ckey, region_code, lat, lon FROM complex_coords", conn)
    conn.close()
    return c


@st.cache_data(ttl=3600, show_spinner=False)
def load_region_map():
    """region_code -> region_name. tabTr·tabS가 공유(Task 9에서 재사용)."""
    cfg = yaml.safe_load(open(ROOT / "config" / "regions.yaml", encoding="utf-8"))
    return {r["code"]: r["name"] for g in cfg.values() for r in g}
```

- [ ] **Step 3: 수동 확인**

Run: `streamlit run app.py` → "🚇 교통" 탭 → 지역 선택 → 5개 목적지 막대그래프 표시 확인.

- [ ] **Step 4: 커밋**

```bash
git add app.py
git commit -m "feat: 지역별 업무지구 소요시간 신규 탭 추가"
```

---

## Task 7: 정비사업 수동 큐레이션 (`config/manual_catalysts.yaml` — redevelopment 섹션)

**Files:**
- Create: `config/manual_catalysts.yaml`
- Create: `scoring/market_context.py`
- Test: `tests/test_market_context.py`

**Interfaces:**
- Produces: `load_redevelopment() -> pd.DataFrame` (columns: region_code, complex_name, stage,
  expected_units, expected_year) — Task 9(공급 집계)가 이 함수를 소비한다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_market_context.py`:
```python
import textwrap

import pandas as pd

from scoring.market_context import load_redevelopment


def test_load_redevelopment_parses_yaml(tmp_path, monkeypatch):
    yaml_path = tmp_path / "manual_catalysts.yaml"
    yaml_path.write_text(textwrap.dedent("""
        redevelopment:
          - region_code: "11680"
            complex_name: "테스트 재건축"
            stage: "관리처분"
            expected_units: 1500
            expected_year: 2028
        transit_planned: []
    """), encoding="utf-8")
    monkeypatch.setattr("scoring.market_context.MANUAL_CATALYSTS_YAML", yaml_path)

    df = load_redevelopment()
    assert len(df) == 1
    assert df.iloc[0]["region_code"] == "11680"
    assert df.iloc[0]["expected_units"] == 1500


def test_load_redevelopment_empty_when_section_missing(tmp_path, monkeypatch):
    yaml_path = tmp_path / "manual_catalysts.yaml"
    yaml_path.write_text("transit_planned: []\n", encoding="utf-8")
    monkeypatch.setattr("scoring.market_context.MANUAL_CATALYSTS_YAML", yaml_path)

    df = load_redevelopment()
    assert df.empty
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python -m pytest tests/test_market_context.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'scoring.market_context'`)

- [ ] **Step 3: 구현**

`config/manual_catalysts.yaml`:
```yaml
# 자동 API가 없는 정비사업(재개발/재건축)·예정 교통노선 수동 큐레이션
# market_context_spec_v1.md §2.1, §3.4 — 기준: 1천 세대 이상 대단지만 등록
#
# 사업단계: 조합설립 | 사업시행 | 관리처분 | 이주철거 | 착공 | 준공
redevelopment:
  []

# 노선단계: 착공 | 공사중 | 준공예정
transit_planned:
  []
```

`scoring/market_context.py`:
```python
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
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `python -m pytest tests/test_market_context.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add config/manual_catalysts.yaml scoring/market_context.py tests/test_market_context.py
git commit -m "feat: 정비사업 수동 큐레이션 YAML + 로더"
```

- [ ] **Step 6: 사용자 큐레이션 (선택, 수동 데이터 입력)**

`config/manual_catalysts.yaml`의 `redevelopment:` 리스트에 실제 1천 세대 이상 정비사업 단지를
사용자가 직접 채워넣는다(서울 정보몽땅 등 참고). 이 스텝은 코드 작업이 아니므로 이 플랜의
실행자가 대신 채우지 않는다 — 빈 리스트로 두어도 이후 태스크는 정상 동작(합계 0으로 집계).

---

## Task 8: 청약홈 분양정보 적재 (`ingest/fetch_supply.py`)

사용자 액션 필요: data.go.kr에서 "한국부동산원_청약홈 분양정보 조회 서비스" 활용신청 후 인증키를
`config/api_keys.local.yaml`의 `apply_home.api_key`에 채워야 Step 6(스모크테스트) 진행 가능.

**Files:**
- Create: `ingest/fetch_supply.py`
- Test: `tests/test_supply.py`

**Interfaces:**
- Consumes: `config/regions.yaml` (지역 코드 목록, `fetch_trades.py`의 `load_regions` 재사용)
- Produces: `supply_presale` 테이블(Task 1 스키마) 완전 채움

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_supply.py`:
```python
from ingest.fetch_supply import normalize_presale_rows, COLUMN_MAP

RAW_SAMPLE = [
    {"HOUSE_NM": "테스트아파트", "RCRIT_PBLANC_DE": "20261201", "TOT_SUPLY_HSHLDCO": "850",
     "SUBSCRPT_AREA_CODE_NM": "서울"},
]


def test_normalize_presale_rows_maps_known_columns():
    df = normalize_presale_rows(RAW_SAMPLE)
    assert list(df.columns) == ["project_name", "expected_ym", "total_units", "region_hint"]
    assert df.iloc[0]["project_name"] == "테스트아파트"
    assert df.iloc[0]["expected_ym"] == "202612"
    assert df.iloc[0]["total_units"] == 850


def test_column_map_has_expected_keys():
    assert set(COLUMN_MAP) == {"project_name", "expected_ym", "total_units", "region_hint"}
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python -m pytest tests/test_supply.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'ingest.fetch_supply'`)

- [ ] **Step 3: 구현**

`ingest/fetch_supply.py`:
```python
"""청약홈 분양 예정분 적재 — 한국부동산원_청약홈 분양정보 조회 서비스
(data.go.kr/data/15098547). 지역 매칭은 API가 반환하는 지역명을 regions.yaml의
시군구명과 문자열 매칭한다(완전 일치 아니면 스킵 — 매칭 실패 건수를 로그로 남긴다).

원본 필드명은 COLUMN_MAP 하나로만 반영된다 — 실제 응답이 다르면 이 값만 수정.
최초 실행 전 `python ingest/fetch_supply.py --smoke-test` 로 원본 응답을 확인할 것.

사용법:
    python ingest/fetch_supply.py --smoke-test
    python ingest/fetch_supply.py
"""
import sys
from pathlib import Path

import pandas as pd
import requests
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_connection  # noqa: E402
from fetch_trades import load_regions  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
API_KEYS_YAML = ROOT / "config" / "api_keys.local.yaml"
REGIONS_YAML = ROOT / "config" / "regions.yaml"

APPLY_HOME_URL = "http://apis.data.go.kr/1613000/AptLttotPblancInfoService/getAPTLttotPblancDetail"

# 원본 API 필드명 → 표준 컬럼명. 실제 응답이 다르면 이 값만 수정.
COLUMN_MAP = {
    "project_name": "HOUSE_NM",
    "expected_ym": "RCRIT_PBLANC_DE",   # YYYYMMDD -> YYYYMM으로 변환
    "total_units": "TOT_SUPLY_HSHLDCO",
    "region_hint": "SUBSCRPT_AREA_CODE_NM",
}


def load_apply_home_key():
    with open(API_KEYS_YAML, encoding="utf-8") as f:
        keys = yaml.safe_load(f) or {}
    key = (keys.get("apply_home") or {}).get("api_key", "")
    if not key:
        raise ValueError("api_keys.local.yaml 의 apply_home.api_key 가 비어있습니다.")
    return key


def normalize_presale_rows(raw):
    df = pd.DataFrame(raw)
    out = pd.DataFrame({std: df[orig] for std, orig in COLUMN_MAP.items()})
    out["expected_ym"] = out["expected_ym"].astype(str).str[:6]
    out["total_units"] = pd.to_numeric(out["total_units"], errors="coerce")
    return out.dropna(subset=["project_name", "expected_ym", "total_units"])


def fetch_raw_presale(api_key, num_of_rows=1000):
    rows, page = [], 1
    while True:
        r = requests.get(APPLY_HOME_URL, params={
            "serviceKey": api_key, "_type": "json",
            "numOfRows": num_of_rows, "page": page,
        }, timeout=30)
        r.raise_for_status()
        body = r.json()["response"]["body"]
        items = body.get("items") or []
        if not items:
            break
        rows.extend(items)
        if len(rows) >= int(body.get("totalCount", 0)):
            break
        page += 1
    return rows


def match_region_code(region_hint, region_rows):
    for r in region_rows:
        if r["name"][:2] in str(region_hint) or str(region_hint) in r["name"]:
            return r["code"]
    return None


def main():
    import argparse
    ap = argparse.ArgumentParser(description="청약홈 분양 예정분 적재")
    ap.add_argument("--smoke-test", action="store_true")
    args = ap.parse_args()

    api_key = load_apply_home_key()
    if args.smoke_test:
        r = requests.get(APPLY_HOME_URL, params={
            "serviceKey": api_key, "_type": "json", "numOfRows": 5, "page": 1,
        }, timeout=30)
        print(r.text[:2000])
        return

    raw = fetch_raw_presale(api_key)
    df = normalize_presale_rows(raw)

    all_regions = load_regions("all")
    df["region_code"] = df["region_hint"].apply(lambda h: match_region_code(h, all_regions))
    matched = df.dropna(subset=["region_code"])
    unmatched_n = len(df) - len(matched)

    conn = get_connection()
    now = pd.Timestamp.utcnow().isoformat()
    rows = [(r.region_code, r.expected_ym, r.project_name, int(r.total_units), "apply_home", now)
            for r in matched.itertuples()]
    conn.executemany(
        "INSERT OR REPLACE INTO supply_presale "
        "(region_code, expected_ym, project_name, total_units, source, fetched_at) "
        "VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    print(f"완료: {len(rows)}건 적재 / 지역 매칭 실패 {unmatched_n}건")
    conn.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `python -m pytest tests/test_supply.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: 커밋**

```bash
git add ingest/fetch_supply.py tests/test_supply.py
git commit -m "feat: 청약홈 분양정보 파싱/지역매칭 함수 + 테스트"
```

- [ ] **Step 6: 사용자 액션 대기 — 청약홈 API 키 발급 후 스모크테스트**

data.go.kr에서 "한국부동산원_청약홈 분양정보 조회 서비스" 활용신청 완료 후 `apply_home.api_key`에
키를 채워달라고 사용자에게 요청. 키 확보 후:

Run: `python ingest/fetch_supply.py --smoke-test`
Expected: JSON 응답 출력. `COLUMN_MAP`의 4개 필드명이 실제 응답과 일치하는지 확인, 다르면 수정.

- [ ] **Step 7: 전체 배치 실행**

Run: `python ingest/fetch_supply.py`
Expected: "완료: N건 적재 / 지역 매칭 실패 M건" — M이 크면(예: 전체의 30% 이상) `match_region_code`의
매칭 로직을 실제 `region_hint` 값 형태에 맞게 조정 후 재실행.

---

## Task 9: 공급 집계 함수 + 신규 공급 탭 (🏗️)

**Files:**
- Modify: `scoring/market_context.py` (집계 함수 추가)
- Modify: `tests/test_market_context.py` (집계 함수 테스트 추가)
- Modify: `app.py` (tabS 블록)

**Interfaces:**
- Consumes: `supply_presale` 테이블(Task 8), `load_redevelopment()`(Task 7), `load_region_map()`(Task 6)
- Produces: `load_supply_by_region_year(conn) -> pd.DataFrame` (columns: region_code, year, presale_units,
  redevelopment_units) — tabS가 이 함수 하나만 호출한다.

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_market_context.py`에 추가:
```python
import sqlite3

from scoring.market_context import load_supply_by_region_year


def test_load_supply_by_region_year_combines_presale_and_redevelopment(tmp_path, monkeypatch):
    yaml_path = tmp_path / "manual_catalysts.yaml"
    yaml_path.write_text(textwrap.dedent("""
        redevelopment:
          - region_code: "11680"
            complex_name: "테스트 재건축"
            stage: "착공"
            expected_units: 500
            expected_year: 2027
        transit_planned: []
    """), encoding="utf-8")
    monkeypatch.setattr("scoring.market_context.MANUAL_CATALYSTS_YAML", yaml_path)

    conn = sqlite3.connect(tmp_path / "test.db")
    conn.execute("""
        CREATE TABLE supply_presale (
            region_code TEXT, expected_ym TEXT, project_name TEXT,
            total_units INTEGER, source TEXT, fetched_at TEXT
        )
    """)
    conn.execute(
        "INSERT INTO supply_presale VALUES ('11680', '202703', 'A단지', 300, 'apply_home', '')")
    conn.commit()

    out = load_supply_by_region_year(conn)
    row = out[(out["region_code"] == "11680") & (out["year"] == 2027)].iloc[0]
    assert row["presale_units"] == 300
    assert row["redevelopment_units"] == 500
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python -m pytest tests/test_market_context.py -v`
Expected: FAIL (`ImportError: cannot import name 'load_supply_by_region_year'`)

- [ ] **Step 3: 구현**

`scoring/market_context.py`에 추가:
```python
def load_supply_by_region_year(conn):
    presale = pd.read_sql_query(
        "SELECT region_code, expected_ym, total_units FROM supply_presale", conn)
    presale["year"] = presale["expected_ym"].str[:4].astype(int)
    presale_agg = (presale.groupby(["region_code", "year"])["total_units"].sum()
                          .rename("presale_units").reset_index())

    redev = load_redevelopment()
    if redev.empty:
        redev_agg = pd.DataFrame(columns=["region_code", "year", "redevelopment_units"])
    else:
        redev_agg = (redev.groupby(["region_code", "expected_year"])["expected_units"].sum()
                          .rename("redevelopment_units")
                          .reset_index().rename(columns={"expected_year": "year"}))

    out = pd.merge(presale_agg, redev_agg, on=["region_code", "year"], how="outer")
    out[["presale_units", "redevelopment_units"]] = out[["presale_units", "redevelopment_units"]].fillna(0)
    return out.sort_values(["region_code", "year"]).reset_index(drop=True)
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `python -m pytest tests/test_market_context.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: tabS 블록 추가**

`app.py`의 `with tabTr:` 블록(Task 6) 앞에 추가:
```python
# ---------------------------------------------------------------- TabS 공급


@st.cache_data(ttl=3600, show_spinner=False)
def load_supply():
    import sqlite3
    from scoring.engine import DB_PATH
    from scoring.market_context import load_supply_by_region_year
    conn = sqlite3.connect(DB_PATH)
    out = load_supply_by_region_year(conn)
    conn.close()
    return out


with tabS:
    try:
        st.markdown("##### 향후 입주 예정 물량 — 분양(자동) + 정비사업(수동 큐레이션)")
        supply = load_supply()
        region_map = load_region_map()  # Task 6에서 정의(tabTr와 공유)
        supply["region_name"] = supply["region_code"].map(region_map)

        sel_region = st.selectbox("지역 (시군구)", sorted(region_map.values()), index=None,
                                  placeholder="지역을 선택하세요", key="supply_region")
        if sel_region:
            sub = supply[supply["region_name"] == sel_region].sort_values("year")
            fig = go.Figure()
            fig.add_trace(go.Bar(x=sub["year"], y=sub["presale_units"], name="분양(자동)",
                                 marker_color=ACCENT))
            fig.add_trace(go.Bar(x=sub["year"], y=sub["redevelopment_units"], name="정비사업(수동)",
                                 marker_color="#f0b429"))
            fig.update_layout(barmode="stack", title=f"{sel_region} 연도별 입주 예정 물량",
                              height=380, margin=dict(t=40, b=0), yaxis_title="세대수")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(sub[["year", "presale_units", "redevelopment_units"]],
                        hide_index=True, use_container_width=True)
        st.caption("정비사업은 1천 세대 이상 대단지만 수동 등록됨(config/manual_catalysts.yaml) — "
                  "누락된 사업이 있을 수 있음.")
    except Exception as e:  # noqa: BLE001
        st.error(f"공급 탭 오류: {e}")
        st.exception(e)


```

- [ ] **Step 6: 수동 확인**

Run: `streamlit run app.py` → "🏗️ 공급" 탭 → 지역 선택 → 스택 막대그래프 표시 확인(Task 8 데이터
없으면 0으로 표시되어도 에러 없이 렌더링되는지 확인).

- [ ] **Step 7: 커밋**

```bash
git add scoring/market_context.py tests/test_market_context.py app.py
git commit -m "feat: 공급 물량 집계(분양+정비사업) + 신규 공급 탭"
```

---

## Task 10: 예정 노선(착공/준공) 큐레이션 + 교통 탭 배지

**Files:**
- Modify: `config/manual_catalysts.yaml` (예시 항목 없음, 스키마만 — Task 7에서 이미 빈 리스트 존재)
- Modify: `scoring/market_context.py` (로더 추가)
- Modify: `tests/test_market_context.py`
- Modify: `app.py` (tabTr에 배지 추가)

**Interfaces:**
- Consumes: `config/manual_catalysts.yaml`의 `transit_planned`
- Produces: `load_planned_transit() -> pd.DataFrame` (columns: line_name, stations, stage, expected_open_year)

- [ ] **Step 1: 실패하는 테스트 추가**

`tests/test_market_context.py`에 추가:
```python
from scoring.market_context import load_planned_transit


def test_load_planned_transit_parses_yaml(tmp_path, monkeypatch):
    yaml_path = tmp_path / "manual_catalysts.yaml"
    yaml_path.write_text(textwrap.dedent("""
        redevelopment: []
        transit_planned:
          - line_name: "GTX-A"
            stations: ["동탄", "판교"]
            stage: "공사중"
            expected_open_year: 2026
    """), encoding="utf-8")
    monkeypatch.setattr("scoring.market_context.MANUAL_CATALYSTS_YAML", yaml_path)

    df = load_planned_transit()
    assert len(df) == 1
    assert df.iloc[0]["line_name"] == "GTX-A"
    assert "동탄" in df.iloc[0]["stations"]
```

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python -m pytest tests/test_market_context.py -v`
Expected: FAIL (`ImportError: cannot import name 'load_planned_transit'`)

- [ ] **Step 3: 구현**

`scoring/market_context.py`에 추가:
```python
def load_planned_transit():
    rows = _load_yaml().get("transit_planned") or []
    if not rows:
        return pd.DataFrame(columns=["line_name", "stations", "stage", "expected_open_year"])
    return pd.DataFrame(rows)
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `python -m pytest tests/test_market_context.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: tabTr에 배지 블록 추가**

`app.py`의 `with tabTr:` 블록 끝(`st.caption(...)` 다음, `except` 앞)에 추가:
```python
        from scoring.market_context import load_planned_transit
        planned = load_planned_transit()
        if not planned.empty:
            st.markdown("###### 🚧 예정 노선 (착공/준공, 현재 소요시간 계산에는 미반영)")
            for row in planned.itertuples():
                years_left = row.expected_open_year - pd.Timestamp.now().year
                badge = "🔜 3년 이내" if years_left <= 3 else "🕐 3년 이상"
                st.markdown(f"- **{row.line_name}** ({row.stage}) — {', '.join(row.stations)} · "
                           f"예정 {row.expected_open_year}년 {badge}")
```

Task 9의 `load_supply()`와 동일하게 함수 내부 지역 import 패턴을 따른다(app.py 기존 `load_assets()`
관례 — 상단 top-level import로 통일하지 않는다).

- [ ] **Step 6: 수동 확인**

`config/manual_catalysts.yaml`의 `transit_planned`에 테스트용 항목 1개 임시로 추가 →
Run: `streamlit run app.py` → "🚇 교통" 탭 하단에 배지 표시 확인 → 테스트 항목 제거.

- [ ] **Step 7: 커밋**

```bash
git add scoring/market_context.py tests/test_market_context.py app.py
git commit -m "feat: 예정 교통노선 수동 큐레이션 로더 + 교통 탭 배지"
```

---

## Task 11: 자산군 비율 z-score (기존 tabA 확장)

**Files:**
- Modify: `scoring/market_context.py` (z-score 계산 함수 추가)
- Modify: `tests/test_market_context.py`
- Modify: `app.py` (tabA에 metric 카드 추가, `app.py:272` 부근)

**Interfaces:**
- Consumes: `load_assets()`(기존 app.py 함수, `reb_apt_index`/`asset_kospi`/`asset_nasdaq`/`asset_gold`/`asset_btc` 컬럼)
- Produces: `asset_ratio_zscore(assets: pd.DataFrame) -> dict[str, float]` (asset 컬럼명 → 최신 z-score)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_market_context.py`에 추가:
```python
import numpy as np

from scoring.market_context import asset_ratio_zscore


def test_asset_ratio_zscore_matches_manual_calc():
    idx = pd.period_range("2020-01", periods=24, freq="M")
    rng = np.random.RandomState(0)
    apt = pd.Series(100 + rng.randn(24).cumsum(), index=idx)
    kospi = pd.Series(100 + rng.randn(24).cumsum(), index=idx)
    assets = pd.DataFrame({"reb_apt_index": apt, "asset_kospi": kospi})

    result = asset_ratio_zscore(assets)

    ratio = apt / kospi
    expected = (ratio.iloc[-1] - ratio.mean()) / ratio.std()
    assert result["asset_kospi"] == pytest.approx(expected)


def test_asset_ratio_zscore_skips_missing_columns():
    idx = pd.period_range("2020-01", periods=12, freq="M")
    assets = pd.DataFrame({"reb_apt_index": pd.Series(range(12), index=idx, dtype=float)})
    result = asset_ratio_zscore(assets)
    assert result == {}
```

`tests/test_market_context.py` 상단 import에 `import pytest` 추가.

- [ ] **Step 2: 테스트 실행 → 실패 확인**

Run: `python -m pytest tests/test_market_context.py -v`
Expected: FAIL (`ImportError: cannot import name 'asset_ratio_zscore'`)

- [ ] **Step 3: 구현**

`scoring/market_context.py`에 추가:
```python
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
```

- [ ] **Step 4: 테스트 실행 → 통과 확인**

Run: `python -m pytest tests/test_market_context.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: tabA에 z-score 카드 추가**

`app.py:274`(`assets = load_assets()` 다음 줄) 뒤에 추가:
```python
        from scoring.market_context import asset_ratio_zscore
        zscores = asset_ratio_zscore(assets)
        if zscores:
            st.markdown("###### 저평가 정도 (비율 z-score, 2003~ 전체 역사 기준)")
            cols = st.columns(len(zscores))
            for col, (asset_col, z) in zip(cols, zscores.items()):
                label = ASSET_LABELS.get(asset_col, asset_col)
                col.metric(f"🏠/{label}", f"{z:+.2f}σ",
                          help="음수 = 부동산이 해당 자산 대비 역사적으로 저평가")
```

- [ ] **Step 6: 수동 확인**

Run: `streamlit run app.py` → "🌐 자산 비교" 탭 → 상단에 4개 z-score metric 카드 표시 확인, 기존
리베이스 차트/수익률표/모멘텀 순위가 그대로 남아있는지 확인(회귀 없음).

- [ ] **Step 7: 커밋**

```bash
git add scoring/market_context.py tests/test_market_context.py app.py
git commit -m "feat: 자산군 비율 z-score 카드 추가 (tabA 확장)"
```

---

## 전체 완료 후 확인

- [ ] **Step 1: 전체 테스트 스위트 실행**

Run: `cd Quant_realestate && python -m pytest tests/ -v`
Expected: 전체 PASS (Task 1~11 누적 약 25개 테스트)

- [ ] **Step 2: 앱 전체 수동 회귀 확인**

Run: `streamlit run app.py`, 8개 탭(가이드/매수타이밍/자산비교/공급/교통/스크리너/단지상세/백테스트)
전부 에러 없이 렌더링되는지 순서대로 클릭 확인. 특히 기존 탭(스크리너·백테스트)이 신규 탭 추가로
회귀하지 않았는지 확인.

- [ ] **Step 3: 문서 갱신**

`docs/market_context_spec_v1.md` 상단에 구현 완료 날짜와 실측 특이사항(있다면 COLUMN_MAP 실제 조정
내역 등)을 한 줄 추가 — `docs/algo_spec_v1.md`/`docs/regime_spec_v1.md` 관례대로.
