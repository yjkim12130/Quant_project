# -*- coding: utf-8 -*-
"""Quant_lotto — 로또 통계 대시보드 & EV 조합 생성기 (Streamlit, 3탭)."""
import altair as alt
import pandas as pd
import streamlit as st

import lotto_data
import lotto_logic as logic

st.set_page_config(page_title="Quant_lotto", page_icon="🎱", layout="wide")

# 공식 로또 공 색상 (번호 구간별 고정 — 색은 엔티티를 따라간다)
BALL_COLORS = {"1-10": "#FBC400", "11-20": "#69C8F2", "21-30": "#FF7272",
               "31-40": "#AAAAAA", "41-45": "#B0D840"}
HONESTY_LABEL = "참고용 — 예측력 없음 (1~1,236회 백테스트로 검증됨)"
EV_LABEL = "당첨 확률과 무관 — 당첨됐을 때의 분할 리스크만 반영"


def ball_group(n: int) -> str:
    if n <= 10:
        return "1-10"
    if n <= 20:
        return "11-20"
    if n <= 30:
        return "21-30"
    if n <= 40:
        return "31-40"
    return "41-45"


def render_balls(nums) -> str:
    """번호를 공식 공 색상 칩으로 렌더링하는 HTML."""
    spans = []
    for n in sorted(nums):
        c = BALL_COLORS[ball_group(n)]
        spans.append(
            f'<span style="display:inline-flex;align-items:center;justify-content:center;'
            f'width:2.2em;height:2.2em;border-radius:50%;background:{c};color:#222;'
            f'font-weight:700;margin-right:.35em;">{n}</span>')
    return "".join(spans)


@st.cache_data(ttl=3600, show_spinner="당첨 이력 데이터를 불러오는 중...")
def get_history():
    df, warning = lotto_data.load_history()
    return df, warning


try:
    df, warning = get_history()
except lotto_data.DataUnavailableError as e:
    st.error(str(e))
    st.stop()

latest = df.iloc[-1]
st.title("🎱 Quant_lotto")
st.caption("당첨 확률은 못 올린다 — 대신 당첨됐을 때 혼자 받을 확률을 올린다.")
if warning:
    st.warning(warning)

top = st.columns(4)
top[0].metric("최신 회차", f"{int(latest['round']):,}회")
top[1].metric("추첨일", str(latest["date"]))
top[2].metric("최신 당첨번호", " ".join(str(int(latest[c])) for c in logic.NUM_COLS))
if top[3].button("데이터 새로고침"):
    get_history.clear()
    st.rerun()

tab_stats, tab_gen, tab_check, tab_pred = st.tabs(
    ["📊 통계 대시보드", "🎯 EV 조합 생성기", "🔍 내 조합 검증기", "🔮 예측 실험실"])

