# YJ-Quant Dashboard 프로젝트 작업 요약

> 작성일: 2026-04-06

---

## 1. 프로젝트 개요

**목표**: `yj-wade-quant` FastAPI 서비스 아키텍처 기반으로 퀀트 알고리즘을 고도화하고,
Docker 없이 Streamlit 독립 실행 대시보드로 즉시 시각화

**실행 방법**:
```bash
# 방법 1: 더블클릭
run_dashboard.bat

# 방법 2: 터미널
python -m streamlit run streamlit_app.py

# 접속
# PC:     http://localhost:8501
# 모바일: http://192.168.219.117:8501  (같은 WiFi)
# 외부:   ngrok http 8501
```

---

## 2. 고도화 작업 4종

### 2-1. T+1 지연 실행 버그 수정
- **문제**: 전일 지표로 상태 결정 후 당일 수익 적용이 안 되던 버그
- **수정**: `.shift(1)`로 전일 신호 컬럼(`_s_VIX`, `_s_CCI` 등) 생성
- **관련 파일**: `backend/services/beta_strategy.py`, `streamlit_app.py`

```python
for col in ["VIX", "CCI", "RSI", "MDD", "Disp", "macro_score"]:
    if col in data.columns:
        data[f"_s_{col}"] = data[col].shift(1)
data = data.dropna(subset=["MA_200", "_s_MDD"]).copy()
```

### 2-2. 나스닥/S&P500 스위칭 + AlphaStrategy

**Beta 전략 NDQ 지원** (`backend/services/beta_strategy.py`):
- `"index": "snp"` → `^GSPC` + `^VIX`
- `"index": "ndq"` → `^IXIC` + `^VXN`

**Alpha 전략** (`backend/services/alpha_strategy.py`):
- Panic 구간에서 레버리지 지수 대신 시총 Top10 낙폭과대 개별주 매집
- SP_Spread_L 역가중 방식
- 연도별 Top10 종목 히스토리 하드코딩 (2000~2026)

```python
# Panic 매수: CMA → yj_alpha 바스켓
buy_a = min((yj_cs * dratio) / params["periodic_denom"], yj_cs)
yj_alpha += buy_a; yj_cs -= buy_a
```

### 2-3. WFV (Walk-Forward Validation) 엔진

**파일**: `backend/services/wfv_engine.py`

- IS 4년 Grid Search (128조합, Calmar Ratio 기준 최적화)
- OOS 1년 (이전 잔고/상태 상속 → 복리 왜곡 없음)
- 내장 Permutation Test (p-value 산출)

```python
class WFVEngine:
    def __init__(self, is_years=4, oos_years=1, param_grid=None):
    
    def run(self, full_data, strategy_type="beta", index="snp"):
        # IS 최적화 → OOS 실행 반복 (상태 상속)
        for fold_idx in range(n_folds):
            best_params = self._optimize_is(is_data)
            oos_result, inherited_state = self._run_oos(oos_data, inherited_state)
```

**WFV 그리드 (128조합)**:
```python
_WFV_GRID = {
    "vix_panic":    [25, 30],
    "mdd_panic":    [-0.12, -0.15],
    "cci_bull":     [50, 100],
    "cci_bear":     [-50, -100],
    "rsi_bull":     [70, 90],
    "rsi_bear":     [40, 60],
    "panic_period": [1, 5],
}
```

### 2-4. 매크로 분류기 + Permutation Test

**매크로 분류기** (`backend/services/macro_classifier.py`):

| Factor | 조건 | 점수 |
|--------|------|------|
| 금리차 역전 | 10Y - 3M < 0 | +1 |
| VIX 과열 | VIX Z-score > 1.5 (504일) | +1 |
| 유동성 경색 | SPY 60일 수익률 - HYG 60일 수익률 > 5% | +1 |

총점 0~3점 → `macro_threshold`(기본 2) 이상이면 레버리지 게이팅

**Permutation Test** (`backend/services/optimizer.py`):
```python
class PermutationTest:
    def run(self, equity_curve, market_rets, n_permutations=1000):
        # 레버리지 타이밍 1000회 셔플 → null 분포
        p_value = np.mean(null_dist >= actual_ret)
        # p < 0.05 → 레버리지 타이밍에 유의미한 알파 존재
```

