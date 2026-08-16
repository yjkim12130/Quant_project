"""
아파트 매매/전월세 실거래가 배치 적재

config/regions.yaml 의 지역 x 지정 기간(연월)을 순회하며 data.go.kr 국토교통부 API를 호출해
data/realestate.db 에 적재한다. (지역, 연월) 단위로 ingest_checkpoint 테이블에 완료 여부를
기록하므로, 중간에 중단돼도 재실행 시 이미 끝난 부분은 건너뛰고 이어서 진행한다.

사용법:
    # 스모크테스트 (강남구 1개월만)
    python ingest/fetch_trades.py --regions 11680 --start 202607 --end 202607 --trade sale

    # 본 적재 (서울 전역 + 경기 전역, 최근 5년, 매매+전세)
    python ingest/fetch_trades.py --regions all --start 202108 --end 202607 --trade sale,jeonse

    # 실패한 항목만 재시도
    python ingest/fetch_trades.py --regions all --start 202108 --end 202607 --trade sale,jeonse --retry-failed
"""
import argparse
import sys
import time
from pathlib import Path

import pandas as pd
import requests
import xmltodict
import yaml
import PublicDataReader as pdr

sys.path.insert(0, str(Path(__file__).resolve().parent))
from db import get_connection, is_done, mark_checkpoint  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REGIONS_YAML = ROOT / "config" / "regions.yaml"
API_KEYS_YAML = ROOT / "config" / "api_keys.local.yaml"

TRADE_TYPE_MAP = {"sale": "매매", "jeonse": "전월세"}
RETRY_ATTEMPTS = 3
RETRY_SLEEP_SEC = 3
CALL_INTERVAL_SEC = 0.3  # API 예의상 호출 간격


class QuotaExceeded(Exception):
    """개발계정 일일 트래픽 한도(1,000건/API) 초과 — 이후 호출은 전부 실패하므로 배치 중단용"""


