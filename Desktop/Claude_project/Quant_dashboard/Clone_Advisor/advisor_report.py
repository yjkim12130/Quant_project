"""
advisor_report.py — 일간 시황 대시보드 정적 HTML 리포트 (Family A)
═══════════════════════════════════════════════════════════════════════
advisor_dashboard.build_dashboard()의 10섹션 dict를 참고 이미지 스타일의
독립 실행형 HTML 문서로 렌더링한다. 실제 뉴스 관련 스톡 사진은 재현하지
않고 아이콘/이모지 카드로 단순화한다(설계 스펙 §2 — 2026-08-17 사용자
승인). 외부 템플릿 엔진 의존성 없이 순수 Python 문자열 포맷으로 조립한다.

build_dashboard()가 담는 문자열 값(뉴스 헤드라인 제목/출처/링크, 관심종목
카테고리·기업명, 캘린더 이벤트명, 룰 템플릿 서술 등)은 RSS·수기 JSON 등
이 코드베이스가 통제하지 않는 소스에서 온다. 이 파일이 만드는 HTML은
디스크에 저장되어 브라우저로 열리므로, HTML 태그/속성에 삽입되는 모든
동적 문자열은 html.escape()로 이스케이프한다(콘텐츠 인젝션 방지).
"""
from __future__ import annotations
import html
import os
from datetime import date
from pathlib import Path
from typing import Optional

import advisor_dashboard as adb

_HERE = os.path.dirname(os.path.abspath(__file__))

_CSS = """
body { background:#0d1117; color:#d6dde8; font-family:'Segoe UI',sans-serif; margin:0; padding:24px; }
.header { background:#0b2a5c; color:#fff; padding:20px 24px; border-radius:12px; margin-bottom:16px; }
.header h1 { margin:0 0 4px; font-size:22px; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; margin-bottom:20px; }
.card { background:#1a1d26; border:1px solid #2e3650; border-radius:12px; padding:14px 16px; }
.card h3 { margin:0 0 6px; font-size:14px; color:#8899aa; }
.card .val { font-size:20px; font-weight:700; }
.up { color:#00d084; } .down { color:#ff4444; }
.section-title { font-size:16px; font-weight:700; margin:24px 0 10px; border-bottom:1px solid #2e3650; padding-bottom:6px; }
table { width:100%; border-collapse:collapse; }
th, td { text-align:left; padding:8px 10px; border-bottom:1px solid #2e3650; font-size:13px; }
.flow { display:flex; gap:8px; flex-wrap:wrap; }
.flow .step { flex:1; min-width:140px; background:#1a1d26; border:1px solid #2e3650; border-radius:10px; padding:10px 12px; }
.scenario { display:flex; gap:10px; }
.scenario .box { flex:1; background:#1a1d26; border:1px solid #2e3650; border-radius:10px; padding:12px; }
.scenario .likely { border-color:#00d084; }
.footer { margin-top:24px; font-size:12px; color:#8899aa; }
"""


def _fmt_pct(v) -> str:
    return f"{v:+.2f}%" if isinstance(v, (int, float)) else "—"


def _tech_dashboard_html(dash: dict) -> str:
    if dash.get("_status") == "NO_YFINANCE":
        return "<p>yfinance 미설치로 시황 데이터를 가져올 수 없습니다.</p>"
    cards = []
    for key, label in adb.TECH_LABELS.items():
        v = dash.get(key, {}) if isinstance(dash.get(key), dict) else {}
        price = v.get("price")
        chg = v.get("chg_pct")
        cls = "up" if isinstance(chg, (int, float)) and chg >= 0 else "down"
        price_txt = f"{price:,.2f}" if isinstance(price, (int, float)) else "—"
        cards.append(
            f'<div class="card"><h3>{html.escape(label)}</h3>'
            f'<div class="val">{price_txt}</div>'
            f'<div class="{cls}">{_fmt_pct(chg)}</div></div>'
        )
    return f'<div class="grid">{"".join(cards)}</div>'


def _fmt_bp(v) -> str:
    return f"{v:+.0f}bp" if isinstance(v, (int, float)) else "—"


