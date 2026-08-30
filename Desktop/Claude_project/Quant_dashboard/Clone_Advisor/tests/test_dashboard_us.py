import advisor_dashboard_us as adu


# ── 단위 정규화 ──────────────────────────────────────────────
def test_to_musd_passes_through_millions():
    assert adu.to_musd(6_730_912.0, "Mil. of U.S. $") == 6_730_912.0


def test_to_musd_scales_billions_to_millions():
    # RRPONTSYD만 $B다 — 이 1000배 환산이 순유동성 정확도를 좌우한다
    assert adu.to_musd(0.17, "Bil. of US $") == 170.0


def test_to_musd_returns_none_for_unknown_unit():
    assert adu.to_musd(1.0, "%") is None
    assert adu.to_musd(None, "Mil. of $") is None


def test_to_musd_scales_raw_dollars_to_millions():
    # debt_total은 재무부 API에서 원 단위 달러($)로 온다 — $40T -> $40M단위
    # 40e12 * 1e-6 = 4e7은 float로도 정확히 떨어져 == 비교가 안전하다
    assert adu.to_musd(40_000_000_000_000.0, "$") == 40_000_000.0


# ── 백분위 ───────────────────────────────────────────────────
def test_pct_rank_at_maximum_is_100():
    assert adu.pct_rank([1.0, 2.0, 3.0, 4.0], 4.0) == 100.0


def test_pct_rank_at_minimum_is_25_for_four_values():
    # 자기 자신을 포함해 <= 인 값의 비율
    assert adu.pct_rank([1.0, 2.0, 3.0, 4.0], 1.0) == 25.0


def test_pct_rank_empty_returns_none():
    assert adu.pct_rank([], 1.0) is None


# ── 기간 변화 (주기 불규칙 대응) ──────────────────────────────
def test_change_over_uses_observation_closest_to_target_date():
    obs = [
        {"date": "2026-01-01", "value": 100.0},
        {"date": "2026-06-01", "value": 150.0},   # 약 90일 전에 가장 가까움
        {"date": "2026-08-29", "value": 200.0},
    ]
    assert adu.change_over(obs, 90) == 50.0


def test_change_over_short_history_returns_none():
    assert adu.change_over([{"date": "2026-08-29", "value": 1.0}], 30) is None


# ── 지표 빌더 ────────────────────────────────────────────────
_META_HY = {"id": "hy_oas", "label": "하이일드 OAS", "unit": "%",
            "unit_label": "%", "freq": "일간", "higher_is": "worse"}


def test_build_indicator_propagates_failure_status():
    out = adu.build_indicator({"_status": "NO_FRED_KEY", "observations": []}, _META_HY)
    assert out["_status"] == "NO_FRED_KEY"
    assert out["latest"] is None
    assert out["label"] == "하이일드 OAS"


def test_build_indicator_defaults_missing_status_to_no_data():
    # _status 키 자체가 없는 raw(dict())가 들어와도 허용된 상태값 집합
    # {"ok","NO_FRED_KEY","NO_DATA","NO_REGISTRY"} 밖으로 새지 않아야 한다
    out = adu.build_indicator({}, _META_HY)
    assert out["_status"] == "NO_DATA"


def test_build_indicator_forces_no_data_when_ok_but_series_empty():
    out = adu.build_indicator({"_status": "ok", "observations": []}, _META_HY)
    assert out["_status"] == "NO_DATA"
    assert out["latest"] is None


def test_build_indicator_computes_latest_and_rank():
    obs = [{"date": f"2026-0{i}-01", "value": float(i)} for i in range(1, 9)]
    out = adu.build_indicator({"_status": "ok", "observations": obs}, _META_HY)
    assert out["_status"] == "ok"
    assert out["latest"] == 8.0
    assert out["latest_date"] == "2026-08-01"
    assert out["pct_rank_3y"] == 100.0


def test_build_indicator_assessment_respects_higher_is_worse():
    obs = [{"date": f"2026-0{i}-01", "value": float(i)} for i in range(1, 9)]
    out = adu.build_indicator({"_status": "ok", "observations": obs}, _META_HY)
    assert "고점" in out["assessment"]


def test_build_indicator_assessment_flips_for_higher_is_better():
    meta = dict(_META_HY, higher_is="better")
    obs = [{"date": f"2026-0{i}-01", "value": float(i)} for i in range(1, 9)]
    out = adu.build_indicator({"_status": "ok", "observations": obs}, meta)
    assert "양호" in out["assessment"]


