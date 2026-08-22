"""ATR(Average True Range) 기반 상대 변동성 계산.

여기서 말하는 '베타'는 통계적 베타(수익률 회귀계수)가 아니라 변동성 크기의 비율이다.
상관관계나 방향성은 보지 않으므로, 기준 종목과 무상관인 자산도 변동폭만 비슷하면 1.0 근처가 나온다.

창 길이(ATR_TARGET_WINDOW)를 126일로 잡은 근거:
- 정확도로는 창을 고를 수 없다. QLD(QQQ 2배 레버리지)의 실측 오차가 14일~252일 구간에서
  0.007~0.009로 사실상 동일했다. 선택 기준은 오직 추정치의 안정성이다.
- 월간 베타 변동폭(리밸런싱 회전율의 대리지표)은 14일 창에서 0.34~0.80으로 노이즈 수준이지만
  126일 창에서 0.15~0.21까지 떨어진다. 252일이 가장 안정적이나(0.08~0.12) 신규 상장 ETF가
  대부분 계산 불가가 되어 실무적으로 쓸 수 없다.
- 경험칙: 창 >= 리밸런싱 주기 x 2~4. 126일은 분기 리밸런싱에 대응한다.
"""
import pandas as pd

ATR_BENCHMARK = "QQQM"
ATR_TARGET_WINDOW = 126  # 약 6개월
ATR_MIN_WINDOW = 63      # 약 3개월. 상장 3개월 미만은 어떤 값도 신뢰할 수 없어 계산하지 않는다.
ATR_HISTORY_PERIOD = "1y"


def true_range(ohlc_df):
    """max(고가-저가, |고가-전일종가|, |저가-전일종가|). 첫 봉은 전일종가가 없어 NaN."""
    prev_close = ohlc_df["Close"].shift(1)
    candidates = pd.concat([
        ohlc_df["High"] - ohlc_df["Low"],
        (ohlc_df["High"] - prev_close).abs(),
        (ohlc_df["Low"] - prev_close).abs(),
    ], axis=1)
    # max(axis=1)은 NaN을 건너뛰므로 첫 봉에서 일중폭이 남는다. 명시적으로 NaN 처리한다.
    return candidates.max(axis=1).where(prev_close.notna())


def atr_pct(ohlc_df, window=ATR_TARGET_WINDOW):
    """최근 window개 True Range의 평균을 최종 종가로 나눈 값.
    통화와 주가 수준이 달라도 비교할 수 있도록 종가 대비 비율로 정규화한다.
    봉이 모자라거나 종가가 0이면 None."""
    if len(ohlc_df) < window + 1:
        return None
    tr = true_range(ohlc_df).dropna()
    if len(tr) < window:
        return None
    last_close = ohlc_df["Close"].iloc[-1]
    if not last_close:
        return None
    return float(tr.iloc[-window:].mean() / last_close)


def compute_atr_betas(histories, benchmark=ATR_BENCHMARK,
                      target_window=ATR_TARGET_WINDOW, min_window=ATR_MIN_WINDOW):
    """histories: dict[str, DataFrame] — High/Low/Close를 가진 일봉.

    returns dict[str, dict]: {"beta": float, "window": int, "provisional": bool}.
    계산할 수 없는 종목은 결과에서 빠진다(기준 종목을 못 구하면 전체가 빈 dict).

    상장한 지 얼마 안 돼 봉이 모자란 종목은 창을 줄여서 재되, 기준 종목도 같은 창으로 다시
    재서 같은 기간끼리 비교한다. 그러지 않으면 신규 종목의 3개월치와 기준의 6개월치를 비교하는
    셈이 되어 서로 다른 시장 국면이 섞인다. 이렇게 계산된 값은 provisional=True로 표시한다.
    """
    benchmark_df = histories.get(benchmark)
    if benchmark_df is None or len(benchmark_df) - 1 < min_window:
        return {}
    benchmark_capacity = len(benchmark_df) - 1

    betas = {}
    for ticker, ohlc_df in histories.items():
        window = min(target_window, len(ohlc_df) - 1, benchmark_capacity)
        if window < min_window:
            continue
        ticker_atr = atr_pct(ohlc_df, window)
        benchmark_atr = atr_pct(benchmark_df, window)
        if ticker_atr is None or not benchmark_atr:
            continue
        betas[ticker] = {
            "beta": ticker_atr / benchmark_atr,
            "window": window,
            "provisional": window < target_window,
        }
    return betas


def tickers_needed(holding_tickers):
    """보유 티커에 기준 종목을 더한 조회 대상. 중복은 제거하되 순서는 유지한다.
    기준 종목이 없으면 어떤 베타도 계산할 수 없으므로 보유하지 않아도 반드시 함께 조회한다."""
    return list(dict.fromkeys(list(holding_tickers) + [ATR_BENCHMARK]))


def beta_map(atr_info):
    """compute_atr_betas 결과에서 ticker -> beta 만 뽑는다."""
    return {ticker: info["beta"] for ticker, info in atr_info.items()}


def provisional_tickers(atr_info):
    """창을 줄여 계산해 신뢰도가 낮은 종목."""
    return [ticker for ticker, info in atr_info.items() if info["provisional"]]
