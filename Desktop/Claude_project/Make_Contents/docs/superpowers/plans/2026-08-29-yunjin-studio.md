# 윤진 Studio 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 윤진님의 레시피 텍스트 파일 하나를 넣으면 촬영 가이드(A1~A5) · 인스타 패키지(B2) · 네이버 블로그 글(B3)이 마크다운으로 생성되는 도구를 만든다.

**Architecture:** 프롬프트 템플릿(`prompts/*.md`)을 코드 밖의 단일 진실 공급원으로 두고, 두 실행 경로가 이를 공유한다 — 경로 1은 Claude Code 스킬(Pro 구독, 추가 과금 0)이고 경로 2는 Streamlit + Anthropic API다. LLM 호출은 2회로 나눈다(①촬영가이드+레시피카드 ②인스타+블로그). 순수 파이썬 모듈 4개(recipe/context/schema/formatter)는 두 경로가 공유하며 TDD로 만들고, API 의존은 `generator.py` 하나에 격리한다.

**Tech Stack:** Python 3.12.4 · pytest 7.4.4 · anthropic 0.105.2(업그레이드 예정) · streamlit 1.41.1 · python-dotenv

**Spec:** `docs/superpowers/specs/2026-08-29-yunjin-studio-design.md`

## Global Constraints

- **작업 디렉터리**: `C:\Users\yjkim\Desktop\Claude_project\Make_Contents`
- **git 저장소 루트가 `C:\Users\yjkim`(홈 디렉터리 전체)다.** 절대 `git add .` / `git add -A`를 쓰지 말 것. 매 커밋은 반드시 파일 경로를 명시적으로 나열한다. 워크트리도 만들지 않는다.
- **모든 파일은 UTF-8로 읽고 쓴다.** `Path.read_text(encoding="utf-8")` / `write_text(..., encoding="utf-8")`. Windows 기본 인코딩(cp949)에 맡기면 한글이 깨진다.
- **프롬프트 문자열을 파이썬 코드 안에 박지 않는다.** 전부 `prompts/*.md`에 두고 읽어 쓴다.
- **템플릿 치환은 `str.replace("{{KEY}}", ...)`만 쓴다.** `str.format()`이나 f-string을 템플릿에 쓰면 템플릿 안의 JSON 중괄호 `{`가 깨진다.
- **계량 표현 `1T = 아빠 숟가락`은 원형 그대로 보존한다.** "밥숟가락", "테이블스푼" 등으로 바꾸면 실패다.
- **`tips`는 `what`(무엇을)과 `why`(왜)를 반드시 분리한다.** `why`가 비면 검증 실패다 — 원리 설명이 이 채널의 정체성이다.
- **인스타 캐러셀은 5~7장.**
- **기본 모델은 `claude-opus-5`**, `channel_profile.json`에서 교체 가능.
- **`.env`와 `output/`은 절대 커밋하지 않는다.**
- 테스트 실행은 `Make_Contents` 디렉터리에서 `python -m pytest`로 한다.

## 스펙과의 차이 1건

스펙 §10은 경로 2에서 `output_config.format`(structured outputs)로 응답 구조를 강제한다고 적었다.
**이 계획은 그 대신 프롬프트 지시 + `schema.py` 검증으로 구조를 보장한다.** 이유는 두 가지다.

1. 경로 1(Claude Code 스킬)에는 API 파라미터라는 개념이 없어 structured outputs를 쓸 수 없다.
   두 경로의 구조 보장 수단이 갈라지면 "경로 1에서 통과한 것이 경로 2에서 다르게 나오는" 문제가 생긴다.
2. `schema.py`는 어차피 필요하다(스펙 §8.1 CLI 진입점). structured outputs를 추가해도 이 검증은 사라지지 않는다.

structured outputs는 나중에 `build_request_kwargs`에 키 하나를 더하는 것으로 언제든 얹을 수 있다.
이 차이를 윤진님·영준님이 반대하면 Task 7에서 되돌린다.

## 작업 순서 개요

| Task | 산출물 | 경로 |
|---|---|---|
| 1 | 프로젝트 뼈대 + `channel_profile.json` + 프로필 로더 | 공용 |
| 2 | `recipe.py` — 레시피 로더 | 공용 |
| 3 | `prompts/*.md` 2개 + 프롬프트 조립 | 공용 |
| 4 | `schema.py` + `validate` CLI | 공용 |
| 5 | `formatter.py` + `render` CLI | 공용 |
| 6 | Claude Code 스킬 + 레시피 2건 실동작 검증 | **경로 1 완성** |
| 7 | `generator.py` — Anthropic API 호출 | 경로 2 |
| 8 | `app.py` — Streamlit UI | **경로 2 완성** |

---

### Task 1: 프로젝트 뼈대와 채널 프로필

**Files:**
- Create: `.gitignore`
- Create: `requirements.txt`
- Create: `channel_profile.json`
- Create: `yunjin_studio/__init__.py`
- Create: `yunjin_studio/context.py`
- Create: `conftest.py` (빈 파일)
- Create: `tests/__init__.py` (빈 파일)
- Test: `tests/test_context.py`

**Interfaces:**
- Consumes: 없음 (첫 태스크)
- Produces:
  - `yunjin_studio.context.ROOT: Path` — `Make_Contents` 디렉터리
  - `yunjin_studio.context.PROFILE_PATH: Path`
  - `yunjin_studio.context.PROMPT_DIR: Path`
  - `yunjin_studio.context.DEFAULT_PROFILE: dict`
  - `yunjin_studio.context.load_profile(path: Path = PROFILE_PATH) -> tuple[dict, list[str]]` — `(프로필, 경고목록)`

주의: 이 폴더에 이미 있는 `requirement.txt`(단수)는 pip 파일이 아니라 요구사항 정의서 템플릿 문서다. 건드리지 말고 `requirements.txt`(복수)를 새로 만든다.

- [ ] **Step 1: `.gitignore` 생성**

`Make_Contents/.gitignore`:

```gitignore
.env
output/
__pycache__/
*.pyc
.pytest_cache/
.streamlit/secrets.toml
```

- [ ] **Step 2: `requirements.txt` 생성**

`Make_Contents/requirements.txt`:

```
anthropic>=0.105.2
streamlit>=1.41.1
python-dotenv>=1.0.0
pytest>=7.4.4
```

- [ ] **Step 3: `channel_profile.json` 생성**

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

- [ ] **Step 4: import 경로 확보용 빈 파일 2개 생성**

`Make_Contents/conftest.py`와 `Make_Contents/tests/__init__.py`를 **빈 파일**로 만든다.

- `conftest.py`는 pytest가 `Make_Contents`를 `sys.path`에 넣게 해서 `import yunjin_studio`가 되게 한다.
- `tests/__init__.py`는 Task 5·7에서 `from tests.test_schema import ...`로 픽스처를 재사용하기 위해 필요하다.

둘 다 내용이 없어야 한다. Windows에서는 `python -c "open('conftest.py','w').close()"` 처럼 만든다.

- [ ] **Step 5: 실패하는 테스트 작성**

`tests/test_context.py`:

```python
import json
from pathlib import Path

from yunjin_studio.context import DEFAULT_PROFILE, PROFILE_PATH, load_profile


def test_load_profile_reads_shipped_file():
    profile, warnings = load_profile()
    assert warnings == []
    assert profile["voice"]["speech_style"] == "해요체"
    assert any("아빠 숟가락" in rule for rule in profile["signature_rules"])


def test_load_profile_falls_back_when_missing(tmp_path):
    profile, warnings = load_profile(tmp_path / "없는파일.json")
    assert profile == DEFAULT_PROFILE
    assert len(warnings) == 1
    assert "기본 프로필" in warnings[0]


def test_load_profile_falls_back_on_broken_json(tmp_path):
    broken = tmp_path / "channel_profile.json"
    broken.write_text("{ 이건 JSON이 아님", encoding="utf-8")
    profile, warnings = load_profile(broken)
    assert profile == DEFAULT_PROFILE
    assert len(warnings) == 1


def test_shipped_profile_and_default_have_same_keys():
    shipped = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    assert set(shipped) == set(DEFAULT_PROFILE)
```

- [ ] **Step 6: 테스트 실패 확인**

Run: `python -m pytest tests/test_context.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'yunjin_studio'`

- [ ] **Step 7: 최소 구현**

`yunjin_studio/__init__.py`: 빈 파일로 생성.

`yunjin_studio/context.py`:

