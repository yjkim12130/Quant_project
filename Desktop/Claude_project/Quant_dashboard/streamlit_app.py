"""
YJ-Quant Dashboard  —  Streamlit 독립 실행 버전
────────────────────────────────────────────────
실행: streamlit run streamlit_app.py

포함 기능:
  Tab 1  오늘의 행동 지침  – 실시간 레짐 + 매크로 점수 + 오늘 할 일
  Tab 2  백테스트          – Beta(SNP/NDQ) / Alpha 전략, 파라미터 조정
  Tab 3  WFV 검증          – Walk-Forward + 상태 상속 + Permutation Test
  Tab 4  전략 비교          – Beta SNP / Beta NDQ / Alpha 동시 비교
"""

import itertools
from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import yfinance as yf

# ═══════════════════════════════════════════════════════════════════════════════
# 페이지 설정
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="YJ-Quant Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  .metric-box {background:#1e2130;border-radius:10px;padding:16px 20px;margin:4px 0;}
  .regime-bull  {color:#00d084;font-size:2rem;font-weight:700;}
  .regime-bear  {color:#ff9800;font-size:2rem;font-weight:700;}
  .regime-panic {color:#ff4444;font-size:2rem;font-weight:700;}
  .action-box   {background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:16px;}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# 0. 상수
# ═══════════════════════════════════════════════════════════════════════════════
TRADING_DAYS = 252
LEV_COST     = 0.045
CMA_INTEREST = 0.035
TODAY        = date.today().isoformat()

TOP10_HISTORY: dict = {
    2000: ['GE','INTC','MSFT','CSCO','XOM','WMT','C','ORCL','PFE','IBM'],
    2001: ['GE','MSFT','XOM','C','WMT','PFE','INTC','JNJ','BP','AIG'],
    2002: ['GE','MSFT','XOM','WMT','C','PFE','JNJ','INTC','AIG','IBM'],
    2003: ['GE','MSFT','XOM','WMT','PFE','C','JNJ','INTC','AIG','IBM'],
    2004: ['GE','XOM','MSFT','WMT','C','PFE','JNJ','INTC','AIG','IBM'],
    2005: ['GE','XOM','MSFT','C','WMT','BP','PFE','JNJ','IBM','AIG'],
    2006: ['XOM','GE','MSFT','C','BAC','WMT','PFE','JNJ','BP','AIG'],
    2007: ['XOM','GE','MSFT','WMT','C','BP','BAC','JNJ','PFE','AIG'],
    2008: ['XOM','GE','MSFT','WMT','JNJ','PG','CVX','T','IBM','JPM'],
    2009: ['XOM','WMT','MSFT','JNJ','PG','IBM','CVX','JPM','GE','AAPL'],
    2010: ['XOM','AAPL','MSFT','BRK-B','GE','WMT','GOOGL','CVX','IBM','PG'],
    2011: ['XOM','AAPL','MSFT','IBM','CVX','JNJ','WMT','GE','PG','GOOGL'],
    2012: ['AAPL','XOM','MSFT','WMT','IBM','GE','CVX','BRK-B','GOOGL','JNJ'],
    2013: ['AAPL','XOM','MSFT','GOOGL','BRK-B','GE','JNJ','WMT','CVX','PG'],
    2014: ['AAPL','XOM','MSFT','GOOGL','BRK-B','JNJ','GE','WMT','CVX','PG'],
    2015: ['AAPL','GOOGL','MSFT','BRK-B','XOM','AMZN','META','JNJ','GE','WMT'],
    2016: ['AAPL','GOOGL','MSFT','BRK-B','AMZN','META','JNJ','XOM','JPM','WMT'],
    2017: ['AAPL','GOOGL','MSFT','AMZN','BRK-B','META','JNJ','JPM','XOM','V'],
    2018: ['AAPL','MSFT','AMZN','GOOGL','BRK-B','META','JNJ','JPM','V','WMT'],
    2019: ['AAPL','MSFT','AMZN','GOOGL','BRK-B','META','JPM','JNJ','V','WMT'],
    2020: ['AAPL','MSFT','AMZN','GOOGL','META','TSLA','BRK-B','V','JNJ','WMT'],
    2021: ['AAPL','MSFT','GOOGL','AMZN','TSLA','META','NVDA','BRK-B','JPM','JNJ'],
    2022: ['AAPL','MSFT','GOOGL','AMZN','BRK-B','TSLA','UNH','JNJ','V','NVDA'],
    2023: ['AAPL','MSFT','AMZN','NVDA','GOOGL','META','TSLA','BRK-B','LLY','V'],
    2024: ['MSFT','AAPL','NVDA','GOOGL','AMZN','META','BRK-B','LLY','TSLA','AVGO'],
    2025: ['NVDA','AAPL','MSFT','GOOGL','AMZN','META','TSLA','AVGO','LLY','BRK-B'],
    2026: ['NVDA','AAPL','MSFT','GOOGL','AMZN','META','TSLA','AVGO','LLY','BRK-B'],
}

# ═══════════════════════════════════════════════════════════════════════════════
# 1. 데이터 수집 (캐시)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_index(index_key: str, fetch_start: str) -> pd.DataFrame:
    if index_key == "ndq":
        price_sym, vix_sym = "^IXIC", "^VXN"
        vix_fill, aux = 20.0, ["^GSPC"]
    else:
        price_sym, vix_sym = "^GSPC", "^VIX"
        vix_fill, aux = 15.0, ["^IXIC"]

    symbols = list({price_sym, vix_sym, *aux})
    raw = yf.download(symbols, start=fetch_start, end=TODAY, progress=False)
    if raw.empty:
        return pd.DataFrame()

    close = raw["Close"].ffill() if isinstance(raw.columns, pd.MultiIndex) else raw.ffill()
    df = pd.DataFrame(index=close.index)
    df["Price"] = close.get(price_sym, pd.Series(dtype=float))
    df["VIX"]   = close.get(vix_sym, vix_fill)
    for s in aux:
        if s in close.columns:
            df[s] = close[s]

    df = df.ffill()
    df["VIX"] = df["VIX"].fillna(vix_fill)
    df["Daily_Ret"] = df["Price"].pct_change()
    return df.dropna(subset=["Price"])


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_stocks(fetch_start: str):
    all_t = list({t for ts in TOP10_HISTORY.values() for t in ts})
    raw = yf.download(["SPY"] + all_t, start=fetch_start, end=TODAY, progress=False)
    close = raw["Close"].ffill() if isinstance(raw.columns, pd.MultiIndex) else raw.ffill()
    spy = close.get("SPY", pd.Series(dtype=float))
    return close, spy


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_macro(fetch_start: str) -> pd.DataFrame:
    symbols = ["^TNX", "^IRX", "HYG", "SPY"]
    raw = yf.download(symbols, start=fetch_start, end=TODAY, progress=False)
    if raw.empty:
        return pd.DataFrame()
    close = raw["Close"].ffill() if isinstance(raw.columns, pd.MultiIndex) else raw.ffill()
    df = pd.DataFrame(index=close.index)
    for s in symbols:
        key = s.replace("^", "")
        if s in close.columns:
            df[key] = close[s]
    return df.ffill()

# ═══════════════════════════════════════════════════════════════════════════════
# 2. 지표 계산
# ═══════════════════════════════════════════════════════════════════════════════

def add_indicators(data: pd.DataFrame) -> pd.DataFrame:
    df = data.copy()
    p = df["Price"]
    df["MA_200"] = p.rolling(200).mean()
    df["Disp"]   = (p - df["MA_200"]) / df["MA_200"] * 100
    sma = p.rolling(200).mean()
    mad = p.rolling(200).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)
    df["CCI"] = (p - sma) / (0.015 * mad)
    delta = p.diff()
    gain = delta.where(delta > 0, 0.0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
    df["RSI"] = 100 - (100 / (1 + gain / loss))
    df["MDD"] = (p / p.rolling(252, min_periods=1).max()) - 1.0
    # T+1 지연 신호 (전일 기준 매매 결정)
    for col in ["VIX", "CCI", "RSI", "MDD", "Disp"]:
        if col in df.columns:
            df[f"_s_{col}"] = df[col].shift(1)
    return df


def calc_macro_score(macro_df: pd.DataFrame, vix_series: pd.Series) -> pd.Series:
    df = macro_df.copy()
    # Factor 1: 금리차 역전
    if "TNX" in df.columns and "IRX" in df.columns:
        s_yield = ((df["TNX"] - df["IRX"]) < 0).astype(int)
    else:
        s_yield = pd.Series(0, index=df.index)
    # Factor 2: VIX Z-score
    vix = vix_series.reindex(df.index).ffill()
    vix_m = vix.rolling(504, min_periods=60).mean()
    vix_s = vix.rolling(504, min_periods=60).std()
    vix_z = (vix - vix_m) / vix_s.replace(0, np.nan)
    s_vix = (vix_z > 1.5).fillna(0).astype(int)
    # Factor 3: 유동성 스트레스 (SPY 대비 HYG 상대 하락)
    if "HYG" in df.columns and "SPY" in df.columns:
        s_liq = ((df["SPY"].pct_change(60) - df["HYG"].pct_change(60)) > 0.05).fillna(0).astype(int)
    else:
        s_liq = pd.Series(0, index=df.index)
    return (s_yield + s_vix + s_liq).reindex(df.index).fillna(0)

# ═══════════════════════════════════════════════════════════════════════════════
# 3. 전략 엔진
# ═══════════════════════════════════════════════════════════════════════════════

def _decide_state(state, vix, cci, rsi, mdd, disp, macro, p):
    macro_thr = p.get("macro_threshold", 2)
    if macro >= macro_thr and state != "Panic":
        return "Bear"
    if vix >= p["vix_panic"] and mdd <= p["mdd_panic"]:
        return "Panic"
    if state == "Panic":
        return "Bear" if (cci > 0 and rsi > p["rsi_bear"]) else "Panic"
    if state == "Bear":
        return "Bull" if (cci > p["cci_bull"] and rsi > p["rsi_bull"]) else "Bear"
    return "Bear" if (cci < p["cci_bear"] and disp < -3.0) else "Bull"


def run_beta(data: pd.DataFrame, params: dict, budget: float,
             inherited_state: dict = None) -> dict:
    df = add_indicators(data)
    df = df.dropna(subset=["MA_200", "_s_MDD"]).copy()

    d_st = (budget * (params["stock_ratio"] / 18)) / TRADING_DAYS
    d_cs = (budget * ((18 - params["stock_ratio"]) / 18)) / TRADING_DAYS
    m_sets, d_sets = params["mdd_threshold_sets"], params["drain_sets"]

    if inherited_state:
        yj_st = float(inherited_state.get("yj_st", 0))
        yj_cs = float(inherited_state.get("yj_cs", 0))
        state = inherited_state.get("state", "Bull")
        p_cnt = int(inherited_state.get("p_cnt", 0))
        total_prin = float(inherited_state.get("total_principal", 0))
    else:
        yj_st = yj_cs = 0.0; state = "Bull"; p_cnt = 0; total_prin = 0.0

    records, state_logs = [], []
    for dt, row in df.iterrows():
        dr   = float(row.get("Daily_Ret", 0) or 0)
        vix  = float(row.get("_s_VIX",  15))
        cci  = float(row.get("_s_CCI",  0))
        rsi  = float(row.get("_s_RSI",  50))
        mdd  = float(row.get("_s_MDD",  0))
        disp = float(row.get("_s_Disp", 0))
        macro = float(row.get("_s_macro_score", 0))

        prev = state
        state = _decide_state(state, vix, cci, rsi, mdd, disp, macro, params)
        if state != prev:
            state_logs.append({"날짜": dt.date(), "변화": f"{prev} → {state}",
                                "VIX": round(vix,1), "MDD%": round(mdd*100,1),
                                "CCI": round(cci,1), "RSI": round(rsi,1)})

        lev = {"Bull": params["lev_bull"], "Bear": params["lev_bear"],
                "Panic": params["lev_panic"]}[state]
        total_prin += budget / TRADING_DAYS
        yj_st += d_st; yj_cs += d_cs
        if dr:
            yj_st *= 1 + dr * lev - max(0, lev - 1) * (LEV_COST / TRADING_DAYS)
        yj_cs *= 1 + CMA_INTEREST / TRADING_DAYS

        if state == "Panic" and p_cnt % params["panic_period"] == 0:
            m = abs(mdd)
            dr_ratio = (d_sets[0] if m >= m_sets[0] else d_sets[1] if m >= m_sets[1]
                        else d_sets[2] if m >= m_sets[2] else 0)
            p_buy = min((yj_cs * dr_ratio) / params["periodic_denom"], yj_cs)
            yj_st += p_buy; yj_cs -= p_buy
        p_cnt = p_cnt + 1 if state == "Panic" else 0

        records.append({"time": dt, "yj_val": yj_st + yj_cs, "yj_st": yj_st,
                         "yj_cs": yj_cs, "state": state, "leverage": lev,
                         "total_principal": total_prin})

    if not records:
        return _empty_result()

    eq  = pd.DataFrame(records).set_index("time")
    dca = _calc_dca(df, budget)
    return {"equity_curve": eq, "dca_curve": dca, "metrics": _calc_metrics(eq),
            "state_logs": state_logs,
            "final_state": {"yj_st": yj_st, "yj_cs": yj_cs, "state": state,
                            "p_cnt": p_cnt, "total_principal": total_prin}}


def run_alpha(data: pd.DataFrame, stock_close: pd.DataFrame, spy: pd.Series,
              params: dict, budget: float, inherited_state: dict = None) -> dict:
    df = add_indicators(data)
    df = df.dropna(subset=["MA_200", "_s_MDD"]).copy()
    stock_ret = stock_close.pct_change().fillna(0)

    d_st = (budget * (params["stock_ratio"] / 18)) / TRADING_DAYS
    d_cs = (budget * ((18 - params["stock_ratio"]) / 18)) / TRADING_DAYS
    m_sets, d_sets = params["mdd_threshold_sets"], params["drain_sets"]
    top_n = params.get("top_n", 10)

    if inherited_state:
        yj_st    = float(inherited_state.get("yj_st", 0))
        yj_cs    = float(inherited_state.get("yj_cs", 0))
        yj_alpha = float(inherited_state.get("yj_alpha", 0))
        state    = inherited_state.get("state", "Bull")
        p_cnt    = int(inherited_state.get("p_cnt", 0))
        total_prin = float(inherited_state.get("total_principal", 0))
    else:
        yj_st = yj_cs = yj_alpha = 0.0; state = "Bull"; p_cnt = 0; total_prin = 0.0

    records = []
    for dt, row in df.iterrows():
        dr   = float(row.get("Daily_Ret", 0) or 0)
        vix  = float(row.get("_s_VIX",  15))
        cci  = float(row.get("_s_CCI",  0))
        rsi  = float(row.get("_s_RSI",  50))
        mdd  = float(row.get("_s_MDD",  0))
        disp = float(row.get("_s_Disp", 0))
        year = dt.year

        state = _decide_state(state, vix, cci, rsi, mdd, disp, 0, params)

        # Alpha 바스켓 일별 수익 반영
        if yj_alpha > 0 and dt in stock_ret.index:
            tickers = TOP10_HISTORY.get(year, TOP10_HISTORY[max(TOP10_HISTORY)])[:top_n]
            avail = [t for t in tickers if t in stock_ret.columns]
            if avail:
                yj_alpha *= (1 + float(stock_ret.loc[dt, avail].mean()))

        # Panic 중: 지수 1배 (레버리지 없음)
        lev_idx = (1.0 if state == "Panic"
                   else {"Bull": params["lev_bull"], "Bear": params["lev_bear"]}[state])
        total_prin += budget / TRADING_DAYS
        yj_st += d_st; yj_cs += d_cs
        if dr:
            yj_st *= 1 + dr * lev_idx - max(0, lev_idx - 1) * (LEV_COST / TRADING_DAYS)
        yj_cs *= 1 + CMA_INTEREST / TRADING_DAYS

        if state == "Panic" and p_cnt % params["panic_period"] == 0:
            m = abs(mdd)
            dr_ratio = (d_sets[0] if m >= m_sets[0] else d_sets[1] if m >= m_sets[1]
                        else d_sets[2] if m >= m_sets[2] else 0)
            buy_a = min((yj_cs * dr_ratio) / params["periodic_denom"], yj_cs)
            yj_alpha += buy_a; yj_cs -= buy_a
        p_cnt = p_cnt + 1 if state == "Panic" else 0

        records.append({"time": dt, "yj_val": yj_st + yj_alpha + yj_cs,
                         "yj_st": yj_st, "yj_alpha": yj_alpha, "yj_cs": yj_cs,
                         "state": state, "leverage": lev_idx,
                         "total_principal": total_prin})

    if not records:
        return _empty_result()

    eq  = pd.DataFrame(records).set_index("time")
    dca = _calc_dca(df, budget)
    return {"equity_curve": eq, "dca_curve": dca, "metrics": _calc_metrics(eq),
            "final_state": {"yj_st": yj_st, "yj_cs": yj_cs, "yj_alpha": yj_alpha,
                            "state": state, "p_cnt": p_cnt, "total_principal": total_prin}}


def _calc_dca(df, budget):
    daily = budget / TRADING_DAYS
    sh = prin = 0.0
    rows = []
    for dt, row in df.iterrows():
        p = row["Price"]
        sh += daily / p if p > 0 else 0
        prin += daily
        rows.append({"time": dt, "portfolio_value": sh * p, "principal": prin})
    return pd.DataFrame(rows).set_index("time")


def _calc_metrics(eq: pd.DataFrame) -> dict:
    if eq.empty:
        return {}
    fv  = eq["yj_val"].iloc[-1]
    inv = eq["total_principal"].iloc[-1]
    tr  = (fv / inv - 1) * 100 if inv > 0 else 0
    pk  = eq["yj_val"].cummax()
    mdd = ((eq["yj_val"] / pk) - 1).min()
    ar  = ((fv / inv) ** (TRADING_DAYS / max(len(eq), 1)) - 1) if inv > 0 else 0
    cal = ar / abs(mdd) if mdd != 0 else 0
    dr  = eq["yj_val"].pct_change().dropna()
    sh  = dr.mean() / dr.std() * np.sqrt(TRADING_DAYS) if dr.std() > 0 else 0
    return {"total_return": round(tr, 2), "annual_return": round(ar * 100, 2),
            "mdd": round(mdd * 100, 2), "calmar_ratio": round(cal, 4),
            "sharpe_ratio": round(sh, 4), "final_value": round(fv, 0)}


def _empty_result():
    return {"equity_curve": pd.DataFrame(), "dca_curve": pd.DataFrame(),
            "metrics": {}, "state_logs": [], "final_state": {}}

# ═══════════════════════════════════════════════════════════════════════════════
# 4. WFV 엔진
# ═══════════════════════════════════════════════════════════════════════════════

_WFV_GRID = {
    "vix_panic":     [25, 30],
    "mdd_panic":     [-0.12, -0.15],
    "cci_bull":      [50, 100],
    "cci_bear":      [-50, -100],
    "rsi_bull":      [70, 90],
    "rsi_bear":      [40, 60],
    "panic_period":  [1, 5],
}  # 128 조합


def run_wfv(data: pd.DataFrame, base_params: dict, budget: float,
            is_years: int, oos_years: int, progress_fn=None) -> dict:
    years = sorted(data.index.year.unique())
    if len(years) < is_years + oos_years:
        return {"error": "데이터 기간 부족", "windows": [],
                "combined_equity": pd.DataFrame(), "metrics": {}, "p_value": None}

    keys, vals = zip(*_WFV_GRID.items())
    combos = [dict(zip(keys, v)) for v in itertools.product(*vals)]
    total_windows = max((len(years) - is_years) // oos_years, 1)

    all_windows, oos_eqs = [], []
    inherited = None

    i = step = 0
    while i + is_years < len(years):
        is_yr  = years[i: i + is_years]
        oos_yr = years[i + is_years: i + is_years + oos_years]
        if not oos_yr:
            break

        is_data  = data[data.index.year.isin(is_yr)]
        oos_data = data[data.index.year.isin(oos_yr)]

        # IS 최적화 (Calmar 기준)
        best_p, best_cal = _optimize_is(is_data, combos, base_params, budget)

        # OOS 실행 (잔고 상속)
        params_full = {**base_params, **best_p}
        res = run_beta(oos_data, params_full, budget, inherited)
        inherited = res["final_state"]

        all_windows.append({
            "IS 기간": f"{is_yr[0]}~{is_yr[-1]}",
            "OOS 기간": f"{oos_yr[0]}",
            "최적 파라미터": {k: best_p.get(k) for k in ["vix_panic","mdd_panic","cci_bull","cci_bear"]},
            "IS Calmar": round(best_cal, 4),
            "OOS 수익률(%)": res["metrics"].get("annual_return", 0),
            "OOS MDD(%)": res["metrics"].get("mdd", 0),
            "OOS Calmar": res["metrics"].get("calmar_ratio", 0),
        })

        if not res["equity_curve"].empty:
            oos_eqs.append(res["equity_curve"])

        step += 1
        if progress_fn:
            progress_fn(step / total_windows)
        i += oos_years

    if not oos_eqs:
        return {"windows": all_windows, "combined_equity": pd.DataFrame(),
                "metrics": {}, "p_value": None}

    combined = pd.concat(oos_eqs).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    metrics  = _calc_metrics(combined)
    mrets    = data["Daily_Ret"].reindex(combined.index).fillna(0)
    p_result = _permutation_test(combined, mrets)

    return {"windows": all_windows, "combined_equity": combined,
            "metrics": metrics, "p_value": p_result}


def _optimize_is(is_data, combos, base_params, budget):
    best_cal, best_p = -np.inf, {}
    for combo in combos:
        try:
            r = run_beta(is_data, {**base_params, **combo}, budget)
            c = r["metrics"].get("calmar_ratio", -np.inf)
            if c > best_cal:
                best_cal, best_p = c, combo
        except Exception:
            continue
    return best_p, best_cal


def _permutation_test(eq: pd.DataFrame, market_rets: pd.Series, n_iter: int = 1000) -> dict:
    if eq.empty or "leverage" not in eq.columns:
        return {"p_value": 1.0, "significant": False}
    lev_seq = eq["leverage"].values
    ret_seq = market_rets.values

    def _compound(rets, levs):
        m = 1.0
        for r, l in zip(rets, levs):
            m *= 1 + r * l - max(0, l - 1) * (LEV_COST / TRADING_DAYS)
        return (m - 1) * 100

    actual = _compound(ret_seq, lev_seq)
    rng = np.random.default_rng(42)
    null = np.array([_compound(ret_seq, rng.permutation(lev_seq)) for _ in range(n_iter)])
    p    = float(np.mean(null >= actual))
    std  = float(null.std())
    return {"p_value": round(p, 4), "actual_ret": round(actual, 2),
            "null_mean": round(float(null.mean()), 2), "null_std": round(std, 2),
            "z_score": round((actual - null.mean()) / std, 3) if std > 0 else 0,
            "significant": p < 0.05, "n_iter": n_iter}

# ═══════════════════════════════════════════════════════════════════════════════
# 5. 차트 (Plotly)
# ═══════════════════════════════════════════════════════════════════════════════

_DARK = "plotly_dark"
_STATE_COLOR = {"Bull": "rgba(30,144,255,0.12)",
                "Bear": "rgba(255,165,0,0.18)",
                "Panic": "rgba(255,50,50,0.22)"}


def fig_equity(eq: pd.DataFrame, dca: pd.DataFrame, title: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=eq.index, y=eq["yj_val"]/1e8, name="YJAlgo",
                             line=dict(color="#00d084", width=2.5)))
    if not dca.empty:
        fig.add_trace(go.Scatter(x=dca.index, y=dca["portfolio_value"]/1e8, name="단순 DCA",
                                 line=dict(color="#ff9800", dash="dot", width=1.5)))
    fig.update_layout(title=title, yaxis_title="자산 (억 원)", template=_DARK,
                      height=380, legend=dict(x=0.01, y=0.99))
    return fig


def fig_drawdown(eq: pd.DataFrame) -> go.Figure:
    pk = eq["yj_val"].cummax()
    dd = ((eq["yj_val"] / pk) - 1) * 100
    fig = go.Figure(go.Scatter(x=eq.index, y=dd, fill="tozeroy",
                               line=dict(color="#ff4444"), fillcolor="rgba(255,68,68,0.25)"))
    fig.update_layout(title="Drawdown (%)", yaxis_title="%", template=_DARK, height=280)
    return fig


def fig_cma(eq: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Scatter(x=eq.index, y=eq["yj_cs"]/1e4, fill="tozeroy",
                               line=dict(color="#00bcd4"), fillcolor="rgba(0,188,212,0.2)"))
    fig.update_layout(title="CMA 현금 잔고 (War Chest, 만 원)", template=_DARK, height=280)
    return fig


def fig_regime(eq: pd.DataFrame, price: pd.Series) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=price.index, y=price.values, name="지수",
                             line=dict(color="white", width=1.5)))
    prev, seg = None, None
    for dt, row in eq.iterrows():
        s = row["state"]
        if s != prev:
            if prev:
                fig.add_vrect(x0=seg, x1=dt, fillcolor=_STATE_COLOR[prev],
                              line_width=0, layer="below")
            seg, prev = dt, s
    if prev and seg is not None:
        fig.add_vrect(x0=seg, x1=eq.index[-1], fillcolor=_STATE_COLOR[prev],
                      line_width=0, layer="below")
    for label, color in [("Bull","#1e90ff"),("Bear","#ffa500"),("Panic","#ff4444")]:
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
                                 marker=dict(color=color, size=10, symbol="square"),
                                 name=label))
    fig.update_layout(title="시장 지수 & 레짐 구간", yaxis_title="지수",
                      template=_DARK, height=380)
    return fig


