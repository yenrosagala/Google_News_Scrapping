import pandas as pd
from supabase import create_client, Client
from app.core.logger import get_logger
import streamlit as st

logger = get_logger("DatabaseAPIService")

class DatabaseService:
    def __init__(self):
        # Ambil URL dan Anon Key otomatis dari secrets.toml untuk AUTO-READ & AUTO-WRITE (Scraper)
        self.supabase_url = st.secrets.get("SUPABASE_URL", "https://qbqvtdhaktjbohyfwkvi.supabase.co")
        self.default_api_key = st.secrets.get("SUPABASE_ANON_KEY", "")

    def _get_client(self, custom_api_key=None) -> Client:
        """Helper internal untuk membuat HTTP Client Supabase secara dinamis"""
        api_key = custom_api_key if custom_api_key else self.default_api_key
        if not api_key:
            raise ValueError("API Key Supabase tidak ditemukan di secrets.toml!")
        return create_client(self.supabase_url, api_key)

    def get_latest_scraped_data(self, limit: int = 50) -> pd.DataFrame:
        """[OTOMATIS ON LOAD] Membaca data tanpa perlu input password manual di UI"""
        try:
            client = self._get_client()
            response = client.table("news_articles")\
                             .select("*")\
                             .order("id", descending=True)\
                             .limit(limit)\
                             .execute()
            
            data = response.data
            if not data:
                return pd.DataFrame()
                
            df = pd.DataFrame(data)
            
            # Standarisasi nama kolom database lama ke ekspektasi UI Streamlit Anda
            rename_dict = {
                "keyword": "kata_kunci",
                "title": "judul",
                "source": "media",
                "published_date": "waktu_tampilan",
                "content": "isi_konten",
                "url": "url",
                "sentiment": "Sentimen"
            }
            rename_dict = {k: v for k, v in rename_dict.items() if k in df.columns}
            if rename_dict:
                df = df.rename(columns=rename_dict)
                
            return df
        except Exception as e:
            logger.error(f"Gagal memuat data via REST API: {str(e)}")
            return pd.DataFrame()

    def save_articles(self, articles: list) -> int:
        """[OTOMATIS PASCA SCRAPING] Menyimpan hasil scraping via API upsert"""
        if not articles:
            return 0
            
        try:
            client = self._get_client()
            payload = []
            for art in articles:
                payload.append({
                    "id": art.get("id"),
                    "title": art.get("title") or art.get("judul"),
                    "url": art.get("url") or art.get("link"),
                    "source": art.get("source") or art.get("media"),
                    "published_date": str(art.get("published_date") or art.get("waktu_tampilan")),
                    "content": art.get("content") or art.get("isi_konten"),
                    "sentiment": art.get("sentiment", art.get("Sentimen", "NEUTRAL")).upper(),
                    "keyword": art.get("keyword") or art.get("kata_kunci")
                })
            
            # .upsert() otomatis mengabaikan atau mengupdate data jika ID sudah ada
            response = client.table("news_articles").upsert(payload).execute()
            return len(response.data) if response.data else 0
        except Exception as e:
            logger.error(f"Scraper gagal menyimpan via REST API: {str(e)}")
            return 0

    # =========================================================
    # MUTASI DATA (WAJIB USER INPUT SERVICE ROLE KEY SEBAGAI PASSWORD)
    # =========================================================

    def update_sentiment(self, article_id: str, new_sentiment: str, admin_api_key: str) -> bool:
        """Mengubah label Sentimen menggunakan Service Role Key dari input user"""
        try:
            client = self._get_client(custom_api_key=admin_api_key)
            response = client.table("news_articles")\
                             .update({"sentiment": new_sentiment.upper()})\
                             .eq("id", article_id)\
                             .execute()
            return len(response.data) > 0
        except Exception as e:
            st.error(f"❌ Otorisasi Gagal: 'Password' Service Key salah atau ditolak.")
            return False

    def delete_article(self, article_id: str, admin_api_key: str) -> bool:
        """Menghapus artikel tunggal menggunakan Service Role Key dari input user"""
        try:
            client = self._get_client(custom_api_key=admin_api_key)
            response = client.table("news_articles")\
                             .delete()\
                             .eq("id", article_id)\
                             .execute()
            return len(response.data) > 0
        except Exception as e:
            st.error(f"❌ Otorisasi Gagal: 'Password' Service Key salah atau ditolak.")
            return False

    def delete_articles_by_date(self, date_str: str, admin_api_key: str) -> bool:
        """Menghapus artikel massal menggunakan Service Role Key dari input user"""
        try:
            client = self._get_client(custom_api_key=admin_api_key)
            start_dt = f"{date_str}T00:00:00"
            end_dt = f"{date_str}T23:59:59"
            
            response = client.table("news_articles")\
                             .delete()\
                             .gte("published_date", start_dt)\
                             .lte("published_date", end_dt)\
                             .execute()
            return len(response.data) > 0
        except Exception as e:
            st.error(f"❌ Otorisasi Gagal: 'Password' Service Key salah atau ditolak.")
            return False

# Inisialisasi Singleton objek global
db_service = DatabaseService()