import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px
from google import genai
import psycopg2
from app.services.database_service import db_service

# 1. Setup Page Config & Session State (Bypass login admin)
st.set_page_config(page_title="Dashboard Monitoring Berita", layout="wide")

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = True
if "role" not in st.session_state:
    st.session_state["role"] = "admin"
if "gemini_dashboard_summary" not in st.session_state:
    st.session_state["gemini_dashboard_summary"] = ""
if "gemini_summary_status" not in st.session_state:
    st.session_state["gemini_summary_status"] = ""

st.title("📊 Dashboard Monitoring Berita")

# --- CUSTOM CSS ---
try:
    with open("app/assets/style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass

# =========================================================
# DATABASE CORE CONNECTION (PostgreSQL Direct via Psycopg2)
# =========================================================
# URL Host tetap menggunakan alamat yang Anda berikan
DB_HOST = "db.qbqvtdhaktjbohyfwkvi.supabase.co"

def get_db_connection(password):
    try:
        conn = psycopg2.connect(
            dsn=f"postgresql://postgres:{password}@{DB_HOST}:5432/postgres",
            connect_timeout=5
        )
        return conn
    except Exception as e:
        st.error(f"❌ Gagal Terhubung ke Database (Password salah atau network error): {str(e)}")
        return None

# Fungsi khusus untuk membaca data tanpa password (menggunakan read-only user / token jembatan jika ada)
# Mengingat Anda meminta string postgresql://postgres, kita asumsikan untuk read data menggunakan password kosong atau minimal.
# JIKA database membutuhkan password bahkan untuk READ, Anda harus memasukkan password default read-only di sini.
def fetch_data_from_db(password=""):
    try:
        conn = psycopg2.connect(
            dsn=f"postgresql://postgres:{password}@{DB_HOST}:5432/postgres",
            connect_timeout=5
        )
        # Menggunakan format query aman untuk mengambil data berita terbaru
        query = "SELECT * FROM articles ORDER BY created_at DESC LIMIT 100;" 
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        # Jika gagal karena butuh password, tampilkan info di dashboard
        st.warning(f"⚠️ Mode Terbatas: Gagal memuat data otomatis secara anonim. Jika DB Anda diproteksi penuh untuk read, silakan isi password di menu bawah.")
        return pd.DataFrame()

# =========================================================
# OTOMATIS AMBIL DATA SAAT HALAMAN DIBUKA (Tanpa Password di Awal)
# =========================================================
df_raw = fetch_data_from_db()

# =========================================================
# SIDEBAR CONTROL PANEL (Hanya Filter Data)
# =========================================================
with st.sidebar:
    st.title("🎛️ Control Panel")
    
    filtered_df = pd.DataFrame()
    
    # Filter Data UI (Hanya muncul jika data berhasil ditarik)
    if not df_raw.empty:
        st.markdown("### Filter Data Dashboard")
        
        options_kw = list(df_raw["kata_kunci"].unique()) if "kata_kunci" in df_raw.columns else []
        selected_keywords = st.multiselect("Filter Keyword", options=options_kw, default=options_kw[:1] if options_kw else None)
        
        options_sent = list(df_raw["Sentimen"].unique()) if "Sentimen" in df_raw.columns else ["POSITIVE", "NEUTRAL", "NEGATIVE"]
        selected_sentiments = st.multiselect("Filter Sentimen", options=options_sent, default=options_sent)
        
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
            
    st.markdown("---")
    st.write("🔧 **Debug Session State:**")
    st.json(st.session_state)

# =========================================================
# RENDER UTAMA DASHBOARD
# =========================================================
if filtered_df.empty:
    st.info("💡 Tidak ada data yang ditampilkan. Pastikan database Anda bisa diakses atau periksa kriteria filter Anda.")

else:
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
        
        clean_df = filtered_df.dropna(subset=['isi_konten', 'judul'])
        formatted_articles = [
            f"Media: {row.get(col_media, '-')}\nJudul: {row['judul']}\nIsi: {row['isi_konten']}" 
            for _, row in clean_df.head(15).iterrows()
        ]
        concatenated_content = "\n\n".join(formatted_articles)
        
        display_title_keyword = ", ".join(selected_keywords) if selected_keywords else "Umum"
        date_range_str = datetime.now().strftime("%d %B %Y")
        t_media = filtered_df[col_media].value_counts().head(3) if col_media else pd.Series()
        t_media_str = ", ".join([f"{m} ({c} artikel)" for m, c in t_media.items()]) if not t_media.empty else "Tidak Terdeteksi"

        raw_keys = st.secrets.get("GEMINI_API_KEYS")
        list_keys = [k.strip() for k in raw_keys if k and str(k).strip()] if isinstance(raw_keys, list) else ([raw_keys.strip()] if isinstance(raw_keys, str) and raw_keys.strip() else [None])

        if st.button("✨ Hasilkan Narasi Ringkasan Otomatis Berbasis Fakta"):
            if not concatenated_content.strip():
                st.warning("Tidak ada konten artikel yang layak untuk dianalisis oleh AI.")
            else:
                area_konten = st.empty()
                area_konten.info("⏳ Gemini AI sedang menyusun analisis, mohon tunggu...")
                
                daftar_model_fallback = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
                response_text = None
                model_terpilih = None
                list_errors = []

                for idx, api_key in enumerate(list_keys):
                    key_log = f"Key #{idx+1}" if api_key else "Default Env"
                    try:
                        client = genai.Client(api_key=api_key) if api_key else genai.Client()
                        for model_name in daftar_model_fallback:
                            try:
                                prompt_instruksi = f"Buat ringkasan berdasarkan topik {display_title_keyword} per tanggal {date_range_str} dari data berikut:\n{concatenated_content}"
                                response = client.models.generate_content(model=model_name, contents=prompt_instruksi)
                                if response.text:
                                    response_text = response.text
                                    model_terpilih = model_name
                                    break
                            except Exception as model_e:
                                list_errors.append(f"- **{model_name}** ({key_log}) Error: {str(model_e)}")
                        if response_text: break
                    except Exception as client_err:
                        list_errors.append(f"- Init Client Gagal ({key_log}): {str(client_err)}")

                if response_text:
                    st.session_state["gemini_dashboard_summary"] = response_text
                    st.session_state["gemini_summary_status"] = f"Hasil Diperbarui ({model_terpilih}) ✨"
                    st.rerun()
                else:
                    st.error(f"🚨 Semua API Key gagal merespons.\n\n**Log:**\n" + "\n".join(list_errors))

        if st.session_state["gemini_dashboard_summary"]:
            st.markdown(f"### Hasil Analisis Eksekutif ({st.session_state['gemini_summary_status']})")
            st.info(st.session_state["gemini_dashboard_summary"])

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
                    color="Sentimen", color_discrete_map={"POSITIVE": "#4CAF50", "NEGATIVE": "#F44336", "NEUTRAL": "#9E9E9E"},
                    template="plotly_dark"
                )
                fig_pie.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_pie, use_container_width=True)
                            
        with g_col2:
            if col_media:
                media_df = filtered_df[col_media].value_counts().head(10).reset_index()
                media_df.columns = ["Media", "Jumlah"]
                fig_bar = px.bar(media_df, x="Jumlah", y="Media", orientation="h", title="Top 10 Media Teraktif", template="plotly_dark")
                fig_bar.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_bar, use_container_width=True)

    # -----------------------------------------------------
    # TAB 3: TABEL DATA
    # -----------------------------------------------------
    with tab3:
        st.subheader("📰 Tabel Artikel Berita Hasil Filter")
        display_cols = ["kata_kunci", "judul", col_media, "waktu_tampilan", "Sentimen"]
        display_cols = [c for c in display_cols if c in filtered_df.columns]
        st.dataframe(filtered_df[display_cols], use_container_width=True, hide_index=True)

