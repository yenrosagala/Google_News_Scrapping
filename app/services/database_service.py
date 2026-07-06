import pandas as pd
import sqlite3  # Murni menggunakan sqlite3 standar bawaan Python
from app.core.logger import get_logger
from app.database import dapatkan_koneksi_db, IS_POSTGRES  # Memanggil fungsi koneksi asli proyek Anda

logger = get_logger("DatabaseService")

class DatabaseService:
    def __init__(self):
        pass

    def get_latest_scraped_data(self, limit: int = 50, fallback_mode: bool = False) -> pd.DataFrame:
        """
        [FITUR DASHBOARD] Membaca data berita terbaru secara dinamis.
        Mendukung fallback_mode jika pencarian pertama tidak membuahkan hasil.
        """
        param_char = "%s" if IS_POSTGRES else "?"
        
        # Jika fallback_mode aktif, kita bisa melonggarkan query (contoh: mengambil data tanpa batasan status jika ada)
        # Untuk saat ini, kita pastikan query mengambil ID terbesar secara mutlak sebagai 'last chance'
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
                # Normalisasi nama kolom ke lowercase terlebih dahulu untuk menghindari Case-Sensitive Bug
                df.columns = [col.lower() for col in df.columns]

                # Standarisasi nama kolom secara dinamis (Auto-Mapping) ke ekspektasi UI Streamlit
                rename_dict = {}
                if "keyword" in df.columns: rename_dict["keyword"] = "kata_kunci"
                if "title" in df.columns: rename_dict["title"] = "judul"
                if "source" in df.columns: rename_dict["source"] = "media"
                if "published_date" in df.columns: rename_dict["published_date"] = "waktu_tampilan"
                if "content" in df.columns: rename_dict["content"] = "isi_konten"
                
                # OPTIMASI POP-UP: Pastikan kolom 'url' dipertahankan ke UI Streamlit
                # Jika ingin mengubah nama kolomnya menjadi 'url_bersih' di UI, aktifkan baris di bawah:
                if "url" in df.columns: rename_dict["url"] = "url_bersih"
                
                # SINKRONISASI: Pastikan kolom sentiment dari DB dipetakan ke 'Sentimen' (Kapital sesuai UI Anda)
                if "sentiment" in df.columns: rename_dict["sentiment"] = "Sentimen"
                
                if rename_dict:
                    df = df.rename(columns=rename_dict)
                    
            return df
        except Exception as e:
            logger.error(f"Gagal memuat data scraping {'(Fallback Mode)' if fallback_mode else ''}: {str(e)}")
            return pd.DataFrame()

    def update_sentiment(self, article_id: str, new_sentiment: str) -> bool:
        """[KEWENANGAN ADMIN] Mengubah label Sentimen secara manual di database."""
        param_char = "%s" if IS_POSTGRES else "?"
        
        # SINKRONISASI: Gunakan 'sentiment' huruf kecil sesuai standar penamaan kolom DB umum,
        # atau sesuaikan dengan skema tabel asli Anda (di sini saya asumsikan kolom DB-nya 'sentiment')
        query = f"UPDATE news_articles SET sentiment = {param_char} WHERE id = {param_char}"
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
        
    
    def save_articles(self, articles: list) -> int:
        """Menyimpan list artikel hasil scraping ke dalam database secara massal."""
        if not articles:
            return 0
            
        param_char = "%s" if IS_POSTGRES else "?"
        # Sesuaikan nama kolom di bawah dengan skema asli tabel DB Anda (gunakan lowercase)
        query = f"""
            INSERT INTO news_articles (id, title, url, source, published_date, content, sentiment, keyword)
            VALUES ({param_char}, {param_char}, {param_char}, {param_char}, {param_char}, {param_char}, {param_char}, {param_char})
            ON CONFLICT(id) DO NOTHING
        """
        saved_count = 0
        try:
            conn = dapatkan_koneksi_db()
            cursor = conn.cursor()
            
            for art in articles:
                try:
                    cursor.execute(query, (
                        art["id"],
                        art["title"],
                        art["url"],
                        art["source"],
                        art["published_date"],
                        art["content"],
                        art["sentiment"],
                        art["keyword"]
                    ))
                    # Hitung data yang benar-benar masuk/berubah jika didukung driver
                    saved_count += 1
                except Exception as ins_err:
                    logger.warning(f"Gagal menyimpan satu artikel ID {art['id']}: {str(ins_err)}")
                    
            conn.commit()
            cursor.close()
            conn.close()
            logger.info(f"Berhasil menyimpan {saved_count} artikel baru ke database.")
            return saved_count
        except Exception as e:
            logger.error(f"Gagal eksekusi save_articles ke database: {str(e)}")
            return 0

# Inisialisasi Singleton objek global agar bisa langsung di-import halaman UI
db_service = DatabaseService()