```python
"""채널 프로필 로드와 프롬프트 조립."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE_PATH = ROOT / "channel_profile.json"
PROMPT_DIR = ROOT / "prompts"

DEFAULT_PROFILE = {
    "channel": {
        "name": "TBD",
        "tagline": "TBD",
        "categories": ["요리", "육아"],
        "platforms": ["instagram", "naver_blog", "youtube"],
    },
    "voice": {
        "speech_style": "해요체",
        "persona": "요리 좀 하는 동네 언니",
        "energy": "차분하지만 확신 있는",
        "banned": ["과장된 리액션", "전문 셰프 어투", "광고성 미사여구", "'꿀팁 대방출' 류 낚시 표현"],
    },
    "signature_rules": [
        "계량은 '1T = 아빠 숟가락' 기준을 유지하고, 이 표현을 다른 말로 바꾸지 않는다",
        "모든 팁은 '무엇을'이 아니라 '왜'를 설명한다 — 원리 설명이 이 채널의 핵심 차별점이다",
        "실패 포인트를 숨기지 않고 조리 단계보다 먼저 알려준다",
        "재료 그룹(주재료/밑간/양념장)의 분리를 유지한다",
    ],
    "audience": {"primary": "TBD", "pain_point": "TBD"},
    "defaults": {"target_duration_sec": 60},
    "model": {"id": "claude-opus-5", "effort": "high"},
}


def load_profile(path: Path = PROFILE_PATH) -> tuple[dict, list[str]]:
    """채널 프로필을 읽는다. 실패하면 기본 프로필과 경고를 돌려준다."""
    if not path.exists():
        return DEFAULT_PROFILE, [f"{path.name}이(가) 없어 기본 프로필로 진행합니다."]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return DEFAULT_PROFILE, [f"{path.name} 파싱 실패({exc}) — 기본 프로필로 진행합니다."]
```

- [ ] **Step 8: 테스트 통과 확인**

Run: `python -m pytest tests/test_context.py -v`
Expected: PASS (4 passed)

- [ ] **Step 9: 커밋**

```bash
git -C C:/Users/yjkim add Desktop/Claude_project/Make_Contents/.gitignore \
                          Desktop/Claude_project/Make_Contents/requirements.txt \
                          Desktop/Claude_project/Make_Contents/channel_profile.json \
                          Desktop/Claude_project/Make_Contents/conftest.py \
                          Desktop/Claude_project/Make_Contents/yunjin_studio/__init__.py \
                          Desktop/Claude_project/Make_Contents/yunjin_studio/context.py \
                          Desktop/Claude_project/Make_Contents/tests/__init__.py \
                          Desktop/Claude_project/Make_Contents/tests/test_context.py
git -C C:/Users/yjkim commit -m "feat(yunjin-studio): 프로젝트 뼈대와 채널 프로필 로더"
```

저장소 루트가 `C:\Users\yjkim`이므로 경로는 전부 루트 기준이고, 모든 커밋에서 `git -C C:/Users/yjkim`을 쓴다.

---

### Task 2: 레시피 로더

**Files:**
- Create: `yunjin_studio/recipe.py`
- Test: `tests/test_recipe.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `yunjin_studio.recipe.Recipe` — `@dataclass(frozen=True)` with `dish_name: str`, `body: str`, `episode: str`
  - `yunjin_studio.recipe.RecipeNotFoundError(FileNotFoundError)`
  - `yunjin_studio.recipe.RECIPE_DIR: Path`
  - `yunjin_studio.recipe.list_recipes(recipe_dir: Path = RECIPE_DIR) -> list[str]`
  - `yunjin_studio.recipe.load_recipe(name: str, recipe_dir: Path = RECIPE_DIR, episode: str = "") -> Recipe`

`Recipe/` 폴더에는 이미 `제육볶음.txt`와 `항정상꽈리고추볶음.txt`가 있다. 두 번째 파일명은 `항정살`이 아니라 **`항정상`** 이다(원본 오타). 파일명을 고치지 말고 그대로 쓴다.

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_recipe.py`:

```python
import pytest

from yunjin_studio.recipe import Recipe, RecipeNotFoundError, list_recipes, load_recipe


def test_list_recipes_finds_both_drafts():
    names = list_recipes()
    assert "제육볶음" in names
    assert "항정상꽈리고추볶음" in names


def test_load_recipe_reads_korean_body():
    recipe = load_recipe("제육볶음")
    assert isinstance(recipe, Recipe)
    assert recipe.dish_name == "제육볶음"
    assert "고추장" in recipe.body
    assert "아빠 숟가락" in recipe.body
    assert recipe.episode == ""


def test_load_recipe_accepts_episode_argument():
    recipe = load_recipe("제육볶음", episode="아빠가 제일 좋아하는 메뉴")
    assert recipe.episode == "아빠가 제일 좋아하는 메뉴"


def test_load_recipe_splits_episode_section(tmp_path):
    path = tmp_path / "테스트요리.txt"
    path.write_text(
        "[재료 준비]\n- 계란 2개\n\n[에피소드]\n아이가 처음 먹은 날\n",
        encoding="utf-8",
    )
    recipe = load_recipe("테스트요리", recipe_dir=tmp_path)
    assert "계란 2개" in recipe.body
    assert "[에피소드]" not in recipe.body
    assert recipe.episode == "아이가 처음 먹은 날"


def test_episode_argument_wins_over_file_section(tmp_path):
    path = tmp_path / "테스트요리.txt"
    path.write_text("본문\n\n[에피소드]\n파일에 적힌 것\n", encoding="utf-8")
    recipe = load_recipe("테스트요리", recipe_dir=tmp_path, episode="인자로 준 것")
    assert recipe.episode == "인자로 준 것"


def test_missing_recipe_lists_available(tmp_path):
    (tmp_path / "있는요리.txt").write_text("본문", encoding="utf-8")
    with pytest.raises(RecipeNotFoundError) as exc:
        load_recipe("없는요리", recipe_dir=tmp_path)
    assert "있는요리" in str(exc.value)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_recipe.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'yunjin_studio.recipe'`

- [ ] **Step 3: 최소 구현**

`yunjin_studio/recipe.py`:

```python
"""Recipe/ 폴더의 레시피 원문을 읽는다."""

from dataclasses import dataclass
from pathlib import Path

RECIPE_DIR = Path(__file__).resolve().parent.parent / "Recipe"
EPISODE_HEADER = "[에피소드]"


class RecipeNotFoundError(FileNotFoundError):
    """요청한 레시피 파일이 없을 때."""


@dataclass(frozen=True)
class Recipe:
    dish_name: str
    body: str
    episode: str


def list_recipes(recipe_dir: Path = RECIPE_DIR) -> list[str]:
    return sorted(p.stem for p in recipe_dir.glob("*.txt"))


def load_recipe(name: str, recipe_dir: Path = RECIPE_DIR, episode: str = "") -> Recipe:
    path = recipe_dir / f"{name}.txt"
    if not path.exists():
        available = ", ".join(list_recipes(recipe_dir)) or "(없음)"
        raise RecipeNotFoundError(
            f"레시피 '{name}'을(를) 찾을 수 없습니다. 사용 가능: {available}"
        )
    body, file_episode = _split_episode(path.read_text(encoding="utf-8"))
    return Recipe(
        dish_name=name,
        body=body.strip(),
        episode=(episode or file_episode).strip(),
    )


def _split_episode(text: str) -> tuple[str, str]:
    if EPISODE_HEADER not in text:
        return text, ""
    head, _, tail = text.partition(EPISODE_HEADER)
    return head, tail
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_recipe.py -v`
Expected: PASS (6 passed)

한글이 깨져 `"고추장" in recipe.body`가 실패하면 인코딩 문제다. `python -c "print(open('Recipe/제육볶음.txt', encoding='utf-8').read()[:80])"`로 원본 인코딩을 확인한다.

- [ ] **Step 5: 커밋**

```bash
git -C C:/Users/yjkim add Desktop/Claude_project/Make_Contents/yunjin_studio/recipe.py \
                          Desktop/Claude_project/Make_Contents/tests/test_recipe.py
git -C C:/Users/yjkim commit -m "feat(yunjin-studio): 레시피 로더와 에피소드 섹션 분리"
```

---

### Task 3: 프롬프트 템플릿과 조립

**Files:**
- Create: `prompts/shooting_guide.md`
- Create: `prompts/publish_pack.md`
- Modify: `yunjin_studio/context.py` (함수 추가)
- Modify: `tests/test_context.py` (테스트 추가)

**Interfaces:**
- Consumes: `yunjin_studio.recipe.Recipe`, `yunjin_studio.context.PROMPT_DIR`
- Produces:
  - `yunjin_studio.context.build_shooting_prompt(profile: dict, recipe: Recipe, duration_sec: int = 60, template_dir: Path = PROMPT_DIR) -> str`
  - `yunjin_studio.context.build_publish_prompt(profile: dict, recipe_card: dict, template_dir: Path = PROMPT_DIR) -> str`

치환 토큰은 `{{CHANNEL_PROFILE}}`, `{{DISH_NAME}}`, `{{RECIPE_BODY}}`, `{{EPISODE}}`, `{{DURATION_SEC}}`, `{{RECIPE_CARD}}` 여섯 개다.

- [ ] **Step 1: `prompts/shooting_guide.md` 작성**

````markdown
# 촬영 가이드 생성 (Phase A)

당신은 요리·육아 콘텐츠 채널의 콘텐츠 디렉터입니다.
아래 채널 프로필과 레시피 원문을 읽고, 촬영 전에 볼 가이드를 만드세요.

