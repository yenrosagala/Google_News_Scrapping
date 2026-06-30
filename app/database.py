import sqlite3
import pandas as pd
import streamlit as st

DB_URL_TEMPLATE = st.secrets.get("DATABASE_URL_TEMPLATE", "berita_google_news.db")
IS_POSTGRES = DB_URL_TEMPLATE.startswith("postgresql://") or DB_URL_TEMPLATE.startswith("postgres://")


def cek_autentikasi_manual():
    """Meminta password secara interaktif tanpa ada nilai bawaan/default yang disimpan."""
    if "db_authenticated" not in st.session_state:
        st.session_state["db_authenticated"] = False
    if "saved_db_password" not in st.session_state:
        st.session_state["saved_db_password"] = ""

    if not st.session_state["db_authenticated"]:
        st.markdown("<br><br>", unsafe_allow_html=True)
        col_a, col_b, col_c = st.columns([1, 2, 1])
        with col_b:
            st.card = st.container(border=True)
            with st.card:
                st.subheader("🔒 Inisialisasi Akses Database")
                st.caption("Aplikasi ini tidak menyimpan password. Silakan masukkan kata sandi database Anda untuk membuka koneksi.")

                input_pass = st.text_input(
                    "Kata Sandi Database / Aplikasi:",
                    type="password",
                    placeholder="Ketik password di sini...",
                )
                tombol_buka = st.button("Hubungkan ke Database", type="primary", use_container_width=True)

                if tombol_buka:
                    if input_pass.strip() == "":
                        st.error("❌ Password tidak boleh kosong!")
                    else:
                        st.session_state["saved_db_password"] = input_pass
                        st.session_state["db_authenticated"] = True
                        st.success("🔑 Berhasil memuat sesi! Membuka dasbor...")
                        st.rerun()
        st.stop()


def dapatkan_koneksi_db():
    if IS_POSTGRES:
        import psycopg2

        if "{PASSWORD}" in DB_URL_TEMPLATE:
            url_final = DB_URL_TEMPLATE.replace("{PASSWORD}", st.session_state["saved_db_password"])
        else:
            url_final = DB_URL_TEMPLATE
        return psycopg2.connect(url_final)

    return sqlite3.connect(DB_URL_TEMPLATE)


def inisialisasi_database():
    try:
        conn = dapatkan_koneksi_db()
        cursor = conn.cursor()
        if IS_POSTGRES:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS artikel (
                    id SERIAL PRIMARY KEY,
                    kata_kunci TEXT NOT NULL,
                    judul TEXT NOT NULL,
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
                CREATE TABLE IF NOT EXISTS artikel (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kata_kunci TEXT NOT NULL,
                    judul TEXT NOT NULL,
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
    except Exception as e:
        st.session_state["db_authenticated"] = False
        st.session_state["saved_db_password"] = ""
        st.sidebar.error(f"❌ Gagal masuk: Password salah atau database menolak koneksi. ({str(e)})")
        st.stop()


def ambil_data_dari_db():
    conn = dapatkan_koneksi_db()
    df = pd.read_sql_query("SELECT * FROM artikel ORDER BY id DESC", conn)
    conn.close()
    return df


def hapus_semua_data_db():
    conn = dapatkan_koneksi_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM artikel")
    jumlah_sebelum = cursor.fetchone()[0]
    cursor.execute("DELETE FROM artikel")
    conn.commit()
    conn.close()

    return jumlah_sebelum
