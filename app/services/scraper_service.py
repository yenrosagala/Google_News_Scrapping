import xml.etree.ElementTree as ET
import hashlib
import requests
import cloudscraper  # Proteksi Cloudflare Bypass
# KODE PERBAIKAN YANG BENAR (Mencari new_decoderv2):
from googlenewsdecoder import gnewsdecoder # IMPORT YANG BENAR DAN AKURAT
from app.core.logger import get_logger

logger = get_logger("ScraperService")

class ScraperService:
    def __init__(self):
        # Inisialisasi cloudscraper dengan simulasi browser desktop
        self.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            }
        )

    def fetch_google_news_rss(self, keyword: str) -> str:
        """Mengambil data XML/RSS mentah dari Google News menggunakan cloudscraper."""
        encoded_keyword = requests.utils.quote(keyword)
        url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=id&gl=ID&ceid=ID:id"
        try:
            response = self.scraper.get(url, timeout=10)
            if response.status_code == 200:
                return response.text
            logger.error(f"Gagal fetch RSS Google News. Status: {response.status_code}")
        except Exception as e:
            logger.error(f"Error saat melakukan request ke Google News: {str(e)}")
        return ""

    def parse_rss_data(self, xml_content: str, keyword: str, limit: int = 10) -> list:
        """Mengurai data RSS, melakukan decode URL asli, dan mengekstrak artikel penuh."""
        articles = []
        if not xml_content:
            return articles

        try:
            root = ET.fromstring(xml_content)
            urls = [item.find('link').text for item in root.findall('.//item') if item.find('link') is not None]
            
            target_urls = urls[:limit]
            logger.info(f"Ditemukan {len(urls)} artikel. Mendecode {len(target_urls)} URL secara lokal...")

            for url in target_urls:
                try:
                    # 1. DECODE URL GOOGLE NEWS MENGGUNAKAN DOKUMENTASI SOURCE GITHUB YANG AKURAT
                    resolved_url = url
                    try:
                        decoded_res = gnewsdecoder(url)
                        if decoded_res and 'decoded_url' in decoded_res:
                            resolved_url = decoded_res['decoded_url']
                    except Exception as e:
                        logger.warning(f"Gagal decode biner URL, fallback ke URL asal: {str(e)}")

                    # 2. Generate ID unik menggunakan MD5 dari URL yang sudah bersih (decoded)
                    article_id = hashlib.md5(resolved_url.encode('utf-8')).hexdigest()

                    # 3. Ambil HTML mentah menggunakan cloudscraper sebelum diserahkan ke newspaper4k
                    html_content = ""
                    try:
                        res = self.scraper.get(resolved_url, timeout=10)
                        if res.status_code == 200:
                            html_content = res.text
                    except Exception as scraper_err:
                        logger.warning(f"Cloudscraper gagal mengambil {resolved_url}: {str(scraper_err)}")

                    # 4. Parsing menggunakan newspaper4k
                    from newspaper import Article
                    article = Article(resolved_url, language='id')
                    
                    if html_content:
                        article.download(input_html=html_content)
                    else:
                        article.download()
                        
                    article.parse()
                    
                    content_text = article.text if article.text else "Konten tidak dapat diekstrak atau halaman kosong."

                    # Format tanggal rilis ke string
                    pub_date = ""
                    if article.publish_date:
                        try:
                            pub_date = article.publish_date.strftime('%Y-%m-%d %H:%M:%S')
                        except AttributeError:
                            pub_date = str(article.publish_date)

                    articles.append({
                        "id": article_id,
                        "title": article.title if article.title else "Untitled",
                        "url": resolved_url,  # URL asli hasil decode masuk ke DataFrame & Database
                        "source": article.source_url if hasattr(article, 'source_url') and article.source_url else resolved_url.split('/')[2],
                        "published_date": pub_date,
                        "content": content_text,
                        "sentiment": "NEUTRAL",
                        "keyword": keyword
                    })
                    logger.info(f"Sukses Ekstrak [{article_id[:8]}]: {article.title[:25]}... ({len(content_text)} karakter)")
                except Exception as e:
                    logger.warning(f"Gagal memproses URL {url}: {str(e)}")
                    continue
                    
        except ET.ParseError as e:
            logger.error(f"Gagal membaca XML menggunakan ElementTree: {str(e)}")
            
        return articles

        
    def execute_scraping_workflow(self, keyword: str, limit: int = 10) -> list:
        """Workflow utama yang dipanggil oleh halaman UI."""
        logger.info(f"Memulai workflow scraping untuk keyword: '{keyword}'")
        xml_data = self.fetch_google_news_rss(keyword)
        articles = self.parse_rss_data(xml_data, keyword=keyword, limit=limit)
        
        # Auto-Save ke DB sebelum di-return ke UI
        if articles:
            from app.services.database_service import db_service # Sesuaikan path import Anda
            db_service.save_articles(articles)
            
        return articles

scraper_service = ScraperService()