def fig_yearly(eq: pd.DataFrame) -> go.Figure:
    yr = eq["yj_val"].resample("YE").last().pct_change().dropna() * 100
    colors = ["#2ecc71" if v >= 0 else "#e74c3c" for v in yr.values]
    fig = go.Figure(go.Bar(x=[str(d.year) for d in yr.index], y=yr.values,
                           marker_color=colors, text=[f"{v:.1f}%" for v in yr.values],
                           textposition="outside"))
    fig.update_layout(title="연도별 수익률 (%)", template=_DARK, height=340)
    return fig


def fig_compare(results: dict) -> go.Figure:
    colors = {"Beta SNP": "#00d084", "Beta NDQ": "#2196f3", "Alpha": "#ff9800"}
    fig = go.Figure()
    for name, res in results.items():
        if res and not res["equity_curve"].empty:
            eq = res["equity_curve"]
            fig.add_trace(go.Scatter(x=eq.index, y=eq["yj_val"]/1e8, name=name,
                                     line=dict(color=colors.get(name, "#aaa"), width=2.5)))
    fig.update_layout(title="전략 비교 – 누적 자산 (억 원)",
                      yaxis_title="자산 (억 원)", template=_DARK,
                      height=420, legend=dict(x=0.01, y=0.99))
    return fig

