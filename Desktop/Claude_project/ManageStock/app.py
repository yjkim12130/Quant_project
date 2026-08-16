# ManageStock/app.py
import pandas as pd
import streamlit as st

import categories
import data_io

st.set_page_config(page_title="ManageStock", layout="wide")
st.title("ManageStock — 포트폴리오 대시보드")

tab1, tab2 = st.tabs(["포트폴리오 대시보드", "종목 관리"])

with tab2:
    st.subheader("종목 추가")
    preset_names = ["직접 입력"] + sorted(categories.TICKER_PRESETS.keys())
    preset_choice = st.selectbox("종목 (프리셋)", preset_names)
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
            if not ticker or not name or not category:
                st.error("종목명, 티커, 카테고리는 필수입니다.")
            else:
                holdings = data_io.load_holdings()
                new_row = pd.DataFrame([{
                    "ticker": ticker, "name": name, "category": category,
                    "currency": currency, "quantity": quantity,
                    "avg_price": avg_price, "beta": beta,
                }], columns=data_io.HOLDINGS_COLUMNS)
                holdings = pd.concat([holdings, new_row], ignore_index=True)
                data_io.save_holdings(holdings)
                st.success(f"{name} 추가 완료")

    st.subheader("보유 종목 수정 / 삭제")
    st.caption("그리드에 없는 새 카테고리는 위 '종목 추가' 폼에서 등록해주세요.")
    holdings_df = data_io.load_holdings()
    known_categories = sorted(set(categories.DEFAULT_CATEGORIES) | set(holdings_df["category"].dropna()))
    edited_df = st.data_editor(
        holdings_df,
        num_rows="dynamic",
        column_config={
            "currency": st.column_config.SelectboxColumn("통화", options=["KRW", "USD"]),
            "category": st.column_config.SelectboxColumn("카테고리", options=known_categories),
        },
        key="holdings_editor",
        use_container_width=True,
    )
    if st.button("변경사항 저장"):
        data_io.save_holdings(edited_df)
        st.success("저장 완료")
        st.rerun()
