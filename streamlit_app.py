import os
import streamlit as st
from google import genai

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
