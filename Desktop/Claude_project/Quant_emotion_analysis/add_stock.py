"""
모니터링 종목 등록 CLI
사용법: python add_stock.py 005930 삼성전자 KOSPI
"""

import sys
from database.schema import init_db
from database.db import upsert_stock

MARKETS = ("KOSPI", "KOSDAQ", "NASDAQ")

def main():
    if len(sys.argv) != 4:
        print("사용법: python add_stock.py <종목코드> <종목명> <시장>")
        print(f"  시장: {' | '.join(MARKETS)}")
        print("  예시: python add_stock.py 005930 삼성전자 KOSPI")
        sys.exit(1)

    code, name, market = sys.argv[1], sys.argv[2], sys.argv[3].upper()
    if market not in MARKETS:
        print(f"오류: 시장은 {MARKETS} 중 하나여야 합니다.")
        sys.exit(1)

    init_db()
    upsert_stock(code, name, market)
    print(f"등록 완료: [{market}] {code} {name}")

if __name__ == "__main__":
    main()
