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

    def _scrape_article(
        self,
        url_google_news: str,
        judul_feed: str,
        fallback_text: str = ""
    ) -> Dict:
        """
        Ekstrak teks artikel penuh menggunakan Newspaper4k.
        """

        judul_final = judul_feed
        isi = ""
        url_target = url_google_news or ""
        article = None

        # Decode URL Google News
        try:
            decoded_url = gnewsdecoder(
                url_google_news,
                interval=1,
                proxy=None
            )

            if decoded_url.get("status"):
                url_target = decoded_url["decoded_url"]

        except Exception as e:
            logger.error(f"Gagal decode URL Google News: {e}")

        # Menghindari URL ganda
        if "https" in url_target and url_target.count("https://") > 1:
            url_target = "https://" + url_target.split("https://")[-1]

        try:
            response = self.scraper.get(
                url_target,
                headers=HTTP_HEADERS,
                timeout=12
            )

            if response.status_code == 200:

                html_text = response.text

                # =============================
                # Parsing HTML manual
                # =============================
                teks_html = ekstrak_teks_dari_html(html_text)

                if len(teks_html.strip()) >= 200:
                    isi = teks_html.strip()

                # =============================
                # Newspaper4k menggunakan HTML
                # =============================
                if not isi:

                    article = Article(
                        url_target,
                        language="id",
                        config=NEWSPAPER_CONFIG
                    )

                    article.set_html(html_text)
                    article.parse()

                    if article.text and len(article.text.strip()) >= 150:
                        isi = article.text.strip()

                # =============================
                # Fallback download Newspaper4k
                # =============================
                if not isi:

                    article = Article(
                        url_target,
                        language="id",
                        config=NEWSPAPER_CONFIG
                    )

                    article.download()
                    article.parse()

                    if article.text and len(article.text.strip()) >= 150:
                        isi = article.text.strip()

                # Update judul apabila Newspaper memperoleh judul yang lebih baik
                if (
                    article
                    and article.title
                    and "Google" not in article.title
                ):
                    judul_final = article.title

        except Exception as e:
            logger.warning(
                f"Newspaper4k gagal mengekstrak artikel {url_target}: {e}"
            )

        # =============================
        # Fallback ke deskripsi RSS
        # =============================
        if len(isi.strip()) < 200:

            fallback = bersihkan_teks_html(fallback_text)

            if len(fallback) >= 200:
                isi = fallback
            else:
                isi = ""

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

            judul_feed = item.findtext("title", "")
            fallback_text = item.findtext("description", "")

            hasil = self._scrape_article(
                url_google_news=link,
                judul_feed=judul_feed,
                fallback_text=fallback_text
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
                "sentiment": sentiment_service.analyze(
                    hasil["isi_konten"]
                )
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