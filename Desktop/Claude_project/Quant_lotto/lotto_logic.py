# -*- coding: utf-8 -*-
"""통계·EV점수·조합생성·검증 로직 (UI 무관, 단독 테스트 대상).

핵심 원칙(스파이크 검증 결과, docs/specs 참조):
- 어떤 조합이든 당첨 확률은 동일(1/8,145,060). 과거 데이터로 확률을 올릴 수 없다.
- EV 점수는 당첨 확률과 무관하며, 당첨됐을 때의 당첨금 분할 리스크만 반영한다.
"""
from math import comb

import numpy as np
import pandas as pd
from scipy import stats

TOTAL_COMBOS = comb(45, 6)  # 8,145,060
NUM_COLS = ["n1", "n2", "n3", "n4", "n5", "n6"]

# EV 가중치 — 스파이크에서 유의했던 신호만 (2026-08-14, 1~1236회 검증)
W_CONSEC = 30      # 연속수 포함: 유일한 통계적 유의 신호 (p=0.004)
W_BIRTHDAY = 30    # 31 이하(생일범위) 비중 낮음
W_FORTIES = 20     # 40번대 포함
W_SUM = 20         # 번호 합계가 인기 구간(100~170) 밖


def validate_picks(nums) -> str | None:
    """6개 번호 입력 검증. 문제 없으면 None, 있으면 한국어 오류 메시지."""
    nums = list(nums)
    if len(nums) != 6:
        return "번호는 정확히 6개를 입력해 주세요."
    if len(set(nums)) != 6:
        return "중복된 번호가 있습니다."
    if any((not isinstance(n, (int, np.integer))) or n < 1 or n > 45 for n in nums):
        return "번호는 1~45 사이의 정수여야 합니다."
    return None


def rank_of(picks: set, draw: set, bonus: int) -> int:
    """등수 판정. 1~5등, 낙첨은 0."""
    m = len(picks & draw)
    if m == 6:
        return 1
    if m == 5:
        return 2 if bonus in picks else 3
    if m == 4:
        return 4
    if m == 3:
        return 5
    return 0


def backtest_combo(picks, df: pd.DataFrame) -> dict:
    """이 조합이 과거 전 회차에서 몇 등에 몇 번 해당했을지."""
    picks = set(int(n) for n in picks)
    result = {r: 0 for r in range(1, 6)}
    draws = df[NUM_COLS].to_numpy()
    bonuses = df["bonus"].to_numpy()
    for row, bonus in zip(draws, bonuses):
        r = rank_of(picks, set(row), int(bonus))
        if r:
            result[r] += 1
    return result


def ev_score(picks) -> tuple[int, list[str]]:
    """독식 점수(0~100)와 근거. 당첨 확률과 무관 — 분할 리스크만 반영."""
    nums = sorted(int(n) for n in picks)
    score, reasons = 0, []

    has_consec = any(b - a == 1 for a, b in zip(nums, nums[1:]))
    if has_consec:
        score += W_CONSEC
        reasons.append(f"연속수 포함 +{W_CONSEC} — 사람들이 기피하는 유일한 통계적 유의 패턴(p=0.004)")
    else:
        reasons.append("연속수 없음 +0")

    le31 = sum(1 for n in nums if n <= 31)
    pts = round((6 - le31) / 6 * W_BIRTHDAY)
    score += pts
    reasons.append(f"생일범위(31 이하) {le31}개 +{pts} — 적을수록 겹칠 사람이 적음")

    if any(n >= 40 for n in nums):
        score += W_FORTIES
        reasons.append(f"40번대 포함 +{W_FORTIES}")
    else:
        reasons.append("40번대 없음 +0")

    total = sum(nums)
    if total < 100 or total > 170:
        score += W_SUM
        reasons.append(f"번호 합계 {total} — 인기 구간(100~170) 밖 +{W_SUM}")
    else:
        reasons.append(f"번호 합계 {total} — 인기 구간(100~170) 안 +0")

    return score, reasons


def generate_combos(n_games: int, min_score: int = 50, rng=None, max_tries: int = 20000):
    """균등 랜덤 생성 + EV 필터. (조합, 점수, 근거) 리스트 반환.

    생성 자체는 순수 균등 랜덤이므로 어떤 조합이 나와도 당첨 확률은 동일하다.
    """
    rng = rng or np.random.default_rng()
    out, seen = [], set()
    for _ in range(max_tries):
        if len(out) >= n_games:
            break
        combo = tuple(sorted(rng.choice(np.arange(1, 46), 6, replace=False).tolist()))
        if combo in seen:
            continue
        seen.add(combo)
        score, reasons = ev_score(combo)
        if score >= min_score:
            out.append((list(combo), score, reasons))
    return out


# ---------- 통계 (탭① 대시보드용) ----------

