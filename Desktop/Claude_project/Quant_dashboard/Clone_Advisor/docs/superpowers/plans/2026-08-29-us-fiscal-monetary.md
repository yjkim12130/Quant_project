# Family E — 미국 재정·통화 모니터 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 미국의 기업 신용 스프레드·통화량·연방 재정·정책금리 14개 지표를 수집·해석해 Streamlit 신규 탭과 정적 HTML 리포트로 보여준다.

**Architecture:** 기존 Family A/B와 동일한 3단 구조 — `advisor_macro.py`(원본 수집) → `advisor_dashboard_us.py`(파생 계산·룰 판정) → 렌더러 2종(Streamlit tab4, `render_html_us()`). 지표 목록은 `macro_series.json` 레지스트리로 빼서 코드 수정 없이 추가할 수 있게 한다. LLM은 쓰지 않고 룰 템플릿으로만 문장을 만든다.

**Tech Stack:** Python 3, requests, pandas, streamlit, plotly, pytest 7.4.4

**Spec:** `docs/superpowers/specs/2026-08-29-us-fiscal-monetary-design.md`

## Global Constraints

- **LLM 미사용.** 모든 서술 문장은 룰 템플릿으로 조립한다(Family A/B 원칙).
- **에러 격리.** 지표 하나의 실패가 그룹을, 그룹 하나의 실패가 탭을 무너뜨리면 안 된다. 모든 실패는 `_status` 문자열로 표현하고 예외를 밖으로 던지지 않는다.
- **`_status` 값**: `"ok"` | `"NO_FRED_KEY"` | `"NO_DATA"` | `"NO_REGISTRY"`.
- **단위 정규화 필수.** `WALCL`/`WRESBAL`/`WTREGEN`은 `$M`, `RRPONTSYD`는 `$B`다. 금액을 조합하는 계산은 반드시 `$M`으로 맞춘 뒤 수행한다. (스펙 §5 — 이 오류로 순유동성이 1000배 틀어질 뻔했다.)
- **FRED 시리즈 13종은 2026-08-29 전수 검증 완료(13/13).** 시리즈 ID를 임의로 바꾸지 말 것.
- **키 취급.** 키를 로그·커밋·에러 메시지에 절대 출력하지 않는다. `.fred_api_key`는 `.gitignore`에 이미 등록됨.
- **테스트 규약.** 순수 계산 함수는 `tests/`에 pytest로 테스트한다(네트워크 금지, 고정 입력만). 네트워크 함수는 라이브 호출로 검증한다.
- **한글 주석.** 기존 모듈과 동일하게 docstring·주석은 한국어로 쓴다.
- **Windows 콘솔 주의.** 검증 스크립트 실행 시 `PYTHONIOENCODING=utf-8`을 붙인다(cp949가 `—`·이모지에서 깨진다).

---

## File Structure

| 파일 | 책임 |
|---|---|
| `advisor_macro.py` (신규) | 원본 수집만. FRED 클라이언트 + 재무부 클라이언트 + 키 로더. 계산·해석 없음. |
| `macro_series.json` (신규) | 지표 레지스트리. 그룹·시리즈 ID·단위·해석 방향. |
| `advisor_dashboard_us.py` (신규) | 단위 정규화, 백분위, 변화량, 파생 계산, 룰 판정, 오케스트레이션. |
| `tests/test_dashboard_us.py` (신규) | 순수 계산 함수 pytest. 네트워크 없음. |
| `advisor_app.py` (수정) | tab4 추가. `with tab2:` 옆(= `with tab1:` 앞). |
| `advisor_report.py` (수정) | `render_html_us()` 추가. |

---

## Task 1: 데이터 레이어 — 키 로더와 FRED 클라이언트

**Files:**
- Create: `advisor_macro.py`
- Test: 라이브 호출 검증(네트워크 필수라 pytest 대상 아님)

**Interfaces:**
- Consumes: 없음
- Produces:
  - `get_fred_key() -> Optional[str]`
  - `fetch_fred_series(series_id: str, api_key: str, years: int = 3) -> dict`
    → `{"_status": "ok"|"NO_DATA", "series_id": str, "observations": [{"date": str, "value": float}], "_msg": str}`

- [ ] **Step 1: `advisor_macro.py` 생성 — 키 로더까지**

`advisor_data.get_dart_key()`(advisor_data.py:54)를 그대로 복제한다. 경로만 `.fred_api_key`로 바꾼다.

```python
"""
advisor_macro.py — 미국 재정·통화 데이터 레이어 (Family E)
═══════════════════════════════════════════════════════════════════════
FRED(세인트루이스 연은)와 미 재무부 FiscalData에서 거시 시계열 원본만
수집한다. 파생 계산·해석은 advisor_dashboard_us.py의 몫 —
advisor_news.py와 동일한 설계 원칙(의존성 최소화, graceful degradation).

FRED는 무료 API 키가 필요하다:
    1) 환경변수 : setx FRED_API_KEY "발급키"
    2) 키 파일  : .fred_api_key 파일에 키 한 줄 저장
키가 없어도 재무부 지표는 정상 동작한다(스펙 §4).
"""
from __future__ import annotations
import os
from datetime import date, timedelta
from typing import Optional

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
_HEADERS = {"User-Agent": "Mozilla/5.0"}

_FRED_BASE = "https://api.stlouisfed.org/fred"
_TREASURY_BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"


def get_fred_key() -> Optional[str]:
    """환경변수 FRED_API_KEY 또는 .fred_api_key 파일에서 키를 읽는다."""
    key = os.environ.get("FRED_API_KEY")
    if key:
        return key.strip()
    path = os.path.join(_HERE, ".fred_api_key")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    return None
```

- [ ] **Step 2: `fetch_fred_series()` 추가**

FRED는 결측을 `"."` 문자열로 준다 — 반드시 걸러야 `float()`에서 터진다.

```python
def fetch_fred_series(series_id: str, api_key: str, years: int = 3) -> dict:
    """FRED 시리즈 1종의 최근 years년 관측치를 날짜 오름차순으로 반환.

    FRED는 결측을 "." 문자열로 주므로 숫자 변환 전에 걸러낸다.
    관측 주기(일/주/월/분기)는 시리즈마다 다르며 여기선 손대지 않는다.
    """
    start = (date.today() - timedelta(days=365 * years)).isoformat()
    try:
        r = requests.get(
            f"{_FRED_BASE}/series/observations",
            params={"series_id": series_id, "api_key": api_key,
                    "file_type": "json", "observation_start": start},
            headers=_HEADERS, timeout=20)
        if r.status_code != 200:
            return {"_status": "NO_DATA", "series_id": series_id,
                    "observations": [], "_msg": f"HTTP {r.status_code}"}
        obs = []
        for o in r.json().get("observations", []):
            raw = o.get("value")
            if raw in (".", None, ""):
                continue
            try:
                obs.append({"date": o["date"], "value": float(raw)})
            except (ValueError, KeyError):
                continue
        if not obs:
            return {"_status": "NO_DATA", "series_id": series_id,
                    "observations": [], "_msg": "관측치 0건"}
        return {"_status": "ok", "series_id": series_id, "observations": obs, "_msg": ""}
    except Exception as e:
        # 키가 예외 메시지에 섞여 나가지 않도록 타입명만 남긴다.
        return {"_status": "NO_DATA", "series_id": series_id,
                "observations": [], "_msg": type(e).__name__}
```

