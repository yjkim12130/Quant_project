"""저평가 아파트 검색기 — Streamlit 메인 (Phase 3: Tab0 가이드 / Tab1 스크리너 / Tab2 단지 상세)

실행: streamlit run app.py   (포트 8502, .streamlit/config.toml)
데이터: data/realestate.db (ingest/fetch_trades.py로 적재) — 앱은 DB만 읽는다.
알고리즘: docs/algo_spec_v1.md / scoring/engine.py

원칙: 예산 등 개인 재무정보는 세션 입력만 받고 어디에도 저장하지 않는다.
"""
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scoring.engine import Params, build_scored_panel, combine_scores  # noqa: E402
from scoring.regime import compute_regime, load_raw_series, REGIME_RV_THRESHOLD, HARD_RATE_HIKE  # noqa: E402
from backtest.event_study import (  # noqa: E402
    run_backtest, BUY_COST_PCT, SELL_COST_PCT, ENTRY_LAG, FACTORS)

ACCENT = "#00d084"  # YJ-Quant 팔레트
RED = "#ff5c5c"

ROOT = Path(__file__).resolve().parent

st.set_page_config(page_title="YJ-RealEstate", page_icon="🏠", layout="wide",
                   initial_sidebar_state="expanded")


def _ai_box(text: str):
    """규칙기반 해석 카드 (YJalgo 컨벤션)"""
    st.markdown(
        f"""<div style="border-left: 4px solid {ACCENT}; background: rgba(0,208,132,0.08);
        padding: 0.8em 1em; border-radius: 0 8px 8px 0; margin: 0.5em 0;">
        🤖 <b>해석</b><br>{text}</div>""",
        unsafe_allow_html=True)


PYEONG = 3.3058  # ㎡ → 평


# ---------------------------------------------------------------- 데이터 (캐시)

@st.cache_data(ttl=3600, show_spinner="시세 패널·팩터 계산 중 (최초 1회, 1~2분)...")
def load_panel():
    params = Params()
    df, totals = build_scored_panel(params)
    return df, totals, params


# ---------------------------------------------------------------- 사이드바

@st.cache_data(ttl=3600, show_spinner="레짐 산출 중...")
def load_regime():
    r = compute_regime()
    return r.dropna(subset=["score"])


df, totals, params = load_panel()
latest_month = df["month"].max()

st.sidebar.title("🏠 YJ-RealEstate")
st.sidebar.caption(f"데이터 기준: {latest_month} · 단지키 {df['ckey'].nunique():,}개")

# ── 매수 타이밍 레짐 (regime_spec_v1 §5) — 장기 검증 통과 (2003~, p<0.0001)
regime_df = load_regime()
cur = regime_df.iloc[-1]
cur_regime = cur["regime"]
st.sidebar.markdown(
    f"""<div style="border: 1px solid {ACCENT}; border-radius: 8px; padding: 0.6em 0.9em; margin: 0.3em 0;">
    <b>매수 타이밍 레짐</b> <span style="float:right">{regime_df.index[-1]}</span><br>
    <span style="font-size: 1.5em">{cur_regime}</span>
    <span style="color:#888"> (score {cur['score']:+.2f})</span></div>""",
    unsafe_allow_html=True)
st.sidebar.caption("검증: 2003~ 사이클 3개, 🟢월 이후 12M 지수수익 +6.2% (97% 양) vs 🔴 -2.9%, p<0.0001")

regime_link = st.sidebar.toggle(
    "레짐 연동 매수 임계", value=False,
    help=f"레짐별 rv_z 임계 자동조절: 🟢 {REGIME_RV_THRESHOLD['🟢 매수적기']}σ / "
         f"🟡 {REGIME_RV_THRESHOLD['🟡 중립']}σ / 🔴 {REGIME_RV_THRESHOLD['🔴 보류']}σ — 보류 국면일수록 극단적 저평가만 🟢 표시")
params_eff = replace(params, rv_buy_z=REGIME_RV_THRESHOLD.get(cur_regime, params.rv_buy_z)) \
    if regime_link else params

regions = sorted(df["region_name"].dropna().unique())
sel_regions = st.sidebar.multiselect("지역 (시군구)", regions, default=[])
sel_bands = st.sidebar.multiselect("전용면적 밴드(㎡)", ["~60", "60~85", "85~"], default=[])

use_jr_floor = st.sidebar.toggle("전세가율 하한 필터", value=False,
                                 help="실사용 가치가 가격을 받치는 단지만 (하방 방어)")
jr_floor = st.sidebar.slider("전세가율 하한 (%)", 30, 80, 50, disabled=not use_jr_floor)

st.sidebar.divider()
st.sidebar.markdown("**💰 예산 (세션 한정, 저장 안 됨)**")
budget = st.sidebar.number_input("총 예산 상한 (억원, 0=미적용)", min_value=0.0, value=0.0, step=0.5,
                                 help="최근 6개월 실거래 중위 총액 기준 필터. 입력값은 어디에도 저장되지 않습니다.")

# ---------------------------------------------------------------- 탭

tab0, tabT, tabA, tabS, tabTr, tab1, tab2, tab3 = st.tabs(
    ["📖 가이드", "⏱️ 매수 타이밍", "🌐 자산 비교", "🏗️ 공급", "🚇 교통",
     "🔍 저평가 스크리너", "🏢 단지 상세", "🧪 백테스트"])

# ---------------------------------------------------------------- Tab0 가이드

