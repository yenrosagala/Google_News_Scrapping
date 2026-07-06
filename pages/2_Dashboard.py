import streamlit as st
import pandas as pd
import re
from datetime import datetime
import plotly.express as px
from google import genai  # Client resmi Google Genai SDK

# Import internal services proyek Anda
from app.services.database_service import db_service 
from app.services.scraper_service import scraper_service
from app.services.report_service import report_service  # Service PDF bawaan Anda

st.set_page_config(page_title="Dashboard Monitoring Berita", layout="wide")

st.title("📊 Dashboard Monitoring Berita")

# Helper function untuk membaca URL bersih tanpa hit internet
def dapatkan_link_tampil(row_data):
    return row_data.get("url") or row_data.get("link") or ""

# =========================================================
# SINKRONISASI OTOMATIS (ON LOAD / DATA TERAKHIR)
# =========================================================

# 1. Ambil data mentah terakhir dari database
df_raw = db_service.get_latest_scraped_data(limit=100)

# 2. Logika Last Chance: Jalankan auto-scraping jika DB benar-benar kosong saat dibuka
if df_raw.empty:
    with st.spinner("💡 Database kosong. Mengambil data awal dari Google News secara otomatis..."):
        keyword_default = "Teknologi" 
        data_baru = scraper_service.execute_scraping_workflow(keyword=keyword_default, limit=20)
        
        if data_baru:
            db_service.save_articles(data_baru)
            df_raw = db_service.get_latest_scraped_data(limit=100)
        else:
            st.error("🛑 Gagal mengambil data otomatis. Cek koneksi atau logs.")

# =========================================================
# SIDEBAR CONTROL PANEL & FILTERING DATA
# =========================================================
filtered_df = pd.DataFrame()

if not df_raw.empty:
    with st.sidebar:
        st.title("🎛️ Control Panel")
        st.markdown("---")
        st.markdown("### Filter Data Dashboard")
        
        # Filter Kata Kunci
        options_kw = list(df_raw["kata_kunci"].unique()) if "kata_kunci" in df_raw.columns else []
        selected_keywords = st.multiselect("Filter Keyword", options=options_kw, default=options_kw[:1] if options_kw else None)
        
        # Filter Sentimen
        options_sent = list(df_raw["Sentimen"].unique()) if "Sentimen" in df_raw.columns else ["POSITIVE", "NEUTRAL", "NEGATIVE"]
        selected_sentiments = st.multiselect("Filter Sentimen", options=options_sent, default=options_sent)
        
        # Filter Media
        col_media = "media" if "media" in df_raw.columns else ("source" if "source" in df_raw.columns else None)
        options_media = list(df_raw[col_media].unique()) if col_media else []
        selected_media = st.multiselect("Filter Media", options=options_media, default=None)

    # Proses Filtering Data
    filtered_df = df_raw.copy()
    if selected_keywords:
        filtered_df = filtered_df[filtered_df["kata_kunci"].isin(selected_keywords)]
    if selected_sentiments:
        filtered_df = filtered_df[filtered_df["Sentimen"].isin(selected_sentiments)]
    if selected_media and col_media:
        filtered_df = filtered_df[filtered_df[col_media].isin(selected_media)]

