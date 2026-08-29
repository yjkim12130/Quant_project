"""검증된 결과 JSON을 마크다운 파일로 쓴다.

사용법:
    python -m yunjin_studio.render <output_dir>
"""

import json
import sys
from pathlib import Path

from .formatter import render_blog, render_instagram, render_shooting_guide

USAGE = "사용법: python -m yunjin_studio.render <output_dir>"


def write_outputs(out_dir: Path, shooting: dict, publish: dict | None = None) -> dict[str, str]:
    """`shooting`(과 주어졌다면 `publish`)을 out_dir에 렌더링한다.

    작성한 모든 파일에 대해 출력 순서대로 {파일명: 내용}을 반환한다.
    """
    written: dict[str, str] = {}

    recipe_card_json = json.dumps(shooting.get("recipe_card") or {}, ensure_ascii=False, indent=2)
    (out_dir / "00_recipe_card.json").write_text(recipe_card_json, encoding="utf-8")
    written["00_recipe_card.json"] = recipe_card_json

    shooting_md = render_shooting_guide(shooting)
    (out_dir / "01_촬영가이드.md").write_text(shooting_md, encoding="utf-8")
    written["01_촬영가이드.md"] = shooting_md

    if publish is not None:
        instagram_md = render_instagram(publish)
        (out_dir / "02_인스타.md").write_text(instagram_md, encoding="utf-8")
        written["02_인스타.md"] = instagram_md

        blog_md = render_blog(publish)
        (out_dir / "03_블로그.md").write_text(blog_md, encoding="utf-8")
        written["03_블로그.md"] = blog_md

    return written


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(USAGE)
        return 2

    out_dir = Path(args[0])
    shooting_path = out_dir / "_raw_shooting.json"
    publish_path = out_dir / "_raw_publish.json"

    if not shooting_path.exists():
        print(f"{shooting_path} 없음")
        return 1

    try:
        shooting = json.loads(shooting_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"{shooting_path.name} 파싱 실패: {exc}")
        return 1

    publish = None
    if publish_path.exists():
        try:
            publish = json.loads(publish_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"{publish_path.name} 파싱 실패: {exc}")
            return 1
    else:
        print(f"경고: {publish_path.name} 없음 — 인스타/블로그는 건너뜁니다.")

    written = write_outputs(out_dir, shooting, publish)

    print(f"{out_dir}에 {len(written)}개 파일 생성: {', '.join(written.keys())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
