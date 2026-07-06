import os
from pathlib import Path

class Config:
    # Base Directory Proyek
    BASE_DIR = Path(__file__).resolve().parent.parent.parent

    # Menggunakan DB_NAME agar tidak merusak database_manager.py
    DB_NAME = os.getenv("DATABASE_URL", str(BASE_DIR / "berita_google_news.db"))
    
    @property
    def DB_PATH(self):
        return self.DB_NAME

    # Streamlit Page Settings
    PAGE_TITLE = "Google News Scraper & Sentiment Analyzer"
    PAGE_ICON = "📰"
    LAYOUT = "wide"

    # Scraping Defaults
    DEFAULT_LIMIT = 100
    TIMEOUT = 30

# 1. Instansiasi objek secara internal
_config_instance = Config()

# 2. Fungsi helper yang dicari oleh database_manager.py
def get_config():
    """Mengembalikan instance dari Config (Singleton Pattern)."""
    return _config_instance

# 3. Export variabel global untuk kebutuhan streamlit_app.py
PAGE_TITLE = _config_instance.PAGE_TITLE
PAGE_ICON = _config_instance.PAGE_ICON
LAYOUT = _config_instance.LAYOUT