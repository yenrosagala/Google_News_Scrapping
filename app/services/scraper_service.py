import xml.etree.ElementTree as ET
import requests
import concurrent.futures
from typing import Optional, List, Dict

import cloudscraper
from newspaper import Article

from app.core.logger import get_logger
from app.services.ai_service import AIService
from app.services.sentiment_service import sentiment_service
from app.services.database_service import DatabaseService

logger = get_logger("ScraperService")


class ScraperService:
    """Service untuk menangani scraping berita dan alur kerja integrasi AI/DB."""

    def __init__(self) -> None:
        self.scraper = cloudscraper.create_scraper(
            browser={
                "browser": "chrome",
                "platform": "windows",
                "desktop": True,
            }
        )

        self.db = DatabaseService()
        self.ai = AIService()

    def fetch_google_news_rss(self, keyword: str) -> str:
        """Mengambil RSS Google News."""
        encoded_keyword = requests.utils.quote(keyword)
        url = (
            f"https://news.google.com/rss/search?"
            f"q={encoded_keyword}&hl=id&gl=ID&ceid=ID:id"
        )

        try:
            response = self.scraper.get(url, timeout=15)
            response.raise_for_status()
            return response.text

        except requests.RequestException as e:
            logger.error(f"Gagal mengambil RSS: {e}")
            return ""

    def _scrape_article(self, url: str) -> Optional[Dict]:
        """
        Mengambil isi berita menggunakan newspaper4k.
        """

        try:
            article = Article(
                url=url,
                language="id",
                browser_user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/138.0 Safari/537.36"
                ),
            )

            article.download()
            article.parse()

            # Membuat ringkasan apabila memungkinkan
            try:
                article.nlp()
                summary = article.summary
                keywords = article.keywords
            except Exception:
                summary = ""
                keywords = []

            return {
                "title": article.title,
                "text": article.text,
                "summary": summary,
                "authors": article.authors,
                "publish_date": article.publish_date,
                "top_image": article.top_image,
                "keywords": keywords,
            }

        except Exception as e:
            logger.warning(f"Gagal scraping artikel {url}: {e}")
            return None

    def _process_single_article(
        self,
        item: ET.Element,
        keyword: str,
    ) -> Optional[Dict]:
        """
        Memproses satu artikel.
        """

        try:
            link = item.findtext("link")

            if not link:
                return None

            rss_title = item.findtext("title")
            rss_source = item.findtext("source")
            rss_date = item.findtext("pubDate")

            # ===========================
            # Scraping isi artikel
            # ===========================
            article = self._scrape_article(link)

            if article is None:
                return None

            # ===========================
            # AI Analysis
            # ===========================
            ai_result = self.ai.analyze_text(
                title=article["title"],
                content=article["text"],
            )

            summary = (
                ai_result.get("summary")
                if ai_result
                else article["summary"]
            )

            sentiment = sentiment_service.analyze(article["text"])

            return {
                "title": article["title"] or rss_title,
                "url": link,
                "source": rss_source,
                "published_date": (
                    article["publish_date"] or rss_date
                ),
                "keyword": keyword,
                "content": article["text"],
                "summary": summary,
                "sentiment": sentiment,
                "authors": ", ".join(article["authors"]),
                "top_image": article["top_image"],
            }

        except Exception as e:
            logger.warning(
                f"Gagal memproses artikel {item.findtext('title')}: {e}"
            )
            return None

    def execute_scraping_workflow(
        self,
        keyword: str,
        limit: int = 10,
    ) -> int:
        """
        Workflow scraping.
        """

        xml_data = self.fetch_google_news_rss(keyword)

        if not xml_data:
            return 0

        try:
            root = ET.fromstring(xml_data)
            items = root.findall(".//item")[:limit]

            articles: List[Dict] = []

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=5
            ) as executor:

                futures = [
                    executor.submit(
                        self._process_single_article,
                        item,
                        keyword,
                    )
                    for item in items
                ]

                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        articles.append(result)

            if articles:
                count = self.db.save_articles(articles)
                logger.info(
                    f"Berhasil menyimpan {count} artikel untuk keyword '{keyword}'"
                )
                return count

            return 0

        except ET.ParseError as e:
            logger.error(f"Gagal parsing XML: {e}")
            return 0


scraper_service = ScraperService()