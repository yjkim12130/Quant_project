"""
advisor_briefing.py — 시황 브리핑 오케스트레이션 (P2)
═══════════════════════════════════════════════════════════════════════
advisor_news.py가 모은 원본(시황 수치·영문/한국어 뉴스 헤드라인)을 바탕으로:
  1) 오늘 핵심 뉴스(영문) 3건 선별 — RSS 최신순 그대로(select_top_headlines)
  2) 오재승 페르소나 해설 — advisor_data.py의 codeable 룰(OJS-*) 매칭 결과를
     문장 템플릿으로 서술(generate_ojs_commentary)
  3) 빈규리 페르소나 해설 — 코스닥 종목명 매칭 결과를 문장 템플릿으로 서술
     (generate_bkr_commentary, 한국어 뉴스 원문 풀에서 매칭 — 영문 TOP News와는
     별개 소스)
를 생성한다.

★ LLM 미사용(2026-08-16): 원래 Claude API로 자연스러운 문장을 생성했으나,
Anthropic API는 Claude Pro 구독과 완전히 별개의 유료 플랫폼이라(크레딧 별도
결제 필요) 룰 기반 텍스트 템플릿으로 전환했다. 오재승/빈규리 둘 다 애초에
"숫자·판단은 코드가 계산, 자연어는 서술만" 구조였으므로(설계 스펙 §3), 서술
부분을 템플릿으로 바꿔도 핵심 가치(판단 로직 모사)는 그대로 유지된다 — 오히려
어떤 룰이 왜 발동했는지 그대로 노출되어 더 투명하다. advisor_llm.py(종목 분석
탭의 정성 룰 자동평가)는 이 변경과 무관한 별개 기능이라 그대로 둔다.

정책(설계 스펙 §3 — 반드시 준수):
  · 오재승 = 구체적 추천 가능. 숫자(매집구간/분할비율/이격 등)는 반드시
    advisor_data.py의 codeable 룰(compute_ojs_signals/evaluate_ojs_rules)이
    계산한다.
  · 빈규리 = 해자·재무 서술만. 매수가·목표가·타이밍 필드는 아예 존재하지 않는다
    (BKR-STYLE-01 — 실제 빈규리는 이런 언급을 한 적이 없음).
  · 빈규리 해설 대상 종목은 코스닥 승강제 40종목 후보군(KOSDAQ_PREMIUM_CANDIDATES)
    매칭 우선.
"""
from __future__ import annotations
import re
from datetime import datetime
from typing import Optional

import advisor_data as ad
import advisor_news as an

# 빈규리 페르소나 디스클레이머 — 반드시 코드 상수(BKR-STYLE-01, codeable=yes).
# advisor_data.py apply_rulebook()의 동일 룰 표기(약 545행)와 문구를 그대로
# 맞춘다 — 두 곳이 달라지면 안 된다.
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

# 길이 내림차순 — "테스"가 "두산테스나"보다 먼저 매치되어 오귀속되는 것을 방지.
_BKR_CANDIDATES_BY_LEN = sorted(KOSDAQ_PREMIUM_CANDIDATES, key=len, reverse=True)


# ─────────────────────────────────────────────────────────────────────
# 1) 핵심 뉴스 선별 — RSS가 이미 최신순으로 제공하므로 앞에서부터 그대로 사용
# ─────────────────────────────────────────────────────────────────────
def select_top_headlines(raw_headlines: list[dict], limit: int = 3) -> dict:
    """뉴스 원문 앞에서부터 limit건. RSS 원문 순서를 그대로 신뢰(LLM 큐레이션 없음)."""
    if not raw_headlines:
        return {"_status": "NO_HEADLINES", "top": [],
                "_msg": "뉴스 소스 일시 장애 — RSS 두 곳 모두 응답 없음"}
    return {"_status": "ok", "top": raw_headlines[:limit]}


# ─────────────────────────────────────────────────────────────────────
# 2) 오재승 해설 — codeable 룰 매칭 결과를 문장 템플릿으로 서술
# ─────────────────────────────────────────────────────────────────────
def generate_ojs_commentary(dashboard: dict, top_headlines: list[dict],
                            target_ticker: str = _OJS_TARGET_TICKER) -> dict:
    """오재승 페르소나: advisor_data.evaluate_ojs_rules()의 활성 룰을 그대로 서술.

    숫자(매집구간/분할비율/이격 등)는 전부 advisor_data.py의 codeable 룰이
    계산한 값이고, 여기선 그 결과를 문장으로 이어붙일 뿐 새 숫자를 만들지 않는다.
    """
    close = ad.get_price_history(target_ticker)
    signals = ad.compute_ojs_signals(close) if close is not None else {"_status": "INSUFFICIENT_HISTORY"}
    if signals.get("_status"):
        # 실제 가격 히스토리를 받지 못해 정량 신호가 하나도 없는 상태(주로
        # yfinance rate-limit). 서술할 근거가 없으므로 조용히 반환한다.
        return {"_status": "NO_SIGNALS",
                "_msg": "가격 히스토리를 받지 못해 정량 신호를 계산할 수 없습니다.",
                "target": target_ticker}
    rules = ad.evaluate_ojs_rules(signals)
    active = [r for r in rules if r["active"]]

    if active:
        commentary = " / ".join(f"{r['id']} · {r['note']}" for r in active)
        action = active[0]["note"]  # evaluate_ojs_rules가 반환하는 순서 = 우선순위
    else:
        commentary = f"{target_ticker}: 뚜렷한 트레이딩 트리거 없음 — 관망 구간."
        action = "관망 / 분할 매수 대기"

    return {
        "_status": "ok",
        "target": target_ticker,
        "signals": signals,
        "active_rules": rules,
        "commentary": commentary,
        "action": action,
    }


# ─────────────────────────────────────────────────────────────────────
# 3) 빈규리 해설 — 종목 매칭 사실만 서술, 매수가·타이밍 없음
# ─────────────────────────────────────────────────────────────────────
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
    """빈규리 페르소나: 오늘 헤드라인에서 코스닥승강제 후보군 종목이 매칭됐다는
    사실만 서술. 매수가/타이밍 필드 자체가 없다(BKR-STYLE-01).

    kr_headlines는 advisor_news.fetch_korean_headlines()의 한국어 원문 풀
    (advisor_news.fetch_raw_headlines()의 영문 TOP News와는 별개 소스) — 코스닥
    종목명이 한글이라 매칭에는 한국어 뉴스가 필요하다.
    """
    picked = _pick_bkr_focus(kr_headlines)
    if not picked:
        return {"_status": "NO_FOCUS_STOCK",
                "_msg": "오늘 헤드라인에 코스닥승강제 후보군 종목이 없습니다."}
    focus, matched_headline = picked

    commentary = (
        f"오늘 '{matched_headline.get('source', '')}' 뉴스에서 코스닥 승강제 "
        f"후보군 종목 '{focus}' 관련 헤드라인이 포착됐습니다: "
        f"「{matched_headline.get('title', '')}」"
    )
    return {
        "_status": "ok",
        "focus_stock": focus,
        "matched_headline": matched_headline,
        "commentary": commentary,
        "disclaimer": _BKR_DISCLAIMER,
    }


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