# ---------- 탭① 통계 대시보드 ----------
with tab_stats:
    st.info(f"**{HONESTY_LABEL}** — 아래 빈도 차이는 전부 자연 노이즈 범위입니다.")

    st.subheader("랜덤성 모니터")
    p = logic.chi2_pvalue(df)
    ov = logic.prev_overlap_stats(df)
    m = st.columns(3)
    m[0].metric("카이제곱 p값 (균등성)", f"{p:.3f}",
                help="0.05보다 크면 완전 랜덤과 통계적으로 구분 불가")
    m[1].metric("직전 회차 겹침 (실측 평균)", f"{ov['mean']:.3f}개",
                f"이론값 {ov['theoretical']:.2f}개", delta_color="off")
    m[2].metric("직전 번호가 다시 나온 회차", f"{ov['pct_ge1']:.1f}%",
                help="'연속으로 안 나온다'는 속설과 달리 5회 중 3회는 재출현")
    verdict = "완전 랜덤과 구분 불가 (정상)" if p > 0.05 else "이례적 편차 감지"
    st.caption(f"현재까지 {int(latest['round']):,}회 기준 판정: **{verdict}**")

    st.subheader("번호별 출현 빈도")
    scope = st.radio("범위", ["전체 회차", "최근 52회", "최근 104회"], horizontal=True)
    last_n = {"전체 회차": None, "최근 52회": 52, "최근 104회": 104}[scope]
    ft = logic.freq_table(df, last_n)
    ft["구간"] = ft["번호"].map(ball_group)
    bars = alt.Chart(ft).mark_bar(size=12, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
        x=alt.X("번호:O", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("출현횟수:Q"),
        color=alt.Color("구간:N",
                        scale=alt.Scale(domain=list(BALL_COLORS), range=list(BALL_COLORS.values())),
                        legend=alt.Legend(title="공 색상 구간", orient="top")),
        tooltip=["번호", "출현횟수", alt.Tooltip("기대값:Q", format=".1f")],
    )
    rule = alt.Chart(ft).mark_rule(strokeDash=[5, 4], color="#666").encode(y="기대값:Q")
    st.altair_chart((bars + rule).properties(height=320), use_container_width=True)
    st.caption(f"점선 = 기대 출현횟수 {ft['기대값'].iloc[0]:.1f}회 (완전 균등일 때)")

    st.subheader("핫 / 콜드 top 10")
    n_recent = st.slider("최근 N회 기준", 20, 200, 52, step=4)
    rt = logic.freq_table(df, n_recent).sort_values("출현횟수", ascending=False)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**🔥 핫넘버 (많이 나옴)**")
        st.dataframe(rt.head(10)[["번호", "출현횟수"]], hide_index=True, use_container_width=True)
    with c2:
        st.markdown("**🧊 콜드넘버 (적게 나옴)**")
        st.dataframe(rt.tail(10)[["번호", "출현횟수"]].iloc[::-1], hide_index=True, use_container_width=True)

# ---------- 탭② EV 조합 생성기 ----------
with tab_gen:
    st.info(f"**{EV_LABEL}** — 조합은 순수 균등 랜덤으로 생성되며, "
            "인기 패턴(생일조합 등)을 피한 조합만 통과시킵니다.")
    g1, g2 = st.columns(2)
    n_games = g1.slider("생성할 게임 수", 1, 5, 5)
    min_score = g2.slider("최소 독식 점수", 0, 100, 60, step=10,
                          help="높일수록 '남들과 안 겹치는' 조합만 통과 (당첨 확률은 동일)")
    if st.button("조합 생성", type="primary"):
        combos = logic.generate_combos(n_games, min_score)
        if len(combos) < n_games:
            st.warning(f"점수 {min_score} 이상 조합을 {len(combos)}개만 찾았습니다. 기준을 낮춰보세요.")
        for i, (nums, score, reasons) in enumerate(combos, 1):
            row = st.columns([3, 1])
            row[0].markdown(f"**{i}게임** &nbsp; {render_balls(nums)}", unsafe_allow_html=True)
            row[1].metric("독식 점수", f"{score}/100")
            with st.expander("점수 근거"):
                for r in reasons:
                    st.markdown(f"- {r}")
        st.caption("어떤 조합이든 1등 확률은 똑같이 1/8,145,060 입니다.")

# ---------- 탭③ 내 조합 검증기 ----------
with tab_check:
    st.markdown("내 번호 6개가 **과거 전 회차에 나왔다면 몇 등이었을지**, "
                "그리고 **남들과 얼마나 겹치는 조합인지** 확인합니다.")
    picks = st.multiselect("번호 6개 선택", list(range(1, 46)), max_selections=6)
    if st.button("검증", type="primary", disabled=len(picks) != 6):
        err = logic.validate_picks(picks)
        if err:
            st.error(err)
        else:
            st.markdown(render_balls(picks), unsafe_allow_html=True)
            score, reasons = logic.ev_score(picks)
            bt = logic.backtest_combo(picks, df)
            k = st.columns(3)
            k[0].metric("독식 점수", f"{score}/100", help=EV_LABEL)
            k[1].metric("과거 당첨 이력 (1~3등)", f"{bt[1] + bt[2] + bt[3]}회")
            k[2].metric("1등 확률", "1 / 8,145,060", "모든 조합과 동일", delta_color="off")
            st.markdown("**과거 전 회차 시뮬레이션** — 이 조합을 매회 샀다면:")
            hist = pd.DataFrame({
                "등수": [f"{r}등" for r in range(1, 6)],
                "횟수": [bt[r] for r in range(1, 6)],
            })
            st.dataframe(hist, hide_index=True)
            spent = len(df) * 1000
            st.caption(f"총 {len(df):,}회 × 1,000원 = {spent:,}원 지출 기준. "
                       "과거에 많이 맞았어도 미래 확률은 변하지 않습니다.")
            with st.expander("독식 점수 근거"):
                for r in reasons:
                    st.markdown(f"- {r}")

# ---------- 탭④ 예측 실험실 ----------
with tab_pred:
    next_round = int(latest["round"]) + 1
    st.warning(
        "**검증 결과, 아래 알고리즘 전부 랜덤과 통계적으로 구분되지 않았습니다.** "
        "train/test 분리 백테스트에서 validation 1위(콜드)조차 test에서는 랜덤 이하(0.760 < 0.800)였습니다. "
        "재미로만 보세요 — 어떤 조합이든 1등 확률은 똑같이 1/8,145,060 입니다.")
    st.subheader(f"{next_round}회 알고리즘별 예측")
    for algo in logic.predict_algorithms(df):
        row = st.columns([2, 4, 2])
        row[0].markdown(f"**{algo['name']}**")
        row[1].markdown(render_balls(algo["picks"]), unsafe_allow_html=True)
        perf = f"검증 성적 {algo['val']:.3f}개/회"
        if algo["test"] is not None:
            perf += f" → test {algo['test']:.3f}개"
        row[2].caption(f"{perf}\n\n{algo['note']}")
    st.caption("성적은 experiments/predict_lab.py 백테스트 기준 (랜덤 기대 0.800개/회). "
               "상세 리포트: experiments\\results_20260814.txt")