- [ ] **Step 3: 라이브 검증 — 시리즈 3종**

Run:
```bash
cd Clone_Advisor && PYTHONIOENCODING=utf-8 python -c "
import advisor_macro as am
k = am.get_fred_key()
print('키 로드:', '성공' if k else '실패')
for sid in ['BAMLH0A0HYM2', 'M2SL', 'WALCL']:
    r = am.fetch_fred_series(sid, k)
    print(sid, r['_status'], len(r['observations']), r['observations'][-1] if r['observations'] else '')
"
```
Expected: 키 로드 성공, 3종 모두 `ok`, 관측치 각각 700+/36/157건 내외.

- [ ] **Step 4: 실패 경로 검증**

Run:
```bash
cd Clone_Advisor && PYTHONIOENCODING=utf-8 python -c "
import advisor_macro as am
print(am.fetch_fred_series('NOSUCHSERIES', am.get_fred_key()))
print(am.fetch_fred_series('M2SL', 'badkey')['_status'])
"
```
Expected: 둘 다 `_status='NO_DATA'`, 예외 없이 dict 반환, `_msg`에 키 문자열이 없을 것.

- [ ] **Step 5: 커밋**

```bash
git add advisor_macro.py
git commit -m "feat(advisor): add FRED client and key loader for Family E"
```

---

## Task 2: 데이터 레이어 — 재무부 부채와 레지스트리 수집

**Files:**
- Create: `macro_series.json`
- Modify: `advisor_macro.py` (append)

**Interfaces:**
- Consumes: `fetch_fred_series()`, `get_fred_key()` (Task 1)
- Produces:
  - `fetch_debt_to_penny(years: int = 3) -> dict`
    → `{"_status", "series_id": "debt_to_penny", "observations": [{"date","value","public","intragov"}], "_msg"}`
    (`value`는 총부채. `build_indicator()`가 공통으로 `value`만 보므로 이름을 맞춘다.)
  - `collect_macro(registry: dict, years: int = 3) -> dict`
    → `{group_id: {indicator_id: <위 fetch 결과 dict>}}`

- [ ] **Step 1: `macro_series.json` 생성**

`unit`은 FRED `units_short` 원문 그대로 적는다(단위 정규화 표와 대조되도록). 사람이 읽을 문자열은 `unit_label`로 분리한다.

```json
{
  "version": "0.1",
  "groups": [
    {
      "id": "credit",
      "label": "기업 신용 스프레드",
      "indicators": [
        {"id": "hy_oas", "label": "하이일드 OAS", "source": "fred",
         "series_id": "BAMLH0A0HYM2", "unit": "%", "unit_label": "%",
         "freq": "일간", "higher_is": "worse"},
        {"id": "ig_oas", "label": "투자등급 OAS", "source": "fred",
         "series_id": "BAMLC0A0CM", "unit": "%", "unit_label": "%",
         "freq": "일간", "higher_is": "worse"}
      ]
    },
    {
      "id": "liquidity",
      "label": "통화량·유동성",
      "indicators": [
        {"id": "m2", "label": "M2 통화량", "source": "fred",
         "series_id": "M2SL", "unit": "Bil. of $", "unit_label": "십억$",
         "freq": "월간", "higher_is": "neutral"},
        {"id": "fed_assets", "label": "연준 총자산", "source": "fred",
         "series_id": "WALCL", "unit": "Mil. of U.S. $", "unit_label": "백만$",
         "freq": "주간", "higher_is": "neutral"},
        {"id": "rrp", "label": "역레포 잔액", "source": "fred",
         "series_id": "RRPONTSYD", "unit": "Bil. of US $", "unit_label": "십억$",
         "freq": "일간", "higher_is": "worse"},
        {"id": "reserves", "label": "지급준비금", "source": "fred",
         "series_id": "WRESBAL", "unit": "Mil. of U.S. $", "unit_label": "백만$",
         "freq": "주간", "higher_is": "better"},
        {"id": "tga", "label": "재무부 일반계정", "source": "fred",
         "series_id": "WTREGEN", "unit": "Mil. of U.S. $", "unit_label": "백만$",
         "freq": "주간", "higher_is": "worse"}
      ]
    },
    {
      "id": "fiscal",
      "label": "연방 재정",
      "indicators": [
        {"id": "debt_total", "label": "연방 총부채", "source": "treasury",
         "series_id": "debt_to_penny", "unit": "$", "unit_label": "달러",
         "freq": "일간", "higher_is": "worse"},
        {"id": "debt_gdp", "label": "부채/GDP", "source": "fred",
         "series_id": "GFDEGDQ188S", "unit": "% of GDP", "unit_label": "% of GDP",
         "freq": "분기", "higher_is": "worse"},
        {"id": "deficit", "label": "월간 재정수지", "source": "fred",
         "series_id": "MTSDS133FMS", "unit": "Mil. of $", "unit_label": "백만$",
         "freq": "월간", "higher_is": "better"},
        {"id": "interest", "label": "연방 이자지급", "source": "fred",
         "series_id": "A091RC1Q027SBEA", "unit": "Bil. of $", "unit_label": "십억$",
         "freq": "분기", "higher_is": "worse"}
      ]
    },
    {
      "id": "rates",
      "label": "정책금리·실질금리",
      "indicators": [
        {"id": "effr", "label": "실효 연방기금금리", "source": "fred",
         "series_id": "DFF", "unit": "%", "unit_label": "%",
         "freq": "일간", "higher_is": "neutral"},
        {"id": "bei5y", "label": "5년 기대인플레이션", "source": "fred",
         "series_id": "T5YIE", "unit": "%", "unit_label": "%",
         "freq": "일간", "higher_is": "neutral"},
        {"id": "real10y", "label": "10년 실질금리", "source": "fred",
         "series_id": "DFII10", "unit": "%", "unit_label": "%",
         "freq": "일간", "higher_is": "neutral"}
      ]
    }
  ]
}
```

- [ ] **Step 2: `fetch_debt_to_penny()` 추가**

재무부는 금액을 문자열로 준다. `fields`로 필요한 열만 받아 응답을 줄인다.

