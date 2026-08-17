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
    if not items:
        return "<p>오늘 선별된 헤드라인이 없습니다.</p>"
    rows = "".join(
        f'<li><b>[{html.escape(it["source"])}]</b> '
        f'<a href="{html.escape(it["link"], quote=True)}">{html.escape(it["title"])}</a></li>'
        for it in items
    )
    return f"<ul>{rows}</ul>"


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
    if not events:
        return "<p>등록된 일정이 없습니다.</p>"
    rows = "".join(
        f'<tr><td>{html.escape(str(e["date"]))}</td><td>{html.escape(str(e["time_kst"]))}</td>'
        f'<td>{html.escape(str(e["event"]))}</td>'
        f'<td>{"★" * int(e.get("importance", 1))}</td><td>{html.escape(str(e["source"]))}</td></tr>'
        for e in events
    )
    return (
        "<table><tr><th>날짜</th><th>시각(KST)</th><th>이벤트</th><th>중요도</th><th>발표처</th></tr>"
        f"{rows}</table>"
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
            f"<li>{i+1}. <b>{html.escape(it['category'])}</b> — {html.escape(it['company'])}</li>"
            for i, it in enumerate(items)
        )
        return f"<ol style='list-style:none;padding-left:0;'>{rows}</ol>"

    return (
        '<div class="grid" style="grid-template-columns:1fr 1fr;">'
        f'<div class="card"><h3>🇺🇸 미국 TOP5</h3>{_col(top10.get("us_top5", []))}</div>'
        f'<div class="card"><h3>🇰🇷 한국 TOP5</h3>{_col(top10.get("kr_top5", []))}</div>'
        "</div>"
    )


def render_html(dashboard: dict) -> str:
    """advisor_dashboard.build_dashboard() 출력 → 독립 실행형 HTML 문자열."""
    sections = [
        ("① Today's Summary", _summary_html(dashboard["summary"])),
        ("② 오늘 반드시 알아야 할 3가지", _must_know_html(dashboard["must_know"])),
        ("③ Tech Dashboard", _tech_dashboard_html(dashboard["tech_dashboard"])),
        ("④ Today's Action", _action_html(dashboard["todays_action"])),
        ("⑤ TOP NEWS", _news_html(dashboard["top_news"])),
        ("⑥ Global → Korea Impact Flow", _flow_html(dashboard["impact_flow"])),
        ("⑦ 오늘 시나리오", _scenarios_html(dashboard["scenarios"])),
        ("⑧ 오늘·이번주 일정", _calendar_html(dashboard["calendar"])),
        ("⑨ Fact / Impact", _fact_impact_html(dashboard["fact_impact"])),
        ("⑩ 수혜 가능 카테고리 · 관찰기업 TOP10", _top10_html(dashboard["top10"])),
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


def save_report(html: str, as_of: Optional[date] = None) -> Path:
    """reports/YYYY-MM-DD_briefing.html로 저장, 저장된 Path 반환."""
    as_of = as_of or date.today()
    out_dir = Path(_HERE) / "reports"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{as_of.isoformat()}_briefing.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
