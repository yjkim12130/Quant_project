import json
from types import SimpleNamespace

import pytest

from tests.test_schema import VALID_PUBLISH, VALID_SHOOTING
from yunjin_studio.generator import (
    ClaudeCliError,
    build_cli_argv,
    build_request_kwargs,
    extract_json,
    generate_publish,
    generate_shooting,
    resolve_engine,
)
from yunjin_studio.recipe import Recipe


def test_extract_json_handles_bare_object():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_strips_code_fence():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_ignores_surrounding_prose():
    assert extract_json('네, 만들었습니다.\n{"a": 1}\n필요하면 말씀해주세요.') == {"a": 1}


def test_extract_json_raises_on_garbage():
    with pytest.raises(ValueError):
        extract_json("JSON이 없습니다")


def test_build_request_kwargs_uses_profile_model():
    kwargs = build_request_kwargs({"model": {"id": "claude-sonnet-5", "effort": "medium"}})
    assert kwargs["model"] == "claude-sonnet-5"
    assert kwargs["output_config"] == {"effort": "medium"}
    assert kwargs["thinking"] == {"type": "adaptive"}


def test_build_request_kwargs_omits_disabled_options():
    kwargs = build_request_kwargs({"model": {"id": "claude-opus-5", "effort": None, "thinking": False}})
    assert "output_config" not in kwargs
    assert "thinking" not in kwargs


class FakeStream:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        text = json.dumps(self._payload, ensure_ascii=False)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


class FakeClient:
    """payloads의 원소가 Exception이면 그 호출에서 예외를 던진다."""

    def __init__(self, payloads):
        self._payloads = list(payloads)
        self.calls = []

        outer = self

        class Messages:
            def stream(self, **kwargs):
                outer.calls.append(kwargs)
                payload = outer._payloads.pop(0)
                if isinstance(payload, Exception):
                    raise payload
                return FakeStream(payload)

        self.messages = Messages()


PROFILE = {
    "model": {"id": "claude-opus-5", "effort": "high", "engine": "api"},
    "signature_rules": [],
}
RECIPE = Recipe(dish_name="제육볶음", body="삼겹살 600g", episode="")


def test_generate_shooting_returns_parsed_json():
    client = FakeClient([VALID_SHOOTING])
    assert generate_shooting(PROFILE, RECIPE, client=client) == VALID_SHOOTING
    assert len(client.calls) == 1


def test_generate_shooting_passes_duration_into_prompt():
    client = FakeClient([VALID_SHOOTING])
    generate_shooting(PROFILE, RECIPE, duration_sec=90, client=client)
    assert "90초" in client.calls[0]["messages"][0]["content"]


def test_generate_publish_receives_recipe_card():
    client = FakeClient([VALID_PUBLISH])
    card = VALID_SHOOTING["recipe_card"]
    assert generate_publish(PROFILE, card, client=client) == VALID_PUBLISH

    prompt = client.calls[0]["messages"][0]["content"]
    assert "1T = 아빠 숟가락" in prompt
    assert "제육볶음" in prompt


def test_publish_failure_does_not_touch_shooting_result():
    """스펙 §12 — 호출② 실패가 호출① 결과를 망가뜨리면 안 된다."""
    client = FakeClient([VALID_SHOOTING, RuntimeError("API 장애")])
    shooting = generate_shooting(PROFILE, RECIPE, client=client)

    with pytest.raises(RuntimeError):
        generate_publish(PROFILE, shooting["recipe_card"], client=client)

    assert shooting == VALID_SHOOTING


# --- 경로 2 기본 엔진: Claude Code CLI (구독 사용, API 과금 없음) -------------

CC_PROFILE = {"model": {"id": "claude-opus-5", "effort": "high"}, "signature_rules": []}


class FakeRunner:
    """claude CLI 대신 미리 준비한 텍스트를 돌려준다.

    payloads의 원소가 Exception이면 그 호출에서 예외를 던진다.
    """

    def __init__(self, payloads):
        self._payloads = list(payloads)
        self.calls = []

    def __call__(self, argv, prompt):
        self.calls.append((argv, prompt))
        payload = self._payloads.pop(0)
        if isinstance(payload, Exception):
            raise payload
        if isinstance(payload, str):
            return payload
        return json.dumps(payload, ensure_ascii=False)


def test_engine_defaults_to_claude_code():
    """프로필에 engine이 없으면 과금되는 API가 아니라 구독 경로를 쓴다."""
    assert resolve_engine({}) == "claude_code"
    assert resolve_engine({"model": {}}) == "claude_code"
    assert resolve_engine({"model": {"engine": "api"}}) == "api"


def test_build_cli_argv_pins_model_and_print_mode():
    argv = build_cli_argv("/usr/bin/claude", "claude-sonnet-5")
    assert argv[0] == "/usr/bin/claude"
    assert "-p" in argv
    assert argv[argv.index("--model") + 1] == "claude-sonnet-5"


def test_generate_shooting_via_cli():
    runner = FakeRunner([VALID_SHOOTING])
    assert generate_shooting(CC_PROFILE, RECIPE, runner=runner) == VALID_SHOOTING
    assert len(runner.calls) == 1

    argv, prompt = runner.calls[0]
    assert "--model" in argv
    assert "제육볶음" in prompt


def test_generate_shooting_via_cli_passes_duration():
    runner = FakeRunner([VALID_SHOOTING])
    generate_shooting(CC_PROFILE, RECIPE, duration_sec=30, runner=runner)
    assert "30초" in runner.calls[0][1]


def test_cli_output_may_be_wrapped_in_code_fence():
    """실측 — claude -p 는 JSON을 ```json 펜스로 감싸 내보내는 경우가 있다."""
    fenced = "```json\n" + json.dumps(VALID_SHOOTING, ensure_ascii=False) + "\n```"
    runner = FakeRunner([fenced])
    assert generate_shooting(CC_PROFILE, RECIPE, runner=runner) == VALID_SHOOTING


def test_generate_publish_via_cli_receives_recipe_card():
    runner = FakeRunner([VALID_PUBLISH])
    card = VALID_SHOOTING["recipe_card"]
    assert generate_publish(CC_PROFILE, card, runner=runner) == VALID_PUBLISH

    prompt = runner.calls[0][1]
    assert "1T = 아빠 숟가락" in prompt


def test_cli_publish_failure_does_not_touch_shooting_result():
    """스펙 §12 — 엔진이 바뀌어도 호출② 실패는 호출① 결과를 건드리지 않는다."""
    runner = FakeRunner([VALID_SHOOTING, ClaudeCliError("CLI 실패")])
    shooting = generate_shooting(CC_PROFILE, RECIPE, runner=runner)

    with pytest.raises(ClaudeCliError):
        generate_publish(CC_PROFILE, shooting["recipe_card"], runner=runner)

    assert shooting == VALID_SHOOTING


def test_cli_path_never_needs_an_api_key(monkeypatch):
    """구독 경로는 ANTHROPIC_API_KEY가 없어도 동작해야 한다 — 이게 이 엔진의 존재 이유다."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    runner = FakeRunner([VALID_SHOOTING])
    assert generate_shooting(CC_PROFILE, RECIPE, runner=runner) == VALID_SHOOTING
