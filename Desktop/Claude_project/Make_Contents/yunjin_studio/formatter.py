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