---

## 3. Streamlit 대시보드 구조

**파일**: `streamlit_app.py` (~900줄)

### Tab 1: 오늘의 행동 지침
- 현재 레짐 (Bull / Bear / Panic)
- VIX / MDD / CCI / RSI / 매크로점수 실시간 표시
- CMA 잔고 시뮬레이션
- **오늘 행동 지침** (매수/유지/방어) 박스
- 레짐 전환 이력 차트

### Tab 2: 백테스트
- Beta(SNP/NDQ) / Alpha 선택
- 파라미터 슬라이더
- 자산 곡선 / Drawdown / CMA 잔고 / 레짐 / 연도별 수익 차트

### Tab 3: WFV 검증
- IS/OOS 연수 설정
- 진행 바
- 윈도우별 IS/OOS 성과 테이블
- Permutation Test p-value 표시

### Tab 4: 전략 비교
- Beta SNP vs NDQ vs Alpha 동시 비교
- 정규화 자산 곡선 + 성과 테이블

---

## 4. 수정된 버그

| # | 버그 | 원인 | 수정 |
|---|------|------|------|
| 1 | Tab 1 레짐 감지 오류 | `_decide_state("Bull", ...)` 단발 판단 | `run_beta` 전체 이력 실행 후 `final_state` 사용 |
| 2 | `p_mdd` 미정의 변수 | 변수 제거 후 잔존 참조 | `abs(mdd)`로 교체 |
| 3 | `run_beta` 중복 호출 | Tab 1 상단/하단 이중 실행 | 하단 중복 제거 |
| 4 | `streamlit run` 명령 실패 | Windows PATH 미등록 | `python -m streamlit run` 사용 |

---

## 5. 파일 구조

```
Quant_dashboard/
├── streamlit_app.py              # Streamlit 대시보드 (메인)
├── run_dashboard.bat             # 더블클릭 실행 스크립트
├── requirements_streamlit.txt   # 의존성
├── .streamlit/
│   └── config.toml              # 다크테마 + 0.0.0.0 바인딩
└── yj-wade-quant/
    └── backend/
        ├── services/
        │   ├── beta_strategy.py   # T+1 지연 + NDQ/SNP 스위칭 (재작성)
        │   ├── alpha_strategy.py  # Alpha 전략 (신규)
        │   ├── backtester.py      # NDQ/Alpha 지원 (수정)
        │   ├── wfv_engine.py      # WFV 엔진 (신규)
        │   ├── macro_classifier.py # 매크로 분류기 (신규)
        │   └── optimizer.py       # Permutation Test 추가
        ├── schemas/
        │   └── backtest.py        # WFV/Permutation/Macro 스키마 추가
        ├── api/v1/
        │   ├── backtest.py        # /wfv, /permutation-test, /macro-status 엔드포인트
        │   └── market.py          # ?index=ndq 지원
        └── core/
            └── seed.py            # 3개 전략 시드 (SNP/NDQ/Alpha)
```

---

## 6. 시드 전략 3종

| 전략명 | 타입 | 특징 |
|--------|------|------|
| YJAlgo v7.1 - S&P500 (Beta) | beta | VIX 25 / CCI ±50 / RSI 70,60 |
| YJAlgo v7.1 - Nasdaq (Beta) | beta | VXN 28 / CCI ±80 / MDD Threshold 상향 |
| YJAlgo Alpha - S&P500 Top10 | alpha | Panic 시 시총 Top10 낙폭과대 매집 |

---

## 7. 향후 과제

- [ ] **Docker 이전**: Streamlit 앱을 yj-wade-quant 서비스에 통합
- [ ] **WFV Alpha 완전 지원**: 현재 내부에서 Beta로 대체 실행 중
- [ ] **Next.js 프론트엔드**: WFV / Permutation Test / 매크로 UI 미반영
- [ ] **실시간 데이터**: 현재 yfinance 일봉 기준, 장중 데이터 미지원