def _yield_curve_html(yc: dict) -> str:
    """장단기 스프레드 카드 2장 + 추세 요약 + 최근 5거래일 관측치.

    자립형 HTML이라 plotly를 심을 수 없어(Streamlit 탭에는 추세 차트가 있다)
    카드의 1개월·3개월 변화와 최근 관측치 표로 추세를 대신 전달한다.
    """
    if yc.get("_status") != "ok":
        return (f"<p>금리 곡선 데이터 조회 실패 [{html.escape(str(yc.get('_status')))}]"
                f": {html.escape(str(yc.get('_msg', '')))}</p>")

    cards = []
    for key, label in adb.SPREAD_LABELS.items():
        value = yc["latest"].get(key)
        d1m = yc["chg_1m"].get(key)
        d3m = yc["chg_3m"].get(key)
        cls = "up" if isinstance(d1m, (int, float)) and d1m >= 0 else "down"
        cards.append(
            f'<div class="card"><h3>{html.escape(label)}</h3>'
            f'<div class="val">{_fmt_bp(value)}</div>'
            f'<div class="{cls}">1개월 {_fmt_bp(d1m)} · 3개월 {_fmt_bp(d3m)}</div></div>'
        )

    rows = "".join(
        f'<tr><td>{html.escape(r["date"])}</td>'
        f'<td>{_fmt_bp(r["t10y3m"])}</td><td>{_fmt_bp(r["t30y10y"])}</td></tr>'
        for r in yc["series"][-5:]
    )
    return (
        f'<div class="grid">{"".join(cards)}</div>'
        f'<p>{html.escape(yc.get("text", ""))}</p>'
        "<table><tr><th>날짜</th><th>10년-3개월</th><th>30년-10년</th></tr>"
        f"{rows}</table>"
    )


def _summary_html(movers: list[dict]) -> str:
    if not movers:
        return "<p>변동 데이터가 없습니다.</p>"
    items = "".join(f"<li>{html.escape(m['text'])}</li>" for m in movers)
    return f"<ul>{items}</ul>"


def _must_know_html(movers: list[dict]) -> str:
    if not movers:
        return "<p>변동 데이터가 없습니다.</p>"
    cards = "".join(
        f'<div class="card"><h3>0{i+1}. {html.escape(m["label"])}</h3>'
        f'<div class="val">{_fmt_pct(m["chg_pct"])}</div></div>'
        for i, m in enumerate(movers)
    )
    return f'<div class="grid">{cards}</div>'


def _action_html(action: dict) -> str:
    if action.get("_status") != "ok":
        status = html.escape(str(action.get("_status")))
        msg = html.escape(str(action.get("_msg", "")))
        return f"<p>Today's Action 생성 실패 [{status}]: {msg}</p>"
    commentary = html.escape(action["commentary"])
    action_text = html.escape(action["action"])
    return f'<p>{commentary}</p><p><b>💡 {action_text}</b></p>'


def _news_html(items: list[dict]) -> str:
    """이 리포트는 디스크에 저장되어 file:// 오리진으로 열릴 수 있으므로,
    RSS가 준 link 값이 http(s) 스킴이 아니면(javascript:/data: 등) 클릭
    가능한 <a>로 만들지 않고 제목만 평문으로 보여준다."""
    if not items:
        return "<p>오늘 선별된 헤드라인이 없습니다.</p>"
    rows = []
    for it in items:
        source_html = html.escape(it["source"])
        title_html = html.escape(it["title"])
        link = it["link"]
        if isinstance(link, str) and link.strip().lower().startswith(("http://", "https://")):
            rows.append(
                f'<li><b>[{source_html}]</b> '
                f'<a href="{html.escape(link, quote=True)}">{title_html}</a></li>'
            )
        else:
            rows.append(f'<li><b>[{source_html}]</b> {title_html}</li>')
    return f"<ul>{''.join(rows)}</ul>"


def _flow_html(flow: list[dict]) -> str:
    if not flow:
        return "<p>오늘은 뚜렷한 드라이버가 없습니다(임계값 미달).</p>"
    steps = "".join(
        f'<div class="step"><b>{html.escape(s["step"])}</b><br>{html.escape(s["label"])}</div>'
        for s in flow
    )
    return f'<div class="flow">{steps}</div>'


def _scenarios_html(scenarios: list[dict]) -> str:
    boxes = "".join(
        f'<div class="box{" likely" if sc["likely"] else ""}">'
        f'<b>{html.escape(sc["label"])}{" ⭐" if sc["likely"] else ""}</b>'
        f'<p>{html.escape(sc["text"])}</p></div>'
        for sc in scenarios
    )
    return f'<div class="scenario">{boxes}</div>'


