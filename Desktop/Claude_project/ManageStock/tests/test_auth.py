import auth


def test_get_app_password_returns_none_when_unset(tmp_path):
    path = str(tmp_path / ".app_password")
    assert auth.get_app_password(env={}, secrets={}, path=path) is None


def test_get_app_password_reads_env_var():
    assert auth.get_app_password(env={"APP_PASSWORD": " secret1 "}, secrets={}) == "secret1"


def test_get_app_password_reads_secrets_first(tmp_path):
    path = str(tmp_path / ".app_password")
    value = auth.get_app_password(
        env={"APP_PASSWORD": "from_env"}, secrets={"APP_PASSWORD": "from_secrets"}, path=path
    )
    assert value == "from_secrets"


def test_get_app_password_falls_back_to_file(tmp_path):
    path = tmp_path / ".app_password"
    path.write_text("from_file\n", encoding="utf-8")
    assert auth.get_app_password(env={}, secrets={}, path=str(path)) == "from_file"