def freq_table(df: pd.DataFrame, last_n: int | None = None) -> pd.DataFrame:
    """번호별 출현 횟수와 기대값. last_n을 주면 최근 N회만."""
    sub = df.tail(last_n) if last_n else df
    counts = np.bincount(sub[NUM_COLS].to_numpy().ravel(), minlength=46)[1:]
    return pd.DataFrame({
        "번호": np.arange(1, 46),
        "출현횟수": counts,
        "기대값": len(sub) * 6 / 45,
    })


def chi2_pvalue(df: pd.DataFrame) -> float:
    """번호별 출현빈도의 균등분포 카이제곱 검정 p값 (높을수록 랜덤과 구분 불가)."""
    counts = np.bincount(df[NUM_COLS].to_numpy().ravel(), minlength=46)[1:]
    return float(stats.chisquare(counts).pvalue)


# ---------- 예측 실험실 (탭④용) ----------
# 주의: experiments/predict_lab.py 검증 결과 모든 알고리즘이 test에서 랜덤과 구분 불가.
# 재미용으로만 제공하며, UI에 해당 판정을 함께 표시한다.

def _top6_scores(scores: np.ndarray) -> list:
    return sorted((np.argsort(scores)[::-1][:6] + 1).tolist())


def _gap_scores(df: pd.DataFrame) -> np.ndarray:
    draws = df[NUM_COLS].to_numpy()
    gaps = np.full(45, float(len(draws)))
    for back, row in enumerate(draws[::-1], start=1):
        for n in row:
            if gaps[n - 1] == len(draws):
                gaps[n - 1] = back - 1
    return gaps


def _freq_scores(df: pd.DataFrame, last_n: int | None = None) -> np.ndarray:
    sub = df.tail(last_n) if last_n else df
    return np.bincount(sub[NUM_COLS].to_numpy().ravel(), minlength=46)[1:].astype(float)


def _ewma_scores(df: pd.DataFrame, alpha: float = 0.1) -> np.ndarray:
    e = np.full(45, 6 / 45)
    for row in df[NUM_COLS].to_numpy():
        hit = np.zeros(45)
        hit[row - 1] = 1
        e = (1 - alpha) * e + alpha * hit
    return e


def _cooc_scores(df: pd.DataFrame) -> np.ndarray:
    draws = df[NUM_COLS].to_numpy()
    C = np.ones((45, 45))
    cnt = np.full(45, 2.0)
    for i in range(1, len(draws)):
        for m in draws[i - 1] - 1:
            C[m, draws[i] - 1] += 1
            cnt[m] += 1
    prev = draws[-1] - 1
    return (C[prev] / cnt[prev, None]).mean(axis=0)


def predict_algorithms(df: pd.DataFrame) -> list[dict]:
    """실험실 알고리즘들의 다음 회차 예측. [{name, picks, val, test}] 반환.

    val/test는 2026-08-14 실험(600~936 / 937~1236회) 성적 — 랜덤 기대 0.800개.
    """
    gap = _gap_scores(df)
    f52 = _freq_scores(df, 52)
    cooc = _cooc_scores(df)

    def z(x):
        return (x - x.mean()) / (x.std() + 1e-9)

    return [
        {"name": "콜드 (장기미출현)", "picks": _top6_scores(gap),
         "val": 0.869, "test": 0.760, "note": "validation 1위였으나 test에서 랜덤 이하로 추락"},
        {"name": "핫넘버 (최근 52회)", "picks": _top6_scores(f52),
         "val": 0.840, "test": None, "note": "validation 2위"},
        {"name": "EWMA (α=0.1)", "picks": _top6_scores(_ewma_scores(df, 0.1)),
         "val": 0.831, "test": None, "note": "validation 3위"},
        {"name": "종합점수 (2단계)", "picks": _top6_scores(z(f52) + z(gap) + z(cooc)),
         "val": 0.831, "test": None, "note": "후보군 확률 → top-N 방식"},
        {"name": "동시출현 마르코프", "picks": _top6_scores(cooc),
         "val": 0.757, "test": None, "note": "직전 회차와 같이 나온 이력 기반"},
        {"name": "핫넘버 (전체)", "picks": _top6_scores(_freq_scores(df)),
         "val": 0.709, "test": None, "note": "validation 꼴찌"},
    ]


def prev_overlap_stats(df: pd.DataFrame) -> dict:
    """직전 회차 번호와의 겹침 실측 통계."""
    draws = [set(row) for row in df[NUM_COLS].to_numpy()]
    overlaps = np.array([len(draws[i] & draws[i - 1]) for i in range(1, len(draws))])
    return {
        "mean": float(overlaps.mean()),
        "theoretical": 6 * 6 / 45,
        "pct_ge1": float((overlaps >= 1).mean() * 100),
    }