with tab0:
    try:
        st.markdown(f"""
## 이 도구는 무엇인가

YJalgo(주식 백테스팅)의 **동일자산군 상대평가** 사고방식을 부동산에 옮긴 개인용 저평가 아파트 검색기입니다.
서울 남부 11개구 + 경기 남부 핵심 11개시의 5년치 국토부 실거래가(매매+전세)를 기반으로 합니다.

## 핵심 아이디어 — "평소 위상 대비 이탈"

같은 그룹(동 × 면적대 × 연식대) 안에서 이 단지가 **평소 유지하던 가격 위상**보다 유난히
처져 있으면 저평가로 봅니다. "원래 그룹보다 20% 비싸던 단지가 지금 8%만 비싸다"가 신호이고,
"원래 싼 단지가 지금도 싸다"는 신호가 아닙니다 (브랜드·입지 프리미엄 오판 방지).

- **rv_z (괴리율)**: 단지가격/그룹중위가 비율의 자기 역사 대비 z-score. **낮을수록(음수) 저평가**
- **dd (조정폭)**: 전고점 대비 하락률 · **mom12**: 12개월 모멘텀 — 조정은 충분한데(dd↓) 하락이
  가속 중은 아닐 때(mom12 하한 위) '매수구간'
- **전세가율 z**: 매매가는 눌렸는데 전세(실사용 수요)가 안 빠졌으면 바닥 신호

## 판정 이모지

| 표시 | 의미 |
|---|---|
| 🟢 저평가 | rv_z < {params.rv_buy_z}σ |
| 🟡 중립 | 평소 위상 범위 안 |
| 🔴 고평가 | rv_z > +{-params.rv_buy_z}σ |
| ⚪ 데이터부족 | 관측 월수 부족 (신뢰 불가) |
| ⚠️ 플래그 | 최근 1년 해제거래 비율 {params.cancel_flag_pct:.0%} 초과 — 시세 신뢰 주의 |

## 주의사항

- 실거래 신고는 계약 후 30일 이내라 **최근 1개월 데이터는 미완성**입니다.
- 거래가 드문 단지는 3개월 롤링+이월로 메꾸며(`carried`), 6개월 넘게 거래 없으면 제외됩니다.
- 이 도구는 **후보 발굴용**입니다. 매수 결정 전 현장 확인(임장)과 호가 확인은 필수입니다.
- 백테스트 검증(Tab3, 개발 예정) 전까지 시그널의 역사적 적중률은 미검증 상태입니다.
""")
    except Exception as e:  # noqa: BLE001
        st.error(f"가이드 탭 오류: {e}")

# ---------------------------------------------------------------- TabT 매수 타이밍


@st.cache_data(ttl=3600, show_spinner="변수 원시값 로딩...")
def load_raw():
    return load_raw_series()