```python
def fetch_debt_to_penny(years: int = 3) -> dict:
    """미 재무부 일간 총부채(debt to the penny). API 키 불필요.

    FRED의 분기 부채 시리즈보다 주기가 촘촘해 이쪽을 쓴다(스펙 §4).
    금액이 문자열로 오므로 float 변환하고, 실패한 행은 건너뛴다.
    """
    start = (date.today() - timedelta(days=365 * years)).isoformat()
    try:
        r = requests.get(
            f"{_TREASURY_BASE}/v2/accounting/od/debt_to_penny",
            params={"filter": f"record_date:gte:{start}",
                    "sort": "record_date",
                    "page[size]": "10000",
                    "fields": "record_date,tot_pub_debt_out_amt,"
                              "debt_held_public_amt,intragov_hold_amt"},
            headers=_HEADERS, timeout=20)
        if r.status_code != 200:
            return {"_status": "NO_DATA", "series_id": "debt_to_penny",
                    "observations": [], "_msg": f"HTTP {r.status_code}"}
        obs = []
        for row in r.json().get("data", []):
            try:
                obs.append({
                    "date": row["record_date"],
                    "value": float(row["tot_pub_debt_out_amt"]),
                    "public": float(row["debt_held_public_amt"]),
                    "intragov": float(row["intragov_hold_amt"]),
                })
            except (ValueError, KeyError, TypeError):
                continue
        if not obs:
            return {"_status": "NO_DATA", "series_id": "debt_to_penny",
                    "observations": [], "_msg": "관측치 0건"}
        return {"_status": "ok", "series_id": "debt_to_penny",
                "observations": obs, "_msg": ""}
    except Exception as e:
        return {"_status": "NO_DATA", "series_id": "debt_to_penny",
                "observations": [], "_msg": type(e).__name__}
```

- [ ] **Step 3: `collect_macro()` 추가**

키가 없을 때 FRED 지표만 접히고 재무부 지표는 살아남는 게 이 함수의 핵심이다.

```python
def collect_macro(registry: dict, years: int = 3) -> dict:
    """레지스트리를 순회하며 그룹별·지표별 원본을 모은다.

    FRED 키가 없으면 source=="fred" 지표는 전부 NO_FRED_KEY로 표시하고
    재무부 지표만 수집한다 — 키 발급 전에도 탭이 뜨게 하기 위함(스펙 §8).
    """
    api_key = get_fred_key()
    out: dict = {}
    for group in registry.get("groups", []):
        gid = group.get("id", "")
        out[gid] = {}
        for meta in group.get("indicators", []):
            iid = meta.get("id", "")
            source = meta.get("source")
            if source == "treasury":
                out[gid][iid] = fetch_debt_to_penny(years=years)
            elif not api_key:
                out[gid][iid] = {"_status": "NO_FRED_KEY",
                                 "series_id": meta.get("series_id", ""),
                                 "observations": [],
                                 "_msg": "FRED API 키 미설정"}
            else:
                out[gid][iid] = fetch_fred_series(
                    meta.get("series_id", ""), api_key, years=years)
    return out
```

- [ ] **Step 4: 라이브 검증 — 재무부 + 전체 수집 14종**

Run:
```bash
cd Clone_Advisor && PYTHONIOENCODING=utf-8 python -c "
import json, advisor_macro as am
d = am.fetch_debt_to_penny()
print('부채:', d['_status'], len(d['observations']), d['observations'][-1])
reg = json.load(open('macro_series.json', encoding='utf-8'))
raw = am.collect_macro(reg)
n_ok = sum(1 for g in raw.values() for r in g.values() if r['_status']=='ok')
for gid, g in raw.items():
    for iid, r in g.items():
        print(f\"  {gid:9s} {iid:11s} {r['_status']:12s} n={len(r['observations'])}\")
print('성공:', n_ok, '/ 14')
"
```
Expected: `성공: 14 / 14`. 부채 최신 관측치의 `value`가 4.0e13 부근($40조).

- [ ] **Step 5: 키 없는 경로 검증**

Run:
```bash
cd Clone_Advisor && mv .fred_api_key .fred_api_key.bak && PYTHONIOENCODING=utf-8 python -c "
import json, advisor_macro as am
raw = am.collect_macro(json.load(open('macro_series.json', encoding='utf-8')))
from collections import Counter
print(Counter(r['_status'] for g in raw.values() for r in g.values()))
print('부채:', raw['fiscal']['debt_total']['_status'])
"; mv .fred_api_key.bak .fred_api_key```
Expected: `Counter({'NO_FRED_KEY': 13, 'ok': 1})`, `부채: ok`. **명령 끝의 `mv`로 키 파일이 반드시 복구되는지 확인할 것.**

- [ ] **Step 6: 커밋**

```bash
git add advisor_macro.py macro_series.json
git commit -m "feat(advisor): add Treasury debt client and macro registry"
```

---

## Task 3: 조립 레이어 — 단위 정규화·백분위·지표 빌더

**Files:**
- Create: `advisor_dashboard_us.py`
- Create: `tests/test_dashboard_us.py`

**Interfaces:**
- Consumes: Task 2의 `collect_macro()` 출력 형태(지표별 `{"_status", "observations": [{"date","value"}]}`)
- Produces:
  - `to_musd(value: Optional[float], unit: str) -> Optional[float]`
  - `pct_rank(values: list[float], current: float) -> Optional[float]`
  - `change_over(obs: list[dict], days: int) -> Optional[float]`
  - `build_indicator(raw: dict, meta: dict) -> dict`
  - `build_group(raw_group: dict, meta_group: dict) -> dict`
  - `load_macro_series() -> Optional[dict]`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_dashboard_us.py`를 만든다. 네트워크를 쓰지 않는 순수 계산만 다룬다.

```python
import advisor_dashboard_us as adu


# ── 단위 정규화 ──────────────────────────────────────────────
def test_to_musd_passes_through_millions():
    assert adu.to_musd(6_730_912.0, "Mil. of U.S. $") == 6_730_912.0


def test_to_musd_scales_billions_to_millions():
    # RRPONTSYD만 $B다 — 이 1000배 환산이 순유동성 정확도를 좌우한다
    assert adu.to_musd(0.17, "Bil. of US $") == 170.0


def test_to_musd_returns_none_for_unknown_unit():
    assert adu.to_musd(1.0, "%") is None
    assert adu.to_musd(None, "Mil. of $") is None


# ── 백분위 ───────────────────────────────────────────────────
def test_pct_rank_at_maximum_is_100():
    assert adu.pct_rank([1.0, 2.0, 3.0, 4.0], 4.0) == 100.0


def test_pct_rank_at_minimum_is_25_for_four_values():
    # 자기 자신을 포함해 <= 인 값의 비율
    assert adu.pct_rank([1.0, 2.0, 3.0, 4.0], 1.0) == 25.0


def test_pct_rank_empty_returns_none():
    assert adu.pct_rank([], 1.0) is None


