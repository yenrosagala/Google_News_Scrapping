import os
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "berita_google_news.db"

DB_URL_TEMPLATE = str(
    st.secrets.get("DATABASE_URL_TEMPLATE", str(DEFAULT_DB_PATH))
)

IS_POSTGRES = (
    DB_URL_TEMPLATE.startswith("postgresql://")
    or DB_URL_TEMPLATE.startswith("postgres://")
)


# ======================================================
# UTILITAS DATABASE
# ======================================================

def _resolve_sqlite_path(db_url):
    if not db_url:
        return str(DEFAULT_DB_PATH)

    if db_url.startswith("sqlite:///"):
        return db_url.replace("sqlite:///", "", 1)

    if db_url.startswith("sqlite://"):
        return db_url.replace("sqlite://", "", 1)

    if os.path.isabs(db_url):
        return db_url

    return str(PROJECT_ROOT / db_url)


# ======================================================
# LOGIN
# ======================================================

def cek_autentikasi_manual():
    if "db_authenticated" not in st.session_state:
        st.session_state.db_authenticated = False

    if "user_type" not in st.session_state:
        st.session_state.user_type = None  # "umum" atau "login"

    if "saved_db_password" not in st.session_state:
        st.session_state.saved_db_password = ""

    # kalau sudah login langsung keluar
    if st.session_state.db_authenticated:
        return

    # --- STYLE PREMIUM SCANDINAVIAN / SAAS MODERN ---
    st.markdown("""
        <style>
        /* Menyembunyikan header default Streamlit agar aplikasi terasa mandiri */
        header {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Container Form Utama */
        .premium-card {
            background-color: #ffffff;
            padding: 2.5rem 2rem;
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.05);
            border: 1px solid #eef2f6;
            margin-top: 10vh;
        }
        
        /* Tipografi Judul */
        .premium-title {
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            color: #0f172a;
            font-size: 26px;
            font-weight: 700;
            letter-spacing: -0.02em;
            margin-bottom: 4px;
            text-align: center;
        }
        .premium-subtitle {
            color: #64748b;
            font-size: 14px;
            margin-bottom: 24px;
            text-align: center;
        }
        
        /* Tag Badge Kecil di Atas */
        .badge-container {
            text-align: center;
            margin-bottom: 8px;
        }
        .premium-badge {
            background-color: #f1f5f9;
            color: #475569;
            padding: 4px 12px;
            border-radius: 100px;
            font-size: 11px;
            font-weight: 600;
            display: inline-block;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        /* Modifikasi UI Tabs agar menyatu secara estetis */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background-color: #f8fafc;
            padding: 6px;
            border-radius: 10px;
            border: 1px solid #e2e8f0;
        }
        .stTabs [data-baseweb="tab"] {
            height: 38px;
            white-space: pre-wrap;
            background-color: transparent;
            border-radius: 6px;
            color: #64748b;
            font-weight: 500;
            border: none !important;
            transition: all 0.2s ease;
        }
        .stTabs [aria-selected="true"] {
            background-color: #ffffff !important;
            color: #0f172a !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
            font-weight: 600;
        }
        </style>
    """, unsafe_allow_html=True)

    # Memposisikan kartu di tengah layar dengan kolom pembantu
    col1, col2, col3 = st.columns([1, 1.8, 1])

    with col2:
        # Wrapper HTML pembuka untuk gaya premium
        st.markdown("""
            <div class="premium-card">
                <div class="badge-container">
                    <span class="premium-badge">🔒 Dashboard Access</span>
                </div>
                <h1 class="premium-title">Media Intelligence Engine</h1>
                <h4 class="premium-title">News Scraper, Analisis Sentimen Berita, Executive Summary AI</h4>
                <p class="premium-subtitle">Aplikasi scraping Google News berdasarkan keyword, Cara merangkum berita otomatis untuk eksekutif.</p>
                <p class="premium-subtitle">Silakan pilih metode autentikasi di bawah untuk melanjutkan</p>
                    
            </div>
        """, unsafe_allow_html=True)
        
        # Menggunakan form Streamlit di dalam container untuk layout yang menyatu
        with st.container():
            tab_umum, tab_login = st.tabs(["👥 Akses Umum", "🔐 Akses Administrator"])

            with tab_umum:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(
                    "<div style='background-color: #f8fafc; border-left: 4px solid #cbd5e1; padding: 16px; border-radius: 0 8px 8px 0; margin-bottom: 20px; font-size: 13.5px; color: #334155;'>"
                    "<strong>Mode Peninjau (Read-Only)</strong><br><br>"
                    "⏱️ Akses instan tanpa kredensial<br>"
                    "📊 Dapat memantau data & grafik analitik secara penuh<br>"
                    "🔒 Fitur modifikasi database & destruksi dinonaktifkan"
                    "</div>", 
                    unsafe_allow_html=True
                )
                
                if st.button(
                    "Masuk sebagai User Umum",
                    type="secondary",
                    use_container_width=True,
                    key="btn_user_umum"
                ):
                    st.session_state.db_authenticated = True
                    st.session_state.user_type = "umum"
                    st.session_state.saved_db_password = ""
                    st.success("Akses umum diberikan. Mempersiapkan dashboard...")
                    st.rerun()

            with tab_login:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown(
                    "<div style='background-color: #eff6ff; border-left: 4px solid #3b82f6; padding: 16px; border-radius: 0 8px 8px 0; margin-bottom: 20px; font-size: 13.5px; color: #1e40af'>"
                    "<strong>Mode Administrator (Full-Access)</strong><br><br>"
                    "⚡ Membuka kontrol penuh pipeline data<br>"
                    "🛠️ Hak akses eksekusi script pencarian baru<br>"
                    "⚠️ Diperlukan password database yang valid"
                    "</div>", 
                    unsafe_allow_html=True
                )
                
                password = st.text_input(
                    "Kredensial Database",
                    type="password",
                    placeholder="Masukkan password database...",
                    key="pwd_login",
                    label_visibility="collapsed" # Menyembunyikan label bawaan agar lebih clean karena sudah ada placeholder
                )
                
                st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)

                if st.button(
                    "Otorisasi & Masuk",
                    type="primary",
                    use_container_width=True,
                    key="btn_user_login"
                ):
                    if password.strip() == "":
                        st.error("Password tidak boleh kosong.")
                    else:
                        st.session_state.saved_db_password = password
                        try:
                            # Test koneksi
                            from app.database import dapatkan_koneksi_db
                            conn = dapatkan_koneksi_db()
                            conn.close()

                            st.session_state.db_authenticated = True
                            st.session_state.user_type = "login"
                            st.success("Otorisasi berhasil. Membuka enkripsi...")
                            st.rerun()

                        except Exception:
                            st.session_state.db_authenticated = False
                            st.session_state.user_type = None
                            st.session_state.saved_db_password = ""
                            st.error("Gagal melakukan otentikasi. Periksa kembali password database Anda.")

        # Footer jaminan keamanan (Trust Signals)
        st.markdown(
            "<p style='text-align: center; color: #94a3b8; font-size: 11px; margin-top: 30px;'>"
            "🔒 Enkripsi End-to-End aktif. Sesi Anda dilindungi sistem keamanan database terisolasi."
            "</p>", 
            unsafe_allow_html=True
        )

    st.stop()


