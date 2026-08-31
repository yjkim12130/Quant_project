import copy

from yunjin_studio import formatter
from yunjin_studio.schema import SHOOTING_KEYS, validate_publish_pack, validate_shooting_guide

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


def test_non_dict_tip_entry_is_reported():
    data = copy.deepcopy(VALID_SHOOTING)
    data["recipe_card"]["tips"] = ["just a string tip"]
    errors = validate_shooting_guide(data)
    assert isinstance(errors, list)
    assert any("tips[0].what" in e for e in errors)
    assert any("tips[0].why" in e for e in errors)


def test_non_dict_recipe_card_is_reported():
    data = copy.deepcopy(VALID_SHOOTING)
    data["recipe_card"] = "oops, this is a string"
    errors = validate_shooting_guide(data)
    assert isinstance(errors, list)
    assert any("recipe_card" in e for e in errors)


def test_non_dict_top_level_argument_shooting_guide_is_reported():
    errors = validate_shooting_guide("not a dict at all")
    assert isinstance(errors, list)
    # 잘못된 타입은 빈 dict 로 취급되어 모든 필수 키가 누락으로 보고되어야 한다.
    for key in SHOOTING_KEYS:
        assert any(f"필수 키 누락: {key}" in e for e in errors)


def test_non_dict_top_level_argument_publish_pack_is_reported():
    errors = validate_publish_pack(["not", "a", "dict"])
    assert isinstance(errors, list)
    assert any("필수 키 누락: b2_instagram" in e for e in errors)
    assert any("필수 키 누락: b3_blog" in e for e in errors)


def test_non_dict_b2_instagram_is_reported():
    data = copy.deepcopy(VALID_PUBLISH)
    data["b2_instagram"] = 12345
    errors = validate_publish_pack(data)
    assert isinstance(errors, list)
    assert any("carousel" in e for e in errors)


def test_tips_as_string_is_reported_as_wrong_type():
    """존재하지만 list 가 아닌 tips 는 진위값 검사를 통과해 버리고 이후 _as_list 로
    조용히 사라질 수 있었다 (라운드 2 회귀) — 타입 오류로 이름이 남아야 한다."""
    data = copy.deepcopy(VALID_SHOOTING)
    data["recipe_card"]["tips"] = "salt helps tenderize"
    errors = validate_shooting_guide(data)
    assert any("recipe_card.tips 는 list 여야 함" in e for e in errors)


def test_tips_as_dict_is_reported_as_wrong_type():
    data = copy.deepcopy(VALID_SHOOTING)
    data["recipe_card"]["tips"] = {"what": "x", "why": "y"}
    errors = validate_shooting_guide(data)
    assert any("recipe_card.tips 는 list 여야 함" in e for e in errors)


def test_body_markdown_as_dict_is_reported_as_wrong_type():
    """dict 값이 str() 로 변환되면 비어 있지 않은 문자열이 되어 blank 검사를
    조용히 통과할 수 있었다 (라운드 2 회귀) — 타입 오류로 이름이 남아야 한다."""
    data = copy.deepcopy(VALID_PUBLISH)
    data["b3_blog"]["body_markdown"] = {"oops": "not a string"}
    errors = validate_publish_pack(data)
    assert any("b3_blog.body_markdown 는 문자열이어야 함" in e for e in errors)


def test_carousel_wrong_type_is_reported():
    """carousel 은 검사 지점이 하나뿐이라 잘못된 타입도 길이 0 으로 걸러진다 —
    이 동작이 우연이 아니라 설계임을 회귀로 고정한다."""
    data = copy.deepcopy(VALID_PUBLISH)
    data["b2_instagram"]["carousel"] = "not a list"
    errors = validate_publish_pack(data)
    assert any("carousel" in e for e in errors)


def test_seo_title_candidates_wrong_type_is_reported():
    data = copy.deepcopy(VALID_PUBLISH)
    data["b3_blog"]["seo_title_candidates"] = "not a list"
    errors = validate_publish_pack(data)
    assert any("seo_title_candidates" in e for e in errors)


