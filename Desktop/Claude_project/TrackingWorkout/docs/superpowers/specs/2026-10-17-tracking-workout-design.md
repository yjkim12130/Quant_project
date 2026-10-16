# TrackingWorkout — 점진적 과부하 트래커 설계 (v1)

- 작성일: 2026-10-17
- 원 요구사항: `../../../Requirement.txt`
- 상태: 설계 승인됨, 구현 계획 작성 전

## 1. 목적

매일 같은 운동을 반복하는 사용자(부부 2인)가

1. 점진적 과부하를 잘 실천하고 있는지 **시각화**로 확인하고,
2. 오늘 점진적 과부하를 달성하려면 운동(기구, 종류)별로 **얼마나 해야 하는지 목표**를 추천받는

모바일 앱. 남편은 주로 웨이트(안드로이드), 아내는 주로 유산소(아이폰).

## 2. 결정 사항 요약

| 항목 | 결정 | 이유 |
|---|---|---|
| 입력 시점 | 헬스장에서 휴대폰으로 세트마다 즉시 | 사용자 요구 |
| 플랫폼 | **PWA** (React + Vite + vite-plugin-pwa), Cloudflare Pages 배포 | 안드로이드·아이폰 한 코드, 비용 0, 오프라인 동작. 아이폰 네이티브는 연 $99 필요 |
| 데이터 공유 | **각자 폰에만 저장**, 동기화 없음 | 운동 종류가 달라 공유 필요성 낮음. db 계층 분리로 추후 확장 여지 |
| 저장소 | **IndexedDB (Dexie)** | 세트 단위 기록 누적, 인덱스 조회, localStorage 용량·삭제 위험 회피 |
| 그래프 | Recharts | React 친화 |
| 웨이트 기록 단위 | **세트별**, 세트 안에 **구간(segment)** 여러 개 허용(드롭) | 실패/드롭 세트 상세 분석 |
| 웨이트 추천 방식 | 운동별 선택: **더블 프로그레션**(기본) / **볼륨 증가** | 사용자 요구 |
| 유산소 강도 | 운동별로 강도 항목을 직접 정의(이름·단위·증가단위) | 기구마다 표시값이 다름 |
| 유산소 부가 기록 | 거리(km), 칼로리(kcal) — 선택 입력 | 사용자 요구 |
| 단위 | kg 고정 | YAGNI |
| 기반 스택 | 셈셈 병아리(`calculator_game/`)와 동일 툴체인 | 검증된 PWA·배포 흐름 재사용 |

## 3. 데이터 모델 (Dexie)

```ts
type ExerciseKind = 'weight' | 'cardio';

interface Exercise {
  id: string;                 // uuid
  equipment: string;          // 기구 이름
  name: string;               // 운동 종류   — (equipment, name) 유일
  kind: ExerciseKind;
  archived: boolean;
  restSeconds: number;        // 휴식 타이머 기본값, 기본 90
  createdAt: number;
  weight?: {
    progression: 'double' | 'volume';
    repMin: number;           // 기본 8
    repMax: number;           // 기본 12
    targetSets: number;       // 기본 3
    increment: number;        // kg, 기본 2.5
    volumeGrowthPct: number;  // 볼륨 방식 증가율, 2~5, 기본 3
  };
  cardio?: {
    metrics: { key: string; label: string; unit: string; step: number }[]; // 예: 속도 km/h 0.5, 경사 % 1
    primaryMetric: string;    // 올릴 강도 항목 key
    minMinutes: number;       // 기본 20
    maxMinutes: number;       // 기본 30
    timeStep: number;         // 분, 기본 2
  };
}

interface Session {           // 하루·한 운동의 기록
  id: string;
  exerciseId: string;
  date: string;               // YYYY-MM-DD (로컬)
  memo?: string;
  // 기록 시점의 추천 목표 스냅샷 — 배지 판정용 (추천 로직이 바뀌어도 과거 판정 유지)
  target?: WeightTarget | CardioTarget;
}

interface WeightSet {
  id: string;
  sessionId: string;
  order: number;
  segments: { weight: number; reps: number }[]; // length ≥ 1, 2 이상이면 드롭
}

interface CardioEntry {
  id: string;
  sessionId: string;
  minutes: number;
  intensity: Record<string, number>; // metric key → 값
  distanceKm?: number;
  kcal?: number;
}
```

인덱스: `exercises: id, &[equipment+name]`, `sessions: id, exerciseId, date, [exerciseId+date]`, `weightSets: id, sessionId`, `cardioEntries: id, sessionId`, `meta: key` (마지막 백업 시각 등).

