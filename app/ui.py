import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from streamlit_plotly_events import plotly_events
from googlenewsdecoder import gnewsdecoder

from app.database import (
    cek_autentikasi_manual,
    inisialisasi_database,
    ambil_data_dari_db,
    hapus_semua_data_db,
    logout,
)

from app.scraper import run_scraper_pipeline
from app.sentiment import hitung_sentimen_leksikon

from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords
import nltk
import re

# Download required NLTK data
# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

# FIX: Tambahkan ini agar stopwords otomatis terunduh jika belum ada
try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

# ======================================================
# HELPER FUNCTION - EXECUTIVE SUMMARY GENERATOR
# ======================================================
@st.cache_data
# 🟢 Sesuaikan parameter fungsi dengan menambahkan kata_kunci dan rentang_waktu
@st.cache_data
def buat_ringkasan_eksekutif(dataframe, kata_kunci, rentang_waktu, num_sentences=5):
    """
    Membuat ringkasan eksekutif dari seluruh konten artikel menggunakan extractive summarization
    dengan sistem caching otomatis ke database.
    """
    from app.database import dapatkan_koneksi_db, IS_POSTGRES
    import nltk
    
    # 🔴 FORCE DOWNLOAD: Paksa unduh langsung di dalam fungsi untuk memastikan resource tersedia
    for res in ['tokenizers/punkt', 'corpora/stopwords']:
        try:
            nltk.data.find(res)
        except LookupError:
            nltk.download(res.split('/')[-1], quiet=True)
            
    from nltk.tokenize import sent_tokenize
    from nltk.corpus import stopwords

    if dataframe.empty:
        return "Tidak ada data artikel yang tersedia untuk diringkas."

    # -------------------------------------------------------------------------
    # 1. CEK KE DATABASE TERLEBIH DAHULU (CACHE HIT)
    # -------------------------------------------------------------------------
    try:
        conn = dapatkan_koneksi_db()
        cursor = conn.cursor()
        
        if IS_POSTGRES:
            query_cek = """
                SELECT hasil_summary FROM executive_summary 
                WHERE kata_kunci = %s AND rentang_waktu = %s 
                ORDER BY waktu_dibuat DESC LIMIT 1
            """
        else:
            query_cek = """
                SELECT hasil_summary FROM executive_summary 
                WHERE kata_kunci = ? AND rentang_waktu = ? 
                ORDER BY waktu_dibuat DESC LIMIT 1
            """
        
        cursor.execute(query_cek, (str(kata_kunci), str(rentang_waktu)))
        row = cursor.fetchone()
        
        if row:
            cursor.close()
            conn.close()
            return row[0]  # ⚡ Kembalikan hasil langsung jika sudah ada di DB
            
    except Exception as e:
        pass  # Jika tabel belum dibuat, abaikan dan lanjut ke pembuatan manual

    # -------------------------------------------------------------------------
    # 2. JIKA CACHE TIDAK ADA, JALANKAN LOGIKA TEXT SUMMARIZATION (CACHE MISS)
    # -------------------------------------------------------------------------
    try:
        konten_semua = dataframe["isi_konten"].dropna()
        konten_semua = konten_semua[konten_semua.str.len() > 0]
        
        if len(konten_semua) == 0:
            return "Tidak ada konten artikel yang tersedia untuk diringkas."
        
        text = " ".join(konten_semua.tolist())
        text = re.sub(r'\[.*?\]', '', text)
        sentences = sent_tokenize(text)
        
        if len(sentences) <= num_sentences:
            summary_hasil = text
        else:
            stop_words = set(stopwords.words('indonesian')) if 'indonesian' in stopwords.fileids() else set()
            words = re.findall(r'\w+', text.lower())
            word_frequencies = {}
            for word in words:
                if word not in stop_words:
                    word_frequencies[word] = word_frequencies.get(word, 0) + 1
            
            if word_frequencies:
                max_frequency = max(word_frequencies.values())
                for word in word_frequencies:
                    word_frequencies[word] = word_frequencies[word] / max_frequency
            
            sentence_scores = {}
            for sent in sentences:
                for word in re.findall(r'\w+', sent.lower()):
                    if word in word_frequencies:
                        sentence_scores[sent] = sentence_scores.get(sent, 0) + word_frequencies[word]
            
            import heapq
            summary_sentences = heapq.nlargest(num_sentences, sentence_scores, key=sentence_scores.get)
            summary_hasil = " ".join(summary_sentences)

        # -------------------------------------------------------------------------
        # 3. SIMPAN HASIL BARU KE DATABASE SEBAGAI CACHE
        # -------------------------------------------------------------------------
        try:
            conn = dapatkan_koneksi_db()
            cursor = conn.cursor()
            if IS_POSTGRES:
                query_insert = "INSERT INTO executive_summary (kata_kunci, rentang_waktu, hasil_summary) VALUES (%s, %s, %s)"
            else:
                query_insert = "INSERT INTO executive_summary (kata_kunci, rentang_waktu, hasil_summary) VALUES (?, ?, ?)"
                
            cursor.execute(query_insert, (str(kata_kunci), str(rentang_waktu), summary_hasil))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as db_err:
            pass

    except Exception as e:
        summary_hasil = f"Gagal membuat ringkasan eksekutif: {str(e)}"
        
    return summary_hasil

