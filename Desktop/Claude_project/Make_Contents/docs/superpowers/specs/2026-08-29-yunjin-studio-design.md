# 윤진 Studio — 레시피 콘텐츠 생성 보조 에이전트 설계

- **작성일**: 2026-08-29
- **상태**: 설계 승인됨 (구현 계획 대기)
- **상위 문서**: `YJ_Content_Factory_SRS_윤진.html` (v2.0, 2026-06-09)
- **사용자**: 윤진 (콘텐츠 기획·촬영·제작) / **개발**: 영준

---

## 1. 배경

윤진 Studio SRS v2는 Phase A(촬영 전 가이드 A1~A5)와 Phase B(촬영 후 멀티플랫폼 B1~B5)로 구성된
2단계 파이프라인을 정의한다. 이 문서는 그중 **첫 실동작 버전**의 설계를 확정한다.

현재 확보된 실물 입력은 `Recipe/` 폴더의 레시피 초안 2건이다.

- `제육볶음.txt` — 기사식당 스타일 제육볶음
- `항정상꽈리고추볶음.txt` — 항정살 꽈리고추 볶음 (편한버전)

두 파일을 분석한 결과, 자유 서술처럼 보이지만 실제로는 **일관된 내부 구조**를 이미 갖추고 있다.

```
[재료 준비]  →  주재료 / 밑간 / 양념장으로 그룹 분리
[조리 순서]  →  번호가 매겨진 단계, 각 단계에 소요시간 표기
💡Tip        →  "왜 그렇게 해야 하는지" 원리 설명
계량 기준     →  "1T = 아빠 숟가락"으로 통일
```

이 구조는 별도 입력 폼 없이 그대로 Input으로 쓸 수 있을 만큼 정제되어 있다.

---

## 2. 목표와 비목표

### 2.1 목표 (In Scope)

| 코드 | 산출물 | 근거 |
|---|---|---|
| 레시피 카드 | 원본 텍스트를 구조화한 JSON | Phase B 자동 연결의 전제 |
| A1 | 영상 시나리오 (구조·타임라인·후킹·BGM) | SRS Phase A |
| A2 | 촬영 대본 (타임코드별 멘트·액션·표정) | SRS Phase A |
| A3 | 촬영 구도/앵글 가이드 | SRS Phase A |
| A4 | 차별화 포인트 | SRS Phase A |
| A5 | 촬영 체크리스트 | SRS Phase A |
| B2 | 인스타그램 패키지 (릴스 캡션·해시태그·캐러셀·스토리) | SRS Phase B 중 영상 불필요 부분 |
| B3 | 네이버 블로그 글 (SEO 제목·본문·사진 위치·태그) | SRS Phase B 중 영상 불필요 부분 |

**B2·B3를 앞당긴 이유**: 촬영 가이드(A1~A5)는 "곧 촬영할 때"만 효용이 있다.
반면 B2·B3는 레시피 텍스트만으로 생성 가능하고 **즉시 발행 가능한 결과물**이라,
확보된 레시피 2건으로 바로 품질을 검증할 수 있다.

### 2.2 비목표 (Out of Scope)

- **B1 편집 가이드 / B4 유튜브 패키지 / B5 수익화** — 촬영된 영상 또는 별도 조사가 전제
- **영상 분석 파이프라인** — Whisper STT, FFmpeg 키프레임, PySceneDetect (SRS Phase 2)
- **육아 에피소드 카드** — 동일 구조를 재사용하되 Input 포맷이 다름 (SRS Phase 2)
- **Vix 영상 자동 생성** (SRS Phase 3)
- **원격 접속** — Tailscale / Streamlit Cloud 배포. 이번엔 로컬 PC 전용
- **성과 데이터 연동·예약 발행** (SRS Phase 4)

---

## 3. 의사결정 로그

