import os
import streamlit as st
from google import genai

import streamlit as st

st.markdown("""
<style>
    /* Global Theme */
    :root {
        --primary: #38BDF8;
        --dark-bg: #0F172A;
        --card-bg: rgba(15, 23, 42, 0.8);
        --text-primary: #FFFFFF;
        --text-secondary: #CBD5E1;
        --border-light: rgba(255, 255, 255, 0.15);
    }

    /* Background */
    html, body, .stApp, [data-testid="stAppViewContainer"] {
        background-image: url("https://cdn.jsdelivr.net/gh/yenrosagala/Google_News_Scrapping@main/5630939.jpg");
        background-size: cover;
        background-attachment: fixed;
        background-position: center;
    }

    /* Main Container & Cards */
    .stContainer, [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.7), rgba(30, 41, 59, 0.7));
    }

    [data-testid="stSidebar"] {
        background: rgba(15, 23, 42, 0.9) !important;
    }

    .premium-card, [data-baseweb="tab-panel"], [data-testid="column"] > div {
        background: var(--card-bg) !important;
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid var(--border-light) !important;
        border-radius: 16px !important;
        box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.4) !important;
        padding: 1.5rem !important;
        transition: all 0.3s ease;
    }

    .premium-card:hover, [data-baseweb="tab-panel"]:hover {
        border-color: rgba(56, 189, 248, 0.3) !important;
        box-shadow: 0 25px 50px -10px rgba(56, 189, 248, 0.15) !important;
    }

    /* Typography */
    h1, h2, h3 {
        color: var(--text-primary) !important;
        font-weight: 700 !important;
    }

    h1 {
        font-size: 2.5rem !important;
        margin-bottom: 1.5rem !important;
    }

    h2 {
        font-size: 1.75rem !important;
        margin-bottom: 1rem !important;
    }

    h3 {
        font-size: 1.25rem !important;
        margin-bottom: 0.75rem !important;
    }

    .stMarkdown p, .stMarkdown strong, label {
        color: var(--text-secondary) !important;
        line-height: 1.6 !important;
    }

    .stMarkdown strong {
        color: var(--text-primary) !important;
        font-weight: 600 !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255, 255, 255, 0.08) !important;
        padding: 8px !important;
        border-radius: 12px !important;
        gap: 4px !important;
    }

    .stTabs [data-baseweb="tab-panel"] {
        padding: 1.5rem !important;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, var(--primary), #0EA5E9) !important;
        color: var(--dark-bg) !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }

    .stTabs [aria-selected="false"] {
        color: var(--text-secondary) !important;
    }

    /* Input Fields */
    input, select, textarea {
        background: rgba(255, 255, 255, 0.08) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-light) !important;
        border-radius: 8px !important;
        padding: 0.75rem !important;
        transition: all 0.2s ease;
    }

    input:focus, select:focus, textarea:focus {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.1) !important;
    }

    input::placeholder {
        color: rgba(255, 255, 255, 0.4) !important;
    }

    /* Buttons */
    button {
        background: linear-gradient(135deg, var(--primary), #0EA5E9) !important;
        color: var(--dark-bg) !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.75rem 1.5rem !important;
        cursor: pointer !important;
        transition: all 0.3s ease;
    }

    button:hover:not([disabled]) {
        box-shadow: 0 10px 25px -5px rgba(56, 189, 248, 0.4) !important;
        transform: translateY(-2px) !important;
    }

    button[disabled] {
        opacity: 0.5 !important;
        cursor: not-allowed !important;
    }

    button[kind="secondary"] {
        background: rgba(255, 255, 255, 0.1) !important;
        color: var(--text-primary) !important;
        border: 1px solid var(--border-light) !important;
    }

    button[kind="secondary"]:hover:not([disabled]) {
        background: rgba(255, 255, 255, 0.15) !important;
        border-color: var(--primary) !important;
    }

    /* Info & Alert Boxes */
    [data-testid="stAlert"] {
        background: rgba(56, 189, 248, 0.15) !important;
        border-left: 4px solid var(--primary) !important;
        color: var(--text-secondary) !important;
        border-radius: 8px !important;
        padding: 1rem !important;
    }

    /* Labels & Text */
    label {
        font-weight: 600 !important;
        margin-bottom: 0.5rem !important;
        display: block !important;
    }

    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
    }

    ::-webkit-scrollbar-track {
        background: rgba(255, 255, 255, 0.05);
    }

    ::-webkit-scrollbar-thumb {
        background: rgba(56, 189, 248, 0.4);
        border-radius: 4px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: rgba(56, 189, 248, 0.6);
    }

    /* Responsive */
    @media (max-width: 768px) {
        h1 {
            font-size: 1.75rem !important;
        }

        h2 {
            font-size: 1.25rem !important;
        }

        .premium-card, [data-baseweb="tab-panel"] {
            padding: 1rem !important;
        }
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