with tabT:
    try:
        raw = load_raw()
        last_raw = raw.dropna(subset=["base_rate"]).iloc[-1]
        streak = (regime_df["regime"][::-1] == cur_regime).cummin().sum()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("현재 판정", cur_regime, help="변수 z 합산 점수를 과거 분위(q30/q70)로 3분할")
        c2.metric("레짐 점수", f"{cur['score']:+.2f}", help="+ = 매수 우호. 유효 변수 z 평균")
        c3.metric("연속 개월", f"{streak}개월")
        c4.metric("하드룰(금리 인상 가속)", "발동 🔴" if cur["hard_rule"] else "미발동",
                  help=f"기준금리 12개월 변화 > +{HARD_RATE_HIKE:.1f}%p면 다른 변수 무관 강제 보류")

        st.markdown("##### 변수별 현황 — 무엇이 이 판정을 만들었나")
        VAR_CARDS = [
            ("rate_dir", "기준금리 방향", f"{last_raw['base_rate']:.2f}%",
             f"12개월 {last_raw['rate_chg12']:+.2f}%p", "인하 국면일수록 매수 우호"),
            ("idx_mom", "수도권 지수 모멘텀", f"12개월 {last_raw['idx_mom12']:+.1f}%",
             f"전고점 대비 {last_raw['idx_dd']:+.1f}%", "지수 상승 전환 = 매수 우호"),
            ("supply_dem", "매매수급지수", f"{last_raw.get('supply_dem', float('nan')):.1f}",
             "기준 100 (수요>공급이면 ↑)", "수요 우위일수록 매수 우호"),
            ("sentiment", "소비심리지수(서울·경기)", f"{last_raw.get('sentiment', float('nan')):.1f}",
             "기준 100", "심리 개선일수록 매수 우호 — 검증 상관 1위(0.59)"),
            ("jr_dir", "시장 전세가율(30개 지역)", f"{last_raw.get('market_jr', float('nan')):.1f}%",
             f"12개월 {last_raw.get('jr_chg12', float('nan')):+.1f}%p", "전세가율 상승 = 실수요가 받치는 바닥"),
            ("vol_ratio", "매매/전세 거래량 비율", f"{last_raw.get('vol_ratio', float('nan')):.2f}",
             "매매 회복 시 ↑", "매수 수요 전환 신호"),
        ]
        cols = st.columns(3)
        for i, (zcol, name, val, sub, hyp) in enumerate(VAR_CARDS):
            z = cur.get(zcol)
            arrow = "🟢" if pd.notna(z) and z > 0.3 else ("🔴" if pd.notna(z) and z < -0.3 else "🟡")
            with cols[i % 3]:
                st.metric(f"{arrow} {name}", val, sub, delta_color="off",
                          help=f"{hyp} · 현재 z={z:+.2f}" if pd.notna(z) else hyp)
        m2z = cur.get("m2_yoy")
        st.caption(f"ℹ️ M2 증가율 {last_raw['m2_yoy']:+.1f}% (z={m2z:+.2f}) — 장기 검증에서 예측력 무효(역방향)로 "
                   "판정돼 **점수에서 제외**, 모니터링만 합니다.")

        # 레짐 히스토리 차트: 점수 + 신호등 + 지수
        hist = regime_df.join(raw[["idx"]], how="left")
        color_map = {"🟢 매수적기": ACCENT, "🟡 중립": "#f0b429", "🔴 보류": RED, "⚪ 판정불가": "#666"}
        fig = go.Figure()
        for rg, color in color_map.items():
            seg = hist[hist["regime"] == rg]
            if len(seg):
                fig.add_trace(go.Scatter(x=seg.index.to_timestamp(), y=seg["score"], mode="markers",
                                         name=rg, marker=dict(color=color, size=5)))
        fig.add_trace(go.Scatter(x=hist.index.to_timestamp(), y=hist["idx"], name="수도권 아파트지수(우축)",
                                 yaxis="y2", line=dict(color="#888", width=1.5)))
        fig.add_hline(y=0, line_color="#555")
        fig.update_layout(title="레짐 점수 히스토리 vs 수도권 아파트 매매가격지수 (2003~)",
                          height=420, margin=dict(t=40, b=0),
                          yaxis=dict(title="레짐 점수"),
                          yaxis2=dict(title="지수", overlaying="y", side="right", showgrid=False),
                          legend=dict(orientation="h", y=1.12))
        st.plotly_chart(fig, use_container_width=True)

        # 변수 원시값 차트
        sel_var = st.selectbox("변수 원시값 시계열 보기", [
            "base_rate 기준금리(%)", "m2_yoy M2 증가율(%)", "idx_mom12 지수 12개월 모멘텀(%)",
            "supply_dem 매매수급지수", "sentiment 소비심리지수", "market_jr 시장 전세가율(%)",
            "vol_ratio 매매/전세 거래량 비율"])
        vcol = sel_var.split()[0]
        if vcol in raw.columns:
            s = raw[vcol].dropna()
            fig2 = go.Figure(go.Scatter(x=s.index.to_timestamp(), y=s, line=dict(color=ACCENT)))
            fig2.update_layout(height=280, margin=dict(t=10, b=0))
            st.plotly_chart(fig2, use_container_width=True)

        # 규칙기반 해석
        zs = {n: cur.get(zc) for zc, n, *_ in VAR_CARDS if pd.notna(cur.get(zc))}
        pos = sorted(((n, z) for n, z in zs.items() if z > 0.3), key=lambda x: -x[1])
        neg = sorted(((n, z) for n, z in zs.items() if z < -0.3), key=lambda x: x[1])
        msg = f"현재 <b>{cur_regime}</b> (점수 {cur['score']:+.2f}, {streak}개월 연속). "
        if pos:
            msg += "우호 요인: " + ", ".join(f"{n}({z:+.1f}σ)" for n, z in pos[:3]) + ". "
        if neg:
            msg += "부담 요인: " + ", ".join(f"{n}({z:+.1f}σ)" for n, z in neg[:3]) + ". "
        if cur["hard_rule"]:
            msg += "<b>⚠️ 금리 인상 가속 하드룰 발동 — 강제 보류 상태.</b> "
        msg += ("이 판정은 2003년 이후 3개 사이클 검증을 통과한 규칙입니다 "
                "(🟢월 이후 12개월 지수수익 평균 +6.2%·양의 비율 97% vs 🔴월 -2.9%·47%, p<0.0001). "
                "단, 시장 레벨 판단이므로 개별 단지 선택은 스크리너와 결합하세요.")
        _ai_box(msg)

        with st.expander("📖 지표 설명·방법론"):
            st.markdown(f"""
- **레짐 점수**: 변수별 "과거 10년 대비 얼마나 이례적인가"(z-score)를 동일가중 평균. 발표 지연 반영
  (M2 2개월, 부동산원 지표 1개월 시차) — 각 시점에 실제로 알 수 있었던 정보만 사용
- **신호등**: 점수를 과거 분포의 상/하위 30% 분위로 3분할 (미래 정보 미사용 expanding 방식)
- **하드룰**: 기준금리 12개월 변화 > +{HARD_RATE_HIKE:.1f}%p (인상 가속기) → 다른 변수 무관 강제 🔴
- **검증**: 2003~2026 수도권, 🟢 vs 🔴 이후 지수수익 격차 +9.1%p(12M)/+9.6%p(24M), 순열검정 p<0.0001.
  변수별 예측력: 심리 0.59 > 수급 0.52 > 금리방향 0.38 > 지수모멘텀 0.36 (M2는 무효 → 점수 제외)
- **한계**: 수도권 단일 지수 기준(지역별 차이 미반영), 정책 이벤트(대출 규제 등)는 아직 미반영(v2)
""")
    except Exception as e:  # noqa: BLE001
        st.error(f"매수 타이밍 탭 오류: {e}")
        st.exception(e)

# ---------------------------------------------------------------- TabA 자산 비교

ASSET_LABELS = {
    "reb_apt_index": "🏠 수도권 아파트", "asset_kospi": "🇰🇷 코스피", "asset_nasdaq": "🇺🇸 나스닥",
    "asset_gold": "🥇 금", "asset_btc": "₿ 비트코인", "ecos_m2": "💧 M2 통화량",
}