같은 운동·같은 날짜 세션은 1개로 유지한다(같은 날 다시 기록하면 기존 세션에 세트 추가).

## 4. 추천 로직 (`src/core/`, 순수 함수)

기준 기록 = 해당 운동의 **오늘 이전 가장 최근 세션 1개**.

### 4.1 공통 지표

- **작업 무게 W**: 각 세트 첫 구간 무게의 최빈값(동률이면 큰 값).
- **유효 횟수**(세트별): 첫 구간 무게가 W일 때 그 구간 횟수, 아니면 0. 드롭 구간은 제외.
- **볼륨**: 모든 구간의 Σ(무게×횟수) — 드롭 포함.
- **e1RM**(Epley): `w × (1 + r/30)`, r=1이면 w. 세션 e1RM = 모든 구간 중 최댓값.
- **목표 무게 달성률**: Σ유효횟수 / (목표 세트 수 × 해당 세트 목표 횟수).
- **무게 반올림**: 증량 단위의 배수로 반올림.

### 4.2 웨이트 — 더블 프로그레션

| 지난번 결과 | 오늘 목표 |
|---|---|
| 목표 세트 수 이상의 세트가 모두 W에서 유효 횟수 ≥ repMax, 드롭 없음 | W + increment, 모든 세트 repMin |
| 그 외 | 같은 W, 세트 i 목표 = min(유효횟수ᵢ + 1, repMax) (유효횟수 0이면 repMin) |
| 드롭이 있던 세트 | 목표에 `dropHint` 표시: "W에서 n+1회 후 드롭" |
| 세트 수 < targetSets | 부족한 세트는 repMin 목표로 추가 |

예: repMax 12, 지난번 `[10×7→8×5], [10×12], [10×9]` → 오늘 `10kg × 8(드롭 힌트) / 12 / 10`.

### 4.3 웨이트 — 볼륨 증가

목표 볼륨 = 지난번 볼륨 × (1 + volumeGrowthPct/100). 두 안을 함께 제시한다.

- **횟수안**: 같은 W, targetSets 세트에 대해 지난번 유효 횟수에서 시작해 목표 볼륨에 도달할 때까지 마지막 세트부터 +1씩 배분.
- **무게안**: W + increment, 모든 세트 같은 횟수 r로, 볼륨 ≥ 목표가 되는 최소 r.

사용자는 기록 화면에서 둘 중 하나를 선택하고, 선택한 안으로 입력칸이 미리 채워진다.

### 4.4 유산소 — 시간 → 강도

주 강도 p = 지난번 `intensity[primaryMetric]`.

| 지난번 결과 | 오늘 목표 |
|---|---|
| minutes ≥ maxMinutes | p + step, minutes = minMinutes, 기타 강도 항목은 지난번 값 유지 |
| 그 외 | 같은 강도, minutes = min(지난번 + timeStep, maxMinutes) |

거리·칼로리는 추천에 쓰지 않고 그래프(분당 kcal, 평균 속도 = 거리/시간)에만 쓴다.

### 4.5 예외 규칙 (우선순위 순)

1. **첫 기록**: 추천 없음. 운동 설정 기본값(웨이트는 repMin, 무게 빈칸; 유산소는 minMinutes)만 채움.
2. **복귀**: 마지막 세션이 오늘로부터 14일 초과 → "지난번 그대로 반복"을 목표로 함.
3. **디로드 제안**(웨이트만): 최근 2개 세션의 e1RM이 모두 그 이전 세션들 중 최고 e1RM보다 낮으면, 정규 목표와 함께 대안 "W×0.9(반올림), repMin"을 **선택지로** 제시. 강제하지 않음.

### 4.6 과부하 실천 배지 (세션별)

- **▲ 달성**: 세션에 저장된 목표 스냅샷을 모두 충족
  - 더블: 각 목표 세트의 유효 횟수 ≥ 목표 횟수, 그리고 W ≥ 목표 무게
  - 볼륨: 볼륨 ≥ 목표 볼륨
  - 유산소: 주 강도 ≥ 목표 && 시간 ≥ 목표
- **＝ 유지**: 미달성이나 지난번 대비 하락 아님
- **▼ 하락**: 웨이트는 e1RM과 볼륨 **모두** 지난번보다 낮음 / 유산소는 같은 주 강도 이하에서 시간 감소
- 목표 스냅샷이 없는 세션(첫 기록)은 배지 없음.

홈 지표: **최근 4주 달성률** = ▲ 세션 수 / 배지가 있는 세션 수.

