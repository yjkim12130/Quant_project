import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = str(DATA_DIR / "emotion_analysis.db")

NAVER_BOARD_URL = "https://finance.naver.com/item/board.naver"
NAVER_READ_URL = "https://finance.naver.com/item/board_read.naver"

CRAWL_DELAY = 1.5       # 요청 간 딜레이 (초)
MAX_PAGES_PER_STOCK = 5 # 종목당 최대 크롤링 페이지 수
MAX_RETRIES = 3         # 실패 시 재시도 횟수

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://finance.naver.com/",
}

# 크롤링 스케줄 (장 시작/종료 전후)
SCHEDULE_TIMES = ["08:50", "15:40"]
