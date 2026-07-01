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

    st.markdown("<br><br>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1,2,1])

    with col2:

        with st.container(border=True):

            st.subheader("🔒 Dashboard Access")

            st.caption(
                "Pilih mode akses untuk membuka dashboard."
            )

            # Tab untuk memilih tipe user
            tab_umum, tab_login = st.tabs(["👥 User Umum", "🔐 User Login"])

            with tab_umum:
                st.info(
                    "**User Umum**\n\n"
                    "✅ Akses dashboard tanpa password\n"
                    "✅ Lihat semua data dan grafik\n"
                    "❌ Tidak bisa hapus database"
                )
                
                if st.button(
                    "Akses sebagai User Umum",
                    type="primary",
                    use_container_width=True,
                    key="btn_user_umum"
                ):
                    st.session_state.db_authenticated = True
                    st.session_state.user_type = "umum"
                    st.session_state.saved_db_password = ""
                    st.success("Login berhasil sebagai User Umum.")
                    st.rerun()

            with tab_login:
                st.info(
                    "**User Login**\n\n"
                    "✅ Akses dashboard dengan password\n"
                    "✅ Lihat semua data dan grafik\n"
                    "✅ Dapat hapus database"
                )
                
                password = st.text_input(
                    "Password",
                    type="password",
                    key="pwd_login"
                )

                if st.button(
                    "Login dengan Password",
                    type="primary",
                    use_container_width=True,
                    key="btn_user_login"
                ):

                    if password.strip() == "":
                        st.error("Password tidak boleh kosong.")

                    else:

                        # simpan password
                        st.session_state.saved_db_password = password

                        try:
                            # test koneksi
                            conn = dapatkan_koneksi_db()
                            conn.close()

                            st.session_state.db_authenticated = True
                            st.session_state.user_type = "login"

                            st.success("Login berhasil.")

                            st.rerun()

                        except Exception:

                            st.session_state.db_authenticated = False
                            st.session_state.user_type = None
                            st.session_state.saved_db_password = ""

                            st.error(
                                "Password salah atau koneksi database gagal."
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