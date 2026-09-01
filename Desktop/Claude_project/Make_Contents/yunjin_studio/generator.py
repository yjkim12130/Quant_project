"""촬영 가이드와 발행 콘텐츠를 두 번의 LLM 호출로 만든다.

엔진은 `channel_profile.json`의 `model.engine`으로 고른다.

- `claude_code` (기본) — 설치된 Claude Code CLI를 `-p` 모드로 부른다.
  구독 안에서 처리되므로 API 종량 과금이 붙지 않고 `ANTHROPIC_API_KEY`도 필요 없다.
- `api` — Anthropic SDK로 직접 부른다. 키가 필요하고 호출량만큼 과금된다.

두 엔진은 같은 프롬프트(`prompts/*.md`)를 쓰고 같은 형식의 dict를 돌려준다.
바꿔 끼워도 `app.py`·`schema.py`·`formatter.py`는 영향을 받지 않는다.
"""

import json
import os
import shutil
import subprocess
import tempfile

from .context import build_publish_prompt, build_shooting_prompt
from .recipe import Recipe

SYSTEM_PROMPT = (
    "당신은 한국어 요리·육아 콘텐츠 제작 어시스턴트입니다. "
    "요청받은 JSON 객체 하나만 출력하고, 그 앞뒤에 어떤 설명도 붙이지 마세요."
)
MAX_TOKENS = 16000
DEFAULT_MODEL = "claude-opus-5"
DEFAULT_ENGINE = "claude_code"

# 실측: 프롬프트 3.8KB → 20KB JSON 응답에 3분 6초. 여유를 크게 둔다.
CLI_TIMEOUT_SEC = 900


class ClaudeCliError(RuntimeError):
    """claude CLI 호출이 실패했을 때."""


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


def _model_id(profile: dict) -> str:
    return (profile.get("model") or {}).get("id") or DEFAULT_MODEL


def resolve_engine(profile: dict) -> str:
    """어떤 엔진을 쓸지 정한다. 프로필에 없으면 과금되지 않는 쪽을 기본으로."""
    return (profile.get("model") or {}).get("engine") or DEFAULT_ENGINE


# --- 엔진 1: Claude Code CLI (구독) -----------------------------------------


def find_claude_binary() -> str:
    """claude 실행 파일 경로. 환경변수로 덮어쓸 수 있다."""
    override = os.environ.get("YUNJIN_CLAUDE_BIN")
    if override:
        return override

    found = shutil.which("claude")
    if found:
        return found

    # Streamlit을 PATH가 좁은 환경에서 띄웠을 때를 위한 표준 설치 위치들
    home = os.path.expanduser("~")
    for candidate in (
        os.path.join(home, ".local", "bin", "claude.exe"),
        os.path.join(home, ".local", "bin", "claude.cmd"),
        os.path.join(home, ".local", "bin", "claude"),
    ):
        if os.path.exists(candidate):
            return candidate

    raise ClaudeCliError(
        "claude 실행 파일을 찾지 못했습니다. Claude Code를 설치했는지 확인하거나, "
        "환경변수 YUNJIN_CLAUDE_BIN에 전체 경로를 지정하세요."
    )


def build_cli_argv(binary: str, model: str) -> list[str]:
    return [
        binary,
        "-p",
        "--model",
        model,
        "--append-system-prompt",
        SYSTEM_PROMPT,
    ]


def run_claude_cli(argv: list[str], prompt: str) -> str:
    """프롬프트를 stdin으로 넘긴다 — 윈도우 argv 길이 제한을 피하기 위함."""
    # 중립 디렉터리에서 실행한다. 프로젝트 폴더에서 돌리면 이 저장소의 CLAUDE.md와
    # recipe-studio 스킬까지 함께 로드되어, 프롬프트가 지시한 것과 다른 일을 할 수 있다.
    result = subprocess.run(
        argv,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=CLI_TIMEOUT_SEC,
        cwd=tempfile.gettempdir(),
    )
    if result.returncode != 0:
        raise ClaudeCliError(
            f"claude CLI가 실패했습니다 (exit {result.returncode}): "
            f"{(result.stderr or '').strip()[:500]}"
        )
    return result.stdout


def _call_cli(profile: dict, prompt: str, runner=None) -> dict:
    runner = runner or run_claude_cli
    argv = build_cli_argv(find_claude_binary(), _model_id(profile))
    return extract_json(runner(argv, prompt))


# --- 엔진 2: Anthropic API (종량 과금) --------------------------------------


def build_request_kwargs(profile: dict) -> dict:
    model_config = profile.get("model") or {}
    kwargs: dict = {
        "model": _model_id(profile),
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


def _call_api(client, kwargs: dict, prompt: str) -> dict:
    with client.messages.stream(**kwargs, messages=[{"role": "user", "content": prompt}]) as stream:
        message = stream.get_final_message()
    text = "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
    return extract_json(text)


# --- 공통 진입점 ------------------------------------------------------------


def _dispatch(profile: dict, prompt: str, client, runner) -> dict:
    if resolve_engine(profile) == "api":
        return _call_api(client or _make_client(), build_request_kwargs(profile), prompt)
    return _call_cli(profile, prompt, runner)


def generate_shooting(
    profile: dict,
    recipe: Recipe,
    duration_sec: int = 60,
    client=None,
    runner=None,
) -> dict:
    """호출① — 레시피 카드와 촬영 가이드 A1~A5."""
    return _dispatch(profile, build_shooting_prompt(profile, recipe, duration_sec), client, runner)


def generate_publish(profile: dict, recipe_card: dict, client=None, runner=None) -> dict:
    """호출② — 인스타 패키지와 블로그 글.

    호출자는 호출①의 결과를 디스크에 저장한 뒤 이 함수를 부른다.
    그래야 여기서 실패해도 호출① 결과가 남는다(스펙 §12).
    """
    return _dispatch(profile, build_publish_prompt(profile, recipe_card), client, runner)
