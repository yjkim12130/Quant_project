# -*- coding: utf-8 -*-
"""로또 6/45 당첨 이력 수집·캐시 모듈.

소스: github.com/smok95/lotto (회차별 JSON). 동행복권 공식 API는 봇 차단으로 사용 불가(2026-08 확인).
첫 실행 시 전 회차를 내려받아 data/history.csv 에 저장하고, 이후에는 증분만 요청한다.
"""
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests

RAW_URL = "https://raw.githubusercontent.com/smok95/lotto/master/results/{}.json"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CACHE_PATH = os.path.join(DATA_DIR, "history.csv")
COLUMNS = ["round", "date", "n1", "n2", "n3", "n4", "n5", "n6",
           "bonus", "first_winners", "first_prize", "total_sales"]


class DataUnavailableError(RuntimeError):
    """네트워크도 캐시도 없어 데이터를 제공할 수 없을 때."""


def _fetch_round(no: int, timeout: int = 10):
    """한 회차 JSON을 가져온다. 없거나(404) 실패하면 None."""
    try:
        r = requests.get(RAW_URL.format(no), timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None


def _row_from_json(d: dict) -> dict:
    nums = sorted(d["numbers"])
    div1 = d["divisions"][0] if d.get("divisions") else {}
    return {
        "round": d["draw_no"],
        "date": d["date"][:10],
        **{f"n{i+1}": nums[i] for i in range(6)},
        "bonus": d["bonus_no"],
        "first_winners": div1.get("winners"),
        "first_prize": div1.get("prize"),
        "total_sales": d.get("total_sales_amount"),
    }


def merge_history(cached: pd.DataFrame, new_rows: pd.DataFrame) -> pd.DataFrame:
    """캐시와 신규 회차를 회차 기준으로 병합(중복 시 신규 우선), 회차순 정렬."""
    merged = pd.concat([cached, new_rows], ignore_index=True)
    merged = merged.drop_duplicates(subset="round", keep="last")
    return merged.sort_values("round").reset_index(drop=True)[COLUMNS]


def _bulk_fetch(start: int, workers: int = 16) -> pd.DataFrame:
    """start 회차부터 존재하는 모든 회차를 병렬로 수집한다."""
    # 상한 탐색: 지수 확장 + 이분 탐색
    if _fetch_round(start) is None:
        return pd.DataFrame(columns=COLUMNS)
    lo, hi = start, max(start * 2, start + 64)
    while _fetch_round(hi) is not None:
        lo, hi = hi, hi * 2
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if _fetch_round(mid) is not None:
            lo = mid
        else:
            hi = mid
    latest = lo

    rows = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_fetch_round, n) for n in range(start, latest + 1)]
        for f in as_completed(futs):
            d = f.result()
            if d:
                rows.append(_row_from_json(d))
    return pd.DataFrame(rows, columns=COLUMNS)


def load_history() -> tuple[pd.DataFrame, str | None]:
    """이력 DataFrame과 경고 메시지(정상이면 None)를 반환한다.

    - 캐시 없음 + 네트워크 가능: 전 회차 수집 후 캐시 저장
    - 캐시 있음: 마지막 회차 이후만 순차 증분 요청, 실패 시 캐시로 동작하며 경고
    - 캐시 없음 + 네트워크 불가: DataUnavailableError
    """
    cached = None
    if os.path.exists(CACHE_PATH):
        try:
            cached = pd.read_csv(CACHE_PATH)
        except Exception:
            cached = None

    if cached is None or cached.empty:
        df = _bulk_fetch(1)
        if df.empty:
            raise DataUnavailableError(
                "당첨 이력을 가져올 수 없습니다. 인터넷 연결을 확인한 뒤 다시 실행해 주세요."
            )
        os.makedirs(DATA_DIR, exist_ok=True)
        df.to_csv(CACHE_PATH, index=False)
        return df, None

    last = int(cached["round"].max())
    new_rows, no = [], last + 1
    network_ok = True
    while True:
        try:
            r = requests.get(RAW_URL.format(no), timeout=10)
        except requests.RequestException:
            network_ok = False
            break
        if r.status_code != 200:
            break  # 다음 회차가 아직 없음 = 최신 상태
        new_rows.append(_row_from_json(r.json()))
        no += 1

    if new_rows:
        cached = merge_history(cached, pd.DataFrame(new_rows, columns=COLUMNS))
        os.makedirs(DATA_DIR, exist_ok=True)
        cached.to_csv(CACHE_PATH, index=False)

    warning = None
    if not network_ok:
        warning = f"네트워크에 연결할 수 없어 캐시된 {last}회차 기준 데이터로 표시합니다."
    return cached, warning