## 채널 프로필

```json
{{CHANNEL_PROFILE}}
```

`signature_rules`는 반드시 지켜야 합니다. 특히:

- 계량 표현은 원문에 적힌 그대로 유지하고 다른 단위로 바꾸지 마세요.
- 모든 팁은 "무엇을 하는가"(what)와 "왜 그래야 하는가"(why)를 분리해 쓰세요. `why`가 비면 실패입니다.
- `voice.banned`에 있는 표현은 쓰지 마세요.

## 레시피

- 요리명: {{DISH_NAME}}
- 목표 러닝타임: {{DURATION_SEC}}초
- 비하인드 에피소드: {{EPISODE}}

원문:

```
{{RECIPE_BODY}}
```

## 작업

1. 원문을 `recipe_card`로 구조화하세요. **원문에 없는 재료나 단계를 지어내지 마세요.**
   재료 그룹(주재료 / 밑간 / 양념장 등)의 분리를 원문 그대로 유지하세요.
2. 원문의 💡Tip을 읽고 "무엇을 하라"(what)와 "왜 그래야 하는가"(why)로 분리해 `tips`에 담으세요.
   원문이 이미 원리를 설명하고 있습니다. 새로 지어내지 말고 원문에서 찾아 옮기세요.
3. A1~A5를 생성하세요.
4. `a4_differentiator.channel_edge`는 일반론("정성이 담긴 집밥")이 아니라
   **이 레시피의 원리 설명에서 도출된 구체적 내용**이어야 합니다.
5. `a2_script`의 타임코드는 0초에서 시작해 {{DURATION_SEC}}초에서 끝나야 합니다.
6. `a3_camera.must_shots`는 정확히 5개입니다.
7. `a1_scenario.hook_lines`는 3개 후보를 제시하세요.

## 출력 형식

설명이나 인사말 없이, 아래 구조의 JSON 객체 **하나만** 출력하세요.

```json
{
  "recipe_card": {
    "dish_name": "문자열",
    "category": "요리",
    "servings": "문자열",
    "difficulty": "문자열",
    "total_time_min": 30,
    "measure_note": "원문의 계량 기준을 그대로",
    "ingredients": [
      { "group": "주재료", "items": [{ "name": "문자열", "amount": "문자열" }] }
    ],
    "steps": [
      { "no": 1, "title": "문자열", "body": "문자열", "duration": "문자열" }
    ],
    "tips": [
      { "step_no": 1, "what": "무엇을 하는가", "why": "왜 그래야 하는가" }
    ],
    "fail_points": ["문자열"]
  },
  "a1_scenario": {
    "target_duration_sec": {{DURATION_SEC}},
    "hook_lines": ["후보1", "후보2", "후보3"],
    "structure": [
      { "section": "후킹", "from_sec": 0, "to_sec": 3, "purpose": "문자열" }
    ],
    "bgm_mood": "문자열",
    "closing": "문자열"
  },
  "a2_script": [
    {
      "timecode": "0:00-0:03",
      "narration": "문자열",
      "action": "문자열",
      "expression": "문자열",
      "onscreen_text": "문자열"
    }
  ],
  "a3_camera": {
    "scenes": [
      {
        "scene": "문자열",
        "angle": "탑뷰 | 45도 | 정면 | 클로즈업",
        "tripod": "위치와 높이",
        "lighting": "문자열",
        "movement": "문자열"
      }
    ],
    "must_shots": ["1", "2", "3", "4", "5"],
    "common_mistakes": ["문자열"],
    "hero_shot": "완성 비주얼 샷 가이드"
  },
  "a4_differentiator": {
    "channel_edge": ["문자열"],
    "vs_competitors": "문자열",
    "series_ideas": ["문자열"]
  },
  "a5_checklist": {
    "before_cooking": ["문자열"],
    "equipment": ["문자열"],
    "during_shoot": ["문자열"],
    "must_not_miss": ["문자열"],
    "after_shoot": ["문자열"]
  }
}
```
````

- [ ] **Step 2: `prompts/publish_pack.md` 작성**

````markdown
# 발행 콘텐츠 생성 (인스타그램 + 네이버 블로그)

당신은 요리·육아 콘텐츠 채널의 카피라이터입니다.
아래 채널 프로필과 구조화된 레시피 카드를 읽고, 바로 발행 가능한 콘텐츠를 만드세요.

## 채널 프로필

```json
{{CHANNEL_PROFILE}}
```

`signature_rules`는 반드시 지켜야 합니다. 특히:

- `recipe_card.measure_note`의 계량 표현을 **한 글자도 바꾸지 말고** 블로그 본문에 그대로 넣으세요.
- 팁을 옮길 때 `why`(원리)를 빠뜨리지 마세요. 순서만 나열하면 이 채널이 아닙니다.
- `voice.banned`에 있는 표현은 쓰지 마세요.

## 레시피 카드

```json
{{RECIPE_CARD}}
```

## 작업

1. **인스타그램** — 릴스 캡션, 해시태그, 캐러셀 슬라이드(정확히 5~7장), 스토리 문구, 썸네일 아이디어.
2. **네이버 블로그** — SEO 제목 후보 3개, 메타 설명, 본문, 사진 삽입 위치, 태그.
   본문은 마크다운으로 쓰고 **서론 → 재료표 → 조리 과정 → 팁 → 마무리** 순서를 따릅니다.
   재료는 마크다운 표로 쓰되 `recipe_card.ingredients`의 그룹 분리를 유지하세요.
3. 두 산출물의 후킹 문구와 톤은 서로 일관되어야 합니다.

## 출력 형식

설명이나 인사말 없이, 아래 구조의 JSON 객체 **하나만** 출력하세요.

```json
{
  "b2_instagram": {
    "reels_caption": "문자열",
    "hashtags": ["#해시태그"],
    "carousel": [{ "slide": 1, "headline": "문자열", "body": "문자열" }],
    "story_lines": ["문자열"],
    "thumbnail_ideas": ["문자열"]
  },
  "b3_blog": {
    "seo_title_candidates": ["후보1", "후보2", "후보3"],
    "meta_description": "문자열",
    "body_markdown": "마크다운 본문 전체",
    "photo_slots": [{ "after_section": "재료", "description": "찍어서 넣을 사진 설명" }],
    "tags": ["문자열"]
  }
}
```
````

- [ ] **Step 3: 실패하는 테스트 추가**

`tests/test_context.py` 하단에 추가:

```python
from yunjin_studio.context import build_publish_prompt, build_shooting_prompt
from yunjin_studio.recipe import Recipe


def _recipe():
    return Recipe(dish_name="제육볶음", body="[재료 준비]\n삼겹살 600g", episode="")


def test_shooting_prompt_includes_signature_rules():
    profile, _ = load_profile()
    prompt = build_shooting_prompt(profile, _recipe())
    for rule in profile["signature_rules"]:
        assert rule in prompt


def test_shooting_prompt_preserves_measure_expression():
    profile, _ = load_profile()
    prompt = build_shooting_prompt(profile, _recipe())
    assert "1T = 아빠 숟가락" in prompt


def test_shooting_prompt_reflects_duration():
    profile, _ = load_profile()
    prompt = build_shooting_prompt(profile, _recipe(), duration_sec=90)
    assert "90초" in prompt
    assert "60초" not in prompt


def test_shooting_prompt_includes_recipe_body_and_episode():
    profile, _ = load_profile()
    recipe = Recipe(dish_name="제육볶음", body="삼겹살 600g", episode="아빠 최애 메뉴")
    prompt = build_shooting_prompt(profile, recipe)
    assert "삼겹살 600g" in prompt
    assert "아빠 최애 메뉴" in prompt


def test_shooting_prompt_shows_placeholder_when_no_episode():
    profile, _ = load_profile()
    prompt = build_shooting_prompt(profile, _recipe())
    assert "(없음)" in prompt


def test_publish_prompt_injects_recipe_card():
    profile, _ = load_profile()
    card = {"dish_name": "제육볶음", "measure_note": "1T = 아빠 숟가락"}
    prompt = build_publish_prompt(profile, card)
    assert "제육볶음" in prompt
    assert "1T = 아빠 숟가락" in prompt


def test_no_unreplaced_tokens_remain():
    profile, _ = load_profile()
    assert "{{" not in build_shooting_prompt(profile, _recipe())
    assert "{{" not in build_publish_prompt(profile, {"dish_name": "x"})
```

- [ ] **Step 4: 테스트 실패 확인**

Run: `python -m pytest tests/test_context.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_shooting_prompt'`

- [ ] **Step 5: `context.py`에 조립 함수 추가**

`yunjin_studio/context.py` 하단에 추가 (상단 import에 `from .recipe import Recipe` 추가):