# ── 기간 변화 (주기 불규칙 대응) ──────────────────────────────
def test_change_over_uses_observation_closest_to_target_date():
    obs = [
        {"date": "2026-01-01", "value": 100.0},
        {"date": "2026-06-01", "value": 150.0},   # 약 90일 전에 가장 가까움
        {"date": "2026-08-29", "value": 200.0},
    ]
    assert adu.change_over(obs, 90) == 50.0


def test_change_over_short_history_returns_none():
    assert adu.change_over([{"date": "2026-08-29", "value": 1.0}], 30) is None


# ── 지표 빌더 ────────────────────────────────────────────────
_META_HY = {"id": "hy_oas", "label": "하이일드 OAS", "unit": "%",
            "unit_label": "%", "freq": "일간", "higher_is": "worse"}


def test_build_indicator_propagates_failure_status():
    out = adu.build_indicator({"_status": "NO_FRED_KEY", "observations": []}, _META_HY)
    assert out["_status"] == "NO_FRED_KEY"
    assert out["latest"] is None
    assert out["label"] == "하이일드 OAS"


def test_build_indicator_computes_latest_and_rank():
    obs = [{"date": f"2026-0{i}-01", "value": float(i)} for i in range(1, 9)]
    out = adu.build_indicator({"_status": "ok", "observations": obs}, _META_HY)
    assert out["_status"] == "ok"
    assert out["latest"] == 8.0
    assert out["latest_date"] == "2026-08-01"
    assert out["pct_rank_3y"] == 100.0


def test_build_indicator_assessment_respects_higher_is_worse():
    obs = [{"date": f"2026-0{i}-01", "value": float(i)} for i in range(1, 9)]
    out = adu.build_indicator({"_status": "ok", "observations": obs}, _META_HY)
    assert "고점" in out["assessment"]


def test_build_indicator_assessment_flips_for_higher_is_better():
    meta = dict(_META_HY, higher_is="better")
    obs = [{"date": f"2026-0{i}-01", "value": float(i)} for i in range(1, 9)]
    out = adu.build_indicator({"_status": "ok", "observations": obs}, meta)
    assert "양호" in out["assessment"]
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `cd Clone_Advisor && python -m pytest tests/test_dashboard_us.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'advisor_dashboard_us'`

- [ ] **Step 3: 최소 구현**

```python
"""
advisor_dashboard_us.py — 미국 재정·통화 모니터 조립 (Family E)
═══════════════════════════════════════════════════════════════════════
advisor_macro.py가 모은 원본 시계열을 지표 카드·파생 계산·룰 판정으로
조립한다. Family A/B와 동일하게 LLM 없이 룰 템플릿만 쓴다.

단위 주의: WALCL/WRESBAL/WTREGEN은 $M인데 RRPONTSYD만 $B다.
금액을 조합하는 계산은 반드시 to_musd()로 맞춘 뒤 수행한다.
"""
from __future__ import annotations
import json
import os
from datetime import date, datetime, timedelta
from typing import Optional

import advisor_macro as am

_HERE = os.path.dirname(os.path.abspath(__file__))
_REGISTRY_PATH = os.path.join(_HERE, "macro_series.json")

# FRED units_short 원문 → $M 배율
_UNIT_TO_MUSD = {
    "Mil. of $": 1.0, "Mil. of U.S. $": 1.0,
    "Bil. of $": 1000.0, "Bil. of US $": 1000.0,
}

_RANK_LOW = 33.0
_RANK_HIGH = 66.0


def load_macro_series() -> Optional[dict]:
    """macro_series.json 로드. 없거나 손상됐으면 None."""
    if not os.path.exists(_REGISTRY_PATH):
        return None
    try:
        with open(_REGISTRY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def to_musd(value: Optional[float], unit: str) -> Optional[float]:
    """금액을 백만달러($M) 기준으로 정규화. 금액 단위가 아니면 None."""
    if not isinstance(value, (int, float)):
        return None
    mult = _UNIT_TO_MUSD.get(unit)
    return None if mult is None else value * mult


def pct_rank(values: list[float], current: float) -> Optional[float]:
    """values 안에서 current의 백분위(0~100). 자기 자신 포함 <= 비율."""
    if not values:
        return None
    le = sum(1 for v in values if v <= current)
    return round(le / len(values) * 100, 1)


def _parse(d: str) -> Optional[date]:
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def change_over(obs: list[dict], days: int) -> Optional[float]:
    """days일 전 대비 변화(절대값 차).

    관측 주기가 일/주/월/분기로 제각각이라 "N번째 앞 관측치"를 쓰면
    지표마다 기간이 달라진다. 목표 날짜에 가장 가까운 관측치를 고른다.
    """
    if len(obs) < 2:
        return None
    last_date = _parse(obs[-1]["date"])
    if last_date is None:
        return None
    target = last_date - timedelta(days=days)
    best, best_gap = None, None
    for o in obs[:-1]:
        d = _parse(o["date"])
        if d is None:
            continue
        gap = abs((d - target).days)
        if best_gap is None or gap < best_gap:
            best, best_gap = o, gap
    if best is None:
        return None
    return round(obs[-1]["value"] - best["value"], 2)


def _assess(rank: Optional[float], higher_is: str) -> str:
    """백분위 + 해석 방향 → 한 줄 판정."""
    if rank is None:
        return ""
    if higher_is == "neutral":
        return f"3년 백분위 {rank:.0f}%"
    high_is_bad = higher_is == "worse"
    if rank >= _RANK_HIGH:
        return "역사적 고점권(부담)" if high_is_bad else "역사적 고점권(양호)"
    if rank <= _RANK_LOW:
        return "역사적 저점권(양호)" if high_is_bad else "역사적 저점권(부담)"
    return "중간권"


def build_indicator(raw: dict, meta: dict) -> dict:
    """원본 시계열 1종 → 카드 렌더에 필요한 값 일체."""
    base = {
        "id": meta.get("id", ""), "label": meta.get("label", ""),
        "unit": meta.get("unit", ""), "unit_label": meta.get("unit_label", ""),
        "freq": meta.get("freq", ""),
        "latest": None, "latest_date": None,
        "chg_1m": None, "chg_1y": None, "pct_rank_3y": None,
        "assessment": "", "series": [],
    }
    status = raw.get("_status")
    obs = raw.get("observations", [])
    if status != "ok" or not obs:
        base["_status"] = status if status != "ok" else "NO_DATA"
        base["_msg"] = raw.get("_msg", "")
        return base

    values = [o["value"] for o in obs]
    rank = pct_rank(values, values[-1])
    base.update({
        "_status": "ok", "_msg": "",
        "latest": obs[-1]["value"], "latest_date": obs[-1]["date"],
        "chg_1m": change_over(obs, 30), "chg_1y": change_over(obs, 365),
        "pct_rank_3y": rank,
        "assessment": _assess(rank, meta.get("higher_is", "neutral")),
        "series": obs,
    })
    return base


def build_group(raw_group: dict, meta_group: dict) -> dict:
    """그룹 1개의 지표 전체를 레지스트리 순서대로 조립."""
    indicators = [
        build_indicator(raw_group.get(m.get("id", ""), {"_status": "NO_DATA",
                                                        "observations": []}), m)
        for m in meta_group.get("indicators", [])
    ]
    ok = [i for i in indicators if i["_status"] == "ok"]
    return {
        "id": meta_group.get("id", ""), "label": meta_group.get("label", ""),
        "indicators": indicators,
        "_status": "ok" if ok else (indicators[0]["_status"] if indicators else "NO_DATA"),
    }
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd Clone_Advisor && python -m pytest tests/test_dashboard_us.py -v`
Expected: 12 passed

