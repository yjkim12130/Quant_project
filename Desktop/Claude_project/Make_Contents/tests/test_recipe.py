import pytest

from yunjin_studio.recipe import Recipe, RecipeNotFoundError, list_recipes, load_recipe


def test_list_recipes_finds_both_drafts():
    names = list_recipes()
    assert "제육볶음" in names
    assert "항정상꽈리고추볶음" in names


def test_load_recipe_reads_korean_body():
    recipe = load_recipe("제육볶음")
    assert isinstance(recipe, Recipe)
    assert recipe.dish_name == "제육볶음"
    assert "고추장" in recipe.body
    assert "아빠 숟가락" in recipe.body
    assert recipe.episode == ""


def test_load_recipe_accepts_episode_argument():
    recipe = load_recipe("제육볶음", episode="아빠가 제일 좋아하는 메뉴")
    assert recipe.episode == "아빠가 제일 좋아하는 메뉴"


def test_load_recipe_splits_episode_section(tmp_path):
    path = tmp_path / "테스트요리.txt"
    path.write_text(
        "[재료 준비]\n- 계란 2개\n\n[에피소드]\n아이가 처음 먹은 날\n",
        encoding="utf-8",
    )
    recipe = load_recipe("테스트요리", recipe_dir=tmp_path)
    assert "계란 2개" in recipe.body
    assert "[에피소드]" not in recipe.body
    assert recipe.episode == "아이가 처음 먹은 날"


def test_episode_argument_wins_over_file_section(tmp_path):
    path = tmp_path / "테스트요리.txt"
    path.write_text("본문\n\n[에피소드]\n파일에 적힌 것\n", encoding="utf-8")
    recipe = load_recipe("테스트요리", recipe_dir=tmp_path, episode="인자로 준 것")
    assert recipe.episode == "인자로 준 것"


def test_missing_recipe_lists_available(tmp_path):
    (tmp_path / "있는요리.txt").write_text("본문", encoding="utf-8")
    with pytest.raises(RecipeNotFoundError) as exc:
        load_recipe("없는요리", recipe_dir=tmp_path)
    assert "있는요리" in str(exc.value)
