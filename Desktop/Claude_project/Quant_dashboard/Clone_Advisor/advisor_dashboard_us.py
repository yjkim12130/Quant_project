"""
advisor_dashboard_us.py — 미국 재정·통화 모니터 조립 (Family E)
═══════════════════════════════════════════════════════════════════════
advisor_macro.py가 모은 원본 시계열을 지표 카드·파생 계산·룰 판정으로
조립한다. Family A/B와 동일하게 LLM 없이 룰 템플릿만 쓴다.

단위 주의: WALCL/WRESBAL/WTREGEN은 $M인데 RRPONTSYD만 $B다.
금액을 조합하는 계산은 반드시 to_musd()로 맞춘 뒤 수행한다.
"""
from __future__ import annotations
import json
import os
from datetime import date, datetime, timedelta
from typing import Optional

import advisor_macro as am

_HERE = os.path.dirname(os.path.abspath(__file__))
_REGISTRY_PATH = os.path.join(_HERE, "macro_series.json")

# FRED units_short 원문 → $M 배율
_UNIT_TO_MUSD = {
    "Mil. of $": 1.0, "Mil. of U.S. $": 1.0,
    "Bil. of $": 1000.0, "Bil. of US $": 1000.0,
    "$": 0.000001,
}

_RANK_LOW = 33.0
_RANK_HIGH = 66.0

# pct_rank_3y가 이름 그대로이려면 백분위 입력을 3년으로 잘라야 한다.
# fed_assets만 QT 피크(2022-04)를 담으려고 8년치를 받아오기 때문이다.
_RANK_WINDOW_DAYS = 1095


