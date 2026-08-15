"""데이터 실측 진단 리포트 — docs/algo_spec_v1.md §7 체크리스트 구현

적재(ingest/fetch_trades.py) 후 실행하면 파라미터 확정에 필요한 실측치를 리포트한다.
부분 적재 상태에서도 동작 (적재된 지역만 집계됨 — 헤더에 커버리지 표시).

사용법:
    python scoring/diagnostics.py            # 전체 리포트
    python scoring/diagnostics.py --save     # docs/diagnostics_report.md 로 저장
"""
import argparse
import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scoring.engine import (  # noqa: E402
    Params, get_connection, load_sale, load_jeonse,
    build_price_series, build_complex_meta, attach_groups, factor_rv,
)

ROOT = Path(__file__).resolve().parent.parent


def _section(title):
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def coverage(sale, jeonse, conn):
    _section("적재 커버리지 (리포트 해석 전 필수 확인)")
    ck = pd.read_sql_query("SELECT source, status, COUNT(*) n FROM ingest_checkpoint GROUP BY source, status", conn)
    print(ck.to_string(index=False))
    for name, df in [("매매", sale), ("전세", jeonse)]:
        print(f"{name}: {len(df):,}건 / 지역 {df['region_code'].nunique()}개 / "
              f"기간 {df['month'].min()}~{df['month'].max()} / 단지키 {df['ckey'].nunique():,}개")


def check1_sparsity(sale, params):
    """체크1: 거래 희소성 → roll_window / ffill_limit / min_group_complexes 근거"""
    _section("체크1. 단지×면적밴드별 월 거래건수 분포 (→ 롤링 윈도·이월 한도·그룹 최소기준)")
    panel = build_price_series(sale, "deal_amount", params)
    monthly_n = panel.groupby(["ckey", "area_band"], observed=True)["n_trades"]

    obs = panel["n_trades"]
    zero_share = (obs == 0).mean()
    print(f"패널 관측치 중 실거래 0건인 월 비율: {zero_share:.1%}  (스무딩·이월이 메꾸는 구멍의 크기)")
    print(f"이월(carried)로 채워진 관측 비율: {panel['carried'].mean():.1%}")

    active_months = monthly_n.apply(lambda s: (s > 0).mean())
    print("\n(단지×면적밴드)별 '거래 있는 달' 비율 분포:")
    print(active_months.describe(percentiles=[.1, .25, .5, .75, .9]).round(3).to_string())
    print(f"\n거래 있는 달 비율 < 1/3 (3개월 롤링으로도 듬성한 대상): {(active_months < 1/3).mean():.1%}")
    print(f"→ 판단 가이드: 위 비율이 높으면 roll_window 확대(3→6개월) 또는 ffill_limit 확대 검토")

    # 그룹 크기: 최신 월 단면
    meta = build_complex_meta(sale)
    latest = panel[panel["month"] == panel["month"].max()].merge(meta, on="ckey")
    from scoring.engine import make_group_key
    latest = latest.copy()
    latest["gk"] = make_group_key(latest, panel["month"].max(), params)
    fine_share = latest["gk"].str.contains(r"\|\*\|", regex=True, na=False)
    print(f"\n최신 월 단면 그룹 배정: 동단위 {(~fine_share & latest['gk'].notna()).mean():.1%} / "
          f"시군구 폴백 {fine_share.mean():.1%} / 제외(미달) {latest['gk'].isna().mean():.1%}")
    print("→ 제외 비율이 10%를 넘으면 min_group_complexes 하향(5→3) 검토")
    return panel


def check2_name_join(sale, jeonse):
    """체크2: 매매·전세 단지키 조인 성공률 → 정규화 규칙 필요 여부"""
    _section("체크2. 매매·전세 단지명 조인 성공률 (→ 단지명 정규화 규칙)")
    sale_keys = set(sale["ckey"].unique())
    j_keys = jeonse.groupby("ckey").size()
    matched = j_keys.index.isin(sale_keys)
    print(f"전세 단지키 {len(j_keys):,}개 중 매매와 매칭: {matched.mean():.1%} (키 기준)")
    print(f"전세 거래량 가중 매칭률: {j_keys[matched].sum() / j_keys.sum():.1%} (건수 기준)")
    unmatched = j_keys[~matched].sort_values(ascending=False).head(10)
    if len(unmatched):
        print("\n미매칭 상위 (전세 건수 많은 순 — 정규화 규칙 후보):")
        for k, n in unmatched.items():
            print(f"  {k}  ({n}건)")
    print("→ 건수 기준 매칭률 90% 미만이면 정규화 규칙 보강 필요 (괄호 제거, 차수 표기 통일 등)")


