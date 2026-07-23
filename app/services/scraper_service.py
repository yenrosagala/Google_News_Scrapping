import xml.etree.ElementTree as ET
import requests
import concurrent.futures
from typing import Optional, List, Dict
import cloudscraper
from app.core.logger import get_logger
from app.services.ai_service import AIService
from app.services.sentiment_service import sentiment_service
from app.services.database_service import DatabaseService

logger = get_logger("ScraperService")

class ScraperService:
    """Service untuk menangani scraping berita dan alur kerja integrasi AI/DB."""

    def __init__(self) -> None:
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
        )
        self.db = DatabaseService() # Inisialisasi instance
        self.ai = AIService()

    def fetch_google_news_rss(self, keyword: str) -> str:
        """Mengambil data RSS feed dari Google News."""
        encoded_keyword = requests.utils.quote(keyword)
        url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=id&gl=ID&ceid=ID:id"
        try:
            response = self.scraper.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.error(f"Gagal fetch RSS untuk {keyword}: {str(e)}")
            return ""

    def _process_single_article(self, item: ET.Element, keyword: str) -> Optional[Dict]:
        """Memproses satu artikel: Parsing, AI Analysis, dan Sentiment."""
        try:
            link = item.findtext('link')
            title = item.findtext('title')
            
            # Logic: Jika tidak ada link, abaikan
            if not link: return None

            # Analisis (Simulasi call ke AI Service yang sudah direfaktor)
            ai_result = AIService.analyze_content(link) 
            
            return {
                "title": title,
                "url": link,
                "source": item.findtext('source'),
                "published_date": item.findtext('pubDate'),
                "keyword": keyword,
                "content": ai_result.get("summary", ""),
                "sentiment": sentiment_service.analyze(ai_result.get("text", ""))
            }
        except Exception as e:
            logger.warning(f"Gagal memproses artikel {item.findtext('title')}: {str(e)}")
            return None

    def execute_scraping_workflow(self, keyword: str, limit: int = 10) -> int:
        """
        Orchestrator utama scraping:
        1. Fetch -> 2. Parallel Processing -> 3. Bulk Save ke DB
        """
        xml_data = self.fetch_google_news_rss(keyword)
        if not xml_data: 
            return 0
        
        try:
            root = ET.fromstring(xml_data)
            items = root.findall('.//item')[:limit]
            articles: List[Dict] = []
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(self._process_single_article, item, keyword): item for item in items}
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result:
                        articles.append(result)
            
            # Integrasi dengan DatabaseService yang sudah kita buat
            if articles:
                count = DatabaseService.save_articles(articles)
                logger.info(f"Berhasil menyimpan {count} artikel untuk keyword: {keyword}")
                return count
            return 0
            
        except ET.ParseError as e:
            logger.error(f"Gagal parsing XML RSS: {str(e)}")
            return 0

scraper_service = ScraperService()