| # | 결정 | 대안 | 채택 이유 |
|---|---|---|---|
| D1 | 범위 = A1~A5 + B2 + B3 | Phase A만 / 전체 | 촬영 전에도 발행 가능한 결과물이 나와 즉시 검증 가능 |
| D2 | 로컬 PC 전용 | Tailscale / Streamlit Cloud | 접근성보다 결과물 품질 검증이 선행 |
| D3 | 하이브리드 (프롬프트 분리 후 2경로) | API 전용 / Claude Code 전용 | 초기 프롬프트 튜닝은 반복 비용이 큼 → 그 구간을 구독 내에서 소화 |
| D4 | LLM 호출 2회 분할 | 1회 통합 / 산출물별 7회 | 응답당 깊이 확보 + 인스타·블로그 톤 일관성 + 부분 재생성 |
| D5 | 입력 폼 없이 `Recipe/*.txt` 직접 사용 | 구조화 폼 UI | 원본이 이미 구조화되어 있어 폼은 손만 늘림 |
| D6 | 레시피 카드는 호출①의 출력에 포함 | 별도 파싱 호출 | 호출 1회 절약, 품질 손실 없음 |
| D7 | 미결 TBD는 `channel_profile.json` 기본값으로 처리 | TBD 확정까지 대기 | SRS 미결 6건이 구현을 막지 않게 함 |

---

## 4. 아키텍처

### 4.1 하이브리드 2경로

**핵심 원칙: 프롬프트 템플릿이 단일 진실 공급원(single source of truth)이다.**
프롬프트를 파이썬 코드 안에 문자열 리터럴로 박지 않는다.

```
                    ┌──────────────────────────┐
                    │  channel_profile.json    │
                    │  prompts/*.md            │   ← 공유 자산
                    │  Recipe/*.txt            │
                    └────────────┬─────────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              │                                     │
      [경로 1] Claude Code 스킬            [경로 2] Streamlit + API
      .claude/skills/recipe-studio/        app.py + yunjin_studio/
      Pro 구독 내, 추가 과금 0             Anthropic API 종량 과금
      1단계 (지금)                         2단계 (품질 확정 후)
              │                                     │
              └──────────────────┬──────────────────┘
                                 ▼
                        output/<날짜>_<요리명>/
```

경로 1과 경로 2는 **같은 템플릿 파일을 읽고 같은 위치에 같은 형식으로 저장**한다.
프롬프트를 고치면 양쪽에 동시 반영된다. 경로 2를 추가할 때 프롬프트는 손대지 않는다.

### 4.2 데이터 흐름

```
Recipe/제육볶음.txt ─┐
channel_profile.json ─┼─→ [context 조립] ─→ 호출① shooting_guide
target_duration=60   ─┤                        └─→ recipe_card + A1~A5
episode_note(선택)   ─┘                                    │
                                                           ▼
channel_profile.json ─┬─→ [context 조립] ─→ 호출② publish_pack
recipe_card ──────────┘                        └─→ B2 + B3
                                                           │
                                                           ▼
                                            [formatter] → 마크다운 4개 파일
```

호출②는 원본 텍스트가 아니라 **호출①이 만든 `recipe_card`(구조화 JSON)** 를 입력으로 받는다.
재료 표기·단계 번호가 두 산출물 사이에서 어긋나지 않게 하기 위함이다.

---

## 5. 채널 프로필 (`channel_profile.json`)

SRS 미결사항 6건(채널명·톤앤무드·페르소나·발행비중·Vix·수익화)을 이 파일 한 곳에 모은다.
윤진님이 쓰면서 고쳐가고, 확정될 때마다 SRS HTML에 반영한다.

```json
{
  "channel": {
    "name": "TBD",
    "tagline": "TBD",
    "categories": ["요리", "육아"],
    "platforms": ["instagram", "naver_blog", "youtube"]
  },
  "voice": {
    "speech_style": "해요체",
    "persona": "요리 좀 하는 동네 언니",
    "energy": "차분하지만 확신 있는",
    "banned": ["과장된 리액션", "전문 셰프 어투", "광고성 미사여구", "'꿀팁 대방출' 류 낚시 표현"]
  },
  "signature_rules": [
    "계량은 '1T = 아빠 숟가락' 기준을 유지하고, 이 표현을 다른 말로 바꾸지 않는다",
    "모든 팁은 '무엇을'이 아니라 '왜'를 설명한다 — 원리 설명이 이 채널의 핵심 차별점이다",
    "실패 포인트를 숨기지 않고 조리 단계보다 먼저 알려준다",
    "재료 그룹(주재료/밑간/양념장)의 분리를 유지한다"
  ],
  "audience": {
    "primary": "TBD",
    "pain_point": "TBD"
  },
  "defaults": {
    "target_duration_sec": 60
  },
  "model": {
    "id": "claude-opus-5",
    "effort": "high"
  }
}
```

### 5.1 `signature_rules`의 근거

