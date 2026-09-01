# -*- coding: utf-8 -*-
"""예측 알고리즘 실험실 (Prediction Lab).

프로토콜:
- Walk-forward: 회차 t 예측에는 t 이전 데이터만 사용 (미래정보 누출 차단)
- Validation(600~936회): 전 후보 평가 + 파라미터 튜닝 → 최고 1개 선정
- Test(937~1236회): 선정된 승자만 단 한 번 평가 — 이것만 공식 성적
- 유의성: 랜덤 기대 0.8개 대비 정규근사 검정 + 후보 수 Bonferroni 보정

실행: python experiments/predict_lab.py
"""
import os
import sys
from datetime import date

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import RandomForestClassifier

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "history.csv")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"results_{date.today():%Y%m%d}.txt")

VALID_START, VALID_END = 600, 936    # 후보 선정 구간 (회차)
TEST_START, TEST_END = 937, 1236     # 최종 평가 구간 (승자만)

E_HITS = 6 * 6 / 45                                  # 0.8
VAR_HITS = 6 * (6/45) * (39/45) * (39/44)            # 초기하분포 분산 ≈ 0.6145
RNG = np.random.default_rng(42)

# ---------- 데이터 및 상태 준비 ----------

df = pd.read_csv(CSV)
N_ROUNDS = len(df)
draws = df[["n1", "n2", "n3", "n4", "n5", "n6"]].to_numpy()          # (N,6)
P = np.zeros((N_ROUNDS, 45), dtype=np.int8)                          # 출현 행렬
for i, row in enumerate(draws):
    P[i, row - 1] = 1
CUM = np.vstack([np.zeros(45, dtype=np.int32), P.cumsum(axis=0)])    # CUM[i] = 0..i-1행 합

WINDOWS = [10, 26, 52, 104]
EWMA_ALPHAS = [0.02, 0.05, 0.10]


def win_freq(r_idx: int, w: int) -> np.ndarray:
    """r_idx(0-based 행) 예측 시점에 사용 가능한 최근 w회 출현 횟수 (행 r_idx-w .. r_idx-1)."""
    lo = max(0, r_idx - w)
    return (CUM[r_idx] - CUM[lo]).astype(float)


# 순차 상태: gap, ewma, 동시출현 전이행렬 — 행을 걸어가며 갱신
gap_state = np.full(45, 200.0)
ewma_state = {a: np.full(45, 6 / 45) for a in EWMA_ALPHAS}
cooc_C = np.ones((45, 45))          # 라플라스 스무딩
cooc_cnt = np.full(45, 2.0)

FEAT_NAMES = ([f"freq_{w}" for w in WINDOWS] + ["freq_all"] + ["gap"]
              + [f"ewma_{a}" for a in EWMA_ALPHAS] + ["cooc"])
features = np.zeros((N_ROUNDS, 45, len(FEAT_NAMES)))

for i in range(N_ROUNDS):
    cols = [win_freq(i, w) for w in WINDOWS]
    cols.append(CUM[i].astype(float) / max(i, 1))
    cols.append(gap_state.copy())
    for a in EWMA_ALPHAS:
        cols.append(ewma_state[a].copy())
    if i >= 1:
        prev = draws[i - 1] - 1
        cooc = (cooc_C[prev] / cooc_cnt[prev, None]).mean(axis=0)
    else:
        cooc = np.full(45, 6 / 45)
    cols.append(cooc)
    features[i] = np.column_stack(cols)

    # 상태 갱신 (i행 결과 반영 → i+1행 예측에 사용됨)
    hit = P[i].astype(bool)
    gap_state[hit] = 0
    gap_state[~hit] += 1
    for a in EWMA_ALPHAS:
        ewma_state[a] = (1 - a) * ewma_state[a] + a * hit
    if i >= 1:
        for m in draws[i - 1] - 1:
            cooc_C[m, draws[i] - 1] += 1
            cooc_cnt[m] += 1


def top6(scores: np.ndarray) -> set:
    return set(np.argsort(scores)[::-1][:6] + 1)


def z_of(col: np.ndarray) -> np.ndarray:
    return (col - col.mean()) / (col.std() + 1e-9)


# ---------- 후보 알고리즘 (이름 -> r_idx에서 6개 번호 집합) ----------

def make_window_algo(w):
    fi = FEAT_NAMES.index(f"freq_{w}")
    return lambda i: top6(features[i, :, fi])

def make_ewma_algo(a):
    fi = FEAT_NAMES.index(f"ewma_{a}")
    return lambda i: top6(features[i, :, fi])

ALGOS = {
    "핫넘버(전체빈도)": lambda i: top6(features[i, :, FEAT_NAMES.index("freq_all")]),
    "콜드(장기미출현)": lambda i: top6(features[i, :, FEAT_NAMES.index("gap")]),
    "동시출현 마르코프": lambda i: top6(features[i, :, FEAT_NAMES.index("cooc")]),
    "종합점수(2단계)": lambda i: top6(
        z_of(features[i, :, FEAT_NAMES.index("freq_52")])
        + z_of(features[i, :, FEAT_NAMES.index("gap")])
        + z_of(features[i, :, FEAT_NAMES.index("cooc")])),
}
for w in WINDOWS:
    ALGOS[f"핫넘버(최근{w})"] = make_window_algo(w)
