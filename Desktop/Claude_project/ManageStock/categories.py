DEFAULT_CATEGORIES = [
    "미국 지수 ETF",
    "미국 개별주",
    "미국 산업 ETF",
    "한국 지수 ETF",
    "한국 개별주",
    "한국 산업 ETF",
]

TICKER_PRESETS = {
    "QQQ": "QQQ",
    "QLD": "QLD",
    "엔비디아": "NVDA",
    "테슬라": "TSLA",
    "구글": "GOOGL",
    "KODEX 200": "069500.KS",
    "KODEX 레버리지": "122630.KS",
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "현대차": "005380.KS",
    "네이버": "035420.KS",
}

# dataviz 스킬 검증 완료 팔레트(8슬롯 순서 고정, CVD 안전) 중 1~6번 슬롯을 기본 카테고리에 고정 배정.
CATEGORY_COLORS = {
    "미국 지수 ETF": "#2a78d6",
    "미국 개별주": "#eb6834",
    "미국 산업 ETF": "#1baf7a",
    "한국 지수 ETF": "#eda100",
    "한국 개별주": "#e87ba4",
    "한국 산업 ETF": "#008300",
}
EXTRA_CATEGORY_PALETTE = ["#4a3aa7", "#e34948"]  # 7~8번 슬롯, 사용자 추가 카테고리용
FALLBACK_CATEGORY_COLOR = "#898781"  # 9번째 이후 카테고리는 팔레트 규칙상 "Other" 취급

# 수익률 바차트용 (국내 관례: 상승=빨강, 하락=파랑)
POSITIVE_COLOR = "#e34948"
NEGATIVE_COLOR = "#2a78d6"
NEUTRAL_COLOR = "#898781"

# 자산 추이 라인차트용 (단일 시리즈, sequential 기본 hue)
TREND_COLOR = "#2a78d6"


def get_category_color_map(categories_present, overrides=None):
    """categories_present: list[str] (중복 가능) -> dict[str, str] 카테고리별 색상.
    기본 6개 카테고리는 항상 고정 색상, 그 외는 알파벳/가나다 순으로 EXTRA_CATEGORY_PALETTE를
    소진한 뒤 FALLBACK_CATEGORY_COLOR로 폴백한다(호출 순서가 바뀌어도 색이 안정적으로 유지됨).
    overrides: dict[str, str] — 사용자가 직접 지정한 카테고리별 색상. 지정된 카테고리는
    기본/자동배정 색상보다 항상 우선한다."""
    colors = dict(CATEGORY_COLORS)
    custom = sorted({c for c in categories_present if c not in colors})
    for i, cat in enumerate(custom):
        if i < len(EXTRA_CATEGORY_PALETTE):
            colors[cat] = EXTRA_CATEGORY_PALETTE[i]
        else:
            colors[cat] = FALLBACK_CATEGORY_COLOR
    if overrides:
        colors.update(overrides)
    return colors
