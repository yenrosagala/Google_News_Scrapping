import os
import streamlit as st
from google import genai

import streamlit as st

st.markdown("""
<style>
    /* 1. Backdrop Global: Mengatur Background Image */
    html, body, .stApp, [data-testid="stAppViewContainer"] {
        background-image: url("https://cdn.jsdelivr.net/gh/yenrosagala/Google_News_Scrapping@main/5630939.jpg") !important;
        background-size: cover !important;
        background-attachment: fixed !important;
        background-position: center !important;
    }

    /* 2. Glassmorphism untuk Container Utama */
    .premium-card, [data-baseweb="tab-panel"] {
        background: rgba(15, 23, 42, 0.75) !important; /* Biru gelap transparan */
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 20px !important;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5) !important;
        padding: 2.5rem !important;
    }

    /* 3. Tipografi agar putih bersih */
    .premium-title, .premium-subtitle, .stMarkdown p, .stMarkdown strong, label {
        color: #FFFFFF !important;
    }

    /* 4. Tab List Styling */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255, 255, 255, 0.1) !important;
        padding: 6px !important;
        border-radius: 12px !important;
    }
    
    .stTabs [aria-selected="true"] {
        background: #38BDF8 !important; /* Warna aksen Sky Blue */
        color: #0F172A !important;
        border-radius: 8px !important;
    }

    /* 5. Input Field Style */
    input {
        background: rgba(255, 255, 255, 0.05) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
    }

    /* 6. Info Box Peninjau/Admin */
    div[style*="background-color: rgb(248, 250, 252)"], 
    div[style*="background-color: rgb(239, 246, 255)"] {
        background: rgba(255, 255, 255, 0.08) !important;
        color: #F1F5F9 !important;
        border-left: 4px solid #38BDF8 !important;
        border-radius: 0 8px 8px 0 !important;
    }

    /* 7. Footer */
    p[style*="text-align: center"] {
        color: #94A3B8 !important;
    }
</style>
""", unsafe_allow_html=True)

# Paksa server Streamlit mengunduh browser bawaan Playwright saat pertama kali jalan
@st.cache_resource
def install_playwright_browsers():
    os.system("playwright install chromium")

install_playwright_browsers()


os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]

# Sekarang Client() akan mendeteksinya tanpa masalah
client = genai.Client()

# Baru masukkan import library Anda yang lain di bawah ini
import nltk
nltk.download('punkt')
nltk.download('punkt_tab')

from app.ui import render_app


st.set_page_config(page_title="Google News Scraper & Analisis Central", layout="wide")
render_app()
