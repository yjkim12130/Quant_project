"""
advisor_app.py — 자문역 인사이트 통합 분석 (P3, 독립 앱)
═══════════════════════════════════════════════════════════════════════
🧮 종목 분석 탭 — 종목 하나를 입력하면 한 화면에:
  ① 정량 데이터        — yfinance LIVE (시세·시총·52주·매출)
  ② 정량 신호          — 개별종목 간이 레짐/RSI/200일선 이격 (자체 계산)
  ③ 오재승 룰 매칭     — 정량 신호 → OJS-* 트레이딩 룰 자동 힌트
  ④ 빈규리 룰북 평가   — 13개 BKR-* 룰 (코드 자동 + 정성 수동 체크) → 점수
  ⑤ 종목카드 JSON      — advisor_data.py 원본 출력

📰 시황 브리핑 탭 — 온디맨드로 10-section daily dashboard(advisor_dashboard.py
오케스트레이션) + downloadable HTML report를 생성한다.

★ v9.3(app.py)과 완전 독립. 안정화·품질 확보 후 v9.4 트랙으로 merge 예정.
실행:  streamlit run advisor_app.py
"""
from __future__ import annotations
import json
from datetime import date

import streamlit as st
import plotly.graph_objects as go

import advisor_data as ad
import advisor_llm as al
import advisor_dashboard as adb
import advisor_report as ar

st.set_page_config(page_title="자문역 인사이트 · 종목 분석 · 시황 브리핑",
                   page_icon="🧮", layout="wide")

# ── 테마 (샘플 리포트와 동일 팔레트) ──────────────────────────────────
st.markdown("""
<style>
  :root { --green:#00d084; --blue:#2196f3; --orange:#ff9800; --red:#ff4444;
          --purple:#ab47bc; --muted:#8899aa; }
  .card { background:#1a1d26; border:1px solid #2e3650; border-radius:12px;
          padding:16px 20px; margin-bottom:14px; }
  .card-green { border-color:var(--green); }
  .card-blue  { border-color:var(--blue); }
  .badge { display:inline-block; font-size:12px; font-weight:700; padding:3px 11px;
           border-radius:20px; margin-left:6px; }
  .b-live { background:rgba(0,208,132,.18); color:var(--green); border:1px solid var(--green); }
  .b-pend { background:rgba(255,152,0,.15); color:var(--orange); border:1px solid var(--orange); }
  .b-reg  { background:rgba(33,150,243,.15); color:var(--blue); border:1px solid var(--blue); }
  .rule-if { color:var(--muted); font-size:13px; }
  .rule-then { color:#d6dde8; font-size:13px; }
  .ev { color:var(--muted); font-size:12px; font-style:italic; }
  h3.sec { border-bottom:1px solid #2e3650; padding-bottom:6px; margin:6px 0 10px; }
</style>
""", unsafe_allow_html=True)

_W = {"high": 3, "mid": 2, "low": 1}
_CAT_ORDER = ["해자", "진위판별", "사업구조", "성장", "재무", "리스크", "스타일"]
_CAT_COLOR = {"해자": "purple", "진위판별": "red", "사업구조": "blue",
              "성장": "green", "재무": "orange", "리스크": "red", "스타일": "muted"}


# ── 캐시된 데이터 로딩 ────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def load_card(name: str, us: bool) -> dict:
    card = ad.build_stock_card(name, us=us)
    return ad.apply_rulebook(card)


@st.cache_data(ttl=600, show_spinner=False)
def load_history(ticker: str):
    return ad.get_price_history(ticker)


@st.cache_data(ttl=600, show_spinner=False)
def load_signals(ticker: str) -> dict:
    return ad.compute_quant_signals(load_history(ticker))


@st.cache_data(ttl=600, show_spinner=False)
def load_ojs(ticker: str, market_cap, revenue_ttm, per) -> dict:
    quant = {"market_cap": market_cap, "revenue_ttm": revenue_ttm, "per": per}
    return ad.compute_ojs_signals(load_history(ticker), quant)


