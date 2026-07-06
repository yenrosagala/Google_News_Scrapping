from fpdf import FPDF
import datetime
import os

class ReportService:
    @staticmethod
    def export_articles_to_pdf(articles: list, output_filename: str = "Laporan_Monitoring_Berita.pdf") -> str:
        """Mengonversi data berita menjadi PDF resmi menggunakan FPDF2 (Murni Python)."""
        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        
        # 1. Header Laporan
        pdf.set_font("Arial", "B", 18)
        pdf.set_text_color(43, 108, 176) # Warna Biru Corporate
        pdf.cell(0, 10, "Laporan Hasil Analisis Media Berita", ln=True, align="L")
        
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(113, 128, 150) # Warna Abu-abu
        waktu_cetak = datetime.datetime.now().strftime('%d-%m-%Y %H:%M')
        pdf.cell(0, 5, f"Dicetak Otomatis Sistem pada: {waktu_cetak}", ln=True, align="L")
        
        # Garis Pembatas Header
        pdf.set_draw_color(49, 130, 206)
        pdf.set_linewidth(0.5)
        pdf.line(15, 27, 195, 27)
        pdf.ln(10)
        
        # 2. Perulangan Data Artikel dari Dataframe Anda
        for item in articles:
            # Judul Artikel
            pdf.set_font("Arial", "B", 11)
            pdf.set_text_color(44, 82, 130)
            judul = item.get('judul', 'Untitled').encode('latin-1', 'ignore').decode('latin-1')
            pdf.multi_cell(0, 6, judul)
            
            # Metadata Artikel
            pdf.set_font("Arial", "I", 8.5)
            pdf.set_text_color(113, 128, 150)
            meta = f"Media: {item.get('media')} | Waktu: {item.get('waktu_tampilan')} | Kata Kunci: {item.get('kata_kunci')}"
            pdf.cell(0, 5, meta, ln=True)
            
            # Kotak Rangkuman AI
            pdf.ln(2)
            pdf.set_font("Arial", "", 9.5)
            pdf.set_text_color(45, 55, 72)
            
            # Isi Rangkuman AI (Ganti kata kunci 'summary' sesuai kolom yang dihasilkan AI Anda)
            summary_text = f"Rangkuman Eksplisit AI:\n{item.get('summary', 'Rangkuman belum dibuat.')}"
            summary_clean = summary_text.encode('latin-1', 'ignore').decode('latin-1')
            
            # Membuat background kotak abu-abu lembut untuk rangkuman
            pdf.set_fill_color(247, 250, 252)
            pdf.multi_cell(0, 5, summary_clean, border="L", fill=True)
            
            # Jarak antar artikel
            pdf.ln(6)
            pdf.set_draw_color(226, 232, 240)
            pdf.set_linewidth(0.2)
            pdf.cell(0, 0, "", border="T", ln=True)
            pdf.ln(4)
            
        # Simpan file ke sistem lokal
        pdf.output(output_filename)
        return output_filename

# Inisialisasi Singleton agar nama panggilannya di pages/2_Dashboard.py tetap sama
report_service = ReportService()