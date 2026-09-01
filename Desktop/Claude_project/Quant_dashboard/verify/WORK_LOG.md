# YJ-Quant Dashboard 작업 로그

## 프로젝트 개요

- **목적**: `Result_simulation_v1.3`, `YJalgo_v7.1_NDQ/SNP` 기능을 통합한 Streamlit 대시보드 구축
- **최종 파일**: `YJalgo_v8.6.txt` (app.py로 배포)
- **작업 기간**: 2026-04-13 ~ 2026-04-14

---

## 버전 히스토리

### v8.4 (기존)
- 7탭 Streamlit 대시보드 초안
- **발견된 버그 4종**:
  1. 적립 순서 오류 (수익 적용 전에 원금 추가 → 과대계상)
  2. `_state()` 매크로 우선순위 오류 (Panic 조건보다 macro 먼저 체크 → Panic 억제)
  3. CAGR 공식 오류 (거래일 기준 → 달력일 기준으로 수정 필요)
  4. Panic 에피소드 로그 누락

### v8.5
- 위 4종 버그 수정 + UI 개선 3종
- **잔존 버그 3종 발견** (v7.1 출력과 비교 후):

| 원인 | 증상 | 영향 |
|------|------|------|
| 원인 1: 웜업 누락 | Tab3에서 `bd = market_df[>=start_year]` 슬라이스 후 전달 → MA_200 warm-up 소실 | 2010년 Panic 에피소드 2건 누락, 초반 수익 손실 |
| 원인 2: 매크로 신호 | `calc_macro` 3요소 점수(수익률곡선+VIX Z-score+HYG스프레드) → 과잉 Bear 강제 | 71건 전환 (v7.1: 40건), CCI=198 강세구간에서도 Bear 강제 |
| 원인 3: 1일 시프트 | `add_ind()`의 `_s_` shift → 전환일 1일 지연 | 금요일 신호 → 월요일 발동, v7.1 대비 최대 3일 지연 |

### v8.6 (최종)
- 3종 버그 전부 수정 + 탭별 AI 해석 박스 추가

---

## v8.6 주요 변경사항

### [Fix-A] 웜업 복원
```python
# 변경 전 (v8.5 Tab3)
bd = market_df[market_df.index >= pd.Timestamp(f"{start_year}-01-01")]
run_beta(bd, params, budget)

# 변경 후 (v8.6 Tab3)
run_beta(market_df, params, budget, sim_start=f"{start_year}-01-01")

# run_beta 내부
def run_beta(data, params, budget, inh=None, sim_start=None, sim_end=None):
    df = add_ind(data)
    df = df.dropna(subset=["MA_200", "MDD"])   # 전체 데이터로 warm-up 계산
    if sim_start: df = df[df.index >= pd.Timestamp(sim_start)]  # 이후 필터링
```
- `run_grid`, `run_wfv`, `run_alpha` 동일하게 적용
- `fetch_start = f"{start_year-3}-01-01"` (웜업 3년치 확보)

### [Fix-B] 매크로 신호 제거
```python
# 변경 전 (v8.5)
def _state(cur, vix, cci, rsi, mdd, disp, macro, p):
    if vix>=p["vix_panic"] and mdd<=p["mdd_panic"]: return "Panic"
    if cur=="Panic": return "Bear" if (cci>0 and rsi>p["rsi_bear"]) else "Panic"
    if macro >= p.get("macro_threshold", 2): return "Bear"  # 과잉 Bear 유발
    ...
_BF = {"macro_threshold": 2}

# 변경 후 (v8.6)
def _state(cur, vix, cci, rsi, mdd, disp, p):  # macro 파라미터 삭제
    if vix>=p["vix_panic"] and mdd<=p["mdd_panic"]: return "Panic"
    if cur=="Panic": return "Bear" if (cci>0 and rsi>p["rsi_bear"]) else "Panic"
    # macro 조건 완전 제거
    if cur=="Bear": return "Bull" if (cci>p["cci_bull"] and rsi>p["rsi_bull"]) else "Bear"
    return "Bear" if (cci<p["cci_bear"] and disp<-3.0) else "Bull"
_BF = {}
```
- `fetch_macro()` 호출 제거 (함수 정의는 유지)
- `calc_macro()` 함수 삭제
- 데이터 로드 시 `macro_score`, `_s_macro_score` 컬럼 추가 제거

### [Fix-C] 1일 시프트 제거
```python
# 변경 전 (v8.5 add_ind)
for c in ["VIX","CCI","RSI","MDD","Disp"]:
    if c in df.columns: df[f"_s_{c}"] = df[c].shift(1)  # 삭제

# 변경 후 (v8.6 add_ind)
# _s_ 블록 완전 제거

# run_beta 내부 변경
vx = float(row.get("VIX",  15))   # 이전: row.get("_s_VIX", 15)
cc = float(row.get("CCI",   0))   # 이전: row.get("_s_CCI",  0)
rs = float(row.get("RSI",  50))   # 이전: row.get("_s_RSI", 50)
md = float(row.get("MDD",   0))   # 이전: row.get("_s_MDD",  0)
dp = float(row.get("Disp",  0))   # 이전: row.get("_s_Disp", 0)
```

### [New] 탭별 AI 해석 박스
```python
def _ai_box(title, bullets, accent="#00d084"):
    """계산 결과 기반 자동 해석 요약 박스"""
    ...
```
각 탭에 `_ai_tab1()` ~ `_ai_tab7()` 함수로 자동 해석 생성:
- 수치 기반 판단 (우수/양호/보통, 위험 수준)
- 전환 조건 안내
- 파라미터 조정 제안

---

## 정합성 검증 결과

### v8.5 vs v7.1 전환 로그 비교