# ======================================================
# LOGOUT
# ======================================================

def logout():

    st.session_state.db_authenticated = False
    st.session_state.user_type = None
    st.session_state.saved_db_password = ""

    st.cache_data.clear()
    st.cache_resource.clear()

    st.rerun()


# ======================================================
# KONEKSI DATABASE
# ======================================================

def dapatkan_koneksi_db():

    if IS_POSTGRES:

        import psycopg2

        if "{PASSWORD}" in DB_URL_TEMPLATE:

            url = DB_URL_TEMPLATE.replace(
                "{PASSWORD}",
                st.session_state.get("saved_db_password", "")
            )

        else:

            url = DB_URL_TEMPLATE

        return psycopg2.connect(url)

    db_path = _resolve_sqlite_path(DB_URL_TEMPLATE)

    Path(db_path).parent.mkdir(
        parents=True,
        exist_ok=True
    )

    return sqlite3.connect(db_path)


# ======================================================
# INISIALISASI DATABASE
# ======================================================

def inisialisasi_database():

    conn = dapatkan_koneksi_db()

    cursor = conn.cursor()

    if IS_POSTGRES:

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS artikel(
                id SERIAL PRIMARY KEY,
                kata_kunci TEXT,
                judul TEXT,
                media TEXT,
                waktu_tampilan TEXT,
                waktu_iso TEXT,
                link TEXT UNIQUE,
                isi_konten TEXT,
                di_scrap_pada TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    else:

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS artikel(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kata_kunci TEXT,
                judul TEXT,
                media TEXT,
                waktu_tampilan TEXT,
                waktu_iso TEXT,
                link TEXT UNIQUE,
                isi_konten TEXT,
                di_scrap_pada TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    conn.commit()
    conn.close()


# ======================================================
# CRUD
# ======================================================

def ambil_data_dari_db():

    conn = dapatkan_koneksi_db()

    df = pd.read_sql_query(
        "SELECT * FROM artikel ORDER BY id DESC",
        conn
    )

    conn.close()

    return df


def hapus_semua_data_db():

    conn = dapatkan_koneksi_db()

    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM artikel")

    jumlah = cursor.fetchone()[0]

    cursor.execute("DELETE FROM artikel")

    conn.commit()

    conn.close()

    return jumlah