def _calendar_html(events: list[dict]) -> str:
    """econ_calendar.json은 사용자가 주기적으로 수기 편집하는 파일이므로
    (파일 자체의 _note 필드, 설계 스펙 §3⑧ 참조) 필드 누락/오타에도 절대
    KeyError/ValueError를 내지 않는다 — 모든 필드를 .get()으로 읽고
    importance 정수 변환은 실패 시 1로 폴백, 결과는 0~5로 클램프한다."""
    if not events:
        return "<p>등록된 일정이 없습니다.</p>"
    rows = []
    for e in events:
        try:
            importance = int(e.get("importance", 1))
        except (TypeError, ValueError):
            importance = 1
        importance = max(0, min(5, importance))
        rows.append(
            f'<tr><td>{html.escape(str(e.get("date", "")))}</td>'
            f'<td>{html.escape(str(e.get("time_kst", "")))}</td>'
            f'<td>{html.escape(str(e.get("event", "")))}</td>'
            f'<td>{"★" * importance}</td>'
            f'<td>{html.escape(str(e.get("source", "")))}</td></tr>'
        )
    return (
        "<table><tr><th>날짜</th><th>시각(KST)</th><th>이벤트</th><th>중요도</th><th>발표처</th></tr>"
        f"{''.join(rows)}</table>"
    )


def _fact_impact_html(rows: list[dict]) -> str:
    if not rows:
        return "<p>오늘은 뚜렷한 팩트/임팩트가 없습니다.</p>"
    body = "".join(
        f'<tr><td>{html.escape(r["fact"])}</td><td>{html.escape(r["impact"])}</td></tr>'
        for r in rows
    )
    return f"<table><tr><th>Fact</th><th>Impact</th></tr>{body}</table>"


def _top10_html(top10: dict) -> str:
    def _col(items: list[dict]) -> str:
        if not items:
            return "<p>—</p>"
        rows = "".join(
            f"<li>{i+1}. <b>{html.escape(it.get('category', ''))}</b> — {html.escape(it.get('company', ''))}</li>"
            for i, it in enumerate(items)
        )
        return f"<ol style='list-style:none;padding-left:0;'>{rows}</ol>"

    return (
        '<div class="grid" style="grid-template-columns:1fr 1fr;">'
        f'<div class="card"><h3>🇺🇸 미국 TOP5</h3>{_col(top10.get("us_top5", []))}</div>'
        f'<div class="card"><h3>🇰🇷 한국 TOP5</h3>{_col(top10.get("kr_top5", []))}</div>'
        "</div>"
    )


def _bkr_html(bkr: dict) -> str:
    """Streamlit 탭(advisor_app.py 🟣 빈규리 해설 섹션)과 동일한 3분기 처리를
    HTML 리포트에도 반영한다 — _status == "ok"/"NO_FOCUS_STOCK"/그 외 실패,
    _action_html()과 동일한 실패 표기 패턴을 따른다."""
    status = bkr.get("_status")
    if status == "ok":
        focus = html.escape(str(bkr.get("focus_stock", "")))
        commentary = html.escape(str(bkr.get("commentary", "")))
        disclaimer = html.escape(str(bkr.get("disclaimer", "")))
        return (
            f'<p><b>{focus}</b></p><p>{commentary}</p>'
            f'<p style="color:#8899aa;font-size:12px;">{disclaimer}</p>'
        )
    if status == "NO_FOCUS_STOCK":
        msg = html.escape(str(bkr.get("_msg", "오늘은 해당되는 종목이 없습니다.")))
        return f"<p>{msg}</p>"
    status_txt = html.escape(str(status))
    msg = html.escape(str(bkr.get("_msg", "")))
    return f"<p>빈규리 해설 생성 실패 [{status_txt}]: {msg}</p>"


def render_html(dashboard: dict) -> str:
    """advisor_dashboard.build_dashboard() 출력 → 독립 실행형 HTML 문자열."""
    sections = [
        ("① Today's Summary", _summary_html(dashboard["summary"])),
        ("② 오늘 반드시 알아야 할 3가지", _must_know_html(dashboard["must_know"])),
        ("③ Tech Dashboard", _tech_dashboard_html(dashboard["tech_dashboard"])),
        ("③-1 미국 국채 금리 곡선 · 장단기 스프레드",
         _yield_curve_html(dashboard.get("yield_curve", {}))),
        ("④ Today's Action", _action_html(dashboard["todays_action"])),
        ("⑤ TOP NEWS", _news_html(dashboard["top_news"])),
        ("⑥ Global → Korea Impact Flow", _flow_html(dashboard["impact_flow"])),
        ("⑦ 오늘 시나리오", _scenarios_html(dashboard["scenarios"])),
        ("⑧ 오늘·이번주 일정", _calendar_html(dashboard["calendar"])),
        ("⑨ Fact / Impact", _fact_impact_html(dashboard["fact_impact"])),
        ("⑩ 수혜 가능 카테고리 · 관찰기업 TOP10", _top10_html(dashboard["top10"])),
        ("🟣 빈규리 해설 — 펀더멘탈", _bkr_html(dashboard["bkr"])),
    ]
    body = "".join(
        f'<div class="section-title">{title}</div>{section_html}'
        for title, section_html in sections
    )
    generated_at = dashboard.get("generated_at", "") or ""
    return (
        "<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'>"
        f"<title>해외 테크·시장 브리핑 {html.escape(generated_at[:10])}</title>"
        f"<style>{_CSS}</style></head><body>"
        '<div class="header"><h1>해외 테크·시장 브리핑</h1>'
        f'<div>생성 시각: {html.escape(generated_at)}</div></div>'
        f"{body}"
        '<div class="footer">본 자료는 정보 제공 목적이며 투자 권유가 아닙니다.</div>'
        "</body></html>"
    )


