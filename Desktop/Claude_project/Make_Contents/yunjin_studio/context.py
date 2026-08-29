"""채널 프로필 로드와 프롬프트 조립."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROFILE_PATH = ROOT / "channel_profile.json"
PROMPT_DIR = ROOT / "prompts"

DEFAULT_PROFILE = {
    "channel": {
        "name": "TBD",
        "tagline": "TBD",
        "categories": ["요리", "육아"],
        "platforms": ["instagram", "naver_blog", "youtube"],
    },
    "voice": {
        "speech_style": "해요체",
        "persona": "요리 좀 하는 동네 언니",
        "energy": "차분하지만 확신 있는",
        "banned": ["과장된 리액션", "전문 셰프 어투", "광고성 미사여구", "'꿀팁 대방출' 류 낚시 표현"],
    },
    "signature_rules": [
        "계량은 '1T = 아빠 숟가락' 기준을 유지하고, 이 표현을 다른 말로 바꾸지 않는다",
        "모든 팁은 '무엇을'이 아니라 '왜'를 설명한다 — 원리 설명이 이 채널의 핵심 차별점이다",
        "실패 포인트를 숨기지 않고 조리 단계보다 먼저 알려준다",
        "재료 그룹(주재료/밑간/양념장)의 분리를 유지한다",
    ],
    "audience": {"primary": "TBD", "pain_point": "TBD"},
    "defaults": {"target_duration_sec": 60},
    "model": {"id": "claude-opus-5", "effort": "high"},
}


def load_profile(path: Path = PROFILE_PATH) -> tuple[dict, list[str]]:
    """채널 프로필을 읽는다. 실패하면 기본 프로필과 경고를 돌려준다."""
    if not path.exists():
        return DEFAULT_PROFILE, [f"{path.name}이(가) 없어 기본 프로필로 진행합니다."]
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except json.JSONDecodeError as exc:
        return DEFAULT_PROFILE, [f"{path.name} 파싱 실패({exc}) — 기본 프로필로 진행합니다."]