@st.cache_data(ttl=3600, show_spinner="자산 시계열 로딩...")
def load_assets():
    import sqlite3
    from scoring.engine import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    m = pd.read_sql_query("SELECT series, ym, value FROM macro_series", conn)
    conn.close()
    wide = m.pivot(index="ym", columns="series", values="value")
    wide.index = pd.PeriodIndex(pd.to_datetime(wide.index, format="%Y%m"), freq="M")
    return wide.sort_index()


@st.cache_data(ttl=3600, show_spinner=False)
def load_transit_times():
    import sqlite3
    from scoring.engine import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    try:
        t = pd.read_sql_query(
            "SELECT ckey, dest, minutes, nearest_station FROM complex_transit_time", conn)
    except Exception:
        t = pd.DataFrame(columns=["ckey", "dest", "minutes", "nearest_station"])
    conn.close()
    return t


@st.cache_data(ttl=3600, show_spinner=False)
def load_complex_coords():
    import sqlite3
    from scoring.engine import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    try:
        c = pd.read_sql_query("SELECT ckey, region_code, lat, lon FROM complex_coords", conn)
    except Exception:
        c = pd.DataFrame(columns=["ckey", "region_code", "lat", "lon"])
    conn.close()
    return c


@st.cache_data(ttl=3600, show_spinner=False)
def load_region_map():
    """region_code -> region_name. tabTr·tabS가 공유(Task 9에서 재사용)."""
    cfg = yaml.safe_load(open(ROOT / "config" / "regions.yaml", encoding="utf-8"))
    return {r["code"]: r["name"] for g in cfg.values() for r in g}


TRANSIT_DEST_ORDER = ["강남", "종로", "여의도", "판교", "동탄"]

