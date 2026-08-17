# Quant_realestate 배포 스펙 v1

**작성일**: 2026-08-18
**목표**: 저평가 아파트 검색기(Quant_realestate)를 Streamlit Community Cloud에 배포하여 모바일·외부에서 접근 가능하게 한다.

## 배경

현재 앱은 로컬 전용(`streamlit run app.py`, 포트 8502)으로만 실행된다. `app.py`는 콜드스타트마다 `scoring/engine.py`가 원본 실거래 DB(`data/realestate.db`, 3GB, `trades_sale` 415만행·`trades_jeonse` 654만행)를 읽어 1~2분간 스코어링 패널을 실시간 계산하는 구조다. 이 DB는 `.gitignore`(`data/*.db`)로 이미 커밋 대상에서 제외되어 있다.

GitHub는 파일당 100MB를 초과하면 일반 커밋을 거부하고, Streamlit Community Cloud 무료 티어는 앱당 약 1GB RAM으로 제한된다. 3GB 원본 DB는 이 두 제약 어느 쪽으로도 통과할 수 없다. 따라서 원본 DB가 아니라 **앱이 실제로 소비하는 계산된 결과물만** 압축된 형태로 배포 대상에 포함시킨다.

## 배포 대상 결정 (승인 완료)

- 배포 앱: Quant_realestate 1개 (다른 앱들은 이번 스코프 밖)
- GitHub: 기존 `github.com/yjkim12130/Quant_project` public 모노레포, `Quant_realestate/` 서브디렉토리 그대로 사용 (별도 레포 분리 안 함)
- Streamlit Cloud "Main file path": `Quant_realestate/app.py`
- 앱 접근: 완전 공개 링크 (`https://<앱이름>.streamlit.app`), 별도 인증/비밀번호 게이트 없음

## 아키텍처

```
[로컬 개발 환경]                         [Streamlit Community Cloud]
data/realestate.db (3GB, gitignored)     data/realestate.db 없음
        |                                        |
  scoring/engine.py 라이브 계산            app.py의 load_*() 함수가
  (기존 동작 그대로 유지)                  raw DB 부재 감지 →
        |                                  data/snapshot/*.parquet 로드
        v                                        ^
  scripts/export_snapshot.py  ---(커밋+푸시)---→  data/snapshot/*.parquet
  (수동 실행, 결과물만 추출)                (GitHub에 커밋되는 유일한 데이터)
```

### 신규 컴포넌트

**`scripts/export_snapshot.py`** (신규)
로컬에서 원본 3GB DB를 대상으로 다음을 1회 실행하고 결과를 `data/snapshot/`에 Parquet으로 저장한다:
- `scoring.engine.build_scored_panel()` 결과 → `data/snapshot/panel.parquet`
- `scoring.market_context`의 원본 거래 의존 시계열(자체 시장 전세가율 등, 예: `own_apt_index`류) → `data/snapshot/market_series.parquet`
- 이미 작은 독립 테이블(`complex_coords`, `station_node`, `station_edge`, `complex_transit_time`, `supply_presale`, `macro_series`)은 재계산 없이 그대로 복사 → `data/snapshot/*.parquet` 각각

구현 태스크 단계에서 정확한 함수 목록은 `app.py`의 `load_*()` 캐시 함수들이 실제로 무엇을 호출하는지 전수 확인해 확정한다(현재 확인된 것: `load_panel`→`build_scored_panel`, `load_assets`→`market_context.leading_apt_index`/`own_apt_index`, `load_transit_times`/`load_complex_coords`/`load_supply`→각각 독립 테이블).

**`app.py`의 로더 함수 수정** (기존 파일 수정)
각 `@st.cache_data` 로더 함수에 분기 추가:
```
원본 DB(data/realestate.db) 존재? → 기존처럼 라이브 계산/조회
없음(클라우드) → data/snapshot/*.parquet에서 대응 테이블 직접 로드
```
로컬 개발 동작은 전혀 바뀌지 않는다 — 원본 DB가 있는 한 항상 라이브 경로를 탄다.

**`.gitignore` 조정**
`data/*.db`는 유지하되, `data/snapshot/`은 커밋 대상에 포함되도록 예외 처리 필요(현재 `data/raw/`만 별도 제외 규칙이 있고 `data/` 전체를 막는 규칙은 없으므로 `snapshot/*.parquet`은 기본적으로 커밋 가능 — 실제 스테이징 시 확인).

## 크기 목표

단지 16,957개 × 최근 수년 월별 집계 기준 Parquet(컬럼 압축)으로 수십MB 예상. `export_snapshot.py` 실행 후 실측하여:
- 50MB 이하: 그대로 진행
- 50~100MB: 진행 가능하나 트리밍 고려
- 100MB 초과: `Params`의 트레일링 윈도우(년수)를 줄여 재추출 (스코어링 로직 자체는 변경하지 않음, 스냅샷에 담는 기간만 조정)

## 데이터 갱신 워크플로 (수동, 실시간 아님)

1. 로컬에서 기존 배치 적재(`ingest/fetch_trades.py` 등) 재실행 → `data/realestate.db` 갱신
2. `python scripts/export_snapshot.py` 실행 → `data/snapshot/*.parquet` 갱신
3. `git add Quant_realestate/data/snapshot/` (targeted add, `-A` 금지) → 커밋 → 푸시
4. Streamlit Cloud가 push를 감지해 자동 재배포

이 프로젝트군의 기존 배치 적재 관행과 동일한 패턴이며, 실시간 API 연동을 배포 앱에 추가하지 않는다.

## 시크릿

`app.py`는 런타임에 외부 API를 호출하지 않는다(확인 완료 — `requests`/`api_keys` 참조 없음). 따라서 Streamlit Cloud의 "Secrets" 설정이 불필요하다. `config/api_keys.local.yaml`, `.streamlit/secrets.toml`은 계속 `.gitignore`로 제외되며 배포와 무관하게 로컬 적재용으로만 쓰인다.

## Git 안전 수칙

저장소 루트가 `C:\Users\yjkim`(홈 디렉토리 전체)이므로:
- 항상 `git add Quant_realestate/<구체적 경로>` 형태의 targeted add만 사용
- `git add -A`, `git add .` 절대 금지
- 커밋 전 `git status`로 스테이징된 파일이 `Quant_realestate/` 범위 내인지 확인

## 예산 정보 저장 금지 원칙 (변경 없음)

기존 확정 원칙 유지: 사이드바 예산 입력은 세션 한정, 어디에도 저장하지 않음. 배포 여부와 무관하게 이 원칙은 그대로 적용된다.

## 검증 기준

- `export_snapshot.py` 실행 성공 + 결과 Parquet 파일들이 100MB 이하
- 로컬에서 `data/realestate.db`를 임시로 이름 변경(또는 별도 클론)한 상태로 앱을 실행해 스냅샷 경로가 정상 동작하는지 확인(클라우드 환경 시뮬레이션)
- 원본 DB가 있는 상태에서 기존 라이브 경로가 그대로 동작하는지 회귀 확인(기존 pytest 스위트 통과)
- GitHub push 성공, Streamlit Cloud 배포 성공, 모바일 브라우저에서 공개 링크 접속 확인

## 스코프 밖

- 다른 앱(Quant_dashboard, ManageStock, Quant_lotto, Clone_Advisor) 배포는 별도 작업
- 실시간 API 연동을 배포 앱에 추가하는 것 (여전히 수동 배치 갱신)
- Family 6번 팩터(공급압력) 등 스코어링 로직 자체의 변경
