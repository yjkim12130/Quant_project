# ManageStock/app.py
import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import auth
import categories
import data_io
import market_data
import portfolio
import volatility

st.set_page_config(page_title="ManageStock", layout="wide")
auth.require_password()
st.title("ManageStock — 포트폴리오 대시보드")

NO_HOLDINGS_MESSAGE = "종목 관리 탭에서 보유 종목을 먼저 등록해주세요."

MERGED_COLUMN_CONFIG = {
    "ticker": st.column_config.TextColumn("티커"),
    "name": st.column_config.TextColumn("종목명"),
    "owners": st.column_config.TextColumn("보유자"),
    "category": st.column_config.TextColumn("카테고리"),
    "currency": st.column_config.TextColumn("통화"),
    "quantity": st.column_config.NumberColumn("총수량"),
    "avg_price": st.column_config.NumberColumn("합산 평단가", format="%.2f"),
    "current_price": st.column_config.NumberColumn("현재가", format="%.2f"),
    "value_krw": st.column_config.NumberColumn("평가금액(원)", format="%.0f"),
    "cost_krw": st.column_config.NumberColumn("매입금액(원)", format="%.0f"),
    "pnl_krw": st.column_config.NumberColumn("손익(원)", format="%.0f"),
    "return_pct": st.column_config.NumberColumn("수익률(%)", format="%.2f"),
    "beta": st.column_config.NumberColumn("베타(수동)"),
    "atr_beta": st.column_config.NumberColumn("변동성 베타", format="%.2f"),
}


def load_dashboard_context():
    """대시보드 탭과 합산 보기 탭이 함께 쓰는 보유종목·시세·환율.
    시세/환율 조회는 캐시(TTL 600초)를 타므로 탭이 늘어도 추가 API 호출은 없다.
    보유 종목이 하나도 없으면 None을 돌려준다."""
    holdings_df, _ = data_io.drop_incomplete_holdings(data_io.load_holdings())
    if holdings_df.empty:
        return None
    prices, failed_tickers = market_data.fetch_prices(holdings_df["ticker"].tolist())
    fetched_fx = market_data.fetch_fx_rate()
    last_fx = st.session_state.get("last_fx_rate")
    fx_rate, fx_is_stale = market_data.resolve_fx_rate(fetched_fx, last_fx)
    if fx_rate is not None:
        st.session_state["last_fx_rate"] = fx_rate
    with st.spinner(f"변동성 베타 계산 중 — 일봉 {volatility.ATR_HISTORY_PERIOD} 조회"):
        histories = market_data.fetch_ohlc_history(volatility.tickers_needed(holdings_df["ticker"].tolist()))
    atr_info = volatility.compute_atr_betas(histories)
    return holdings_df, prices, failed_tickers, fx_rate, fx_is_stale, atr_info


context = load_dashboard_context()

tab1, tab2, tab3 = st.tabs(["포트폴리오 대시보드", "합산 보기", "종목 관리"])

with tab1:
    if context is None:
        st.info(NO_HOLDINGS_MESSAGE)
    else:
        holdings_df, prices, failed_tickers, fx_rate, fx_is_stale, atr_info = context

        if failed_tickers:
            st.warning("시세 조회 실패: " + ", ".join(failed_tickers))

        if fx_rate is None:
            st.error("환율 조회 실패 — USD 종목 금액을 계산할 수 없습니다.")
        else:
            if fx_is_stale:
                st.caption(f"⚠️ 환율 조회 실패, 마지막 확인 환율 사용: {fx_rate:,.2f} KRW/USD")
            else:
                st.metric("현재 환율 (USD/KRW)", f"{fx_rate:,.2f}")

            metrics_df = portfolio.compute_holding_metrics(
                holdings_df, prices, fx_rate, volatility.beta_map(atr_info)
            )
            valid_df = metrics_df.dropna(subset=["value_krw"])

            totals = portfolio.compute_totals(valid_df)
            col1, col2, col3 = st.columns(3)
            col1.metric("총평가금액", f"{totals['total_value_krw']:,.0f} 원")
            col2.metric("총손익금", f"{totals['total_pnl_krw']:,.0f} 원")
            col3.metric("총수익률", f"{totals['total_return_pct']:.2f} %")

            category_df = portfolio.aggregate_by_category(valid_df)

            if category_df.empty:
                st.warning("시세를 조회할 수 있는 종목이 없어 차트를 표시할 수 없습니다.")
            else:
                today = datetime.date.today().isoformat()
                snapshot_values = dict(zip(category_df["category"], category_df["value_krw"]))
                snapshot_values["TOTAL"] = totals["total_value_krw"]
                data_io.append_snapshot(today, snapshot_values)

                color_overrides = data_io.load_category_colors()
                color_map = categories.get_category_color_map(
                    category_df["category"].tolist(), overrides=color_overrides
                )

                pie = px.pie(
                    category_df, names="category", values="value_krw",
                    color="category", color_discrete_map=color_map,
                    title="카테고리별 비중",
                )
                pie.update_traces(textinfo="percent+label")
                st.plotly_chart(pie, use_container_width=True)

                bar_colors = [
                    categories.POSITIVE_COLOR if v >= 0 else categories.NEGATIVE_COLOR
                    for v in category_df["return_pct"]
                ]
                bar = go.Figure(go.Bar(
                    x=category_df["return_pct"], y=category_df["category"],
                    orientation="h", marker_color=bar_colors,
                ))
                bar.update_layout(title="카테고리별 수익률 (%)", xaxis_title="수익률 (%)", yaxis_title=None)
                st.plotly_chart(bar, use_container_width=True)

            display_df = metrics_df.copy()
            display_df["시세조회"] = display_df["current_price"].apply(lambda v: "실패" if pd.isna(v) else "정상")
            st.dataframe(
                display_df[[
                    "category", "name", "ticker", "owner", "currency", "quantity", "avg_price",
                    "current_price", "value_krw", "pnl_krw", "return_pct", "beta", "atr_beta", "시세조회",
                ]],
                use_container_width=True,
            )

            history_df = data_io.load_history()
            total_history = history_df[history_df["category"] == "TOTAL"].sort_values("date")
            if len(total_history) < 2:
                st.info("데이터가 쌓이면 자산 추이가 표시됩니다.")
            else:
                trend = go.Figure(go.Scatter(
                    x=total_history["date"], y=total_history["value_krw"],
                    mode="lines+markers",
                    line=dict(color=categories.TREND_COLOR, width=2),
                ))
                trend.update_layout(title="총자산 추이 (KRW)", xaxis_title=None, yaxis_title="평가금액 (원)")
                st.plotly_chart(trend, use_container_width=True)