@st.cache_data(ttl=1800, show_spinner=False)
def load_dashboard() -> dict:
    return adb.build_dashboard()


def price_chart(close, ojs: dict):
    """종가 + 200일선 + 오재승 그물망 12 MA 리본(정/역배열 색)."""
    fig = go.Figure()
    periods = ojs.get("periods") if isinstance(ojs, dict) else None
    periods = periods or list(range(20, 76, 5))
    arr = ojs.get("net_arrangement", "") if isinstance(ojs, dict) else ""
    ribbon = ("rgba(255,68,68,.22)" if "정배열" in arr
              else "rgba(33,150,243,.22)" if "역배열" in arr
              else "rgba(136,153,170,.20)")
    for p in periods:                                   # 그물망 리본
        ma = close.rolling(p).mean()
        fig.add_trace(go.Scatter(x=ma.index, y=ma, mode="lines",
                      line=dict(width=1, color=ribbon),
                      showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=close.index, y=close, mode="lines",
                  line=dict(width=1.6, color="#d6dde8"), name="종가"))
    if len(close) >= 200:                               # 200일선
        ma200 = close.rolling(200).mean()
        fig.add_trace(go.Scatter(x=ma200.index, y=ma200, mode="lines",
                      line=dict(width=1.4, color="#ff9800", dash="dot"),
                      name="200일선"))
    fig.update_layout(template="plotly_dark", height=340,
                      margin=dict(l=8, r=8, t=8, b=8),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#161922",
                      legend=dict(orientation="h", y=1.04, x=0,
                                  bgcolor="rgba(0,0,0,0)"))
    fig.update_xaxes(gridcolor="#2e3650")
    fig.update_yaxes(gridcolor="#2e3650")
    return fig


def _krw(v):
    if not isinstance(v, (int, float)):
        return "—"
    if v >= 1e12:
        return f"{v/1e12:.2f}조"
    if v >= 1e8:
        return f"{v/1e8:,.0f}억"
    return f"{v:,.0f}"


def ojs_hint(sig: dict) -> list[str]:
    """정량 신호 → 오재승 룰 자동 힌트."""
    out = []
    reg = sig.get("regime", "")
    rsi = sig.get("rsi14")
    dev = sig.get("ma200_dev_pct")
    if reg in ("정배열 눌림", "약세 과매도") and rsi is not None and rsi < 40:
        out.append("OJS-MA-01 · 200일선 위 눌림 + 과매도 → 분할 매수 후보 자리")
    if reg.startswith("강세"):
        out.append("OJS-MACD-01 · 추세 구간 → 신고가 돌파 시 선취매 관점")
    if dev is not None and dev < -5:
        out.append("OJS-CASH-01 · 이격 음(-) 확대 → 만수르 분할(현금 분할 매집) 구간")
    if not out:
        out.append("뚜렷한 트레이딩 트리거 없음 — 관망 / 유니버스 편입 단계")
    return out


# ════════════════════════════════════════════════════════════════════
# 사이드바
# ════════════════════════════════════════════════════════════════════
st.sidebar.title("🧮 자문역 인사이트")
st.sidebar.caption("빈규리(펀더멘탈) × 오재승(타이밍) · 독립 앱")
name = st.sidebar.text_input("종목명 / 티커", value="와이제이링크",
                             help="한국: 한글 종목명(예: 와이제이링크) · 미국: 티커(예: AAPL)")
us = st.sidebar.checkbox("미국 종목 (yfinance 티커 직접 입력)", value=False)
run_clicked = st.sidebar.button("분석 실행", type="primary", use_container_width=True)

dart_on = ad.get_dart_key() is not None
st.sidebar.markdown("---")
st.sidebar.markdown(
    f"**DART 재무 연동**: {'🟢 ON' if dart_on else '🟠 키 대기'}")
if not dart_on:
    st.sidebar.caption("opendart.fss.or.kr 무료키 발급 후 "
                       "`DART_API_KEY` 환경변수 또는 `.dart_api_key` 파일 설정 시 "
                       "영업이익률·부채비율 자동 채움")

