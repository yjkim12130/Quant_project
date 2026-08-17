"""
kiwoom_data.py — 키움증권 REST API 데이터 레이어 (Family B)
═══════════════════════════════════════════════════════════════════════
한국 증시 자체 데이터(KOSPI/KOSDAQ 지수·등락종목수·수급·개별종목·업종)를
키움증권 REST API로 공급한다. advisor_news.py(Family A, yfinance+RSS)와
병렬 구조 — 여기선 원본 수집만 담당, 해석/서술은 advisor_dashboard_kr.py
의 몫이다(advisor_data.py/advisor_news.py와 동일한 설계 원칙).
"""
from __future__ import annotations
import glob
import os
import time
from typing import Optional

import requests

_HERE = os.path.dirname(os.path.abspath(__file__))
_KIWOOM_KEY_DIR = os.path.join(os.path.dirname(_HERE), "kiwoom_api_key")

_TOKEN_URL = "https://api.kiwoom.com/oauth2/token"
_HEADERS_JSON = {"Content-Type": "application/json;charset=UTF-8"}

# 인메모리 토큰 캐시 — 프로세스 생존 기간 동안만 유지(재시작 시 재발급).
_token_cache: dict = {"token": None, "expires_at": 0.0}


def _get_kiwoom_key(kind: str) -> Optional[str]:
    """kind: 'appkey' 또는 'secretkey'. 환경변수(KIWOOM_APPKEY/KIWOOM_SECRETKEY) 우선,
    없으면 kiwoom_api_key/*_{kind}.txt 파일에서 읽는다(계좌번호 접두사는 무시)."""
    env_name = f"KIWOOM_{kind.upper()}"
    val = os.environ.get(env_name)
    if val:
        return val.strip()
    matches = glob.glob(os.path.join(_KIWOOM_KEY_DIR, f"*_{kind}.txt"))
    if not matches:
        return None
    with open(matches[0], encoding="utf-8") as f:
        return f.read().strip()