```python
def _render(template: str, values: dict[str, str]) -> str:
    """{{KEY}} 토큰만 치환한다. str.format을 쓰면 템플릿의 JSON 중괄호가 깨진다."""
    out = template
    for key, value in values.items():
        out = out.replace("{{" + key + "}}", value)
    return out


def _as_json_block(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def build_shooting_prompt(
    profile: dict,
    recipe: Recipe,
    duration_sec: int = 60,
    template_dir: Path = PROMPT_DIR,
) -> str:
    template = (template_dir / "shooting_guide.md").read_text(encoding="utf-8")
    return _render(
        template,
        {
            "CHANNEL_PROFILE": _as_json_block(profile),
            "DISH_NAME": recipe.dish_name,
            "RECIPE_BODY": recipe.body,
            "EPISODE": recipe.episode or "(없음)",
            "DURATION_SEC": str(duration_sec),
        },
    )


def build_publish_prompt(
    profile: dict,
    recipe_card: dict,
    template_dir: Path = PROMPT_DIR,
) -> str:
    template = (template_dir / "publish_pack.md").read_text(encoding="utf-8")
    return _render(
        template,
        {
            "CHANNEL_PROFILE": _as_json_block(profile),
            "RECIPE_CARD": _as_json_block(recipe_card),
        },
    )
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `python -m pytest tests/ -v`
Expected: PASS (17 passed)

`test_shooting_prompt_reflects_duration`에서 `"60초" not in prompt`가 실패하면, 템플릿 어딘가에 "60초"가 하드코딩되어 있다는 뜻이다. 템플릿에서 지운다.

- [ ] **Step 7: 커밋**

```bash
git -C C:/Users/yjkim add Desktop/Claude_project/Make_Contents/prompts/shooting_guide.md \
                          Desktop/Claude_project/Make_Contents/prompts/publish_pack.md \
                          Desktop/Claude_project/Make_Contents/yunjin_studio/context.py \
                          Desktop/Claude_project/Make_Contents/tests/test_context.py
git -C C:/Users/yjkim commit -m "feat(yunjin-studio): 프롬프트 템플릿 2종과 컨텍스트 조립"
```

---

### Task 4: 출력 스키마 검증과 validate CLI

**Files:**
- Create: `yunjin_studio/schema.py`
- Create: `yunjin_studio/validate.py`
- Test: `tests/test_schema.py`

**Interfaces:**
- Consumes: 없음
- Produces:
  - `yunjin_studio.schema.CAROUSEL_MIN: int = 5`, `CAROUSEL_MAX: int = 7`
  - `yunjin_studio.schema.validate_shooting_guide(data: dict) -> list[str]` — 오류 메시지 목록, 빈 리스트면 통과
  - `yunjin_studio.schema.validate_publish_pack(data: dict, measure_note: str = "") -> list[str]`
  - `yunjin_studio.validate.main(argv: list[str] | None = None) -> int` — 종료코드 0 통과 / 1 실패 / 2 사용법 오류
- 출력 폴더 규약(이후 태스크가 따른다):
  - `_raw_shooting.json` — 호출① 원본 응답
  - `_raw_publish.json` — 호출② 원본 응답
  - `00_recipe_card.json`, `01_촬영가이드.md`, `02_인스타.md`, `03_블로그.md`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_schema.py`:

```python
import copy

from yunjin_studio.schema import validate_publish_pack, validate_shooting_guide

VALID_SHOOTING = {
    "recipe_card": {
        "dish_name": "제육볶음",
        "measure_note": "1T = 아빠 숟가락",
        "ingredients": [{"group": "주재료", "items": [{"name": "삼겹살", "amount": "600g"}]}],
        "steps": [{"no": 1, "title": "밑간", "body": "재워두기", "duration": "10분"}],
        "tips": [{"step_no": 1, "what": "설탕을 넣는다", "why": "연육 작용을 돕는다"}],
        "fail_points": ["오버쿡"],
    },
    "a1_scenario": {"hook_lines": ["a", "b", "c"], "structure": [], "bgm_mood": "x", "closing": "y"},
    "a2_script": [{"timecode": "0:00-0:03", "narration": "a", "action": "b"}],
    "a3_camera": {"scenes": [], "must_shots": ["1", "2", "3", "4", "5"], "hero_shot": "x"},
    "a4_differentiator": {"channel_edge": ["원리 설명"], "vs_competitors": "x", "series_ideas": []},
    "a5_checklist": {"before_cooking": ["x"], "equipment": ["x"], "during_shoot": ["x"]},
}

VALID_PUBLISH = {
    "b2_instagram": {
        "reels_caption": "캡션",
        "hashtags": ["#집밥"],
        "carousel": [{"slide": i, "headline": "h", "body": "b"} for i in range(1, 6)],
        "story_lines": ["s"],
        "thumbnail_ideas": ["t"],
    },
    "b3_blog": {
        "seo_title_candidates": ["1", "2", "3"],
        "meta_description": "설명",
        "body_markdown": "본문입니다. 계량은 1T = 아빠 숟가락 기준이에요.",
        "photo_slots": [{"after_section": "재료", "description": "d"}],
        "tags": ["집밥"],
    },
}


def test_valid_shooting_guide_passes():
    assert validate_shooting_guide(copy.deepcopy(VALID_SHOOTING)) == []


def test_missing_top_level_key_is_reported():
    data = copy.deepcopy(VALID_SHOOTING)
    del data["a3_camera"]
    errors = validate_shooting_guide(data)
    assert any("a3_camera" in e for e in errors)


def test_empty_tip_why_is_reported():
    data = copy.deepcopy(VALID_SHOOTING)
    data["recipe_card"]["tips"][0]["why"] = "   "
    errors = validate_shooting_guide(data)
    assert any("why" in e for e in errors)


def test_empty_tip_what_is_reported():
    data = copy.deepcopy(VALID_SHOOTING)
    data["recipe_card"]["tips"][0]["what"] = ""
    errors = validate_shooting_guide(data)
    assert any("what" in e for e in errors)


def test_missing_measure_note_is_reported():
    data = copy.deepcopy(VALID_SHOOTING)
    data["recipe_card"]["measure_note"] = ""
    errors = validate_shooting_guide(data)
    assert any("measure_note" in e for e in errors)


def test_valid_publish_pack_passes():
    assert validate_publish_pack(copy.deepcopy(VALID_PUBLISH), "1T = 아빠 숟가락") == []


def test_carousel_too_few_slides_is_reported():
    data = copy.deepcopy(VALID_PUBLISH)
    data["b2_instagram"]["carousel"] = data["b2_instagram"]["carousel"][:3]
    errors = validate_publish_pack(data)
    assert any("carousel" in e for e in errors)


def test_carousel_too_many_slides_is_reported():
    data = copy.deepcopy(VALID_PUBLISH)
    slide = {"slide": 9, "headline": "h", "body": "b"}
    data["b2_instagram"]["carousel"] = [slide] * 9
    errors = validate_publish_pack(data)
    assert any("carousel" in e for e in errors)


def test_lost_measure_note_in_blog_is_reported():
    data = copy.deepcopy(VALID_PUBLISH)
    data["b3_blog"]["body_markdown"] = "본문입니다. 계량은 밥숟가락 기준이에요."
    errors = validate_publish_pack(data, "1T = 아빠 숟가락")
    assert any("계량" in e for e in errors)


def test_seo_title_candidates_must_be_three():
    data = copy.deepcopy(VALID_PUBLISH)
    data["b3_blog"]["seo_title_candidates"] = ["하나"]
    errors = validate_publish_pack(data)
    assert any("seo_title_candidates" in e for e in errors)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'yunjin_studio.schema'`

- [ ] **Step 3: `schema.py` 구현**

