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


def _wrong_type(value, expected: type) -> str | None:
    """value 가 참 값(존재)인데 expected 타입이 아니면 실제 타입 이름을 돌려준다.

    없거나 비어 있는 값(None, "", [], {}, 0, False)은 각 필드의 '누락 또는 비어 있음'
    검사가 따로 담당한다 — formatter.py 의 `X.get(key) or {}` / `... or []` 패턴이
    falsy 값은 이미 안전하게 빈 컨테이너로 대체하므로, 여기서는 formatter.py 가 실제로
    반복/색인해서 터지는 "존재하지만 잘못된 타입" 조합만 잡는다.
    """
    if not value:
        return None
    if isinstance(value, expected):
        return None
    return type(value).__name__


def _check_type(errors: list[str], path: str, value, expected: type, phrase: str) -> bool:
    """value 가 존재하는데 expected 타입이 아니면 오류를 남기고 True 를 돌려준다
    (호출부가 원소 단위 검사를 건너뛸 신호로 쓴다 — 타입 자체가 틀렸으면 원소를 볼 필요가 없다)."""
    wrong = _wrong_type(value, expected)
    if wrong:
        errors.append(f"{path} 는 {phrase} (실제 타입: {wrong})")
        return True
    return False


def _check_entries(errors: list[str], path: str, items, expected: type, phrase: str) -> None:
    """items(list) 의 각 원소가 expected 타입이 아니면 오류를 남긴다.

    formatter.py 가 원소에 .get()/.lstrip() 등을 호출하는 필드에서만 부른다 — 그 외의
    필드(문자열을 그대로 나열만 하는 목록 등)는 원소 타입이 무엇이든 formatter.py 가
    f-string 으로 그대로 찍어내므로 검사할 필요가 없다.
    """
    for index, item in enumerate(items or []):
        if not isinstance(item, expected):
            errors.append(f"{path}[{index}] 는 {phrase} (실제 타입: {type(item).__name__})")


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

    # recipe_card.ingredients: formatter._ingredients 가 각 group 에 .get("items")/.get("group")를,
    # 각 item 에 .get("name")/.get("amount")를 호출한다 — 존재하지만 list 가 아니거나(문자열 등),
    # list 안에 dict 가 아닌 원소가 섞이면 위의 truthy 검사를 통과해 버리고 렌더링에서 터진다.
    raw_ingredients = card.get("ingredients")
    if not _check_type(errors, "recipe_card.ingredients", raw_ingredients, list, "list 여야 함"):
        for g_index, group in enumerate(_as_list(raw_ingredients)):
            group_path = f"recipe_card.ingredients[{g_index}]"
            if not isinstance(group, dict):
                errors.append(f"{group_path} 는 dict 여야 함 (실제 타입: {type(group).__name__})")
                continue
            raw_items = group.get("items")
            if not _check_type(errors, f"{group_path}.items", raw_items, list, "list 여야 함"):
                _check_entries(errors, f"{group_path}.items", _as_list(raw_items), dict, "dict 여야 함")

    # recipe_card.steps: formatter._steps 가 각 step 에 .get()/[] 를 호출한다 — 위와 동일한 이유.
    raw_steps = card.get("steps")
    if not _check_type(errors, "recipe_card.steps", raw_steps, list, "list 여야 함"):
        _check_entries(errors, "recipe_card.steps", _as_list(raw_steps), dict, "dict 여야 함")

    # recipe_card.fail_points: formatter 는 _lines() 로 그대로 나열하지만, truthy 스칼라
    # (예: 정수)가 들어오면 반복 자체가 불가능해 TypeError 가 난다.
    _check_type(errors, "recipe_card.fail_points", card.get("fail_points"), list, "list 여야 함")

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

    # a1_scenario.structure: formatter 가 각 원소에 .get("from_sec") 등을 호출하는 제너레이터를
    # 만든다 — 소비되는 시점(= _lines 내부)에야 터지므로 검증 시점에 미리 잡아야 한다.
    raw_structure = scenario.get("structure")
    if not _check_type(errors, "a1_scenario.structure", raw_structure, list, "list 여야 함"):
        _check_entries(errors, "a1_scenario.structure", _as_list(raw_structure), dict, "dict 여야 함")

    raw_a2_script = data.get("a2_script")
    # a2_script: 예전에는 _as_list 로 조용히 빈 리스트가 되어 "비어 있음" 이라고만 보고했다 —
    # 실제로는 "비어 있음"이 아니라 "타입이 틀림"인 경우를 구분해서 알려준다. formatter 가
    # 각 원소에 .get()을 호출하므로 원소 타입도 함께 짚는다.
    if not raw_a2_script:
        errors.append("a2_script 누락 또는 비어 있음")
    elif not _check_type(errors, "a2_script", raw_a2_script, list, "list 여야 함"):
        _check_entries(errors, "a2_script", raw_a2_script, dict, "dict 여야 함")

    camera = _as_dict(data.get("a3_camera"))
    if len(_as_list(camera.get("must_shots"))) != 5:
        errors.append("a3_camera.must_shots 는 5개여야 함")

    # a3_camera.scenes: formatter 가 각 원소에 .get("scene") 등을 호출한다 — 지금까지 전혀
    # 검증되지 않던 필드라 잘못된 타입이 그대로 렌더링까지 흘러가 터졌다.
    raw_scenes = camera.get("scenes")
    if not _check_type(errors, "a3_camera.scenes", raw_scenes, list, "list 여야 함"):
        _check_entries(errors, "a3_camera.scenes", _as_list(raw_scenes), dict, "dict 여야 함")

    _check_type(errors, "a3_camera.common_mistakes", camera.get("common_mistakes"), list, "list 여야 함")

    differentiator = _as_dict(data.get("a4_differentiator"))
    raw_channel_edge = differentiator.get("channel_edge")
    if not raw_channel_edge:
        errors.append("a4_differentiator.channel_edge 누락 또는 비어 있음")
    else:
        _check_type(errors, "a4_differentiator.channel_edge", raw_channel_edge, list, "list 여야 함")

    _check_type(
        errors, "a4_differentiator.series_ideas", differentiator.get("series_ideas"), list, "list 여야 함"
    )

    # a5_checklist: 지금까지 키 존재 여부만 확인했을 뿐 값 자체는 전혀 검증하지 않았다.
    # formatter 는 `data.get("a5_checklist") or {}` 로 받아 바로 .get() 을 호출하므로,
    # truthy 한 비-dict 값(문자열 등)이 오면 컨테이너 단계에서부터 터진다.
    raw_checklist = data.get("a5_checklist")
    if not _check_type(errors, "a5_checklist", raw_checklist, dict, "dict 여야 함"):
        checklist = _as_dict(raw_checklist)
        for field in ("before_cooking", "equipment", "during_shoot", "must_not_miss", "after_shoot"):
            _check_type(errors, f"a5_checklist.{field}", checklist.get(field), list, "list 여야 함")

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
    # carousel 슬라이드 하나하나는 formatter 가 .get("headline") 등을 호출한다 — 장수만
    # 맞고 원소가 dict 가 아니면 여전히 렌더링에서 터진다.
    _check_entries(errors, "b2_instagram.carousel", carousel, dict, "dict 여야 함")

    if _blank(instagram.get("reels_caption")):
        errors.append("b2_instagram.reels_caption 비어 있음")

    raw_hashtags = instagram.get("hashtags")
    # hashtags: formatter 가 ' '.join(...) 으로 이어 붙이므로 리스트여야 하고, 원소도
    # 전부 문자열이어야 한다(정수 등이 섞이면 join 자체가 TypeError).
    if not raw_hashtags:
        errors.append("b2_instagram.hashtags 비어 있음")
    elif not _check_type(errors, "b2_instagram.hashtags", raw_hashtags, list, "list 여야 함"):
        _check_entries(errors, "b2_instagram.hashtags", raw_hashtags, str, "문자열이어야 함")

    _check_type(errors, "b2_instagram.story_lines", instagram.get("story_lines"), list, "list 여야 함")
    _check_type(
        errors, "b2_instagram.thumbnail_ideas", instagram.get("thumbnail_ideas"), list, "list 여야 함"
    )

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

    # photo_slots: 지금까지 전혀 검증되지 않았다. formatter 가 각 원소에 .get("after_section")
    # 등을 호출하므로, list 여야 하고 원소도 dict 여야 한다.
    raw_photo_slots = blog.get("photo_slots")
    if not _check_type(errors, "b3_blog.photo_slots", raw_photo_slots, list, "list 여야 함"):
        _check_entries(errors, "b3_blog.photo_slots", _as_list(raw_photo_slots), dict, "dict 여야 함")

    # tags: formatter 가 각 원소에 .lstrip("#") 을 호출하므로 문자열이어야 한다.
    raw_tags = blog.get("tags")
    if not _check_type(errors, "b3_blog.tags", raw_tags, list, "list 여야 함"):
        _check_entries(errors, "b3_blog.tags", _as_list(raw_tags), str, "문자열이어야 함")

    if measure_note and measure_note not in body:
        errors.append(
            f"b3_blog.body_markdown 에 계량 기준 '{measure_note}' 이(가) 원형 그대로 없음"
        )

    return errors
