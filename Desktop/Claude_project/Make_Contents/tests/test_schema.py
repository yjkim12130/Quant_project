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