레시피 2건에서 **실제로 관찰된** 패턴이며, 추측이 아니다.

**계량 규칙** — 두 파일 모두 첫 줄에 `1T = 아빠 숟가락`을 명시한다. 생성물에서 이것이
"밥숟가락"이나 "테이블스푼"으로 치환되면 윤진님 고유의 목소리가 사라진다.

**원리 설명 Tip** — 이것이 채널의 실질적 차별점이다. 관찰된 사례:

| 레시피 | 지시 | 원리 설명 |
|---|---|---|
| 제육볶음 | 설탕·식초로 밑간 | 설탕은 연육 작용, 식초는 구울 때 휘발되며 잡내를 잡음 |
| 제육볶음 | 고기 기름에 양념 먼저 볶기 | 고춧가루·고추장의 날냄새가 날아가고 불향이 살아남 |
| 제육볶음 | 인덕션 화구에서 빼기 | 잔열에 채소가 오버쿡되어 너무 달아짐 |
| 항정살 | 굽고 기름 닦아내기 | 기름이 남으면 양념이 겉돌고 배지 않음 |
| 항정살 | 고기를 통으로 빼두기 | 육즙을 가둠 |
| 항정살 | 결 반대로 썰기 | 질기지 않고 부드러움 |

대부분의 레시피 채널은 **순서**를 알려주고, 윤진님은 **원리**를 알려준다.
따라서 **A4(차별화 포인트)의 답은 이미 원본 레시피 안에 존재**하며,
프롬프트는 이를 발명하는 것이 아니라 발굴·언어화하는 역할을 맡는다.

---

## 6. 입력 규격

### 6.1 레시피 원본

`Recipe/*.txt` — 별도 폼이나 변환 없이 원문 그대로 사용한다.
파일명(확장자 제외)이 요리명의 기본값이 된다.

### 6.2 실행 시 인자

SRS의 Phase A Input 항목 중 레시피 파일에 없는 2가지만 별도로 받는다.

| 인자 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `recipe` | 필수 | — | `Recipe/` 내 파일명 |
| `duration` | 선택 | `60` | 목표 러닝타임(초). 30 / 60 / 90 |
| `episode` | 선택 | 없음 | 비하인드 에피소드 한두 줄 |

`episode`를 상시로 쓰고 싶으면 레시피 파일 하단에 `[에피소드]` 섹션을 추가하는 것도 허용한다
(있으면 읽고, 없으면 인자 또는 생략).

---

## 7. LLM 호출 설계

### 7.1 호출① — `prompts/shooting_guide.md`

**입력**: 채널 프로필 + 레시피 원문 + `duration` + `episode`
**출력**: `recipe_card` + `a1`~`a5`

```json
{
  "recipe_card": {
    "dish_name": "기사식당 스타일 제육볶음",
    "category": "요리",
    "servings": "2~3인분",
    "difficulty": "쉬움",
    "total_time_min": 30,
    "measure_note": "1T = 아빠 숟가락",
    "ingredients": [
      { "group": "주재료", "items": [{ "name": "삼겹살 또는 앞다리살", "amount": "600g" }] },
      { "group": "고기 밑간", "items": [{ "name": "설탕", "amount": "1T" }] },
      { "group": "제육 양념장", "items": [{ "name": "고추장", "amount": "1T" }] }
    ],
    "steps": [
      { "no": 1, "title": "고기 밑간하기", "body": "...", "duration": "10~20분" }
    ],
    "tips": [
      { "step_no": 1, "what": "설탕과 식초를 넣는다", "why": "설탕은 연육 작용, 식초는 휘발되며 잡내 제거" }
    ],
    "fail_points": ["인덕션 잔열에 두면 채소가 오버쿡되어 달아짐"]
  },

  "a1_scenario": {
    "target_duration_sec": 60,
    "hook_lines": ["후보 3개"],
    "structure": [{ "section": "후킹", "from_sec": 0, "to_sec": 3, "purpose": "..." }],
    "bgm_mood": "...",
    "closing": "..."
  },

  "a2_script": [
    { "timecode": "0:00-0:03", "narration": "...", "action": "...", "expression": "...", "onscreen_text": "..." }
  ],

  "a3_camera": {
    "scenes": [
      { "scene": "밑간 주무르기", "angle": "탑뷰", "tripod": "높이 40cm, 도마 정면 위",
        "lighting": "...", "movement": "고정" }
    ],
    "must_shots": ["반드시 찍어야 할 장면 5개"],
    "common_mistakes": ["..."],
    "hero_shot": "완성 비주얼 샷 가이드"
  },

  "a4_differentiator": {
    "channel_edge": ["원본 레시피에서 발굴한 차별점"],
    "vs_competitors": "...",
    "series_ideas": ["..."]
  },

  "a5_checklist": {
    "before_cooking": ["..."], "equipment": ["..."], "during_shoot": ["..."],
    "must_not_miss": ["..."], "after_shoot": ["..."]
  }
}
```