# =========================================================
# RENDER UTAMA DASHBOARD
# =========================================================
if not filtered_df.empty:
    
    # METRIK UTAMA ROW
    kpi1, kpi2, kpi3 = st.columns(3)
    with kpi1:
        st.metric("Total Berita Terfilter", len(filtered_df))
    with kpi2:
        media_count = filtered_df[col_media].nunique() if col_media else 0
        st.metric("Portal Media Unik", media_count)
    with kpi3:
        st.metric("Keyword Aktif", filtered_df["kata_kunci"].nunique() if "kata_kunci" in filtered_df.columns else 1)

    # PENYUSUNAN SISTEM TAB
    tab1, tab2, tab3 = st.tabs(["📝 Analisis AI", "📈 Visualisasi Grafik", "📂 Tabel Data"])

    # -----------------------------------------------------
    # TAB 1: ANALISIS AI & GENERATE SUMMARY
    # -----------------------------------------------------
    with tab1:
        st.subheader("📋 Ringkasan Eksekutif Konten (Official Gemini Client)")
        
        # Siapkan Korpus Data Teks untuk Prompt
        clean_df = filtered_df.dropna(subset=['isi_konten', 'judul'])
        formatted_articles = [
            f"Media: {row.get(col_media, '-')}\nJudul: {row['judul']}\nIsi: {row['isi_konten']}" 
            for _, row in clean_df.head(15).iterrows()  # Ambil top 15 untuk efisiensi tokens
        ]
        concatenated_content = "\n\n".join(formatted_articles)
        
        # --- PERBAIKAN: INISIALISASI VARIABEL METADATA YANG HILANG ---
        display_title_keyword = ", ".join(selected_keywords) if selected_keywords else "Umum"
        date_range_str = datetime.now().strftime("%d %B %Y")
        t_media = filtered_df[col_media].value_counts().head(3) if col_media else {}
        # --- PERBAIKAN SINKRONISASI METADATA (Bebas Ambiguous Series Error) ---
        display_title_keyword = ", ".join(selected_keywords) if selected_keywords else "Umum"
        date_range_str = datetime.now().strftime("%d %B %Y")
        
        # Ambil top 3 media teraktif
        t_media = filtered_df[col_media].value_counts().head(3) if col_media else pd.Series()
        
        # Perbaikan Evaluasi Kondisi Menggunakan properti .empty bawaan Pandas
        if not t_media.empty:
            t_media_str = ", ".join([f"{m} ({c} artikel)" for m, c in t_media.items()])
        else:
            t_media_str = "Tidak Terdeteksi"
            
        catatan_regenerate = ""

        # 1. Ambil secara aman dari st.secrets menggunakan sistem fallback get()
        raw_keys = st.secrets.get("GEMINI_API_KEYS")

        # 2. Validasi tipe data: Pastikan formatnya adalah List/Array
        if isinstance(raw_keys, list):
            list_keys = [k.strip() for k in raw_keys if k and str(k).strip()]
        elif isinstance(raw_keys, str) and raw_keys.strip():
            list_keys = [raw_keys.strip()]
        else:
            list_keys = []

        if not list_keys:
            list_keys = [None]

        # Perbaikan Struktur Session State Key
        state_key = "gemini_dashboard_summary"
        state_status_key = "gemini_summary_status"
        if state_key not in st.session_state:
            st.session_state[state_key] = ""
        if state_status_key not in st.session_state:
            st.session_state[state_status_key] = ""

        # Tombol Pemicu AI
        if st.button("✨ Hasilkan Narasi Ringkasan Otomatis Berbasis Fakta"):
            if not concatenated_content.strip():
                st.warning("Tidak ada konten artikel yang layak untuk dianalisis oleh AI.")
            else:
                # Membuat container kosong untuk efek stream visual buatan
                area_konten = st.empty()
                area_konten.info("⏳ Gemini AI sedang menyusun esai analisis mendalam, mohon tunggu...")
                
                daftar_model_fallback = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
                response_text = None
                model_terpilih = None
                list_errors = []

                for idx, api_key in enumerate(list_keys):
                    key_log = f"Key #{idx+1} ({api_key[:6]}...)" if api_key else "Default Env"
                    try:
                        client = genai.Client(api_key=api_key) if api_key else genai.Client()
                        
                        for model_name in daftar_model_fallback:
                            try:
                                prompt_instruksi = f"""
                                Judul Tugas: Analisis Berita Eksekutif Komprehensif (Metode Terintegrasi 5W+1H dengan Sitasi Numerik)

                                ## Instruksi Utama
                                Berdasarkan KORPUS BERITA yang diberikan, buatlah sebuah laporan analisis berita eksekutif yang mendalam, komprehensif, objektif, dan berbasis fakta dalam bentuk esai naratif (narrative essay) yang mengalir. Jangan menggunakan subjudul yang memisahkan unsur 5W+1H (What, Who, When, Where, Why, How), melainkan integrasikan seluruh unsur tersebut secara alami ke dalam paragraf-paragraf analisis.

                                Sebelum menulis isi esai, buatlah satu judul utama yang paling sesuai dengan keseluruhan isi korpus berita.

                                ---
                                ## I. Ketentuan Judul (WAJIB)
                                - Buat satu judul utama sebelum isi analisis.
                                - Panjang judul sekitar 10–20 kata.

                                ---
                                ## II. Pedoman Metadata & Konteks
                                Pada paragraf pembuka, jelaskan secara natural informasi berikut:
                                - Profil Kata Kunci yang Dianalisis: {display_title_keyword}
                                - Rentang Waktu Analisis (waktu_tampil): {date_range_str}
                                - Tiga Kontributor Media Teratas: {t_media_str}

                                ---
                                ## III. Kerangka Analisis
                                Berdasarkan seluruh artikel pada KORPUS BERITA, lakukan analisis yang mengintegrasikan seluruh unsur 5W+1H ke dalam narasi esai.

                                ---
                                ## IV. Ketentuan Sitasi (WAJIB)
                                Setiap informasi faktual harus disertai sitasi numerik berbentuk [1], [2], [3], dan seterusnya.

                                ---
                                ## V. Daftar Pustaka (WAJIB)
                                Setelah esai selesai, buat bagian berjudul Daftar Pustaka. Format: [1] Nama Media. Tanggal Publikasi. *Judul Artikel*.

                                ---
                                ## VI. Ketentuan Format Penulisan
                                - Gunakan bahasa Indonesia yang formal, objektif, analitis, dan profesional.
                                - Gunakan bold pada informasi strategis seperti angka penting atau institusi penting.

                                ---
                                ## VII. Struktur Output (Wajib Ikuti Format Label Ini)
                                Susun hasil akhir dengan urutan berlabel kaku berikut:
                                Judul Analisis
                                [Tulis Judul Utama Disini]

                                Isi Analisis
                                [Tulis Seluruh Paragraf Esai Naratif Beserta Sitasi Disini]

                                Daftar Pustaka
                                [Tulis Daftar Pustaka Numerik Disini]

                                KORPUS BERITA:
                                {concatenated_content}
                                {catatan_regenerate}
                                """
                                
                                response = client.models.generate_content(
                                    model=model_name,
                                    contents=prompt_instruksi
                                )
                                
                                if response.text:
                                    response_text = response.text
                                    model_terpilih = model_name
                                    break
                            except Exception as model_e:
                                list_errors.append(f"- **{model_name}** ({key_log}) Error: {str(model_e)}")
                                continue
                        if response_text:
                            break
                    except Exception as client_err:
                        list_errors.append(f"- Init Client Gagal ({key_log}): {str(client_err)}")
                        continue

                if response_text:
                    st.session_state[state_key] = response_text
                    st.session_state[state_status_key] = f"Hasil Diperbarui ({model_terpilih} via {key_log}) ✨"
                    st.rerun()
                else:
                    error_summary = "\n".join(list_errors)
                    st.error(f"🚨 **Semua API Key dan Model Gemini gagal merespons.**\n\n**Log:**\n{error_summary}")

        # Tampilkan Hasil Ringkasan jika Sudah Terisi
        if st.session_state[state_key]:
            st.markdown(f"### Hasil Analisis Eksekutif ({st.session_state[state_status_key]})")
            st.info(st.session_state[state_key])
            
            st.divider()
            st.subheader("🖨️ Cetak Laporan Eksekutif")
            
            if st.button("📥 Ekspor Hasil Rangkuman AI ke Berkas PDF"):
                with st.spinner("Menyusun file PDF resmi..."):
                    data_list = filtered_df.to_dict(orient="records")
                    file_report = report_service.export_articles_to_pdf(data_list, "Laporan_Monitoring_Berita.pdf")
                    
                    with open(file_report, "rb") as pdf_file:
                        st.download_button(
                            label="Klik di Sini untuk Mengunduh PDF",
                            data=pdf_file,
                            file_name=f"Laporan_Monitoring_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf"
                        )

    # -----------------------------------------------------
    # TAB 2: VISUALISASI GRAFIK
    # -----------------------------------------------------
    with tab2:
        st.subheader("📈 Analisis Grafik Distribusi Data Berita")
        g_col1, g_col2 = st.columns(2)
        
        with g_col1:
            if "Sentimen" in filtered_df.columns:
                sentimen_df = filtered_df["Sentimen"].value_counts().reset_index()
                sentimen_df.columns = ["Sentimen", "Jumlah"]
                fig_pie = px.pie(
                    sentimen_df, names="Sentimen", values="Jumlah", 
                    title="Proporsi Sentimen Berita", hole=0.4,
                    color="Sentimen",
                    color_discrete_map={"POSITIVE": "#4CAF50", "NEGATIVE": "#F44336", "NEUTRAL": "#9E9E9E"}
                )
                st.plotly_chart(fig_pie, use_container_width=True)
                
        with g_col2:
            if col_media:
                media_df = filtered_df[col_media].value_counts().head(10).reset_index()
                media_df.columns = ["Media", "Jumlah"]
                fig_bar = px.bar(
                    media_df, x="Jumlah", y="Media", orientation="h",
                    title="Top 10 Media Teraktif",
                    color_discrete_sequence=["#38BDF8"]
                )
                fig_bar.update_yaxes(autorange="reversed")
                st.plotly_chart(fig_bar, use_container_width=True)

    # -----------------------------------------------------
    # TAB 3: TABEL DATA
    # -----------------------------------------------------
    with tab3:
        st.subheader("📰 Tabel Artikel Berita Hasil Filter")
        display_cols = ["kata_kunci", "judul", col_media, "waktu_tampilan", "Sentimen"]
        display_cols = [c for c in display_cols if c in filtered_df.columns]
        
        st.dataframe(filtered_df[display_cols], use_container_width=True, hide_index=True)

