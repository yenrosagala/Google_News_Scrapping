import google.generativeai as genai

class AIService:
    def __init__(self, api_key: str):
        # Konfigurasi token API Gemini Anda
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')

    def generate_summary(self, full_text: str) -> str:
        """Menerima artikel teks utuh, mengembalikan rangkuman 3 poin bahasa Indonesia."""
        if not full_text or len(full_text.strip()) < 150:
            return "Konten berita terlalu pendek untuk dirangkum secara optimal."
            
        prompt = (
            "Bertindaklah sebagai analis media profesional. Ringkaslah isi konten berita di bawah ini "
            "menjadi bentuk ringkasan eksekutif maksimal 3 poin bullet menggunakan Bahasa Indonesia yang "
            f"formal, objektif, dan lugas:\n\n{full_text}"
        )
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            return f"Gagal memproses rangkuman AI: {str(e)}"