- [ ] **Step 5: 커밋**

```bash
git add advisor_dashboard_us.py tests/test_dashboard_us.py
git commit -m "feat(advisor): add indicator builder with unit normalization"
```

---

## Task 4: 조립 레이어 — 파생 계산과 종합 판정

**Files:**
- Modify: `advisor_dashboard_us.py` (append)
- Modify: `tests/test_dashboard_us.py` (append)

**Interfaces:**
- Consumes: `to_musd()`, `change_over()`, `build_group()` (Task 3)
- Produces:
  - `compute_m2_yoy(obs: list[dict]) -> Optional[float]`
  - `compute_qt_progress(obs: list[dict]) -> dict` → `{"peak","peak_date","current","drawdown","drawdown_pct"}`
  - `compute_hy_ig_gap(hy: dict, ig: dict) -> Optional[float]` (bp)
  - `compute_net_liquidity(groups: dict) -> Optional[float]` ($M)
  - `build_derived(groups: dict) -> dict`
  - `build_assessment(groups: dict, derived: dict) -> list[dict]`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_dashboard_us.py` 끝에 붙인다.

```python
# ── 파생 계산 ────────────────────────────────────────────────
def test_compute_m2_yoy_percent_change():
    obs = [{"date": "2025-08-01", "value": 100.0},
           {"date": "2026-08-01", "value": 110.0}]
    assert adu.compute_m2_yoy(obs) == 10.0


def test_compute_m2_yoy_short_history_returns_none():
    assert adu.compute_m2_yoy([{"date": "2026-08-01", "value": 100.0}]) is None


def test_compute_qt_progress_measures_drawdown_from_peak():
    obs = [{"date": "2026-01-01", "value": 8000.0},
           {"date": "2026-04-01", "value": 9000.0},   # 피크
           {"date": "2026-08-01", "value": 6750.0}]
    out = adu.compute_qt_progress(obs)
    assert out["peak"] == 9000.0
    assert out["peak_date"] == "2026-04-01"
    assert out["current"] == 6750.0
    assert out["drawdown"] == 2250.0
    assert out["drawdown_pct"] == 25.0


def test_compute_hy_ig_gap_in_basis_points():
    hy = {"_status": "ok", "latest": 2.63}
    ig = {"_status": "ok", "latest": 0.79}
    assert adu.compute_hy_ig_gap(hy, ig) == 184.0


def test_compute_hy_ig_gap_none_when_either_missing():
    assert adu.compute_hy_ig_gap({"_status": "NO_DATA", "latest": None},
                                 {"_status": "ok", "latest": 0.79}) is None


def test_compute_net_liquidity_normalizes_billions_before_subtracting():
    # WALCL·WTREGEN은 $M, RRP만 $B — 정규화 없이 빼면 1000배 틀린다
    groups = {"liquidity": {"indicators": [
        {"id": "fed_assets", "_status": "ok", "latest": 6_730_912.0,
         "unit": "Mil. of U.S. $"},
        {"id": "rrp", "_status": "ok", "latest": 0.17, "unit": "Bil. of US $"},
        {"id": "tga", "_status": "ok", "latest": 950_736.0,
         "unit": "Mil. of U.S. $"},
    ]}}
    assert adu.compute_net_liquidity(groups) == 5_780_006.0


def test_compute_net_liquidity_none_when_component_missing():
    groups = {"liquidity": {"indicators": [
        {"id": "fed_assets", "_status": "NO_FRED_KEY", "latest": None,
         "unit": "Mil. of U.S. $"},
    ]}}
    assert adu.compute_net_liquidity(groups) is None


# ── 종합 판정 ────────────────────────────────────────────────
def test_build_assessment_flags_credit_stress_at_high_rank():
    groups = {"credit": {"indicators": [
        {"id": "hy_oas", "_status": "ok", "latest": 8.0, "pct_rank_3y": 95.0},
    ]}}
    rows = adu.build_assessment(groups, {})
    credit = next(r for r in rows if r["id"] == "credit")
    assert credit["verdict"] == "스트레스"


def test_build_assessment_reports_unknown_when_data_missing():
    rows = adu.build_assessment({}, {})
    assert all(r["verdict"] == "판정 불가" for r in rows)
    assert len(rows) == 3
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `cd Clone_Advisor && python -m pytest tests/test_dashboard_us.py -v`
Expected: 신규 9건 FAIL — `AttributeError: module 'advisor_dashboard_us' has no attribute 'compute_m2_yoy'`

- [ ] **Step 3: 최소 구현**

`advisor_dashboard_us.py` 끝에 붙인다.