**`tips`를 `what` / `why`로 분리한 것이 이 설계의 의도적 장치다.**
`why`가 비어 있으면 채널 정체성이 살지 않는다는 신호이므로, 스키마 수준에서 강제한다.

### 7.2 호출② — `prompts/publish_pack.md`

**입력**: 채널 프로필 + `recipe_card`(호출①의 출력)
**출력**: `b2_instagram` + `b3_blog`

```json
{
  "b2_instagram": {
    "reels_caption": "...",
    "hashtags": ["#..."],
    "carousel": [{ "slide": 1, "headline": "...", "body": "..." }],
    "story_lines": ["..."],
    "thumbnail_ideas": ["..."]
  },
  "b3_blog": {
    "seo_title_candidates": ["후보 3개"],
    "meta_description": "...",
    "body_markdown": "서론-재료표-과정-팁-마무리 전체 본문",
    "photo_slots": [{ "after_section": "재료", "description": "촬영·삽입할 사진 설명" }],
    "tags": ["..."]
  }
}
```

캐러셀은 SRS 기준 5~7장으로 제한한다.

### 7.3 분할 근거

- **1회 통합의 문제**: 응답 한 개에 8천 토큰을 밀어넣으면 블로그 본문이 얕아진다. 부분 재생성도 불가하다.
- **7회 분할의 문제**: 비용 3배, 그리고 산출물끼리 후킹 문구·톤이 따로 논다.
- **2회 분할**: 응답당 4천 토큰대로 깊이가 유지되고, 인스타·블로그가 같은 호출이라 톤이 일관된다.
  "촬영 가이드만 다시" 또는 "블로그만 다시"가 가능하다.

---

## 8. 파일 구조

```
Make_Contents/
├── Recipe/                            # 윤진님 원본 (구조 변경 없음)
│   ├── 제육볶음.txt
│   └── 항정상꽈리고추볶음.txt
├── channel_profile.json               # 톤·페르소나·시그니처 규칙·모델 설정
├── prompts/
│   ├── shooting_guide.md              # 호출① 템플릿
│   └── publish_pack.md                # 호출② 템플릿
├── .claude/
│   └── skills/
│       └── recipe-studio/SKILL.md     # 경로 1 (Claude Code, 비용 0)
├── yunjin_studio/                     # 공용 파이썬 코어
│   ├── __init__.py
│   ├── recipe.py                      # 레시피 로드 + 메타 병합
│   ├── context.py                     # 프로필 + 레시피 + 템플릿 → 프롬프트 조립
│   ├── schema.py                      # 출력 스키마 정의·검증
│   ├── formatter.py                   # JSON → 마크다운
│   └── generator.py                   # Anthropic API 호출 (경로 2 전용)
├── output/
│   └── 2026-08-29_제육볶음/
│       ├── 00_recipe_card.json
│       ├── 01_촬영가이드.md
│       ├── 02_인스타.md
│       └── 03_블로그.md
├── tests/
│   ├── test_recipe.py
│   ├── test_context.py
│   ├── test_schema.py
│   └── test_formatter.py
├── app.py                             # Streamlit (2단계)
└── docs/superpowers/specs/            # 이 문서
```

### 8.1 모듈 책임

| 모듈 | 하는 일 | 의존 |
|---|---|---|
| `recipe.py` | `Recipe/*.txt` 로드, `[에피소드]` 섹션 분리, 인자 병합 | 없음 |
| `context.py` | 템플릿 `.md` + 프로필 + 레시피 → 완성된 프롬프트 문자열 | `recipe.py` |
| `schema.py` | 응답 JSON 구조 검증, 필수 필드 누락 탐지 | 없음 |
| `formatter.py` | 검증된 JSON → 사람이 읽는 마크다운 4종 | `schema.py` |
| `generator.py` | Anthropic API 호출, 재시도, 에러 변환 | `context.py`, `schema.py` |

