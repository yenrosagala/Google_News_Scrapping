import xml.etree.ElementTree as ET
import requests
import concurrent.futures
from typing import Optional, List, Dict

import cloudscraper
from googlenewsdecoder import gnewsdecoder
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
        keyword = requests.utils.quote(keyword)
        main_url = (
            f"https://news.google.com/rss/search?"
            f"q={keyword}&hl=id&gl=ID&ceid=ID:id"
        )

        #use plywriht to scrape all url in xphat and save in urls
        # for each url in urls: use newspaper tu scrape the content
        try:
            response = self.scraper.get(main_url, timeout=15)
            response.raise_for_status()
            return response.text

        except requests.RequestException as e:
            logger.error(f"Gagal mengambil RSS: {e}")
            return ""

    def _scrape_article(
    self,
    url_google_news: str,
    judul_feed: str,
    fallback_text: str = ""
) -> Dict:
    """
    Mengekstrak isi artikel menggunakan Google News Decoder
    dan Newspaper4k.
    """

    judul_final = judul_feed
    isi = ""
    url_target = url_google_news or ""

    # Decode URL Google News
    try:
        decoded = gnewsdecoder(
            url_google_news,
            interval=1,
            proxy=None
        )

        if decoded.get("status"):
            url_target = decoded["decoded_url"]

    except Exception as e:
        logger.warning(f"Gagal decode URL: {e}")

    # Membersihkan URL ganda
    if "https://" in url_target and url_target.count("https://") > 1:
        url_target = "https://" + url_target.split("https://")[-1]

    try:

        article = Article(
            url=url_target,
            language="id"
        )

        article.download()
        article.parse()

        if article.text:
            isi = article.text.strip()

        if article.title and "Google" not in article.title:
            judul_final = article.title

    except Exception as e:
        logger.warning(
            f"Gagal ekstraksi artikel {url_target}: {e}"
        )

    # fallback ke description RSS
    if len(isi) < 200:
        isi = fallback_text.strip()

    return {
        "judul": judul_final,
        "isi_konten": isi,
        "url_target": url_target,
    }

   def _process_single_article(
    self,
    item: ET.Element,
    keyword: str
) -> Optional[Dict]:

    try:

        link = item.findtext("link")

        if not link:
            return None

        hasil = self._scrape_article(
            url_google_news=link,
            judul_feed=item.findtext("title", ""),
            fallback_text=item.findtext("description", "")
        )

        if not hasil["isi_konten"]:
            return None

        return {
            "title": hasil["judul"],
            "url": hasil["url_target"],
            "source": item.findtext("source"),
            "published_date": item.findtext("pubDate"),
            "keyword": keyword,
            "content": hasil["isi_konten"],
            "sentiment": sentiment_service.analyze_text(
                hasil["isi_konten"]
            ),
        }

    except Exception as e:
        logger.warning(
            f"Gagal memproses artikel: {e}"
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