else:
    st.info("💡 Tidak ada data yang cocok dengan kriteria filter aktif saat ini.")

# =========================================================
# BAGIAN 3: OTORITAS MANIPULASI DATABASE (KHUSUS ADMIN)
# =========================================================
if st.session_state.get("authenticated", False) and st.session_state.get("role") == "admin":
    st.write("---")
    st.subheader("🛠️ Panel Manajemen Data (Wewenang Admin Only)")
    
    col_adm1, col_adm2 = st.columns(2)
    
    with col_adm1:
        st.markdown("**Koreksi Sentimen Manual**")
        target_id = st.text_input("Masukkan ID Artikel Berita", key="id_sentimen")
        new_sentiment = st.selectbox("Ubah Sentimen Ke", ["POSITIVE", "NEUTRAL", "NEGATIVE"])
        if st.button("Perbarui Sentimen"):
            if target_id:
                success = db_service.update_sentiment(target_id, new_sentiment)
                if success:
                    st.success(f"Sentimen untuk ID {target_id} berhasil diubah ke {new_sentiment}!")
                    st.rerun()
                else:
                    st.error("Gagal memperbarui. ID tidak ditemukan.")
            else:
                st.error("ID Artikel tidak boleh kosong!")
                
    with col_adm2:
        st.markdown("**Penghapusan Artikel Konten**")
        target_delete_id = st.text_input("Masukkan ID Artikel yang akan Dihapus", key="id_hapus")
        if st.button("⚠️ Hapus Artikel Permanen", type="secondary"):
            if target_delete_id:
                success = db_service.delete_article(target_delete_id)
                if success:
                    st.warning(f"Artikel dengan ID {target_delete_id} berhasil dihapus dari database.")
                    st.rerun()
                else:
                    st.error("Gagal menghapus. ID tidak ditemukan.")
            else:
                st.error("ID Artikel tidak boleh kosong!")