import copy

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