def load_regions(group):
    with open(REGIONS_YAML, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if group == "all":
        items = []
        for g in cfg.values():
            items.extend(g)
        return items
    if group in cfg:
        return cfg[group]
    # 개별 5자리 법정동코드 직접 지정도 허용 (스모크테스트용)
    for g in cfg.values():
        for r in g:
            if r["code"] == group:
                return [r]
    raise ValueError(f"알 수 없는 지역 그룹/코드: {group} (regions.yaml의 그룹명 또는 5자리 코드를 입력하세요)")


def load_service_key():
    if not API_KEYS_YAML.exists():
        raise FileNotFoundError(
            f"{API_KEYS_YAML} 없음 — config/api_keys.example.yaml 을 복사해서 "
            "config/api_keys.local.yaml 로 만들고 발급받은 키를 채워주세요."
        )
    with open(API_KEYS_YAML, encoding="utf-8") as f:
        keys = yaml.safe_load(f) or {}
    key = (keys.get("data_go_kr") or {}).get("transaction_price_key", "")
    if not key:
        raise ValueError("api_keys.local.yaml 의 data_go_kr.transaction_price_key 가 비어있습니다.")
    return key


def month_range(start, end):
    months = pd.period_range(start=start, end=end, freq="M")
    return [m.strftime("%Y%m") for m in months]


def _clean_sale(df, region_code, region_name):
    if df is None or df.empty:
        return pd.DataFrame()
    out = pd.DataFrame(index=df.index)
    out["region_code"] = region_code
    out["region_name"] = region_name
    out["dong_name"] = df.get("umdNm")
    out["complex_name"] = df.get("aptNm")
    out["apt_seq"] = df.get("aptSeq")
    out["jibun"] = df.get("jibun")
    out["exclusive_area"] = pd.to_numeric(df.get("excluUseAr"), errors="coerce")
    y = df.get("dealYear").astype(str)
    m = df.get("dealMonth").astype(str).str.zfill(2)
    d = df.get("dealDay").astype(str).str.zfill(2)
    out["contract_date"] = y + "-" + m + "-" + d
    amt = df.get("dealAmount").astype(str).str.replace(",", "", regex=False).str.strip()
    out["deal_amount"] = pd.to_numeric(amt, errors="coerce")
    out["floor"] = pd.to_numeric(df.get("floor"), errors="coerce")
    out["build_year"] = pd.to_numeric(df.get("buildYear"), errors="coerce")
    out["road_name"] = df.get("roadNm")
    # 해제거래 마커는 'O' (2026-08-14 원본 API 실측: cdealType ∈ {None, 'O'}, cdealDay에 해제일)
    out["cancelled"] = (df.get("cdealType") == "O").astype(int) if "cdealType" in df.columns else 0
    out["fetched_at"] = pd.Timestamp.utcnow().isoformat()
    return out.dropna(subset=["exclusive_area", "deal_amount", "contract_date"])


def _clean_jeonse(df, region_code, region_name):
    if df is None or df.empty:
        return pd.DataFrame()
    out = pd.DataFrame(index=df.index)
    out["region_code"] = region_code
    out["region_name"] = region_name
    out["dong_name"] = df.get("umdNm")
    out["complex_name"] = df.get("aptNm")
    out["jibun"] = df.get("jibun")
    out["exclusive_area"] = pd.to_numeric(df.get("excluUseAr"), errors="coerce")
    y = df.get("dealYear").astype(str)
    m = df.get("dealMonth").astype(str).str.zfill(2)
    d = df.get("dealDay").astype(str).str.zfill(2)
    out["contract_date"] = y + "-" + m + "-" + d
    dep = df.get("deposit").astype(str).str.replace(",", "", regex=False).str.strip()
    out["deposit"] = pd.to_numeric(dep, errors="coerce")
    mr = df.get("monthlyRent").astype(str).str.replace(",", "", regex=False).str.strip()
    out["monthly_rent"] = pd.to_numeric(mr, errors="coerce").fillna(0)
    out["floor"] = pd.to_numeric(df.get("floor"), errors="coerce")
    out["build_year"] = pd.to_numeric(df.get("buildYear"), errors="coerce")
    out["contract_type"] = df.get("contractType")
    out["fetched_at"] = pd.Timestamp.utcnow().isoformat()
    return out.dropna(subset=["exclusive_area", "deposit", "contract_date"])


def _insert(conn, table, df):
    if df.empty:
        return 0
    cols = list(df.columns)
    placeholders = ",".join("?" for _ in cols)
    sql = f"INSERT OR IGNORE INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
    # numpy int64/float64는 sqlite3가 못 받아 BLOB로 저장됨 — 파이썬 네이티브 타입으로 변환
    rows = [
        tuple(None if pd.isna(v) else (v.item() if hasattr(v, "item") else v) for v in row)
        for row in df[cols].itertuples(index=False, name=None)
    ]
    cur = conn.executemany(sql, rows)
    conn.commit()
    return cur.rowcount


def verify_api_response(reader, trade_key, region_code, year_month):
    """PublicDataReader는 API 에러 시 빈 DataFrame을 반환해 '거래 없음'과 구분이 안 됨.
    빈 결과가 나왔을 때 1행짜리 직접 호출로 실제 에러 여부를 판별한다.
    정상이면 None, 에러면 에러 메시지 문자열을 반환."""
    url = reader.meta_dict["아파트"][TRADE_TYPE_MAP[trade_key]]["url"]
    res = requests.get(url, params={
        "serviceKey": requests.utils.unquote(reader.service_key),
        "LAWD_CD": region_code, "DEAL_YMD": year_month, "numOfRows": "1",
    }, timeout=30, verify=False)
    if res.status_code != 200:
        try:
            hdr = xmltodict.parse(res.text)["OpenAPI_ServiceResponse"]["cmmMsgHeader"]
            return f"HTTP {res.status_code}: {hdr.get('errMsg')} (code {hdr.get('returnReasonCode')})"
        except Exception:  # noqa: BLE001
            return f"HTTP {res.status_code}: {res.text[:200]}"
    try:
        header = xmltodict.parse(res.text)["response"]["header"]
        if header["resultCode"] not in ("00", "000"):
            return f"resultCode {header['resultCode']}: {header.get('resultMsg')}"
    except Exception:  # noqa: BLE001
        return f"응답 파싱 실패: {res.text[:200]}"
    return None


def fetch_one(reader, region_code, region_name, year_month, trade_key, conn):
    """지역 x 연월 x 거래유형 1건 조회+적재. 성공 시 True, 실패 시 False."""
    trade_type = TRADE_TYPE_MAP[trade_key]
    table = "trades_sale" if trade_key == "sale" else "trades_jeonse"
    cleaner = _clean_sale if trade_key == "sale" else _clean_jeonse

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            df = reader.get_data(
                property_type="아파트",
                trade_type=trade_type,
                sigungu_code=region_code,
                year_month=year_month,
                translate=False,
                verbose=False,
            )
            if df is None or df.empty:
                err = verify_api_response(reader, trade_key, region_code, year_month)
                if err:
                    if "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in err or "code 22" in err:
                        raise QuotaExceeded(err)
                    raise RuntimeError(err)
            cleaned = cleaner(df, region_code, region_name)
            n = _insert(conn, table, cleaned)
            mark_checkpoint(conn, trade_key, region_code, year_month, "done", row_count=n)
            return True
        except QuotaExceeded:
            raise  # 재시도 무의미 — main에서 배치 전체를 멈춘다 (체크포인트 미기록이라 내일 이어서 진행됨)
        except Exception as e:  # noqa: BLE001 — 배치 적재는 개별 실패로 전체가 죽으면 안 됨
            if attempt == RETRY_ATTEMPTS:
                mark_checkpoint(conn, trade_key, region_code, year_month, "failed", error=str(e)[:300])
                print(f"  [실패] {region_name}({region_code}) {year_month} {trade_type}: {e}")
                return False
            time.sleep(RETRY_SLEEP_SEC * attempt)
    return False


def main():
    ap = argparse.ArgumentParser(description="아파트 실거래가 배치 적재")
    ap.add_argument("--regions", default="all", help="regions.yaml 그룹명(all/seoul/gyeonggi) 또는 5자리 코드")
    ap.add_argument("--start", required=True, help="시작 연월 YYYYMM")
    ap.add_argument("--end", required=True, help="종료 연월 YYYYMM")
    ap.add_argument("--trade", default="sale,jeonse", help="sale,jeonse 중 콤마로 선택")
    ap.add_argument("--retry-failed", action="store_true", help="이전에 failed로 기록된 항목만 재시도")
    args = ap.parse_args()

    regions = load_regions(args.regions)
    months = month_range(args.start, args.end)
    trade_keys = [t.strip() for t in args.trade.split(",") if t.strip() in TRADE_TYPE_MAP]

    service_key = load_service_key()
    reader = pdr.TransactionPrice(service_key=service_key)
    conn = get_connection()

    # 배치 시작 전 키 유효성 1회 선검증 - 키가 죽어있으면 전체를 failed로 도배하지 않고 즉시 중단
    err = verify_api_response(reader, trade_keys[0], regions[0]["code"], months[0])
    if err:
        if "LIMITED_NUMBER_OF_SERVICE_REQUESTS" in err or "code 22" in err:
            print(f"[중단] 오늘 일일 한도가 이미 소진된 상태입니다: {err}")
            print("키 자체는 정상입니다 - 내일(한도 리셋 후) 같은 명령을 다시 실행하면 체크포인트에서 이어서 진행됩니다.")
        else:
            print(f"[중단] API 키 검증 실패: {err}")
            print("활용신청 승인/반영 상태를 data.go.kr 마이페이지에서 확인하세요. (신청 직후라면 최대 1시간 반영 지연 가능)")
        sys.exit(1)

    total = len(regions) * len(months) * len(trade_keys)
    done = skipped = failed = 0
    print(f"대상: 지역 {len(regions)}개 x 연월 {len(months)}개({months[0]}~{months[-1]}) x 거래유형 {trade_keys} = 총 {total}건")

    exhausted = set()  # 일일 한도 소진된 거래유형 (매매/전월세 API 한도가 각각이므로 유형별 추적)
    for region in regions:
        code, name = region["code"], region["name"]
        for ym in months:
            for tk in trade_keys:
                if tk in exhausted:
                    continue
                if args.retry_failed:
                    row = conn.execute(
                        "SELECT status FROM ingest_checkpoint WHERE source=? AND region_code=? AND year_month=?",
                        (tk, code, ym),
                    ).fetchone()
                    if row is not None and row[0] != "failed":
                        skipped += 1
                        continue
                elif is_done(conn, tk, code, ym):
                    skipped += 1
                    continue

                try:
                    ok = fetch_one(reader, code, name, ym, tk, conn)
                except QuotaExceeded as e:
                    exhausted.add(tk)
                    print(f"\n[한도 도달] {TRADE_TYPE_MAP[tk]} API 일일 한도 소진 - 해당 유형 중단: {e}", flush=True)
                    continue
                done += 1 if ok else 0
                failed += 0 if ok else 1
                if done and done % 100 == 0:
                    print(f"  진행: 성공 {done} / 스킵 {skipped} / 실패 {failed}", flush=True)
                time.sleep(CALL_INTERVAL_SEC)
        if exhausted == set(trade_keys):
            print("모든 거래유형 한도 소진 - 내일 같은 명령 재실행 시 체크포인트에서 이어서 진행됩니다.")
            break

    print(f"완료: 성공 {done} / 스킵(이미적재) {skipped} / 실패 {failed}")
    if failed:
        print("실패 항목은 --retry-failed 옵션으로 재시도할 수 있습니다.")
    conn.close()


if __name__ == "__main__":
    main()
