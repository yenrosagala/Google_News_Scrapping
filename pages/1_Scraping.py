# pages/1_Scraping.py
import streamlit as st
from app.services.scraper_service import scraper_service
from app.repositories.news_repository import NewsRepository
from app.core.logger import setup_logger

logger = setup_logger("page_scraping")

st.title("📰 Scraper Engine")
st.subheader("Cari dan Analisis Sentimen Berita Secara Real-Time")

# Form Input
with st.form("scraping_form"):
    keyword = st.text_input("Masukkan Kata Kunci (Keyword):", st.session_state.get("current_keyword", ""))
    num_results = st.number_input("Jumlah Berita:", min_value=5, max_value=100, value=20, step=5)
    submit_button = st.form_submit_button("Mulai Scraping")

if submit_button:
    if not keyword.strip():
        st.error("Keyword tidak boleh kosong!")
    else:
        st.session_state["current_keyword"] = keyword
        
        with st.spinner(f"Sedang mengambil {num_results} berita tentang '{keyword}'..."):
            # Panggil service hasil refactor Tahap 3
            articles = scraper_service.execute_scraping_workflow(keyword, num_results)
            
            if articles:
                # Simpan ke database via Repository hasil refactor Tahap 2
                saved_count = NewsRepository.save_articles(articles)
                st.session_state["scraped_data"] = articles
                st.success(f"Berhasil mengambil {len(articles)} artikel! {saved_count} artikel baru disimpan ke DB.")
            else:
                st.warning("Tidak ada berita yang ditemukan atau gagal melakukan parsing.")

# Tampilkan preview data jika ada di session state
if st.session_state.get("scraped_data"):
    st.write("### Preview Data Terakhir")
    st.dataframe(st.session_state["scraped_data"])