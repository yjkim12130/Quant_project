# 스코어링 알고리즘 명세 v1 (algo_spec_v1)

> 2026-08-14 브레인스토밍 세션(docs/brainstorm_algo_v1.md 안건 A~H)에서 확정.
> `scoring/engine.py` 구현의 기준 문서. 데이터 의존 파라미터는 §7 체크리스트 실측 후 확정.

## 1. 가격 시계열 구성 (안건 B)

- 관측 단위: **(단지, 면적밴드) × 월**
- 가격 지표: 해당 월 거래들의 **중위 ㎡당가** (`deal_amount / exclusive_area`의 median, 만원/㎡)
- 해제거래(`cancelled=1`)는 모든 지표 계산에서 제외
- 스무딩: **3개월 롤링 중위** → 그래도 결측이면 마지막 관측 **최대 6개월 이월**
- 이월 한도 초과 단지는 해당 월 스코어링 제외 (강제 보간 금지)
- 층 보정 없음 (v1)

```
price(c, b, t) = rolling_median_3m( median_sqm_price(c, b, t) ), ffill limit 6
  c=단지, b=면적밴드, t=월
```

## 2. Peer Group 정의 (안건 A)

```python
def make_group_key(complex_row) -> tuple:
    # v1: (법정동, 면적밴드, 연식밴드)
    # 폴백: 그룹 내 단지 < MIN_GROUP_COMPLEXES → (시군구, 면적밴드, 연식밴드)
    # 그래도 미달 → None (스코어링 제외)
```

- 면적밴드: `~60 / 60~85 / 85~` (전용면적 ㎡, 3구간)
- 연식밴드: `~10년 / 10~25년 / 25년~` (스코어링 시점 기준 경과년수, 동적 계산)
- `MIN_GROUP_COMPLEXES = 5` (기본값, 실측 후 조정)
- **교체 가능 인터페이스**: 그룹 정의는 이 함수 하나에만 존재해야 함. Phase 5에서 학군·역세권 축으로 교체 예정.
- 그룹 기준가: 그룹 내 단지들의 price의 **중위값** `group_price(g, t)`

## 3. 팩터 정의

### Factor1 — 상대가치 괴리율 (안건 C, 핵심)

```
ratio(c, t)  = price(c, t) / group_price(g(c), t)
rv_z(c, t)   = ( ratio(c, t) - mean(ratio(c, t-L..t-1)) ) / std(ratio(c, t-L..t-1))
```

- 해석: rv_z < 0 → 평소 그룹 내 위상 대비 저평가. 절대 ±5% 임계 사용 안 함.
- `L`(lookback, 기본 24개월)과 매수 임계(기본 -1.0σ)는 **그리드서치+WFV 대상**

### Factor2 — 전세가율 (안건 E)

```
jr(c, t)    = jeonse_price(c, t) / price(c, t)          # 동일 면적밴드 매칭
jr_z(c, t)  = jr의 자기 역사(L개월) 대비 z-score          # rv_z와 동일 프레임 재사용
```

- **점수**: jr_z > 0 (전세가율이 평소보다 상승 = 실사용 수요가 받치는 바닥) 가점
- **옵션 필터**: 사이드바 토글 "전세가율 X% 미만 제외" (기본 off, X 기본 50%)
- 전세 데이터 없는 단지: Factor2 점수 0 (중립) 처리, 커버리지는 §7-5로 실측

### Factor3 — 과열도/모멘텀 (안건 D)

```
dd(c, t)   = price(c, t) / rolling_max(price(c, ~t)) - 1     # 전고점 대비 DD (음수)
mom12(c,t) = price(c, t) / price(c, t-12) - 1                # 12개월 모멘텀
```

- 매수구간 판정: `dd < DD_THRESHOLD` (조정 충분) **AND** `mom12 > MOM_FLOOR` (추세가 하락 가속 아님)
- 추세 지속성 경고: dd 단독 사용 금지 — 반드시 mom12와 결합
- D3(거래량)·D4(전세가율 방향)는 v1 제외, 백테스트 검증 후 편입 검토

### Factor4/5 — 개발호재·세수 보너스 (안건 F의 3단계)

