import copy
import json

from tests.test_schema import VALID_PUBLISH, VALID_SHOOTING
from yunjin_studio.render import main


def _write_shooting(tmp_path, data=None):
    (tmp_path / "_raw_shooting.json").write_text(
        json.dumps(data if data is not None else VALID_SHOOTING, ensure_ascii=False),
        encoding="utf-8",
    )


def _write_publish(tmp_path, data=None):
    (tmp_path / "_raw_publish.json").write_text(
        json.dumps(data if data is not None else VALID_PUBLISH, ensure_ascii=False),
        encoding="utf-8",
    )


def test_usage_error_returns_exit_code_two(capsys):
    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "사용법" in captured.out


def test_missing_shooting_json_returns_exit_code_one(tmp_path, capsys):
    exit_code = main([str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "_raw_shooting.json" in captured.out
    assert "없음" in captured.out
    assert not (tmp_path / "00_recipe_card.json").exists()


def test_corrupted_shooting_json_is_reported_not_raised(tmp_path, capsys):
    (tmp_path / "_raw_shooting.json").write_text("{ this is not valid json", encoding="utf-8")

    exit_code = main([str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "_raw_shooting.json" in captured.out
    assert "파싱 실패" in captured.out


def test_corrupted_publish_json_is_reported_not_raised(tmp_path, capsys):
    _write_shooting(tmp_path)
    (tmp_path / "_raw_publish.json").write_text("[[[not json", encoding="utf-8")

    exit_code = main([str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "_raw_publish.json" in captured.out
    assert "파싱 실패" in captured.out


def test_publish_missing_still_writes_shooting_files_and_exits_zero(tmp_path, capsys):
    """Regression test for Finding 1: the em dash in the warning string used to
    crash `print` under a cp949 stdout before any file was written. With
    `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` in place, the
    warning must print without raising and the two available files must land
    on disk with exit code 0."""
    _write_shooting(tmp_path)

    exit_code = main([str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "경고" in captured.out
    assert "_raw_publish.json" in captured.out
    assert (tmp_path / "00_recipe_card.json").exists()
    assert (tmp_path / "01_촬영가이드.md").exists()
    assert not (tmp_path / "02_인스타.md").exists()
    assert not (tmp_path / "03_블로그.md").exists()


def test_full_success_writes_four_files_and_exits_zero(tmp_path, capsys):
    _write_shooting(tmp_path)
    _write_publish(tmp_path)

    exit_code = main([str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    for name in (
        "00_recipe_card.json",
        "01_촬영가이드.md",
        "02_인스타.md",
        "03_블로그.md",
    ):
        assert (tmp_path / name).exists()
        assert name in captured.out
