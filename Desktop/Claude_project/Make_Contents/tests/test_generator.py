import json
from types import SimpleNamespace

import pytest

from tests.test_schema import VALID_PUBLISH, VALID_SHOOTING
from yunjin_studio.generator import (
    build_request_kwargs,
    extract_json,
    generate_publish,
    generate_shooting,
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


PROFILE = {"model": {"id": "claude-opus-5", "effort": "high"}, "signature_rules": []}
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
