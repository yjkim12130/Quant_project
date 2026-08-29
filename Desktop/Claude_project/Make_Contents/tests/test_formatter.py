import copy

from tests.test_schema import VALID_PUBLISH, VALID_SHOOTING
from yunjin_studio.formatter import render_blog, render_instagram, render_shooting_guide
from yunjin_studio.render import write_outputs


def test_shooting_guide_keeps_ingredient_groups():
    md = render_shooting_guide(copy.deepcopy(VALID_SHOOTING))
    assert "주재료" in md
    assert "삼겹살" in md
    assert "600g" in md


def test_shooting_guide_shows_tip_why():
    md = render_shooting_guide(copy.deepcopy(VALID_SHOOTING))
    assert "연육 작용을 돕는다" in md


def test_shooting_guide_has_all_five_sections():
    md = render_shooting_guide(copy.deepcopy(VALID_SHOOTING))
    for heading in ("A1", "A2", "A3", "A4", "A5"):
        assert heading in md


def test_shooting_guide_tolerates_missing_optional_fields():
    data = copy.deepcopy(VALID_SHOOTING)
    del data["a4_differentiator"]["series_ideas"]
    del data["recipe_card"]["fail_points"]
    md = render_shooting_guide(data)
    assert isinstance(md, str)
    assert "제육볶음" in md


def test_instagram_lists_all_carousel_slides():
    md = render_instagram(copy.deepcopy(VALID_PUBLISH))
    assert md.count("슬라이드") == 5
    assert "#집밥" in md


def test_blog_uses_seo_title_and_body():
    md = render_blog(copy.deepcopy(VALID_PUBLISH))
    assert "1T = 아빠 숟가락" in md
    assert "본문입니다" in md


def test_blog_lists_photo_slots():
    md = render_blog(copy.deepcopy(VALID_PUBLISH))
    assert "재료" in md


def test_write_outputs_writes_all_four_files_and_returns_mapping(tmp_path):
    shooting = copy.deepcopy(VALID_SHOOTING)
    publish = copy.deepcopy(VALID_PUBLISH)

    written = write_outputs(tmp_path, shooting, publish)

    expected_names = [
        "00_recipe_card.json",
        "01_촬영가이드.md",
        "02_인스타.md",
        "03_블로그.md",
    ]
    assert list(written.keys()) == expected_names
    for name in expected_names:
        assert (tmp_path / name).exists()

    on_disk = (tmp_path / "01_촬영가이드.md").read_text(encoding="utf-8")
    assert on_disk == written["01_촬영가이드.md"]


def test_write_outputs_without_publish_writes_only_two_files(tmp_path):
    shooting = copy.deepcopy(VALID_SHOOTING)

    written = write_outputs(tmp_path, shooting, publish=None)

    assert list(written.keys()) == ["00_recipe_card.json", "01_촬영가이드.md"]
    assert not (tmp_path / "02_인스타.md").exists()
    assert not (tmp_path / "03_블로그.md").exists()