# ======================================================
# DEFINISI DIALOG
# ======================================================
def dapatkan_link_tampil(row_data):
    link = row_data.get("link") or ""
    if not link:
        return ""

    try:
        decoded = gnewsdecoder(link, interval=1, proxy=None)
        if decoded.get("status") and decoded.get("decoded_url"):
            url_target = decoded["decoded_url"]
            if "https" in url_target and url_target.count("https://") > 1:
                url_target = "https://" + url_target.split("https://")[-1]
            return url_target
    except Exception:
        pass

    return link


@st.dialog("📄 Artikel Lengkap", width="large")
def show_article(row_data):
    st.subheader(row_data["judul"])
    st.caption(f"**Media**: {row_data['media']} | **Tanggal**: {row_data['waktu_tampilan']}")
    
    st.divider()
    
    if pd.isna(row_data["isi_konten"]) or row_data["isi_konten"].strip() == "":
        st.info("Konten artikel kosong atau tidak berhasil di-scrap.")
    else:
        st.write(row_data["isi_konten"])
        
    st.divider()
    st.write("**Link Sumber:**")
    link_tampil = dapatkan_link_tampil(row_data)
    st.code(link_tampil, language=None)


def render_app():

    st.set_page_config(
        page_title="News Intelligence Dashboard",
        page_icon="📰",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    cek_autentikasi_manual()
    inisialisasi_database()

    # ======================================================
    # CSS STYLING - Fluent UI / Power BI Inspired
    # ======================================================
    st.markdown("""
    <style>
        .main .block-container { padding-top: 2rem; padding-bottom: 2rem; }
        .main-title { background: linear-gradient(90deg, #0078D4, #106EBE); padding: 25px; border-radius: 12px; color: white; margin-bottom: 1.5rem; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1); }
        .main-title h1 { margin: 0; font-size: 2.5rem; font-weight: 600; }
        .main-title p { margin: 0.5rem 0 0 0; font-size: 1.1rem; opacity: 0.9; }
        .kpi-box { background: linear-gradient(135deg, #0078D4 0%, #106EBE 100%); padding: 20px; border-radius: 10px; color: white; text-align: center; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15); transition: all 0.2s ease; }
        .kpi-box:hover { transform: translateY(-3px); box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2); }
        .kpi-label { font-size: 0.85rem; opacity: 0.9; margin-bottom: 8px; font-weight: 500; }
        .kpi-value { font-size: 2rem; font-weight: 700; color: #FFFFFF; }
        .stButton>button { border-radius: 6px; font-weight: 500; }
        .stButton>button[kind="primary"] { background-color: #0078D4; color: white; }
        .stButton>button[kind="secondary"] { background-color: #F3F2F1; color: #323130; border: 1px solid #C8C6C4; }
        .stButton>button:hover { opacity: 0.9; }
        [data-testid="stSidebar"] { background-color: #F3F2F1; border-right: 1px solid #E1DFDD; }
        .stDataFrame { border-radius: 8px; overflow: hidden; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06); }
        .stTabs [data-baseweb="tab-list"] { gap: 24px; background-color: #F8F8F8; padding: 8px; border-radius: 8px; }
        .stTabs [data-baseweb="tab"] { padding: 12px 20px; font-weight: 500; color: #605E5C; }
        .stTabs [aria-selected="true"] { background-color: #0078D4; color: white; border-radius: 6px; }
        [data-testid="stDialog"] { border-radius: 12px; }
        .footer { text-align: center; padding: 1rem; color: #605E5C; font-size: 0.9rem; border-top: 1px solid #E1DFDD; margin-top: 2rem; }
    </style>
    """, unsafe_allow_html=True)

    # ======================================================
    # HEADER
    # ======================================================
    st.markdown("""
    <div class="main-title">
        <h1>📰 News Intelligence Dashboard</h1>
        <p>Google News Scraping • Sentiment Analysis • Real-time Monitoring</p>
    </div>
    """, unsafe_allow_html=True)

    # ======================================================
    # SIDEBAR
    # ======================================================
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/news.png", width=70)
        st.title("Control Panel")
        st.markdown("---")

        user_type = st.session_state.get("user_type", "unknown")
        if user_type == "umum":
            st.info("👥 **User Umum**\n\nDashboard view-only mode")
        elif user_type == "login":
            st.success("🔐 **User Login**\n\nFull access including delete")

        st.markdown("---")
        keyword = st.text_input("🔍 Keyword Pencarian", placeholder="Contoh: Inflasi Papua")

        if st.button("🚀 Jalankan Scraping", width='stretch', type="primary"):
            if not keyword.strip():
                st.warning("Masukkan keyword terlebih dahulu.")
            else:
                progress_bar = st.progress(0.0)
                status_text = st.empty()
                try:
                    run_scraper_pipeline(
                        keyword=keyword,
                        on_progress=lambda p: progress_bar.progress(p),
                        on_status=lambda s: status_text.text(s)
                    )
                    st.success("✅ Scraping selesai. Data telah diperbarui.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Terjadi kegagalan sistem saat scraping: {e}")

        st.markdown("---")
        if user_type == "login":
            with st.popover("🗑 Hapus Seluruh Database", width='stretch'):
                st.warning("⚠️ Tindakan ini akan menghapus semua artikel dari database!")
                password_konfirmasi = st.text_input("Masukkan password akun Anda", type="password", key="del_pwd")
                
                if st.button("Konfirmasi Hapus Data", type="primary", width='stretch'):
                    password_login = st.session_state.get("saved_db_password", "")
                    if password_konfirmasi == password_login: 
                        jumlah = hapus_semua_data_db()
                        st.success(f"✅ {jumlah} berita berhasil dihapus.")
                        st.rerun()
                    else:
                        st.error("❌ Password salah. Harus sama dengan password login Anda.")
        else:
            st.button("🗑 Hapus Seluruh Database", width='stretch', disabled=True, help="Fitur ini hanya tersedia untuk User Login")

        st.markdown("---")
        if st.button("🚪 Logout", width='stretch', type="secondary"):
            logout()

    # ======================================================
    # DATA FETCH & PREP
    # ======================================================
    df = ambil_data_dari_db()

    if len(df) > 0:
        df["waktu_tampilan"] = pd.to_datetime(df["waktu_tampilan"], errors="coerce")
        df["tanggal"] = df["waktu_tampilan"].dt.date
        df["Sentimen"] = df["isi_konten"].apply(hitung_sentimen_leksikon)

        # Bagian Filter UI dan seleksi multiselect tetap dipertahankan di sini
        col1, col2 = st.columns([2, 1])
        with col1:
            selected_keyword = st.multiselect("Filter Keyword", options=df["kata_kunci"].unique(), default=None)
        with col2:
            selected_sentimen = st.multiselect("Filter Sentimen", options=["Positif", "Negatif"], default=["Positif", "Negatif"])

        col3, col4 = st.columns([2, 1])
        with col3:
            selected_media = st.multiselect("Filter Media", options=df["media"].unique(), default=None)
        with col4:
            min_date = df["waktu_tampilan"].min().date()
            max_date = df["waktu_tampilan"].max().date()
            
            date_range = st.date_input("Rentang Tanggal", value=[min_date, max_date], min_value=min_date, max_value=max_date)
            start_date, end_date = None, None
            if isinstance(date_range, list) or isinstance(date_range, tuple):
                if len(date_range) == 2:
                    start_date, end_date = date_range

        # Proses Penyaringan Dataframe Jalankan Terlebih Dahulu
        filtered_df = df.copy()
        if selected_keyword:
            filtered_df = filtered_df[filtered_df["kata_kunci"].isin(selected_keyword)]
        if selected_media:
            filtered_df = filtered_df[filtered_df["media"].isin(selected_media)]
        if selected_sentimen:
            filtered_df = filtered_df[filtered_df["Sentimen"].isin(selected_sentimen)]
            
        if start_date and end_date:
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date).replace(hour=23, minute=59, second=59)
            mask = (filtered_df["waktu_tampilan"] >= start_dt) & (filtered_df["waktu_tampilan"] <= end_dt)
            filtered_df = filtered_df[mask]

        # REVISI UTAMA: Hitung KPI berdasarkan hasil filter (filtered_df)
        total_berita = len(filtered_df)
        berita_dengan_isi = filtered_df["isi_konten"].notna().sum()
        jumlah_media = filtered_df["media"].nunique()
        jumlah_keyword = filtered_df["kata_kunci"].nunique()

    else:
        total_berita, berita_dengan_isi, jumlah_media, jumlah_keyword = 0, 0, 0, 0
        filtered_df = pd.DataFrame()

    # ======================================================
    # KPI CARDS
    # ======================================================
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.markdown(f'<div class="kpi-box"><div class="kpi-label">📰 Total Berita</div><div class="kpi-value">{total_berita:,}</div></div>', unsafe_allow_html=True)
    with kpi2:
        st.markdown(f'<div class="kpi-box"><div class="kpi-label">📄 Dengan Isi</div><div class="kpi-value">{berita_dengan_isi:,}</div></div>', unsafe_allow_html=True)
    with kpi3:
        st.markdown(f'<div class="kpi-box"><div class="kpi-label">🏢 Jumlah Media</div><div class="kpi-value">{jumlah_media:,}</div></div>', unsafe_allow_html=True)
    with kpi4:
        st.markdown(f'<div class="kpi-box"><div class="kpi-label">🔖 Jumlah Keyword</div><div class="kpi-value">{jumlah_keyword:,}</div></div>', unsafe_allow_html=True)

    # ======================================================
    # CHARTS & TABS
    # ======================================================
    tab1, tab2, tab3 = st.tabs(["📊 Analisis", "📈 Grafik", "📂 Data"])
    with tab1:
        st.subheader("📋 Ringkasan Eksekutif")
        
        # 🟢 PERBAIKAN UTAMA: Amankan selected_keyword di awal agar tidak UnboundLocalError jika data kosong
        try:
            # Periksa apakah selected_keyword ada di level global/local streamlit
            if 'selected_keyword' in locals() or 'selected_keyword' in globals():
                active_keywords = selected_keyword if selected_keyword else []
            else:
                active_keywords = []
        except NameError:
            active_keywords = []

        keyword_str = ", ".join(active_keywords) if active_keywords else "All"

        # Amankan juga start_date dan end_date
        try:
            if start_date and end_date:
                date_range_str = f"{start_date}_to_{end_date}"
            else:
                date_range_str = "all_time"
        except NameError:
            date_range_str = "all_time"
            
        periode_str = f"period_{date_range_str}" 

        # --------------------------------------------------------------------
        # Fungsi helper interaksi database cache (Anti-Error jika tabel kosong)
        # --------------------------------------------------------------------
        def cek_cache_summary_db(kata_kunci, rentang_waktu):
            from app.database import dapatkan_koneksi_db, IS_POSTGRES
            try:
                conn = dapatkan_koneksi_db()
                cursor = conn.cursor()
                if IS_POSTGRES:
                    query = "SELECT hasil_summary FROM executive_summary WHERE kata_kunci = %s AND rentang_waktu = %s ORDER BY waktu_dibuat DESC LIMIT 1"
                else:
                    query = "SELECT hasil_summary FROM executive_summary WHERE kata_kunci = ? AND rentang_waktu = ?"
                cursor.execute(query, (str(kata_kunci), str(rentang_waktu)))
                row = cursor.fetchone()
                cursor.close()
                conn.close()
                if row: return row[0]
            except Exception:
                return None
            return None

        def simpan_summary_ke_db(kata_kunci, rentang_waktu, hasil_summary):
            from app.database import dapatkan_koneksi_db, IS_POSTGRES
            try:
                conn = dapatkan_koneksi_db()
                cursor = conn.cursor()
                if IS_POSTGRES:
                    query = "INSERT INTO executive_summary (kata_kunci, rentang_waktu, hasil_summary) VALUES (%s, %s, %s)"
                else:
                    query = "INSERT INTO executive_summary (kata_kunci, rentang_waktu, hasil_summary) VALUES (?, ?, ?)"
                cursor.execute(query, (str(kata_kunci), str(rentang_waktu), hasil_summary))
                conn.commit()
                cursor.close()
                conn.close()
            except Exception:
                pass
        # --------------------------------------------------------------------

        # Menggunakan try-except pembungkus len(filtered_df) agar aman jika filtered_df tidak terdefinisi
        try:
            df_length = len(filtered_df)
        except NameError:
            df_length = 0

        if df_length > 0:
            col1, col2, col3 = st.columns(3)
            with col1:
                sentimen_count = filtered_df["Sentimen"].value_counts()
                positif = sentimen_count.get("Positif", 0)
                negatif = sentimen_count.get("Negatif", 0)
                netral = sentimen_count.get("Netral", 0)
                total = len(filtered_df)
                persen_positif = (positif / total * 100) if total > 0 else 0
                persen_negatif = (negatif / total * 100) if total > 0 else 0
                st.markdown(f"**Analisis Sentimen**\n- 🟢 Positif: {positif} ({persen_positif:.1f}%)\n- 🔴 Negatif: {negatif} ({persen_negatif:.1f}%)\n- ⚪ Netral: {netral} ({100 - persen_positif - persen_negatif:.1f}%)")
            
            with col2:
                top_media = filtered_df["media"].value_counts().head(3)
                st.markdown("**Top 3 Media**")
                for idx, (media, count) in enumerate(top_media.items(), 1):
                    st.write(f"{idx}. {media}: {count} berita")
            
            with col3:
                trend_harian = filtered_df.groupby(filtered_df["waktu_tampilan"].dt.date).size()
                st.markdown(f"**Statistik Harian**\n- Rata-rata: {trend_harian.mean():.0f} berita/hari\n- Puncak: {trend_harian.max()} berita\n- Terendah: {trend_harian.min()} berita")
            
            st.divider()
            st.markdown("**Insights Utama**")
            insights = []
            if persen_positif > persen_negatif:
                insights.append(f"📈 Sentimen cenderung positif dengan {persen_positif:.1f}% berita positif")
            elif persen_negatif > persen_positif:
                insights.append(f"📉 Sentimen cenderung negatif dengan {persen_negatif:.1f}% berita negatif")
            else:
                insights.append("⚖️ Sentimen seimbang antara positif and negatif")
            
            if len(top_media) > 0:
                insights.append(f"📰 Media dominan: {top_media.index[0]} dengan {top_media.values[0]} artikel")
            
            total_isi = filtered_df["isi_konten"].notna().sum()
            insights.append(f"📄 {(total_isi / len(filtered_df) * 100):.1f}% berita memiliki isi lengkap")
            
            for insight in insights:
                st.write(f"• {insight}")
            
            # --------------------------------------------------
            # ATTACHED: EXECUTIVE SUMMARY SYSTEM (Official Gemini Client)
            # --------------------------------------------------
            st.divider()

            with st.expander("📝 Ringkasan Eksekutif Konten (Official Gemini Client)", expanded=True):
                if active_keywords and len(active_keywords) > 0:
                    default_keyword = active_keywords[0]
                else:
                    default_keyword = "Inflasi Papua"
                    
                target_keyword = st.text_input("Konfirmasi Kata Kunci Analisis:", value=default_keyword)
                
                # Filter data berdasarkan keyword target
                filtered_data = filtered_df[filtered_df['kata_kunci'].astype(str).str.contains(target_keyword, case=False, na=False)]
                
                if filtered_data.empty:
                    st.warning(f"Data tidak ditemukan untuk kata kunci: '{target_keyword}'")
                else:
                    date_min = filtered_data['waktu_tampilan'].dropna().min()
                    date_max = filtered_data['waktu_tampilan'].dropna().max()
                    date_range_str = f"{date_min} sampai {date_max}"
                    
                    # Fungsi cek cache berdasarkan kata kunci di database
                    def cek_cache_summary_hanya_keyword(kata_kunci):
                        from app.database import dapatkan_koneksi_db, IS_POSTGRES
                        try:
                            conn = dapatkan_koneksi_db()
                            cursor = conn.cursor()
                            if IS_POSTGRES:
                                query = "SELECT hasil_summary FROM executive_summary WHERE kata_kunci = %s ORDER BY waktu_dibuat DESC LIMIT 1"
                            else:
                                query = "SELECT hasil_summary FROM executive_summary WHERE kata_kunci = ? ORDER BY waktu_dibuat DESC LIMIT 1"
                            cursor.execute(query, (str(kata_kunci),))
                            row = cursor.fetchone()
                            cursor.close()
                            conn.close()
                            if row: return row[0]
                        except Exception:
                            return None
                        return None

                    # 🟢 PERBAIKAN UTAMA: Ambil nilai cache terlebih dahulu untuk inisialisasi yang aman
                    state_key = f"summary_{target_keyword.replace(' ', '_').lower()}"
                    state_status_key = f"status_{state_key}"
                    
                    # Ambil data dari database jika belum ada di session state
                    if state_key not in st.session_state:
                        cache_db = cek_cache_summary_hanya_keyword(target_keyword)
                        st.session_state[state_key] = cache_db
                        # Inisialisasi status secara eksplisit sejak awal
                        st.session_state[state_status_key] = "Versi Cache" if cache_db else "Baru"
                    
                    # Double check untuk memastikan kunci status SELALU ada (mencegah KeyError)
                    if state_status_key not in st.session_state:
                        st.session_state[state_status_key] = "Versi Cache" if st.session_state[state_key] else "Baru"

                    # 🟢 Gunakan satu wadah/container tunggal untuk area judul dan konten summary
                    area_judul = st.empty()
                    area_konten = st.empty()

                    # Render tampilan awal (mengambil nilai dari session_state yang sudah pasti aman)
                    if st.session_state[state_key]:
                        area_judul.success(f"### 📊 Executive Summary by AI: {target_keyword} ({st.session_state[state_status_key]})")
                        area_konten.markdown(st.session_state[state_key])
                        st.write("---")
                    else:
                        area_judul.info("💡 Belum ada narasi ringkasan otomatis untuk filter ini di database.")

                    # Tombol aksi dinamis
                    trigger_generate = False
                    if st.session_state[state_key] and st.session_state[state_status_key] == "Versi Cache":
                        st.info("💡 Data di atas dapat diperbarui dengan menggabungkan artikel historis dan artikel baru hasil scraping.")
                        if st.button("🔄 Generate Ulang", key="regenerate_gemini_summary"):
                            trigger_generate = True
                    elif not st.session_state[state_key]:
                        if st.button("✨ Hasilkan Narasi Ringkasan Otomatis", key="generate_gemini_summary"):
                            trigger_generate = True

                    # Proses pembuatan narasi ke Gemini Client
                    if trigger_generate:
                        # Ubah status judul komponen menjadi mode memproses
                        area_judul.info("⏳ Sedang menulis dan memperbarui ringkasan eksekutif baru...")
                        
                        try:
                            from google import genai
                            client = genai.Client()
                            
                            t_media = filtered_data['media'].value_counts().head(3)
                            t_media_str = ", ".join([f"{m} ({c} artikel)" for m, c in t_media.items()])
                            
                            clean_df = filtered_data.dropna(subset=['isi_konten', 'judul', 'media'])
                            
                            # Gunakan sampling gabungan jika sebelumnya sudah ada data di database
                            if st.session_state[state_status_key] == "Versi Cache":
                                clean_df = clean_df.sample(frac=0.15, random_state=42)
                                catatan_regenerate = "\n- CATATAN TAMBAHAN: Data ini merupakan gabungan komprehensif dari data historis dan hasil scraping terbaru. Soroti tren pergerakan atau perubahan situasi terbaru jika terdeteksi."
                            else:
                                clean_df = clean_df.sample(frac=0.10, random_state=42)
                                catatan_regenerate = ""
                            
                            formatted_articles = [
                                f"--- ARTIKEL: {row['judul']} ({row['media']}) ---\n{row['isi_konten']}"
                                for _, row in clean_df.iterrows()
                            ]
                            concatenated_content = "\n\n".join(formatted_articles)
                            
                            if len(concatenated_content) > 120000:
                                concatenated_content = concatenated_content[:120000] + "\n\n... [Sisa konten dipotong demi efisiensi konteks] ..."

                            prompt_instruksi = f"""
                            Judul Tugas: Analisis Berita Eksekutif Komprehensif (Metode Terintegrasi 5W+1H)

                            Instruksi Utama:
                            Buatlah sebuah analisis berita eksekutif yang mendalam dan komprehensif dalam bentuk ESSAI MURNI mengalir (narrative essay). Jangan menggunakan sub-judul kaku untuk masing-masing poin 5W+1H (seperti "WHAT:", "WHO:", dll), melainkan leburkan seluruh unsur tersebut secara organis, mengalir, dan profesional ke dalam paragraf-paragraf esai. {catatan_regenerate}

                            I. PEDOMAN METADATA & KONTEKS (Wajib ditulis di paragraf pembuka secara natural):
                            - Profil Kata Kunci yang Dianalisis: {target_keyword}
                            - Cakupan Rentang Tanggal (waktu_tampil): {date_range_str}
                            - 3 Kontributor Media Teratas: {t_media_str}

                            II. KERANGKA ESSAI (Integrasikan seluruh poin ini ke dalam narasi esai):
                            Berdasarkan kolom isi_konten pada data gabungan, narasikan:
                            - Peristiwa utama, pengumuman, kebijakan, atau isu krusial yang dilaporkan terkait tren inflasi.
                            - Individu, organisasi, institusi (seperti BI, Pemda, Bulog, BPS) yang terlibat aktif atau terdampak dalam pemberitaan.
                            - Linimasa atau waktu terjadinya peristiwa-peristiwa penting tersebut berdasarkan data artikel.
                            - Cakupan geografis daerah yang memberikan dampak atau terdampak terbesar di wilayah Papua (seperti Jayapura, Nabire, Keerom, dll).
                            - Akar penyebab atau faktor pendorong mengapa situasi inflasi tersebut terjadi (seperti kendala logistik, wabah penyakit ternak, regulasi subsidi).
                            - Bagaimana situasi tersebut berkembang saat ini serta bagaimana respons taktis, operasi pasar, atau strategi jangka panjang yang dilakukan oleh pihak berwenang.

                            III. KETENTUAN FORMAT & GAYA BAHASA:
                            - Gunakan bahasa Indonesia formal, objektif, dan analitis.
                            - Gunakan teknik tebal (bolding) pada frasa kunci atau angka penting untuk menjaga scannability (keterbacaan cepat) agar laporan mudah dipahami oleh tingkat eksekutif.
                            - Hindari penggunaan poin-poin (bullet points) di bagian inti analisis; pertahaman struktur narasi esai yang padat dan berisi.

                            KORPUS BERITA:
                            {concatenated_content}
                            """
                            
                            response_stream = client.models.generate_content_stream(
                                model="gemini-2.5-flash",
                                contents=prompt_instruksi
                            )
                            
                            full_response_text = []
                            
                            # Bersihkan area konten lama, lalu jalankan live stream ketikan baru
                            for chunk in response_stream:
                                if chunk.text:
                                    full_response_text.append(chunk.text)
                                    area_konten.markdown("".join(full_response_text))
                            
                            final_text = "".join(full_response_text)
                            if final_text:
                                # Simpan permanen ke database backend
                                simpan_summary_ke_db(target_keyword, periode_str, final_text)
                                
                                # Update data session state internal Streamlit sebelum rerun
                                st.session_state[state_key] = final_text
                                st.session_state[state_status_key] = "Hasil Diperbarui ✨"
                                
                                # Timpa ulang komponen judul menjadi warna sukses/hijau dengan label baru
                                area_judul.success(f"### 📊 Executive Summary by AI: {target_keyword} ({st.session_state[state_status_key]})")
                                st.toast("✅ Ringkasan berhasil diperbarui!", icon="🚀")
                                
                                time.sleep(0.5)
                                st.rerun()
                                
                        except Exception as e:
                            st.error(f"Terjadi kesalahan saat menghubungi API Gemini: {e}")

                        else:
                            st.info("❌ Tidak ada data untuk ditampilkan.")

                with tab2:
                    st.subheader("📈 Visualisasi Data")
                    if len(filtered_df) > 0:
                        col1, col2 = st.columns([1, 1], gap="large")
                        with col1:
                            sentimen_count = filtered_df["Sentimen"].value_counts().reset_index()
                            sentimen_count.columns = ["Sentimen", "Jumlah"]
                            fig_sentimen = px.pie(sentimen_count, names="Sentimen", values="Jumlah", title="Distribusi Sentimen", color="Sentimen", color_discrete_map={"Positif": "#4CAF50", "Negatif": "#F44336"}, hole=0.5)
                            fig_sentimen.update_traces(textinfo='percent+label')
                            st.plotly_chart(fig_sentimen, width='stretch')

                        with col2:
                            top_10_m = filtered_df["media"].value_counts().head(10).reset_index()
                            top_10_m.columns = ["Media", "Jumlah"]
                            fig_media = px.bar(top_10_m, x="Jumlah", y="Media", orientation="h", title="Top 10 Media", color="Jumlah", color_continuous_scale="Blues")
                            fig_media.update_layout(yaxis={'categoryorder': 'total ascending'})
                            st.plotly_chart(fig_media, width='stretch')

                        if "tanggal" in filtered_df.columns:
                            berita_per_hari = filtered_df.groupby("tanggal").size().reset_index(name="Jumlah")
                            berita_per_hari["tanggal"] = pd.to_datetime(berita_per_hari["tanggal"])
                            fig_line = px.line(berita_per_hari, x="tanggal", y="Jumlah", title="Jumlah Berita per Hari", markers=True)
                            fig_line.update_traces(line_color="#0078D4")
                            st.plotly_chart(fig_line, width='stretch')
                    else:
                        st.info("Tidak ada data untuk ditampilkan.")

    with tab3:
        st.subheader("📂 Database Berita")
        if len(filtered_df) > 0:
            display_df = filtered_df[["kata_kunci", "judul", "media", "waktu_tampilan", "Sentimen", "isi_konten"]].copy()
            display_df["waktu_tampilan"] = pd.to_datetime(display_df["waktu_tampilan"]).dt.strftime("%d %b %Y, %H:%M")

            selected_rows = st.dataframe(display_df, width='stretch', hide_index=True, height=500, selection_mode="single-row", on_select="rerun")

            csv = filtered_df.to_csv(index=False, sep=";").encode('utf-8')
            st.download_button(label="⬇️ Download Data (Excel/CSV)", data=csv, file_name=f"news_data_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv", width='stretch')

            export_df = filtered_df.copy()
            for col in ["kata_kunci", "judul", "media", "waktu_tampilan", "Sentimen", "isi_konten", "link"]:
                if col not in export_df.columns:
                    export_df[col] = ""

            export_df = export_df[["kata_kunci", "judul", "media", "waktu_tampilan", "Sentimen", "isi_konten", "link"]].copy()
            export_df = export_df.rename(columns={"waktu_tampilan": "waktu_tampil", "Sentimen": "sentimen", "isi_konten": "isi_konten", "link": "link_sumber"})
            export_csv = export_df.to_csv(index=False, sep=";").encode("utf-8")
            st.download_button(label="⬇️ Download Data Lengkap (CSV)", data=export_csv, file_name=f"news_data_lengkap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv", width='stretch')

            selected_row_index = selected_rows["selection"]["rows"]
            if selected_row_index:
                row_terpilih = filtered_df.iloc[selected_row_index[0]]           
                show_article(row_terpilih)
        else:
            st.info("❌ Tidak ada data berita yang sesuai filter.")

    # ======================================================
    # FOOTER
    # ======================================================
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown('<div class="footer">© 2026 | News Intelligence Dashboard | Yenro Sagala - BPS Provinsi Papua</div>', unsafe_allow_html=True)