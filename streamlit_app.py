import streamlit as st

from app.ui import render_app


st.set_page_config(page_title="Google News Scraper & Analisis Central", layout="wide")
render_app()
