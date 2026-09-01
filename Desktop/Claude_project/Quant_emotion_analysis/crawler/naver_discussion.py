"""
네이버 금융 종목 토론방 크롤러
- 종목 코드별 토론글 수집 (제목, 본문, 날짜, 조회수, 추천/비추천)
- 이미 수집한 nid 는 조기 종료로 중복 방지
"""

import logging
import time
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

from config import CRAWL_DELAY, HEADERS, MAX_PAGES_PER_STOCK, MAX_RETRIES
from config import NAVER_BOARD_URL, NAVER_READ_URL
from database.db import get_latest_nid, insert_posts

logger = logging.getLogger(__name__)


@dataclass
class Post:
    stock_code: str
    nid: str
    title: str = ""
    content: str = ""
    author: str = ""
    post_date: str = ""
    views: int = 0
    likes: int = 0
    dislikes: int = 0

    def to_dict(self) -> dict:
        return {
            "stock_code": self.stock_code,
            "nid": self.nid,
            "title": self.title,
            "content": self.content,
            "author": self.author,
            "post_date": self.post_date,
            "views": self.views,
            "likes": self.likes,
            "dislikes": self.dislikes,
        }


class NaverDiscussionCrawler:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    # ------------------------------------------------------------------ #
    #  내부 유틸                                                           #
    # ------------------------------------------------------------------ #

    def _get(self, url: str, params: dict | None = None) -> BeautifulSoup | None:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = self.session.get(url, params=params, timeout=10)
                resp.raise_for_status()
                resp.encoding = "euc-kr"
                return BeautifulSoup(resp.text, "lxml")
            except requests.RequestException as e:
                logger.warning("GET 실패 (시도 %d/%d) %s — %s", attempt, MAX_RETRIES, url, e)
                time.sleep(CRAWL_DELAY * attempt)
        return None

    @staticmethod
    def _safe_int(text: str) -> int:
        try:
            return int(text.replace(",", "").strip())
        except (ValueError, AttributeError):
            return 0

    # ------------------------------------------------------------------ #
    #  목록 페이지 파싱                                                     #
    # ------------------------------------------------------------------ #

    def _parse_list_page(self, soup: BeautifulSoup, stock_code: str) -> list[Post]:
        posts: list[Post] = []
        table = soup.find("table", class_="type2")
        if not table:
            return posts

        for tr in table.select("tr"):
            title_td = tr.find("td", class_="title")
            if not title_td:
                continue

            a_tag = title_td.find("a")
            if not a_tag:
                continue

            href = a_tag.get("href", "")
            nid = ""
            for part in href.split("&"):
                if part.startswith("nid="):
                    nid = part.split("=")[1]
                    break
            if not nid:
                continue

            tds = tr.find_all("td")
            date_text = tds[1].get_text(strip=True) if len(tds) > 1 else ""
            views    = self._safe_int(tds[2].get_text()) if len(tds) > 2 else 0
            likes    = self._safe_int(tds[3].get_text()) if len(tds) > 3 else 0
            dislikes = self._safe_int(tds[4].get_text()) if len(tds) > 4 else 0

            posts.append(Post(
                stock_code=stock_code,
                nid=nid,
                title=a_tag.get_text(strip=True),
                post_date=date_text,
                views=views,
                likes=likes,
                dislikes=dislikes,
            ))
        return posts

    # ------------------------------------------------------------------ #
    #  개별 게시글 본문 파싱                                                #
    # ------------------------------------------------------------------ #

    def _fetch_content(self, stock_code: str, nid: str) -> str:
        soup = self._get(NAVER_READ_URL, params={"code": stock_code, "nid": nid})
        if not soup:
            return ""

        # 네이버 토론방 본문 영역
        content_div = (
            soup.find("div", id="body")
            or soup.find("td", class_="view_cnt")
            or soup.find("div", class_="view_se")
        )
        if content_div:
            return content_div.get_text(separator="\n", strip=True)
        return ""

    # ------------------------------------------------------------------ #
    #  공개 API                                                            #
    # ------------------------------------------------------------------ #

    def crawl_stock(
        self,
        stock_code: str,
        max_pages: int = MAX_PAGES_PER_STOCK,
        fetch_content: bool = True,
    ) -> int:
        """
        종목 1개의 토론방을 크롤링해서 DB에 저장.
        이미 수집한 nid 를 만나면 해당 페이지에서 조기 종료.
        반환값: 새로 삽입된 게시글 수
        """
        latest_nid = get_latest_nid(stock_code)
        total_inserted = 0

        for page in range(1, max_pages + 1):
            soup = self._get(NAVER_BOARD_URL, params={"code": stock_code, "page": page})
            if not soup:
                break

            posts = self._parse_list_page(soup, stock_code)
            if not posts:
                logger.info("[%s] p%d — 게시글 없음, 종료", stock_code, page)
                break

            # 중복 체크 및 본문 수집
            new_posts: list[Post] = []
            stop_flag = False
            for post in posts:
                if latest_nid and int(post.nid) <= int(latest_nid):
                    stop_flag = True
                    break
                if fetch_content:
                    post.content = self._fetch_content(stock_code, post.nid)
                    time.sleep(CRAWL_DELAY)
                new_posts.append(post)

            inserted = insert_posts([p.to_dict() for p in new_posts])
            total_inserted += inserted
            logger.info("[%s] p%d — %d건 수집, %d건 신규 저장", stock_code, page, len(new_posts), inserted)

            if stop_flag:
                logger.info("[%s] 기존 nid 도달 — 조기 종료", stock_code)
                break

            time.sleep(CRAWL_DELAY)

        return total_inserted

    def crawl_stocks(self, stock_list: list[dict], **kwargs) -> dict[str, int]:
        """여러 종목 순차 크롤링. 반환값: {stock_code: inserted_count}"""
        results = {}
        for stock in stock_list:
            code = stock["code"]
            logger.info("크롤링 시작: %s (%s)", stock.get("name", code), code)
            results[code] = self.crawl_stock(code, **kwargs)
        return results
