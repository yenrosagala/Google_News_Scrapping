import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
import re
from app.services.database_service import db_service
from app.services.sentiment_service import sentiment_service
from google import genai 
from app.services.scraper_service import scraper_service
from app.components.sidebar import render_sidebar




try:
    from app.services.report_service import ReportService
    generate_pdf_report = ReportService.export_articles_to_pdf
except ImportError:
    generate_pdf_report = None # Fallback jika belum diimplementasi sempurna

# =========================================================
# 1. INISIALISASI HALAMAN & STATE (ANTI-ERROR)
# =========================================================
st.set_page_config(page_title="FlashNews: Dashboard Berita", layout="wide", page_icon="📊")
st.title("📊 FlashNews: Dashboard Berita")
st.write("Menampilkan ringkasan, analisis, dan visualisasi data berita yang telah diambil melalui proses scraping.")

try:
    with open("app/assets/style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "role" not in st.session_state:
    st.session_state["role"] = "user"  
if "gemini_dashboard_summary" not in st.session_state:
    st.session_state["gemini_dashboard_summary"] = ""
if "active_keyword" not in st.session_state:
    st.session_state["active_keyword"] = []



@st.cache_data(ttl=60)
def load_dashboard_data():
    return db_service.get_latest_scraped_data(limit=1000)

df_raw = load_dashboard_data()

# Standarisasi Waktu (Timezone Stripping)
date_col = "published_date" if "published_date" in df_raw.columns else ("waktu_tampilan" if "waktu_tampilan" in df_raw.columns else None)

if not df_raw.empty and date_col:
    df_raw[date_col] = pd.to_datetime(df_raw[date_col], errors="coerce")
    if df_raw[date_col].dt.tz is not None:
        df_raw[date_col] = df_raw[date_col].dt.tz_localize(None)
    df_raw["tanggal_saja"] = df_raw[date_col].dt.date

if df_raw.empty:
    st.warning("Basis data kosong. Silakan jalankan Scraper terlebih dahulu untuk sinkronisasi data.")
    st.stop()

col_keyword = "keyword" if "keyword" in df_raw.columns else "kata_kunci"
col_media = "source" if "source" in df_raw.columns else "media"
col_content = "content" if "content" in df_raw.columns else "isi_konten"
col_title = "title" if "title" in df_raw.columns else "judul"
col_sentiment = "sentiment" if "sentiment" in df_raw.columns else ("Sentimen" if "Sentimen" in df_raw.columns else None)



        # =========================================================
        # 🟢 SCRAPER
        # =========================================================
    
    # Form Input User
with st.form("scraping_form"):
    keyword = st.text_input("Masukkan Kata Kunci (Keyword):", st.session_state.get("current_keyword", ""))
    num_results = st.number_input("Jumlah Berita:", min_value=5, max_value=100, value=20, step=5)
    submit_button = st.form_submit_button("Mulai Scraping")

    # Eksekusi saat Form disubmit
    if submit_button:
        if not keyword.strip():
            st.error("Keyword tidak boleh kosong!")
        else:
            st.session_state["current_keyword"] = keyword
            
            with st.spinner(f"Sedang mengambil {num_results} berita tentang '{keyword}'..."):
                # 1. Jalankan Scraper Pipeline
                
                articles = scraper_service.execute_scraping_workflow(keyword, num_results)
                                
                if articles:
                    # 2. Simpan ke database via db_service (Menyimpan URL Bersih)
                    saved_count = db_service.save_articles(articles)
                    
                    st.success(f"✅ Berhasil mengambil {len(articles)} artikel! {saved_count} artikel baru berhasil disimpan ke DB.")
                    
                    # 3. Paksa Streamlit rerun agar data langsung masuk ke preview database di bawah
                    st.rerun()
                else:
                    st.warning("Tidak ada berita yang ditemukan atau gagal melakukan parsing.")

st.divider()
    

# =========================================================
# 2. SIDEBAR INTERFACE: GAWAI LOGIN & OTORISASI ROLE
# =========================================================
st.sidebar.title("🔐 Otorisasi Akses")

if not st.session_state["authenticated"]:
    mode_pilihan = st.sidebar.radio("Pilih Mode Masuk:", ["User Umum (Read-Only)", "Administrator"])
    
    if mode_pilihan == "User Umum (Read-Only)":
        if st.sidebar.button("Masuk Sistem", use_container_width=True):
            st.session_state["authenticated"] = True
            st.session_state["role"] = "user"
            st.rerun()
            
    elif mode_pilihan == "Administrator":
        input_password = st.sidebar.text_input("Kata Sandi Admin:", type="password")
        if st.sidebar.button("Otorisasi Admin", type="primary", use_container_width=True):
            sandi_valid = st.secrets.get("ADMIN_PASSWORD", "admin123")
            if input_password == sandi_valid:
                st.session_state["authenticated"] = True
                st.session_state["role"] = "admin"
                st.sidebar.success("Otorisasi Berhasil!")
                st.rerun()
            else:
                st.sidebar.error("❌ Kata Sandi Administrator Salah!")
else:
    st.sidebar.info(f"Mode Aktif: **{st.session_state['role'].upper()}**")
    if st.sidebar.button("🚪 Keluar / Ganti Akun", use_container_width=True):
        st.session_state["authenticated"] = False
        st.session_state["role"] = "user"
        st.rerun()






# =========================================================
# 4. SIDEBAR CONTROL PANEL (FILTER)
# =========================================================
with st.sidebar:
    st.markdown("---")
    st.title("🎛️ Control Panel Data")
    
    available_options = list(df_raw[col_keyword].dropna().unique()) if col_keyword in df_raw.columns else []
    raw_defaults = st.session_state.active_keyword if isinstance(st.session_state.active_keyword, list) else []
    validated_defaults = [kw for kw in raw_defaults if kw in available_options]

    selected_keyword = st.multiselect("Filter Keyword", options=available_options, default=validated_defaults if validated_defaults else None)
    st.session_state.active_keyword = selected_keyword
    
    opsi_sentimen = list(df_raw[col_sentiment].dropna().unique()) if col_sentiment else ["POSITIVE", "NEGATIVE", "NEUTRAL"]
    selected_sentimen = st.multiselect("Filter Sentimen", options=opsi_sentimen, default=opsi_sentimen)
    
    opsi_media = list(df_raw[col_media].dropna().unique()) if col_media in df_raw.columns else []
    selected_media = st.multiselect("Filter Media", options=opsi_media, default=None)
    
    start_date, end_date = None, None
    if date_col and not df_raw[date_col].dropna().empty:
        min_date = df_raw["tanggal_saja"].min()
        max_date = df_raw["tanggal_saja"].max()
        
        date_range = st.date_input("Rentang Tanggal", value=[min_date, max_date], min_value=min_date, max_value=max_date)
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_date, end_date = date_range

# =========================================================
# 5. PROSES FILTERING DATA
# =========================================================
filtered_df = df_raw.copy()

if selected_keyword:
    filtered_df = filtered_df[filtered_df[col_keyword].isin(selected_keyword)]
if selected_media:
    filtered_df = filtered_df[filtered_df[col_media].isin(selected_media)]
if col_sentiment and selected_sentimen:
    filtered_df = filtered_df[filtered_df[col_sentiment].isin(selected_sentimen)]

if start_date and end_date and date_col:
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date).replace(hour=23, minute=59, second=59)
    mask = (filtered_df[date_col] >= start_dt) & (filtered_df[date_col] <= end_dt)
    filtered_df = filtered_df[mask]