```python
# ─────────────────────────────────────────────────────────────────────
# 파생 계산 — 원시값만으로는 크기를 가늠할 수 없어 해석 근거를 만든다
# ─────────────────────────────────────────────────────────────────────
def _find(groups: dict, gid: str, iid: str) -> dict:
    """조립된 그룹에서 지표 1개를 꺼낸다. 없으면 빈 dict."""
    for ind in groups.get(gid, {}).get("indicators", []):
        if ind.get("id") == iid:
            return ind
    return {}


def compute_m2_yoy(obs: list[dict]) -> Optional[float]:
    """M2 전년동월 대비 증가율(%). 잔액보다 증감이 의미 있다."""
    if len(obs) < 2:
        return None
    diff = change_over(obs, 365)
    if diff is None:
        return None
    base = obs[-1]["value"] - diff       # 1년 전 값
    if not base:
        return None
    return round(diff / base * 100, 2)


def compute_qt_progress(obs: list[dict]) -> dict:
    """연준 총자산 피크 대비 감축액·감축률 — 양적긴축 진행도."""
    empty = {"peak": None, "peak_date": None, "current": None,
             "drawdown": None, "drawdown_pct": None}
    if not obs:
        return empty
    peak_obs = max(obs, key=lambda o: o["value"])
    current = obs[-1]["value"]
    drawdown = peak_obs["value"] - current
    return {
        "peak": peak_obs["value"], "peak_date": peak_obs["date"],
        "current": current, "drawdown": round(drawdown, 2),
        "drawdown_pct": (round(drawdown / peak_obs["value"] * 100, 2)
                         if peak_obs["value"] else None),
    }


def compute_hy_ig_gap(hy: dict, ig: dict) -> Optional[float]:
    """하이일드 − 투자등급 OAS(bp). 신용 차별화 정도."""
    if hy.get("_status") != "ok" or ig.get("_status") != "ok":
        return None
    a, b = hy.get("latest"), ig.get("latest")
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return None
    return round((a - b) * 100, 1)


def compute_net_liquidity(groups: dict) -> Optional[float]:
    """순유동성($M) = 연준 총자산 − 역레포 − 재무부 일반계정.

    RRPONTSYD만 $B라 to_musd()로 맞춘 뒤 뺀다(스펙 §5 단위 정규화).
    """
    parts = []
    for iid in ("fed_assets", "rrp", "tga"):
        ind = _find(groups, "liquidity", iid)
        if ind.get("_status") != "ok":
            return None
        v = to_musd(ind.get("latest"), ind.get("unit", ""))
        if v is None:
            return None
        parts.append(v)
    return round(parts[0] - parts[1] - parts[2], 2)


def build_derived(groups: dict) -> dict:
    """파생 지표 묶음."""
    m2 = _find(groups, "liquidity", "m2")
    fed = _find(groups, "liquidity", "fed_assets")
    return {
        "m2_yoy": compute_m2_yoy(m2.get("series", [])),
        "qt": compute_qt_progress(fed.get("series", [])),
        "hy_ig_gap": compute_hy_ig_gap(_find(groups, "credit", "hy_oas"),
                                       _find(groups, "credit", "ig_oas")),
        "net_liquidity": compute_net_liquidity(groups),
    }


# ─────────────────────────────────────────────────────────────────────
# 종합 판정 3줄 — 룰 템플릿(LLM 미사용)
# ─────────────────────────────────────────────────────────────────────
_UNKNOWN = "판정 불가"


def build_assessment(groups: dict, derived: dict) -> list[dict]:
    """유동성·신용·재정 3줄 판정. 근거 데이터가 없으면 '판정 불가'."""
    rows = []

    # 유동성 — M2 YoY 부호로 판정, 연준자산 축소율은 부연
    m2_yoy = derived.get("m2_yoy")
    if isinstance(m2_yoy, (int, float)):
        verdict = "완화" if m2_yoy > 2 else "긴축" if m2_yoy < 0 else "중립"
        text = f"M2 전년비 {m2_yoy:+.1f}%"
        qt = derived.get("qt") or {}
        if isinstance(qt.get("drawdown_pct"), (int, float)):
            text += f" · 연준자산 피크 대비 {qt['drawdown_pct']:.1f}% 축소"
    else:
        verdict, text = _UNKNOWN, "M2 데이터 없음"
    rows.append({"id": "liquidity", "label": "유동성", "verdict": verdict, "text": text})

    # 신용 — HY OAS 3년 백분위
    hy = _find(groups, "credit", "hy_oas")
    rank = hy.get("pct_rank_3y") if hy.get("_status") == "ok" else None
    if isinstance(rank, (int, float)):
        verdict = ("스트레스" if rank > _RANK_HIGH
                   else "안정" if rank < _RANK_LOW else "경계")
        text = f"하이일드 OAS {hy.get('latest'):.2f}% (3년 백분위 {rank:.0f}%)"
        gap = derived.get("hy_ig_gap")
        if isinstance(gap, (int, float)):
            text += f" · HY−IG {gap:+.0f}bp"
    else:
        verdict, text = _UNKNOWN, "신용 스프레드 데이터 없음"
    rows.append({"id": "credit", "label": "신용", "verdict": verdict, "text": text})

    # 재정 — 부채/GDP 1년 변화
    dg = _find(groups, "fiscal", "debt_gdp")
    if dg.get("_status") == "ok" and isinstance(dg.get("chg_1y"), (int, float)):
        verdict = "부담 가중" if dg["chg_1y"] > 0 else "지속가능"
        text = f"부채/GDP {dg['latest']:.1f}% (1년 {dg['chg_1y']:+.1f}%p)"
        it = _find(groups, "fiscal", "interest")
        if it.get("_status") == "ok" and isinstance(it.get("chg_1y"), (int, float)):
            text += f" · 이자지급 1년 {it['chg_1y']:+,.0f}십억$"
    else:
        verdict, text = _UNKNOWN, "재정 데이터 없음"
    rows.append({"id": "fiscal", "label": "재정", "verdict": verdict, "text": text})

    return rows
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd Clone_Advisor && python -m pytest tests/test_dashboard_us.py -v`
Expected: 21 passed

- [ ] **Step 5: 커밋**

```bash
git add advisor_dashboard_us.py tests/test_dashboard_us.py
git commit -m "feat(advisor): add macro derived metrics and rule-based assessment"
```

---

## Task 5: 오케스트레이션과 라이브 검증

**Files:**
- Modify: `advisor_dashboard_us.py` (append)

**Interfaces:**
- Consumes: `load_macro_series()`, `build_group()`, `build_derived()`, `build_assessment()`, `am.collect_macro()`
- Produces:
  - `build_briefing_us() -> dict` → `{"_status", "groups": {gid: <build_group 결과>}, "derived": {...}, "assessment": [...], "generated_at": str}`

- [ ] **Step 1: `build_briefing_us()` 구현**

```python
# ─────────────────────────────────────────────────────────────────────
# 오케스트레이션
# ─────────────────────────────────────────────────────────────────────
def build_briefing_us() -> dict:
    """레지스트리 → 수집 → 조립 → 파생 → 판정 전체 파이프라인."""
    registry = load_macro_series()
    if not registry:
        return {"_status": "NO_REGISTRY", "groups": {}, "derived": {},
                "assessment": [],
                "generated_at": datetime.now().isoformat(timespec="seconds")}

    raw = am.collect_macro(registry)
    groups = {
        g["id"]: build_group(raw.get(g["id"], {}), g)
        for g in registry.get("groups", []) if g.get("id")
    }
    derived = build_derived(groups)
    return {
        "_status": "ok",
        "groups": groups,
        "derived": derived,
        "assessment": build_assessment(groups, derived),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
```

- [ ] **Step 2: 라이브 검증 — 14종 전부 ok인지**

Run:
```bash
cd Clone_Advisor && PYTHONIOENCODING=utf-8 python -c "
import advisor_dashboard_us as adu
b = adu.build_briefing_us()
print('상태:', b['_status'])
n = 0
for gid, g in b['groups'].items():
    print('[' + g['label'] + ']')
    for i in g['indicators']:
        n += i['_status'] == 'ok'
        print('   %-16s %-12s %18s %-8s 1개월 %10s 백분위 %6s %s' % (
            i['label'], i['_status'], i['latest'], i['unit_label'],
            i['chg_1m'], i['pct_rank_3y'], i['assessment']))
print('ok:', n, '/ 14')
print('파생:', b['derived'])
for r in b['assessment']:
    print('  %s: %s — %s' % (r['label'], r['verdict'], r['text']))
"
```
Expected: `ok: 14 / 14`. 판정 3줄에 `판정 불가`가 없을 것.

