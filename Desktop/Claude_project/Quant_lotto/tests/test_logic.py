# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import pytest

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lotto_logic as logic
from lotto_data import COLUMNS, merge_history


# ---------- 등수 판정 ----------

DRAW = {1, 2, 3, 4, 5, 6}
BONUS = 7

@pytest.mark.parametrize("picks,expected", [
    ({1, 2, 3, 4, 5, 6}, 1),      # 6개 일치 → 1등
    ({1, 2, 3, 4, 5, 7}, 2),      # 5개 + 보너스 → 2등
    ({1, 2, 3, 4, 5, 45}, 3),     # 5개 → 3등
    ({1, 2, 3, 4, 44, 45}, 4),    # 4개 → 4등
    ({1, 2, 3, 43, 44, 45}, 5),   # 3개 → 5등
    ({1, 2, 42, 43, 44, 45}, 0),  # 2개 → 낙첨
    ({40, 41, 42, 43, 44, 45}, 0),
])
def test_rank_of(picks, expected):
    assert logic.rank_of(picks, DRAW, BONUS) == expected


def test_backtest_combo_counts():
    df = pd.DataFrame([
        {"n1": 1, "n2": 2, "n3": 3, "n4": 4, "n5": 5, "n6": 6, "bonus": 7},
        {"n1": 1, "n2": 2, "n3": 3, "n4": 40, "n5": 41, "n6": 42, "bonus": 8},
    ])
    result = logic.backtest_combo([1, 2, 3, 4, 5, 6], df)
    assert result[1] == 1   # 첫 회차 1등
    assert result[5] == 1   # 둘째 회차 3개 일치 → 5등


# ---------- 입력 검증 ----------

def test_validate_picks():
    assert logic.validate_picks([1, 2, 3, 4, 5, 6]) is None
    assert logic.validate_picks([1, 2, 3, 4, 5]) is not None       # 5개
    assert logic.validate_picks([1, 1, 2, 3, 4, 5]) is not None    # 중복
    assert logic.validate_picks([0, 2, 3, 4, 5, 6]) is not None    # 범위 밖
    assert logic.validate_picks([46, 2, 3, 4, 5, 6]) is not None


# ---------- EV 점수 ----------

def test_ev_score_bounds():
    for combo in [[1, 2, 3, 4, 5, 6], [40, 41, 42, 43, 44, 45], [7, 13, 22, 28, 30, 31]]:
        score, reasons = logic.ev_score(combo)
        assert 0 <= score <= 100
        assert len(reasons) == 4

def test_ev_score_extremes():
    # 최악(인기 조합): 생일범위 6개, 연속수 없음, 40번대 없음, 합계 인기구간
    worst, _ = logic.ev_score([3, 8, 15, 21, 26, 31])   # 합=104
    assert worst == 0
    # 최선(비인기 조합): 연속수 있음, 생일범위 0개, 40번대 있음, 합계 구간 밖
    best, _ = logic.ev_score([37, 38, 40, 42, 43, 45])  # 합=245
    assert best == 100

def test_ev_consec_only_signal():
    with_consec, _ = logic.ev_score([2, 3, 15, 22, 28, 30])
    without, _ = logic.ev_score([2, 5, 15, 22, 28, 30])
    assert with_consec - without == logic.W_CONSEC


# ---------- 조합 생성 ----------

def test_generate_combos():
    rng = np.random.default_rng(0)
    combos = logic.generate_combos(5, min_score=50, rng=rng)
    assert len(combos) == 5
    for nums, score, reasons in combos:
        assert logic.validate_picks(nums) is None
        assert score >= 50
        assert nums == sorted(nums)


# ---------- 증분 병합 ----------

def _row(rnd, nums, bonus=7):
    base = {"round": rnd, "date": "2026-01-01", "bonus": bonus,
            "first_winners": 10, "first_prize": 1, "total_sales": 1}
    base.update({f"n{i+1}": n for i, n in enumerate(sorted(nums))})
    return base

def test_merge_history():
    cached = pd.DataFrame([_row(1, [1, 2, 3, 4, 5, 6]), _row(2, [7, 8, 9, 10, 11, 12])], columns=COLUMNS)
    new = pd.DataFrame([_row(2, [7, 8, 9, 10, 11, 13]), _row(3, [1, 5, 9, 13, 17, 21])], columns=COLUMNS)
    merged = merge_history(cached, new)
    assert list(merged["round"]) == [1, 2, 3]          # 정렬 + 중복 제거
    assert merged.loc[merged["round"] == 2, "n6"].iloc[0] == 13  # 신규 우선


# ---------- 통계 ----------

def test_predict_algorithms():
    rows = [_row(i, np.random.default_rng(i).choice(np.arange(1, 46), 6, replace=False)) for i in range(1, 121)]
    df = pd.DataFrame(rows, columns=COLUMNS)
    preds = logic.predict_algorithms(df)
    assert len(preds) == 6
    for algo in preds:
        assert logic.validate_picks(algo["picks"]) is None   # 유효한 6개 번호
        assert algo["picks"] == sorted(algo["picks"])
    # 콜드는 최근에 안 나온 번호를 골라야 함: 마지막 회차 번호와 겹치지 않아야 정상
    cold = next(a for a in preds if "콜드" in a["name"])
    last_nums = set(df.iloc[-1][["n1", "n2", "n3", "n4", "n5", "n6"]])
    assert not (set(cold["picks"]) & last_nums)


def test_freq_table_and_stats():
    rows = [_row(i, np.random.default_rng(i).choice(np.arange(1, 46), 6, replace=False)) for i in range(1, 101)]
    df = pd.DataFrame(rows, columns=COLUMNS)
    ft = logic.freq_table(df)
    assert len(ft) == 45
    assert ft["출현횟수"].sum() == 600
    assert 0 <= logic.chi2_pvalue(df) <= 1
    ov = logic.prev_overlap_stats(df)
    assert ov["theoretical"] == pytest.approx(0.8)