def load_macro_series() -> Optional[dict]:
    """macro_series.json 로드. 없거나 손상됐으면 None."""
    if not os.path.exists(_REGISTRY_PATH):
        return None
    try:
        with open(_REGISTRY_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def to_musd(value: Optional[float], unit: str) -> Optional[float]:
    """금액을 백만달러($M) 기준으로 정규화. 금액 단위가 아니면 None."""
    if not isinstance(value, (int, float)):
        return None
    mult = _UNIT_TO_MUSD.get(unit)
    return None if mult is None else value * mult


# 파생값은 전부 $M 기준이라 표시 포맷터의 기본 단위도 $M이다.
_MUSD = "Mil. of U.S. $"


def fmt_usd(value: Optional[float], unit: str = _MUSD, signed: bool = False) -> str:
    """금액을 자릿수에 맞춰 $T/$B/$M로 줄여 표기. 금액 단위가 아니면 원값.

    연방 총부채는 원 단위 달러($)로 와서 그대로 찍으면 15자리가 되고 좁은
    metric 카드를 넘친다. 그렇다고 조($T) 고정으로 하면 역레포(수백 $M)나
    월간 재정수지가 0.00T이 되어 못 읽는다 — 그래서 크기에 맞춰 고른다.
    """
    if not isinstance(value, (int, float)):
        return "—"
    musd = to_musd(value, unit)
    if musd is None:                      # "%", "% of GDP" 등 비금액 단위
        return f"{value:+,.2f}" if signed else f"{value:,.2f}"
    sign = "-" if musd < 0 else ("+" if signed else "")
    a = abs(musd)
    if a >= 1_000_000:
        return f"{sign}${a / 1_000_000:,.2f}T"
    if a >= 1_000:
        return f"{sign}${a / 1_000:,.1f}B"
    return f"{sign}${a:,.1f}M"


def pct_rank(values: list[float], current: float) -> Optional[float]:
    """values 안에서 current의 백분위(0~100). 자기 자신 포함 <= 비율."""
    if not values:
        return None
    le = sum(1 for v in values if v <= current)
    return round(le / len(values) * 100, 1)


def _parse(d: str) -> Optional[date]:
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _closest_observation(obs: list[dict], target: date) -> Optional[dict]:
    """target 날짜에 가장 가까운 관측치. change_over와 change_over_labeled가 공유."""
    best, best_gap = None, None
    for o in obs:
        d = _parse(o["date"])
        if d is None:
            continue
        gap = abs((d - target).days)
        if best_gap is None or gap < best_gap:
            best, best_gap = o, gap
    return best


def change_over(obs: list[dict], days: int) -> Optional[float]:
    """days일 전 대비 변화(절대값 차).

    관측 주기가 일/주/월/분기로 제각각이라 "N번째 앞 관측치"를 쓰면
    지표마다 기간이 달라진다. 목표 날짜에 가장 가까운 관측치를 고른다.
    """
    if len(obs) < 2:
        return None
    last_date = _parse(obs[-1]["date"])
    if last_date is None:
        return None
    target = last_date - timedelta(days=days)
    best = _closest_observation(obs[:-1], target)
    if best is None:
        return None
    return round(obs[-1]["value"] - best["value"], 2)


def _period_label(actual_days: int) -> str:
    """실제 관측 간격(일) → 사람이 읽는 기간 라벨.

    분기 시리즈에서 change_over(obs, 30)을 부르면 가장 가까운 관측치가
    실제로는 ~91일 전이다. 요청한 30일이 아니라 실제로 골라진 간격을 보고
    라벨을 정해야 "1개월"이라는 거짓 라벨을 피할 수 있다.
    """
    if actual_days <= 45:
        return "1개월"
    if actual_days <= 135:
        return "1분기"
    if actual_days <= 400:
        return "1년"
    return f"{actual_days}일"


def change_over_labeled(obs: list[dict], days: int) -> tuple[Optional[float], str]:
    """change_over(obs, days) + 실제로 선택된 관측치 간격에 맞는 기간 라벨.

    change_over의 기존 시그니처(다른 곳에서 이미 쓰고 있다)는 건드리지 않고
    별도 헬퍼로 라벨까지 함께 돌려준다.
    """
    fallback = _period_label(days)
    if len(obs) < 2:
        return None, fallback
    last_date = _parse(obs[-1]["date"])
    if last_date is None:
        return None, fallback
    target = last_date - timedelta(days=days)
    best = _closest_observation(obs[:-1], target)
    if best is None:
        return None, fallback
    best_date = _parse(best["date"])
    actual_days = abs((last_date - best_date).days) if best_date else days
    return round(obs[-1]["value"] - best["value"], 2), _period_label(actual_days)


def recent_window(obs: list[dict], days: int = _RANK_WINDOW_DAYS) -> list[dict]:
    """마지막 관측일 기준 days일 이내 관측치만 남긴다.

    지표별 조회기간이 다르면(fed_assets는 8년) 백분위 모수도 달라져
    "3년 백분위"라는 이름이 거짓이 된다. 백분위 입력만 자르고 차트용
    series는 받아온 전체를 그대로 둔다.
    """
    if not obs:
        return []
    last_date = _parse(obs[-1]["date"])
    if last_date is None:
        return list(obs)
    cutoff = last_date - timedelta(days=days)
    out = []
    for o in obs:
        d = _parse(o.get("date", ""))
        if d is None or d >= cutoff:
            out.append(o)
    return out


def _assess(rank: Optional[float], higher_is: str) -> str:
    """백분위 + 해석 방향 → 한 줄 판정."""
    if rank is None:
        return ""
    if higher_is == "neutral":
        return f"3년 백분위 {rank:.0f}%"
    high_is_bad = higher_is == "worse"
    if rank >= _RANK_HIGH:
        return "역사적 고점권(부담)" if high_is_bad else "역사적 고점권(양호)"
    if rank <= _RANK_LOW:
        return "역사적 저점권(양호)" if high_is_bad else "역사적 저점권(부담)"
    return "중간권"


def build_indicator(raw: dict, meta: dict) -> dict:
    """원본 시계열 1종 → 카드 렌더에 필요한 값 일체."""
    base = {
        "id": meta.get("id", ""), "label": meta.get("label", ""),
        "unit": meta.get("unit", ""), "unit_label": meta.get("unit_label", ""),
        "freq": meta.get("freq", ""),
        "latest": None, "latest_date": None,
        "chg_1m": None, "chg_1m_label": "1개월", "chg_1y": None, "pct_rank_3y": None,
        "assessment": "", "series": [],
    }
    status = raw.get("_status")
    obs = raw.get("observations", [])
    if status != "ok" or not obs:
        base["_status"] = status if (status and status != "ok") else "NO_DATA"
        base["_msg"] = raw.get("_msg", "")
        return base

    # 백분위 모수는 최근 3년으로 자른다 — fed_assets만 8년치를 받아오므로
    # 자르지 않으면 pct_rank_3y가 지표마다 다른 기간을 뜻하게 된다.
    window = recent_window(obs)
    rank = pct_rank([o["value"] for o in window], obs[-1]["value"])
    chg_1m, chg_1m_label = change_over_labeled(obs, 30)
    base.update({
        "_status": "ok", "_msg": "",
        "latest": obs[-1]["value"], "latest_date": obs[-1]["date"],
        "chg_1m": chg_1m, "chg_1m_label": chg_1m_label,
        "chg_1y": change_over(obs, 365),
        "pct_rank_3y": rank,
        "assessment": _assess(rank, meta.get("higher_is", "neutral")),
        "series": obs,
    })
    return base


def build_group(raw_group: dict, meta_group: dict) -> dict:
    """그룹 1개의 지표 전체를 레지스트리 순서대로 조립."""
    indicators = [
        build_indicator(raw_group.get(m.get("id", ""), {"_status": "NO_DATA",
                                                        "observations": []}), m)
        for m in meta_group.get("indicators", [])
    ]
    ok = [i for i in indicators if i["_status"] == "ok"]
    return {
        "id": meta_group.get("id", ""), "label": meta_group.get("label", ""),
        "indicators": indicators,
        "_status": "ok" if ok else (indicators[0]["_status"] if indicators else "NO_DATA"),
    }


# ─────────────────────────────────────────────────────────────────────
# 파생 계산 — 원시값만으로는 크기를 가늠할 수 없어 해석 근거를 만든다
# ─────────────────────────────────────────────────────────────────────
def _find(groups: dict, gid: str, iid: str) -> dict:
    """조립된 그룹에서 지표 1개를 꺼낸다. 없으면 빈 dict."""
    for ind in groups.get(gid, {}).get("indicators", []):
        if ind.get("id") == iid:
            return ind
    return {}


def compute_m2_yoy(obs: list[dict]) -> Optional[float]:
    """M2 전년동월 대비 증가율(%). 잔액보다 증감이 의미 있다."""
    if len(obs) < 2:
        return None
    diff = change_over(obs, 365)
    if diff is None:
        return None
    base = obs[-1]["value"] - diff       # 1년 전 값
    if not base:
        return None
    return round(diff / base * 100, 2)


def compute_qt_progress(obs: list[dict]) -> dict:
    """연준 총자산 피크 대비 감축액·감축률 — 양적긴축 진행도."""
    empty = {"peak": None, "peak_date": None, "current": None,
             "drawdown": None, "drawdown_pct": None}
    if not obs:
        return empty
    peak_obs = max(obs, key=lambda o: o["value"])
    current = obs[-1]["value"]
    drawdown = peak_obs["value"] - current
    return {
        "peak": peak_obs["value"], "peak_date": peak_obs["date"],
        "current": current, "drawdown": round(drawdown, 2),
        "drawdown_pct": (round(drawdown / peak_obs["value"] * 100, 2)
                         if peak_obs["value"] else None),
    }


def compute_hy_ig_gap(hy: dict, ig: dict) -> Optional[float]:
    """하이일드 − 투자등급 OAS(bp). 신용 차별화 정도."""
    if hy.get("_status") != "ok" or ig.get("_status") != "ok":
        return None
    a, b = hy.get("latest"), ig.get("latest")
    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        return None
    return round((a - b) * 100, 1)


def compute_net_liquidity(groups: dict) -> Optional[float]:
    """순유동성($M) = 연준 총자산 − 역레포 − 재무부 일반계정.

    RRPONTSYD만 $B라 to_musd()로 맞춘 뒤 뺀다(스펙 §5 단위 정규화).
    """
    parts = []
    for iid in ("fed_assets", "rrp", "tga"):
        ind = _find(groups, "liquidity", iid)
        if ind.get("_status") != "ok":
            return None
        v = to_musd(ind.get("latest"), ind.get("unit", ""))
        if v is None:
            return None
        parts.append(v)
    return round(parts[0] - parts[1] - parts[2], 2)


_NET_LIQUIDITY_PARTS = ("fed_assets", "rrp", "tga")


def build_net_liquidity_series(groups: dict) -> list[dict]:
    """순유동성 시계열 = 연준 총자산 − 역레포 − 재무부 일반계정 ($M).

    스칼라 버전(compute_net_liquidity)과 같은 단위 함정을 관측치마다 밟는다
    — WALCL/WTREGEN은 $M인데 RRPONTSYD만 $B라 날짜별로 to_musd()를 태우지
    않으면 1000배 틀린다.

    세 시리즈는 주기가 다르다(연준자산·TGA는 주간, 역레포는 일간). 보간 대신
    공통 날짜 교집합만 쓴다 — 결과는 주간이 되고 그걸로 충분하다. 셋 중
    하나라도 ok가 아니면 빈 리스트(부분 합성으로 거짓 추세를 만들지 않는다).
    """
    maps: list[dict] = []
    for iid in _NET_LIQUIDITY_PARTS:
        ind = _find(groups, "liquidity", iid)
        if ind.get("_status") != "ok":
            return []
        unit = ind.get("unit", "")
        by_date = {}
        for o in ind.get("series", []):
            value = to_musd(o.get("value"), unit)
            day = o.get("date")
            if value is not None and day:
                by_date[day] = value
        if not by_date:
            return []
        maps.append(by_date)

    common = set(maps[0]) & set(maps[1]) & set(maps[2])
    return [{"date": d, "value": round(maps[0][d] - maps[1][d] - maps[2][d], 2)}
            for d in sorted(common)]


def build_derived(groups: dict) -> dict:
    """파생 지표 묶음."""
    m2 = _find(groups, "liquidity", "m2")
    fed = _find(groups, "liquidity", "fed_assets")
    nl_series = build_net_liquidity_series(groups)
    return {
        "m2_yoy": compute_m2_yoy(m2.get("series", [])),
        "qt": compute_qt_progress(fed.get("series", [])),
        "hy_ig_gap": compute_hy_ig_gap(_find(groups, "credit", "hy_oas"),
                                       _find(groups, "credit", "ig_oas")),
        "net_liquidity": compute_net_liquidity(groups),
        "net_liquidity_series": nl_series,
        "net_liquidity_chg_3m": change_over(nl_series, 90),
    }


# ─────────────────────────────────────────────────────────────────────
# 종합 판정 3줄 — 룰 템플릿(LLM 미사용)
# ─────────────────────────────────────────────────────────────────────
_UNKNOWN = "판정 불가"


def _sign_verdict(value: float) -> str:
    """근거가 하나뿐일 때 그 부호만으로 방향을 읽는다."""
    return "완화" if value > 0 else "긴축" if value < 0 else "중립"


def build_assessment(groups: dict, derived: dict) -> list[dict]:
    """유동성·신용·재정 3줄 판정. 근거 데이터가 없으면 '판정 불가'."""
    rows = []

    # 유동성 — 스펙 §7: "순유동성 3개월 변화 + M2 YoY 부호"
    m2_yoy = derived.get("m2_yoy")
    nl = derived.get("net_liquidity")
    nl_chg = derived.get("net_liquidity_chg_3m")
    has_m2 = isinstance(m2_yoy, (int, float))
    has_nl = isinstance(nl_chg, (int, float))

    nl_txt = (f"순유동성 {fmt_usd(nl)} "
              f"(3개월 {fmt_usd(nl_chg, signed=True)})") if has_nl else ""
    m2_txt = f"M2 전년비 {m2_yoy:+.1f}%" if has_m2 else ""

    if has_nl and has_m2:
        # 두 근거의 부호가 같을 때만 방향을 단정한다. 엇갈리면 중립.
        verdict = ("완화" if nl_chg > 0 and m2_yoy > 0 else
                   "긴축" if nl_chg < 0 and m2_yoy < 0 else "중립")
        text = f"{nl_txt} · {m2_txt}"
    elif has_m2:
        verdict = _sign_verdict(m2_yoy)
        text = f"{m2_txt} · 순유동성 근거 없음(연준자산·역레포·TGA 중 결측)"
    elif has_nl:
        verdict = _sign_verdict(nl_chg)
        text = f"{nl_txt} · M2 데이터 없음"
    else:
        verdict, text = _UNKNOWN, "유동성 데이터 없음"

    if verdict != _UNKNOWN:
        qt = derived.get("qt") or {}
        if isinstance(qt.get("drawdown_pct"), (int, float)):
            text += f" · 연준자산 피크 대비 {qt['drawdown_pct']:.1f}% 축소"
    rows.append({"id": "liquidity", "label": "유동성", "verdict": verdict, "text": text})

    # 신용 — HY OAS 3년 백분위
    hy = _find(groups, "credit", "hy_oas")
    rank = hy.get("pct_rank_3y") if hy.get("_status") == "ok" else None
    if isinstance(rank, (int, float)):
        verdict = ("스트레스" if rank > _RANK_HIGH
                   else "안정" if rank < _RANK_LOW else "경계")
        text = f"하이일드 OAS {hy.get('latest'):.2f}% (3년 백분위 {rank:.0f}%)"
        gap = derived.get("hy_ig_gap")
        if isinstance(gap, (int, float)):
            text += f" · HY−IG {gap:+.0f}bp"
    else:
        verdict, text = _UNKNOWN, "신용 스프레드 데이터 없음"
    rows.append({"id": "credit", "label": "신용", "verdict": verdict, "text": text})

    # 재정 — 부채/GDP 1년 변화
    dg = _find(groups, "fiscal", "debt_gdp")
    if dg.get("_status") == "ok" and isinstance(dg.get("chg_1y"), (int, float)):
        verdict = "부담 가중" if dg["chg_1y"] > 0 else "지속가능"
        text = f"부채/GDP {dg['latest']:.1f}% (1년 {dg['chg_1y']:+.1f}%p)"
        it = _find(groups, "fiscal", "interest")
        if it.get("_status") == "ok" and isinstance(it.get("chg_1y"), (int, float)):
            text += f" · 이자지급 1년 {it['chg_1y']:+,.0f}십억$"
    else:
        verdict, text = _UNKNOWN, "재정 데이터 없음"
    rows.append({"id": "fiscal", "label": "재정", "verdict": verdict, "text": text})

    return rows


# ─────────────────────────────────────────────────────────────────────
# 오케스트레이션
# ─────────────────────────────────────────────────────────────────────
def _empty_briefing(status: str, msg: str = "") -> dict:
    """실패 시 반환할 빈 브리핑. 렌더러가 기대하는 키를 모두 갖춘다."""
    return {"_status": status, "_msg": msg, "groups": {}, "derived": {},
            "assessment": [],
            "generated_at": datetime.now().isoformat(timespec="seconds")}


def build_briefing_us() -> dict:
    """레지스트리 → 수집 → 조립 → 파생 → 판정 전체 파이프라인.

    macro_series.json은 사용자 손편집 지점이므로(스펙 §5) 모양이 어긋난
    레지스트리가 들어올 수 있다. 그런 경우에도 예외를 밖으로 던지지 않고
    NO_REGISTRY로 되돌린다 — 이 탭(tab4)이 tab1보다 먼저 실행되기 때문에
    여기서 예외가 새면 종목 분석 탭까지 통째로 빈 화면이 된다.
    """
    registry = load_macro_series()
    if not registry:
        return _empty_briefing("NO_REGISTRY")

    try:
        raw = am.collect_macro(registry)
        groups = {
            g["id"]: build_group(raw.get(g["id"], {}), g)
            for g in registry.get("groups", [])
            if isinstance(g, dict) and g.get("id")
        }
        derived = build_derived(groups)
        assessment = build_assessment(groups, derived)
    except Exception as e:
        return _empty_briefing("NO_REGISTRY", f"레지스트리 처리 실패: {type(e).__name__}")

    return {
        "_status": "ok",
        "_msg": "",
        "groups": groups,
        "derived": derived,
        "assessment": assessment,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