with tab2:
    if context is None:
        st.info(NO_HOLDINGS_MESSAGE)
    else:
        st.caption(
            "계좌·소유자가 달라 여러 행으로 기록된 같은 종목을 하나로 합쳐 보여줍니다. "
            "합산 평단가는 수량가중평균이며, 같은 티커라도 통화가 다르면 평단가를 합칠 수 없어 행을 나눕니다."
        )
        holdings_df, prices, failed_tickers, fx_rate, fx_is_stale, atr_info = context

        if failed_tickers:
            st.warning("시세 조회 실패: " + ", ".join(failed_tickers))

        if fx_rate is None:
            st.error("환율 조회 실패 — USD 종목 금액을 계산할 수 없습니다.")
        else:
            metrics_df = portfolio.compute_holding_metrics(
                holdings_df, prices, fx_rate, volatility.beta_map(atr_info)
            )
            valid_df = metrics_df.dropna(subset=["value_krw"])
            merged_df = portfolio.merge_by_ticker(valid_df)

            if merged_df.empty:
                st.warning("시세를 조회할 수 있는 종목이 없어 합산 표를 표시할 수 없습니다.")
            else:
                totals = portfolio.compute_totals(valid_df)
                col1, col2, col3 = st.columns(3)
                col1.metric("합산 종목 수", f"{len(merged_df)} 종목")
                col2.metric("총평가금액", f"{totals['total_value_krw']:,.0f} 원")
                col3.metric("총손익금", f"{totals['total_pnl_krw']:,.0f} 원")

                if not atr_info:
                    st.warning(
                        f"변동성 베타를 계산할 수 없습니다 — 기준 종목 {volatility.ATR_BENCHMARK}의 "
                        "일봉을 가져오지 못했습니다."
                    )
                else:
                    st.caption(
                        f"변동성 베타: {volatility.ATR_BENCHMARK}의 ATR({volatility.ATR_TARGET_WINDOW}거래일, "
                        f"약 6개월)을 1.0으로 둔 상대 변동성입니다. 수익률 상관을 보는 통계적 베타가 아니라 "
                        "변동폭의 크기 비율이므로, 기준과 무상관인 자산도 변동폭만 비슷하면 1.0 근처가 나옵니다."
                    )
                    provisional = volatility.provisional_tickers(atr_info)
                    if provisional:
                        st.caption(
                            "⚠️ 상장 기간이 짧아 창을 줄여 계산한 잠정치(기준 종목도 같은 창으로 재계산): "
                            + ", ".join(provisional)
                        )

                st.dataframe(merged_df, use_container_width=True, column_config=MERGED_COLUMN_CONFIG)

                st.subheader("종목별 소유자 내역")
                ticker_labels = {
                    f"{row['name']} ({row['ticker']})": row["ticker"]
                    for _, row in merged_df.iterrows()
                }
                picked_label = st.selectbox("종목 선택", list(ticker_labels))
                breakdown_df = valid_df[valid_df["ticker"] == ticker_labels[picked_label]]
                st.dataframe(
                    breakdown_df[[
                        "owner", "category", "currency", "quantity", "avg_price",
                        "current_price", "value_krw", "pnl_krw", "return_pct",
                    ]],
                    use_container_width=True,
                )