# --- round 3: 라운드 2가 "이미 안전하다"고 잘못 주장한 세 지점 -----------------------
#
# 공통점: truthy 진위값 검사(`if not card.get(key)`)는 문자열처럼 "존재하지만 잘못된
# 타입"인 값을 통과시켜 버린다. round 2는 tips/body_markdown 두 곳만 고쳤고 나머지는
# "이미 안전하다"고 주장했지만, 그 근거는 타입 강제 호출부(_as_dict/_as_list)만 훑은
# 것이었다 — 실제 소비자인 formatter.py 가 무엇을 반복(for)하고 무엇에 .get() 을
# 호출하는지는 보지 않았다. 아래는 그 축으로 다시 짚은 세 가지 실제 재현 사례다.


def test_ingredients_as_string_is_reported_as_wrong_type():
    data = copy.deepcopy(VALID_SHOOTING)
    data["recipe_card"]["ingredients"] = "삼겹살 600g"
    errors = validate_shooting_guide(data)
    assert any("recipe_card.ingredients 는 list 여야 함" in e for e in errors)


def test_ingredients_group_non_dict_entry_is_reported():
    data = copy.deepcopy(VALID_SHOOTING)
    data["recipe_card"]["ingredients"] = ["주재료: 삼겹살 600g"]
    errors = validate_shooting_guide(data)
    assert any("recipe_card.ingredients[0] 는 dict 여야 함" in e for e in errors)


def test_ingredients_items_non_dict_entry_is_reported():
    data = copy.deepcopy(VALID_SHOOTING)
    data["recipe_card"]["ingredients"][0]["items"] = ["삼겹살 600g"]
    errors = validate_shooting_guide(data)
    assert any("items[0] 는 dict 여야 함" in e for e in errors)


def test_steps_as_string_is_reported_as_wrong_type():
    data = copy.deepcopy(VALID_SHOOTING)
    data["recipe_card"]["steps"] = "밑간부터 볶기까지"
    errors = validate_shooting_guide(data)
    assert any("recipe_card.steps 는 list 여야 함" in e for e in errors)


def test_steps_non_dict_entry_is_reported():
    data = copy.deepcopy(VALID_SHOOTING)
    data["recipe_card"]["steps"] = ["밑간부터 볶기까지"]
    errors = validate_shooting_guide(data)
    assert any("recipe_card.steps[0] 는 dict 여야 함" in e for e in errors)


def test_a3_camera_scenes_as_string_is_reported_as_wrong_type():
    data = copy.deepcopy(VALID_SHOOTING)
    data["a3_camera"]["scenes"] = "탑뷰로 고정"
    errors = validate_shooting_guide(data)
    assert any("a3_camera.scenes 는 list 여야 함" in e for e in errors)


def test_a3_camera_scenes_non_dict_entry_is_reported():
    data = copy.deepcopy(VALID_SHOOTING)
    data["a3_camera"]["scenes"] = ["탑뷰로 고정"]
    errors = validate_shooting_guide(data)
    assert any("a3_camera.scenes[0] 는 dict 여야 함" in e for e in errors)


def test_a2_script_wrong_type_message_names_the_real_problem():
    """a2_script = '문자열' 은 비어 있는 게 아니라 타입이 틀린 것이다 — '비어 있음'이라는
    잘못된 메시지 대신 실제 문제를 이름으로 남겨야 한다."""
    data = copy.deepcopy(VALID_SHOOTING)
    data["a2_script"] = "무언가의 대본"
    errors = validate_shooting_guide(data)
    assert any("a2_script 는 list 여야 함" in e for e in errors)
    assert not any(e == "a2_script 비어 있음" for e in errors)


def test_a2_script_non_dict_entry_is_reported():
    data = copy.deepcopy(VALID_SHOOTING)
    data["a2_script"] = ["그냥 문자열"]
    errors = validate_shooting_guide(data)
    assert any("a2_script[0] 는 dict 여야 함" in e for e in errors)