def check3_rv_dist(sale, params):
    """체크3: rv_z 분포 지역 비교 → 임계 σ 타당성"""
    _section("체크3. rv_z 분포 지역 비교 (→ 매수 임계 σ 설정)")
    panel = build_price_series(sale, "deal_amount", params)
    meta = build_complex_meta(sale)
    df = attach_groups(panel, meta, params)
    df = factor_rv(df, params)
    valid = df.dropna(subset=["rv_z"])
    if valid.empty:
        print("rv_z 계산 가능 표본 없음 (관측 월수 부족) — 적재 진행 후 재실행")
        return
    stats = (valid.groupby("region_code")["rv_z"]
             .agg(["count", "mean", "std",
                   lambda s: s.quantile(.05), lambda s: s.quantile(.95),
                   lambda s: (s < params.rv_buy_z).mean()]))
    stats.columns = ["n", "mean", "std", "p5", "p95", f"z<{params.rv_buy_z}"]
    print(stats.round(3).to_string())
    print(f"\n전체: mean={valid['rv_z'].mean():.3f}, std={valid['rv_z'].std():.3f} "
          f"(이론상 0/1에 가까워야 정상 — 크게 벗어나면 lookback·그룹 정의 재점검)")
    print(f"→ 'z<임계' 비율이 지역별로 크게 다르면(예: 2배 이상) 임계를 지역 공통 σ로 쓰는 게 부적절할 수 있음")


def check4_cancel(sale, params):
    """체크4: 해제거래 비율 → CANCEL_FLAG_PCT 확정"""
    _section("체크4. 해제거래 비율 분포 (→ 경고 플래그 임계)")
    print(f"전체 해제비율: {sale['cancelled'].mean():.2%}")
    by_year = sale.groupby(sale["month"].dt.year)["cancelled"].agg(["mean", "size"])
    print("\n연도별:"); print((by_year.rename(columns={"mean": "해제율", "size": "거래수"})
                            .assign(해제율=lambda d: (d['해제율'] * 100).round(2))).to_string())
    recent = sale[sale["month"] >= sale["month"].max() - 12]
    per_cx = recent.groupby("ckey")["cancelled"].agg(["mean", "size"])
    per_cx = per_cx[per_cx["size"] >= 5]  # 표본 5건 미만 단지는 비율 무의미
    for th in (0.05, 0.10, 0.20):
        print(f"최근 1년 해제비율 > {th:.0%} 단지(거래 5건 이상 중): {(per_cx['mean'] > th).mean():.1%}")
    print(f"→ 플래그 대상이 전체의 2~5% 수준이 되도록 CANCEL_FLAG_PCT(현재 {params.cancel_flag_pct:.0%}) 조정")


def check5_jeonse_coverage(sale, jeonse, params):
    """체크5: 전세가율 계산 가능률 → Factor2 커버리지"""
    _section("체크5. 전세가율 계산 가능 단지 비율 (→ Factor2 커버리지)")
    sp = build_price_series(sale, "deal_amount", params)
    jp = build_price_series(jeonse, "deposit", params)
    latest = sp["month"].max()
    s_latest = sp[sp["month"] == latest][["ckey", "area_band"]]
    j_latest = jp[jp["month"] == latest][["ckey", "area_band"]].assign(has_j=True)
    m = s_latest.merge(j_latest, on=["ckey", "area_band"], how="left")
    cov = m["has_j"].fillna(False).mean()
    print(f"최신 월({latest}) 매매 패널 중 전세 패널 매칭: {cov:.1%}")
    m2 = s_latest.assign(rc=s_latest["ckey"].str.split("|").str[0]).merge(j_latest, on=["ckey", "area_band"], how="left")
    print("\n지역별 커버리지:")
    print(m2.groupby("rc")["has_j"].apply(lambda s: s.fillna(False).mean()).round(3).to_string())
    print("→ 커버리지 70% 미만이면 Factor2를 스코어에 넣을 때 결측 중립(0) 처리 유지가 안전")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--save", action="store_true", help="docs/diagnostics_report.md 로 저장")
    args = ap.parse_args()

    buf = io.StringIO()

    class Tee(io.TextIOBase):
        def write(self, s):
            sys.__stdout__.write(s)
            buf.write(s)
            return len(s)

    params = Params()
    conn = get_connection()
    try:
        sale = load_sale(conn)
        jeonse = load_jeonse(conn)
        out = Tee() if args.save else sys.stdout
        with redirect_stdout(out):
            print("# 데이터 실측 진단 리포트 (algo_spec_v1 §7)")
            print(f"생성: {pd.Timestamp.now():%Y-%m-%d %H:%M}")
            coverage(sale, jeonse, conn)
            check1_sparsity(sale, params)
            check2_name_join(sale, jeonse)
            check3_rv_dist(sale, params)
            check4_cancel(sale, params)
            check5_jeonse_coverage(sale, jeonse, params)
    finally:
        conn.close()

    if args.save:
        out_path = ROOT / "docs" / "diagnostics_report.md"
        out_path.write_text("```\n" + buf.getvalue() + "\n```", encoding="utf-8")
        print(f"\n저장됨: {out_path}")


if __name__ == "__main__":
    main()