with tab3:
    st.subheader("데이터 백업 / 복원")
    st.caption("클라우드 배포 환경은 재배포 시 저장된 데이터가 초기화될 수 있습니다. 주기적으로 다운로드해두고, 초기화됐을 때 복원하세요.")
    backup_col, restore_col = st.columns(2)
    with backup_col:
        st.download_button(
            "보유 종목 CSV 다운로드",
            data=data_io.load_holdings().to_csv(index=False),
            file_name="holdings_backup.csv",
            mime="text/csv",
        )
    with restore_col:
        uploaded_holdings = st.file_uploader("보유 종목 CSV 복원", type="csv", key="holdings_restore")
        if uploaded_holdings is not None:
            restored_df = pd.read_csv(
                uploaded_holdings,
                dtype={"ticker": str, "name": str, "category": str, "currency": str, "owner": str},
            )
            missing_cols = data_io.missing_required_columns(restored_df)
            if missing_cols:
                st.error(f"CSV 형식이 올바르지 않습니다 (누락된 열: {', '.join(missing_cols)})")
            else:
                data_io.save_holdings(restored_df)
                st.success("복원 완료")
                st.rerun()

    st.subheader("종목 추가")
    preset_names = ["직접 입력"] + sorted(categories.TICKER_PRESETS.keys())
    preset_choice = st.selectbox("종목 (프리셋)", preset_names)
    owner_choice = st.selectbox("소유자", categories.DEFAULT_OWNERS + ["직접 입력"])
    owner = st.text_input("새 소유자명") if owner_choice == "직접 입력" else owner_choice
    with st.form("add_holding_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            if preset_choice == "직접 입력":
                name = st.text_input("종목명")
                ticker = st.text_input("티커 (예: 005930.KS, QQQ)")
            else:
                name = preset_choice
                ticker = categories.TICKER_PRESETS[preset_choice]
                st.text_input("티커", value=ticker, disabled=True)

            category_choice = st.selectbox("카테고리", categories.DEFAULT_CATEGORIES + ["직접 입력"])
            category = st.text_input("새 카테고리명") if category_choice == "직접 입력" else category_choice
        with col2:
            quantity = st.number_input("수량", min_value=0.0, step=1.0)
            avg_price = st.number_input("평단가", min_value=0.0, step=1.0)
            beta = st.number_input("베타(레버리지 배수)", min_value=0.0, value=1.0, step=0.5)
            inferred_currency = data_io.infer_currency(ticker) if ticker else "USD"
            currency = st.radio("통화", ["KRW", "USD"], index=0 if inferred_currency == "KRW" else 1, horizontal=True)

        submitted = st.form_submit_button("추가")
        if submitted:
            if not ticker or not name or not category or not owner:
                st.error("종목명, 티커, 카테고리, 소유자는 필수입니다.")
            else:
                holdings = data_io.load_holdings()
                new_row = pd.DataFrame([{
                    "ticker": ticker, "name": name, "category": category,
                    "currency": currency, "quantity": quantity,
                    "avg_price": avg_price, "beta": beta, "owner": owner,
                }], columns=data_io.HOLDINGS_COLUMNS)
                holdings = pd.concat([holdings, new_row], ignore_index=True)
                data_io.save_holdings(holdings)
                st.success(f"{name} 추가 완료")

    st.subheader("보유 종목 수정 / 삭제")
    st.caption("그리드에 없는 새 카테고리는 위 '종목 추가' 폼에서 등록해주세요.")
    holdings_df = data_io.load_holdings()
    known_categories = sorted(set(categories.DEFAULT_CATEGORIES) | set(holdings_df["category"].dropna()))
    known_owners = sorted(set(categories.DEFAULT_OWNERS) | set(holdings_df["owner"].dropna()))
    edited_df = st.data_editor(
        holdings_df,
        num_rows="dynamic",
        column_config={
            "currency": st.column_config.SelectboxColumn("통화", options=["KRW", "USD"]),
            "category": st.column_config.SelectboxColumn("카테고리", options=known_categories),
            "owner": st.column_config.SelectboxColumn("소유자", options=known_owners),
        },
        key="holdings_editor",
        use_container_width=True,
    )
    if st.button("변경사항 저장"):
        cleaned_df, dropped = data_io.drop_incomplete_holdings(edited_df)
        data_io.save_holdings(cleaned_df)
        if dropped:
            st.warning(f"티커/종목명/카테고리가 비어있는 행 {dropped}건은 저장하지 않았습니다.")
        st.success("저장 완료")
        st.rerun()

    st.subheader("카테고리 색상 설정")
    st.caption("비중 파이차트에만 적용됩니다. 수익률 바차트(상승/하락)와 자산 추이 차트는 대상이 아닙니다.")
    current_categories = sorted(holdings_df["category"].dropna().unique().tolist())
    if not current_categories:
        st.caption("등록된 종목이 없어 카테고리 색상을 설정할 수 없습니다.")
    else:
        saved_colors = data_io.load_category_colors()
        default_color_map = categories.get_category_color_map(current_categories)
        with st.form("category_color_form"):
            picked_colors = {}
            for cat in current_categories:
                default_value = saved_colors.get(cat, default_color_map.get(cat, categories.FALLBACK_CATEGORY_COLOR))
                picked_colors[cat] = st.color_picker(cat, value=default_value)
            if st.form_submit_button("색상 저장"):
                data_io.save_category_colors(picked_colors)
                st.success("카테고리 색상 저장 완료")
                st.rerun()