def test_a5_checklist_wrong_type_is_reported():
    data = copy.deepcopy(VALID_SHOOTING)
    data["a5_checklist"] = "체크리스트 텍스트"
    errors = validate_shooting_guide(data)
    assert any("a5_checklist 는 dict 여야 함" in e for e in errors)


def test_photo_slots_wrong_type_is_reported():
    data = copy.deepcopy(VALID_PUBLISH)
    data["b3_blog"]["photo_slots"] = "재료 사진 하나"
    errors = validate_publish_pack(data)
    assert any("b3_blog.photo_slots 는 list 여야 함" in e for e in errors)


def test_photo_slots_non_dict_entry_is_reported():
    data = copy.deepcopy(VALID_PUBLISH)
    data["b3_blog"]["photo_slots"] = ["재료 사진 하나"]
    errors = validate_publish_pack(data)
    assert any("b3_blog.photo_slots[0] 는 dict 여야 함" in e for e in errors)


def test_hashtags_non_string_entry_is_reported():
    data = copy.deepcopy(VALID_PUBLISH)
    data["b2_instagram"]["hashtags"] = [123]
    errors = validate_publish_pack(data)
    assert any("b2_instagram.hashtags[0] 는 문자열이어야 함" in e for e in errors)


def test_tags_non_string_entry_is_reported():
    data = copy.deepcopy(VALID_PUBLISH)
    data["b3_blog"]["tags"] = [123]
    errors = validate_publish_pack(data)
    assert any("b3_blog.tags[0] 는 문자열이어야 함" in e for e in errors)


# --- 핵심 불변식: validate 가 [] 면 render 는 절대 예외를 던지지 않는다 -----------------
#
# 이전 두 라운드는 이 계약 자체를 테스트한 적이 없다. "타입 오류를 이름으로 남긴다"는
# 개별 사례 테스트만으로는, formatter.py 가 실제로 무엇을 소비하는지 놓친 필드가 있어도
# 알아챌 방법이 없다. 아래 테스트는 스키마가 아니라 소비자(formatter)를 기준으로 삼아,
# "검증 통과 = 렌더링 성공"이라는 계약을 직접 확인한다.


def _set_nested(data, path, value):
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    return data


def _seeded_shooting():
    """구조(a1_scenario.structure)/장면(a3_camera.scenes)은 VALID_SHOOTING에서 빈 리스트다.
    원소 단위 타입 오류를 시험하려면 최소 하나씩은 채워둔 사본이 필요하다."""
    data = copy.deepcopy(VALID_SHOOTING)
    data["a1_scenario"]["structure"] = [
        {"from_sec": 0, "to_sec": 5, "section": "훅", "purpose": "시선을 끈다"}
    ]
    data["a3_camera"]["scenes"] = [
        {"scene": "1", "angle": "탑뷰", "tripod": "O", "lighting": "자연광", "movement": "고정"}
    ]
    return data


_WRONG_TYPE_VALUES = ["문자열", 123, 3.14, True, {"unexpected": "dict"}]
_ENTRY_WRONG_TYPE_VALUES = ["문자열 원소", 123, None, ["중첩", "리스트"]]

_SHOOTING_FIELD_PATHS = [
    ("recipe_card",),
    ("recipe_card", "ingredients"),
    ("recipe_card", "steps"),
    ("recipe_card", "tips"),
    ("recipe_card", "fail_points"),
    ("a1_scenario",),
    ("a1_scenario", "structure"),
    ("a2_script",),
    ("a3_camera",),
    ("a3_camera", "scenes"),
    ("a3_camera", "common_mistakes"),
    ("a4_differentiator",),
    ("a4_differentiator", "channel_edge"),
    ("a4_differentiator", "series_ideas"),
    ("a5_checklist",),
    ("a5_checklist", "before_cooking"),
    ("a5_checklist", "equipment"),
    ("a5_checklist", "during_shoot"),
    ("a5_checklist", "must_not_miss"),
    ("a5_checklist", "after_shoot"),
]

