import os
import streamlit as st
from google import genai

import streamlit as st

st.markdown("""
<style>
    /* Global Theme */
    :root {
        --primary: #38BDF8;
        --primary-dark: #0EA5E9;
        --dark-bg: #0F172A;
        --card-bg: rgba(20, 30, 50, 0.95);
        --text-primary: #FFFFFF;
        --text-secondary: #E2E8F0;
        --border-light: rgba(255, 255, 255, 0.25);
    }

    /* Background with strong overlay */
    html, body, .stApp, [data-testid="stAppViewContainer"] {
        background-image: url("https://cdn.jsdelivr.net/gh/yenrosagala/Google_News_Scrapping@main/5630939.jpg");
        background-size: cover;
        background-attachment: fixed;
        background-position: center;
        background-color: #0F172A;
    }

    .stApp::before {
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.88), rgba(30, 41, 59, 0.88));
        pointer-events: none;
        z-index: -1;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: rgba(15, 23, 42, 0.98) !important;
    }

    [data-testid="stSidebar"] > div:first-child {
        background: rgba(20, 30, 50, 0.95) !important;
    }

    /* Main Container */
    [data-testid="stAppViewContainer"] {
        background: transparent;
    }

    /* Cards & Containers */
    .premium-card,
    [data-baseweb="tab-panel"],
    [data-testid="column"] > div,
    .stContainer > div {
        background: var(--card-bg) !important;
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        border: 1px solid var(--border-light) !important;
        border-radius: 12px !important;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5) !important;
        padding: 1.5rem !important;
    }

    .premium-card:hover,
    [data-baseweb="tab-panel"]:hover {
        border-color: var(--primary) !important;
        box-shadow: 0 15px 40px rgba(56, 189, 248, 0.2) !important;
    }

    /* Typography - High Contrast */
    h1, h2, h3, h4, h5, h6 {
        color: #FFFFFF !important;
        font-weight: 700 !important;
        letter-spacing: -0.5px;
    }

    h1 {
        font-size: 2.75rem !important;
        margin-bottom: 1rem !important;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
    }

    h2 {
        font-size: 1.875rem !important;
        margin-bottom: 0.75rem !important;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
    }

    h3 {
        font-size: 1.375rem !important;
        margin-bottom: 0.5rem !important;
    }

    /* Paragraph & Text */
    p, .stMarkdown {
        color: #E2E8F0 !important;
        font-size: 1rem !important;
        line-height: 1.7 !important;
    }

    .stMarkdown p {
        margin-bottom: 0.75rem !important;
    }

    .stMarkdown strong {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    /* Labels - Clear & Bold */
    label {
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 1.05rem !important;
        margin-bottom: 0.75rem !important;
        display: block !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255, 255, 255, 0.12) !important;
        padding: 10px !important;
        border-radius: 10px !important;
        gap: 6px !important;
    }

    .stTabs [data-baseweb="tab"] {
        color: #CBD5E1 !important;
        font-weight: 600 !important;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #38BDF8, #0EA5E9) !important;
        color: #0F172A !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
    }

    .stTabs [data-baseweb="tab-panel"] {
        padding: 1.75rem !important;
        background: var(--card-bg) !important;
    }

    /* Input Fields - Bright & Clear */
    input,
    select,
    textarea,
    [data-baseweb="input"] input,
    [data-baseweb="select"] {
        background: rgba(255, 255, 255, 0.12) !important;
        color: #FFFFFF !important;
        border: 1.5px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 8px !important;
        padding: 0.875rem !important;
        font-size: 1rem !important;
        font-weight: 500;
        transition: all 0.2s ease;
    }

    input:focus,
    select:focus,
    textarea:focus {
        border-color: var(--primary) !important;
        background: rgba(255, 255, 255, 0.15) !important;
        box-shadow: 0 0 0 4px rgba(56, 189, 248, 0.2) !important;
        outline: none !important;
    }

    input::placeholder {
        color: rgba(255, 255, 255, 0.55) !important;
    }

    /* Buttons - Bold & Clear */
    button {
        background: linear-gradient(135deg, #38BDF8, #0EA5E9) !important;
        color: #0F172A !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        padding: 0.875rem 1.75rem !important;
        cursor: pointer !important;
        transition: all 0.3s ease;
        box-shadow: 0 4px 12px rgba(56, 189, 248, 0.25) !important;
    }

    button:hover:not([disabled]) {
        box-shadow: 0 8px 24px rgba(56, 189, 248, 0.4) !important;
        transform: translateY(-2px) !important;
    }

    button[disabled] {
        opacity: 0.4 !important;
        cursor: not-allowed !important;
    }

    button[kind="secondary"] {
        background: rgba(255, 255, 255, 0.15) !important;
        color: #FFFFFF !important;
        border: 1.5px solid rgba(255, 255, 255, 0.3) !important;
        box-shadow: none !important;
    }

    button[kind="secondary"]:hover:not([disabled]) {
        background: rgba(255, 255, 255, 0.25) !important;
        border-color: var(--primary) !important;
    }

    /* Alerts & Info Boxes */
    [data-testid="stAlert"] {
        background: rgba(56, 189, 248, 0.2) !important;
        border-left: 4px solid #38BDF8 !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
        padding: 1.25rem !important;
        font-weight: 500 !important;
    }

    /* Multiselect Tags */
    [data-baseweb="tag"] {
        background: linear-gradient(135deg, rgba(56, 189, 248, 0.3), rgba(14, 165, 233, 0.3)) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(56, 189, 248, 0.5) !important;
        font-weight: 600 !important;
    }

    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }

    ::-webkit-scrollbar-track {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 5px;
    }

    ::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, #38BDF8, #0EA5E9);
        border-radius: 5px;
        border: 2px solid rgba(15, 23, 42, 0.5);
    }

    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(180deg, #0EA5E9, #38BDF8);
    }

    /* Responsive Design */
    @media (max-width: 768px) {
        h1 {
            font-size: 2rem !important;
        }

        h2 {
            font-size: 1.5rem !important;
        }

        label {
            font-size: 0.95rem !important;
        }

        .premium-card, [data-baseweb="tab-panel"] {
            padding: 1.25rem !important;
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
