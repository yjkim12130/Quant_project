import advisor_dashboard as ad


# ── build_yield_curve _status 누수 방어 (F6) ───────────────────────────
# build_indicator(advisor_dashboard_us.py)에서 이미 고친 것과 같은 결함:
# "_status" 키 자체가 없으면 status는 None이고, `status != "ok"`만 보면
# None이 그대로 새어 나간다. e787eab/48491f0의 수정을 형제 함수에도 편다.
def test_build_yield_curve_defaults_missing_status_to_no_data():
    out = ad.build_yield_curve({})
    assert out["_status"] == "NO_DATA"


def test_build_yield_curve_forces_no_data_when_ok_but_series_empty():
    out = ad.build_yield_curve({"_status": "ok", "series": []})
    assert out["_status"] == "NO_DATA"


def test_build_yield_curve_propagates_real_failure_status():
    out = ad.build_yield_curve({"_status": "NO_YFINANCE", "series": [],
                                 "_msg": "yfinance 미설치"})
    assert out["_status"] == "NO_YFINANCE"
    assert out["_msg"] == "yfinance 미설치"


def test_build_yield_curve_ok_with_data_computes_spreads():
    raw = {"_status": "ok", "series": [
        {"date": "2026-08-01", "us3m": 4.30, "us10y": 4.10, "us30y": 4.60},
        {"date": "2026-08-29", "us3m": 4.20, "us10y": 4.15, "us30y": 4.65},
    ]}
    out = ad.build_yield_curve(raw)
    assert out["_status"] == "ok"
    assert out["latest"]["t10y3m"] == -5.0     # (4.15-4.20)*100
