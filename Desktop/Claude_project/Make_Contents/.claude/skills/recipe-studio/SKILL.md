---
name: recipe-studio
description: 사용자가 Recipe/ 폴더의 레시피로 촬영 가이드·인스타그램·네이버 블로그 콘텐츠를 만들어 달라고 할 때 사용한다. API 호출 없이 Claude Code가 직접 생성하는 무료 실행 경로다.
---

# Recipe Studio

`Recipe/<요리명>.txt` 원문 하나로 촬영 가이드 + 인스타그램 + 네이버 블로그 초안을 만든다.
`prompts/*.md`는 Anthropic API에 보내는 프롬프트가 아니라, **Claude Code 자신이 따라야 할
생성 지시서**다. API 호출은 없다 — 이 세션이 프롬프트를 읽고 그 지시대로 직접 콘텐츠를 쓴다.

## 절차

1. `channel_profile.json`을 읽는다 (UTF-8).
2. `Recipe/<요리명>.txt`을 읽는다 (UTF-8). `[에피소드]` 섹션이 있으면 본문과 분리한다.
   요리명이 주어지지 않았으면 `Recipe/*.txt` 목록을 보여주고 어떤 걸 할지 물어본다.
3. `prompts/shooting_guide.md`를 읽고 `{{CHANNEL_PROFILE}}`, `{{DISH_NAME}}`,
   `{{RECIPE_BODY}}`, `{{EPISODE}}`(없으면 `(없음)`), `{{DURATION_SEC}}`(기본 60,
   30/60/90 허용)을 치환한다. 그리고 **템플릿의 지시를 따라 JSON을 직접 생성한다** —
   API를 부르는 게 아니라 이 자리에서 직접 쓰는 것이다.
4. 결과를 `output/<YYYY-MM-DD>_<요리명>/_raw_shooting.json`에 저장한다
   (`ensure_ascii=False`, `indent=2`, UTF-8).
5. `prompts/publish_pack.md`를 읽고 `{{CHANNEL_PROFILE}}`과 `{{RECIPE_CARD}}`(4번에서
   만든 `recipe_card` 객체)를 치환해 생성하고, 같은 폴더의 `_raw_publish.json`에 저장한다.
6. 검증한다: `python -m yunjin_studio.validate output/<폴더>`. exit 0이면 통과. 실패하면
   문제 있는 필드를 한 줄씩 짚어주므로, 해당 `_raw_*.json`을 고쳐서 통과할 때까지
   반복한다.
7. 렌더링한다: `python -m yunjin_studio.render output/<폴더>` — `00_recipe_card.json`,
   `01_촬영가이드.md`, `02_인스타.md`, `03_블로그.md`를 만든다.
8. 사용자에게 생성된 파일 목록과 블로그 제목 후보 3개를 보여준다.

## 규칙

- `channel_profile.json`의 `signature_rules`를 반드시 지킨다.
- **각 레시피의 계량 표현을 원문 그대로 보존한다.** 두 예시 레시피는 일부러 다르게
  쓰여 있다 — 제육볶음은 `1T = 아빠 숟가락`, 항정살은 `1T = 아빠 수저`. 그 레시피가
  쓰는 표현을 `measure_note`와 블로그 본문에 그대로 옮기고, 절대 둘을 하나의 표현으로
  통일하지 않는다.
- 모든 팁은 `why`가 비어 있으면 안 된다. 원문이 이미 그 이유를 설명하고 있으니
  지어내지 말고 원문에서 찾아 옮긴다.
- 원문에 없는 재료나 조리 단계를 지어내지 않는다.
- `a4_differentiator.channel_edge`는 이 레시피만의 구체적 근거에서 나와야 하며,
  일반적인 칭찬이면 안 된다. 참고로 실제 두 실행 결과는 각각 "식초가 휘발되며
  잡내를 데려간다는 설명은 대부분의 제육 영상에 없습니다", "'기름을 닦아낸다'는
  단계 자체가 대부분의 항정살 레시피에 없습니다"였다.
- `output/`은 git에서 제외된다 — 절대 커밋하지 않는다.
- 결과가 검증에서 계속 거부되면 고칠 곳은 `prompts/*.md`이지, Python 코드가 아니다.