- [ ] **Step 3: 파생 손검산**

Step 2 출력에서 아래를 손으로 확인한다. 하나라도 어긋나면 멈추고 원인을 찾는다.
- `net_liquidity` ≈ `fed_assets − rrp×1000 − tga` (전부 $M). 2026-08 기준 대략 **5.7e6 $M(= $5.7조)** 근처여야 한다. `5.7e9` 같은 값이 나오면 단위 정규화가 깨진 것이다.
- `hy_ig_gap` ≈ (hy_oas − ig_oas) × 100. 2026-08-27 실측 기준 약 **184bp**.
- `qt.drawdown_pct`가 0~40% 범위인지(피크 대비 축소율).
- `m2_yoy`가 −10~+30% 범위인지.

- [ ] **Step 4: 커밋**

```bash
git add advisor_dashboard_us.py
git commit -m "feat(advisor): add Family E briefing orchestration"
```

---

## Task 6: Streamlit 탭

**Files:**
- Modify: `advisor_app.py`

**Interfaces:**
- Consumes: `advisor_dashboard_us.build_briefing_us()`, `advisor_report.render_html_us()` (Task 7 — 없으면 `try/except`가 경고만 띄우고 넘어간다)
- Produces: tab4 렌더링, `macro_chart(indicators, title)` 헬퍼

- [ ] **Step 1: 임포트와 캐시 로더 추가**

`import advisor_dashboard_kr as adk` 다음 줄에 추가:

```python
import advisor_dashboard_us as adu
```

`load_briefing_kr()` 정의 다음에 추가한다. **TTL 6시간인 이유는 월간·분기 시리즈라 30분 갱신이 무의미하고, 호출당 외부 API를 14번 두드리기 때문이다.**

```python
@st.cache_data(ttl=21600, show_spinner=False)   # 6시간 — 월간·분기 시리즈
def load_briefing_us() -> dict:
    return adu.build_briefing_us()
```

- [ ] **Step 2: 차트 헬퍼 추가**

`yield_curve_chart()` 정의 다음에 추가한다. **단위가 다른 지표를 한 축에 겹치지 않는다**(스펙 §9).

```python
_MACRO_COLORS = ["#4fc3f7", "#ffb74d", "#81c784", "#e57373", "#ba68c8"]


def macro_chart(indicators: list[dict], title: str):
    """같은 단위의 지표들만 한 차트에. 단위가 섞이면 호출부에서 나눠 넘긴다."""
    fig = go.Figure()
    for i, ind in enumerate(indicators):
        series = ind.get("series", [])
        if not series:
            continue
        fig.add_trace(go.Scatter(
            x=[o["date"] for o in series], y=[o["value"] for o in series],
            mode="lines", name=ind["label"],
            line=dict(width=1.6, color=_MACRO_COLORS[i % len(_MACRO_COLORS)])))
    fig.update_layout(template="plotly_dark", height=300, title=title,
                      margin=dict(l=8, r=8, t=36, b=8),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#161922",
                      legend=dict(orientation="h", y=1.02, x=0,
                                  bgcolor="rgba(0,0,0,0)"))
    fig.update_xaxes(gridcolor="#2e3650")
    fig.update_yaxes(gridcolor="#2e3650")
    return fig
```

- [ ] **Step 3: 탭 목록 확장**

```python
tab1, tab2, tab3, tab4 = st.tabs(
    ["🧮 종목 분석", "📰 시황 브리핑", "🏦 증시·정책 브리핑", "🇺🇸 재정·통화"])
```

- [ ] **Step 4: tab4 블록 추가**

`with tab3:` 블록이 끝난 **직후**, `with tab1:` 보다 **앞에** 넣는다. (tab1이 `st.stop()`으로 스크립트를 끊기 때문 — 파일 상단 주석 참조.)

```python
with tab4:
    st.caption("미국 재정·통화·신용 상태 · FRED + 미 재무부 · 6시간 캐시")
    if st.button("🇺🇸 브리핑 생성", type="primary"):
        with st.spinner("FRED·재무부 시계열 수집 중…"):
            st.session_state["briefing_us"] = load_briefing_us()

    bus = st.session_state.get("briefing_us")
    if not bus:
        st.info("위 버튼을 눌러 미국 재정·통화 브리핑을 생성하세요.")
    elif bus.get("_status") == "NO_REGISTRY":
        st.error("macro_series.json을 읽을 수 없습니다.")
    else:
        st.caption(f"생성 시각: {bus['generated_at']}")

        try:
            report_html_us = ar.render_html_us(bus)
            st.download_button(
                "📥 리포트 다운로드 (HTML)", data=report_html_us,
                file_name=f"{bus['generated_at'][:10]}_briefing_us.html",
                mime="text/html", key="download_us")
        except Exception as e:
            st.warning(f"HTML 리포트 생성 실패: {e}")

        st.markdown("### 종합 판정")
        a_cols = st.columns(3)
        for i, row in enumerate(bus["assessment"]):
            a_cols[i].metric(row["label"], row["verdict"])
            a_cols[i].caption(row["text"])

        for group in bus["groups"].values():
            st.markdown(f"### {group['label']}")
            inds = group["indicators"]
            if inds and all(i["_status"] == "NO_FRED_KEY" for i in inds):
                st.warning("FRED API 키가 없어 이 그룹을 표시할 수 없습니다. "
                           "`.fred_api_key` 파일에 키를 저장하세요.")
                continue

            g_cols = st.columns(len(inds))
            for i, ind in enumerate(inds):
                value = ind["latest"]
                g_cols[i].metric(
                    ind["label"],
                    f"{value:,.2f}" if isinstance(value, (int, float)) else "—",
                    delta=(f"{ind['chg_1m']:+,.2f} (1개월)"
                           if isinstance(ind["chg_1m"], (int, float)) else None))
                g_cols[i].caption(f"{ind['unit_label']} · {ind['freq']}"
                                  + (f" · {ind['assessment']}" if ind["assessment"] else ""))

            # 단위별로 차트를 나눈다 — %와 $를 한 축에 겹치지 않기 위함
            by_unit: dict[str, list[dict]] = {}
            for ind in inds:
                if ind["_status"] == "ok" and ind.get("series"):
                    by_unit.setdefault(ind["unit_label"], []).append(ind)
            for unit_label, unit_inds in by_unit.items():
                st.plotly_chart(
                    macro_chart(unit_inds, f"{group['label']} — {unit_label}"),
                    use_container_width=True)
```

- [ ] **Step 5: 구문 확인**

Run: `cd Clone_Advisor && python -c "import ast,io; ast.parse(io.open('advisor_app.py',encoding='utf-8').read()); print('syntax ok')"`
Expected: `syntax ok`

