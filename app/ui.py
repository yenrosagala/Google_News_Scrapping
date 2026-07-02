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
    dapatkan_koneksi_db,
    IS_POSTGRES,
)

# Fungsi pembantu untuk menyimpan summary baru ke database sesuai standard schema
def simpan_summary_ke_db(kata_kunci, rentang_waktu, hasil_summary):
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

from app.scraper import run_scraper_pipeline
from app.sentiment import hitung_sentimen_leksikon
from app.generate_pdf import generate_pdf_report  # 📄 Mengimpor fungsi PDF profesional murni Python

from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords
import nltk
import re
import time

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

# ======================================================
# HELPER FUNCTION - EXECUTIVE SUMMARY GENERATOR
# ======================================================
@st.cache_data
def buat_ringkasan_eksekutif(dataframe, kata_kunci, rentang_waktu, num_sentences=5):
    import nltk
    for res in ['tokenizers/punkt', 'corpora/stopwords']:
        try:
            nltk.data.find(res)
        except LookupError:
            nltk.download(res.split('/')[-1], quiet=True)
            
    from nltk.tokenize import sent_tokenize
    from nltk.corpus import stopwords

    if dataframe.empty:
        return "Tidak ada data artikel yang tersedia untuk diringkas."

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
            return row[0]
            
    except Exception:
        pass

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

        simpan_summary_ke_db(kata_kunci, rentang_waktu, summary_hasil)

    except Exception as e:
        summary_hasil = f"Gagal membuat ringkasan eksekutif: {str(e)}"
        
    return summary_hasil

