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