- [ ] **Step 6: 앱 부팅 확인**

Run:
```bash
cd Clone_Advisor && PYTHONIOENCODING=utf-8 python -m streamlit run advisor_app.py --server.port 8599 --server.headless true > "$CLAUDE_JOB_DIR/tmp/st_us.log" 2>&1 &
sleep 25 && curl -s -o /dev/null -w "HTTP %{http_code}\n" http://localhost:8599/ && cat "$CLAUDE_JOB_DIR/tmp/st_us.log"
```
Expected: `HTTP 200`, 로그에 traceback 없음.
확인 후 반드시 종료: `PID=$(netstat -ano | grep ":8599" | grep LISTENING | awk '{print $5}' | head -1); taskkill //F //PID $PID`

- [ ] **Step 7: 커밋**

```bash
git add advisor_app.py
git commit -m "feat(advisor): add US fiscal/monetary tab to Streamlit app"
```

---

## Task 7: 정적 HTML 리포트

**Files:**
- Modify: `advisor_report.py`

**Interfaces:**
- Consumes: `build_briefing_us()` 출력
- Produces: `render_html_us(briefing: dict) -> str`

- [ ] **Step 1: `render_html_us()` 구현**

`render_html_kr()` 정의 **앞**에 추가한다. plotly를 심을 수 없으므로 카드 + 최근 5개 관측치 표로 대체하고, 기존 `.grid`/`.card`/`.up`/`.down` CSS를 재사용한다.

```python
def _macro_group_html(group: dict) -> str:
    """지표 카드 + 지표별 최근 5개 관측치 표."""
    inds = group.get("indicators", [])
    if not inds:
        return "<p>지표가 없습니다.</p>"
    if all(i.get("_status") == "NO_FRED_KEY" for i in inds):
        return "<p>FRED API 키가 없어 이 그룹을 표시할 수 없습니다.</p>"

    cards = []
    for ind in inds:
        value = ind.get("latest")
        chg = ind.get("chg_1m")
        cls = "up" if isinstance(chg, (int, float)) and chg >= 0 else "down"
        val_txt = f"{value:,.2f}" if isinstance(value, (int, float)) else "—"
        chg_txt = f"1개월 {chg:+,.2f}" if isinstance(chg, (int, float)) else "1개월 —"
        cards.append(
            f'<div class="card"><h3>{html.escape(ind.get("label", ""))}</h3>'
            f'<div class="val">{val_txt}</div>'
            f'<div class="{cls}">{chg_txt}</div>'
            f'<div>{html.escape(ind.get("unit_label", ""))} · '
            f'{html.escape(ind.get("assessment", ""))}</div></div>')

    rows = []
    for ind in inds:
        if ind.get("_status") != "ok":
            continue
        for o in ind.get("series", [])[-5:]:
            rows.append(f'<tr><td>{html.escape(ind.get("label", ""))}</td>'
                        f'<td>{html.escape(o["date"])}</td>'
                        f'<td>{o["value"]:,.2f}</td></tr>')
    table = ("<table><tr><th>지표</th><th>날짜</th><th>값</th></tr>"
             f'{"".join(rows)}</table>') if rows else ""
    return f'<div class="grid">{"".join(cards)}</div>{table}'


def _macro_assessment_html(rows: list[dict]) -> str:
    if not rows:
        return "<p>판정 데이터가 없습니다.</p>"
    cards = "".join(
        f'<div class="card"><h3>{html.escape(r.get("label", ""))}</h3>'
        f'<div class="val">{html.escape(r.get("verdict", ""))}</div>'
        f'<div>{html.escape(r.get("text", ""))}</div></div>' for r in rows)
    return f'<div class="grid">{cards}</div>'


def render_html_us(briefing: dict) -> str:
    """advisor_dashboard_us.build_briefing_us() 출력 → 독립 실행형 HTML."""
    sections = [("종합 판정", _macro_assessment_html(briefing.get("assessment", [])))]
    for group in briefing.get("groups", {}).values():
        sections.append((group.get("label", ""), _macro_group_html(group)))

    body = "".join(f'<div class="section-title">{html.escape(title)}</div>{section_html}'
                   for title, section_html in sections)
    generated_at = briefing.get("generated_at", "") or ""
    return (
        "<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'>"
        f"<title>미국 재정·통화 모니터 {html.escape(generated_at[:10])}</title>"
        f"<style>{_CSS}</style></head><body>"
        '<div class="header"><h1>미국 재정·통화 모니터</h1>'
        f'<div>생성 시각: {html.escape(generated_at)}</div></div>'
        f"{body}</body></html>")
```

- [ ] **Step 2: 렌더러 검증**

Run:
```bash
cd Clone_Advisor && PYTHONIOENCODING=utf-8 python -c "
import advisor_dashboard_us as adu, advisor_report as ar
b = adu.build_briefing_us()
h = ar.render_html_us(b)
print('HTML 길이:', len(h))
for label in ['종합 판정', '기업 신용 스프레드', '통화량·유동성', '연방 재정', '정책금리·실질금리']:
    print('  ' + label + ':', '포함' if label in h else '누락!')
"
```
Expected: 5개 라벨 전부 `포함`, HTML 길이 5000자 이상.

- [ ] **Step 3: 키 없는 경로 렌더 검증**

Run:
```bash
cd Clone_Advisor && mv .fred_api_key .fred_api_key.bak && PYTHONIOENCODING=utf-8 python -c "
import advisor_dashboard_us as adu, advisor_report as ar
b = adu.build_briefing_us()
h = ar.render_html_us(b)
print('키 없이도 렌더:', len(h) > 1000)
print('안내 문구 포함:', 'FRED API 키가 없어' in h)
print('부채 카드 살아있음:', '연방 총부채' in h)
"; mv .fred_api_key.bak .fred_api_key
```
Expected: 세 줄 모두 `True`. **끝의 `mv`로 키 파일이 복구됐는지 `ls -la .fred_api_key`로 확인할 것.**

- [ ] **Step 4: 전체 테스트 재실행**

Run: `cd Clone_Advisor && python -m pytest tests/ -v`
Expected: 21 passed

- [ ] **Step 5: 커밋**

```bash
git add advisor_report.py
git commit -m "feat(advisor): add static HTML report for US fiscal/monetary monitor"
```

---

## 완료 조건

- [ ] `pytest tests/ -v` 21건 통과
- [ ] `build_briefing_us()`가 14/14 지표 `ok`
- [ ] 순유동성이 $5.7조 규모(5.7e6 $M) — 1000배 오차 없음
- [ ] 키를 치운 상태에서도 탭·리포트가 뜨고 재무부 총부채 카드는 살아 있음
- [ ] 앱 헤드리스 부팅 HTTP 200, traceback 없음
- [ ] `git status`에 `.fred_api_key`가 나타나지 않음
