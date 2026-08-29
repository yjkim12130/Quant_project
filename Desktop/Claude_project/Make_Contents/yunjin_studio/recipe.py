"""Recipe/ 폴더의 레시피 원문을 읽는다."""

from dataclasses import dataclass
from pathlib import Path

RECIPE_DIR = Path(__file__).resolve().parent.parent / "Recipe"
EPISODE_HEADER = "[에피소드]"


class RecipeNotFoundError(FileNotFoundError):
    """요청한 레시피 파일이 없을 때."""


@dataclass(frozen=True)
class Recipe:
    dish_name: str
    body: str
    episode: str


def list_recipes(recipe_dir: Path = RECIPE_DIR) -> list[str]:
    return sorted(p.stem for p in recipe_dir.glob("*.txt"))


def load_recipe(name: str, recipe_dir: Path = RECIPE_DIR, episode: str = "") -> Recipe:
    path = recipe_dir / f"{name}.txt"
    if not path.exists():
        available = ", ".join(list_recipes(recipe_dir)) or "(없음)"
        raise RecipeNotFoundError(
            f"레시피 '{name}'을(를) 찾을 수 없습니다. 사용 가능: {available}"
        )
    body, file_episode = _split_episode(path.read_text(encoding="utf-8"))
    return Recipe(
        dish_name=name,
        body=body.strip(),
        episode=(episode or file_episode).strip(),
    )


def _split_episode(text: str) -> tuple[str, str]:
    if EPISODE_HEADER not in text:
        return text, ""
    head, _, tail = text.partition(EPISODE_HEADER)
    return head, tail