| 항목 | v7.1 (Nasdaq) | v8.5 (S&P500) | v8.6 (예상) |
|------|--------------|--------------|------------|
| 총 상태 전환 수 | 40건 | 71건 | ~40건 |
| 2010년 전환 | 5건 (6/29 시작) | 0건 | 5건 복원 |
| 매크로 과잉 전환 | 0건 | 32건 | 0건 |
| 날짜 정합성 | 기준 | 1~3일 지연 | v7.1과 동일 |
| Panic 에피소드 | 13건 | 11건 | 13건 복원 |

### 1일 시프트 패턴 확인
| v8.5 날짜 | v7.1 날짜 | 설명 |
|-----------|-----------|------|
| 2011-08-05 | 2011-08-04 | +1일 |
| 2011-08-09 | 2011-08-08 | +1일 |
| 2016-02-08 | 2016-02-05 | +3일 (금→다음 월, 주말 건너뜀) |
| 2016-03-31 | 2016-03-30 | +1일 |

### 매크로 과잉 전환 예시 (v8.6에서 제거)
| 날짜 | 전환 | CCI | 비고 |
|------|------|-----|------|
| 2014-12-12 | Bull→Bear | 130.2 | 완전 강세 구간, 매크로=2만으로 강제 Bear |
| 2018-02-05 | Bull→Bear | 150.0 | 완전 강세 구간 |
| 2020-02-21 | Bull→Bear | 198.3 | 극단적 강세 구간 |
| 2020-09-04 | Bull→Bear | 162.6 | 강세 구간 |

### 최종 자산 비교
| 전략 | v7.1 (Nasdaq) | v8.5 (S&P500) |
|------|--------------|--------------|
| ETF+CMA | 55.52억 | 44.51억 |
| 격차 원인 | 기준 | 웜업 누락 + 매크로 과잉 Bear = ~11억 손실 |

---

## 알고리즘 정리

### 상태 머신 (v8.6 기준)
```
상태: Bull / Bear / Panic

전환 규칙:
  Bull → Bear  : CCI < cci_bear AND Disp < -3.0%
  Bull → Panic : VIX >= vix_panic AND MDD <= mdd_panic  (최우선)
  Bear → Bull  : CCI > cci_bull AND RSI > rsi_bull
  Bear → Panic : VIX >= vix_panic AND MDD <= mdd_panic
  Panic → Bear : CCI > 0 AND RSI > rsi_bear
```

### CMA 드레인 (Panic 시)
```
MDD 단계별 드레인 비율:
  1단계 (MDD >= threshold[0]): drain[0] 비율 매수
  2단계 (MDD >= threshold[1]): drain[1] 비율 매수
  3단계 (MDD >= threshold[2]): drain[2] 비율 매수

기본값 (S&P500): threshold=(0.45, 0.30, 0.15), drain=(1.0, 0.6, 0.4)
기본값 (Nasdaq): threshold=(0.55, 0.35, 0.15), drain=(1.0, 0.6, 0.4)
```

### 5종 전략 비교 (Tab5)
| 전략 | ETF 적립 | CMA | Panic 드레인 대상 |
|------|---------|-----|-----------------|
| 0. ETF Only | 18/18 (레버리지) | 없음 | - |
| 1. ETF+CMA | M/18 (레버리지) | 있음 | ETF |
| 2. TopN Only | TopN 18/18 | 없음 | - |
| 3. TopN+CMA | TopN M/18 | 있음 | TopN |
| 4. ETF→TopN | ETF M/18 (레버리지) | 있음 | TopN 개별주 |

`M` = `stock_ratio` (사이드바 1번 파라미터의 첫 번째 값, 기본 15)

---

## 파일 구조

```
verify/
├── YJalgo_v8.6.txt          ← 최종 버전 (이 파일)
├── YJalgo_v8.5.txt          ← 이전 버전 (참고용)
├── YJalgo_v8.4.txt          ← 원본 (참고용)
├── Result_simulation_v1.3.txt
├── YJalgo_v7.1_NDQ.txt
├── YJalgo_v7.1_SNP.txt
├── WORK_LOG.md              ← 이 파일
└── output/
    ├── Result_simulation/
    │   └── 상세로그_result_simulation.txt
    ├── YJalgo_v7.1_NDQ/
    │   └── 상세로그_v7.1.txt
    └── YJalgo_v8.5/
        ├── ETF+TOPN_result.csv
        ├── ETF_연도별 성과.csv
        ├── ETF_상태변경로그.csv
        ├── ETF_panic_상세로그2.csv
        └── ETF_panic_매수내역.csv
```

---

## 수정 이력 (버그 및 에러)

| 일시 | 파일 | 내용 |
|------|------|------|
| 2026-04-13 | v8.5 | 최초 작성 (Fix1~7 적용) |
| 2026-04-14 | v8.6 | Fix-A/B/C + AI 요약 추가 |
| 2026-04-14 | v8.6 | SyntaxError 수정: Unicode 마이너스(U+2212) → ASCII 하이픈(-) (line 106) |

---

## 향후 과제

1. **매크로 신호 재검증**: `calc_macro` (수익률곡선 역전 + VIX Z-score + HYG 스프레드) 3요소가 실제 시장 하락과 상관관계/인과관계가 있는지 통계 검증 후 v8.7에 선택적 재도입 검토
2. **GitHub 이식**: `https://github.com/bnabis93/yj-wade-quant` 에 `YJalgo_v8.6` → `app.py` 로 merge (gh CLI 설치 필요)
3. **실시간 검증**: v8.6 실행 후 출력 CSV를 `output/YJalgo_v8.6/` 폴더에 저장해 v7.1과 수치 직접 비교
