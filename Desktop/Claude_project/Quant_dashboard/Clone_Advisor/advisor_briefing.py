"""
advisor_briefing.py — 시황 브리핑 LLM 오케스트레이션 (P2)
═══════════════════════════════════════════════════════════════════════
advisor_news.py가 모은 원본(시황 수치·영문/한국어 뉴스 헤드라인)을 바탕으로:
  1) 오늘 핵심 뉴스(영문) 3건 선별(select_top_headlines)
  2) 오재승 페르소나 해설 — 구체적 추천 포함(generate_ojs_commentary)
  3) 빈규리 페르소나 해설 — 해자/재무 서술만, 매수가·타이밍 없음(generate_bkr_commentary,
     한국어 뉴스 원문 풀에서 코스닥 종목명 매칭 — 영문 TOP News와는 별개 소스)
를 생성한다. Claude 클라이언트 사용 패턴(구조화 출력, 프롬프트 캐싱,
에러 분류)은 advisor_llm.py와 동일하게 맞춘다.

정책(설계 스펙 §3 — 반드시 준수):
  · 오재승 = 구체적 추천 가능. 숫자(매집구간/분할비율/이격 등)는 반드시
    advisor_data.py의 codeable 룰(compute_ojs_signals/evaluate_ojs_rules)이
    계산하고, LLM은 그 숫자를 근거로 서술만 한다(숫자를 새로 만들지 않음).
  · 빈규리 = 해자·재무 서술만. 매수가·목표가·타이밍 필드는 출력 스키마에
    아예 존재하지 않는다(BKR-STYLE-01 — 실제 빈규리는 이런 언급을 한 적이 없음).
  · 빈규리 해설 대상 종목은 코스닥 승강제 40종목 후보군(KOSDAQ_PREMIUM_CANDIDATES)
    매칭 우선.
"""
from __future__ import annotations
import json
import re
from datetime import datetime
from typing import Optional

import advisor_data as ad
import advisor_llm as al
import advisor_news as an

# 빈규리 페르소나 디스클레이머 — 반드시 코드 상수. LLM이 생성하는 자유 텍스트가
# 아니다(BKR-STYLE-01, codeable=yes). advisor_data.py apply_rulebook()의 동일 룰
# 표기(약 545행)와 문구를 그대로 맞춘다 — 두 곳이 달라지면 안 된다.
_BKR_DISCLAIMER = "본 카드는 투자의견이 아닌 종목 소개입니다."

# ─────────────────────────────────────────────────────────────────────
# 코스닥 승강제 프리미엄리그 예상 수혜주 40종목
# 출처: 코스닥 승강제 종합분석보고서(QIA-2026-MK-0703, 빈규리 작성, 2026-07-03)
#
# 전부 한글 종목명이라 advisor_news.fetch_raw_headlines()(영문 RSS)로는 매치가
# 거의 안 걸린다 — 그래서 빈규리 전용으로 advisor_news.fetch_korean_headlines()
# (한국경제/연합뉴스, 한글) 원문 풀을 따로 받아 여기에 매칭한다.
KOSDAQ_PREMIUM_CANDIDATES = [
    "리노공업", "ISC", "피에스케이", "HPSP", "코미코", "테스", "고영",
    "하나마이크론", "동진쎄미켐", "주성엔지니어링", "티씨케이", "티에스이",
    "두산테스나", "기가비스", "하나머티리얼즈", "티엘비", "프로텍", "심텍",
    "삼현", "에스피지", "원익머트리얼즈", "동성화인텍", "에코프로비엠",
    "비즈로셀", "LS마린솔루션", "세미파이브", "가온칩스", "에스엠", "휴젤",
    "파마리서치", "클래시스", "에스티팜", "엘앤씨바이오", "인바디", "티앤엘",
    "실리콘투", "피엔티", "RFHIC", "비에이치아이", "파크시스템스",
]

_OJS_TARGET_TICKER = "QQQ"  # MVP 고정 대상: 오재승 방 "미국 ETF 적립" 테마와 일치