# ── 파생 계산 ────────────────────────────────────────────────
def test_compute_m2_yoy_percent_change():
    obs = [{"date": "2025-08-01", "value": 100.0},
           {"date": "2026-08-01", "value": 110.0}]
    assert adu.compute_m2_yoy(obs) == 10.0


def test_compute_m2_yoy_short_history_returns_none():
    assert adu.compute_m2_yoy([{"date": "2026-08-01", "value": 100.0}]) is None


def test_compute_qt_progress_measures_drawdown_from_peak():
    obs = [{"date": "2026-01-01", "value": 8000.0},
           {"date": "2026-04-01", "value": 9000.0},   # 피크
           {"date": "2026-08-01", "value": 6750.0}]
    out = adu.compute_qt_progress(obs)
    assert out["peak"] == 9000.0
    assert out["peak_date"] == "2026-04-01"
    assert out["current"] == 6750.0
    assert out["drawdown"] == 2250.0
    assert out["drawdown_pct"] == 25.0


def test_compute_hy_ig_gap_in_basis_points():
    hy = {"_status": "ok", "latest": 2.63}
    ig = {"_status": "ok", "latest": 0.79}
    assert adu.compute_hy_ig_gap(hy, ig) == 184.0


def test_compute_hy_ig_gap_none_when_either_missing():
    assert adu.compute_hy_ig_gap({"_status": "NO_DATA", "latest": None},
                                 {"_status": "ok", "latest": 0.79}) is None


def test_compute_net_liquidity_normalizes_billions_before_subtracting():
    # WALCL·WTREGEN은 $M, RRP만 $B — 정규화 없이 빼면 1000배 틀린다
    groups = {"liquidity": {"indicators": [
        {"id": "fed_assets", "_status": "ok", "latest": 6_730_912.0,
         "unit": "Mil. of U.S. $"},
        {"id": "rrp", "_status": "ok", "latest": 0.17, "unit": "Bil. of US $"},
        {"id": "tga", "_status": "ok", "latest": 950_736.0,
         "unit": "Mil. of U.S. $"},
    ]}}
    assert adu.compute_net_liquidity(groups) == 5_780_006.0


def test_compute_net_liquidity_none_when_component_missing():
    groups = {"liquidity": {"indicators": [
        {"id": "fed_assets", "_status": "NO_FRED_KEY", "latest": None,
         "unit": "Mil. of U.S. $"},
    ]}}
    assert adu.compute_net_liquidity(groups) is None


# ── 종합 판정 ────────────────────────────────────────────────
def test_build_assessment_flags_credit_stress_at_high_rank():
    groups = {"credit": {"indicators": [
        {"id": "hy_oas", "_status": "ok", "latest": 8.0, "pct_rank_3y": 95.0},
    ]}}
    rows = adu.build_assessment(groups, {})
    credit = next(r for r in rows if r["id"] == "credit")
    assert credit["verdict"] == "스트레스"


def test_build_assessment_reports_unknown_when_data_missing():
    rows = adu.build_assessment({}, {})
    assert all(r["verdict"] == "판정 불가" for r in rows)
    assert len(rows) == 3


# ── 손편집된 레지스트리 방어 (tab4 예외가 앱 전체를 죽이지 않게) ──────
# macro_series.json은 "코드 수정 없이 지표 추가" 지점이라(스펙 §5) JSON
# 파싱은 되지만 모양이 어긋난 입력이 들어올 수 있다. tab4는 tab1보다 먼저
# 실행되므로 여기서 예외가 새면 종목 분석 탭까지 빈 화면이 된다.
import advisor_macro as am


def test_collect_macro_survives_groups_as_dict():
    # groups가 리스트가 아니라 dict — 순회하면 문자열 키가 나와 .get이 터진다
    assert am.collect_macro({"groups": {"credit": {"indicators": []}}}) == {}


def test_collect_macro_survives_groups_as_string_list():
    assert am.collect_macro({"groups": ["credit", "liquidity"]}) == {}


def test_collect_macro_survives_group_with_no_indicators():
    # 네트워크를 타지 않는다 — 지표가 0개라 fetch 호출이 없다
    out = am.collect_macro({"groups": [{"id": "credit", "label": "신용"}]})
    assert out == {"credit": {}}


