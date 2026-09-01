"""Anthropic API로 두 번 호출해 촬영 가이드와 발행 콘텐츠를 만든다."""

import json
import os

from .context import build_publish_prompt, build_shooting_prompt
from .recipe import Recipe

SYSTEM_PROMPT = (
    "당신은 한국어 요리·육아 콘텐츠 제작 어시스턴트입니다. "
    "요청받은 JSON 객체 하나만 출력하고, 그 앞뒤에 어떤 설명도 붙이지 마세요."
)
MAX_TOKENS = 16000


def extract_json(text: str) -> dict:
    """응답 텍스트에서 JSON 객체 하나를 뽑는다."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.lstrip().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"응답에서 JSON 객체를 찾지 못했습니다: {text[:200]}")
    return json.loads(cleaned[start : end + 1])


def build_request_kwargs(profile: dict) -> dict:
    model_config = profile.get("model") or {}
    kwargs: dict = {
        "model": model_config.get("id", "claude-opus-5"),
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
    }
    effort = model_config.get("effort")
    if effort:
        kwargs["output_config"] = {"effort": effort}
    if model_config.get("thinking", True):
        kwargs["thinking"] = {"type": "adaptive"}
    return kwargs


def _make_client():
    from anthropic import Anthropic

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY가 설정되지 않았습니다. Make_Contents/.env에 추가하세요."
        )
    return Anthropic()


def _call(client, kwargs: dict, prompt: str) -> dict:
    with client.messages.stream(**kwargs, messages=[{"role": "user", "content": prompt}]) as stream:
        message = stream.get_final_message()
    text = "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
    return extract_json(text)


def generate_shooting(
    profile: dict,
    recipe: Recipe,
    duration_sec: int = 60,
    client=None,
) -> dict:
    """호출① — 레시피 카드와 촬영 가이드 A1~A5."""
    client = client or _make_client()
    prompt = build_shooting_prompt(profile, recipe, duration_sec)
    return _call(client, build_request_kwargs(profile), prompt)


def generate_publish(profile: dict, recipe_card: dict, client=None) -> dict:
    """호출② — 인스타 패키지와 블로그 글.

    호출자는 호출①의 결과를 디스크에 저장한 뒤 이 함수를 부른다.
    그래야 여기서 실패해도 호출① 결과가 남는다(스펙 §12).
    """
    client = client or _make_client()
    prompt = build_publish_prompt(profile, recipe_card)
    return _call(client, build_request_kwargs(profile), prompt)
