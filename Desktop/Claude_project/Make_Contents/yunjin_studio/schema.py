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


def _as_dict(value) -> dict:
    """value 가 dict 가 아니면 빈 dict 로 취급 — 잘못된 타입도 예외 대신 오류 목록으로."""
    return value if isinstance(value, dict) else {}


def _as_list(value) -> list:
    """value 가 list 가 아니면 빈 list 로 취급 — 잘못된 타입도 예외 대신 오류 목록으로."""
    return value if isinstance(value, list) else []


def _as_str(value) -> str:
    """value 를 문자열로 강제 — None 은 빈 문자열, 그 외 타입은 str() 변환."""
    if isinstance(value, str):
        return value
    return "" if value is None else str(value)


def validate_shooting_guide(data: dict) -> list[str]:
    errors: list[str] = []

    data = _as_dict(data)

    for key in SHOOTING_KEYS:
        if key not in data:
            errors.append(f"필수 키 누락: {key}")

    card = _as_dict(data.get("recipe_card"))
    for key in CARD_KEYS:
        if not card.get(key):
            errors.append(f"recipe_card.{key} 누락 또는 비어 있음")

    raw_tips = card.get("tips")
    # 존재하지만 list 가 아닌 값(문자열, dict 등)은 위의 진위값 검사를 통과해 버리고
    # 아래에서 _as_list 로 조용히 빈 리스트가 되어 사라질 수 있다 — 타입 자체를 먼저 짚는다.
    if raw_tips and not isinstance(raw_tips, list):
        errors.append(
            f"recipe_card.tips 는 list 여야 함 (실제 타입: {type(raw_tips).__name__})"
        )

    for index, tip in enumerate(_as_list(raw_tips)):
        tip = _as_dict(tip)
        if _blank(tip.get("what")):
            errors.append(f"recipe_card.tips[{index}].what 비어 있음")
        if _blank(tip.get("why")):
            errors.append(
                f"recipe_card.tips[{index}].why 비어 있음 — 원리 설명은 채널 정체성 규칙"
            )

    scenario = _as_dict(data.get("a1_scenario"))
    if len(_as_list(scenario.get("hook_lines"))) != 3:
        errors.append("a1_scenario.hook_lines 는 후보 3개여야 함")

    if not _as_list(data.get("a2_script")):
        errors.append("a2_script 비어 있음")

    camera = _as_dict(data.get("a3_camera"))
    if len(_as_list(camera.get("must_shots"))) != 5:
        errors.append("a3_camera.must_shots 는 5개여야 함")

    if not _as_list(_as_dict(data.get("a4_differentiator")).get("channel_edge")):
        errors.append("a4_differentiator.channel_edge 비어 있음")

    return errors


def validate_publish_pack(data: dict, measure_note: str = "") -> list[str]:
    errors: list[str] = []

    data = _as_dict(data)

    for key in ("b2_instagram", "b3_blog"):
        if key not in data:
            errors.append(f"필수 키 누락: {key}")

    instagram = _as_dict(data.get("b2_instagram"))
    # carousel/hashtags 는 길이·진위 검사 단 한 곳에서만 값을 사용하므로, 잘못된 타입도
    # _as_list 로 빈 리스트가 되는 순간 그 자리에서 바로 걸린다 (놓칠 틈이 없음 — 설계상 안전).
    carousel = _as_list(instagram.get("carousel"))
    if not CAROUSEL_MIN <= len(carousel) <= CAROUSEL_MAX:
        errors.append(
            f"b2_instagram.carousel 장수 {len(carousel)} — {CAROUSEL_MIN}~{CAROUSEL_MAX}장이어야 함"
        )
    if _blank(instagram.get("reels_caption")):
        errors.append("b2_instagram.reels_caption 비어 있음")
    if not _as_list(instagram.get("hashtags")):
        errors.append("b2_instagram.hashtags 비어 있음")

    blog = _as_dict(data.get("b3_blog"))
    raw_body = blog.get("body_markdown")
    # dict/list 같은 값도 _as_str 로 str() 변환하면 비어 있지 않은 문자열이 되어 버려
    # 아래 blank 검사를 조용히 통과한다 — 타입 자체를 먼저 짚는다.
    if raw_body is not None and not isinstance(raw_body, str):
        errors.append(
            f"b3_blog.body_markdown 는 문자열이어야 함 (실제 타입: {type(raw_body).__name__})"
        )
    body = _as_str(raw_body)
    if _blank(body):
        errors.append("b3_blog.body_markdown 비어 있음")
    # seo_title_candidates 도 carousel 과 같은 이유로 단일 검사 지점이라 잘못된 타입을
    # 놓치지 않는다 (길이 0 이 되어 3개 요구조건에 항상 걸림).
    if len(_as_list(blog.get("seo_title_candidates"))) != 3:
        errors.append("b3_blog.seo_title_candidates 는 후보 3개여야 함")
    if measure_note and measure_note not in body:
        errors.append(
            f"b3_blog.body_markdown 에 계량 기준 '{measure_note}' 이(가) 원형 그대로 없음"
        )

    return errors