def test_collect_macro_skips_non_dict_indicator():
    out = am.collect_macro({"groups": [{"id": "credit", "indicators": ["hy_oas"]}]})
    assert out == {"credit": {}}


def test_collect_macro_survives_registry_without_groups():
    assert am.collect_macro({}) == {}


# ── 백분위 3년 윈도우 (fed_assets만 8년치를 받아오는 데 따른 방어) ────
def test_recent_window_drops_observations_older_than_three_years():
    obs = [{"date": "2018-04-01", "value": 8_965_487.0},   # QT 피크, 창 밖
           {"date": "2024-01-01", "value": 7_000_000.0},
           {"date": "2026-08-01", "value": 6_730_912.0}]
    assert [o["date"] for o in adu.recent_window(obs)] == ["2024-01-01", "2026-08-01"]


def test_pct_rank_3y_ignores_extremes_older_than_three_years():
    # 8년치를 받아오는 fed_assets에서도 pct_rank_3y는 최근 3년만 봐야 한다.
    # 자르지 않으면 2018년 극단값 때문에 백분위가 33.3%로 나온다.
    meta = {"id": "fed_assets", "label": "연준 총자산",
            "unit": "Mil. of U.S. $", "unit_label": "백만$",
            "freq": "주간", "higher_is": "neutral"}
    obs = [{"date": "2018-04-01", "value": 100.0},   # 창 밖 최대값
           {"date": "2024-01-01", "value": 10.0},
           {"date": "2026-08-01", "value": 20.0}]
    out = adu.build_indicator({"_status": "ok", "observations": obs}, meta)
    assert out["pct_rank_3y"] == 100.0          # 최근 3년(10, 20) 중 최대
    assert len(out["series"]) == 3              # 차트용 series는 자르지 않는다


def test_years_override_is_read_from_indicator_meta():
    assert am._years_for({"years": 8}, 3) == 8
    assert am._years_for({}, 3) == 3
    assert am._years_for({"years": "8"}, 3) == 3      # 손편집 오타 방어
    assert am._years_for({"years": 0}, 3) == 3


def test_registry_gives_fed_assets_a_longer_lookback():
    # WALCL의 실제 사이클 피크는 2022-04 — 기본 3년 창에는 들어오지 않는다
    reg = adu.load_macro_series()
    fed = next(i for g in reg["groups"] if g["id"] == "liquidity"
               for i in g["indicators"] if i["id"] == "fed_assets")
    assert fed["years"] >= 5


# ── 순유동성 시계열 (관측치마다 단위 정규화) ─────────────────────────
def _liq_groups(fed=None, rrp=None, tga=None):
    """liquidity 그룹 3종을 시계열로 세팅. 기본값은 전부 정상."""
    return {"liquidity": {"indicators": [
        {"id": "fed_assets", "_status": "ok", "unit": "Mil. of U.S. $",
         "series": fed if fed is not None else [
             {"date": "2026-06-03", "value": 6_800_000.0},
             {"date": "2026-06-10", "value": 6_750_000.0}]},
        {"id": "rrp", "_status": "ok", "unit": "Bil. of US $",
         "series": rrp if rrp is not None else [
             {"date": "2026-06-03", "value": 10.0},     # = 10,000 $M
             {"date": "2026-06-08", "value": 99.0},     # 교집합 밖(일간)
             {"date": "2026-06-10", "value": 20.0}]},   # = 20,000 $M
        {"id": "tga", "_status": "ok", "unit": "Mil. of U.S. $",
         "series": tga if tga is not None else [
             {"date": "2026-06-03", "value": 800_000.0},
             {"date": "2026-06-10", "value": 750_000.0}]},
    ]}}


def test_net_liquidity_series_intersects_dates_and_sorts():
    out = adu.build_net_liquidity_series(_liq_groups())
    # 역레포만 일간이라 06-08은 교집합에서 빠진다 → 주간이 된다
    assert [o["date"] for o in out] == ["2026-06-03", "2026-06-10"]


def test_net_liquidity_series_normalizes_billions_per_observation():
    # 정규화를 빼먹으면 6,800,000 - 10 - 800,000 = 5,999,990 으로 1000배 틀린다
    out = adu.build_net_liquidity_series(_liq_groups())
    assert out[0]["value"] == 6_800_000.0 - 10_000.0 - 800_000.0   # 5,990,000
    assert out[1]["value"] == 6_750_000.0 - 20_000.0 - 750_000.0   # 5,980,000