with tabA:
    try:
        assets = load_assets()
        st.markdown("##### 자산군 상대 성과 — 부동산도 여러 자산 중 하나다")

        rng = st.radio("기간", ["1년", "3년", "5년", "10년", "전체"], index=2, horizontal=True)
        n_months = {"1년": 12, "3년": 36, "5년": 60, "10년": 120, "전체": 10**4}[rng]
        logy = st.toggle("로그 스케일", value=(rng in ("10년", "전체")))

        cols_avail = [c for c in ASSET_LABELS if c in assets.columns]
        sub = assets[cols_avail].dropna(how="all").iloc[-n_months:]
        rebased = pd.DataFrame(index=sub.index)
        for c in cols_avail:
            s = sub[c].dropna()
            if len(s) >= 2:
                rebased[c] = sub[c] / s.iloc[0] * 100

        fig = go.Figure()
        palette = {"reb_apt_index": ACCENT, "asset_kospi": "#4c9aff", "asset_nasdaq": "#b37feb",
                   "asset_gold": "#f0b429", "asset_btc": "#ff9f43", "ecos_m2": "#8899aa"}
        for c in rebased.columns:
            fig.add_trace(go.Scatter(x=rebased.index.to_timestamp(), y=rebased[c],
                                     name=ASSET_LABELS[c],
                                     line=dict(color=palette.get(c), width=2.5 if c == "reb_apt_index" else 1.5,
                                               dash=None if c != "ecos_m2" else "dot")))
        if "ecos_base_rate" in assets.columns:
            br = assets["ecos_base_rate"].iloc[-n_months:].dropna()
            fig.add_trace(go.Scatter(x=br.index.to_timestamp(), y=br, name="기준금리(%, 우축)",
                                     yaxis="y2", line=dict(color="#888", width=1, dash="dash")))
        fig.update_layout(
            title=f"시작점=100 기준 상대 성과 ({rng})", height=460, margin=dict(t=40, b=0),
            yaxis=dict(title="지수 (시작=100)", type="log" if logy else "linear"),
            yaxis2=dict(title="기준금리 %", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", y=1.14))
        st.plotly_chart(fig, use_container_width=True)

        # 기간별 수익률 표
        rows = []
        for c in cols_avail:
            s = assets[c].dropna()
            row = {"자산": ASSET_LABELS[c]}
            for label, n in [("1년", 12), ("3년", 36), ("5년", 60), ("10년", 120)]:
                if len(s) > n:
                    r = s.iloc[-1] / s.iloc[-n - 1] - 1
                    row[label] = f"{r * 100:+.1f}%"
                    row[f"{label}(연)"] = f"{((1 + r) ** (12 / n) - 1) * 100:+.1f}%" if n > 12 else None
            rows.append(row)
        table = pd.DataFrame(rows)[["자산", "1년", "3년", "3년(연)", "5년", "5년(연)", "10년", "10년(연)"]]
        st.dataframe(table, hide_index=True, use_container_width=True)
        st.caption("연 = 연평균 복리(CAGR). 수도권 아파트지수는 최근월 공표분(약 1~2개월 지연)까지 반영")

        # 해석
        mom = {}
        for c in cols_avail:
            s = assets[c].dropna()
            if len(s) > 12:
                mom[ASSET_LABELS[c]] = (s.iloc[-1] / s.iloc[-13] - 1) * 100
        rank = sorted(mom.items(), key=lambda x: -x[1])
        apt_pos = [i for i, (n, _) in enumerate(rank) if "아파트" in n]
        apt_rank = apt_pos[0] + 1 if apt_pos else None
        msg = "최근 12개월 모멘텀 순위: " + " > ".join(f"{n} {v:+.1f}%" for n, v in rank) + ". "
        if apt_rank:
            msg += f"수도권 아파트는 {len(rank)}개 자산 중 <b>{apt_rank}위</b>. "
        msg += ("주의: 아파트지수는 실거래 기반 평활 지수라 변동성이 구조적으로 낮게 보입니다 — "
                "수익률 비교는 유효하지만 변동성(위험) 비교는 과소평가되므로, 레버리지(대출)까지 "
                "고려한 실질 위험은 표시보다 큽니다.")
        _ai_box(msg)

        with st.expander("📖 읽는 법"):
            st.markdown("""
- **시작=100 차트**: 선택 기간 시작점을 100으로 정규화한 상대 성과. 장기 구간은 로그 스케일 권장
  (복리 효과 왜곡 방지)
- **M2(점선)**: 통화량 — "모든 자산의 분모". M2보다 덜 오른 자산은 실질 구매력 기준 제자리
- **기준금리(우축 점선)**: 할인율 — 금리 인하기에 자산 전반이 우호적이었는지 확인
- **아파트지수의 특성**: 월간·평활·후행(공표 1~2개월 지연). 단기 비교보다 3년+ 추세 비교에 적합
- 데이터: 부동산원(수도권 아파트), yfinance(코스피·나스닥·금·비트코인, 월말 종가), 한국은행 ECOS(M2·기준금리)
""")
    except Exception as e:  # noqa: BLE001
        st.error(f"자산 비교 탭 오류: {e}")
        st.exception(e)

# ---------------------------------------------------------------- TabS 공급


@st.cache_data(ttl=3600, show_spinner=False)
def load_supply():
    import sqlite3
    from scoring.engine import DB_PATH
    from scoring.market_context import load_supply_by_region_year
    conn = sqlite3.connect(DB_PATH)
    out = load_supply_by_region_year(conn)
    conn.close()
    return out


with tabS:
    try:
        st.markdown("##### 향후 입주 예정 물량 — 분양(자동) + 정비사업(수동 큐레이션)")
        supply = load_supply()
        region_map = load_region_map()  # Task 6에서 정의(tabTr와 공유)
        supply["region_name"] = supply["region_code"].map(region_map)

        sel_region = st.selectbox("지역 (시군구)", sorted(region_map.values()), index=None,
                                  placeholder="지역을 선택하세요", key="supply_region")
        if sel_region:
            sub = supply[supply["region_name"] == sel_region].sort_values("year")
            fig = go.Figure()
            fig.add_trace(go.Bar(x=sub["year"], y=sub["presale_units"], name="분양(자동)",
                                 marker_color=ACCENT))
            fig.add_trace(go.Bar(x=sub["year"], y=sub["redevelopment_units"], name="정비사업(수동)",
                                 marker_color="#f0b429"))
            fig.update_layout(barmode="stack", title=f"{sel_region} 연도별 입주 예정 물량",
                              height=380, margin=dict(t=40, b=0), yaxis_title="세대수")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(sub[["year", "presale_units", "redevelopment_units"]],
                        hide_index=True, use_container_width=True)
        st.caption("정비사업은 1천 세대 이상 대단지만 수동 등록됨(config/manual_catalysts.yaml) — "
                  "누락된 사업이 있을 수 있음.")
    except Exception as e:  # noqa: BLE001
        st.error(f"공급 탭 오류: {e}")
        st.exception(e)

# ---------------------------------------------------------------- TabTr 교통


with tabTr:
    try:
        st.markdown("##### 업무지구별 소요시간 — 역 기반 근사 (오차 ±5~10분)")
        transit = load_transit_times()
        coords = load_complex_coords()
        merged = transit.merge(
            coords[["ckey", "region_code"]], on="ckey", how="left")
        region_map = load_region_map()
        merged["region_name"] = merged["region_code"].map(region_map)

        sel_region = st.selectbox("지역 (시군구)", sorted(region_map.values()), index=None,
                                  placeholder="지역을 선택하세요", key="transit_region")
        if sel_region:
            sub = merged[merged["region_name"] == sel_region]
            agg = (sub.groupby("dest")["minutes"].median()
                      .reindex(TRANSIT_DEST_ORDER).reset_index())
            fig = go.Figure(go.Bar(x=agg["dest"], y=agg["minutes"], marker_color=ACCENT,
                                   text=agg["minutes"].round(0), textposition="outside"))
            fig.update_layout(title=f"{sel_region} 대표 소요시간(중위값, 분)", height=380,
                              margin=dict(t=40, b=0), yaxis_title="분")
            st.plotly_chart(fig, use_container_width=True)
            st.caption(f"표본 {sub['ckey'].nunique()}개 단지 기준 중위값")
            from scoring.market_context import load_planned_transit
            planned = load_planned_transit()
            if not planned.empty:
                st.markdown("###### 🚧 예정 노선 (착공/준공, 현재 소요시간 계산에는 미반영)")
                for row in planned.itertuples():
                    years_left = row.expected_open_year - pd.Timestamp.now().year
                    badge = "🔜 3년 이내" if years_left <= 3 else "🕐 3년 이상"
                    st.markdown(f"- **{row.line_name}** ({row.stage}) — {', '.join(row.stations)} · "
                               f"예정 {row.expected_open_year}년 {badge}")
    except Exception as e:  # noqa: BLE001
        st.error(f"교통 탭 오류: {e}")
        st.exception(e)


# ---------------------------------------------------------------- Tab1 스크리너

with tab1:
    try:
        snap = combine_scores(df, params_eff, month=latest_month)
        snap = snap.merge(totals, on=["ckey", "area_band"], how="left")
        if regime_link:
            st.caption(f"레짐 연동 on: 현재 {cur_regime} → 🟢 판정 임계 rv_z < {params_eff.rv_buy_z}σ")

        # 필터 적용
        if sel_regions:
            snap = snap[snap["region_name"].isin(sel_regions)]
        if sel_bands:
            snap = snap[snap["area_band"].astype(str).isin(sel_bands)]
        if use_jr_floor:
            snap = snap[snap["jeonse_ratio"].fillna(0) >= jr_floor / 100]
        if budget > 0:
            snap = snap[snap["recent_total"].notna() & (snap["recent_total"] <= budget * 10000)]

        n_green = (snap["signal"] == "🟢 저평가").sum()
        n_buyzone = snap["buy_zone"].fillna(False).sum()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("대상 (단지×면적밴드)", f"{len(snap):,}")
        c2.metric("🟢 저평가", f"{n_green:,}")
        c3.metric("매수구간 (DD+모멘텀)", f"{int(n_buyzone):,}")
        c4.metric("⚠️ 해제 플래그", f"{int(snap['cancel_flag'].sum()):,}")

        view = snap.copy()
        view["평당가(만)"] = (view["price"] * PYEONG).round(0)
        view["총액(억)"] = (view["recent_total"] / 10000).round(1)
        view["연식"] = (latest_month.year - view["build_year"]).astype("Int64")
        view["전세가율"] = (view["jeonse_ratio"] * 100).round(1)
        view["DD%"] = (view["dd"] * 100).round(1)
        view["12M%"] = (view["mom12"] * 100).round(1)
        view["rv_z"] = view["rv_z"].round(2)
        view["플래그"] = np.where(view["cancel_flag"], "⚠️", "")
        view["매수구간"] = np.where(view["buy_zone"].fillna(False), "✅", "")

        show_cols = ["signal", "complex_name", "region_name", "dong_name", "area_band", "연식",
                     "평당가(만)", "총액(억)", "전세가율", "rv_z", "DD%", "12M%", "매수구간", "플래그"]
        st.dataframe(
            view[show_cols].rename(columns={
                "signal": "판정", "complex_name": "단지", "region_name": "지역",
                "dong_name": "동", "area_band": "면적"}),
            use_container_width=True, height=560, hide_index=True)

        # 규칙기반 해석 — buy_zone은 백테스트에서 역효과 확인(regime_spec_v1 §6)으로
        # 추천 조건에서 중립화: 표시(✅)만 하고 후보 선정에는 미사용
        top = view[(view["signal"] == "🟢 저평가") & ~view["cancel_flag"]].head(5)
        if len(top):
            names = ", ".join(f"{r.complex_name}({r.dong_name} {r.area_band})"
                              for r in top.itertuples())
            _ai_box(f"괴리율 저평가 + 플래그 없음 조건의 상위 후보: <b>{names}</b>. "
                    f"괴리율은 '평소 위상 대비'라 그룹 재편(재건축 진척 등) 이벤트가 있었는지 확인 필요. "
                    f"매수구간 ✅는 참고 표시만 — 백테스트에서 이 조건이 수익을 낮춰 추천에 미반영 (매수 타이밍은 레짐 모델 개발 중).")
        else:
            _ai_box("현재 필터 조건에서 후보(저평가+무플래그) 없음. 필터를 완화해보세요.")

        with st.expander("📖 지표 설명"):
            st.markdown("""
- **판정**: rv_z 기준 🟢/🟡/🔴, 관측 부족 시 ⚪
- **평당가(만)**: 3개월 롤링 중위 ㎡당가 × 3.3058
- **총액(억)**: 최근 6개월 실거래 중위 총액 (예산 필터 기준값)
- **전세가율**: 동일 면적밴드 전세 중위가 ÷ 매매 중위가
- **rv_z**: 그룹 대비 비율의 자기 역사 z-score (낮을수록 저평가)
- **DD% / 12M%**: 전고점 대비 조정폭 / 12개월 모멘텀
- **매수구간 ✅**: DD < 임계 AND 모멘텀 > 하한 (조정 충분 + 하락 비가속)
- **플래그 ⚠️**: 최근 1년 해제거래 비율 초과 — 자전거래 의심, 시세 신뢰 주의
""")
    except Exception as e:  # noqa: BLE001
        st.error(f"스크리너 탭 오류: {e}")
        st.exception(e)

# ---------------------------------------------------------------- Tab2 단지 상세

with tab2:
    try:
        pool = df if not sel_regions else df[df["region_name"].isin(sel_regions)]
        complexes = (pool[["ckey", "complex_name", "region_name", "dong_name"]]
                     .drop_duplicates("ckey"))
        complexes["label"] = (complexes["region_name"] + " " + complexes["dong_name"]
                              + " · " + complexes["complex_name"])
        sel_label = st.selectbox("단지 선택", sorted(complexes["label"]),
                                 index=None, placeholder="지역 필터 후 단지를 선택하세요")
        if sel_label:
            ckey = complexes.set_index("label").loc[sel_label, "ckey"]
            cx = df[df["ckey"] == ckey].sort_values("month")
            bands = cx["area_band"].astype(str).unique().tolist()
            sel_band = st.radio("면적밴드", bands, horizontal=True)
            cxb = cx[cx["area_band"].astype(str) == sel_band].copy()
            cxb["date"] = cxb["month"].dt.to_timestamp()

            last = cxb.iloc[-1]
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("평당가", f"{last['price'] * PYEONG:,.0f}만원")
            m2.metric("rv_z", f"{last['rv_z']:.2f}σ" if pd.notna(last["rv_z"]) else "—")
            m3.metric("전고점 대비", f"{last['dd'] * 100:+.1f}%" if pd.notna(last["dd"]) else "—")
            m4.metric("12M 모멘텀", f"{last['mom12'] * 100:+.1f}%" if pd.notna(last["mom12"]) else "—")

            transit = load_transit_times()
            cx_transit = transit[transit["ckey"] == ckey]
            if not cx_transit.empty:
                st.markdown("###### 🚇 업무지구별 소요시간 (역 기반 근사)")
                cols = st.columns(len(TRANSIT_DEST_ORDER))
                for col, dest in zip(cols, TRANSIT_DEST_ORDER):
                    row = cx_transit[cx_transit["dest"] == dest]
                    if row.empty:
                        col.metric(dest, "—")
                    else:
                        col.metric(dest, f"{row.iloc[0]['minutes']:.0f}분")
                st.caption(f"최근접역: {cx_transit.iloc[0]['nearest_station']} · "
                          "오차 ±5~10분 수준 근사치(순위 비교용)")

            # 차트1: 평당가 vs 그룹
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=cxb["date"], y=cxb["price"] * PYEONG,
                                     name="단지 평당가", line=dict(color=ACCENT, width=2)))
            fig.add_trace(go.Scatter(x=cxb["date"], y=cxb["group_price"] * PYEONG,
                                     name="그룹 중위 평당가", line=dict(color="#888", dash="dot")))
            carried_pts = cxb[cxb["carried"]]
            if len(carried_pts):
                fig.add_trace(go.Scatter(x=carried_pts["date"], y=carried_pts["price"] * PYEONG,
                                         mode="markers", name="이월(거래없음)",
                                         marker=dict(color="#666", size=5, symbol="circle-open")))
            fig.update_layout(title="평당가 추이 (만원/평)", height=380, margin=dict(t=40, b=0),
                              legend=dict(orientation="h", y=1.12))
            st.plotly_chart(fig, use_container_width=True)

            # 차트2: rv_z 추이
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=cxb["date"], y=cxb["rv_z"], name="rv_z",
                                      line=dict(color=ACCENT)))
            fig2.add_hline(y=params.rv_buy_z, line_dash="dash", line_color=ACCENT,
                           annotation_text=f"매수 임계 {params.rv_buy_z}σ")
            fig2.add_hline(y=-params.rv_buy_z, line_dash="dash", line_color=RED)
            fig2.add_hline(y=0, line_color="#555")
            fig2.update_layout(title="그룹 대비 괴리율 z-score 추이", height=320, margin=dict(t=40, b=0))
            st.plotly_chart(fig2, use_container_width=True)

            # 해석
            g_n = int(last["group_n"]) if pd.notna(last["group_n"]) else 0
            fallback = "|*|" in str(last.get("group_key", ""))
            grp_desc = f"시군구 폴백 그룹(표본 {g_n}개)" if fallback else f"동 단위 그룹(표본 {g_n}개)"
            if pd.notna(last["rv_z"]) and last["rv_z"] < params.rv_buy_z:
                msg = (f"현재 {grp_desc} 대비 평소 위상보다 <b>{abs(last['rv_z']):.1f}σ 낮게</b> 거래 중 — 저평가 구간. "
                       + ("전고점 대비 조정도 충분하고 하락 가속이 아니라 매수구간 조건 충족."
                          if bool(last.get("buy_zone")) else
                          "다만 모멘텀/조정폭 조건은 미충족 — 하락 진행 중일 수 있어 관망 병행."))
            elif pd.notna(last["rv_z"]):
                msg = f"{grp_desc} 대비 평소 위상 범위 안({last['rv_z']:+.1f}σ) — 뚜렷한 저평가 아님."
            else:
                msg = "관측 월수가 부족해 괴리율 판정 불가 (⚪)."
            if bool(last.get("cancel_flag")):
                msg += " <b>⚠️ 최근 1년 해제거래 비율이 높아 시세 신뢰에 주의.</b>"
            _ai_box(msg)
    except Exception as e:  # noqa: BLE001
        st.error(f"단지 상세 탭 오류: {e}")
        st.exception(e)

