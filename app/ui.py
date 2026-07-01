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
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)


# ======================================================
# HELPER FUNCTION - EXECUTIVE SUMMARY GENERATOR
# ======================================================
@st.cache_data
def buat_ringkasan_eksekutif(dataframe, num_sentences=5):
    """
    Membuat ringkasan eksekutif dari seluruh konten artikel menggunakan extractive summarization.
    
    Parameters:
    -----------
    dataframe : pd.DataFrame
        Dataframe dengan kolom 'isi_konten'
    num_sentences : int
        Jumlah kalimat untuk ringkasan (default: 5)
    
    Returns:
    --------
    str : Ringkasan teks atau pesan jika konten kosong
    """
    try:
        # Kumpulkan semua konten artikel
        konten_semua = dataframe["isi_konten"].dropna()
        konten_semua = konten_semua[konten_semua.str.len() > 0]
        
        if len(konten_semua) == 0:
            return "Tidak ada konten artikel yang tersedia untuk diringkas."
        
        # Gabungkan semua konten
        teks_gabungan = " ".join(konten_semua.astype(str))
        
        if len(teks_gabungan.strip()) < 100:
            return "Konten artikel terlalu singkat untuk diringkas."
        
        # Tokenisasi kalimat
        try:
            kalimat = sent_tokenize(teks_gabungan, language='english')
        except:
            # Fallback jika tokenizer gagal
            kalimat = re.split(r'[.!?]+', teks_gabungan)
            kalimat = [k.strip() for k in kalimat if k.strip()]
        
        if len(kalimat) < 2:
            return "Konten artikel terlalu singkat untuk diringkas."
        
        # Hitung TF-IDF sederhana
        words = re.findall(r'\w+', teks_gabungan.lower())
        word_freq = {}
        for word in words:
            if len(word) > 3:  # Hanya kata dengan length > 3
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Normalize
        if word_freq:
            max_freq = max(word_freq.values())
            for word in word_freq:
                word_freq[word] = word_freq[word] / max_freq
        
        # Hitung skor kalimat
        skor_kalimat = {}
        for i, kalimat_text in enumerate(kalimat):
            skor = 0
            words_kalimat = re.findall(r'\w+', kalimat_text.lower())
            for word in words_kalimat:
                skor += word_freq.get(word, 0)
            skor_kalimat[i] = skor
        
        # Ambil top N kalimat
        num_ringkas = min(num_sentences, len(kalimat))
        top_kalimat = sorted(skor_kalimat.items(), key=lambda x: x[1], reverse=True)[:num_ringkas]
        top_kalimat = sorted(top_kalimat, key=lambda x: x[0])  # Urutkan kembali sesuai urutan asli
        
        ringkasan = " ".join([kalimat[idx] for idx, _ in top_kalimat])
        
        return ringkasan if ringkasan.strip() else "Gagal membuat ringkasan dari konten artikel."
        
    except Exception as e:
        return f"Error generating summary: {str(e)}"


