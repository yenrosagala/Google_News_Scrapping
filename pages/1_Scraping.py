import streamlit as st
import pandas as pd
from app.services.scraper_service import scraper_service
# Kita konsisten gunakan db_service yang mengelola save dan fetch data
from app.services.database_service import db_service 
from app.core.logger import setup_logger

logger = setup_logger("page_scraping")

try:
    with open("app/assets/style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    logger.warning("File style.css tidak ditemukan di folder assets. Menggunakan style default.")

st.title("📰 Scraper Engine")
st.subheader("Cari dan Analisis Sentimen Berita Secara Real-Time")

# Form Input User
with st.form("scraping_form"):
    keyword = st.text_input("Masukkan Kata Kunci (Keyword):", st.session_state.get("current_keyword", ""))
    num_results = st.number_input("Jumlah Berita:", min_value=5, max_value=100, value=20, step=5)
    submit_button = st.form_submit_button("Mulai Scraping")

# Eksekusi saat Form disubmit
if submit_button:
    if not keyword.strip():
        st.error("Keyword tidak boleh kosong!")
    else:
        st.session_state["current_keyword"] = keyword
        
        with st.spinner(f"Sedang mengambil {num_results} berita tentang '{keyword}'..."):
            # 1. Jalankan Scraper Pipeline
            articles = scraper_service.execute_scraping_workflow(keyword, num_results)
            
            if articles:
                # 2. Simpan ke database via db_service (Menyimpan URL Bersih)
                saved_count = db_service.save_articles(articles)
                
                st.success(f"✅ Berhasil mengambil {len(articles)} artikel! {saved_count} artikel baru berhasil disimpan ke DB.")
                
                # 3. Paksa Streamlit rerun agar data langsung masuk ke preview database di bawah
                st.rerun()
            else:
                st.warning("Tidak ada berita yang ditemukan atau gagal melakukan parsing.")

st.divider()

# =========================================================
# PREVIEW DATA TERAKHIR DARI DATABASE (BUKAN MEMORI/SCRAPING ULANG)
# =========================================================
st.write("### 📂 Data Hasil Scraping Terakhir di Database")

# Ambil data rilisan terakhir secara instan dari DB (Limit 10 atau sesuai kebutuhan)
df_preview = db_service.get_latest_scraped_data(limit=10)

if not df_preview.empty:
    st.dataframe(df_preview, width='stretch')
else:
    st.info("💡 Belum ada data hasil scraping di dalam database. Silakan masukkan keyword di atas untuk memulai.")