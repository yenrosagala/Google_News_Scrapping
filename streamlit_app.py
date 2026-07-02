import os
import streamlit as st
from google import genai

import streamlit as st

st.markdown("""
<style>
    /* =========================================================================
       1. VARIABLES & GLOBAL THEME
       ========================================================================= */
    :root {
        --primary: #38BDF8;
        --primary-dark: #0EA5E9;
        --dark-bg: #0F172A;
        --card-bg: rgba(20, 30, 50, 0.95);
        --text-primary: #FFFFFF;
        --text-secondary: #E2E8F0;
        --border-light: rgba(255, 255, 255, 0.25);
    }

    html, body, .stApp, [data-testid="stAppViewContainer"] {
        background-image: url("https://cdn.jsdelivr.net/gh/yenrosagala/Google_News_Scrapping@main/5630939.jpg");
        background-size: cover;
        background-attachment: fixed;
        background-position: center;
        background-color: var(--dark-bg);
    }

    .stApp::before {
        content: "";
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.88), rgba(30, 41, 59, 0.88));
        pointer-events: none;
        z-index: -1;
    }

    /* =========================================================================
       2. CONTAINERS, CARDS & SIDEBAR
       ========================================================================= */
    [data-testid="stSidebar"] { background: rgba(15, 23, 42, 0.98) !important; }
    [data-testid="stSidebar"] > div:first-child { background: rgba(20, 30, 50, 0.95) !important; }
    
    .premium-card, [data-baseweb="tab-panel"], [data-testid="column"] > div, .stContainer > div {
        background: var(--card-bg) !important;
        backdrop-filter: blur(8px);
        border: 1px solid var(--border-light) !important;
        border-radius: 12px !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5) !important;
        padding: 1.5rem !important;
    }

    /* =========================================================================
       3. TYPOGRAPHY & LABELS
       ========================================================================= */
    h1, h2, h3, h4, h5, h6 { color: var(--text-primary) !important; font-weight: 700 !important; }
    p, .stMarkdown { color: var(--text-secondary) !important; line-height: 1.7 !important; }
    .stMarkdown strong { color: var(--text-primary) !important; }

    label {
        color: var(--text-primary) !important;
        font-weight: 700 !important;
        font-size: 1.05rem !important;
        margin-bottom: 0.75rem !important;
        display: block !important;
    }

    /* Target khusus untuk strong di tab panel */
    div[role="tabpanel"] strong, div[role="tabpanel"] b, #tabs-bui31-tabpanel-1 strong {
        color: var(--primary) !important;
        font-weight: 800 !important;
        text-shadow: 0px 0px 8px rgba(56, 189, 248, 0.5) !important;
    }

    /* =========================================================================
       4. INPUTS, BUTTONS & TABS
       ========================================================================= */
    /* Input & Select */
    input, select, textarea, [data-baseweb="input"] input, [data-baseweb="select"] {
        background: rgba(255, 255, 255, 0.12) !important;
        color: var(--text-primary) !important;
        border: 1.5px solid var(--border-light) !important;
        border-radius: 8px !important;
        padding: 0.875rem !important;
    }

    input:focus { border-color: var(--primary) !important; box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.2) !important; }

    /* Buttons */
    button {
        background: linear-gradient(135deg, var(--primary), var(--primary-dark)) !important;
        color: var(--dark-bg) !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        padding: 0.875rem 1.75rem !important;
        transition: all 0.3s ease;
    }

    button[kind="secondary"] {
        background: rgba(255, 255, 255, 0.15) !important;
        color: var(--text-primary) !important;
        border: 1.5px solid var(--border-light) !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        display: flex !important;
        justify-content: center !important; /* Mengatur elemen anak ke tengah */
        gap: 20px !important;              /* Memberi jarak antar tab agar tidak menempel */
        background: transparent !important; /* Opsional: sesuaikan dengan tema Anda */
    }

    /* 2. Opsional: Memastikan tombol tab memiliki lebar yang proporsional */
    .stTabs [data-testid="stTab"] {
        flex: 0 1 auto !important;         /* Tab hanya memakan ruang sesuai isi teks */
        min-width: 120px !important;       /* Memberikan lebar minimum agar rapi */
    }
    /* =========================================================================
       5. UTILS & RESPONSIVE
       ========================================================================= */
    [data-testid="stAlert"] {
        background: rgba(56, 189, 248, 0.2) !important;
        border-left: 4px solid var(--primary) !important;
        color: var(--text-primary) !important;
    }

    [data-baseweb="tag"] {
        background: linear-gradient(135deg, rgba(56, 189, 248, 0.3), rgba(14, 165, 233, 0.3)) !important;
        color: var(--text-primary) !important;
        border: 1px solid rgba(56, 189, 248, 0.5) !important;
    }

    ::-webkit-scrollbar { width: 10px; height: 10px; }
    ::-webkit-scrollbar-thumb { background: linear-gradient(180deg, var(--primary), var(--primary-dark)); border-radius: 5px; }

    @media (max-width: 768px) {
        h1 { font-size: 2rem !important; }
        .premium-card { padding: 1.25rem !important; }
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