## 5. 화면

하단 탭 3개(오늘 / 기록·그래프 / 설정), 세로 고정, 한 손 조작, 큰 터치 영역.

1. **오늘**: 날짜, 4주 달성률, 최근 7일 내 기록한 운동 + 수동 추가한 운동 목록(각각 목표 요약, 최근 배지 5개, 완료 여부). 순서는 길게 눌러 변경. 백업 경고 배너(마지막 백업 14일 경과 시).
2. **기록**(오늘 → 운동 탭):
   - 상단: 목표, 지난번 기록과 날짜. 볼륨 방식은 횟수안/무게안 토글, 디로드 제안 시 대안 토글.
   - 웨이트: 완료된 세트 목록 + 현재 세트 입력(목표값 미리 채움, 무게 ±increment / 횟수 ±1 큰 버튼, 숫자 탭 시 직접 입력). **[무게 바꿈]** = 같은 세트에 구간 추가. **[✔ 완료]** = 즉시 DB 저장 + 휴식 타이머 시작. 세트 길게 누르면 수정/삭제.
   - 유산소: 시간, 정의된 강도 항목들, 거리, 칼로리 입력 후 저장.
   - **휴식 타이머**: 세트 완료 시 운동의 restSeconds로 카운트다운, ±15초 버튼, 건너뛰기. 종료 시 화면 표시 + 짧은 비프음 + `navigator.vibrate`(지원 기기만). 앱이 백그라운드여도 복귀 시 남은 시간이 정확하도록 종료 시각 기준으로 계산.
3. **기록·그래프**: 운동 목록 → 운동 상세
   - 웨이트: e1RM 추이 선(PR 마커), 날짜별 볼륨 누적 막대(목표 무게 구간 / 드롭 구간 색 구분), 목표 무게 달성률(%) 선.
   - 유산소: 시간 선 + 주 강도 선(보조축), 거리·칼로리 막대.
   - 기간 필터 4주 / 3개월 / 전체. 아래에 날짜별 기록 목록 + 배지.
4. **설정**: 운동 추가/수정/숨김(기구 이름, 운동 종류, 웨이트/유산소, 추천 방식과 파라미터, 유산소 강도 항목 정의, 휴식 시간), JSON 백업 내보내기/가져오기, 앱 정보.

## 6. 코드 구조

```
TrackingWorkout/
  src/core/            React·DB 비의존 순수 로직
    metrics.ts         작업 무게, 유효 횟수, 볼륨, e1RM, 반올림
    progression/
      weightDouble.ts
      weightVolume.ts
      cardio.ts
      rules.ts         첫 기록·복귀·디로드 분기, recommend() 진입점
    badge.ts           배지 판정, 달성률
  src/db/              Dexie 스키마, repository, backup.ts
  src/ui/              screens/, components/, charts/, timer/
```

의존 방향: `ui → core`, `ui → db`. `core`는 `db`를 모르고 `db`는 추천을 모른다.

## 7. 오류 처리·데이터 안전

- 첫 실행 시 `navigator.storage.persist()` 요청.
- iOS Safari에서 standalone이 아니면 "공유 → 홈 화면에 추가" 안내 배너.
- 백업: 전체 DB를 `{ app: 'tracking-workout', version, exportedAt, data }` JSON으로 내보냄(Web Share API, 미지원 시 다운로드).
- 복원: app/version/스키마 검증 실패 시 거부하고 사유 표시. 통과 시 현재 데이터를 자동 백업 파일로 내보낸 뒤 **전체 교체**(트랜잭션).
- 입력 검증: 무게 ≥ 0, 횟수 ≥ 1 정수, 시간 > 0, (equipment, name) 중복 거부.

## 8. 테스트 (TDD)

- `core`: 4장 표의 각 행 + 예외 규칙 + 반올림 + 볼륨 두 안 + 유산소 강도 상승 + 배지 3종 + 달성률.
- `db`: fake-indexeddb로 저장·조회·같은 날 세션 병합·백업 왕복·잘못된 백업 거부.
- `ui`: Testing Library로 목표 미리 채움 → 완료 → 다음 세트, 드롭 구간 추가, 휴식 타이머(fake timers), 운동 등록.
- 배포: `npm run deploy` = 테스트 → 빌드 → Cloudflare Pages(검색엔진 비노출, 셈셈과 동일).

## 9. 범위 밖 (v1)

기기 간 동기화, 푸시 알림, 운동 루틴 템플릿, lb 단위, Capacitor 네이티브 패키징(추후 안드로이드 APK 원하면 별도 작업).
