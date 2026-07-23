import pandas as pd
import uuid
import streamlit as st
from supabase import create_client, Client
from app.core.logger import get_logger
from app.core import config

logger = get_logger("DatabaseService")

class DatabaseService:
    """Service layer untuk menangani interaksi dengan Supabase."""
    
    def __init__(self):
        self.supabase_url = st.secrets.get("SUPABASE_URL", "https://qbqvtdhaktjbohyfwkvi.supabase.co")
        self.default_api_key = st.secrets.get("SUPABASE_PUBLISHABLE_KEY", "")

    def _get_client(self, custom_api_key: str = None) -> Client:
        """Helper untuk membuat client dengan opsional API Key (untuk admin)."""
        api_key = custom_api_key or self.default_api_key
        if not api_key:
            raise ValueError("API Key Supabase tidak ditemukan!")
        return create_client(self.supabase_url, api_key)

    def get_latest_scraped_data(self, limit: int = 1000) -> pd.DataFrame:
        """Mengambil data berita terbaru dengan pembersihan kolom."""
        try:
            client = self._get_client()
            response = client.table("news_articles").select("*").order("id", desc=True).limit(limit).execute()
            
            if not response.data:
                return pd.DataFrame()
                
            df = pd.DataFrame(response.data)
            
            # Mapping kolom untuk menjaga kompatibilitas dengan UI lama
            mapping = {
                "keyword": "kata_kunci",
                "title": "judul",
                "source": "media",
                "published_date": "waktu_tampilan",
                "content": "isi_konten",
                "sentiment": "Sentimen"
            }
            return df.rename(columns=mapping)
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return pd.DataFrame()

    def save_articles(self, articles: list) -> int:
        """Menyimpan/Upsert artikel dengan proteksi UUID."""
        if not articles:
            return 0
            
        try:
            client = self._get_client()
            payload = [self._prepare_article_row(art) for art in articles]
            response = client.table("news_articles").upsert(payload).execute()
            return len(response.data) if response.data else 0
        except Exception as e:
            logger.error(f"Error saving articles: {e}")
            return 0

    def delete_articles_by_date(self, date_str: str, admin_api_key: str) -> bool:
        """Menghapus artikel berdasarkan tanggal dengan validasi keamanan."""
        # Ambil kunci dari config jika tidak disediakan
        key_to_use = admin_api_key or config.ADMIN_PASSWORD
    
        if key_to_use != config.ADMIN_PASSWORD:
            logger.warning("Upaya akses ilegal ke fitur penghapusan massal.")
            return False           
        try:
            client = self._get_client(custom_api_key=admin_api_key)
            start_dt = f"{date_str}T00:00:00"
            end_dt = f"{date_str}T23:59:59"
            
            response = client.table("news_articles").delete().gte("published_date", start_dt).lte("published_date", end_dt).execute()
            return True
        except Exception as e:
            logger.error(f"Error deleting articles: {e}")
            return False

    def _prepare_article_row(self, art: dict) -> dict:
        """Helper untuk normalisasi format data sebelum masuk DB."""
        url = art.get("url") or art.get("link", "")
        return {
            "id": art.get("id") or str(uuid.uuid5(uuid.NAMESPACE_URL, url)) if url else str(uuid.uuid4()),
            "title": art.get("title") or art.get("judul"),
            "url": url,
            "source": art.get("source") or art.get("media"),
            "published_date": str(art.get("published_date") or art.get("waktu_tampilan")),
            "content": art.get("content") or art.get("isi_konten"),
            "sentiment": str(art.get("sentiment", art.get("Sentimen", "NEUTRAL"))).upper(),
            "keyword": art.get("keyword") or art.get("kata_kunci")
        }

db_service = DatabaseService()