def save_report(doc: str, as_of: Optional[date] = None) -> Path:
    """reports/YYYY-MM-DD_briefing.html로 저장, 저장된 Path 반환."""
    as_of = as_of or date.today()
    out_dir = Path(_HERE) / "reports"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{as_of.isoformat()}_briefing.html"
    out_path.write_text(doc, encoding="utf-8")
    return out_path


# ─────────────────────────────────────────────────────────────────────
# Family B — 미국·한국 증시·정책 브리핑(PAGE1+PAGE2) HTML 렌더러
# ─────────────────────────────────────────────────────────────────────
def _kpi_html_kr(kpi: list[dict]) -> str:
    cards = []
    for item in kpi:
        label = html.escape(str(item.get("label", "")))
        value = item.get("value")
        chg = item.get("chg_pct")
        cls = "up" if isinstance(chg, (int, float)) and chg >= 0 else "down"
        value_txt = f"{value:,.2f}" if isinstance(value, (int, float)) else "—"
        chg_txt = _fmt_pct(chg) if chg is not None else ""
        cards.append(
            f'<div class="card"><h3>{label}</h3>'
            f'<div class="val">{value_txt}</div>'
            f'<div class="{cls}">{chg_txt}</div></div>'
        )
    return f'<div class="grid">{"".join(cards)}</div>' if cards else "<p>데이터 없음</p>"


def _volatility_html_kr(vol: dict) -> str:
    def _fmt(v):
        return f"{v:,.1f}" if isinstance(v, (int, float)) else "—"
    adr = vol.get("adr", {})
    atr = vol.get("atr", {})
    flow = vol.get("investor_flow", {})
    rows = (
        f'<div class="card"><h3>ADR</h3><div class="val">KOSPI {_fmt(adr.get("kospi"))} / '
        f'KOSDAQ {_fmt(adr.get("kosdaq"))}</div></div>'
        f'<div class="card"><h3>ATR(14)</h3><div class="val">KOSPI {_fmt(atr.get("kospi"))} / '
        f'KOSDAQ {_fmt(atr.get("kosdaq"))}</div></div>'
    )
    for market_key, market_label in (("kospi", "KOSPI"), ("kosdaq", "KOSDAQ")):
        f_ = flow.get(market_key, {})
        rows += (
            f'<div class="card"><h3>{market_label} 수급</h3>'
            f'<div class="val">외국인 {_fmt(f_.get("foreign_net"))} · '
            f'개인 {_fmt(f_.get("individual_net"))} · '
            f'기관 {_fmt(f_.get("institution_net"))}</div></div>'
        )
    return f'<div class="grid">{rows}</div>'


def _leadership_html_kr(lead: dict) -> str:
    def _list(items: list[dict], name_key: str = "sector") -> str:
        if not items:
            return "<p>—</p>"
        rows = "".join(
            f"<li>{html.escape(str(it.get(name_key) or it.get('name', '')))} "
            f"{_fmt_pct(it.get('chg_pct'))}</li>"
            for it in items
        )
        return f"<ul>{rows}</ul>"

    return (
        '<div class="grid" style="grid-template-columns:1fr 1fr;">'
        f'<div class="card"><h3>업종 상승 TOP3</h3>{_list(lead.get("sectors_up", []))}</div>'
        f'<div class="card"><h3>업종 하락 TOP3</h3>{_list(lead.get("sectors_down", []))}</div>'
        f'<div class="card"><h3>종목 상승 TOP3</h3>{_list(lead.get("stocks_up", []), "name")}</div>'
        f'<div class="card"><h3>종목 하락 TOP3</h3>{_list(lead.get("stocks_down", []), "name")}</div>'
        "</div>"
    )


