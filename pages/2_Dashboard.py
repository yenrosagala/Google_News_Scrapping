import streamlit as st
import pandas as pd
from app.services.database_service import db_service
from app.services.report_service import report_service  # Service PDF WeasyPrint
from app.core.auth import init_auth_session, render_login_form, render_logout

# 1. Inisialisasi Session untuk Login Admin di Sidebar
init_auth_session()

st.set_page_config(page_title="Dashboard Analitik Berita", layout="wide")
st.title("📊 Dashboard Hasil Scraping & Monitoring Berita")

# =========================================================
# BAGIAN 1: FORM LOGIN/LOGOUT (HANYA DI SIDEBAR)
# =========================================================
# Memasang form login di sidebar agar tidak menutupi konten utama Dashboard
if not st.session_state.get("authenticated", False):
    render_login_form()
else:
    st.sidebar.success(f"Masuk sebagai: {st.session_state.username.upper()}")
    render_logout()

# =========================================================
# BAGIAN 2: KONTEN UTAMA (TERBUKA UNTUK UMUM)
# =========================================================
# Mengambil data dari database menggunakan service mandiri kita
df = db_service.get_latest_scraped_data(limit=50)

if df.empty:
    st.info("💡 Belum ada data hasil scraping terakhir di dalam database.")
else:
    # A. Row Ringkasan Metrik Utama (Umum)
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Berita Ditarik", len(df))
    col2.metric("Kata Kunci Utama", df["kata_kunci"].iloc[0] if "kata_kunci" in df.columns else "-")
    col3.metric("Portal Media Unik", df["media"].nunique() if "media" in df.columns else df["source"].nunique())
    
    # B. Tabel Utama Hasil Scraping (Umum)
    st.subheader("📰 Tabel Artikel Berita Terbaru")
    st.dataframe(df, use_container_width=True)

    # C. Fitur Ekspor ke PDF & Rangkuman AI (Umum)
    st.write("---")
    st.subheader("🖨️ Cetak Laporan Eksekutif")
    if st.button("📥 Ekspor Hasil Rangkuman AI ke Berkas PDF"):
        with st.spinner("Sedang merangkum konten berita dan menyusun file PDF..."):
            # Mengonversi DataFrame ke bentuk List Dictionary untuk engine PDF
            data_list = df.to_dict(orient="records")
            
            # Panggil engine PDF WeasyPrint
            file_report = report_service.export_articles_to_pdf(data_list, "Laporan_Monitoring_Berita.pdf")
            
            with open(file_report, "rb") as pdf_file:
                st.download_button(
                    label="Klik di Sini untuk Mengunduh PDF",
                    data=pdf_file,
                    file_name="Laporan_Monitoring_Berita.pdf",
                    mime="application/pdf"
                )

# =========================================================
# BAGIAN 3: OTORITAS MANIPULASI DATABASE (KHUSUS ADMIN)
# =========================================================
# Logika kondisional: Bagian ini hanya muncul jika Admin sudah login di sidebar
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