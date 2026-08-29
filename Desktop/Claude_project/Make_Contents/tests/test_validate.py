from yunjin_studio.validate import main


def test_corrupted_shooting_json_is_reported_not_raised(tmp_path, capsys):
    (tmp_path / "_raw_shooting.json").write_text("{ this is not valid json", encoding="utf-8")

    exit_code = main([str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "_raw_shooting.json" in captured.out
    assert "파싱 실패" in captured.out


def test_corrupted_publish_json_is_reported_not_raised(tmp_path, capsys):
    (tmp_path / "_raw_publish.json").write_text("[[[not json", encoding="utf-8")

    exit_code = main([str(tmp_path)])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "_raw_publish.json" in captured.out
    assert "파싱 실패" in captured.out


def test_missing_output_files_are_reported_with_exit_code_one(tmp_path, capsys):
    exit_code = main([str(tmp_path / "없는폴더")])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "_raw_shooting.json 없음" in captured.out
    assert "_raw_publish.json 없음" in captured.out


def test_usage_error_returns_exit_code_two(capsys):
    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "사용법" in captured.out