def test_net_liquidity_series_empty_when_a_component_failed():
    groups = _liq_groups()
    groups["liquidity"]["indicators"][1]["_status"] = "NO_DATA"
    assert adu.build_net_liquidity_series(groups) == []


def test_net_liquidity_series_empty_when_no_common_dates():
    groups = _liq_groups(tga=[{"date": "2025-01-01", "value": 800_000.0}])
    assert adu.build_net_liquidity_series(groups) == []


def test_build_derived_exposes_net_liquidity_series_and_3m_change():
    derived = adu.build_derived(_liq_groups())
    assert len(derived["net_liquidity_series"]) == 2
    assert "net_liquidity_chg_3m" in derived


# ── 유동성 판정 4분면 (스펙 §7: 순유동성 3개월 변화 + M2 YoY 부호) ────
def _liquidity_row(derived):
    return next(r for r in adu.build_assessment({}, derived) if r["id"] == "liquidity")


def test_liquidity_easing_when_both_signals_positive():
    row = _liquidity_row({"net_liquidity": 5_800_000.0,
                          "net_liquidity_chg_3m": 120_000.0, "m2_yoy": 5.4})
    assert row["verdict"] == "완화"
    assert "$5.80T" in row["text"]          # $M 원시값이 아니라 조 단위로


def test_liquidity_tightening_when_both_signals_negative():
    row = _liquidity_row({"net_liquidity": 5_800_000.0,
                          "net_liquidity_chg_3m": -120_000.0, "m2_yoy": -1.2})
    assert row["verdict"] == "긴축"


def test_liquidity_neutral_when_signals_disagree():
    row = _liquidity_row({"net_liquidity": 5_800_000.0,
                          "net_liquidity_chg_3m": 120_000.0, "m2_yoy": -1.2})
    assert row["verdict"] == "중립"


def test_liquidity_falls_back_to_m2_sign_and_says_so():
    # 구 규칙(m2_yoy > 2)이면 1.0%는 "중립"이었다 — 스펙은 부호만 본다
    row = _liquidity_row({"m2_yoy": 1.0})
    assert row["verdict"] == "완화"
    assert "순유동성 근거 없음" in row["text"]


def test_liquidity_unknown_when_no_evidence_at_all():
    assert _liquidity_row({})["verdict"] == "판정 불가"


# ── 금액 표시 포맷 ───────────────────────────────────────────────────
def test_fmt_usd_shrinks_raw_dollars_to_trillions():
    # 15자리("37,900,000,000,000.00")가 좁은 metric 카드를 넘치던 문제
    assert adu.fmt_usd(37_900_000_000_000.0, "$") == "$37.90T"


def test_fmt_usd_picks_billions_and_millions_by_magnitude():
    assert adu.fmt_usd(950_736.0, "Mil. of U.S. $") == "$950.7B"
    assert adu.fmt_usd(0.17, "Bil. of US $") == "$170.0M"


def test_fmt_usd_leaves_non_money_units_alone():
    assert adu.fmt_usd(2.63, "%") == "2.63"
    assert adu.fmt_usd(None, "%") == "—"


def test_fmt_usd_signs_deltas():
    assert adu.fmt_usd(120_000.0, signed=True) == "+$120.0B"
    assert adu.fmt_usd(-120_000.0, signed=True) == "-$120.0B"


# ── chg_1m 기간 라벨 (F4) ────────────────────────────────────────────
# change_over(obs, 30)은 허용오차 없이 "30일에 가장 가까운" 관측치를 고른다.
# 분기 시리즈는 전분기(~91일 전)가 가장 가깝다 — 실제 간격을 보고 라벨을
# 고르지 않으면 전분기 대비 변화가 "1개월"로 잘못 표시된다.
def test_change_over_labeled_is_1_month_for_monthly_series():
    obs = [{"date": "2026-07-01", "value": 10.0},
           {"date": "2026-08-01", "value": 12.0}]
    delta, label = adu.change_over_labeled(obs, 30)
    assert delta == 2.0
    assert label == "1개월"


def test_change_over_labeled_is_1_quarter_for_quarterly_series():
    obs = [{"date": "2026-05-01", "value": 118.0},
           {"date": "2026-08-01", "value": 120.0}]   # 실제 간격 92일
    delta, label = adu.change_over_labeled(obs, 30)
    assert delta == 2.0
    assert label == "1분기"


