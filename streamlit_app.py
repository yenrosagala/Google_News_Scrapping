import streamlit as st
from app.core.config import PAGE_TITLE, PAGE_ICON, LAYOUT
from app.core.logger import get_logger
from app.utils.session import init_state

# 1. Setup Logger
logger = get_logger("MainApp")
logger.info("Aplikasi Google News Scrapper berhasil dimuat.")

# 2. Terapkan Page Config dari Core Config
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout=LAYOUT
)

# 3. Inject CSS Eksternal
try:
    with open("app/assets/style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    logger.warning("File style.css tidak ditemukan di folder assets. Menggunakan style default.")

# 4. Inisialisasi State Awal Aplikasi
init_state("search_keyword", "")
init_state("is_scrapped", False)

# 5. Tampilan Halaman Utama (Home / Landing Page)
st.markdown("<div class='main-header'>📰 Google News Scraper & Sentiment Analyzer</div>", unsafe_allow_html=True)

st.markdown("""
### Selamat Datang di Aplikasi Analisis Berita
Aplikasi ini dirancang untuk membantu Anda melakukan *scraping* berita dari Google News secara otomatis, 
menganalisis sentimen publik, dan mengekspor hasilnya ke dalam format laporan yang siap pakai.

#### 👈 Silakan Pilih Menu di Samping untuk Memulai:
1. **Scraping**: Untuk mengambil data berita terbaru berdasarkan kata kunci.
2. **Dashboard**: Untuk melihat visualisasi data dan analisis sentimen berita yang telah diambil.
""")

st.info("Gunakan menu navigasi di *sidebar* sebelah kiri untuk berpindah halaman.")