# ======================================================
# DEFINISI DIALOG DETAIL ARTIKEL
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

    # CSS Global styling
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

    st.markdown("""
    <div class="main-title">
        <h1>📰 News Intelligence Dashboard</h1>
        <p>Google News Scraping • Sentiment Analysis • Real-time Monitoring</p>
    </div>
    """, unsafe_allow_html=True)

    # Pre-fetch data awal untuk menentukan default filter keyword terakhir
    df = ambil_data_dari_db()
    
    # LOGIKA FILTER KEYWORD DEFAULT (DATABASE TERBARU / SCRAPING TERBARU)
    if "active_keyword" not in st.session_state:
        st.session_state.active_keyword = None
        if len(df) > 0:
            df["waktu_tampilan"] = pd.to_datetime(df["waktu_tampilan"], errors="coerce")
            id_terakhir = df["waktu_tampilan"].idxmax()
            if pd.notna(id_terakhir):
                raw_kw = df.loc[id_terakhir, "kata_kunci"]
                # Mengakomodasi pemisahan multi-keyword hasil scraping baru jika dipisah tanda koma
                if "," in str(raw_kw):
                    st.session_state.active_keyword = [k.strip() for k in str(raw_kw).split(",") if k.strip()]
                else:
                    st.session_state.active_keyword = [str(raw_kw).strip()]

    # ======================================================
    # MENU UTAMA SCRAPING (HALAMAN UTAMA)
    # ======================================================
    with st.container():
        st.markdown("### 🚀 Menu Utama Scraping")
        keyword = st.text_input("🔍 Keyword Pencarian Baru", placeholder="Contoh: Inflasi Papua")

        if st.button("🔥 Jalankan Scraping", width='stretch', type="primary"):
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
                    # 💡 Jika scraping baru multi-keyword dipisah koma, pecah langsung ke state filter
                    if "," in keyword:
                        st.session_state.active_keyword = [k.strip() for k in keyword.split(",") if k.strip()]
                    else:
                        st.session_state.active_keyword = [keyword.strip()]
                        
                    st.success("✅ Scraping selesai. Data telah diperbarui.")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Terjadi kegagalan sistem saat scraping: {e}")
        st.divider()

    # ======================================================
    # SIDEBAR - KONTROL FILTER & UTILITY
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

        st.markdown("### 🎛️ Filter Data Dashboard")
        
        if len(df) > 0:
            available_options = list(df["kata_kunci"].unique())
            raw_defaults = st.session_state.active_keyword if st.session_state.active_keyword else []
            validated_defaults = [kw for kw in raw_defaults if kw in available_options]

            selected_keyword = st.multiselect(
                "Filter Keyword", 
                options=available_options, 
                default=validated_defaults if validated_defaults else None
            )
            st.session_state.active_keyword = selected_keyword
            
            selected_sentimen = st.multiselect("Filter Sentimen", options=["Positif", "Negatif", "Netral"], default=["Positif", "Negatif", "Netral"])
            selected_media = st.multiselect("Filter Media", options=df["media"].unique(), default=None)
            
            df["waktu_tampilan"] = pd.to_datetime(df["waktu_tampilan"], errors="coerce")
            min_date = df["waktu_tampilan"].min().date()
            max_date = df["waktu_tampilan"].max().date()
            date_range = st.date_input("Rentang Tanggal", value=[min_date, max_date], min_value=min_date, max_value=max_date)
            
            start_date, end_date = None, None
            if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
                start_date, end_date = date_range
        else:
            st.info("Belum ada data untuk difilter.")
            selected_keyword, selected_sentimen, selected_media = [], [], []
            start_date, end_date = None, None

        st.markdown("---")
        if user_type == "login":
            with st.popover("🗑 Hapus Seluruh Database", width='stretch'):
                st.warning("⚠️ Tindakan ini akan menghapus semua artikel dari database!")
                password_konfirmasi = st.text_input("Masukkan password akun Anda", type="password", key="del_pwd")
                if st.button("Konfirmasi Hapus Data", type="primary", width='stretch'):
                    password_login = st.session_state.get("saved_db_password", "")
                    if password_konfirmasi == password_login: 
                        jumlah = hapus_semua_data_db()
                        if "active_keyword" in st.session_state:
                            del st.session_state.active_keyword
                        st.success(f"✅ {jumlah} berita berhasil dihapus.")
                        st.rerun()
                    else:
                        st.error("❌ Password salah. Harus sama dengan password login Anda.")
        else:
            st.button("🗑 Hapus Seluruh Database", width='stretch', disabled=True)

        st.markdown("---")
        if st.button("🚪 Logout", width='stretch', type="secondary"):
            if "active_keyword" in st.session_state:
                del st.session_state.active_keyword
            logout()

    # ======================================================
    # DATA PROCESSING & PIPELINE FILTERING
    # ======================================================
    if len(df) > 0:
        df["tanggal"] = df["waktu_tampilan"].dt.date
        df["Sentimen"] = df["isi_konten"].apply(hitung_sentimen_leksikon)

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

        total_berita = len(filtered_df)
        berita_dengan_isi = filtered_df["isi_konten"].notna().sum()
        jumlah_media = filtered_df["media"].nunique()
        jumlah_keyword = filtered_df["kata_kunci"].nunique()
    else:
        total_berita, berita_dengan_isi, jumlah_media, jumlah_keyword = 0, 0, 0, 0
        filtered_df = pd.DataFrame()

    # KPI Cards
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.markdown(f'<div class="kpi-box"><div class="kpi-label">📰 Total Berita</div><div class="kpi-value">{total_berita:,}</div></div>', unsafe_allow_html=True)
    with kpi2:
        st.markdown(f'<div class="kpi-box"><div class="kpi-label">📄 Dengan Isi</div><div class="kpi-value">{berita_dengan_isi:,}</div></div>', unsafe_allow_html=True)
    with kpi3:
        st.markdown(f'<div class="kpi-box"><div class="kpi-label">🏢 Jumlah Media</div><div class="kpi-value">{jumlah_media:,}</div></div>', unsafe_allow_html=True)
    with kpi4:
        st.markdown(f'<div class="kpi-box"><div class="kpi-label">🔖 Jumlah Keyword</div><div class="kpi-value">{jumlah_keyword:,}</div></div>', unsafe_allow_html=True)

    # WORKSPACE TABS
    tab1, tab2, tab3 = st.tabs(["📊 Analisis", "📈 Grafik", "📂 Data"])
    with tab1:
        st.subheader("📋 Ringkasan Eksekutif")
        
        active_keywords = selected_keyword if selected_keyword else []
        keyword_str = ", ".join(active_keywords) if active_keywords else "All"
        date_range_str = f"{start_date} sampai {end_date}" if (start_date and end_date) else "all_time"
        periode_str = f"period_{date_range_str}" 

        if len(filtered_df) > 0:
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
            
            st.divider()

            # --- OFFICIAL GEMINI SYSTEM EXPANDER ---
            with st.expander("📝 Ringkasan Eksekutif Konten (Official Gemini Client)", expanded=True):
                # 🟢 REVISI UTAMA: Nilai bawaan (value) otomatis mengambil dan menggabungkan SEMUA keyword terpilih di filter sidebar
                joined_default_keywords = ", ".join(active_keywords) if active_keywords else "Inflasi Papua"
                
                input_keyword = st.text_input(
                    "Konfirmasi Kata Kunci Analisis (Pisahkan dengan koma untuk kombinasi gabungan multi-keyword):", 
                    value=joined_default_keywords
                )
                
                # Ubah teks input menjadi list Proper Case yang bersih
                target_keywords_list = [kw.strip().title() for kw in input_keyword.split(",") if kw.strip()]
                
                if target_keywords_list:
                    # Menggunakan OR LOGIC (A|B) agar semua berita dari kata kunci yang dipilih digabung jadi satu kesatuan esai
                    regex_pattern = "|".join([re.escape(kw) for kw in target_keywords_list])
                    filtered_data = filtered_df[filtered_df['kata_kunci'].astype(str).str.contains(regex_pattern, case=False, na=False)]
                else:
                    filtered_data = pd.DataFrame()
                
                # Penggabungan string nama untuk key cache database dan file PDF
                target_keyword = "_dan_".join([kw.replace(" ", "_").lower() for kw in target_keywords_list]) if target_keywords_list else "inflasi_papua"
                # Label cantik untuk tampilan judul report UI & PDF
                display_title_keyword = ", ".join(target_keywords_list) if target_keywords_list else "Inflasi Papua"
                
                if filtered_data.empty:
                    st.warning(f"Data tidak ditemukan untuk kecocokan kombinasi kata kunci: {target_keywords_list}")
                else:
                    date_min = filtered_data['waktu_tampilan'].dropna().min()
                    date_max = filtered_data['waktu_tampilan'].dropna().max()
                    date_range_str = f"{date_min} sampai {date_max}"
                    
                    def cek_cache_summary_hanya_keyword(kata_kunci):
                        try:
                            conn = dapatkan_koneksi_db()
                            cursor = conn.cursor()
                            query = "SELECT hasil_summary FROM executive_summary WHERE kata_kunci = %s ORDER BY waktu_dibuat DESC LIMIT 1" if IS_POSTGRES else "SELECT hasil_summary FROM executive_summary WHERE kata_kunci = ? ORDER BY waktu_dibuat DESC LIMIT 1"
                            cursor.execute(query, (str(kata_kunci),))
                            row = cursor.fetchone()
                            cursor.close()
                            conn.close()
                            if row: return row[0]
                        except Exception:
                            return None
                        return None

                    state_key = f"summary_{target_keyword}"
                    state_status_key = f"status_{state_key}"
                    
                    if state_key not in st.session_state:
                        cache_db = cek_cache_summary_hanya_keyword(target_keyword)
                        st.session_state[state_key] = cache_db
                        st.session_state[state_status_key] = "Versi Cache" if cache_db else "Baru"

                    area_judul = st.empty()
                    area_konten = st.empty()

                    if st.session_state[state_key]:
                        area_judul.success(f"### 📊 Executive Summary by AI: {display_title_keyword} ({st.session_state[state_status_key]})")
                        area_konten.markdown(st.session_state[state_key])
                        
                        # --- EXPORT REPORT PDF AMAN ---
                        st.write("---")
                        st.markdown("#### 📥 Cetak Laporan Analisis Resmi")
                        t_media = filtered_data['media'].value_counts().head(3)
                        t_media_str = ", ".join([f"{m} ({c} artikel)" for m, c in t_media.items()])

                        try:
                            pdf_bytes = generate_pdf_report(
                                filtered_df=filtered_df,
                                insights=insights,
                                target_keyword=display_title_keyword,
                                date_range_str=date_range_str,
                                t_media_str=t_media_str,
                                summary_text=st.session_state[state_key]
                            )
                            if pdf_bytes:
                                st.download_button(
                                    label="📄 Download Laporan Resmi (PDF)",
                                    data=bytes(pdf_bytes),
                                    file_name=f"Laporan_Analisis_{target_keyword}_{datetime.now().strftime('%Y%m%d')}.pdf",
                                    mime="application/pdf",
                                    width='stretch'
                                )
                        except Exception as pdf_err:
                            st.error(f"Sistem gagal menyiapkan cetakan PDF: {pdf_err}")
                    else:
                        area_judul.info("💡 Belum ada narasi ringkasan otomatis untuk filter ini di database.")

                    trigger_generate = False
                    if st.session_state[state_key] and st.session_state[state_status_key] == "Versi Cache":
                        if st.button("🔄 Generate Ulang ", key="regenerate_gemini_summary"):
                            trigger_generate = True
                            st.session_state[state_status_key] = "Versi Cache"
                    elif not st.session_state[state_key]:
                        if st.button("✨ Hasilkan Narasi Ringkasan Otomatis", key="generate_gemini_summary"):
                            trigger_generate = True

                    # ======================================================
                    # LOGIKA GENERATE TEKS DAN BLOK FAILOVER MODEL AGRESIF
                    # ======================================================
                    if trigger_generate:
                        area_judul.info("⏳ Sedang menulis dan memperbarui ringkasan eksekutif baru...")
                        try:
                            from google import genai
                            client = genai.Client()
                            
                            t_media = filtered_data['media'].value_counts().head(3)
                            t_media_str = ", ".join([f"{m} ({c} artikel)" for m, c in t_media.items()])
                            clean_df = filtered_data.dropna(subset=['isi_konten', 'judul', 'media'])
                            
                            # 🟢 REVISI: Stratified Sampling Proporsional Berdasarkan Sentimen (Total Sampel 25%)
                            if len(clean_df) > 10:
                                # Mengelompokkan berdasarkan kolom 'Sentimen' dan mengambil 25% sampel secara proporsional dari masing-masing kelompok
                                clean_df = clean_df.groupby('Sentimen', group_keys=False).apply(
                                    lambda x: x.sample(frac=0.25, random_state=42) if len(x) > 0 else x
                                )
                            else:
                                clean_df = clean_df

                            # Logika penentu catatan instruksi ke Gemini berdasarkan status cache
                            if st.session_state[state_status_key] == "Versi Cache":
                                catatan_regenerate = "\n- CATATAN TAMBAHAN: Data ini merupakan gabungan komprehensif dari data historis dan hasil scraping terbaru. Soroti tren pergerakan atau perubahan situasi terbaru jika terdeteksi."
                            else:
                                catatan_regenerate = ""
                                
                            formatted_articles = [f"--- ARTIKEL: {row['judul']} ({row['media']}) ---\n{row['isi_konten']}" for _, row in clean_df.iterrows()]
                            concatenated_content = "\n\n".join(formatted_articles)
                            if len(concatenated_content) > 120000:
                                concatenated_content = concatenated_content[:120000] + "\n\n... [Sisa konten dipotong demi efisiensi konteks] ..."

                            prompt_instruksi = f"""
                            **Judul Tugas: Analisis Berita Eksekutif Komprehensif**

                            ### Instruksi Utama

                            Buatlah sebuah analisis berita eksekutif yang mendalam dan komprehensif dalam bentuk **esai naratif (narrative essay)** yang mengalir. Jangan menggunakan subjudul kaku untuk masing-masing unsur 5W+1H (WHAT, WHO, WHEN, WHERE, WHY, HOW), melainkan integrasikan seluruh unsur tersebut secara alami ke dalam paragraf-paragraf esai. {catatan_regenerate}

                            ---

                            ### I. Pedoman Metadata & Konteks

                            Pada paragraf pembuka, jelaskan secara natural informasi berikut:

                            * Profil Kata Kunci yang Dianalisis: {target_keyword}
                            * Cakupan Rentang Tanggal (waktu_tampil): {date_range_str}
                            * 3 Kontributor Media Teratas: {t_media_str}

                            ---

                            ### II. Kerangka Esai

                            Berdasarkan kolom **isi_konten** pada data gabungan, lakukan analisis yang mencakup secara terpadu:

                            * Peristiwa utama, pengumuman, kebijakan, maupun isu strategis yang diberitakan terkait tren inflasi.
                            * Individu, organisasi, maupun institusi (misalnya BI, BPS, Bulog, Pemerintah Daerah, kementerian, pelaku usaha) yang berperan atau terdampak.
                            * Kronologi perkembangan isu berdasarkan waktu publikasi artikel.
                            * Wilayah Papua yang menjadi pusat perhatian atau terdampak terbesar (Jayapura, Nabire, Keerom, Mimika, dan sebagainya).
                            * Faktor penyebab utama yang memengaruhi kondisi inflasi.
                            * Perkembangan situasi terkini beserta respons pemerintah, operasi pasar, kebijakan, maupun strategi jangka panjang.

                            ---

                            ### III. Ketentuan Sitasi (WAJIB)

                            * Gunakan **sitasi numerik** dengan format **[1]**, **[2]**, **[3]**, dan seterusnya.
                            * Nomor referensi diberikan **berdasarkan pertama kali sumber muncul di dalam esai**.
                            * Jika sumber yang sama digunakan kembali pada bagian lain, gunakan **nomor yang sama**, jangan membuat nomor baru.
                            * Sitasi ditempatkan pada akhir kalimat atau akhir paragraf yang memuat informasi dari sumber tersebut.

                            Contoh:

                            > Harga cabai merah mengalami kenaikan akibat terganggunya distribusi antardaerah menjelang hari besar keagamaan **[1]**.

                            atau

                            > Pemerintah daerah bersama Bulog meningkatkan intensitas operasi pasar sebagai langkah stabilisasi harga **[2][5]**.

                            * Apabila suatu kalimat disusun dari beberapa artikel, cantumkan seluruh nomor referensi yang relevan, misalnya **[2][4][7]**.
                            * Jangan membuat sitasi terhadap sumber yang tidak terdapat pada korpus berita.
                            * Jangan mengarang informasi bibliografi.

                            ---

                            ### IV. Daftar Pustaka (WAJIB)

                            Setelah esai selesai, buat bagian:

                            # Daftar Pustaka

                            Ketentuannya:

                            * Daftar pustaka disusun **berdasarkan nomor referensi**, bukan alfabet.
                            * Nomor pada daftar pustaka **harus sama persis** dengan nomor sitasi yang digunakan dalam esai.
                            * Setiap nomor hanya muncul satu kali.
                            * Jangan menambahkan referensi yang tidak pernah disitasi.

                            Gunakan format berikut:

                            [1] Nama Media. Tanggal Publikasi. *Judul Artikel*. URL

                            Apabila URL tidak tersedia:

                            [1] Nama Media. Tanggal Publikasi. *Judul Artikel*.

                            Contoh:

                            [1] Kompas. 15 Juni 2026. *Harga Cabai di Papua Naik akibat Gangguan Distribusi*.

                            [2] Antara. 17 Juni 2026. *Bulog Gelar Operasi Pasar di Jayapura*.

                            ---

                            ### V. Ketentuan Format & Gaya Bahasa

                            * Gunakan bahasa Indonesia formal, objektif, akademis, dan analitis.
                            * Gunakan **bold** pada frasa penting, angka strategis, nama kebijakan, indikator utama, atau temuan penting agar mudah dipindai oleh pembaca tingkat eksekutif.
                            * Hindari bullet point pada bagian isi analisis.
                            * Pertahankan alur narasi yang runtut dari pembukaan, analisis, hingga penutup.
                            * Jangan menambahkan informasi di luar korpus berita.
                            * Jika terdapat perbedaan informasi antarartikel, jelaskan secara objektif dengan tetap memberikan sitasi yang sesuai.

                            ---

                            ### KORPUS BERITA

                            {concatenated_content}

                            """
                            
                            daftar_model_fallback = [
                                "gemini-2.5-flash", 
                                "gemini-3.1-flash-lite",
                                "gemini-3-flash-preview",
                                "gemini-2.5-flash-lite"
                            ]
                            
                            response_stream = None
                            model_terpilih = None
                            list_errors = []
                            
                            for model_name in daftar_model_fallback:
                                try:
                                    response_stream = client.models.generate_content_stream(
                                        model=model_name,
                                        contents=prompt_instruksi
                                    )
                                    model_terpilih = model_name
                                    break  
                                except Exception as e:
                                    list_errors.append(f"- **{model_name}**: {str(e)}")
                                    st.toast(f"🔄 {model_name} sibuk/gagal, mencoba cadangan berikutnya...", icon="⚠️")
                                    continue

                            if response_stream is None:
                                error_summary = "\n".join(list_errors)
                                st.error(
                                    f"🚨 **Semua model Gemini gagal merespons.** Silakan coba sesaat lagi.\n\n"
                                    f"**Detail Log Kegagalan Sistem:**\n{error_summary}"
                                )
                            else:
                                full_response_text = []
                                for chunk in response_stream:
                                    if chunk.text:
                                        full_response_text.append(chunk.text)
                                        area_konten.markdown("".join(full_response_text))
                                
                                final_text = "".join(full_response_text)
                                if final_text:
                                    simpan_summary_ke_db(target_keyword, periode_str, final_text)
                                    st.session_state[state_key] = final_text
                                    st.session_state[state_status_key] = f"Hasil Diperbarui ({model_terpilih}) ✨"
                                    
                                    area_judul.success(f"### 📊 Executive Summary by AI: {display_title_keyword} ({st.session_state[state_status_key]})")
                                    st.toast("✅ Ringkasan berhasil diperbarui!", icon="🚀")
                                    
                                    time.sleep(0.5)
                                    st.rerun()
                                    
                        except Exception as main_e:
                            st.error(f"Terjadi kesalahan internal sistem: {main_e}")
        else:
            st.info("❌ Tidak ada data untuk ditampilkan.")

    with tab2:
        st.subheader("📈 Visualisasi Data")
        if len(filtered_df) > 0:
            col1, col2 = st.columns([1, 1], gap="large")
            with col1:
                sentimen_count = filtered_df["Sentimen"].value_counts().reset_index()
                sentimen_count.columns = ["Sentimen", "Jumlah"]
                fig_sentimen = px.pie(sentimen_count, names="Sentimen", values="Jumlah", title="Distribusi Sentimen", color="Sentimen", color_discrete_map={"Positif": "#4CAF50", "Negatif": "#F44336", "Netral": "#9E9E9E"}, hole=0.5)
                st.plotly_chart(fig_sentimen, width='stretch')
            with col2:
                top_10_m = filtered_df["media"].value_counts().head(10).reset_index()
                top_10_m.columns = ["Media", "Jumlah"]
                fig_media = px.bar(top_10_m, x="Jumlah", y="Media", orientation="h", title="Top 10 Media", color_continuous_scale="Blues")
                st.plotly_chart(fig_media, width='stretch')
        else:
            st.info("Tidak ada data untuk grafik.")

    with tab3:
        st.subheader("📂 Database Berita")
        if len(filtered_df) > 0:
            display_df = filtered_df[["kata_kunci", "judul", "media", "waktu_tampilan", "Sentimen", "isi_konten"]].copy()
            display_df["waktu_tampilan"] = pd.to_datetime(display_df["waktu_tampilan"]).dt.strftime("%d %b %Y, %H:%M")
            selected_rows = st.dataframe(display_df, width='stretch', hide_index=True, height=500, selection_mode="single-row", on_select="rerun")
            
            selected_row_index = selected_rows["selection"]["rows"]
            if selected_row_index:
                show_article(filtered_df.iloc[selected_row_index[0]])
        else:
            st.info("❌ Tidak ada data berita.")

    st.markdown("<br><hr><div class='footer'>© 2026 | News Intelligence Dashboard | Yenro PSagala - BPS Provinsi Papua</div>", unsafe_allow_html=True)