# =========================================================
# 6. RENDER UTAMA DASHBOARD
# =========================================================
st.markdown("## Insights Utama")
if filtered_df.empty:
    st.info("💡 Tidak ada data yang sesuai dengan kriteria filter Anda.")
else:
    # --- METRIK UTAMA ---
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("Total Berita Terfilter", len(filtered_df))
    kpi2.metric("Portal Media Unik", filtered_df[col_media].nunique() if col_media in filtered_df.columns else 0)
    kpi3.metric("Keyword Aktif", filtered_df[col_keyword].nunique() if col_keyword in filtered_df.columns else 0)

    # =========================================================
    # 🟢 IMPLEMENTASI INSIGHT & RINGKASAN EKSEKUTIF (GEMINI CLIENT)
    # =========================================================
    
    insights = []
    top_media = filtered_df[col_media].value_counts() if col_media in filtered_df.columns else []
    
    # Perhitungan Persentase Sentimen
    if col_sentiment and not filtered_df[col_sentiment].empty:
        total_sentimen = len(filtered_df[col_sentiment].dropna())
        if total_sentimen > 0:
            sentimen_counts = filtered_df[col_sentiment].value_counts()
            jml_positif = sentimen_counts.get('POSITIVE', 0) + sentimen_counts.get('Positive', 0)
            jml_negatif = sentimen_counts.get('NEGATIVE', 0) + sentimen_counts.get('Negative', 0)
            persen_positif = (jml_positif / total_sentimen) * 100
            persen_negatif = (jml_negatif / total_sentimen) * 100
        else:
            persen_positif = 0; persen_negatif = 0
            
        if persen_positif > persen_negatif:
            insights.append(f"📈 Sentimen cenderung positif dengan {persen_positif:.1f}% berita positif")
        elif persen_negatif > persen_positif:
            insights.append(f"📉 Sentimen cenderung negatif dengan {persen_negatif:.1f}% berita negatif")
        else:
            insights.append("⚖️ Sentimen seimbang antara positif and negatif")
            
    if len(top_media) > 0:
        insights.append(f"📰 Media dominan: {top_media.index[0]} dengan {top_media.values[0]} artikel")
        
    total_isi = filtered_df[col_content].notna().sum() if col_content in filtered_df.columns else 0
    insights.append(f"📄 {(total_isi / len(filtered_df) * 100):.1f}% berita memiliki isi lengkap")
    
    for insight in insights:
        st.write(f"- {insight}")
    
    st.divider()

    # --- PENYUSUNAN SISTEM TAB ---
    tab_data, tab_viz = st.tabs(["📂 Tabel Data & AI Analysis", "📈 Visualisasi Grafik"])

    with tab_data:
        with st.expander("📝 Ringkasan Eksekutif Konten (Official Gemini Client)", expanded=True):
            active_keywords = st.session_state.get("active_keyword", [])
            joined_default_keywords = ", ".join(active_keywords) if active_keywords else "Inflasi Papua"
            
            input_keyword = st.text_input(
                "Konfirmasi Kata Kunci Analisis (Pisahkan dengan koma untuk kombinasi gabungan multi-keyword):", 
                value=joined_default_keywords
            )
            
            target_keywords_list = [kw.strip().title() for kw in input_keyword.split(",") if kw.strip()]
            
            if target_keywords_list:
                regex_pattern = "|".join([re.escape(kw) for kw in target_keywords_list])
                filtered_data = filtered_df[filtered_df[col_keyword].astype(str).str.contains(regex_pattern, case=False, na=False)]
            else:
                filtered_data = pd.DataFrame()
            
            target_keyword = "_dan_".join([kw.replace(" ", "_").lower() for kw in target_keywords_list]) if target_keywords_list else "inflasi_papua"
            display_title_keyword = ", ".join(target_keywords_list) if target_keywords_list else "Inflasi Papua"
            
            if filtered_data.empty:
                st.warning(f"Data tidak ditemukan untuk kecocokan kombinasi kata kunci: {target_keywords_list}")
            else:
                date_min = filtered_data[date_col].dropna().min()
                date_max = filtered_data[date_col].dropna().max()
                date_range_str = f"{date_min} sampai {date_max}"
                periode_str = date_range_str
                
                # FUNGSI CACHE DUMMY - Sila ganti dengan service DB asli jika diperlukan
                def cek_cache_summary_hanya_keyword(kata_kunci):
                    return None
                    
                def simpan_summary_ke_db(kunci, periode, teks):
                    pass # Tambahkan fungsi DB Anda di sini

                state_key = f"summary_{target_keyword}"
                state_status_key = f"status_{state_key}"
                
                if state_key not in st.session_state:
                    cache_db = cek_cache_summary_hanya_keyword(target_keyword)
                    st.session_state[state_key] = cache_db
                    st.session_state[state_status_key] = "Versi Cache" if cache_db else "Baru"

                area_judul = st.empty()
                area_konten = st.empty()

                if st.session_state.get(state_key):
                    raw_text = st.session_state[state_key]
                    parsed_title = display_title_keyword
                    parsed_body = raw_text
                    parsed_references = ""
                    
                    if "Isi Analisis" in raw_text:
                        parts = raw_text.split("Isi Analisis")
                        title_part = parts[0].replace("Judul Analisis", "").replace("**", "").strip()
                        if title_part:
                            parsed_title = title_part
                        
                        rest = parts[1]
                        if "Daftar Pustaka" in rest:
                            rest_parts = rest.split("Daftar Pustaka")
                            parsed_body = rest_parts[0].strip()
                            parsed_references = rest_parts[1].strip()
                        else:
                            parsed_body = rest.strip()
                    elif "Daftar Pustaka" in raw_text:
                        rest_parts = raw_text.split("Daftar Pustaka")
                        parsed_body = rest_parts[0].strip()
                        parsed_references = rest_parts[1].strip()

                    area_judul.success(f"### 📊 {parsed_title} ({st.session_state[state_status_key]})")
                    area_konten.markdown(parsed_body)
                    if parsed_references:
                        st.markdown("### 📚 Daftar Pustaka")
                        st.markdown(parsed_references)
                    
                    st.write("---")
                    st.markdown("#### 📥 Cetak Laporan Analisis Resmi")
                    t_media = filtered_data[col_media].value_counts().head(3)
                    t_media_str = ", ".join([f"{m} ({c} artikel)" for m, c in t_media.items()])

                    try:
                        if generate_pdf_report:
                            pdf_bytes = generate_pdf_report(
                                filtered_df=filtered_df,
                                insights=insights,
                                target_keyword=parsed_title, 
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
                                    use_container_width=True
                                )
                    except Exception as pdf_err:
                        st.error(f"Sistem gagal menyiapkan cetakan PDF: {pdf_err}")
                else:
                    area_judul.info("💡 Belum ada narasi ringkasan otomatis untuk filter ini di database.")

                trigger_generate = False
                if st.session_state.get(state_key) and st.session_state.get(state_status_key) == "Versi Cache":
                    if st.button("🔄 Generate Ulang ", key="regenerate_gemini_summary"):
                        trigger_generate = True
                        st.session_state[state_status_key] = "Versi Cache"
                elif not st.session_state.get(state_key):
                    if st.button("✨ Hasilkan Narasi Ringkasan Otomatis", key="generate_gemini_summary"):
                        trigger_generate = True

                if trigger_generate:
                    area_judul.info("⏳ Sedang menulis dan memperbarui ringkasan eksekutif baru...")
                    try:
                        list_keys = st.secrets.get("GEMINI_API_KEYS", [])
                        if not list_keys:
                            list_keys = [None]
                        
                        t_media = filtered_data[col_media].value_counts().head(3)
                        t_media_str = ", ".join([f"{m} ({c} artikel)" for m, c in t_media.items()])
                        clean_df = filtered_data.dropna(subset=[col_content, col_title, col_media])
                        
                        if len(clean_df) > 10 and col_sentiment in clean_df.columns:
                            clean_df = clean_df.groupby(col_sentiment, group_keys=False).apply(
                                lambda x: x.sample(frac=0.75, random_state=42) if len(x) > 0 else x
                            )
                        
                        catatan_regenerate = "\n- CATATAN TAMBAHAN: Data ini merupakan gabungan komprehensif dari data historis dan hasil scraping terbaru. Soroti tren pergerakan atau perubahan situasi terbaru jika terdeteksi." if st.session_state.get(state_status_key) == "Versi Cache" else ""
                        
                        formatted_articles = [
                            f"--- ARTIKEL REFERENSI ---\nMedia: {row[col_media]}\nTanggal: {row[date_col]}\nJudul: {row[col_title]}\nIsi:\n{row[col_content]}" 
                            for _, row in clean_df.iterrows()
                        ]
                        concatenated_content = "\n\n".join(formatted_articles)
                        if len(concatenated_content) > 120000:
                            concatenated_content = concatenated_content[:120000] + "\n\n... [Sisa konten dipotong demi efisiensi konteks] ..."

                        prompt_instruksi = f"""
                        Judul Tugas: Analisis Berita Eksekutif Komprehensif (Metode Terintegrasi 5W+1H dengan Sitasi Numerik)

                        ## Instruksi Utama
                        Berdasarkan KORPUS BERITA yang diberikan, buatlah sebuah laporan analisis berita eksekutif yang mendalam, komprehensif, objektif, dan berbasis fakta dalam bentuk esai naratif (narrative essay) yang mengalir. Jangan menggunakan subjudul yang memisahkan unsur 5W+1H (What, Who, When, Where, Why, How), melainkan integrasikan seluruh unsur tersebut secara alami ke dalam paragraf-paragraf analisis.

                        Sebelum menulis isi esai, buatlah satu judul utama yang paling sesuai dengan keseluruhan isi korpus berita.

                        ---

                        ## I. Ketentuan Judul (WAJIB)
                        - Buat satu judul utama sebelum isi analisis.
                        - Judul harus mencerminkan tema, isu strategis, dan fokus utama yang muncul dari keseluruhan korpus berita, bukan hanya dari artikel pertama.
                        - Gunakan bahasa Indonesia yang formal, profesional, informatif, dan analitis.
                        - Panjang judul sekitar 10–20 kata.
                        - Hindari judul yang terlalu umum, sensasional (clickbait), berupa pertanyaan, maupun hanya mengulang kata kunci pencarian.
                        - Jangan mencantumkan sitasi pada judul.

                        ---

                        ## II. Pedoman Metadata & Konteks
                        Pada paragraf pembuka, jelaskan secara natural informasi berikut:
                        - Profil Kata Kunci yang Dianalisis: {display_title_keyword}
                        - Rentang Waktu Analisis: {date_range_str}
                        - Tiga Kontributor Media Teratas: {t_media_str}
                        Informasi tersebut harus menyatu secara alami dalam paragraf pembuka, bukan ditampilkan sebagai daftar kaku.

                        ---

                        ## III. Kerangka Analisis
                        Berdasarkan seluruh artikel pada KORPUS BERITA, lakukan analisis yang mengintegrasikan seluruh unsur 5W+1H ke dalam narasi esai, meliputi peristiwa, institusi yang terlibat (BI, Pemda, BPS, Bulog), linimasa kronologis, cakupan geografis Papua (Jayapura, Nabire, Keerom, dll), akar penyebab masalah, respons operasi pasar taktis, serta implikasi sosial-ekonomi jangka panjangnya.

                        ---

                        ## IV. Ketentuan Sitasi (WAJIB)
                        Setiap informasi faktual, data, angka, kebijakan, pernyataan, maupun kesimpulan yang berasal dari artikel berita harus disertai sitasi numerik berbentuk [1], [2], [3], dan seterusnya.
                        - Nomor referensi diberikan berdasarkan kemunculan pertama sumber dalam esai.
                        - Jika sumber yang sama digunakan kembali, gunakan nomor yang sama.
                        - Satu kalimat dapat memiliki lebih dari satu sitasi, misalnya [2][5] atau [1][3][4].
                        - Sitasi ditempatkan pada akhir kalimat atau akhir paragraf.

                        ---

                        ## V. Daftar Pustaka (WAJIB)
                        Setelah esai selesai, buat bagian berjudul Daftar Pustaka.
                        - Daftar pustaka disusun berdasarkan nomor referensi, bukan berdasarkan alfabet.
                        - Nomor pada daftar pustaka harus sama dengan nomor yang digunakan pada sitasi dalam esai.
                        - Gunakan format penulisan: [1] Nama Media. Tanggal Publikasi. *Judul Artikel*.

                        ---

                        ## VI. Ketentuan Format Penulisan
                        - Gunakan bahasa Indonesia yang formal, objektif, analitis, dan profesional.
                        - Tulis dalam bentuk esai murni tanpa bullet point pada bagian analisis.
                        - Gunakan bold pada informasi strategis seperti angka penting, persentase, nama kebijakan/program, institusi penting, atau daerah fokus utama.

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
                        
                        daftar_model_fallback = [
                            "gemini-2.5-flash", 
                            "gemini-3.1-flash-lite",
                            "gemini-3-flash-preview",
                            "gemini-2.5-flash-lite"
                        ]
                        
                        response_stream = None
                        model_terpilih = None
                        list_errors = []
                        api_key_terpilih_log = "Default Environment"

                        for idx, api_key in enumerate(list_keys):
                            key_log = f"Key #{idx+1} ({api_key[:6]}...)" if api_key else "Default Env"
                            try:
                                client = genai.Client(api_key=api_key) if api_key else genai.Client()
                                
                                for model_name in daftar_model_fallback:
                                    try:
                                        response_stream = client.models.generate_content_stream(
                                            model=model_name,
                                            contents=prompt_instruksi
                                        )
                                        model_terpilih = model_name
                                        api_key_terpilih_log = key_log
                                        break  
                                    except Exception as model_e:
                                        list_errors.append(f"- **{model_name}** ({key_log}) Error: {str(model_e)}")
                                        continue
                                
                                if response_stream is not None:
                                    break
                                    
                            except Exception as client_err:
                                list_errors.append(f"- Init Client Gagal ({key_log}): {str(client_err)}")
                                st.toast(f"🔄 API Key #{idx+1} bermasalah, mencoba key cadangan...", icon="⚠️")
                                continue

                        if response_stream is None:
                            error_summary = "\n".join(list_errors)
                            st.error(
                                f"🚨 **Semua API Key dan Model Gemini gagal merespons (Mencapai batas limit kuota).** Silakan coba beberapa saat lagi.\n\n"
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
                                st.session_state[state_status_key] = f"Hasil Diperbarui ({model_terpilih} via {api_key_terpilih_log}) ✨"
                                st.rerun()
                                
                    except Exception as main_e:
                        st.error(f"Terjadi kesalahan internal sistem: {main_e}")
            st.divider()

    st.write("Data Hasil Scraping Terfilter")
st.write("Data Hasil Scraping Terfilter")

# 1. Definisikan Dialog Pop-up
@st.dialog("Detail Berita", width="large")
def show_news_detail(row):
    st.subheader(row[col_title])
    st.caption(f"📅 {row[date_col]} | 📰 {row[col_media]} | 🏷️ {row[col_sentiment]}")
    st.markdown("---")
    st.write(row[col_content])
    if st.button("Tutup"):
        st.rerun()

# 2. Gunakan st.dataframe dengan pemilihan baris yang stabil
event = st.dataframe(
    filtered_df,
    use_container_width=True,
    selection_mode="single-row", 
    on_select="rerun",
    key="data_editor"
)

# 3. PERBAIKAN: Bungkus logika pemilihan dengan pengecekan Role Admin
# Pastikan st.session_state.role sudah terinisiasi (defaultnya 'user')
if st.session_state.get("role") == "admin":
    selection = st.session_state.get("data_editor", None)
    
    if selection and "selection" in selection and len(selection["selection"]["rows"]) > 0:
        idx = selection["selection"]["rows"][0]
        selected_row_data = filtered_df.iloc[idx]
        
        # Panggil dialog pop-up
        show_news_detail(selected_row_data)
else:
    # Opsi: Berikan pesan jika user mencoba klik tapi tidak punya akses
    if st.session_state.get("data_editor", {}).get("selection", {}).get("rows"):
        st.info("Fitur detail berita hanya tersedia untuk akun Admin.")
     

    


st.divider()

        # --- TAB VISUALISASI ---
with tab_viz:
    st.write("### Grafik Analitik")
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        if col_sentiment and col_sentiment in filtered_df.columns:
            fig_pie = px.pie(filtered_df, names=col_sentiment, title="Distribusi Sentimen Berita", hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Data sentimen belum tersedia.")
            
    with col_chart2:
        if col_media in filtered_df.columns:
            top_media_chart = filtered_df[col_media].value_counts().reset_index()
            top_media_chart.columns = ['Media', 'Jumlah']
            fig_bar = px.bar(top_media_chart.head(10), x='Media', y='Jumlah', title="Top 10 Portal Media", color='Jumlah', color_continuous_scale="Blues")
            st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# =========================================================
# 7. AREA DESTRUKTIF: KHUSUS OTORITAS ADMINISTRATOR (ADMIN)
# =========================================================
if st.session_state["authenticated"] and st.session_state["role"] == "admin":
    st.error("⚠️ PANEL ADMINISTRATOR: Manajemen Destruksi Basis Data")
    
    col_adm1, col_adm2 = st.columns(2)
    
    with col_adm1:
        st.markdown("**Penghapusan Artikel Tunggal (Per ID)**")
        target_delete_id = st.text_input("Masukkan ID Artikel", key="id_hapus")
        admin_key_2 = st.text_input("Masukkan Service Role Key Supabase", type="password", key="pass_db_2")
        
        if st.button("⚠️ Eksekusi Hapus Artikel", use_container_width=True):
            if target_delete_id and admin_key_2:
                success = db_service.delete_article(target_delete_id, admin_api_key=admin_key_2)
                if success:
                    st.success("Artikel berhasil dihapus dari database.")
                    st.cache_data.clear()
                    st.rerun()
            else:
                st.error("Spesifikasi ID dan Service Key wajib diisi lengkap!")

    with col_adm2:
        st.markdown("**Penghapusan Massal (Berdasarkan Tanggal Publikasi)**")
        target_date_del = st.date_input("Pilih Tanggal Target", key="date_hapus_massal")
        admin_key_3 = st.text_input("Masukkan Service Role Key Supabase (Massal)", type="password", key="pass_db_3")
        
        if st.button("🚨 EKSEKUSI HAPUS MASAL TANGGAL INI", type="primary", use_container_width=True):
            if admin_key_3:
                date_str = target_date_del.strftime("%Y-%m-%d")
                success = db_service.delete_articles_by_date(date_str, admin_api_key=admin_key_3)
                if success:
                    st.warning(f"Seluruh records data pada tanggal {date_str} telah dibersihkan.")
                    st.cache_data.clear()
                    st.rerun()
            else:
                st.error("Otorisasi Service Key tidak boleh kosong!")