`generator.py`만 API에 의존한다. 나머지 4개는 순수 함수로, 경로 1·2가 공유하며 테스트 가능하다.

`schema.py`와 `formatter.py`는 CLI 진입점을 함께 제공한다. 경로 1(Claude Code 스킬)이
자신이 생성한 JSON을 같은 규칙으로 검증·변환하기 위해서다.

```
python -m yunjin_studio.validate output/<폴더>/00_recipe_card.json
python -m yunjin_studio.render  output/<폴더>/
```

이 CLI가 없으면 경로 1과 경로 2의 검증 기준이 갈라지고, 수용 기준 3·4번을
경로 1에서 확인할 방법이 사라진다.

---

## 9. 실행 경로 1 — Claude Code 스킬 (1단계)

`.claude/skills/recipe-studio/SKILL.md`

Claude Code가 스킬 지시에 따라 직접 수행한다. API 호출도, `generator.py`도 쓰지 않는다.

1. `channel_profile.json`을 읽는다
2. 지정된 `Recipe/<이름>.txt`를 읽는다
3. `prompts/shooting_guide.md` 템플릿에 프로필·레시피·러닝타임을 채워 넣고, 그 지시대로 산출물을 생성한다
4. 결과를 `output/<날짜>_<요리명>/`에 `00_recipe_card.json`과 `01_촬영가이드.md`로 저장한다
5. `prompts/publish_pack.md`에 `recipe_card`를 넣고 같은 방식으로 `02_인스타.md`, `03_블로그.md`를 생성한다
6. `python -m yunjin_studio.validate`로 생성 결과를 검증한다 — 경로 2와 동일한 스키마 규칙을 통과해야 한다

**이 단계의 목적은 프롬프트 튜닝이다.** 레시피 2건을 반복 생성하며 프롬프트를 다듬고,
결과물이 윤진님 기준을 통과하면 경로 2로 넘어간다. 이 반복 구간에서 API 비용이 발생하지 않는다.

---

## 10. 실행 경로 2 — Streamlit + API (2단계)

`app.py` — 단일 페이지.

1. `Recipe/` 파일 목록에서 선택 (드롭다운)
2. 러닝타임 선택 (30/60/90), 에피소드 입력 (선택)
3. "생성" 버튼 → `generator.py`가 호출①→호출② 순차 실행, 진행 상황 표시
4. 탭 4개(레시피 카드 / 촬영 가이드 / 인스타 / 블로그)로 결과 표시
5. `output/`에 저장 + 각 탭 다운로드 버튼

**구현 메모**:
- 모델은 `channel_profile.json`의 `model.id`를 따른다. 기본 `claude-opus-5`, `claude-sonnet-5`로 교체 가능
- `thinking: {type: "adaptive"}` 사용, `output_config.effort`는 프로필의 `model.effort`를 따른다
- 응답이 길어 스트리밍(`client.messages.stream()`)으로 호출하고 `.get_final_message()`로 수집한다
- 응답 구조 보장을 위해 `output_config.format`(structured outputs)로 스키마를 강제한다
- API 키는 `.env`의 `ANTHROPIC_API_KEY`로만 읽고, 소스와 `output/`에 절대 포함하지 않는다
- `.gitignore`에 `.env`, `output/` 추가

---

## 11. 테스트 전략

LLM 호출은 목(mock)으로 대체하고, **결정적으로 검증 가능한 4개 모듈**을 TDD로 구현한다.
생성 품질 자체는 레시피 2건으로 눈으로 검증한다(자동 테스트 대상 아님).

| 테스트 | 검증 내용 |
|---|---|
| `test_recipe.py` | `.txt` 로드, `[에피소드]` 섹션 분리, 파일명→요리명, 없는 파일 처리 |
| `test_context.py` | 프로필의 `signature_rules`가 프롬프트에 실제로 포함되는가 · `1T = 아빠 숟가락`이 유실되지 않는가 · 러닝타임이 반영되는가 · 호출②에 `recipe_card`가 주입되는가 |
| `test_schema.py` | 정상 응답 통과 · 필수 필드 누락 탐지 · `tips[].why` 누락 탐지 · 캐러셀 장수 범위(5~7) |
| `test_formatter.py` | JSON→마크다운 변환, 재료 그룹 분리 유지, 빈 선택 필드 처리 |