```python
"""생성 결과 JSON의 구조와 채널 규칙을 검증한다."""

CAROUSEL_MIN = 5
CAROUSEL_MAX = 7

SHOOTING_KEYS = (
    "recipe_card",
    "a1_scenario",
    "a2_script",
    "a3_camera",
    "a4_differentiator",
    "a5_checklist",
)
CARD_KEYS = ("dish_name", "measure_note", "ingredients", "steps", "tips")


def _blank(value) -> bool:
    return not str(value or "").strip()


def validate_shooting_guide(data: dict) -> list[str]:
    errors: list[str] = []

    for key in SHOOTING_KEYS:
        if key not in data:
            errors.append(f"필수 키 누락: {key}")

    card = data.get("recipe_card") or {}
    for key in CARD_KEYS:
        if not card.get(key):
            errors.append(f"recipe_card.{key} 누락 또는 비어 있음")

    for index, tip in enumerate(card.get("tips") or []):
        if _blank(tip.get("what")):
            errors.append(f"recipe_card.tips[{index}].what 비어 있음")
        if _blank(tip.get("why")):
            errors.append(
                f"recipe_card.tips[{index}].why 비어 있음 — 원리 설명은 채널 정체성 규칙"
            )

    scenario = data.get("a1_scenario") or {}
    if len(scenario.get("hook_lines") or []) != 3:
        errors.append("a1_scenario.hook_lines 는 후보 3개여야 함")

    if not (data.get("a2_script") or []):
        errors.append("a2_script 비어 있음")

    camera = data.get("a3_camera") or {}
    if len(camera.get("must_shots") or []) != 5:
        errors.append("a3_camera.must_shots 는 5개여야 함")

    if not ((data.get("a4_differentiator") or {}).get("channel_edge") or []):
        errors.append("a4_differentiator.channel_edge 비어 있음")

    return errors


def validate_publish_pack(data: dict, measure_note: str = "") -> list[str]:
    errors: list[str] = []

    for key in ("b2_instagram", "b3_blog"):
        if key not in data:
            errors.append(f"필수 키 누락: {key}")

    instagram = data.get("b2_instagram") or {}
    carousel = instagram.get("carousel") or []
    if not CAROUSEL_MIN <= len(carousel) <= CAROUSEL_MAX:
        errors.append(
            f"b2_instagram.carousel 장수 {len(carousel)} — {CAROUSEL_MIN}~{CAROUSEL_MAX}장이어야 함"
        )
    if _blank(instagram.get("reels_caption")):
        errors.append("b2_instagram.reels_caption 비어 있음")
    if not (instagram.get("hashtags") or []):
        errors.append("b2_instagram.hashtags 비어 있음")

    blog = data.get("b3_blog") or {}
    body = blog.get("body_markdown") or ""
    if _blank(body):
        errors.append("b3_blog.body_markdown 비어 있음")
    if len(blog.get("seo_title_candidates") or []) != 3:
        errors.append("b3_blog.seo_title_candidates 는 후보 3개여야 함")
    if measure_note and measure_note not in body:
        errors.append(
            f"b3_blog.body_markdown 에 계량 기준 '{measure_note}' 이(가) 원형 그대로 없음"
        )

    return errors
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_schema.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: `validate.py` CLI 구현**

```python
"""생성 결과를 검증한다.

사용법:
    python -m yunjin_studio.validate <output_dir>
"""

import json
import sys
from pathlib import Path

from .schema import validate_publish_pack, validate_shooting_guide

