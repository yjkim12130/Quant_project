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