# ─────────────────────────────────────────────────────────────────────
# 공통 Claude 호출 헬퍼 (advisor_llm.py의 에러 분류 패턴 재사용)
# ─────────────────────────────────────────────────────────────────────
def _call_claude(system: str, user: str, schema: dict, max_tokens: int) -> dict:
    """성공 시 {"_status":"ok", **parsed_json}, 실패 시 에러 dict."""
    client = al.anthropic.Anthropic(api_key=al.get_anthropic_key())
    try:
        resp = client.messages.create(
            model=al.MODEL,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            system=[{
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
    except al.anthropic.AuthenticationError:
        return {"_status": "AUTH_ERROR", "_msg": "API 키가 유효하지 않습니다."}
    except al.anthropic.RateLimitError:
        return {"_status": "RATE_LIMIT", "_msg": "요청이 많습니다. 잠시 후 재시도하세요."}
    except al.anthropic.APIStatusError as e:
        return {"_status": "API_ERROR", "_msg": f"{e.status_code}: {e.message}"}
    except Exception as e:  # 네트워크 등
        return {"_status": "ERROR", "_msg": str(e)[:200]}

    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"_status": "PARSE_ERROR", "_msg": text[:200]}
    return {"_status": "ok", **data}


# ─────────────────────────────────────────────────────────────────────
# 1) 핵심 뉴스 3건 선별
# ─────────────────────────────────────────────────────────────────────
_TOP_SCHEMA = {
    "type": "object",
    "properties": {
        "top": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "link": {"type": "string"},
                    "source": {"type": "string"},
                    "why": {"type": "string"},
                },
                "required": ["title", "link", "source", "why"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["top"],
    "additionalProperties": False,
}


def select_top_headlines(raw_headlines: list[dict], limit: int = 3) -> dict:
    """뉴스 원문 목록 → 오늘 핵심 limit건 + 왜 중요한지 1줄."""
    if not raw_headlines:
        return {"_status": "NO_HEADLINES", "top": [],
                "_msg": "뉴스 소스 일시 장애 — RSS 두 곳 모두 응답 없음"}
    ok, why = al.llm_available()
    if not ok:
        return {"_status": "UNAVAILABLE", "_msg": why, "top": []}

    system = (
        "당신은 시장 브리핑 에디터입니다. 주어진 뉴스 원문 목록에서 오늘 시장에 "
        f"가장 중요한 {limit}건을 고르고, 각각 왜 중요한지 1줄로 씁니다. "
        "title/link/source는 원문 그대로 복사하고 절대 새로 만들지 않습니다."
    )
    user = f"[뉴스 원문 목록]\n{json.dumps(raw_headlines, ensure_ascii=False)}"
    result = _call_claude(system, user, _TOP_SCHEMA, max_tokens=1500)
    if result["_status"] != "ok":
        result.setdefault("top", [])
    return result


# ─────────────────────────────────────────────────────────────────────
# 2) 오재승 해설 — 구체적 추천 포함
# ─────────────────────────────────────────────────────────────────────
_OJS_SCHEMA = {
    "type": "object",
    "properties": {
        "commentary": {"type": "string"},
        "action": {"type": "string"},
    },
    "required": ["commentary", "action"],
    "additionalProperties": False,
}


def generate_ojs_commentary(dashboard: dict, top_headlines: list[dict],
                            target_ticker: str = _OJS_TARGET_TICKER) -> dict:
    """오재승 페르소나: 매크로·타이밍 해설 + 구체적 action(매집구간/분할비율 등)."""
    ok, why = al.llm_available()
    if not ok:
        return {"_status": "UNAVAILABLE", "_msg": why}

    close = ad.get_price_history(target_ticker)
    signals = ad.compute_ojs_signals(close) if close is not None else {"_status": "INSUFFICIENT_HISTORY"}
    if signals.get("_status"):
        # 실제 가격 히스토리를 받지 못해 정량 신호가 하나도 없는 상태(주로 yfinance
        # rate-limit). 숫자 근거가 전혀 없는 채로 LLM에 "구체적 action을 써라"고
        # 요청하면 모델이 숫자를 지어낼 수밖에 없다 — 이 경우 LLM을 호출하지 않고
        # 조용히 반환한다.
        return {"_status": "NO_SIGNALS",
                "_msg": "가격 히스토리를 받지 못해 정량 신호를 계산할 수 없습니다.",
                "target": target_ticker}
    rules = ad.evaluate_ojs_rules(signals)

    ojs_rb = ad.load_ojs_rulebook()
    philosophy = " ".join(ojs_rb.get("philosophy", [])) if ojs_rb else ""

    system = (
        "당신은 '오재승 자문역'의 매크로·타이밍 판단기준(철학·룰북)을 이식받은 해설 엔진입니다. "
        "핵심은 말투 모사가 아니라 그의 실제 판단 논리(어떤 신호에서 왜 그렇게 판단하는지)를 "
        "재현하는 것입니다.\n"
        f"철학: {philosophy}\n"
        "오늘의 시장 데이터·정량 신호·핵심 뉴스를 아래 활성 룰에 대입해 2~3문장 해설을 쓰고, "
        "마지막에 action 한 줄(구체적 매집구간·분할비율·진입 판단)을 씁니다. "
        "action은 반드시 아래 제공된 정량 신호의 숫자만 근거로 사용하고 새로운 숫자를 만들지 않습니다."
    )
    user = (
        f"[대상] {target_ticker}\n"
        f"[정량 신호] {json.dumps(signals, ensure_ascii=False)}\n"
        f"[활성 룰] {json.dumps(rules, ensure_ascii=False)}\n"
        f"[오늘 시장 대시보드] {json.dumps(dashboard, ensure_ascii=False)}\n"
        f"[오늘 핵심 뉴스] {json.dumps(top_headlines, ensure_ascii=False)}\n"
        "위 정보로 해설과 action을 JSON으로 반환하세요."
    )
    result = _call_claude(system, user, _OJS_SCHEMA, max_tokens=2000)
    if result["_status"] == "ok":
        result["target"] = target_ticker
        result["signals"] = signals
        result["active_rules"] = rules
    return result


# ─────────────────────────────────────────────────────────────────────
# 3) 빈규리 해설 — 해설만, 매수가·타이밍 없음
# ─────────────────────────────────────────────────────────────────────
_BKR_SCHEMA = {
    "type": "object",
    "properties": {
        "commentary": {"type": "string"},
    },
    "required": ["commentary"],
    "additionalProperties": False,
}

# 길이 내림차순 — "테스"가 "두산테스나"보다 먼저 매치되어 오귀속되는 것을 방지.
_BKR_CANDIDATES_BY_LEN = sorted(KOSDAQ_PREMIUM_CANDIDATES, key=len, reverse=True)


def _pick_bkr_focus(kr_headlines: list[dict]) -> Optional[tuple[str, dict]]:
    """한국어 헤드라인 원문에서 코스닥 승강제 40종목 후보군과 일치하는 첫
    (종목명, 매치된 헤드라인) 쌍. 매치 없으면 None.

    두 가지 함정을 피한다:
      1) 순서 의존 오귀속 — 짧은 이름이 긴 이름의 부분 문자열인 경우
         (예: "테스" ⊂ "두산테스나") 긴 이름을 먼저 검사해야 한다.
      2) 영문 대문자 약칭의 오탐 — "ISC" 같은 짧은 ASCII 티커는 "DISCLOSES",
         "DISCOVER" 등 무관한 영단어 안의 부분 문자열로도 매치되므로 단어
         경계(\\b) 매치를 요구한다. 한글 종목명은 단어 경계 개념이 다르게
         적용되고 "ISC" 사례 같은 오탐 위험이 없어 부분 문자열 매치로 충분하다.
    """
    for h in kr_headlines:
        title = h.get("title", "")
        for name in _BKR_CANDIDATES_BY_LEN:
            if name.isascii() and name.isupper():
                if re.search(rf"\b{re.escape(name)}\b", title):
                    return name, h
            elif name in title:
                return name, h
    return None


def generate_bkr_commentary(dashboard: dict, kr_headlines: list[dict]) -> dict:
    """빈규리 페르소나: 해자·재무 서술만. 매수가/타이밍 필드 자체가 스키마에 없음.

    kr_headlines는 advisor_news.fetch_korean_headlines()의 한국어 원문 풀
    (advisor_news.fetch_raw_headlines()의 영문 TOP News와는 별개 소스) — 코스닥
    종목명이 한글이라 매칭에는 한국어 뉴스가 필요하다.
    """
    ok, why = al.llm_available()
    if not ok:
        return {"_status": "UNAVAILABLE", "_msg": why}

    picked = _pick_bkr_focus(kr_headlines)
    if not picked:
        return {"_status": "NO_FOCUS_STOCK",
                "_msg": "오늘 헤드라인에 코스닥승강제 후보군 종목이 없습니다."}
    focus, matched_headline = picked

    bkr_rb = ad.load_rulebook()
    philosophy = " ".join(bkr_rb.get("philosophy", [])) if bkr_rb else ""

    system = (
        "당신은 '빈규리 CPA' 자문역의 펀더멘탈 판단기준(사업·해자·재무를 보는 기준)을 이식받은 "
        "해설 엔진입니다. 핵심은 말투 모사가 아니라 그녀가 실제로 어떤 근거로 종목을 평가하는지 "
        "그 분석 논리를 재현하는 것입니다.\n"
        f"철학: {philosophy}\n"
        "사업·해자·재무 관점으로만 2~3문장 해설을 씁니다. "
        "절대 금지: 매수가, 목표가, 매수 시점, 진입 타이밍 등 구체적 가격·타이밍 언급. "
        "실제 빈규리는 이런 언급을 한 적이 없습니다(BKR-STYLE-01). "
        "'종목 소개이지 투자의견이 아니다'라는 안내 문구는 화면에 코드가 별도로 "
        "고정 표기하므로 당신이 직접 쓸 필요는 없습니다."
    )
    # 참고: 이 페르소나는 사업·해자·재무 서술만 하며 매크로/가격 데이터를 다루지
    # 않으므로(BKR-STYLE-01 및 설계 스펙 §3), 오재승 해설과 달리 시장 대시보드
    # (지수·VIX·DXY 등 가격 데이터)는 프롬프트에 포함하지 않는다. 뉴스도 관련
    # 없는 나머지 원문을 다 넣지 않고, 실제로 매치를 유발한 헤드라인 1건만 근거로
    # 준다 — 잡음을 줄이고 "왜 이 종목을 골랐는지"를 명확히 한다.
    user = (
        f"[오늘 헤드라인에서 발견된 종목] {focus}\n"
        f"[촉발 뉴스] {json.dumps(matched_headline, ensure_ascii=False)}\n"
        "위 정보로 해설을 JSON으로 반환하세요."
    )
    result = _call_claude(system, user, _BKR_SCHEMA, max_tokens=1500)
    if result["_status"] == "ok":
        result["focus_stock"] = focus
        result["disclaimer"] = _BKR_DISCLAIMER
    return result


# ─────────────────────────────────────────────────────────────────────
# 4) 오케스트레이션
# ─────────────────────────────────────────────────────────────────────
def build_briefing() -> dict:
    """시황 브리핑 전체 파이프라인 실행.

    영문 원문(TOP News/오재승용)과 한국어 원문(빈규리 매칭용)은 서로 다른
    풀이다 — advisor_news.fetch_raw_headlines() vs .fetch_korean_headlines().
    """
    dashboard = an.get_market_dashboard()
    raw = an.fetch_raw_headlines()
    headlines = select_top_headlines(raw)
    top = headlines.get("top", [])
    kr_raw = an.fetch_korean_headlines()
    ojs = generate_ojs_commentary(dashboard, top)
    bkr = generate_bkr_commentary(dashboard, kr_raw)
    return {
        "dashboard": dashboard,
        "headlines": headlines,
        "ojs": ojs,
        "bkr": bkr,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
