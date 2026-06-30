import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from wordcloud import WordCloud

from app.database import ambil_data_dari_db, cek_autentikasi_manual, hapus_semua_data_db, inisialisasi_database
from app.sentiment import hitung_sentimen_leksikon
from app.scraper import run_scraper_pipeline


def render_app():
    st.set_page_config(page_title="News Intelligence Dashboard", page_icon="📰", layout="wide")

    st.markdown(
        """
        <div style="padding: 1.2rem 0 0.6rem 0;">
            <h1 style="margin-bottom: 0.2rem;">Dasbor Analisis Media Terpusat & Google News Scraper</h1>
            <p style="margin-top: 0; color: #5b6472;">Pantau berita, analisis sentimen, dan ektrak konten secara terpusat.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cek_autentikasi_manual()
    inisialisasi_database()

    df_master = ambil_data_dari_db()

    with st.sidebar:
        st.header("⚙️ Kontrol Panel Scraper")
        st.caption("Kelola pengumpulan data dan filter tampilan dari sini.")
        kata_kunci_input = st.text_input("Topik Baru untuk di-Scrap:", placeholder="Contoh: Sensus Ekonomi")
        tombol_tanam = st.button("Jalankan Sinkronisasi", type="primary", use_container_width=True)

        st.markdown("---")
        st.header("🎯 Filter Visualisasi Dasbor")
        if not df_master.empty:
            opsi_keyword = ["Semua Kata Kunci"] + list(df_master["kata_kunci"].unique())
            keyword_terpilih = st.selectbox("Pilih Data Kata Kunci:", opsi_keyword)
        else:
            keyword_terpilih = "Semua Kata Kunci"

        st.markdown("---")
        st.header("🗑️ Hapus Data")
        st.caption("Tindakan ini akan menghapus semua record berita dari database.")
        with st.form("clear_db_form", clear_on_submit=True):
            password_hapus = st.text_input(
                "Konfirmasi password untuk menghapus data:",
                type="password",
                key="clear_db_password_input",
                placeholder="Masukkan password",
            )
            tombol_hapus = st.form_submit_button("Hapus Semua Data", type="secondary", use_container_width=True)

            if tombol_hapus:
                if not password_hapus.strip():
                    st.error("❌ Password konfirmasi tidak boleh kosong.")
                elif password_hapus != st.session_state.get("saved_db_password", ""):
                    st.error("❌ Password salah. Data tidak terhapus.")
                else:
                    jumlah_hapus = hapus_semua_data_db()
                    st.success(f"✅ Semua data berhasil dihapus ({jumlah_hapus} baris).")
                    st.rerun()

        st.markdown("---")
        if st.button("🚪 Putuskan Sesi / Log Out", use_container_width=True):
            st.session_state["db_authenticated"] = False
            st.session_state["saved_db_password"] = ""
            st.rerun()

    if tombol_tanam and kata_kunci_input.strip():
        progress_bar = st.progress(0.0)
        status_text = st.empty()
        data_baru = run_scraper_pipeline(kata_kunci_input, progress_bar, status_text)

        progress_bar.empty()
        status_text.empty()
        st.success(f"✨ Sinkronisasi selesai! Berhasil menambahkan {data_baru} berita baru.")
        st.rerun()

    if keyword_terpilih == "Semua Kata Kunci":
        df_aktual = df_master.copy()
    else:
        df_aktual = df_master[df_master["kata_kunci"] == keyword_terpilih].copy()

    df_aktual = df_aktual.copy()
    df_aktual["memiliki_konten"] = (
        df_aktual["isi_konten"].notna()
        & df_aktual["isi_konten"].astype(str).str.strip().ne("")
        & ~df_aktual["isi_konten"].astype(str).str.contains(r"\[Gagal Ekstrak\]", case=False, na=False)
    )

    st.markdown("---")
    st.subheader("📊 Ringkasan News Count")
    col_count_1, col_count_2, col_count_3 = st.columns(3)
    with col_count_1:
        st.metric("Total berita yang tersimpan", int(len(df_aktual)))
    with col_count_2:
        st.metric("Berita dengan konten berhasil diekstraksi", int(df_aktual["memiliki_konten"].sum()))
    with col_count_3:
        st.metric("Berita tanpa konten", int((~df_aktual["memiliki_konten"]).sum()))

    tab1, tab2, tab3 = st.tabs(["📈 Analisis Grafik & Sentimen", "☁️ Word Cloud Konten", "🗃️ Data Tabel Database"])

    with tab1:
        if not df_aktual.empty:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Top 10 Media Teraktif")
                top_media = df_aktual["media"].value_counts().head(10).reset_index()
                top_media.columns = ["Nama Media", "Jumlah Artikel"]
                st.bar_chart(data=top_media, x="Nama Media", y="Jumlah Artikel", color="#1f77b4")
            with col2:
                st.subheader("Analisis Sentimen Kompleks (Leksikon Indonesia)")
                df_aktual["Sentimen"] = df_aktual["isi_konten"].apply(hitung_sentimen_leksikon)
                sentiment_counts = df_aktual["Sentimen"].value_counts().reset_index()
                sentiment_counts.columns = ["Sentimen", "Total"]
                st.bar_chart(data=sentiment_counts, x="Sentimen", y="Total", color="#ef553b")
        else:
            st.info("Database kosong. Silakan jalankan sinkronisasi data terlebih dahulu.")

    with tab2:
        st.subheader("☁️ Awan Kata Konten Berita")
        if not df_aktual.empty:
            df_valid = df_aktual[df_aktual["isi_konten"].notna() & (~df_aktual["isi_konten"].str.contains(r"\[Gagal Ekstrak\]", case=False, na=False))]
            semua_teks = " ".join(df_valid["isi_konten"].astype(str))
            stopwords_id = {'yang', 'di', 'dan', 'itu', 'dengan', 'untuk', 'dari', 'seperti', 'ini', 'akan', 'dapat', 'oleh', 'ke', 'ada', 'adalah', 'sebuah', 'pada', 'tersebut', 'dalam', 'bisa', 'ia', 'juga', 'atau', 'telah'}
            if len(semua_teks.strip()) > 30:
                wordcloud = WordCloud(width=900, height=450, background_color="white", stopwords=stopwords_id, colormap="plasma").generate(semua_teks)
                fig, ax = plt.subplots(figsize=(12, 6))
                ax.imshow(wordcloud, interpolation="bilinear")
                ax.axis("off")
                st.pyplot(fig)
            else:
                st.warning("Volume teks belum mencukupi.")
        else:
            st.info("Jalankan sinkronisasi berita.")

    with tab3:
        st.subheader("🗃️ Daftar Rekam Data Berita")
        if not df_aktual.empty:
            if "Sentimen" not in df_aktual.columns:
                df_aktual["Sentimen"] = df_aktual["isi_konten"].apply(hitung_sentimen_leksikon)
            df_tampil = df_aktual[["kata_kunci", "judul", "media", "waktu_tampilan", "Sentimen", "link", "isi_konten"]].head(30).copy()
            df_tampil["link"] = df_tampil["link"].apply(lambda value: value if isinstance(value, str) and value else "")

            if "selected_article" not in st.session_state:
                st.session_state["selected_article"] = None

            selection_state = st.dataframe(
                df_tampil,
                use_container_width=True,
                on_select="rerun",
                selection_mode="single-row",
                key="news_table_selection",
                column_config={
                    "link": st.column_config.TextColumn("link"),
                },
            )

            selected_rows = []
            selection_obj = getattr(selection_state, "selection", None)
            if selection_obj is not None:
                selected_rows = list(getattr(selection_obj, "rows", []))

            if selected_rows:
                row_idx = int(selected_rows[0])
                selected_row = df_tampil.iloc[row_idx]
                selected_payload = {
                    "index": row_idx,
                    "judul": selected_row["judul"],
                    "media": selected_row["media"],
                    "waktu_tampilan": selected_row["waktu_tampilan"],
                    "isi_konten": selected_row["isi_konten"],
                }

                if st.session_state["selected_article"] != selected_payload:
                    st.session_state["selected_article"] = selected_payload
                    st.rerun()

            if st.session_state["selected_article"] is not None:
                article = st.session_state["selected_article"]

                @st.dialog(f"Isi Konten - {article['judul']}")
                def show_article_detail(payload):
                    st.markdown(f"**Judul:** {payload['judul']}")
                    st.markdown(f"**Media:** {payload['media'] or '-'}")
                    st.markdown(f"**Waktu:** {payload['waktu_tampilan'] or '-'}")
                    st.markdown("### Isi Konten")
                    st.write(payload["isi_konten"] or "Tidak ada konten yang tersedia.")
                    if st.button("Tutup"):
                        st.session_state["selected_article"] = None
                        st.rerun()

                show_article_detail(article)
        else:
            st.info("Belum ada record data.")