_SHOOTING_ENTRY_PATHS = [
    ("recipe_card", "ingredients", 0),
    ("recipe_card", "ingredients", 0, "items", 0),
    ("recipe_card", "steps", 0),
    ("recipe_card", "tips", 0),
    ("a1_scenario", "structure", 0),
    ("a2_script", 0),
    ("a3_camera", "scenes", 0),
]

_PUBLISH_FIELD_PATHS = [
    ("b2_instagram",),
    ("b2_instagram", "carousel"),
    ("b2_instagram", "hashtags"),
    ("b2_instagram", "story_lines"),
    ("b2_instagram", "thumbnail_ideas"),
    ("b3_blog",),
    ("b3_blog", "seo_title_candidates"),
    ("b3_blog", "photo_slots"),
    ("b3_blog", "tags"),
]

_PUBLISH_ENTRY_PATHS = [
    ("b2_instagram", "carousel", 0),
    ("b2_instagram", "hashtags", 0),
    ("b3_blog", "photo_slots", 0),
    ("b3_blog", "tags", 0),
]


def test_shooting_guide_validate_pass_implies_render_succeeds():
    """어떤 입력이든, validate_shooting_guide 가 [] 를 돌려주면 render_shooting_guide 는
    예외를 던지지 않아야 한다. 필드 단위/원소 단위로 다양한 잘못된 타입을 주입해 이
    계약을 직접 확인한다 — 이 테스트 하나가 3라운드에 걸친 버그를 전부 잡아냈어야 한다."""
    failures = []

    for path in _SHOOTING_FIELD_PATHS:
        for value in _WRONG_TYPE_VALUES:
            data = _set_nested(copy.deepcopy(VALID_SHOOTING), path, value)
            if validate_shooting_guide(data) == []:
                try:
                    formatter.render_shooting_guide(data)
                except Exception as exc:  # noqa: BLE001 - 실패 지점 자체를 보고하기 위함
                    failures.append(f"field path={path} value={value!r} -> {type(exc).__name__}: {exc}")

    for path in _SHOOTING_ENTRY_PATHS:
        for value in _ENTRY_WRONG_TYPE_VALUES:
            data = _set_nested(_seeded_shooting(), path, value)
            if validate_shooting_guide(data) == []:
                try:
                    formatter.render_shooting_guide(data)
                except Exception as exc:
                    failures.append(f"entry path={path} value={value!r} -> {type(exc).__name__}: {exc}")

    assert failures == [], "\n".join(failures)


def test_publish_pack_validate_pass_implies_render_succeeds():
    """validate_publish_pack 이 [] 를 돌려주면 render_instagram/render_blog 는 예외를
    던지지 않아야 한다. 같은 계약을 인스타/블로그 쪽에서도 확인한다."""
    failures = []

    for path in _PUBLISH_FIELD_PATHS:
        for value in _WRONG_TYPE_VALUES:
            data = _set_nested(copy.deepcopy(VALID_PUBLISH), path, value)
            if validate_publish_pack(data) == []:
                try:
                    formatter.render_instagram(data)
                    formatter.render_blog(data)
                except Exception as exc:
                    failures.append(f"field path={path} value={value!r} -> {type(exc).__name__}: {exc}")

    for path in _PUBLISH_ENTRY_PATHS:
        for value in _ENTRY_WRONG_TYPE_VALUES:
            data = _set_nested(copy.deepcopy(VALID_PUBLISH), path, value)
            if validate_publish_pack(data) == []:
                try:
                    formatter.render_instagram(data)
                    formatter.render_blog(data)
                except Exception as exc:
                    failures.append(f"entry path={path} value={value!r} -> {type(exc).__name__}: {exc}")

    assert failures == [], "\n".join(failures)