def _flow_table_html_kr(rows: list[dict]) -> str:
    if not rows:
        return "<p>데이터 없음</p>"
    body = "".join(
        f'<tr><td>{html.escape(str(r.get("price_driver","")))}</td>'
        f'<td>{html.escape(str(r.get("supply_driver","")))}</td>'
        f'<td>{html.escape(str(r.get("trigger","")))}</td>'
        f'<td>{html.escape(str(r.get("durability","")))}</td></tr>'
        for r in rows
    )
    return ("<table><tr><th>가격</th><th>수급</th><th>촉발요인</th><th>지속성</th></tr>"
            f"{body}</table>")


def _policy_cards_html(cards: list[dict]) -> str:
    if not cards:
        return "<p>—</p>"
    blocks = []
    for c in cards:
        blocks.append(
            '<div class="card">'
            f'<h3>{html.escape(str(c.get("title","")))}</h3>'
            f'<p><b>사실상태</b>: {html.escape(str(c.get("fact_state","")))}</p>'
            f'<p><b>향후방향</b>: {html.escape(str(c.get("outlook","")))}</p>'
            f'<p><b>한국시장영향</b>: {html.escape(str(c.get("korea_impact","")))} '
            f'({html.escape(str(c.get("polarity","")))} · 정확도 {html.escape(str(c.get("accuracy","")))})</p>'
            "</div>"
        )
    return f'<div class="grid">{"".join(blocks)}</div>'


def render_html_kr(briefing: dict) -> str:
    """advisor_dashboard_kr.build_briefing_kr() 출력 → PAGE1+PAGE2 HTML 문자열."""
    p1 = briefing.get("page1", {})
    p2 = briefing.get("page2", {})

    key_themes = ", ".join(html.escape(str(t)) for t in p1.get("key_themes", [])) or "—"
    conclusion = "".join(f"<li>{html.escape(str(c))}</li>" for c in p1.get("conclusion", []))
    scenarios_html = _scenarios_html(p1.get("scenarios", []))  # Family A 헬퍼 재사용
    daily_comment = html.escape(str(p1.get("daily_comment", "")))

    us_cards_html = _policy_cards_html(p2.get("policy_cards", {}).get("us", []))
    kr_cards_html = _policy_cards_html(p2.get("policy_cards", {}).get("kr", []))
    korea_links = "".join(f"<li>{html.escape(str(l))}</li>" for l in p2.get("korea_links", [])) or "<li>—</li>"
    checkpoints = "".join(f"<li>{html.escape(str(c))}</li>" for c in p2.get("checkpoints", [])) or "<li>—</li>"
    summary_html = "".join(
        f'<div class="card"><h3>{html.escape(str(s.get("title","")))}</h3>'
        f'<p>{html.escape(str(s.get("fact_state","")))}</p></div>'
        for s in p2.get("summary", [])
    ) or "<p>—</p>"

    page1_body = (
        f'<div class="section-title">KEY THEMES</div><p>{key_themes}</p>'
        f'<div class="section-title">① 오늘의 결론</div><ul>{conclusion}</ul>'
        f'<div class="section-title">② 마감 KPI</div>{_kpi_html_kr(p1.get("kpi", []))}'
        f'<div class="section-title">③ 시장 변동성 지표</div>{_volatility_html_kr(p1.get("volatility", {}))}'
        f'<div class="section-title">④ 업종·종목 리더십</div>{_leadership_html_kr(p1.get("leadership", {}))}'
        f'<div class="section-title">⑤ 가격→수급→촉발요인→지속성</div>{_flow_table_html_kr(p1.get("flow_table", []))}'
        f'<div class="section-title">⑥ 오늘 시나리오</div>{scenarios_html}'
        f'<div class="section-title">⑦ 오늘 하루 코멘트</div><p>{daily_comment}</p>'
    )
    page2_body = (
        f'<div class="section-title">PAGE2 · 핵심요약</div>{summary_html}'
        f'<div class="section-title">정책카드 비교 · 미국</div>{us_cards_html}'
        f'<div class="section-title">정책카드 비교 · 한국</div>{kr_cards_html}'
        f'<div class="section-title">미·한 연결경로</div><ul>{korea_links}</ul>'
        f'<div class="section-title">체크포인트</div><ul>{checkpoints}</ul>'
    )

    return (
        "<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'>"
        f"<title>증시·정책 브리핑 {html.escape(str(briefing.get('generated_at',''))[:10])}</title>"
        f"<style>{_CSS}</style></head><body>"
        '<div class="header"><h1>미국·한국 증시·정책 브리핑</h1>'
        f'<div>생성 시각: {html.escape(str(briefing.get("generated_at","")))}</div></div>'
        f"{page1_body}{page2_body}"
        '<div class="footer">본 자료는 정보 제공 목적이며 투자 권유가 아닙니다.</div>'
        "</body></html>"
    )
