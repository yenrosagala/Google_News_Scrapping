import html
import logging
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import time

import feedparser
import pandas as pd
import requests
# MENGGUNAKAN NEWSPAPER4K
from newspaper import Article, Config 
# Menggunakan decoder resmi untuk membongkar URL terenkripsi Google
from googlenewsdecoder import gnewsdecoder 

from app.database import IS_POSTGRES, dapatkan_koneksi_db

# Konfigurasi Logging Standar Produksi
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Inisialisasi HTTP Session dengan pooling
HTTP_SESSION = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=25, pool_maxsize=25)
HTTP_SESSION.mount("http://", adapter)
HTTP_SESSION.mount("https://", adapter)

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "id,en-US;q=0.7,en;q=0.3"
}

# Inisialisasi Konfigurasi Newspaper4k untuk Optimasi Kecepatan
NEWSPAPER_CONFIG = Config()
NEWSPAPER_CONFIG.headers = HTTP_HEADERS
NEWSPAPER_CONFIG.fetch_images = False      
NEWSPAPER_CONFIG.memoize_articles = False  
NEWSPAPER_CONFIG.request_timeout = 12


def bersihkan_teks_html(raw_text):
    if not raw_text:
        return ""
    plain_text = re.sub(r"<[^>]+>", " ", raw_text)
    plain_text = html.unescape(plain_text)
    plain_text = re.sub(r"\s+", " ", plain_text).strip()
    return plain_text


def normalisasi_token_kata_kunci(keyword):
    if not keyword:
        return []
    return [token for token in re.sub(r"[^a-z0-9]+", " ", str(keyword).lower()).split() if token]


def cocok_dengan_kata_kunci(keyword, judul, isi_konten):
    kata_kunci_tokens = normalisasi_token_kata_kunci(keyword)
    if not kata_kunci_tokens:
        return True

    teks_pencarian = " ".join(filter(None, [judul or "", isi_konten or ""]))
    teks_tokens = set(normalisasi_token_kata_kunci(teks_pencarian))
    
    return any(token in teks_tokens for token in kata_kunci_tokens)


def bersihkan_judul_feed(judul):
    if not judul:
        return ""

    judul = judul.strip()
    if " - " in judul:
        judul = " - ".join(judul.split(" - ")[:-1])
    return judul


def ekstrak_teks_dari_html(raw_html):
    if not raw_html:
        return ""

    cleaned_html = re.sub(r"<script.*?</script>", " ", raw_html, flags=re.I | re.S)
    cleaned_html = re.sub(r"<style.*?</style>", " ", cleaned_html, flags=re.I | re.S)

    paragraphs = []
    for match in re.finditer(r"<p[^>]*>(.*?)</p>", cleaned_html, flags=re.I | re.S):
        text = re.sub(r"<[^>]+>", " ", match.group(1))
        text = html.unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > 40:
            paragraphs.append(text)

    if paragraphs:
        joined = "\n\n".join(paragraphs)
        if len(joined.strip()) >= 200:
            return joined.strip()

    plain_text = re.sub(r"<[^>]+>", " ", cleaned_html)
    plain_text = html.unescape(plain_text)
    plain_text = re.sub(r"\s+", " ", plain_text).strip()
    return plain_text


def ekstrak_isi_berita_aman(url_google_news, fallback_text="", judul_feed="", source_url=""):
    """Ekstrak teks artikel penuh menggunakan Newspaper4k."""
    judul_final = bersihkan_judul_feed(judul_feed)
    isi = ""
    url_target = url_google_news or ""
    article = None

    try:
        decoded_url = gnewsdecoder(url_google_news, interval=1, proxy=None)
        if decoded_url.get("status"):
            url_target = decoded_url["decoded_url"]
    except Exception as e:
        logging.error(f"Eror saat memanggil gnewsdecoder: {e}")

    if "https" in url_target and url_target.count("https://") > 1:
        url_target = "https://" + url_target.split("https://")[-1]

    try:
        response = HTTP_SESSION.get(url_target, headers=HTTP_HEADERS, timeout=12)
        if response.status_code == 200:
            html_text = response.text
            teks_html = ekstrak_teks_dari_html(html_text)
            if len(teks_html.strip()) >= 200:
                isi = teks_html.strip()

            # Jika parsing manual kurang memadai, gunakan Newspaper4k dengan HTML lokal
            if not isi:
                article = Article(url_target, language="id", config=NEWSPAPER_CONFIG)
                article.set_html(html_text)
                article.parse()

                if article.text and len(article.text.strip()) >= 150:
                    isi = article.text.strip()

            # Jika masih kosong, biarkan Newspaper4k melakukan download secara penuh
            if not isi:
                article = Article(url_target, language="id", config=NEWSPAPER_CONFIG)
                article.download()
                article.parse()

                if article.text and len(article.text.strip()) >= 150:
                    isi = article.text.strip()

            if article and getattr(article, "title", None) and "Google" not in article.title:
                judul_final = article.title
    except Exception as e:
        logging.warning(f"Engine Newspaper4k gagal mengekstrak konten penuh dari {url_target}: {e}")

    if not isi or len(isi) < 200:
        fallback_text_clean = bersihkan_teks_html(fallback_text)
        if len(fallback_text_clean) >= 200:
            isi = fallback_text_clean
        else:
            isi = ""

    return {
        "judul": judul_final,
        "isi_konten": isi,
        "url_target": url_target,
    }


