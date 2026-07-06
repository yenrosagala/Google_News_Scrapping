import pandas as pd
import sqlite3  # Murni menggunakan sqlite3 standar bawaan Python (Bebas dari pysqlcipher3)
from app.core.logger import get_logger
from app.database import dapatkan_koneksi_db, IS_POSTGRES  # Memanggil fungsi koneksi asli proyek Anda

logger = get_logger("DatabaseService")

class DatabaseService:
    def __init__(self):
        pass

    def get_latest_scraped_data(self, limit: int = 50) -> pd.DataFrame:
        """[FITUR DASHBOARD] Membaca seluruh data berita terbaru secara dinamis menggunakan SELECT *"""
        param_char = "%s" if IS_POSTGRES else "?"
        
        # Menggunakan SELECT * agar terhindar dari error 'no such column: kata_kunci'
        query = f"""
            SELECT * FROM news_articles
            ORDER BY id DESC
            LIMIT {param_char}
        """
        try:
            # Membuka koneksi melalui fungsi database utama Anda
            conn = dapatkan_koneksi_db()
            df = pd.read_sql_query(query, conn, params=(limit,))
            conn.close()
            
            if not df.empty:
                # Standarisasi nama kolom secara dinamis (Auto-Mapping)
                # Langkah ini mendeteksi nama kolom database (Bahasa Inggris) 
                # lalu menerjemahkannya ke Bahasa Indonesia agar sinkron dengan file 'ui_backup.py' dan Report PDF Anda.
                rename_dict = {}
                if "keyword" in df.columns: rename_dict["keyword"] = "kata_kunci"
                if "title" in df.columns: rename_dict["title"] = "judul"
                if "source" in df.columns: rename_dict["source"] = "media"
                if "published_date" in df.columns: rename_dict["published_date"] = "waktu_tampilan"
                if "content" in df.columns: rename_dict["content"] = "isi_konten"
                if "sentiment" in df.columns: rename_dict["sentiment"] = "Sentimen"
                
                if rename_dict:
                    df = df.rename(columns=rename_dict)
                    
            return df
        except Exception as e:
            logger.error(f"Gagal memuat data scraping terakhir untuk Dashboard: {str(e)}")
            return pd.DataFrame()

    def update_sentiment(self, article_id: str, new_sentiment: str) -> bool:
        """[KEWENANGAN ADMIN] Mengubah label Sentimen secara manual di database."""
        param_char = "%s" if IS_POSTGRES else "?"
        query = f"UPDATE news_articles SET Sentimen = {param_char} WHERE id = {param_char}"
        try:
            conn = dapatkan_koneksi_db()
            cursor = conn.cursor()
            cursor.execute(query, (new_sentiment.upper(), article_id))
            conn.commit()
            rows_affected = cursor.rowcount
            cursor.close()
            conn.close()
            return rows_affected > 0
        except Exception as e:
            logger.error(f"Admin gagal mengubah Sentimen untuk ID {article_id}: {str(e)}")
            return False

    def delete_article(self, article_id: str) -> bool:
        """[KEWENANGAN ADMIN] Menghapus artikel berita berdasarkan ID dari database."""
        param_char = "%s" if IS_POSTGRES else "?"
        query = f"DELETE FROM news_articles WHERE id = {param_char}"
        try:
            conn = dapatkan_koneksi_db()
            cursor = conn.cursor()
            cursor.execute(query, (article_id,))
            conn.commit()
            rows_affected = cursor.rowcount
            cursor.close()
            conn.close()
            return rows_affected > 0
        except Exception as e:
            logger.error(f"Admin gagal menghapus artikel ID {article_id}: {str(e)}")
            return False

# Inisialisasi Singleton objek global agar bisa langsung di-import halaman UI
db_service = DatabaseService()