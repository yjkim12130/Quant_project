import json
from pathlib import Path

from yunjin_studio.context import (
    DEFAULT_PROFILE,
    PROFILE_PATH,
    build_publish_prompt,
    build_shooting_prompt,
    load_profile,
)
from yunjin_studio.recipe import Recipe


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
