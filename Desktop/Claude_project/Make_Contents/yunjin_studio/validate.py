"""생성 결과를 검증한다.

사용법:
    python -m yunjin_studio.validate <output_dir>
"""

import json
import sys
from pathlib import Path

from .schema import validate_publish_pack, validate_shooting_guide

USAGE = "사용법: python -m yunjin_studio.validate <output_dir>"


def main(argv: list[str] | None = None) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(USAGE)
        return 2

    out_dir = Path(args[0])
    errors: list[str] = []
    measure_note = ""

    shooting_path = out_dir / "_raw_shooting.json"
    if shooting_path.exists():
        try:
            shooting = json.loads(shooting_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{shooting_path.name} 파싱 실패: {exc}")
        else:
            errors += validate_shooting_guide(shooting)
            if isinstance(shooting, dict):
                card = shooting.get("recipe_card")
                if isinstance(card, dict):
                    measure_note = card.get("measure_note") or ""
    else:
        errors.append(f"{shooting_path.name} 없음")

    publish_path = out_dir / "_raw_publish.json"
    if publish_path.exists():
        try:
            publish = json.loads(publish_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{publish_path.name} 파싱 실패: {exc}")
        else:
            errors += validate_publish_pack(publish, measure_note)
    else:
        errors.append(f"{publish_path.name} 없음")

    if errors:
        print(f"검증 실패 ({len(errors)}건):")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("검증 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