for a in EWMA_ALPHAS:
    ALGOS[f"EWMA(α={a})"] = make_ewma_algo(a)

# ML: 20회차마다 재학습하는 RandomForest (번호별 이진 분류, 확률 top6)
ML_RETRAIN_EVERY = 20
ML_TRAIN_MIN = 150

class MLAlgo:
    def __init__(self):
        self.model = None
        self.trained_upto = -1

    def predict(self, i: int) -> set:
        if self.model is None or i - self.trained_upto >= ML_RETRAIN_EVERY:
            X = features[ML_TRAIN_MIN:i].reshape(-1, len(FEAT_NAMES))
            y = P[ML_TRAIN_MIN:i].ravel()
            self.model = RandomForestClassifier(
                n_estimators=100, max_depth=6, n_jobs=-1, random_state=0)
            self.model.fit(X, y)
            self.trained_upto = i
        proba = self.model.predict_proba(features[i])[:, 1]
        return top6(proba)

ml = MLAlgo()
ALGOS["ML(RandomForest)"] = ml.predict


# ---------- 평가 ----------

def evaluate(algo_fn, start_round: int, end_round: int) -> np.ndarray:
    hits = []
    for r in range(start_round, end_round + 1):
        i = r - 1
        picks = algo_fn(i)
        hits.append(len(picks & set(draws[i])))
    return np.array(hits, dtype=float)


def significance(hits: np.ndarray, n_candidates: int = 1):
    se = np.sqrt(VAR_HITS / len(hits))
    zval = (hits.mean() - E_HITS) / se
    p_raw = 1 - stats.norm.cdf(zval)          # 단측: 랜덤보다 나은가
    p_adj = min(1.0, p_raw * n_candidates)    # Bonferroni
    return zval, p_raw, p_adj


lines = []
def log(s=""):
    print(s, flush=True)
    lines.append(s)

log(f"=== 예측 알고리즘 실험실 — {date.today()} ===")
log(f"데이터: 1~{N_ROUNDS}회 | Validation {VALID_START}~{VALID_END} | Test {TEST_START}~{TEST_END}")
log(f"랜덤 기대값: 평균 {E_HITS:.4f}개/회, 3개+ 적중 2.38%")
log()

# 1) Validation: 전 후보 평가
log(f"[1] Validation ({VALID_START}~{VALID_END}회, {VALID_END-VALID_START+1}회 예측)")
log(f"    {'알고리즘':<18}{'평균적중':>9}{'3+적중률':>9}")
val_results = {}
for name, fn in ALGOS.items():
    if name == "ML(RandomForest)":
        ml.model, ml.trained_upto = None, -1
    h = evaluate(fn, VALID_START, VALID_END)
    val_results[name] = h
    log(f"    {name:<18}{h.mean():>9.4f}{(h>=3).mean()*100:>8.2f}%")

# 랜덤 기준선 (validation, 100장/회 시뮬레이션)
rh = np.array([
    np.mean([len(set(RNG.choice(np.arange(1, 46), 6, replace=False)) & set(draws[r-1]))
             for _ in range(100)])
    for r in range(VALID_START, VALID_END + 1)])
log(f"    {'랜덤(기준선)':<18}{rh.mean():>9.4f}")
log()

winner = max(val_results, key=lambda k: val_results[k].mean())
n_cand = len(ALGOS)
log(f"[2] 선정: '{winner}' (validation 평균 {val_results[winner].mean():.4f}개, 후보 {n_cand}개 중 1위)")
log()

# 2) Test: 승자만 단 한 번
if winner == "ML(RandomForest)":
    ml.model, ml.trained_upto = None, -1
    # test 직전까지 학습된 상태로 시작하도록 validation 구간을 한 번 걸어줌
    evaluate(ALGOS[winner], VALID_START, TEST_START - 1)
th = evaluate(ALGOS[winner], TEST_START, TEST_END)
zval, p_raw, p_adj = significance(th, n_cand)
log(f"[3] Test ({TEST_START}~{TEST_END}회, {len(th)}회 예측) — 공식 성적 (승자만 평가)")
log(f"    평균 적중: {th.mean():.4f}개  (랜덤 기대 {E_HITS:.4f})")
log(f"    3개+ 적중: {(th>=3).mean()*100:.2f}%  (랜덤 기대 2.38%)")
log(f"    z={zval:.2f}, p(단측)={p_raw:.3f}, Bonferroni 보정 p={p_adj:.3f} (후보 {n_cand}개)")
log()

verdict_win = p_adj < 0.05
if verdict_win:
    log("[판정] 승자가 test에서 랜덤을 통계적으로 유의하게 이겼습니다. 앱에 예측 모드 통합을 검토하세요.")
else:
    log("[판정] 승자도 test에서 랜덤과 통계적으로 구분되지 않았습니다.")
    log("       validation 1위는 후보 중 우연히 앞선 것을 골랐을 가능성이 높으며,")
    log("       이는 '과거 데이터에 예측력이 없다'는 전 회차 검증과 일치하는 결과입니다.")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print(f"\nsaved -> {OUT}")