def test_change_over_labeled_short_history_falls_back_to_requested_period():
    delta, label = adu.change_over_labeled([{"date": "2026-08-29", "value": 1.0}], 30)
    assert delta is None
    assert label == "1개월"


def test_build_indicator_exposes_chg_1m_label_for_quarterly_series():
    meta = dict(_META_HY, freq="분기")
    obs = [{"date": "2026-05-01", "value": 118.0},
           {"date": "2026-08-01", "value": 120.0}]
    out = adu.build_indicator({"_status": "ok", "observations": obs}, meta)
    assert out["chg_1m"] == 2.0
    assert out["chg_1m_label"] == "1분기"


def test_build_indicator_chg_1m_label_defaults_when_no_data():
    out = adu.build_indicator({}, _META_HY)
    assert out["chg_1m_label"] == "1개월"


# ── 경계값 통일: _assess(카드)와 build_assessment(요약)가 66.0/33.0에서
#    같은 판단을 내려야 한다 (F7) ─────────────────────────────────────
def _credit_verdict(rank):
    groups = {"credit": {"indicators": [
        {"id": "hy_oas", "_status": "ok", "latest": 3.0, "pct_rank_3y": rank}]}}
    return next(r for r in adu.build_assessment(groups, {}) if r["id"] == "credit")["verdict"]


def test_high_boundary_rank_agrees_between_card_and_summary():
    assert "고점권" in adu._assess(66.0, "worse")      # 카드: >= 66 → 고점권
    assert _credit_verdict(66.0) == "스트레스"           # 요약도 66.0에서 스트레스


def test_low_boundary_rank_agrees_between_card_and_summary():
    assert "저점권" in adu._assess(33.0, "worse")       # 카드: <= 33 → 저점권
    assert _credit_verdict(33.0) == "안정"               # 요약도 33.0에서 안정


def test_mid_rank_is_neutral_in_both_card_and_summary():
    assert adu._assess(50.0, "worse") == "중간권"
    assert _credit_verdict(50.0) == "경계"


# ── 판정 임계값 분기 커버리지 (F8) ───────────────────────────────────
# build_assessment은 이 기능의 경제적 주장이 모여 있는 곳인데 기존 테스트는
# derived={}만 넘겨 8개 분기 중 1개(신용 스트레스)만 실행했다. 유동성 4분면은
# F3 테스트가 이미 덮으므로 여기선 신용 나머지 분기와 재정 2분기를 채운다.
def test_build_assessment_credit_stable_at_low_rank():
    assert _credit_verdict(10.0) == "안정"


def test_build_assessment_credit_caution_at_mid_rank():
    assert _credit_verdict(50.0) == "경계"


def test_build_assessment_fiscal_burden_increasing_when_ratio_rises():
    groups = {"fiscal": {"indicators": [
        {"id": "debt_gdp", "_status": "ok", "latest": 120.5, "chg_1y": 2.3}]}}
    fiscal = next(r for r in adu.build_assessment(groups, {}) if r["id"] == "fiscal")
    assert fiscal["verdict"] == "부담 가중"


def test_build_assessment_fiscal_sustainable_when_ratio_falls():
    groups = {"fiscal": {"indicators": [
        {"id": "debt_gdp", "_status": "ok", "latest": 118.0, "chg_1y": -1.0}]}}
    fiscal = next(r for r in adu.build_assessment(groups, {}) if r["id"] == "fiscal")
    assert fiscal["verdict"] == "지속가능"


def test_build_assessment_fiscal_unknown_when_data_missing():
    fiscal = next(r for r in adu.build_assessment({}, {}) if r["id"] == "fiscal")
    assert fiscal["verdict"] == "판정 불가"


# ── 레지스트리 unit 계약 (F8) ────────────────────────────────────────
# macro_series.json 오타(예: "Bil. of U.S. $" — 매핑된 "Bil. of US $"와
# 다름)는 to_musd()에서 조용히 None이 된다. 모든 unit이 _UNIT_TO_MUSD에
# 있거나 알려진 비금액 단위인지 계약으로 고정한다.
_NON_MONEY_UNITS = {"%", "% of GDP"}


def test_all_registry_units_are_mapped_or_known_non_money():
    reg = adu.load_macro_series()
    units = {i.get("unit") for g in reg["groups"] for i in g.get("indicators", [])}
    unmapped = units - set(adu._UNIT_TO_MUSD) - _NON_MONEY_UNITS
    assert not unmapped, f"매핑되지 않은 unit: {unmapped}"