# ═══════════════════════════════════════════════════════════════════════════════
# 6. 기본 파라미터
# ═══════════════════════════════════════════════════════════════════════════════

_BASE = dict(lev_bull=2.0, lev_bear=1.0, lev_panic=1.5,
             stock_ratio=15, panic_period=1, periodic_denom=1,
             mdd_threshold_sets=[0.45,0.30,0.15], drain_sets=[1.0,0.6,0.4],
             macro_threshold=2)

P_SNP = dict(**_BASE, index="snp", vix_panic=25, mdd_panic=-0.15,
             cci_bull=50, cci_bear=-50, rsi_bull=70, rsi_bear=60)

P_NDQ = dict(**_BASE, index="ndq", vix_panic=28, mdd_panic=-0.15,
             cci_bull=80, cci_bear=-80, rsi_bull=70, rsi_bear=60,
             mdd_threshold_sets=[0.55,0.35,0.15])

P_ALPHA = dict(**P_SNP, top_n=10, alpha_weight="sp_spread_l")

# ═══════════════════════════════════════════════════════════════════════════════
# 7. 사이드바
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.title("⚙️ 설정")
    index_choice = st.radio("기준 지수", ["S&P 500 (SNP)", "Nasdaq (NDQ)"], index=0)
    index_key    = "snp" if "SNP" in index_choice else "ndq"
    start_year   = st.slider("백테스트 시작 연도", 2005, 2020, 2010)
    annual_budget = st.number_input("연간 투자금 (원)", value=40_000_000, step=1_000_000,
                                    format="%d")
    st.divider()
    st.caption("데이터는 yfinance에서 실시간 수집됩니다.\n(시장 지표는 1시간 캐시)")