# =========================================================
# MANAGEMENT PANEL (PASSWORD DIBUTUHKAN DI SINI UNTUK MODIFIKASI/HAPUS)
# =========================================================
if st.session_state.get("authenticated") and st.session_state.get("role") == "admin":
    st.write("---")
    st.subheader("🛠️ Panel Manajemen Data (Wewenang Admin Only)")
    st.info("🔑 Anda wajib memasukkan **Supabase Service Role Key** sebagai password untuk melakukan tindakan di bawah ini.")
    
    col_adm1, col_adm2, col_adm3 = st.columns(3)
    
    with col_adm1:
        st.markdown("**Koreksi Sentimen Manual**")
        target_id = st.text_input("Masukkan ID Artikel Berita", key="id_sentimen")
        new_sentiment = st.selectbox("Ubah Sentimen Ke", ["POSITIVE", "NEUTRAL", "NEGATIVE"])
        
        # Kolom input "password" (Padahal aslinya diisi Service Role Key)
        admin_key_1 = st.text_input("Masukkan Service Key (Password)", type="password", key="pass_db_1")
        
        if st.button("Perbarui Sentimen"):
            if target_id and admin_key_1:
                success = db_service.update_sentiment(target_id, new_sentiment, admin_api_key=admin_key_1)
                if success:
                    st.success("Sentimen berhasil diperbarui!")
                    st.rerun()
            else: st.error("ID dan Service Key tidak boleh kosong!")
                
    with col_adm2:
        st.markdown("**Penghapusan Artikel (Per ID)**")
        target_delete_id = st.text_input("Masukkan ID Artikel", key="id_hapus")
        
        # Kolom input "password"
        admin_key_2 = st.text_input("Masukkan Service Key (Password)", type="password", key="pass_db_2")
        
        if st.button("⚠️ Hapus Artikel"):
            if target_delete_id and admin_key_2:
                success = db_service.delete_article(target_delete_id, admin_api_key=admin_key_2)
                if success:
                    st.warning("Artikel berhasil dihapus!")
                    st.rerun()
            else: st.error("ID dan Service Key tidak boleh kosong!")

    with col_adm3:
        st.markdown("**Penghapusan Massal (Per Tanggal)**")
        target_date = st.date_input("Pilih Tanggal Data", key="date_hapus_massal")
        
        # Kolom input "password"
        admin_key_3 = st.text_input("Masukkan Service Key (Password)", type="password", key="pass_db_3")
        
        if st.button("🚨 HAPUS DATA TANGGAL INI", type="primary"):
            if admin_key_3:
                date_str = target_date.strftime("%Y-%m-%d")
                success = db_service.delete_articles_by_date(date_str, admin_api_key=admin_key_3)
                if success:
                    st.success(f"Artikel pada tanggal {date_str} dibersihkan!")
                    st.rerun()
            else:
                st.error("❌ Service Key wajib diisi untuk menghapus data massal!")