def ambil_teks_ringkasan(entry):
    if not entry:
        return ""

    if hasattr(entry, "get"):
        for key in ("summary", "description", "content", "subtitle"):
            value = entry.get(key)
            if isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, dict):
                        nested_value = item.get("value") or item.get("body") or item.get("content")
                        if nested_value:
                            return bersihkan_teks_html(str(nested_value))
                    if item:
                        return bersihkan_teks_html(str(item))
            if isinstance(value, dict):
                for nested_key in ("value", "body", "content"):
                    nested_value = value.get(nested_key)
                    if nested_value:
                        return bersihkan_teks_html(str(nested_value))
            if value:
                return bersihkan_teks_html(str(value))

    for attr in ("summary", "description", "content", "text"):
        value = getattr(entry, attr, None)
        if isinstance(value, (list, tuple)):
            for item in value:
                if item:
                    return bersihkan_teks_html(str(item))
        if value:
            return bersihkan_teks_html(str(value))

    return ""


def proses_tunggal_item(entry, keyword_bersih):
    judul_raw = entry.get("title", "")
    link_asli = entry.get("link", "")

    if not judul_raw or not judul_raw.strip() or not link_asli:
        return None

    judul = bersihkan_judul_feed(judul_raw)

    source_obj = entry.get("source")
    media = source_obj.get("title", "Tidak ditemukan") if source_obj and "title" in source_obj else "Tidak ditemukan"

    waktu_tampilan = entry.get("published", "Tidak ditemukan")
    try:
        dt = datetime.strptime(waktu_tampilan, "%a, %d %b %Y %H:%M:%S %Z")
        waktu_iso = dt.isoformat()
    except Exception:
        waktu_iso = datetime.utcnow().isoformat()

    summary_text = ambil_teks_ringkasan(entry)

    hasil_ekstraksi = ekstrak_isi_berita_aman(
        url_google_news=link_asli,
        fallback_text=summary_text,
        judul_feed=judul,
    )

    judul_final = hasil_ekstraksi["judul"]
    isi_konten = hasil_ekstraksi["isi_konten"]
    link_final = hasil_ekstraksi.get("url_target") or link_asli

    if keyword_bersih and not cocok_dengan_kata_kunci(keyword_bersih, judul_final, isi_konten):
        return None

    return {
        "kata_kunci": keyword_bersih,
        "judul": judul_final,
        "media": media,
        "waktu_tampilan": waktu_tampilan,
        "waktu_iso": waktu_iso,
        "link": link_final,
        "isi_konten": isi_konten,
    }


def ambil_feed_google_news(keyword):
    query = urllib.parse.quote(keyword)
    url = f"https://news.google.com/rss/search?q={query}&hl=id&gl=ID&ceid=ID:id"
    response = HTTP_SESSION.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    return feedparser.parse(response.content)