# ═══════════════════════════════════════════════════════════════════════════════
# 데이터 로드 (공통)
# ═══════════════════════════════════════════════════════════════════════════════

fetch_start = f"{start_year - 3}-01-01"   # MA200/MDD252 warmup
macro_start = f"{start_year - 2}-01-01"

with st.spinner("📡 시장 데이터 수집 중..."):
    market_df = fetch_index(index_key, fetch_start)
    macro_df  = fetch_macro(macro_start)

if market_df.empty:
    st.error("시장 데이터를 가져올 수 없습니다. 네트워크를 확인하세요.")
    st.stop()

# 매크로 점수 병합
if not macro_df.empty:
    macro_score = calc_macro_score(macro_df, market_df["VIX"])
    aligned = macro_score.reindex(market_df.index).ffill().fillna(0)
    market_df["macro_score"] = aligned
    market_df["_s_macro_score"] = market_df["macro_score"].shift(1)

# ═══════════════════════════════════════════════════════════════════════════════
# 탭 레이아웃
# ═══════════════════════════════════════════════════════════════════════════════

tab1, tab2, tab3, tab4 = st.tabs([
    "🏠 오늘의 행동 지침",
    "📈 백테스트",
    "🔄 WFV 검증",
    "🆚 전략 비교",
])