llm_ok, llm_why = al.llm_available()
st.sidebar.markdown(f"**Claude 정성 평가**: {'🟢 ON' if llm_ok else '🟠 미연결'}")
if not llm_ok:
    st.sidebar.caption(f"{llm_why} — 설정 시 11개 정성 룰을 Claude가 자동 판정")

st.sidebar.markdown("---")
st.sidebar.caption("빈규리 증류 종목 예시")
st.sidebar.caption("와이제이링크 · 헥토파이낸셜 · 켄코아에어로스페이스 · 엔젤로보틱스")

# ════════════════════════════════════════════════════════════════════
# 메인
# ════════════════════════════════════════════════════════════════════
# ⚠️ `with tab2:` 블록은 반드시 `with tab1:` 보다 먼저 실행되어야 한다.
# tab1 블록은 입력이 없으면 st.stop()으로 스크립트 실행을 완전히 중단시키므로
# (d4a28c7), tab1이 먼저 오면 "브리핑 생성" 버튼 클릭이 tab2 렌더링에 도달하지
# 못하고 조용히 삼켜진다. 이 순서를 다시 뒤집지 말 것 — 필요하면 st.stop() 의존을
# 먼저 제거해야 한다.
tab1, tab2 = st.tabs(["🧮 종목 분석", "📰 시황 브리핑"])