USAGE = "사용법: python -m yunjin_studio.validate <output_dir>"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(USAGE)
        return 2

    out_dir = Path(args[0])
    errors: list[str] = []
    measure_note = ""

    shooting_path = out_dir / "_raw_shooting.json"
    if shooting_path.exists():
        shooting = json.loads(shooting_path.read_text(encoding="utf-8"))
        errors += validate_shooting_guide(shooting)
        measure_note = (shooting.get("recipe_card") or {}).get("measure_note", "")
    else:
        errors.append(f"{shooting_path.name} 없음")

    publish_path = out_dir / "_raw_publish.json"
    if publish_path.exists():
        publish = json.loads(publish_path.read_text(encoding="utf-8"))
        errors += validate_publish_pack(publish, measure_note)
    else:
        errors.append(f"{publish_path.name} 없음")

    if errors:
        print(f"검증 실패 ({len(errors)}건):")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("검증 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: CLI 수동 확인**

```bash
python -m yunjin_studio.validate
```
Expected: 사용법 출력, 종료코드 2

```bash
python -m yunjin_studio.validate output/없는폴더
```
Expected: `_raw_shooting.json 없음`, `_raw_publish.json 없음` 2건 출력, 종료코드 1

- [ ] **Step 7: 커밋**

```bash
git -C C:/Users/yjkim add Desktop/Claude_project/Make_Contents/yunjin_studio/schema.py \
                          Desktop/Claude_project/Make_Contents/yunjin_studio/validate.py \
                          Desktop/Claude_project/Make_Contents/tests/test_schema.py
git -C C:/Users/yjkim commit -m "feat(yunjin-studio): 출력 스키마 검증과 validate CLI"
```

---

### Task 5: 마크다운 포맷터와 render CLI

**Files:**
- Create: `yunjin_studio/formatter.py`
- Create: `yunjin_studio/render.py`
- Test: `tests/test_formatter.py`

**Interfaces:**
- Consumes: `yunjin_studio.schema` (검증), Task 4의 출력 폴더 규약
- Produces:
  - `yunjin_studio.formatter.render_shooting_guide(data: dict) -> str`
  - `yunjin_studio.formatter.render_instagram(data: dict) -> str`
  - `yunjin_studio.formatter.render_blog(data: dict) -> str`
  - `yunjin_studio.render.main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_formatter.py`:

```python
import copy

from tests.test_schema import VALID_PUBLISH, VALID_SHOOTING
from yunjin_studio.formatter import render_blog, render_instagram, render_shooting_guide


def test_shooting_guide_keeps_ingredient_groups():
    md = render_shooting_guide(copy.deepcopy(VALID_SHOOTING))
    assert "주재료" in md
    assert "삼겹살" in md
    assert "600g" in md


def test_shooting_guide_shows_tip_why():
    md = render_shooting_guide(copy.deepcopy(VALID_SHOOTING))
    assert "연육 작용을 돕는다" in md


def test_shooting_guide_has_all_five_sections():
    md = render_shooting_guide(copy.deepcopy(VALID_SHOOTING))
    for heading in ("A1", "A2", "A3", "A4", "A5"):
        assert heading in md


def test_shooting_guide_tolerates_missing_optional_fields():
    data = copy.deepcopy(VALID_SHOOTING)
    del data["a4_differentiator"]["series_ideas"]
    del data["recipe_card"]["fail_points"]
    md = render_shooting_guide(data)
    assert isinstance(md, str)
    assert "제육볶음" in md


def test_instagram_lists_all_carousel_slides():
    md = render_instagram(copy.deepcopy(VALID_PUBLISH))
    assert md.count("슬라이드") == 5
    assert "#집밥" in md


def test_blog_uses_seo_title_and_body():
    md = render_blog(copy.deepcopy(VALID_PUBLISH))
    assert "1T = 아빠 숟가락" in md
    assert "본문입니다" in md


def test_blog_lists_photo_slots():
    md = render_blog(copy.deepcopy(VALID_PUBLISH))
    assert "재료" in md
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `python -m pytest tests/test_formatter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'yunjin_studio.formatter'`

`from tests.test_schema import ...`가 `ModuleNotFoundError: No module named 'tests'`로 실패하면
Task 1 Step 4에서 만든 `conftest.py`와 `tests/__init__.py`가 있는지 확인한다.

- [ ] **Step 3: `formatter.py` 구현**

```python
"""검증된 JSON을 사람이 읽는 마크다운으로 바꾼다."""


def _lines(items, bullet: str = "- ") -> str:
    return "\n".join(f"{bullet}{item}" for item in (items or [])) or "- (없음)"


def _ingredients(card: dict) -> str:
    blocks = []
    for group in card.get("ingredients") or []:
        rows = [
            f"| {item.get('name', '')} | {item.get('amount', '')} |"
            for item in group.get("items") or []
        ]
        blocks.append(
            f"**{group.get('group', '재료')}**\n\n"
            "| 재료 | 양 |\n| --- | --- |\n" + "\n".join(rows)
        )
    return "\n\n".join(blocks) or "(없음)"


def _steps(card: dict) -> str:
    rows = []
    for step in card.get("steps") or []:
        duration = f" _({step['duration']})_" if step.get("duration") else ""
        rows.append(f"{step.get('no', '')}. **{step.get('title', '')}**{duration}\n   {step.get('body', '')}")
    return "\n".join(rows) or "(없음)"


def _tips(card: dict) -> str:
    rows = []
    for tip in card.get("tips") or []:
        rows.append(f"- **{tip.get('what', '')}**\n  - 왜: {tip.get('why', '')}")
    return "\n".join(rows) or "- (없음)"


def render_shooting_guide(data: dict) -> str:
    card = data.get("recipe_card") or {}
    a1 = data.get("a1_scenario") or {}
    a3 = data.get("a3_camera") or {}
    a4 = data.get("a4_differentiator") or {}
    a5 = data.get("a5_checklist") or {}

    script_rows = "\n".join(
        f"| {s.get('timecode', '')} | {s.get('narration', '')} | "
        f"{s.get('action', '')} | {s.get('onscreen_text', '')} |"
        for s in data.get("a2_script") or []
    )
    scene_rows = "\n".join(
        f"| {s.get('scene', '')} | {s.get('angle', '')} | {s.get('tripod', '')} | "
        f"{s.get('lighting', '')} | {s.get('movement', '')} |"
        for s in a3.get("scenes") or []
    )

    return f"""# {card.get('dish_name', '')} — 촬영 가이드

- 목표 러닝타임: {a1.get('target_duration_sec', '')}초
- 인원: {card.get('servings', '-')} · 난이도: {card.get('difficulty', '-')} · 총 {card.get('total_time_min', '-')}분
- 계량 기준: **{card.get('measure_note', '')}**

## 재료

{_ingredients(card)}

## 조리 순서

{_steps(card)}

## 팁 (무엇을 / 왜)

{_tips(card)}

## 실패 포인트

{_lines(card.get('fail_points'))}

---

## A1. 영상 시나리오

**후킹 문장 후보**

{_lines(a1.get('hook_lines'))}

**구조**

{_lines(f"{s.get('from_sec')}~{s.get('to_sec')}초 · {s.get('section')} — {s.get('purpose')}" for s in a1.get('structure') or [])}

- BGM 분위기: {a1.get('bgm_mood', '')}
- 마무리: {a1.get('closing', '')}

## A2. 촬영 대본

| 타임코드 | 멘트 | 액션 | 자막 |
| --- | --- | --- | --- |
{script_rows}

## A3. 촬영 구도 / 앵글

| 장면 | 앵글 | 삼각대 | 조명 | 카메라 이동 |
| --- | --- | --- | --- | --- |
{scene_rows}

**반드시 찍어야 할 장면 TOP 5**

{_lines(a3.get('must_shots'))}

**흔한 실수**

{_lines(a3.get('common_mistakes'))}

**완성 비주얼 샷**: {a3.get('hero_shot', '')}

## A4. 차별화 포인트

{_lines(a4.get('channel_edge'))}

- 경쟁 채널 대비: {a4.get('vs_competitors', '')}

**시리즈화 아이디어**

{_lines(a4.get('series_ideas'))}

## A5. 촬영 체크리스트

**요리 전**

{_lines(a5.get('before_cooking'), '- [ ] ')}

**장비**

{_lines(a5.get('equipment'), '- [ ] ')}

**촬영 중**

{_lines(a5.get('during_shoot'), '- [ ] ')}

**놓치면 안 되는 것**

{_lines(a5.get('must_not_miss'), '- [ ] ')}

**촬영 후**

{_lines(a5.get('after_shoot'), '- [ ] ')}
"""


def render_instagram(data: dict) -> str:
    insta = data.get("b2_instagram") or {}
    slides = "\n\n".join(
        f"**슬라이드 {s.get('slide', i + 1)} — {s.get('headline', '')}**\n\n{s.get('body', '')}"
        for i, s in enumerate(insta.get("carousel") or [])
    )
    return f"""# 인스타그램 패키지

## 릴스 캡션

{insta.get('reels_caption', '')}

## 해시태그

{' '.join(insta.get('hashtags') or [])}

## 캐러셀

{slides}

## 스토리 문구

{_lines(insta.get('story_lines'))}

## 썸네일 아이디어

{_lines(insta.get('thumbnail_ideas'))}
"""


def render_blog(data: dict) -> str:
    blog = data.get("b3_blog") or {}
    titles = blog.get("seo_title_candidates") or [""]
    photos = _lines(
        f"{p.get('after_section', '')} 뒤 — {p.get('description', '')}"
        for p in blog.get("photo_slots") or []
    )
    return f"""# 네이버 블로그 초안

## 제목 후보

{_lines(titles)}

## 메타 설명

{blog.get('meta_description', '')}

---

{blog.get('body_markdown', '')}

---

## 사진 삽입 위치

{photos}

## 태그

{' '.join(f"#{t.lstrip('#')}" for t in blog.get('tags') or [])}
"""
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m pytest tests/test_formatter.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: `render.py` CLI 구현**

```python
"""검증된 결과 JSON을 마크다운 파일로 쓴다.

사용법:
    python -m yunjin_studio.render <output_dir>
"""

import json
import sys
from pathlib import Path

from .formatter import render_blog, render_instagram, render_shooting_guide

USAGE = "사용법: python -m yunjin_studio.render <output_dir>"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(USAGE)
        return 2

    out_dir = Path(args[0])
    shooting_path = out_dir / "_raw_shooting.json"
    publish_path = out_dir / "_raw_publish.json"

    if not shooting_path.exists():
        print(f"{shooting_path} 없음")
        return 1

    shooting = json.loads(shooting_path.read_text(encoding="utf-8"))
    written = []

    (out_dir / "00_recipe_card.json").write_text(
        json.dumps(shooting.get("recipe_card") or {}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    written.append("00_recipe_card.json")

    (out_dir / "01_촬영가이드.md").write_text(render_shooting_guide(shooting), encoding="utf-8")
    written.append("01_촬영가이드.md")

    if publish_path.exists():
        publish = json.loads(publish_path.read_text(encoding="utf-8"))
        (out_dir / "02_인스타.md").write_text(render_instagram(publish), encoding="utf-8")
        (out_dir / "03_블로그.md").write_text(render_blog(publish), encoding="utf-8")
        written += ["02_인스타.md", "03_블로그.md"]
    else:
        print(f"경고: {publish_path.name} 없음 — 인스타/블로그는 건너뜁니다.")

    print(f"{out_dir}에 {len(written)}개 파일 생성: {', '.join(written)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: 전체 테스트 통과 확인**

Run: `python -m pytest tests/ -v`
Expected: PASS (34 passed)

- [ ] **Step 7: 커밋**

```bash
git -C C:/Users/yjkim add Desktop/Claude_project/Make_Contents/yunjin_studio/formatter.py \
                          Desktop/Claude_project/Make_Contents/yunjin_studio/render.py \
                          Desktop/Claude_project/Make_Contents/tests/test_formatter.py
git -C C:/Users/yjkim commit -m "feat(yunjin-studio): 마크다운 포맷터와 render CLI"
```

---

### Task 6: Claude Code 스킬 (경로 1 완성)

**Files:**
- Create: `.claude/skills/recipe-studio/SKILL.md`

**Interfaces:**
- Consumes: `channel_profile.json`, `prompts/*.md`, `Recipe/*.txt`, `python -m yunjin_studio.validate`, `python -m yunjin_studio.render`
- Produces: `output/<YYYY-MM-DD>_<요리명>/` 폴더 6개 파일

이 태스크의 검증은 단위 테스트가 아니라 **실제 실행**이다. 레시피 2건으로 끝까지 돌려본다.

- [ ] **Step 1: `.claude/skills/recipe-studio/SKILL.md` 작성**

````markdown
---
name: recipe-studio
description: 윤진 Studio — Recipe 폴더의 레시피 텍스트로 촬영 가이드(A1~A5), 인스타 패키지, 네이버 블로그 글을 생성한다. 사용자가 레시피 이름을 대며 콘텐츠·촬영 가이드·블로그 글 생성을 요청할 때 사용.
---

# 레시피 콘텐츠 생성

`Make_Contents` 디렉터리에서 실행한다. Anthropic API를 호출하지 않는다 — 당신이 직접 생성한다.

## 인자

- 레시피 이름 (필수) — `Recipe/` 안의 파일명(확장자 제외)
- 러닝타임 (선택, 기본 60) — 30 / 60 / 90
- 에피소드 (선택)

이름을 주지 않았으면 `Recipe/*.txt` 목록을 보여주고 고르게 한다.

## 절차

1. `channel_profile.json`을 읽는다.
2. `Recipe/<이름>.txt`를 읽는다. 파일에 `[에피소드]` 섹션이 있으면 본문과 분리한다.
3. `prompts/shooting_guide.md`를 읽는다. 템플릿의 `{{CHANNEL_PROFILE}}` `{{DISH_NAME}}`
   `{{RECIPE_BODY}}` `{{EPISODE}}` `{{DURATION_SEC}}` 토큰을 실제 값으로 바꾼 뒤,
   **그 지시를 그대로 수행해** JSON을 만든다.
4. `output/<오늘날짜>_<요리명>/_raw_shooting.json`에 저장한다.
5. `prompts/publish_pack.md`를 읽고 `{{CHANNEL_PROFILE}}` `{{RECIPE_CARD}}`를 채운다.
   `{{RECIPE_CARD}}`에는 4단계 결과의 `recipe_card`를 넣는다.
   지시를 수행해 JSON을 만들고 같은 폴더의 `_raw_publish.json`에 저장한다.
6. 검증한다:

   ```bash
   python -m yunjin_studio.validate output/<폴더>
   ```

   실패하면 오류 메시지가 가리키는 항목을 고쳐 해당 `_raw_*.json`을 다시 쓰고 재검증한다.
   통과할 때까지 반복한다.
7. 마크다운으로 변환한다:

   ```bash
   python -m yunjin_studio.render output/<폴더>
   ```

8. 생성된 파일 목록과 블로그 제목 후보 3개를 사용자에게 보여준다.

## 반드시 지킬 것

- `channel_profile.json`의 `signature_rules`를 어기지 않는다.
- 계량 표현(`measure_note`)을 다른 단위로 바꾸지 않는다. 블로그 본문에도 원형 그대로 넣는다.
- 모든 팁에 `why`(왜 그래야 하는가)를 채운다. 원문에 이미 원리가 적혀 있으니 찾아서 옮긴다.
- 레시피 원문에 없는 재료나 조리 단계를 지어내지 않는다.
- `output/`은 git에 커밋하지 않는다.
````

- [ ] **Step 2: 제육볶음으로 실행**

Claude Code에서 스킬을 호출한다: `/recipe-studio 제육볶음`

Expected:
- `output/2026-08-29_제육볶음/`에 `_raw_shooting.json`, `_raw_publish.json`, `00_recipe_card.json`, `01_촬영가이드.md`, `02_인스타.md`, `03_블로그.md` 6개 생성
- `python -m yunjin_studio.validate output/2026-08-29_제육볶음` → `검증 통과`, 종료코드 0

- [ ] **Step 3: 수용 기준 육안 확인**

`output/2026-08-29_제육볶음/`을 열어 아래를 확인한다.

- [ ] `03_블로그.md`와 `02_인스타.md`에 `1T = 아빠 숟가락`이 원형 그대로 있다
- [ ] `01_촬영가이드.md`의 "팁 (무엇을 / 왜)" 항목마다 "왜:" 뒤가 비어 있지 않다
- [ ] A4 차별화 포인트가 일반론이 아니라 이 레시피의 원리(식초 휘발로 잡내 제거, 고기 기름에 양념 먼저 볶기, 인덕션 잔열 오버쿡 등)에서 나왔다
- [ ] `00_recipe_card.json`의 재료 그룹이 주재료 / 고기 밑간 / 제육 양념장으로 분리되어 있다
- [ ] 원문에 없는 재료가 추가되지 않았다

기준을 못 넘으면 `prompts/*.md`를 고치고 2단계부터 다시 돌린다. **코드는 고치지 않는다.**

- [ ] **Step 4: 항정살 레시피로 실행**

`/recipe-studio 항정상꽈리고추볶음 duration=30`

Expected: 위와 동일한 6개 파일, 검증 통과. `a2_script`의 마지막 타임코드가 30초 부근이다.

- [ ] **Step 5: 커밋**

프롬프트를 튜닝했다면 함께 커밋한다. `output/`은 제외한다.

```bash
git -C C:/Users/yjkim add Desktop/Claude_project/Make_Contents/.claude/skills/recipe-studio/SKILL.md \
                          Desktop/Claude_project/Make_Contents/prompts/
git -C C:/Users/yjkim commit -m "feat(yunjin-studio): Claude Code 스킬 추가 (경로 1 완성)"
```

---

### Task 7: Anthropic API 생성기

**Files:**
- Create: `yunjin_studio/generator.py`
- Test: `tests/test_generator.py`

**Interfaces:**
- Consumes: `yunjin_studio.context.build_shooting_prompt`, `build_publish_prompt`, `yunjin_studio.recipe.Recipe`
- Produces:
  - `yunjin_studio.generator.SYSTEM_PROMPT: str`
  - `yunjin_studio.generator.extract_json(text: str) -> dict`
  - `yunjin_studio.generator.build_request_kwargs(profile: dict) -> dict`
  - `yunjin_studio.generator.generate_shooting(profile: dict, recipe: Recipe, duration_sec: int = 60, client=None) -> dict` — 호출①
  - `yunjin_studio.generator.generate_publish(profile: dict, recipe_card: dict, client=None) -> dict` — 호출②

**호출을 두 함수로 나눈 이유**: 스펙 §12는 "호출② 실패 시 호출①의 결과물은 보존한다"를 요구한다.
두 호출을 한 함수 안에 묶으면 호출②의 예외가 호출① 결과까지 날려버린다.
호출자(경로 2의 `app.py`)가 호출① 직후 `_raw_shooting.json`을 저장하고 나서 호출②를 하도록 강제한다.

- [ ] **Step 1: SDK 업그레이드**

```bash
pip install -U anthropic
python -c "import anthropic; print(anthropic.__version__)"
```

현재 설치본은 0.105.2다. `thinking`, `output_config`는 신형 파라미터이므로 최신으로 올린다.
업그레이드 후에도 해당 파라미터가 거부되면(`TypeError` 또는 400) `channel_profile.json`의
`model.effort`를 `null`로, `model.thinking`을 `false`로 두면 아래 `build_request_kwargs`가
그 키를 빼고 요청한다.

- [ ] **Step 2: 실패하는 테스트 작성**

`tests/test_generator.py`:

```python
import json
from types import SimpleNamespace

import pytest

from tests.test_schema import VALID_PUBLISH, VALID_SHOOTING
from yunjin_studio.generator import (
    build_request_kwargs,
    extract_json,
    generate_publish,
    generate_shooting,
)
from yunjin_studio.recipe import Recipe


def test_extract_json_handles_bare_object():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_strips_code_fence():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_ignores_surrounding_prose():
    assert extract_json('네, 만들었습니다.\n{"a": 1}\n필요하면 말씀해주세요.') == {"a": 1}


def test_extract_json_raises_on_garbage():
    with pytest.raises(ValueError):
        extract_json("JSON이 없습니다")


def test_build_request_kwargs_uses_profile_model():
    kwargs = build_request_kwargs({"model": {"id": "claude-sonnet-5", "effort": "medium"}})
    assert kwargs["model"] == "claude-sonnet-5"
    assert kwargs["output_config"] == {"effort": "medium"}
    assert kwargs["thinking"] == {"type": "adaptive"}


def test_build_request_kwargs_omits_disabled_options():
    kwargs = build_request_kwargs({"model": {"id": "claude-opus-5", "effort": None, "thinking": False}})
    assert "output_config" not in kwargs
    assert "thinking" not in kwargs


class FakeStream:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        text = json.dumps(self._payload, ensure_ascii=False)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


class FakeClient:
    """payloads의 원소가 Exception이면 그 호출에서 예외를 던진다."""

    def __init__(self, payloads):
        self._payloads = list(payloads)
        self.calls = []

        outer = self

        class Messages:
            def stream(self, **kwargs):
                outer.calls.append(kwargs)
                payload = outer._payloads.pop(0)
                if isinstance(payload, Exception):
                    raise payload
                return FakeStream(payload)

        self.messages = Messages()


PROFILE = {"model": {"id": "claude-opus-5", "effort": "high"}, "signature_rules": []}
RECIPE = Recipe(dish_name="제육볶음", body="삼겹살 600g", episode="")


def test_generate_shooting_returns_parsed_json():
    client = FakeClient([VALID_SHOOTING])
    assert generate_shooting(PROFILE, RECIPE, client=client) == VALID_SHOOTING
    assert len(client.calls) == 1


def test_generate_shooting_passes_duration_into_prompt():
    client = FakeClient([VALID_SHOOTING])
    generate_shooting(PROFILE, RECIPE, duration_sec=90, client=client)
    assert "90초" in client.calls[0]["messages"][0]["content"]


def test_generate_publish_receives_recipe_card():
    client = FakeClient([VALID_PUBLISH])
    card = VALID_SHOOTING["recipe_card"]
    assert generate_publish(PROFILE, card, client=client) == VALID_PUBLISH

    prompt = client.calls[0]["messages"][0]["content"]
    assert "1T = 아빠 숟가락" in prompt
    assert "제육볶음" in prompt


def test_publish_failure_does_not_touch_shooting_result():
    """스펙 §12 — 호출② 실패가 호출① 결과를 망가뜨리면 안 된다."""
    client = FakeClient([VALID_SHOOTING, RuntimeError("API 장애")])
    shooting = generate_shooting(PROFILE, RECIPE, client=client)

    with pytest.raises(RuntimeError):
        generate_publish(PROFILE, shooting["recipe_card"], client=client)

    assert shooting == VALID_SHOOTING
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `python -m pytest tests/test_generator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'yunjin_studio.generator'`

- [ ] **Step 4: `generator.py` 구현**

```python
"""Anthropic API로 두 번 호출해 촬영 가이드와 발행 콘텐츠를 만든다."""

import json
import os

from .context import build_publish_prompt, build_shooting_prompt
from .recipe import Recipe

SYSTEM_PROMPT = (
    "당신은 한국어 요리·육아 콘텐츠 제작 어시스턴트입니다. "
    "요청받은 JSON 객체 하나만 출력하고, 그 앞뒤에 어떤 설명도 붙이지 마세요."
)
MAX_TOKENS = 16000


def extract_json(text: str) -> dict:
    """응답 텍스트에서 JSON 객체 하나를 뽑는다."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.lstrip().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"응답에서 JSON 객체를 찾지 못했습니다: {text[:200]}")
    return json.loads(cleaned[start : end + 1])


def build_request_kwargs(profile: dict) -> dict:
    model_config = profile.get("model") or {}
    kwargs: dict = {
        "model": model_config.get("id", "claude-opus-5"),
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
    }
    effort = model_config.get("effort")
    if effort:
        kwargs["output_config"] = {"effort": effort}
    if model_config.get("thinking", True):
        kwargs["thinking"] = {"type": "adaptive"}
    return kwargs


def _make_client():
    from anthropic import Anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY가 설정되지 않았습니다. Make_Contents/.env에 추가하세요."
        )
    return Anthropic()


def _call(client, kwargs: dict, prompt: str) -> dict:
    with client.messages.stream(**kwargs, messages=[{"role": "user", "content": prompt}]) as stream:
        message = stream.get_final_message()
    text = "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
    return extract_json(text)


def generate_shooting(
    profile: dict,
    recipe: Recipe,
    duration_sec: int = 60,
    client=None,
) -> dict:
    """호출① — 레시피 카드와 촬영 가이드 A1~A5."""
    client = client or _make_client()
    prompt = build_shooting_prompt(profile, recipe, duration_sec)
    return _call(client, build_request_kwargs(profile), prompt)


def generate_publish(profile: dict, recipe_card: dict, client=None) -> dict:
    """호출② — 인스타 패키지와 블로그 글.

    호출자는 호출①의 결과를 디스크에 저장한 뒤 이 함수를 부른다.
    그래야 여기서 실패해도 호출① 결과가 남는다(스펙 §12).
    """
    client = client or _make_client()
    prompt = build_publish_prompt(profile, recipe_card)
    return _call(client, build_request_kwargs(profile), prompt)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `python -m pytest tests/ -v`
Expected: PASS (41 passed)

- [ ] **Step 6: 실제 API로 1회 확인**

`Make_Contents/.env`에 `ANTHROPIC_API_KEY=sk-ant-...`를 넣고 (`.gitignore`에 이미 포함됨):

```bash
python -c "
from dotenv import load_dotenv; load_dotenv()
import json, pathlib
from yunjin_studio.context import load_profile
from yunjin_studio.recipe import load_recipe
from yunjin_studio.generator import generate_shooting, generate_publish
profile, _ = load_profile()
d = pathlib.Path('output/api_test'); d.mkdir(parents=True, exist_ok=True)
shooting = generate_shooting(profile, load_recipe('제육볶음'))
(d/'_raw_shooting.json').write_text(json.dumps(shooting, ensure_ascii=False, indent=2), encoding='utf-8')
publish = generate_publish(profile, shooting['recipe_card'])
(d/'_raw_publish.json').write_text(json.dumps(publish, ensure_ascii=False, indent=2), encoding='utf-8')
print('ok')
"
python -m yunjin_studio.validate output/api_test
python -m yunjin_studio.render output/api_test
```

Expected: `ok` → `검증 통과` → 4개 파일 생성.

`TypeError: unexpected keyword argument 'output_config'` 또는 400이 나면 1단계의 안내대로
`channel_profile.json`에서 `model.effort`를 `null`로, `model.thinking`을 `false`로 바꾸고 다시 실행한다.

- [ ] **Step 7: 커밋**

```bash
git -C C:/Users/yjkim add Desktop/Claude_project/Make_Contents/yunjin_studio/generator.py \
                          Desktop/Claude_project/Make_Contents/tests/test_generator.py \
                          Desktop/Claude_project/Make_Contents/requirements.txt \
                          Desktop/Claude_project/Make_Contents/channel_profile.json
git -C C:/Users/yjkim commit -m "feat(yunjin-studio): Anthropic API 생성기"
```

---

### Task 8: Streamlit UI (경로 2 완성)

**Files:**
- Create: `app.py`

**Interfaces:**
- Consumes: `yunjin_studio` 전체
- Produces: 없음 (최종 진입점)

- [ ] **Step 1: `app.py` 작성**

```python
"""윤진 Studio — 레시피 콘텐츠 생성기."""

import json
from datetime import date
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from yunjin_studio.context import ROOT, load_profile
from yunjin_studio.formatter import render_blog, render_instagram, render_shooting_guide
from yunjin_studio.generator import generate_publish, generate_shooting
from yunjin_studio.recipe import list_recipes, load_recipe
from yunjin_studio.schema import validate_publish_pack, validate_shooting_guide

load_dotenv(ROOT / ".env")

st.set_page_config(page_title="윤진 Studio", page_icon="🍳", layout="wide")
st.title("🍳 윤진 Studio")
st.caption("레시피 텍스트 하나로 촬영 가이드 · 인스타 · 블로그를 만듭니다.")

profile, warnings = load_profile()
for warning in warnings:
    st.warning(warning)

names = list_recipes()
if not names:
    st.error("Recipe 폴더에 .txt 파일이 없습니다.")
    st.stop()

col_left, col_right = st.columns([2, 1])
with col_left:
    name = st.selectbox("레시피", names)
with col_right:
    duration = st.selectbox("목표 러닝타임(초)", [30, 60, 90], index=1)
episode = st.text_input("비하인드 에피소드 (선택)", "")

if st.button("생성", type="primary"):
    recipe = load_recipe(name, episode=episode)
    out_dir = ROOT / "output" / f"{date.today():%Y-%m-%d}_{name}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 호출①의 결과를 먼저 디스크에 남긴다. 호출②가 실패해도 살아남게 하기 위함(스펙 §12).
    with st.spinner("① 촬영 가이드를 만드는 중… (1~2분)"):
        shooting = generate_shooting(profile, recipe, duration_sec=duration)
    (out_dir / "_raw_shooting.json").write_text(
        json.dumps(shooting, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with st.spinner("② 인스타·블로그를 만드는 중… (1~2분)"):
        publish = generate_publish(profile, shooting.get("recipe_card") or {})
    (out_dir / "_raw_publish.json").write_text(
        json.dumps(publish, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    measure_note = (shooting.get("recipe_card") or {}).get("measure_note", "")
    errors = validate_shooting_guide(shooting) + validate_publish_pack(publish, measure_note)
    if errors:
        st.warning("검증 경고 " + str(len(errors)) + "건")
        for error in errors:
            st.write("- " + error)

    st.session_state["result"] = (str(out_dir), shooting, publish)

if "result" in st.session_state:
    out_dir_str, shooting, publish = st.session_state["result"]
    out_dir = Path(out_dir_str)

    card_md = json.dumps(shooting.get("recipe_card") or {}, ensure_ascii=False, indent=2)
    guide_md = render_shooting_guide(shooting)
    insta_md = render_instagram(publish)
    blog_md = render_blog(publish)

    (out_dir / "00_recipe_card.json").write_text(card_md, encoding="utf-8")
    (out_dir / "01_촬영가이드.md").write_text(guide_md, encoding="utf-8")
    (out_dir / "02_인스타.md").write_text(insta_md, encoding="utf-8")
    (out_dir / "03_블로그.md").write_text(blog_md, encoding="utf-8")

    st.success(f"저장 완료: {out_dir}")

    tabs = st.tabs(["레시피 카드", "촬영 가이드", "인스타", "블로그"])
    for tab, label, body, filename in zip(
        tabs,
        ["레시피 카드", "촬영 가이드", "인스타", "블로그"],
        [card_md, guide_md, insta_md, blog_md],
        ["00_recipe_card.json", "01_촬영가이드.md", "02_인스타.md", "03_블로그.md"],
    ):
        with tab:
            if filename.endswith(".json"):
                st.code(body, language="json")
            else:
                st.markdown(body)
            st.download_button(f"{label} 내려받기", body, file_name=filename)
```

- [ ] **Step 2: 실행 확인**

```bash
streamlit run app.py
```

Expected:
- 브라우저가 열리고 레시피 드롭다운에 `제육볶음`, `항정상꽈리고추볶음`이 보인다
- 제육볶음 선택 → 러닝타임 60 → "생성" → 1~3분 후 탭 4개에 결과가 뜬다
- `output/<날짜>_제육볶음/`에 6개 파일이 생긴다
- 내려받기 버튼 4개가 동작한다

- [ ] **Step 3: 전체 테스트 재확인**

Run: `python -m pytest tests/ -v`
Expected: PASS (42 passed)

- [ ] **Step 4: 커밋**

```bash
git -C C:/Users/yjkim add Desktop/Claude_project/Make_Contents/app.py
git -C C:/Users/yjkim commit -m "feat(yunjin-studio): Streamlit UI (경로 2 완성)"
```

---

## 완료 확인 (스펙 §15 수용 기준)

전체 구현 후 아래를 모두 확인한다.

- [ ] 1. `Recipe/제육볶음.txt`로 경로 1 실행 → `output/`에 파일 생성 (Task 6 Step 2)
- [ ] 2. `Recipe/항정상꽈리고추볶음.txt`로도 동일 동작 (Task 6 Step 4)
- [ ] 3. 블로그·인스타에 `1T = 아빠 숟가락` 원형 유지 — `validate`가 자동 검사 (Task 4)
- [ ] 4. 모든 팁에 `why` 존재 — `validate`가 자동 검사 (Task 4)
- [ ] 5. A4 차별화 포인트가 원본 레시피의 원리에서 도출 (Task 6 Step 3, 육안)
- [ ] 6. `python -m pytest tests/ -v` 전체 통과
- [ ] 7. `prompts/*.md`만 수정하고 재실행해도 결과가 바뀐다 (Task 6 Step 3에서 확인)

## 후속 (이번 범위 밖)

스펙 §2.2와 §16에 따라 아래는 별도 계획으로 다룬다.

- Phase B 영상 분석 (Whisper STT · FFmpeg · PySceneDetect) → B1 편집 가이드, B4 유튜브
- 육아 에피소드 카드 Input
- B5 수익화 연결
- Tailscale 원격 접속
- `YJ_Content_Factory_SRS_윤진.html` v2.1 반영
