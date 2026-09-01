"""
APScheduler 기반 자동 크롤링 스케줄러
장 시작(08:50) / 장 종료 후(15:40) 자동 실행
"""

import logging
import sys
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from config import SCHEDULE_TIMES
from crawler.naver_discussion import NaverDiscussionCrawler
from database.db import get_active_stocks
from database.schema import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/crawler.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def run_crawl():
    logger.info("=== 크롤링 시작: %s ===", datetime.now().strftime("%Y-%m-%d %H:%M"))
    stocks = get_active_stocks()
    if not stocks:
        logger.warning("모니터링 종목이 없습니다. DB에 종목을 추가하세요.")
        return

    crawler = NaverDiscussionCrawler()
    results = crawler.crawl_stocks(stocks)

    total = sum(results.values())
    logger.info("=== 크롤링 완료: 총 %d건 신규 수집 ===", total)
    for code, cnt in results.items():
        logger.info("  %-12s %d건", code, cnt)


def start_scheduler():
    init_db()
    scheduler = BlockingScheduler(timezone="Asia/Seoul")

    for t in SCHEDULE_TIMES:
        hour, minute = t.split(":")
        scheduler.add_job(
            run_crawl,
            CronTrigger(hour=int(hour), minute=int(minute), timezone="Asia/Seoul"),
            id=f"crawl_{t.replace(':', '')}",
            name=f"Naver 크롤링 ({t})",
        )
        logger.info("스케줄 등록: 매일 %s", t)

    logger.info("스케줄러 시작 (종료: Ctrl+C)")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("스케줄러 종료")


def run_once():
    """단발 실행 (테스트 / 수동 수집용)"""
    init_db()
    run_crawl()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        run_once()
    else:
        start_scheduler()
