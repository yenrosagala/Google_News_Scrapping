import io
from datetime import datetime
from fpdf import FPDF
import matplotlib.pyplot as plt
import seaborn as sns

def generate_pdf_report(filtered_df, insights, target_keyword, date_range_str, t_media_str, summary_text):
    """
    Fungsi utilitas murni untuk membuat file PDF berdasarkan data yang dikirim dari UI.
    Grafik dibuat menggunakan Matplotlib/Seaborn agar tidak ketergantungan pada Chrome/Kaleido.
    """
    # Set style global untuk grafik biar rapi
    plt.style.use('ggplot')
    
    # 1. BIKIN GRAFIK SENTIMEN (Pie Chart)
    img_sentimen_bytes = io.BytesIO()
    if not filtered_df.empty and "Sentimen" in filtered_df.columns:
        sentimen_counts = filtered_df["Sentimen"].value_counts()
        
        fig, ax = plt.subplots(figsize=(5, 4))
        colors = {"Positif": "#4CAF50", "Negatif": "#F44336", "Netral": "#9E9E9E"}
        current_colors = [colors.get(x, "#9E9E9E") for x in sentimen_counts.index]
        
        ax.pie(
            sentimen_counts.values, 
            labels=sentimen_counts.index, 
            autopct='%1.1f%%', 
            startangle=90, 
            colors=current_colors,
            wedgeprops=dict(width=0.4, edgecolor='w') # Membuat efek Donut chart seperti Plotly
        )
        ax.set_title("Distribusi Sentimen", fontsize=12, fontweight='bold', pad=10)
        plt.tight_layout()
        plt.savefig(img_sentimen_bytes, format='png', dpi=200)
        plt.close()
        img_sentimen_bytes.seek(0)

    # 2. BIKIN GRAFIK TOP 10 MEDIA (Horizontal Bar Chart)
    img_media_bytes = io.BytesIO()
    if not filtered_df.empty and "media" in filtered_df.columns:
        top_10_m = filtered_df["media"].value_counts().head(10)
        
        fig, ax = plt.subplots(figsize=(6, 4))
        sns.barplot(x=top_10_m.values, y=top_10_m.index, ax=ax, palette="Blues_r")
        ax.set_title("Top 10 Media Kontributor", fontsize=12, fontweight='bold', pad=10)
        ax.set_xlabel("Jumlah Berita")
        plt.tight_layout()
        plt.savefig(img_media_bytes, format='png', dpi=200)
        plt.close()
        img_media_bytes.seek(0)

    # 3. INISIALISASI DOKUMEN FPDF
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(left=15, top=15, right=15)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # --- HEADER LAPORAN ---
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(0, 120, 212)  # Warna biru tema #0078D4
    # Memberikan lebar pasti 180mm (A4 = 210mm - margin kiri 15mm - margin kanan 15mm)
    pdf.cell(180, 10, "LAPORAN NEWS INTELLIGENCE", align="C", new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(180, 6, f"Dibuat pada: {datetime.now().strftime('%d %B %Y, %H:%M')}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    
    # Garis Pembatas Biru
    pdf.set_draw_color(0, 120, 212)
    pdf.set_line_width(0.8)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(8)
    
    # --- METADATA ANALISIS ---
   # Mengubah target_keyword menjadi format Proper Case (Kapital di awal kata)
    proper_keyword = str(target_keyword).title()

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(50, 50, 50)
    pdf.cell(45, 6, "Kata Kunci Analisis", border=0)
    pdf.set_font("Helvetica", "", 11)
    # Gunakan proper_keyword yang sudah dikonversi
    pdf.cell(135, 6, f": {proper_keyword}", border=0, new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(45, 6, "Rentang Waktu", border=0)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(135, 6, f": {date_range_str}", border=0, new_x="LMARGIN", new_y="NEXT")
    
    # --- BAGIAN TOP MEDIA (MENGGUNAKAN MULTI_CELL) ---
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(45, 6, "Top Media", border=0)
    pdf.set_font("Helvetica", "", 11)
    # Gunakan multi_cell dengan lebar 135 agar teks membungkus (wrap) ke bawah jika melebihi batas margin
    pdf.multi_cell(135, 6, f": {t_media_str}", border=0, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

     # Garis Pembatas Biru
    pdf.set_draw_color(0, 120, 212)
    pdf.set_line_width(0.8)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(10)
    
    # --- SEKSI 1: VISUALISASI GRAFIK ---
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 100, 180)
    pdf.cell(180, 8, "1. Grafik & Visualisasi Analisis", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    
    # Tempel gambar chart dari memory bytes buffer
    y_pos = pdf.get_y()
    if img_sentimen_bytes.getvalue():
        pdf.image(img_sentimen_bytes, x=15, y=y_pos, w=85)
    if img_media_bytes.getvalue():
        pdf.image(img_media_bytes, x=105, y=y_pos, w=90)
    pdf.set_y(y_pos + 65) # Atur ulang posisi Y setelah penempelan gambar agar tidak menumpuk teks berikutnya
    pdf.ln(5)
    
    # --- SEKSI 2: INSIGHTS UTAMA ---
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 100, 180)
    pdf.cell(180, 8, "2. Insights Utama", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(50, 50, 50)
    pdf.ln(2)
    for insight in insights:
        clean_insight = insight.encode('ascii', 'ignore').decode('ascii').strip()
        pdf.multi_cell(180, 6, f"- {clean_insight}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)
    
    # --- SEKSI 3: EXECUTIVE SUMMARY BY AI ---
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 100, 180)
    pdf.cell(180, 8, "3. Executive Summary (AI Generated)", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10.5)
    pdf.set_text_color(30, 30, 30)
    pdf.ln(2)
    
   
    clean_summary = summary_text.replace("**", "").encode('ascii', 'ignore').decode('ascii')
    pdf.multi_cell(180, 5.5, clean_summary, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10) # Beri jarak yang cukup setelah teks selesai

    # --- PENUTUP & GARIS PEMBATAS ---
    # Mengamankan posisi Y agar garis pembatas dan footer tidak menggantung sendirian jika halaman habis
    if pdf.get_y() > 250:
        pdf.add_page()
        
    # Garis Pembatas Biru Halus
    pdf.set_draw_color(0, 120, 212)
    pdf.set_line_width(0.4) # Diperhalus dari 0.8 menjadi 0.4 agar lebih elegan
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(6)
    
    # --- FOOTER LAPORAN ---
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(140, 140, 140) # Warna abu-abu yang sedikit lebih lembut
    
    # Teks informasi sistem dan pembuat disatukan agar mengalir secara formal
    teks_footer_1 = "Laporan resmi ini dihasilkan secara otomatis oleh sistem News Intelligence Dashboard."
    teks_footer_2 = "Aplikasi: newscrapper.streamlit.app | Pengembang: Yenro P. Sagala - BPS Provinsi Papua"
    
    pdf.cell(180, 4, teks_footer_1, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(180, 4, teks_footer_2, align="C", new_x="LMARGIN", new_y="NEXT")
    
    return pdf.output()