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