# ---------------------------------------------------------------- Tab3 백테스트


@st.cache_data(ttl=3600, show_spinner="백테스트 실행 중 (이벤트 집계·IC·순열검정, 1~2분)...")
def cached_backtest():
    # df는 load_panel 캐시 재사용 — 여기서 다시 빌드하지 않음
    _df, _, _params = load_panel()
    res = run_backtest(params=_params, n_perm=500, df=_df)
    res.pop("df")  # 캐시 직렬화 부담 제거 (39만 행 패널은 세션에 불필요)
    return res


with tab3:
    try:
        st.markdown("""#### 시그널 검증 (event study)
과거 매 시점 시그널 → **+1개월 진입** → N개월 보유 → 실제 수익률.
**초과수익 = 단지 수익률 − 소속 그룹 수익률** (시장 전체 상승 착시 제거).""")

        if st.button("백테스트 실행", type="primary") or "bt" in st.session_state:
            if "bt" not in st.session_state:
                st.session_state["bt"] = cached_backtest()
            res = st.session_state["bt"]

            h = st.radio("보유기간 (개월)", res["horizons"], index=1, horizontal=True)

            # ── 코호트 성과
            rows = []
            for name, s in res["cohorts"][h].items():
                if s:
                    rows.append({
                        "코호트": name, "이벤트 수": f"{s['n_events']:,}",
                        "절대수익 평균": f"{s['abs_mean'] * 100:+.1f}%",
                        "초과수익 평균": f"{s['excess_mean'] * 100:+.1f}%",
                        "초과수익 중위": f"{s['excess_median'] * 100:+.1f}%",
                        "승률(초과>0)": f"{s['hit_rate'] * 100:.1f}%"})
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            pv = res["pvalue"][h]
            pv_txt = ", ".join(f"{k}: p={v:.3f}" for k, v in pv.items() if pd.notna(v))
            st.caption(f"순열검정(무작위 단지 선택 대비 우위): {pv_txt} — p<0.05면 우연으로 보기 어려움")

            col_l, col_r = st.columns(2)

            # ── 팩터 IC
            with col_l:
                st.markdown("**팩터 예측력 (IC)** — 팩터값과 이후 초과수익의 월별 순위상관")
                ic = res["ic"][h].copy()
                label = {"rv_z": "괴리율 rv_z (낮을수록 좋다 가설)",
                         "jr_z": "전세가율 jr_z (높을수록 좋다 가설)",
                         "dd": "조정폭 dd (깊을수록 좋다 가설)",
                         "mom12": "모멘텀 mom12 (가설: 양수 유지)"}
                ic["팩터"] = ic["factor"].map(label)
                hyp_neg = {"rv_z", "dd"}  # 음의 IC가 가설 방향인 팩터
                ic["가설 방향 일치"] = [
                    "✅" if (r.factor in hyp_neg) == (r.mean_IC < 0) else "❌ (역방향)"
                    for r in ic.itertuples()]
                ic["유의성"] = np.where(ic["IC_tstat"].abs() > 2, "유의", "약함")
                st.dataframe(ic[["팩터", "mean_IC", "IC_tstat", "가설 방향 일치", "유의성"]]
                             .round(3), hide_index=True, use_container_width=True)

            # ── 임계 스윕
            with col_r:
                st.markdown("**rv_z 임계 스윕** — 임계를 깊게 잡을수록 수익↑ 후보수↓")
                sw = res["sweep"][h]
                sw_num = sw[sw["rv_z<"] != "전체(기준)"].copy()
                fig = go.Figure()
                fig.add_trace(go.Bar(x=sw_num["rv_z<"].astype(str), y=sw_num["excess_mean"] * 100,
                                     name="초과수익 평균(%)", marker_color=ACCENT))
                fig.add_trace(go.Scatter(x=sw_num["rv_z<"].astype(str), y=sw_num["hit_rate"] * 100,
                                         name="승률(%)", yaxis="y2", line=dict(color="#f0b429")))
                fig.update_layout(height=300, margin=dict(t=10, b=0),
                                  yaxis=dict(title="초과수익 %"),
                                  yaxis2=dict(title="승률 %", overlaying="y", side="right"),
                                  legend=dict(orientation="h", y=1.15))
                st.plotly_chart(fig, use_container_width=True)

            # ── 해석
            s_rv = res["cohorts"][h].get(f"rv_z<{params.rv_buy_z}", {})
            s_full = res["cohorts"][h].get("rv_z+매수구간", {})
            mom_row = res["ic"][h].query("factor == 'mom12'")
            mom_flip = len(mom_row) and mom_row.iloc[0]["mean_IC"] < 0
            msg = (f"rv_z<{params.rv_buy_z} 시그널은 {h}개월 보유 시 그룹 대비 평균 "
                   f"<b>{s_rv.get('excess_mean', 0) * 100:+.1f}%p</b>, 승률 {s_rv.get('hit_rate', 0) * 100:.0f}% "
                   f"(p={pv.get(f'rv_z<{params.rv_buy_z}', float('nan')):.3f}) — 저평가 괴리율은 유효한 변수. ")
            if s_full and s_rv and s_full.get("excess_mean", 0) < s_rv.get("excess_mean", 0):
                msg += ("한편 모멘텀 가드를 더한 '매수구간' 조건이 오히려 초과수익을 낮춤")
                if mom_flip:
                    msg += (" — IC도 가설과 역방향(이 표본에선 떨어질 때 사는 쪽이 유리했음). "
                            "단, 5년 표본은 사이클 1개뿐이라 이 결론은 레짐 모델(문제 1)에서 재검증 필요.")
            _ai_box(msg)

            with st.expander("📖 방법론·한계"):
                st.markdown(f"""
- **진입 시차**: 시그널 +{ENTRY_LAG}개월 (실거래 신고 지연 반영)
- **벤치마크**: 소속 그룹 중위가의 동일 기간 수익률 — 초과수익은 "같은 그룹에서 이 단지를 고른 효과"만 측정
- **비용**: 절대수익률에 매수 {BUY_COST_PCT:.1%} + 매도 {SELL_COST_PCT:.1%} 차감 근사 가능 (표는 비용 전).
  양도세는 보유기간·1주택 비과세 여부에 따라 별도 — 미반영
- **한계 1**: 표본 5년 = 상승→급락→회복 사이클 **1개**. 모멘텀 관련 결론은 특히 사이클 의존적
- **한계 2**: 이월(carried) 가격이 수익률을 평활화 — 실제 체결 가능가와 차이 존재
- **한계 3**: 시그널이 겹치는 단지-월 이벤트는 독립이 아님 (순열검정이 월 구조는 보존)
""")
        else:
            st.info("버튼을 누르면 5년 전체 이벤트에 대해 코호트 성과·팩터 IC·임계 스윕·순열검정을 계산합니다 (1~2분).")
    except Exception as e:  # noqa: BLE001
        st.error(f"백테스트 탭 오류: {e}")
        st.exception(e)