def get_kiwoom_token() -> Optional[str]:
    """OAuth 접근토큰 발급·캐싱. 만료 60초 전부터 재발급 시도."""
    if _token_cache["token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    appkey = _get_kiwoom_key("appkey")
    secretkey = _get_kiwoom_key("secretkey")
    if not appkey or not secretkey:
        return None

    try:
        r = requests.post(
            _TOKEN_URL,
            json={"grant_type": "client_credentials", "appkey": appkey, "secretkey": secretkey},
            headers=_HEADERS_JSON,
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None

    if data.get("return_code") != 0 or not data.get("token"):
        return None

    _token_cache["token"] = data["token"]
    # expires_dt 형식: "YYYYMMDDHHMMSS" — 정확한 만료 계산 대신, 못 미더울 땐
    # 보수적으로 30분 뒤 재발급하도록 캐시(대부분의 브로커 API 토큰 수명은
    # 이보다 훨씬 길다 — 30분은 안전 마진).
    _token_cache["expires_at"] = time.time() + 1800
    return _token_cache["token"]


_BASE_URL = "https://api.kiwoom.com"
_MRKCOND_PATH = "/api/dostk/mrkcond"
_SECT_PATH = "/api/dostk/sect"

_INDEX_CODES = {"KOSPI": "001", "KOSDAQ": "101"}


def _auth_headers(api_id: str) -> dict:
    token = get_kiwoom_token()
    return {
        "Content-Type": "application/json;charset=UTF-8",
        "api-id": api_id,
        "authorization": f"Bearer {token}",
    }


def _parse_num(raw) -> Optional[float]:
    """키움 응답의 부호 접두사 문자열(예: '+274500', '--829332')을 float로 변환.
    '+' 제거 후 남은 문자열이 '-'로 시작하면 음수로 취급(단일·이중 부호 모두 동일 처리)."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    stripped = s.replace("+", "")
    sign = -1.0 if stripped.startswith("-") else 1.0
    digits = stripped.lstrip("-")
    try:
        return sign * float(digits)
    except ValueError:
        return None


def _get_sector_index_rows(inds_cd: str) -> list[dict]:
    """전업종지수요청(ka20003) 원본 행 리스트. 실패 시 빈 리스트.
    inds_cd='001'|'101'은 각각 KOSPI/KOSDAQ 종합지수를 포함한 전체 업종 목록을 반환한다
    (지수 시세·등락종목수·업종별 등락률을 이 한 번의 호출로 전부 얻을 수 있음 — 실측 확인됨)."""
    token = get_kiwoom_token()
    if not token:
        return []
    try:
        r = requests.post(
            f"{_BASE_URL}{_SECT_PATH}",
            headers=_auth_headers("ka20003"),
            json={"inds_cd": inds_cd},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("all_inds_idex") or []
    except Exception:
        return []


def get_index_quote(market: str) -> dict:
    """KOSPI/KOSDAQ 지수 현재가·등락률(전업종지수요청 ka20003 중 종합지수 행)."""
    code = _INDEX_CODES.get(market.upper())
    if not code:
        return {"market": market, "price": None, "chg_pct": None, "_status": "NO_DATA"}
    rows = _get_sector_index_rows(code)
    row = next((r for r in rows if r.get("stk_cd") == code), None)
    if not row:
        return {"market": market, "price": None, "chg_pct": None, "_status": "NO_DATA"}
    return {
        "market": market,
        "price": _parse_num(row.get("cur_prc")),
        "chg_pct": _parse_num(row.get("flu_rt")),
    }


def get_advance_decline(market: str) -> dict:
    """KOSPI/KOSDAQ 등락종목수(ADR 계산용). 종합지수 행의 rising/fall/stdns 필드 사용."""
    code = _INDEX_CODES.get(market.upper())
    if not code:
        return {"market": market, "advancers": None, "decliners": None,
                "unchanged": None, "_status": "NO_DATA"}
    rows = _get_sector_index_rows(code)
    row = next((r for r in rows if r.get("stk_cd") == code), None)
    if not row:
        return {"market": market, "advancers": None, "decliners": None,
                "unchanged": None, "_status": "NO_DATA"}
    adv = _parse_num(row.get("rising"))
    dec = _parse_num(row.get("fall"))
    unch = _parse_num(row.get("stdns"))
    return {
        "market": market,
        "advancers": int(adv) if adv is not None else None,
        "decliners": int(dec) if dec is not None else None,
        "unchanged": int(unch) if unch is not None else None,
    }


def get_sector_returns() -> list[dict]:
    """업종별 등락률(종합지수·대형주/중형주/소형주 등 규모별 그룹 제외, 개별 업종만).
    KOSPI 기준(inds_cd='001') 전업종지수 목록에서 종합/규모그룹(001~004, 실측 확인됨:
    001=종합(KOSPI) 002=대형주 003=중형주 004=소형주 005부터 실제 업종)을 뺀 나머지."""
    rows = _get_sector_index_rows("001")
    out = []
    for r in rows:
        code = r.get("stk_cd")
        if code in ("001", "002", "003", "004"):  # 종합/대형주/중형주/소형주 — 업종이 아님
            continue
        chg = _parse_num(r.get("flu_rt"))
        if chg is None:
            continue
        out.append({"sector": r.get("stk_nm", ""), "chg_pct": chg})
    return out


def get_stock_quote(code: str) -> dict:
    """개별종목 시세(일별주가요청 ka10086의 최신 1건)."""
    token = get_kiwoom_token()
    if not token:
        return {"code": code, "name": None, "price": None, "chg_pct": None, "_status": "AUTH_FAILED"}
    try:
        r = requests.post(
            f"{_BASE_URL}{_MRKCOND_PATH}",
            headers=_auth_headers("ka10086"),
            json={"stk_cd": code, "qry_dt": time.strftime("%Y%m%d"), "indc_tp": "1"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        rows = data.get("daly_stkpc") or []
        if not rows:
            return {"code": code, "name": None, "price": None, "chg_pct": None, "_status": "NO_DATA"}
        latest = rows[0]
        return {
            "code": code,
            "name": None,  # ka10086 응답엔 종목명이 없음 — 필요 시 호출부에서 알고 있는 이름 사용
            "price": _parse_num(latest.get("close_pric")),
            "chg_pct": _parse_num(latest.get("flu_rt")),
        }
    except Exception:
        return {"code": code, "name": None, "price": None, "chg_pct": None, "_status": "NO_DATA"}


_CHART_PATH = "/api/dostk/chart"


def get_index_ohlc_history(market: str, days: int = 20) -> list[dict]:
    """지수 일봉(ATR 계산용). 업종차트요청(ka20006) — 최근 days일. 실패 시 빈 리스트.
    응답 수치는 부호 접두사 없이 100배 스케일(예: '697794' → 6977.94)로 온다 — 실측 확인됨,
    ka20003/ka10086 계열의 부호 접두사 스케일과 다르므로 _parse_num을 쓰지 않고 직접 변환."""
    token = get_kiwoom_token()
    if not token:
        return []
    code = _INDEX_CODES.get(market.upper())
    if not code:
        return []
    try:
        r = requests.post(
            f"{_BASE_URL}{_CHART_PATH}",
            headers=_auth_headers("ka20006"),
            json={"inds_cd": code, "base_dt": time.strftime("%Y%m%d")},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        rows = data.get("inds_dt_pole_qry") or []
        out = []
        for row in rows[:days]:
            try:
                out.append({
                    "date": row.get("dt", ""),
                    "open": float(row["open_pric"]) / 100,
                    "high": float(row["high_pric"]) / 100,
                    "low": float(row["low_pric"]) / 100,
                    "close": float(row["cur_prc"]) / 100,
                })
            except (KeyError, ValueError, TypeError):
                continue
        return out
    except Exception:
        return []


def get_investor_flow(market: str) -> dict:
    """외국인/기관/개인 순매수(금액, 업종별순매수요청 ka10051의 종합지수 행).
    단위는 실측 규모 비교로 '억원'으로 추정(공식 단위 문서 미확인 — 다르면 unit 필드만 고치면 됨)."""
    code = _INDEX_CODES.get(market.upper())
    if not code:
        return {"market": market, "foreign_net": None, "individual_net": None,
                "institution_net": None, "unit": "", "_status": "NO_DATA"}
    token = get_kiwoom_token()
    if not token:
        return {"market": market, "foreign_net": None, "individual_net": None,
                "institution_net": None, "unit": "", "_status": "AUTH_FAILED"}
    mrkt_tp = "0" if market.upper() == "KOSPI" else "1"
    try:
        r = requests.post(
            f"{_BASE_URL}{_SECT_PATH}",
            headers=_auth_headers("ka10051"),
            json={"mrkt_tp": mrkt_tp, "amt_qty_tp": "0", "stex_tp": "1",
                  "base_dt": time.strftime("%Y%m%d")},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        rows = data.get("inds_netprps") or []
        row = next((x for x in rows if x.get("inds_cd") == code), None)
        if not row:
            return {"market": market, "foreign_net": None, "individual_net": None,
                    "institution_net": None, "unit": "", "_status": "NO_DATA"}
        return {
            "market": market,
            "foreign_net": _parse_num(row.get("frgnr_netprps")),
            "individual_net": _parse_num(row.get("ind_netprps")),
            "institution_net": _parse_num(row.get("orgn_netprps")),
            "unit": "억원",
        }
    except Exception:
        return {"market": market, "foreign_net": None, "individual_net": None,
                "institution_net": None, "unit": "", "_status": "NO_DATA"}


_RKINFO_PATH = "/api/dostk/rkinfo"
_MARKET_RANK_CODES = {"KOSPI": "001", "KOSDAQ": "101"}


def get_top_movers(market: str, direction: str, limit: int = 3) -> list[dict]:
    """상승률/하락률 상위 종목(전일대비등락률상위요청 ka10027). direction: 'up'|'down'.
    실패 시 빈 리스트. 응답의 top-level 키 이름이 방향(상승/하락)에 따라 달라서
    dict 값 중 list인 첫 항목을 그대로 사용한다(정확한 키 이름에 의존하지 않음)."""
    token = get_kiwoom_token()
    if not token:
        return []
    mrkt_tp = _MARKET_RANK_CODES.get(market.upper())
    if not mrkt_tp:
        return []
    sort_tp = "1" if direction == "up" else "3"
    try:
        r = requests.post(
            f"{_BASE_URL}{_RKINFO_PATH}",
            headers=_auth_headers("ka10027"),
            json={"mrkt_tp": mrkt_tp, "sort_tp": sort_tp, "trde_qty_cnd": "0000",
                  "stk_cnd": "0", "crd_cnd": "0", "updown_incls": "1", "pric_cnd": "0",
                  "trde_prica_cnd": "0", "stex_tp": "1"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        rows = next((v for v in data.values() if isinstance(v, list)), [])
        out = []
        for row in rows[:limit]:
            chg = _parse_num(row.get("flu_rt"))
            if chg is None:
                continue
            out.append({"name": row.get("stk_nm", ""), "chg_pct": chg})
        return out
    except Exception:
        return []
