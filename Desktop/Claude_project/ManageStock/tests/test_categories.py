import categories


def test_default_categories_all_have_colors():
    for cat in categories.DEFAULT_CATEGORIES:
        assert cat in categories.CATEGORY_COLORS


def test_default_category_colors_are_unique():
    colors = [categories.CATEGORY_COLORS[c] for c in categories.DEFAULT_CATEGORIES]
    assert len(colors) == len(set(colors))


def test_ticker_presets_contains_example_entries():
    assert categories.TICKER_PRESETS["QQQ"] == "QQQ"
    assert categories.TICKER_PRESETS["삼성전자"] == "005930.KS"


def test_get_category_color_map_uses_known_colors_for_defaults():
    color_map = categories.get_category_color_map(["한국 개별주", "미국 지수 ETF"])
    assert color_map["한국 개별주"] == categories.CATEGORY_COLORS["한국 개별주"]
    assert color_map["미국 지수 ETF"] == categories.CATEGORY_COLORS["미국 지수 ETF"]


def test_get_category_color_map_assigns_extra_palette_to_custom_categories():
    color_map = categories.get_category_color_map(["가상자산", "원자재"])
    assert color_map["가상자산"] == categories.EXTRA_CATEGORY_PALETTE[0]
    assert color_map["원자재"] == categories.EXTRA_CATEGORY_PALETTE[1]


def test_get_category_color_map_falls_back_beyond_extra_palette():
    custom = ["카테고리A", "카테고리B", "카테고리C"]
    color_map = categories.get_category_color_map(custom)
    assert color_map["카테고리C"] == categories.FALLBACK_CATEGORY_COLOR


def test_get_category_color_map_is_deterministic_regardless_of_input_order():
    map1 = categories.get_category_color_map(["가상자산", "원자재"])
    map2 = categories.get_category_color_map(["원자재", "가상자산"])
    assert map1 == map2


def test_get_category_color_map_override_wins_for_default_category():
    color_map = categories.get_category_color_map(
        ["한국 개별주"], overrides={"한국 개별주": "#123456"}
    )
    assert color_map["한국 개별주"] == "#123456"


def test_get_category_color_map_override_wins_for_custom_category():
    color_map = categories.get_category_color_map(
        ["가상자산"], overrides={"가상자산": "#abcdef"}
    )
    assert color_map["가상자산"] == "#abcdef"


def test_get_category_color_map_without_overrides_unaffected():
    color_map = categories.get_category_color_map(["한국 개별주"])
    assert color_map["한국 개별주"] == categories.CATEGORY_COLORS["한국 개별주"]