with tab2:
    st.caption("일간 시황 대시보드 · 오재승(매크로·타이밍) × 빈규리(펀더멘탈) · 온디맨드 생성")
    if st.button("📰 브리핑 생성", type="primary"):
        with st.spinner("시황 데이터 수집 + 대시보드 조립 중…"):
            result = load_dashboard()
            st.session_state["dashboard"] = result

            # 실패 상태가 30분 TTL 캐시에 그대로 굳어버리면 재클릭해도 같은
            # 실패가 반복 반환된다 — RSS 장애/yfinance rate-limit 등 "깨끗하지
            # 않은" 결과일 때만 캐시를 비워 다음 클릭이 재시도되게 한다.
            # NO_FOCUS_STOCK(빈규리 후보군이 오늘 뉴스에 없음)은 정상적인
            # 결정론적 결과이지 실패가 아니므로 캐시를 비우지 않는다.
            ojs_clean = result.get("todays_action", {}).get("_status") == "ok"
            bkr_clean = result.get("bkr", {}).get("_status") in ("ok", "NO_FOCUS_STOCK")
            dash_clean = result.get("tech_dashboard", {}).get("_status") != "NO_YFINANCE"
            hl_clean = result.get("news_status") == "ok"
            if not (ojs_clean and bkr_clean and dash_clean and hl_clean):
                load_dashboard.clear()

    dboard = st.session_state.get("dashboard")
    if not dboard:
        st.info("위 버튼을 눌러 오늘의 시황 대시보드를 생성하세요.")
    else:
        st.caption(f"생성 시각: {dboard['generated_at']}")

        try:
            report_html = ar.render_html(dboard)
            ar.save_report(report_html, as_of=date.fromisoformat(dboard["generated_at"][:10]))
            st.download_button(
                "📥 리포트 다운로드 (HTML)",
                data=report_html,
                file_name=f"{dboard['generated_at'][:10]}_briefing.html",
                mime="text/html",
            )
        except Exception as e:
            # HTML 리포트 생성/저장 실패가 탭 전체를 무너뜨리지 않도록 격리
            # (advisor_data.py/advisor_news.py와 동일한 컨벤션) — 아래 10개
            # 섹션은 report_html 성공 여부와 무관하게 그대로 렌더링된다.
            st.warning(f"HTML 리포트 생성 실패: {e}")

        st.markdown("### ① Today's Summary")
        for m in dboard["summary"]:
            st.markdown(f"- {m['text']}")

        st.markdown("### ② 오늘 반드시 알아야 할 3가지")
        must_know = dboard["must_know"]
        if must_know:
            mk_cols = st.columns(len(must_know))
            for i, m in enumerate(must_know):
                mk_cols[i].metric(f"0{i+1}. {m['label']}", f"{m['chg_pct']:+.2f}%")

        st.markdown("### ③ Tech Dashboard")
        dash = dboard["tech_dashboard"]
        if dash.get("_status") == "NO_YFINANCE":
            st.warning("yfinance 미설치로 시황 데이터를 가져올 수 없습니다.")
        else:
            _cols = st.columns(len(adb.TECH_LABELS))
            for i, (k, label) in enumerate(adb.TECH_LABELS.items()):
                v = dash.get(k, {}) if isinstance(dash.get(k), dict) else {}
                price = v.get("price")
                chg = v.get("chg_pct")
                _cols[i].metric(
                    label,
                    f"{price:,.2f}" if isinstance(price, (int, float)) else "—",
                    delta=f"{chg}%" if chg is not None else None,
                )

        st.markdown("### ④ Today's Action")
        action = dboard["todays_action"]
        if action.get("_status") == "ok":
            st.markdown(action["commentary"])
            st.success(f"💡 {action['action']}")
            with st.expander("근거 신호"):
                st.json(action.get("signals", {}))
        else:
            st.warning(f"Today's Action 생성 실패 [{action.get('_status')}]: {action.get('_msg','')}")

        st.markdown("### ⑤ TOP NEWS")
        if not dboard["top_news"]:
            if dboard.get("news_status") not in (None, "ok"):
                st.warning(dboard.get("news_msg") or "뉴스 소스 조회에 실패했습니다.")
            else:
                st.info("오늘 선별된 헤드라인이 없습니다.")
        else:
            for item in dboard["top_news"]:
                st.markdown(f"**[{item['source']}]** [{item['title']}]({item['link']})")

        st.markdown("### ⑥ Global → Korea Impact Flow")
        flow = dboard["impact_flow"]
        if not flow:
            st.info("오늘은 뚜렷한 드라이버가 없습니다(임계값 미달).")
        else:
            flow_cols = st.columns(len(flow))
            for i, step in enumerate(flow):
                flow_cols[i].markdown(f"**{step['step']}**\n\n{step['label']}")

        st.markdown("### ⑦ 오늘 시나리오")
        sc_cols = st.columns(3)
        for i, sc in enumerate(dboard["scenarios"]):
            with sc_cols[i]:
                st.markdown(f"**{sc['label']}**" + (" ⭐ 가장 유력" if sc["likely"] else ""))
                st.caption(sc["text"])

        st.markdown("### ⑧ 오늘·이번주 일정")
        if not dboard["calendar"]:
            st.info("등록된 일정이 없습니다.")
        else:
            st.table(dboard["calendar"])

        st.markdown("### ⑨ Fact / Impact")
        if not dboard["fact_impact"]:
            st.info("오늘은 뚜렷한 팩트/임팩트가 없습니다.")
        else:
            st.table(dboard["fact_impact"])

        st.markdown("### ⑩ 수혜 가능 카테고리 · 관찰기업 TOP10")
        t1, t2 = st.columns(2)
        with t1:
            st.markdown("**🇺🇸 미국 TOP5**")
            for i, item in enumerate(dboard["top10"].get("us_top5", [])):
                st.markdown(f"{i+1}. **{item.get('category', '')}** — {item.get('company', '')}")
        with t2:
            st.markdown("**🇰🇷 한국 TOP5**")
            for i, item in enumerate(dboard["top10"].get("kr_top5", [])):
                st.markdown(f"{i+1}. **{item.get('category', '')}** — {item.get('company', '')}")

        st.markdown("### 🟣 빈규리 해설 — 펀더멘탈")
        bkr = dboard["bkr"]
        if bkr.get("_status") == "ok":
            st.markdown(f"**{bkr['focus_stock']}**")
            st.markdown(bkr["commentary"])
            st.caption(bkr["disclaimer"])
        elif bkr.get("_status") == "NO_FOCUS_STOCK":
            st.info(bkr.get("_msg", "오늘은 해당되는 종목이 없습니다."))
        else:
            st.warning(f"빈규리 해설 생성 실패 [{bkr.get('_status')}]: {bkr.get('_msg','')}")