`test_context.py`의 계량 규칙·시그니처 규칙 검증이 **회귀 방지의 핵심**이다.
프롬프트를 튜닝하다 채널 정체성 규칙이 빠지는 사고를 이 테스트가 잡는다.

---

## 12. 에러 처리

| 상황 | 처리 |
|---|---|
| 레시피 파일 없음 | 사용 가능한 파일 목록을 함께 보여주고 중단 |
| `channel_profile.json` 없음/파손 | 기본 프로필로 진행하되 경고 표시 |
| API 키 미설정 | 경로 2에서만 발생. 설정 안내 후 중단 (경로 1은 무관) |
| 응답 스키마 불일치 | 원본 응답을 `output/.../_raw.json`으로 남기고, 누락 필드를 명시해 실패 |
| Rate limit / 5xx | SDK 기본 재시도에 맡기고, 소진 시 명확한 메시지로 실패 |
| 호출② 실패 | 호출①의 결과물은 이미 저장되어 있으므로 보존하고, 호출②만 재실행 가능하게 함 |

부분 실패 시 성공한 산출물을 버리지 않는다. 호출을 2회로 나눈 실질적 이득 중 하나다.

---

## 13. 비용

경로 1(Claude Code 스킬)은 Pro 구독 내에서 동작하므로 **추가 과금이 없다**.
경로 2 도입 후 예상 비용은 아래와 같다 (레시피 1건 = 호출 2회, 한국어 출력 합계 약 8천 토큰 기준).

| 모델 | 입력/출력 단가 (1M 토큰) | 레시피 1건 | 주 3건 × 4주 |
|---|---|---|---|
| `claude-opus-5` | $5 / $25 | 약 $0.21 | 약 $2.5 (≈3,600원) |
| `claude-sonnet-5` | $3 / $15 | 약 $0.13 | 약 $1.5 (≈2,200원) |

thinking 토큰을 넉넉히 감안해도 월 5천원 미만이다.
**Claude Pro 구독료와 Anthropic API 사용료는 별도 청구**된다는 점을 명시해 둔다.

---

## 14. 미해결 사항

SRS의 미결 6건 중 이 설계가 흡수한 것과 남은 것.

| 항목 | 상태 |
|---|---|
| 채널명 | **미결** — `channel_profile.json`의 `channel.name`에 TBD로 대기 |
| 톤앤무드 | **잠정 결정** — 해요체 / "요리 좀 하는 동네 언니". 윤진님 확인 후 확정 |
| 타깃 페르소나 | **미결** — `audience`에 TBD로 대기. 프롬프트 품질에 영향이 크므로 우선 확정 권장 |
| 요리 vs 육아 발행 비중 | **범위 밖** — 육아 파이프라인 자체가 이번 범위 밖 |
| Vix API 사전 조사 | **범위 밖** — SRS Phase 3 |
| 수익화 전략 우선순위 | **범위 밖** — B5가 이번 범위 밖 |

어느 항목도 구현을 막지 않는다. 전부 `channel_profile.json` 수정으로 나중에 반영 가능하다.

---

## 15. 수용 기준

이 설계의 구현이 완료되었다고 말하려면 아래가 모두 참이어야 한다.

1. `Recipe/제육볶음.txt`로 경로 1을 실행하면 `output/`에 4개 파일이 생성된다
2. `Recipe/항정상꽈리고추볶음.txt`로도 동일하게 동작한다
3. 생성된 블로그 글과 인스타 캡션에 `1T = 아빠 숟가락` 계량 표현이 원형 그대로 유지된다
4. 생성된 팁에 "왜"에 해당하는 설명이 포함되어 있다 (`tips[].why` 비어 있지 않음)
5. A4 차별화 포인트가 원본 레시피의 원리 설명에서 도출된 내용을 담고 있다 (일반론이 아님)
6. `pytest` 전체 통과
7. 프롬프트 템플릿을 수정하면 재실행만으로 결과물에 반영된다 (코드 수정 불필요)

---

## 16. 다음 단계

1. 이 스펙을 윤진님·영준님이 검토
2. 구현 계획(implementation plan) 작성
3. 경로 1 구현 → 레시피 2건으로 프롬프트 튜닝
4. 품질 확정 후 경로 2(Streamlit + API) 추가
5. 확정된 사항을 `YJ_Content_Factory_SRS_윤진.html`에 v2.1로 반영