# ======================================================
# DEFINISI DIALOG (Harus berada di top-level / luar fungsi render jika memungkinkan,
# atau minimal di luar kontrol seleksi baris agar tidak didefinisikan ulang)
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
    
    # Memuat isi konten dari database
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
        /* Global */
        .main .block-container {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        /* Header */
        .main-title {
            background: linear-gradient(90deg, #0078D4, #106EBE);
            padding: 25px;
            border-radius: 12px;
            color: white;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }

        .main-title h1 {
            margin: 0;
            font-size: 2.5rem;
            font-weight: 600;
        }

        .main-title p {
            margin: 0.5rem 0 0 0;
            font-size: 1.1rem;
            opacity: 0.9;
        }

        /* Metric Cards */
        .kpi-box {
            background: linear-gradient(135deg, #0078D4 0%, #106EBE 100%);
            padding: 20px;
            border-radius: 10px;
            color: white;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
            transition: all 0.2s ease;
        }

        .kpi-box:hover {
            transform: translateY(-3px);
            box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
        }

        .kpi-label {
            font-size: 0.85rem;
            opacity: 0.9;
            margin-bottom: 8px;
            font-weight: 500;
        }

        .kpi-value {
            font-size: 2rem;
            font-weight: 700;
            color: #FFFFFF;
        }

        /* Button Styling */
        .stButton>button {
            border-radius: 6px;
            font-weight: 500;
        }

        .stButton>button[kind="primary"] {
            background-color: #0078D4;
            color: white;
        }

        .stButton>button[kind="secondary"] {
            background-color: #F3F2F1;
            color: #323130;
            border: 1px solid #C8C6C4;
        }

        .stButton>button:hover {
            opacity: 0.9;
        }

        /* Sidebar */
        [data-testid="stSidebar"] {
            background-color: #F3F2F1;
            border-right: 1px solid #E1DFDD;
        }

        [data-testid="stSidebar"] .css-1lcbmhc {
            padding-top: 1rem;
        }

        /* Dataframe */
        .stDataFrame {
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06);
        }

        /* Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
            background-color: #F8F8F8;
            padding: 8px;
            border-radius: 8px;
        }

        .stTabs [data-baseweb="tab"] {
            padding: 12px 20px;
            font-weight: 500;
            color: #605E5C;
        }

        .stTabs [aria-selected="true"] {
            background-color: #0078D4;
            color: white;
            border-radius: 6px;
        }

        /* Dialog */
        [data-testid="stDialog"] {
            border-radius: 12px;
        }

        /* Footer */
        .footer {
            text-align: center;
            padding: 1rem;
            color: #605E5C;
            font-size: 0.9rem;
            border-top: 1px solid #E1DFDD;
            margin-top: 2rem;
        }

        /* Tooltip */
        .tooltip {
            position: relative;
            display: inline-block;
            cursor: help;
        }

        .tooltip .tooltiptext {
            visibility: hidden;
            width: 200px;
            background-color: #323130;
            color: #FFFFFF;
            text-align: center;
            border-radius: 6px;
            padding: 8px;
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 50%;
            margin-left: -100px;
            opacity: 0;
            transition: opacity 0.3s;
            font-size: 0.85rem;
        }

        .tooltip:hover .tooltiptext {
            visibility: visible;
            opacity: 1;
        }
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

        # Tampilkan User Type Info
        user_type = st.session_state.get("user_type", "unknown")
        if user_type == "umum":
            st.info("👥 **User Umum**\n\nDashboard view-only mode")
        elif user_type == "login":
            st.success("🔐 **User Login**\n\nFull access including delete")

        st.markdown("---")

        # Keyword Input
        keyword = st.text_input("🔍 Keyword Pencarian", placeholder="Contoh: Inflasi Papua")

        # Run Scraping Button
        if st.button("🚀 Jalankan Scraping", use_container_width=True, type="primary"):
            if not keyword.strip():
                st.warning("Masukkan keyword terlebih dahulu.")
            else:
                progress_bar = st.progress(0.0)
                status_text = st.empty()

                try:
                    # IMPLEMENTASI BARU: Memanggil pipeline backend murni dengan callback terisolasi
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

        # Hapus Database - Hanya untuk User Login
        user_type = st.session_state.get("user_type", None)
        
        if user_type == "login":
            # Menggunakan st.popover agar kontainer UI bertahan saat proses input
            with st.popover("🗑 Hapus Seluruh Database", use_container_width=True):
                st.warning("⚠️ Tindakan ini akan menghapus semua artikel dari database!")
                password_konfirmasi = st.text_input("Masukkan password akun Anda", type="password", key="del_pwd")
                
                if st.button("Konfirmasi Hapus Data", type="primary", use_container_width=True):
                    # Mengambil password login yang tersimpan di database.py
                    password_login = st.session_state.get("saved_db_password", "")
                    
                    # Validasi: mencocokkan input konfirmasi dengan password sesi login saat ini
                    if password_konfirmasi == password_login: 
                        jumlah = hapus_semua_data_db()
                        st.success(f"✅ {jumlah} berita berhasil dihapus.")
                        st.rerun()
                    else:
                        st.error("❌ Password salah. Harus sama dengan password login Anda.")
        else:
            # User Umum - Tampilkan pesan bahwa fitur ini tidak tersedia
            st.button(
                "🗑 Hapus Seluruh Database",
                use_container_width=True,
                disabled=True,
                help="Fitur ini hanya tersedia untuk User Login"
            )

        st.markdown("---")

        # Logout Button
        if st.button("🚪 Logout", use_container_width=True, type="secondary"):
            logout()

    # ======================================================
    # DATA FETCH & PREP
    # ======================================================

    df = ambil_data_dari_db()

    if len(df) > 0:
        df["waktu_tampilan"] = pd.to_datetime(df["waktu_tampilan"], errors="coerce")
        df["tanggal"] = df["waktu_tampilan"].dt.date
        df["Sentimen"] = df["isi_konten"].apply(hitung_sentimen_leksikon)

        # Hitung KPI
        total_berita = len(df)
        berita_dengan_isi = df["isi_konten"].notna().sum()
        jumlah_media = df["media"].nunique()
        jumlah_keyword = df["kata_kunci"].nunique()

        # Filter Data
        col1, col2 = st.columns([2, 1])
        with col1:
            selected_keyword = st.multiselect(
                "Filter Keyword",
                options=df["kata_kunci"].unique(),
                default=None
            )
        with col2:
            selected_sentimen = st.multiselect(
                "Filter Sentimen",
                options=["Positif", "Negatif"],
                default=["Positif", "Negatif"]
            )

        col3, col4 = st.columns([2, 1])
        with col3:
            selected_media = st.multiselect(
                "Filter Media",
                options=df["media"].unique(),
                default=None
            )
        with col4:
            min_date = df["waktu_tampilan"].min().date()
            max_date = df["waktu_tampilan"].max().date()
            
            # Memastikan penanganan input rentang tanggal aman dari error kosong/tunggal
            date_range = st.date_input(
                "Rentang Tanggal",
                value=[min_date, max_date],
                min_value=min_date,
                max_value=max_date
            )
            
            start_date, end_date = None, None
            if isinstance(date_range, list) or isinstance(date_range, tuple):
                if len(date_range) == 2:
                    start_date, end_date = date_range

        # Apply Filters
        filtered_df = df.copy()
        if selected_keyword:
            filtered_df = filtered_df[filtered_df["kata_kunci"].isin(selected_keyword)]
        if selected_media:
            filtered_df = filtered_df[filtered_df["media"].isin(selected_media)]
        if selected_sentimen:
            filtered_df = filtered_df[filtered_df["Sentimen"].isin(selected_sentimen)]
        if start_date and end_date:
            mask = (filtered_df["waktu_tampilan"].dt.date >= start_date) & \
                   (filtered_df["waktu_tampilan"].dt.date <= end_date)
            filtered_df = filtered_df[mask]

    else:
        total_berita = 0
        berita_dengan_isi = 0
        jumlah_media = 0
        jumlah_keyword = 0
        filtered_df = pd.DataFrame()

    # ======================================================
    # KPI CARDS
    # ======================================================

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        st.markdown(f"""
        <div class="kpi-box">
            <div class="kpi-label">📰 Total Berita</div>
            <div class="kpi-value">{total_berita:,}</div>
        </div>
        """, unsafe_allow_html=True)

    with kpi2:
        st.markdown(f"""
        <div class="kpi-box">
            <div class="kpi-label">📄 Dengan Isi</div>
            <div class="kpi-value">{berita_dengan_isi}</div>
        </div>
        """, unsafe_allow_html=True)

    with kpi3:
        st.markdown(f"""
        <div class="kpi-box">
            <div class="kpi-label">🏢 Jumlah Media</div>
            <div class="kpi-value">{jumlah_media}</div>
        </div>
        """, unsafe_allow_html=True)

    with kpi4:
        st.markdown(f"""
        <div class="kpi-box">
            <div class="kpi-label">🔖 Jumlah Keyword</div>
            <div class="kpi-value">{jumlah_keyword}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ======================================================
    # CHARTS & TABS
    # ======================================================

    tab1, tab2, tab3 = st.tabs(["📊 Analisis", "📈 Grafik", "📂 Data"])

    with tab1:
        st.subheader("📋 Ringkasan Eksekutif")
        
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
                
                st.markdown(f"""
                **Analisis Sentimen**
                - 🟢 Positif: {positif} ({persen_positif:.1f}%)
                - 🔴 Negatif: {negatif} ({persen_negatif:.1f}%)
                - ⚪ Netral: {netral} ({100 - persen_positif - persen_negatif:.1f}%)
                """)
            
            with col2:
                top_media = filtered_df["media"].value_counts().head(3)
                st.markdown("**Top 3 Media**")
                for idx, (media, count) in enumerate(top_media.items(), 1):
                    st.write(f"{idx}. {media}: {count} berita")
            
            with col3:
                trend_harian = filtered_df.groupby(filtered_df["waktu_tampilan"].dt.date).size()
                rata_rata = trend_harian.mean()
                maks_hari = trend_harian.max()
                min_hari = trend_harian.min()
                
                st.markdown(f"""
                **Statistik Harian**
                - Rata-rata: {rata_rata:.0f} berita/hari
                - Puncak: {maks_hari} berita
                - Terendah: {min_hari} berita
                """)
            
            st.divider()
            
            st.markdown("**Insights Utama**")
            insights = []
            
            if persen_positif > persen_negatif:
                insights.append(f"📈 Sentimen cenderung positif dengan {persen_positif:.1f}% berita positif")
            elif persen_negatif > persen_positif:
                insights.append(f"📉 Sentimen cenderung negatif dengan {persen_negatif:.1f}% berita negatif")
            else:
                insights.append("⚖️ Sentimen seimbang antara positif dan negatif")
            
            if len(top_media) > 0:
                insights.append(f"📰 Media dominan: {top_media.index[0]} dengan {top_media.values[0]} artikel")
            
            total_isi = filtered_df["isi_konten"].notna().sum()
            persen_isi = (total_isi / len(filtered_df) * 100) if len(filtered_df) > 0 else 0
            insights.append(f"📄 {persen_isi:.1f}% berita memiliki isi lengkap")
            
            for insight in insights:
                st.write(f"• {insight}")
            
            # ======================================================
            # EXECUTIVE SUMMARY - Ringkasan Konten Berita via g4f Library
            # ======================================================
            st.divider()
            
            with st.expander("📝 Ringkasan Eksekutif Konten (g4f Client)", expanded=False):
                st.markdown("Klik tombol di bawah untuk meminta AI merangkum poin-poin utama berita.")
                
                if st.button("✨ Hasilkan Narasi Ringkasan Otomatis", key="generate_g4f_summary"):
                    with st.spinner("🔄 Sedang menganalisis teks konten seluruh berita..."):
                        try:
                            # Import Client resmi dari library g4f
                            from g4f.client import Client
                            
                            # Mengambil maksimal 8-10 berita teratas
                            sample_texts = filtered_df["isi_konten"].dropna().head(10).tolist()
                            
                            if not sample_texts:
                                st.warning("Tidak ditemukan teks artikel utuh pada kolom 'isi_konten' untuk dirangkum.")
                            else:
                                # Menggabungkan korpus berita menjadi satu dokumen prompt
                                gabungan_berita = ""
                                for idx, teks in enumerate(sample_texts, 1):
                                    gabungan_berita += f"\n[ARTIKEL {idx}]\n{teks}\n"
                                
                                prompt_instruksi = f"""
                                Anda adalah seorang analis media profesional yang andal. 
                                Tugas Anda adalah membaca kumpulan artikel berita di bawah ini dan menyusun sebuah Ringkasan Eksekutif (Executive Summary) yang padat, informatif, dan ringkas dalam Bahasa Indonesia.

                                Poin wajib dalam ringkasan:
                                1. Topik atau isu utama yang paling mendominasi dari seluruh artikel.
                                2. Dampak signifikan (ekonomi/lingkungan/sosial) yang dilaporkan.
                                3. Kesimpulan naratif umum dari tren berita ini.

                                Gunakan format poin-poin markdown yang rapi. Jangan mengada-ada atau memalsukan fakta di luar teks yang diberikan.

                                Berikut data beritanya:
                                {gabungan_berita}
                                """
                                
                                # Inisialisasi g4f Client sesuai panduan Anda
                                client = Client()
                                
                                # Memanggil completion. Anda bisa menggunakan "gpt-4o", "gemini-flash", atau "llama-3.1-70b"
                                response = client.chat.completions.create(
                                    model="gpt-4o",  
                                    messages=[{"role": "user", "content": prompt_instruksi}],
                                    web_search=False
                                )
                                
                                # Mengambil teks hasil akhir
                                ai_response = response.choices[0].message.content
                                
                                if ai_response:
                                    st.info(ai_response)
                                else:
                                    st.error("AI mengembalikan respons kosong. Silakan coba klik tombol kembali.")
                                    
                        except Exception as e:
                            st.error(f"Terjadi kegagalan pada g4f Client: {e}")
                            st.caption("Tip: Jika gagal, ganti parameter `model` ke opsi lain seperti 'gemini-flash' atau 'llama-3.1-70b' yang mungkin sedang memiliki provider aktif lebih stabil.")
        else:
            st.info("Tidak ada data untuk ditampilkan. Lakukan scraping terlebih dahulu.")

    with tab2:
        st.subheader("📈 Visualisasi Data")
        
        if len(filtered_df) > 0:
            col1, col2 = st.columns([1, 1], gap="large")

            with col1:
                # Donut Chart Sentimen
                sentimen_count = filtered_df["Sentimen"].value_counts().reset_index()
                sentimen_count.columns = ["Sentimen", "Jumlah"]

                fig_sentimen = px.pie(
                    sentimen_count,
                    names="Sentimen",
                    values="Jumlah",
                    title="Distribusi Sentimen",
                    color="Sentimen",
                    color_discrete_map={"Positif": "#4CAF50", "Negatif": "#F44336"},
                    hole=0.5
                )
                fig_sentimen.update_traces(textinfo='percent+label')
                fig_sentimen.update_layout(
                    title_x=0.5,
                    font=dict(size=14),
                    showlegend=True
                )
                st.plotly_chart(fig_sentimen, use_container_width=True)

            with col2:
                # Top 10 Media
                top_media = filtered_df["media"].value_counts().head(10).reset_index()
                top_media.columns = ["Media", "Jumlah"]

                fig_media = px.bar(
                    top_media,
                    x="Jumlah",
                    y="Media",
                    orientation="h",
                    title="Top 10 Media",
                    color="Jumlah",
                    color_continuous_scale="Blues"
                )
                fig_media.update_layout(
                    title_x=0.5,
                    yaxis={'categoryorder': 'total ascending'},
                    font=dict(size=12)
                )
                st.plotly_chart(fig_media, use_container_width=True)

            # Line Chart - Berita per Hari
            if "tanggal" in filtered_df.columns:
                berita_per_hari = filtered_df.groupby("tanggal").size().reset_index(name="Jumlah")
                berita_per_hari["tanggal"] = pd.to_datetime(berita_per_hari["tanggal"])

                fig_line = px.line(
                    berita_per_hari,
                    x="tanggal",
                    y="Jumlah",
                    title="Jumlah Berita per Hari",
                    markers=True
                )
                fig_line.update_traces(line_color="#0078D4")
                fig_line.update_layout(
                    title_x=0.5,
                    xaxis_title="Tanggal",
                    yaxis_title="Jumlah Berita",
                    hovermode="x unified"
                )
                st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("Tidak ada data untuk ditampilkan.")

    with tab3:
        st.subheader("📂 Database Berita")

        if len(filtered_df) > 0:

            # Buat salinan dataframe khusus tampilan tabel agar lebih rapi
            display_df = filtered_df[[
                "kata_kunci", "judul", "media", "waktu_tampilan", "Sentimen", "isi_konten"
            ]].copy()

            # Format tampilan tanggal ke format string yang mudah dibaca manusia
            display_df["waktu_tampilan"] = pd.to_datetime(display_df["waktu_tampilan"]).dt.strftime("%d %b %Y, %H:%M")

            # Tabel interaktif dengan mode seleksi satu baris (Single-Row)
            selected_rows = st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                height=500,
                selection_mode="single-row",
                on_select="rerun"
            )

            # Tombol Download Data Terfilter
            csv = filtered_df.to_csv(index=False, sep=";").encode('utf-8')
            st.download_button(
                label="⬇️ Download Data (Excel/CSV)",
                data=csv,
                file_name=f"news_data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )

            # Tombol Download Data Lengkap dengan kolom yang diinginkan
            export_df = filtered_df.copy()
            for col in ["kata_kunci", "judul", "media", "waktu_tampilan", "Sentimen", "isi_konten", "link"]:
                if col not in export_df.columns:
                    export_df[col] = ""

            export_df = export_df[["kata_kunci", "judul", "media", "waktu_tampilan", "Sentimen", "isi_konten", "link"]].copy()
            export_df = export_df.rename(columns={
                "waktu_tampilan": "waktu_tampil",
                "Sentimen": "sentimen",
                "isi_konten": "isi_konten",
                "link": "link_sumber"
            })

            export_csv = export_df.to_csv(index=False, sep=";").encode("utf-8")
            st.download_button(
                label="⬇️ Download Data Lengkap (CSV)",
                data=export_csv,
                file_name=f"news_data_lengkap_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )

            # ======================================================
            # LOGIKA POPUP DETAIL ARTIKEL (OTOMATIS TANPA LOOP)
            # ======================================================
            selected_row_index = selected_rows["selection"]["rows"]
            
            if selected_row_index:
                # Mengambil data asli dari baris yang dicentang berdasarkan urutan indeksnya
                row_terpilih = filtered_df.iloc[selected_row_index[0]]           
                
                # Langsung panggil fungsi dialog untuk memicu popup modal ke pengguna
                show_article(row_terpilih)

        else:
            st.info("❌ Tidak ada data berita yang sesuai filter.")

    # ======================================================
    # FOOTER
    # ======================================================
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown(
        '<div class="footer">© 2026 | News Intelligence Dashboard | Yenro Sagala - BPS Provinsi Papua</div>',
        unsafe_allow_html=True
    )