def run_scraper_pipeline(keyword, on_progress=None, on_status=None):
    """Pipeline scraper utama yang mendukung multi-keyword (koma) dan sinonim (pipa)."""
    if not keyword or not keyword.strip():
        if on_status:
            on_status("⚠️ Keyword pencarian kosong.")
        return pd.DataFrame()

    # 1. Pecah input user berdasarkan koma untuk mendapatkan daftar topik utama
    list_keyword = [k.strip() for k in keyword.split(",") if k.strip()]
    total_keywords = len(list_keyword)
    df_gabungan = pd.DataFrame()
    
    def update_status(pesan):
        logging.info(pesan)
        if on_status:
            on_status(pesan)

    for kw_idx, kw_target in enumerate(list_keyword):
        # kw_target di sini bisa berupa kata tunggal "papua" 
        # atau kombinasi sinonim "kecerdasan buatan | AI"
        update_status(f"🔍 [{kw_idx + 1}/{total_keywords}] Memulai pencarian untuk: '{kw_target}'...")
        
        try:
            # Fungsi ini sekarang otomatis menangani operator OR jika ada tanda '|'
            feed = ambil_feed_google_news(kw_target)
            berita_items = feed.get("entries", []) or []
        except Exception as e:
            update_status(f"⚠️ Gagal mengambil feed Google News untuk '{kw_target}': {e}")
            continue

        if not berita_items:
            update_status(f"ℹ️ Tidak ada berita ditemukan untuk keyword '{kw_target}'.")
            continue

        conn = dapatkan_koneksi_db()
        cursor = conn.cursor()
        links_dari_feed = list({e.get("link", "") for e in berita_items if e.get("link", "")})
        existing_links = set()

        ukuran_batch = 500
        for i in range(0, len(links_dari_feed), ukuran_batch):
            batch_links = links_dari_feed[i:i + ukuran_batch]
            if IS_POSTGRES:
                cursor.execute("SELECT link FROM artikel WHERE link = ANY(%s)", (batch_links,))
            else:
                format_placeholder = ",".join(["?"] * len(batch_links))
                cursor.execute(f"SELECT link FROM artikel WHERE link IN ({format_placeholder})", batch_links)
            existing_links.update(row[0] for row in cursor.fetchall())

        items_to_process = [e for e in berita_items if e.get("link", "") not in existing_links]
        total_proses = len(items_to_process)
        
        if total_proses == 0:
            update_status(f"✅ Semua berita untuk '{kw_target}' sudah ada di database.")
            conn.close()
            continue

        data_siap_simpan = []
        update_status(f"⏳ [{kw_target}] Mengunduh {total_proses} artikel secara paralel...")
        
        with ThreadPoolExecutor(max_workers=8) as executor:
            # Kirim kw_target (termasuk string sinonimnya jika ada) ke worker thread
            futu_ke_item = {executor.submit(proses_tunggal_item, item, kw_target): item for item in items_to_process}
            
            for index, future in enumerate(as_completed(futu_ke_item)):
                if on_progress:
                    base_progress = kw_idx / total_keywords
                    current_kw_progress = ((index + 1) / total_proses) / total_keywords
                    on_progress(min(base_progress + current_kw_progress, 1.0))
                try:
                    hasil = future.result()
                    if hasil:
                        data_siap_simpan.append(hasil)
                        update_status(f"🚀 [{kw_target}] Konten ditarik: {hasil['judul'][:30]}...")
                except Exception as exc:
                    logging.error(f"Error pada thread worker: {exc}")

        if data_siap_simpan:
            try:
                if IS_POSTGRES:
                    query_insert = """
                        INSERT INTO artikel (kata_kunci, judul, media, waktu_tampilan, waktu_iso, link, isi_konten)
                        VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (link) DO NOTHING
                    """
                else:
                    query_insert = """
                        INSERT OR IGNORE INTO artikel (kata_kunci, judul, media, waktu_tampilan, waktu_iso, link, isi_konten)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """
                
                kolom_db = ["kata_kunci", "judul", "media", "waktu_tampilan", "waktu_iso", "link", "isi_konten"]
                list_tuple_data = [tuple(item[col] for col in kolom_db) for item in data_siap_simpan]
                
                for i in range(0, len(list_tuple_data), 100):
                    cursor.executemany(query_insert, list_tuple_data[i:i + 100])
                    
                conn.commit()
                df_kw = pd.DataFrame(data_siap_simpan)[kolom_db]
                df_gabungan = pd.concat([df_gabungan, df_kw], ignore_index=True)
                update_status(f"✅ [{kw_target}] Sukses menyimpan {len(df_kw)} artikel baru.")
                
            except Exception as e:
                logging.error(f"Gagal commit batch ke DB untuk '{kw_target}': {e}")
                conn.rollback()
            finally:
                conn.close()
        else:
            conn.close()

    if not df_gabungan.empty:
        update_status(f"🎉 Semua selesai! Total {len(df_gabungan)} artikel baru dimasukkan dari seluruh keyword.")
    return df_gabungan