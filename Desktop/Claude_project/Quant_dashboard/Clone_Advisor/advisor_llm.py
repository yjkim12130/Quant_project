"""
advisor_llm.py — 빈규리 정성 룰 LLM 자동 평가 (P1: RAG/지식 기반)
═══════════════════════════════════════════════════════════════════════
binkyuri_rulebook.json의 '정성 룰'(codeable != "yes", 12개)을 Claude가
종목의 사업·해자·재무 맥락을 읽고 met / not_met / unknown 으로 판정한다.

  · 모델       : claude-opus-4-8 (adaptive thinking)
  · 구조화 출력: output_config.format(json_schema) — 룰별 판정/근거/확신도
  · 프롬프트 캐싱: 안정적인 룰북+지시문을 system(앞단)에 cache_control,
                  가변적인 종목 맥락은 user(뒤)로 → 종목만 바뀌어도 prefix 재사용
  · 키         : 환경변수 ANTHROPIC_API_KEY 또는 .anthropic_api_key 파일

설치:  pip install anthropic
"""
from __future__ import annotations
import json
import os
from typing import Optional

try:
    import anthropic
except Exception:  # pragma: no cover
    anthropic = None

_HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = "claude-opus-4-8"

# 룰별 판정 결과 스키마 (structured outputs)
_SCHEMA = {
    "type": "object",
    "properties": {
        "evaluations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "rule_id": {"type": "string"},
                    "verdict": {"type": "string", "enum": ["met", "not_met", "unknown"]},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "reasoning": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["rule_id", "verdict", "confidence", "reasoning", "evidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["evaluations"],
    "additionalProperties": False,
}


def get_anthropic_key() -> Optional[str]:
    """환경변수 ANTHROPIC_API_KEY 또는 .anthropic_api_key 파일에서 키를 읽는다."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key.strip()
    path = os.path.join(_HERE, ".anthropic_api_key")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    return None


def llm_available() -> tuple[bool, str]:
    """(사용가능, 사유). 앱에서 버튼 활성화 판단용."""
    if anthropic is None:
        return False, "anthropic SDK 미설치 (pip install anthropic)"
    if not get_anthropic_key():
        return False, "ANTHROPIC_API_KEY 미설정 (.anthropic_api_key 파일 또는 환경변수)"
    return True, "ok"


def _build_system(rulebook: dict, rules: list[dict]) -> str:
    """안정적(캐시 대상) system 프롬프트: 페르소나 + 룰 정의 + 지시문."""
    lines = [
        "당신은 한국 주식 스몰캡 펀더멘탈 분석가 '빈규리 CPA'의 판단 프레임을 이식받은 평가 엔진입니다.",
        "철학: " + " ".join(rulebook.get("philosophy", [])),
        "",
        "아래 11개 '정성 판단 룰'을 주어진 종목에 대해 각각 평가하세요.",
        "각 룰의 IF 조건이 종목에 대해 충족되는지를 met / not_met / unknown 으로 판정합니다.",
        "",
        "[룰 목록]",
    ]
    for r in rules:
        ev = r.get("evidence", [{}])
        ex = ev[0] if ev else {}
        lines.append(
            f"- {r['id']} ({r['category']}/{r.get('weight','mid')}) {r['name']}\n"
            f"    IF: {r['if']}\n"
            f"    THEN: {r['then']}\n"
            f"    참고예시: [{ex.get('stock','')}] {ex.get('quote','')}"
        )
    lines += [
        "",
        "[판정 지침]",
        "1. 종목의 사업·고객사·해자·재무에 대한 당신의 지식과, user가 제공하는 정량 데이터를 함께 사용합니다.",
        "2. 근거가 충분하면 met/not_met, 정보가 부족하면 반드시 unknown(추측 금지).",
        "3. confidence는 근거의 확실성(high/medium/low). 지식이 오래됐거나 불확실하면 낮춥니다.",
        "4. reasoning은 1~2문장 한국어. evidence는 판정의 핵심 근거(고객사/라이선스/수치 등) 한 줄.",
        "5. 모든 룰에 대해 정확히 하나의 평가를 반환합니다(rule_id 일치).",
        "6. 투자 추천이 아니라 '룰 충족 여부' 판정임을 유지합니다.",
    ]
    return "\n".join(lines)


def _build_user(card: dict, signals: Optional[dict]) -> str:
    """가변(캐시 미대상) user 프롬프트: 종목 맥락."""
    q = card.get("quant", {})
    fin = card.get("financials", {})
    lines = [
        f"[평가 대상 종목]",
        f"종목명: {card.get('name')}  (티커 {card.get('ticker')}, {card.get('market')})",
        f"섹터/산업: {q.get('sector')} / {q.get('industry')}",
        f"현재가: {q.get('price')} {q.get('currency','')}",
        f"시가총액: {q.get('market_cap')}",
        f"매출(TTM): {q.get('revenue_ttm')}  순이익률: {q.get('profit_margin')}",
        f"52주: {q.get('wk52_low')} ~ {q.get('wk52_high')}",
    ]
    if isinstance(fin, dict) and fin.get("op_margin") is not None:
        lines.append(f"영업이익률(DART): {fin.get('op_margin')}  부채비율: {fin.get('debt_ratio')}")
    if signals and not signals.get("_status"):
        lines.append(
            f"정량신호: 레짐 {signals.get('regime')}, RSI {signals.get('rsi14')}, "
            f"200일선이격 {signals.get('ma200_dev_pct')}%, 3개월수익 {signals.get('ret_3m_pct')}%"
        )
    lines.append("")
    lines.append("위 종목에 대해 11개 룰을 각각 평가해 JSON으로 반환하세요.")
    return "\n".join(lines)


def evaluate_qualitative_rules(card: dict, rulebook: dict,
                               signals: Optional[dict] = None) -> dict:
    """
    정성 룰(codeable != 'yes')을 Claude로 평가.
    반환: {"_status":"ok", "evaluations":[{rule_id,verdict,confidence,reasoning,evidence}],
           "usage":{...}} 또는 {"_status":"<ERROR>", "_msg": ...}
    """
    ok, why = llm_available()
    if not ok:
        return {"_status": "UNAVAILABLE", "_msg": why}

    rules = [r for r in rulebook["rules"] if r.get("codeable") != "yes"]
    client = anthropic.Anthropic(api_key=get_anthropic_key())
    system = _build_system(rulebook, rules)
    user = _build_user(card, signals)

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            system=[{
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},  # 룰북 prefix 캐싱
            }],
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
        )
    except anthropic.AuthenticationError:
        return {"_status": "AUTH_ERROR", "_msg": "API 키가 유효하지 않습니다."}
    except anthropic.RateLimitError:
        return {"_status": "RATE_LIMIT", "_msg": "요청이 많습니다. 잠시 후 재시도하세요."}
    except anthropic.APIStatusError as e:
        return {"_status": "API_ERROR", "_msg": f"{e.status_code}: {e.message}"}
    except Exception as e:  # 네트워크 등
        return {"_status": "ERROR", "_msg": str(e)[:200]}

    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"_status": "PARSE_ERROR", "_msg": text[:200]}

    u = resp.usage
    return {
        "_status": "ok",
        "evaluations": data.get("evaluations", []),
        "usage": {
            "input": u.input_tokens,
            "output": u.output_tokens,
            "cache_read": getattr(u, "cache_read_input_tokens", 0),
            "cache_write": getattr(u, "cache_creation_input_tokens", 0),
        },
        "model": resp.model,
    }