with tab1:
    if not (run_clicked or name):
        st.info("좌측에서 종목을 입력하고 **분석 실행**을 눌러주세요.")
        st.stop()

    with st.spinner(f"'{name}' 데이터 수집 중…"):
        card = load_card(name, us)

    if card.get("_error"):
        st.error(f"❌ {card['_error']}")
        st.info("한국 종목은 **정확한 한글 종목명**(예: 유한양행, 에스티팜)을, "
                "미국 종목은 좌측 체크 후 **티커**(예: AAPL)를 입력하세요.")
        st.stop()

    q = card.get("quant", {})

    # yfinance 빈 응답 가드 — 조용한 null 대신 명확한 경고 + 재시도
    if q.get("_status") in ("NO_DATA", "NO_YFINANCE") or q.get("price") is None:
        st.error(f"⚠️ '{card['name']}' ({card.get('ticker','')}) 의 시세를 받지 못했습니다.")
        st.warning(
            "원인은 보통 **yfinance 일시적 rate-limit**(종목을 빠르게 연속 입력하면 발생)이거나 "
            "해당 티커를 yfinance가 커버하지 않는 경우입니다.\n\n"
            "- **20~30초 후 다시 '분석 실행'** 을 눌러보세요 (대개 해결됩니다).\n"
            "- 데이터 레이어는 정상이며, 캐시(10분)에 빈 결과가 남지 않도록 재조회합니다."
        )
        # 빈 결과가 캐시에 굳지 않도록 무효화
        load_card.clear()
        load_signals.clear()
        st.stop()

    tkr_full = q.get("ticker", "")
    sig = load_signals(tkr_full) if tkr_full else {"_status": "NO_TICKER"}
    ojs = (load_ojs(tkr_full, q.get("market_cap"), q.get("revenue_ttm"), q.get("per"))
           if tkr_full else {"_status": "NO_TICKER"})

    # ── 헤더 ──────────────────────────────────────────────────────────────
    regime = sig.get("regime", "—")
    top1, top2 = st.columns([3, 2])
    with top1:
        st.markdown(f"## {card['name']} "
                    f"<span class='badge b-reg'>{card.get('market','')}</span>",
                    unsafe_allow_html=True)
        st.caption(f"{card.get('ticker','')} · {q.get('name','')} · "
                   f"{q.get('sector','')}/{q.get('industry','')} · 분석일 {card.get('as_of','')}")
    with top2:
        st.metric("간이 레짐 (독립 신호)", regime,
                  delta=f"RSI {sig.get('rsi14','—')}", delta_color="off")

    # ── ① 정량 데이터 (yfinance LIVE) ─────────────────────────────────────
    st.markdown("### ① 정량 데이터 <span class='badge b-live'>yfinance LIVE</span>",
                unsafe_allow_html=True)
    c = st.columns(5)
    cur = q.get("currency", "")
    c[0].metric("현재가", f"{q.get('price','—'):,}" if isinstance(q.get('price'), (int, float)) else "—",
                help=cur)
    c[1].metric("시가총액", _krw(q.get("market_cap")))
    c[2].metric("매출 TTM", _krw(q.get("revenue_ttm")))
    pm = q.get("profit_margin")
    c[3].metric("순이익률", f"{pm*100:.1f}%" if isinstance(pm, (int, float)) else "—")
    c[4].metric("52주 밴드",
                f"{q.get('wk52_low','—'):,}~{q.get('wk52_high','—'):,}"
                if isinstance(q.get('wk52_low'), (int, float)) else "—")

    # ── 차트 (종가 + 200일선 + 오재승 그물망 리본) ───────────────────────
    close = load_history(tkr_full) if tkr_full else None
    if close is not None and len(close) >= 30:
        arr = ojs.get("net_arrangement", "—") if isinstance(ojs, dict) else "—"
        st.markdown(f"### 📈 가격 차트 <span class='badge b-reg'>그물망 12 MA · {arr}</span>",
                    unsafe_allow_html=True)
        st.plotly_chart(price_chart(close, ojs), use_container_width=True)

    # ── ② 정량 신호 (간이 레짐) ───────────────────────────────────────────
    st.markdown("### ② 정량 신호 <span class='badge b-reg'>개별종목 자체 계산 · v9.3 미의존</span>",
                unsafe_allow_html=True)
    if sig.get("_status"):
        st.warning(f"신호 계산 불가: {sig['_status']}")
    else:
        s = st.columns(5)
        s[0].metric("200일선 이격", f"{sig.get('ma200_dev_pct','—')}%")
        s[1].metric("RSI(14)", sig.get("rsi14", "—"))
        s[2].metric("52주 위치", f"{sig.get('wk52_pos_pct','—')}%")
        s[3].metric("1개월 수익", f"{sig.get('ret_1m_pct','—')}%")
        s[4].metric("3개월 수익", f"{sig.get('ret_3m_pct','—')}%")

        st.markdown("#### 🔵 오재승 타이밍 — 7룰 자동 매칭 "
                    "<span class='badge b-reg'>가격 데이터 정량</span>",
                    unsafe_allow_html=True)
        for h in ojs_hint(sig):
            st.caption(f"💡 {h}")

        if isinstance(ojs, dict) and not ojs.get("_status"):
            ojs_rb = ad.load_ojs_rulebook()
            rb_by_id = {r["id"]: r for r in ojs_rb["rules"]} if ojs_rb else {}
            rules = ad.evaluate_ojs_rules(ojs)
            active_n = sum(1 for r in rules if r["active"])
            st.caption(f"🟢 활성 신호 {active_n}/{len(rules)}룰 "
                       f"(OJS-MA-01·LINE-01·SEASON-01은 룰북 참조)")
            for r in rules:
                icon = "🟢" if r["active"] else "⚪"
                meta = rb_by_id.get(r["id"], {})
                st.markdown(
                    f"{icon} **{r['id']}** · {r['name']} — {r['note']}")
                if meta.get("then"):
                    st.markdown(
                        f"<div class='ev'>→ {meta['then']}</div>",
                        unsafe_allow_html=True)
        else:
            st.caption("그물망/MACD 신호 계산을 위한 가격 히스토리가 부족합니다.")

    # ── ④ 빈규리 룰북 평가 ────────────────────────────────────────────────
    st.markdown("### ③ 빈규리 펀더멘탈 룰북 평가 "
                "<span class='badge b-live'>코드 자동</span> "
                "<span class='badge b-pend'>정성 수동</span>", unsafe_allow_html=True)

    rb = ad.load_rulebook()
    if not rb:
        st.warning("binkyuri_rulebook.json 을 찾을 수 없습니다.")
    else:
        auto_ids = {m["id"] for m in card.get("rulebook", {}).get("auto_matched", [])}
        rules_by_cat: dict[str, list] = {}
        for r in rb["rules"]:
            rules_by_cat.setdefault(r["category"], []).append(r)

        # ── Claude 정성 평가 트리거 + 캐시(세션) ──────────────────────────
        eval_key = f"llm_eval::{card.get('ticker')}"
        bc1, bc2 = st.columns([1, 2])
        with bc1:
            if st.button("🤖 Claude로 정성 룰 자동 평가", disabled=not llm_ok,
                         use_container_width=True):
                with st.spinner("Claude가 11개 정성 룰 평가 중…"):
                    st.session_state[eval_key] = al.evaluate_qualitative_rules(card, rb, sig)
        with bc2:
            if not llm_ok:
                st.caption(f"🟠 {llm_why}")
            elif eval_key not in st.session_state:
                st.caption("버튼을 누르면 해자·진위판별 등 11개 정성 룰을 Claude가 판정·근거 제시합니다.")

        llm_res = st.session_state.get(eval_key)
        llm_map: dict[str, dict] = {}
        if llm_res:
            if llm_res.get("_status") == "ok":
                llm_map = {e["rule_id"]: e for e in llm_res["evaluations"]}
                u = llm_res.get("usage", {})
                st.caption(f"✅ Claude({llm_res.get('model','')}) 평가 완료 · "
                           f"met={sum(1 for e in llm_map.values() if e['verdict']=='met')}/{len(llm_map)} · "
                           f"토큰 in {u.get('input',0)}(cache {u.get('cache_read',0)})/out {u.get('output',0)}")
            else:
                st.warning(f"평가 실패 [{llm_res.get('_status')}]: {llm_res.get('_msg','')}")

        st.caption("🟢자동=코드 확인 · 🤖Claude=LLM 판정(met 자동 체크) · 그 외=근거 보고 직접 체크. "
                   "체크한 룰의 가중치 합으로 점수 산출.")

        _VICON = {"met": "✅", "not_met": "❌", "unknown": "❔"}
        checked_w = 0
        total_w = 0
        cat_scores: dict[str, tuple] = {}
        for cat in _CAT_ORDER:
            if cat not in rules_by_cat:
                continue
            with st.expander(f"📁 {cat}  ({len(rules_by_cat[cat])}룰)", expanded=(cat in ("해자", "진위판별"))):
                cw = ct = 0
                for r in rules_by_cat[cat]:
                    w = _W.get(r.get("weight", "mid"), 2)
                    total_w += w
                    ct += w
                    is_auto = r["id"] in auto_ids
                    ev = llm_map.get(r["id"])
                    llm_met = bool(ev and ev["verdict"] == "met")
                    default = is_auto or llm_met
                    label = f"**{r['id']}** · {r['name']}  ·  ({r.get('weight','mid')})"
                    if is_auto:
                        label += "  🟢자동"
                    if ev:
                        label += f"  🤖{_VICON.get(ev['verdict'],'')}{ev['verdict']}({ev['confidence']})"
                    # LLM 재평가 시 위젯 기본값을 새로 반영하기 위해 key에 평가 유무 포함
                    ck = f"chk_{r['id']}_{'L' if ev else '0'}"
                    checked = st.checkbox(label, value=default, key=ck)
                    st.markdown(f"<div class='rule-if'>IF: {r['if']}</div>"
                                f"<div class='rule-then'>→ {r['then']}</div>",
                                unsafe_allow_html=True)
                    if ev:
                        st.markdown(f"<div class='ev'>🤖 {ev['reasoning']} "
                                    f"<b>근거:</b> {ev['evidence']}</div>", unsafe_allow_html=True)
                    elif r.get("evidence"):
                        e = r["evidence"][0]
                        st.markdown(f"<div class='ev'>예: [{e['stock']}] {e['quote']}</div>",
                                    unsafe_allow_html=True)
                    if checked:
                        checked_w += w
                        cw += w
                cat_scores[cat] = (cw, ct)

        # 점수 패널
        st.markdown("#### 📊 룰북 점수")
        pct = (checked_w / total_w * 100) if total_w else 0
        st.progress(min(pct / 100, 1.0),
                    text=f"종합 {checked_w}/{total_w} ({pct:.0f}%)")
        pcols = st.columns(len(cat_scores))
        for i, (cat, (cw, ct)) in enumerate(cat_scores.items()):
            pcols[i].metric(cat, f"{cw}/{ct}")

    # ── ⑤ 종목카드 JSON ───────────────────────────────────────────────────
    with st.expander("📦 종목카드 JSON (advisor_data.py 원본 출력 + 신호)"):
        out = dict(card)
        out["signals"] = sig
        out["ojs_signals"] = ojs
        st.code(json.dumps(out, ensure_ascii=False, indent=2), language="json")

    st.markdown("---")
    st.caption("자문역 인사이트 통합 분석 (P3, 독립 앱) · 정량=yfinance LIVE / DART · "
               "정성=빈규리 룰북(BKR-*) · 타이밍=오재승 룰(OJS-*) · "
               "v9.3과 독립 — 안정화 후 v9.4 트랙 merge 예정")