# ───────────────────────────────────────────────────────────────────────────────
# Tab 1: 오늘의 행동 지침
# ───────────────────────────────────────────────────────────────────────────────
with tab1:
    st.subheader(f"📅 기준일: {market_df.index[-1].date()}  ({index_choice})")

    enriched = add_indicators(market_df)
    last = enriched.iloc[-1]

    vix  = float(last.get("VIX", 20))
    cci  = float(last.get("CCI", 0))
    rsi  = float(last.get("RSI", 50))
    mdd  = float(last.get("MDD", 0))
    disp = float(last.get("Disp", 0))
    macro_s = float(last.get("macro_score", 0))

    params_today = P_NDQ if index_key == "ndq" else P_SNP
    # 전체 이력 시뮬레이션으로 현재 레짐 정확히 도출 (stateful — 단발 판단 금지)
    _sim_data = market_df[market_df.index >= pd.Timestamp(f"{start_year}-01-01")]
    with st.spinner("📊 레짐 계산 중..."):
        hist_res = run_beta(_sim_data, params_today, annual_budget)
    regime = hist_res["final_state"].get("state", "Bull")

    lev = params_today["lev_" + regime.lower()]
    d_stock = (annual_budget * (params_today["stock_ratio"] / 18)) / TRADING_DAYS
    d_cma   = (annual_budget * ((18 - params_today["stock_ratio"]) / 18)) / TRADING_DAYS

    # ── 현재 레짐 ──
    regime_class = f"regime-{regime.lower()}"
    r_emoji = {"Bull": "🟢", "Bear": "🟡", "Panic": "🔴"}[regime]
    st.markdown(f"""
    <div class="metric-box">
      <span style="color:#aaa;font-size:0.9rem">현재 레짐 (T+1 기준, 전일 종가 신호)</span><br>
      <span class="{regime_class}">{r_emoji} {regime}</span>
      <span style="color:#aaa;font-size:1rem"> &nbsp;→ 추천 레버리지 <b style="color:white">{lev}x</b></span>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # ── 시장 지표 ──
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("VIX",   f"{vix:.2f}",  delta=f"임계: {params_today['vix_panic']}")
    c2.metric("MDD",   f"{mdd*100:.1f}%",  delta=f"임계: {params_today['mdd_panic']*100:.0f}%")
    c3.metric("CCI",   f"{cci:.1f}",  delta=f"Bull>{params_today['cci_bull']} | Bear<{params_today['cci_bear']}")
    c4.metric("RSI",   f"{rsi:.1f}",  delta=f"Bull>{params_today['rsi_bull']}")
    c5.metric("Macro", f"{int(macro_s)}/3", delta="≥2 → Bear 강제")

    st.divider()

    # ── 매크로 세부 ──
    if not macro_df.empty:
        macro_last = macro_df.iloc[-1]
        m1, m2, m3 = st.columns(3)
        tnx = float(macro_last.get("TNX", 0) or 0)
        irx = float(macro_last.get("IRX", 0) or 0)
        spread = tnx - irx
        m1.metric("금리차 (10Y-3M)", f"{spread:.2f}%",
                  delta="역전 중" if spread < 0 else "정상",
                  delta_color="inverse" if spread < 0 else "normal")
        m2.metric("10Y 국채", f"{tnx:.2f}%")
        m3.metric("3M 국채", f"{irx:.2f}%")

    st.divider()

    # ── 오늘의 행동 지침 ──
    st.markdown("### 📋 오늘 할 일")
    action_col1, action_col2 = st.columns(2)

    # CMA 잔고 & 총 자산 (시뮬레이션 결과)
    _fs = hist_res.get("final_state", {})
    _cma_balance = _fs.get("yj_cs", 0)
    _total_asset = _fs.get("yj_st", 0) + _fs.get("yj_alpha", 0) + _cma_balance

    with action_col1:
        st.markdown(f"""
        <div class="action-box">
        <b>기본 일일 적립</b><br><br>
        📊 주식 매수: <b>{d_stock:,.0f}원</b><br>
        💰 CMA 적립: <b>{d_cma:,.0f}원</b><br>
        📅 연간 투자금: <b>{annual_budget/1e4:,.0f}만 원</b><br><br>
        <hr style="border-color:#333">
        💼 현재 CMA 잔고: <b style="color:#00bcd4">{_cma_balance/1e4:,.0f}만 원</b><br>
        📈 추정 총 자산: <b style="color:#00d084">{_total_asset/1e8:.2f}억 원</b>
        </div>
        """, unsafe_allow_html=True)

    with action_col2:
        if regime == "Panic":
            m_abs = abs(mdd)
            m_sets = params_today["mdd_threshold_sets"]
            d_sets = params_today["drain_sets"]
            dr_ratio = (d_sets[0] if m_abs >= m_sets[0] else
                        d_sets[1] if m_abs >= m_sets[1] else
                        d_sets[2] if m_abs >= m_sets[2] else 0)
            st.markdown(f"""
            <div class="action-box" style="border-color:#ff4444">
            🚨 <b>Panic 매수 발동!</b><br><br>
            MDD 깊이: <b>{m_abs*100:.1f}%</b><br>
            CMA 인출 비율: <b>{dr_ratio*100:.0f}%</b><br>
            추정 인출 금액: 현재 CMA 잔고 × {dr_ratio*100:.0f}%<br>
            <small style="color:#aaa">→ 인출 후 즉시 지수 추가 매수</small>
            </div>
            """, unsafe_allow_html=True)
        elif regime == "Bear":
            st.markdown(f"""
            <div class="action-box" style="border-color:#ffa500">
            🟡 <b>Bear 구간 – 방어 모드</b><br><br>
            레버리지: <b>1x</b> (무레버리지)<br>
            기본 적립만 유지<br>
            CMA 현금 비중 확대 권장
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="action-box" style="border-color:#00d084">
            🟢 <b>Bull 구간 – 공격 모드</b><br><br>
            레버리지: <b>2x</b><br>
            기본 적립 + 레버리지 지수 보유<br>
            CMA에서 추가 매수 가능
            </div>
            """, unsafe_allow_html=True)

    # ── 최근 레짐 전환 이력 (위에서 이미 계산된 hist_res 재사용) ──
    st.divider()
    st.markdown("### 🔄 최근 레짐 전환 이력")
    if hist_res.get("state_logs"):
        slogs = pd.DataFrame(hist_res["state_logs"]).tail(20)
        st.dataframe(slogs, use_container_width=True, hide_index=True)
    else:
        st.info("레짐 전환 기록 없음")

# ───────────────────────────────────────────────────────────────────────────────
# Tab 2: 백테스트
# ───────────────────────────────────────────────────────────────────────────────
with tab2:
    st.subheader("📈 백테스트")

    bt_col1, bt_col2 = st.columns([1, 3])
    with bt_col1:
        strategy_type = st.radio("전략", ["Beta (지수)", "Alpha (개별주)"])
        st.divider()
        st.markdown("**레짐 파라미터**")
        p = P_NDQ.copy() if index_key == "ndq" else P_SNP.copy()
        p["vix_panic"]  = st.slider("VIX Panic 임계치", 20, 40, int(p["vix_panic"]))
        p["mdd_panic"]  = st.slider("MDD Panic 임계치 (%)", -30, -5,
                                     int(p["mdd_panic"]*100)) / 100
        p["cci_bull"]   = st.slider("CCI Bull 진입", 20, 150, int(p["cci_bull"]))
        p["cci_bear"]   = st.slider("CCI Bear 진입", -150, -20, int(p["cci_bear"]))
        p["rsi_bull"]   = st.slider("RSI Bull 기준", 50, 90, int(p["rsi_bull"]))
        p["rsi_bear"]   = st.slider("RSI Bear 기준", 30, 70, int(p["rsi_bear"]))
        st.divider()
        p["panic_period"]   = st.slider("Panic 매수 주기 (일)", 1, 10, int(p["panic_period"]))
        p["periodic_denom"] = st.slider("Panic 매수 분할 수", 1, 10, int(p["periodic_denom"]))
        run_bt = st.button("▶ 백테스트 실행", type="primary", use_container_width=True)

    with bt_col2:
        if run_bt:
            bt_data = market_df[market_df.index >= pd.Timestamp(f"{start_year}-01-01")]

            if "Alpha" in strategy_type:
                with st.spinner("📦 개별주 데이터 수집 중 (최초 1회 약 30초)..."):
                    stock_close, spy = fetch_stocks(f"{start_year - 1}-01-01")
                with st.spinner("🔄 Alpha 전략 백테스트 중..."):
                    res = run_alpha(bt_data, stock_close, spy, p, annual_budget)
            else:
                with st.spinner("🔄 Beta 전략 백테스트 중..."):
                    res = run_beta(bt_data, p, annual_budget)

            eq, dca, m = res["equity_curve"], res["dca_curve"], res["metrics"]

            if eq.empty:
                st.error("백테스트 결과가 없습니다.")
            else:
                # 성과 지표
                mc1, mc2, mc3, mc4, mc5 = st.columns(5)
                mc1.metric("총 수익률",    f"{m.get('total_return',0):.1f}%")
                mc2.metric("연환산(CAGR)", f"{m.get('annual_return',0):.1f}%")
                mc3.metric("최대 MDD",     f"{m.get('mdd',0):.1f}%")
                mc4.metric("Calmar",       f"{m.get('calmar_ratio',0):.3f}")
                mc5.metric("Sharpe",       f"{m.get('sharpe_ratio',0):.3f}")

                st.plotly_chart(fig_equity(eq, dca, f"YJAlgo {strategy_type} vs DCA ({start_year}~)"),
                                use_container_width=True)

                row1, row2 = st.columns(2)
                with row1:
                    st.plotly_chart(fig_drawdown(eq), use_container_width=True)
                with row2:
                    st.plotly_chart(fig_cma(eq), use_container_width=True)

                st.plotly_chart(fig_regime(eq, market_df["Price"]), use_container_width=True)
                st.plotly_chart(fig_yearly(eq), use_container_width=True)

                # 연도별 성과 테이블
                st.markdown("#### 📊 연도별 성과")
                yr_grp = eq.groupby(eq.index.year).last()
                rows = []
                for yr, r in yr_grp.iterrows():
                    inv = r["total_principal"]
                    rows.append({
                        "연도": yr,
                        "YJ 자산(억)": round(r["yj_val"]/1e8, 2),
                        "YJ 수익률(%)": round((r["yj_val"]/inv - 1)*100, 1) if inv > 0 else 0,
                        "CMA 잔고(만)": round(r["yj_cs"]/1e4, 0),
                        "레짐": r["state"],
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

                # 상태 전환 이력
                if res.get("state_logs"):
                    with st.expander("🔄 전체 레짐 전환 이력"):
                        st.dataframe(pd.DataFrame(res["state_logs"]),
                                     use_container_width=True, hide_index=True)
        else:
            st.info("좌측 파라미터를 설정하고 **백테스트 실행** 버튼을 누르세요.")

# ───────────────────────────────────────────────────────────────────────────────
# Tab 3: WFV 검증
# ───────────────────────────────────────────────────────────────────────────────
with tab3:
    st.subheader("🔄 Walk-Forward Validation")
    st.caption("IS 기간 최적 파라미터 도출 → OOS 기간 잔고 상속 실행 → 반복")

    wc1, wc2 = st.columns([1, 3])
    with wc1:
        is_y  = st.selectbox("IS 기간 (학습)", [3, 4, 5], index=1)
        oos_y = st.selectbox("OOS 기간 (검증)", [1, 2], index=0)
        run_wfv_btn = st.button("▶ WFV 실행", type="primary", use_container_width=True)
        st.divider()
        st.markdown(f"""
        **예상 윈도우 수**
        약 {max((2026 - start_year - is_y) // oos_y, 1)}개

        **그리드 크기**
        128 조합 × 윈도우 수

        ⚠️ 오래 걸릴 수 있습니다.
        """)

    with wc2:
        if run_wfv_btn:
            wfv_data = market_df[market_df.index >= pd.Timestamp(f"{start_year}-01-01")]
            base_p   = P_NDQ.copy() if index_key == "ndq" else P_SNP.copy()

            progress_bar = st.progress(0, text="WFV 실행 중...")

            def _update_progress(v):
                progress_bar.progress(min(v, 1.0), text=f"WFV 진행 중... {v*100:.0f}%")

            with st.spinner("⏳ WFV 실행 중 (몇 분 소요될 수 있습니다)..."):
                wfv_res = run_wfv(wfv_data, base_p, annual_budget, is_y, oos_y, _update_progress)
            progress_bar.empty()

            if "error" in wfv_res:
                st.error(wfv_res["error"])
            else:
                combined = wfv_res["combined_equity"]
                metrics  = wfv_res["metrics"]
                p_res    = wfv_res["p_value"]

                # 성과
                wm1, wm2, wm3, wm4 = st.columns(4)
                wm1.metric("WFV 총 수익률",    f"{metrics.get('total_return',0):.1f}%")
                wm2.metric("WFV CAGR",          f"{metrics.get('annual_return',0):.1f}%")
                wm3.metric("WFV 최대 MDD",      f"{metrics.get('mdd',0):.1f}%")
                wm4.metric("WFV Calmar",         f"{metrics.get('calmar_ratio',0):.3f}")

                st.plotly_chart(fig_equity(combined, pd.DataFrame(), "WFV 누적 자산 (OOS 구간 연결)"),
                                use_container_width=True)

                # Permutation Test
                if p_res:
                    st.markdown("#### 📊 Permutation Test (전략 통계적 유의성)")
                    pm1, pm2, pm3, pm4 = st.columns(4)
                    sig = p_res.get("significant", False)
                    pm1.metric("p-value",    f"{p_res.get('p_value',1):.4f}",
                               delta="유의 (p<0.05)" if sig else "비유의",
                               delta_color="normal" if sig else "inverse")
                    pm2.metric("실제 수익률",  f"{p_res.get('actual_ret',0):.1f}%")
                    pm3.metric("귀무분포 평균", f"{p_res.get('null_mean',0):.1f}%")
                    pm4.metric("Z-score",      f"{p_res.get('z_score',0):.3f}")

                    if sig:
                        st.success(f"✅ 전략이 통계적으로 유의합니다 (p={p_res.get('p_value'):.4f} < 0.05). "
                                   f"레버리지 타이밍에 실질적 알파가 존재합니다.")
                    else:
                        st.warning(f"⚠️ 유의하지 않습니다 (p={p_res.get('p_value'):.4f}). "
                                   f"파라미터 재조정을 고려하세요.")

                # 윈도우별 결과 테이블
                st.markdown("#### 🪟 윈도우별 결과")
                st.dataframe(pd.DataFrame(wfv_res["windows"]),
                             use_container_width=True, hide_index=True)
        else:
            st.info("설정 후 **WFV 실행** 버튼을 누르세요.")

# ───────────────────────────────────────────────────────────────────────────────
# Tab 4: 전략 비교
# ───────────────────────────────────────────────────────────────────────────────
with tab4:
    st.subheader("🆚 전략 비교 – Beta SNP / Beta NDQ / Alpha")

    run_cmp = st.button("▶ 비교 실행 (전체)", type="primary")

    if run_cmp:
        cmp_data_snp = fetch_index("snp", fetch_start)
        cmp_data_ndq = fetch_index("ndq", fetch_start)
        cmp_data_snp = cmp_data_snp[cmp_data_snp.index >= pd.Timestamp(f"{start_year}-01-01")]
        cmp_data_ndq = cmp_data_ndq[cmp_data_ndq.index >= pd.Timestamp(f"{start_year}-01-01")]

        results = {}
        with st.spinner("Beta SNP 백테스트 중..."):
            results["Beta SNP"] = run_beta(cmp_data_snp, P_SNP, annual_budget)
        with st.spinner("Beta NDQ 백테스트 중..."):
            results["Beta NDQ"] = run_beta(cmp_data_ndq, P_NDQ, annual_budget)
        with st.spinner("📦 개별주 수집 중 (Alpha, 최초 약 30초)..."):
            stock_close, spy = fetch_stocks(f"{start_year - 1}-01-01")
        with st.spinner("Alpha 백테스트 중..."):
            results["Alpha"] = run_alpha(cmp_data_snp, stock_close, spy, P_ALPHA, annual_budget)

        # 비교 차트
        st.plotly_chart(fig_compare(results), use_container_width=True)

        # 성과 비교 테이블
        rows = []
        for name, res in results.items():
            m = res.get("metrics", {})
            rows.append({
                "전략": name,
                "총 수익률(%)": m.get("total_return", 0),
                "CAGR(%)":      m.get("annual_return", 0),
                "최대 MDD(%)":  m.get("mdd", 0),
                "Calmar":       m.get("calmar_ratio", 0),
                "Sharpe":       m.get("sharpe_ratio", 0),
                "최종 자산(억)": round(m.get("final_value", 0)/1e8, 2),
            })

        df_cmp = pd.DataFrame(rows)
        st.dataframe(df_cmp.style.highlight_max(
            subset=["총 수익률(%)","CAGR(%)","Calmar","Sharpe","최종 자산(억)"],
            color="rgba(0,208,132,0.3)"
        ).highlight_min(
            subset=["최대 MDD(%)"], color="rgba(255,68,68,0.3)"
        ), use_container_width=True, hide_index=True)

        # 드로우다운 비교
        st.markdown("#### Drawdown 비교")
        dd_fig = go.Figure()
        dd_colors = {"Beta SNP": "#00d084", "Beta NDQ": "#2196f3", "Alpha": "#ff9800"}
        for name, res in results.items():
            eq = res["equity_curve"]
            if not eq.empty:
                pk = eq["yj_val"].cummax()
                dd = ((eq["yj_val"] / pk) - 1) * 100
                dd_fig.add_trace(go.Scatter(x=eq.index, y=dd, name=name,
                                            line=dict(color=dd_colors.get(name), width=1.5)))
        dd_fig.update_layout(template=_DARK, height=320, yaxis_title="Drawdown (%)")
        st.plotly_chart(dd_fig, use_container_width=True)

    else:
        st.info("**비교 실행** 버튼을 눌러 세 전략을 동시에 비교하세요.")