- `manual_catalysts.yaml` (Phase 5): 지역/단지별 ±보너스 점수, 고정 규칙 (최적화 대상 아님)
- 지방재정365 세수 개선율 (Phase 5): 상위/하위 구간 ±보너스, 고정 규칙

### Factor6 — 공급압력 / 매크로 레짐 (안건 H)

- Phase 6. 데이터 소스 재조사 후 설계. ECOS 기준금리 + 규제강도 → Bull/Bear/Panic 레짐, 레짐별 임계 스위칭.

## 4. 스코어 결합 (안건 F)

```
[1단계 하드필터]
  - 예산 범위 (Tab4, 세션 한정 수동 입력 — 어디에도 저장 금지)
  - 유동성: 이월 한도 내 가격 존재
  - (옵션) 전세가율 하한 필터
  - ⚠️ 해제 플래그: 최근 1년 해제비율 > CANCEL_FLAG_PCT 단지는 경고 표시 (제외 아님)

[2단계 핵심 랭킹]  score = z_norm(rv_z) + z_norm(과열도 스코어)   # 동일가중
[3단계 보너스]     score += catalyst_bonus + fiscal_bonus          # Phase 5부터
```

- 스크리너 표시: 🟢 강한 저평가 / 🟡 중립 / 🔴 고평가 (YJalgo 이모지 컨벤션 계승, 임계는 σ 기반)

## 5. 파라미터 대장

| 파라미터 | 기본값 | 성격 |
|---|---|---|
| 면적밴드 경계 | 60, 85㎡ | 고정 (확정) |
| 연식밴드 경계 | 10, 25년 | 고정 (확정) |
| MIN_GROUP_COMPLEXES | 5 | 실측 후 조정 (§7-1) |
| 롤링 윈도 / 이월 한도 | 3개월 / 6개월 | 실측 후 조정 (§7-1) |
| L (lookback) | 24개월 | **그리드서치+WFV** |
| rv_z 매수 임계 | -1.0σ | **그리드서치+WFV** |
| DD_THRESHOLD | -10% | **그리드서치+WFV** |
| MOM_FLOOR | -5% | **그리드서치+WFV** |
| CANCEL_FLAG_PCT | 10% | 고정, 실측 후 조정 (§7-4) |

과적합 방어 원칙: **그리드서치 대상은 위 4개를 초과하지 않는다.** 가중치는 최적화하지 않는다(동일가중 고정).

## 6. 백테스트 설계 (안건 G)

- **신호**: 시점 t에 하드필터 통과 + score 상위 N% (or rv_z < 임계)
- **성과**: t+1y / 2y / 3y 수익률. 벤치마크 = **소속 그룹 중위 수익률 대비 초과수익** (상승장 착시 제거)
- **누수 방지**: 시점 t 스코어는 **t-1개월까지의 데이터만** 사용 (실거래 신고 지연 30일 반영)
- **비용 모델** (`include_costs` 토글): 취득세(주택수 구간별)·중개보수·보유세 단순 모델, 양도세는 보유기간·1주택 비과세 가정 토글
- **검증 통계**: YJalgo `_perm` 이식 — 무작위 단지 선택 대비 초과수익 순열검정 p-value
- **WFV**: 학습 3년 → 검증 1년 롤링 (시점 60개 제약상 fold 수 적음을 인지하고 해석)

## 7. 적재 완료 직후 실측 체크리스트 (파라미터 확정용)

1. 단지×면적밴드별 월 거래건수 분포 → 롤링 윈도·MIN_GROUP_COMPLEXES 확정
2. `complex_name` 표기 변형/매매·전세 조인 성공률 → 정규화 규칙 필요 여부
3. rv_z 분포 지역 비교 (강남 vs 화성) → 임계 σ 타당성
4. 해제거래 비율 분포 → CANCEL_FLAG_PCT 확정
5. 전세가율 계산 가능 단지 비율 → Factor2 커버리지

## 8. 구현 순서 (scoring/engine.py)

1. `build_price_series()` — §1 (DB → 월 중위가 패널)
2. `make_group_key()` + `build_group_series()` — §2
3. `factor_rv()`, `factor_jeonse()`, `factor_overheat()` — §3
4. `combine_scores()` — §4
5. 체크리스트 §7 스크립트 (`scoring/diagnostics.py`)
6. 백테스트 §6 (`backtest/event_study.py`) — Phase 4
