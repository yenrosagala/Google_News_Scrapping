import base64
import html
import re
import urllib.parse

import requests
import feedparser
from newspaper import Article

from app.database import IS_POSTGRES, dapatkan_koneksi_db


def decode_google_news_link(url_google_news, source_url=None, article_title=None, summary_text=None):
    """Ubah link Google News RSS/encoded/read menjadi URL sumber asli jika memungkinkan."""
    if not url_google_news:
        return url_google_news

    if source_url:
        parsed_source = urllib.parse.urlparse(source_url)
        if parsed_source.scheme and parsed_source.netloc:
            if parsed_source.path in {"", "/"}:
                if article_title:
                    slug = re.sub(r"[^a-z0-9]+", "-", article_title.lower()).strip("-")
                    if slug:
                        return f"{source_url.rstrip('/')}/{slug}"
                if summary_text:
                    summary_slug = re.sub(r"[^a-z0-9]+", "-", summary_text.lower()).strip("-")
                    if summary_slug:
                        return f"{source_url.rstrip('/')}/{summary_slug[:80]}"
            return source_url

    parsed = urllib.parse.urlparse(url_google_news)
    if parsed.netloc not in {"news.google.com", "www.news.google.com"}:
        return url_google_news

    if parsed.path.startswith("/read/"):
        return source_url or url_google_news

    if "/rss/articles/" not in parsed.path:
        return url_google_news

    try:
        raw_token = parsed.path.split("/rss/articles/", 1)[1].split("?", 1)[0]
        decoded = base64.urlsafe_b64decode(raw_token + "=" * (-len(raw_token) % 4))
        decoded_text = decoded.decode("utf-8", errors="ignore")

        matches = re.findall(r"https?://[^\s\"'<>]+", decoded_text)
        if matches:
            cleaned = matches[0].rstrip(").,;:")
            if cleaned.startswith("http"):
                return cleaned
            return f"https://{cleaned.lstrip('/')}"
    except Exception:
        pass

    if url_google_news.startswith("https://news.google.com/rss/articles/"):
        return source_url or "https://news.google.com/"

    return url_google_news


def bersihkan_teks_html(raw_text):
    if not raw_text:
        return ""
    plain_text = re.sub(r"<[^>]+>", " ", raw_text)
    plain_text = html.unescape(plain_text)
    plain_text = re.sub(r"\s+", " ", plain_text).strip()
    return plain_text


def ekstrak_isi_berita_aman(url_google_news, fallback_text="", judul=""):
    hasil_teks = ""
    try:
        artikel = Article(url_google_news, language="id", keep_article_html=False)
        artikel.download()
        artikel.parse()

        for kandidat in [getattr(artikel, "summary", ""), getattr(artikel, "text", "")]:
            teks = (kandidat or "").strip()
            if not teks:
                continue
            if len(teks) < 40:
                continue
            if judul and teks.lower() == judul.lower():
                continue
            hasil_teks = teks
            break
    except Exception:
        hasil_teks = ""

    fallback_text = bersihkan_teks_html(fallback_text or "")
    if not hasil_teks or len(hasil_teks) < 40:
        if fallback_text:
            return fallback_text
        if judul:
            return f"[Gagal Ekstrak]: {judul}"
        return "[Gagal Ekstrak]: Teks terlalu pendek atau dilindungi paywall"

    return hasil_teks


def ambil_feed_google_news(keyword):
    query = requests.utils.quote(keyword)
    url = f"https://news.google.com/rss/search?q={query}&hl=id&gl=ID&ceid=ID:id"
    response = requests.get(
        url,
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    response.raise_for_status()
    return feedparser.parse(response.content)


def run_scraper_pipeline(keyword, progress_bar, status_text):
    conn = dapatkan_koneksi_db()
    cursor = conn.cursor()
    jumlah_data_baru = 0

    try:
        feed = ambil_feed_google_news(keyword)
        berita_items = getattr(feed, "entries", []) or []
    except Exception as e:
        status_text.text(f"⚠️ Gagal mengambil feed Google News: {e}")
        conn.close()
        return 0

    total_target = len(berita_items)
    if total_target == 0:
        status_text.text("⚠️ Tidak ada berita yang ditemukan dari Google News.")
        conn.close()
        return 0

    for index, entry in enumerate(berita_items):
        progress_bar.progress((index + 1) / total_target)
        judul_raw = getattr(entry, "title", "") or ""
        if not judul_raw or not judul_raw.strip():
            continue

        link = getattr(entry, "link", "") or ""
        if not link:
            continue

        source_obj = getattr(entry, "source", None)
        source_url = None
        if source_obj:
            source_url = getattr(source_obj, "href", None) or getattr(source_obj, "url", None) or getattr(source_obj, "link", None)

        link_asli = link
        status_text.text(f"⏳ [{index + 1}/{total_target}] Memeriksa: {judul_raw[:40]}...")

        if IS_POSTGRES:
            cursor.execute("SELECT 1 FROM artikel WHERE link = %s", (link_asli,))
        else:
            cursor.execute("SELECT 1 FROM artikel WHERE link = ?", (link_asli,))

        if cursor.fetchone():
            continue

        if IS_POSTGRES:
            cursor.execute(
                "SELECT id, link FROM artikel WHERE kata_kunci = %s AND judul = %s",
                (keyword.strip(), judul_raw.strip()),
            )
        else:
            cursor.execute(
                "SELECT id, link FROM artikel WHERE kata_kunci = ? AND judul = ?",
                (keyword.strip(), judul_raw.strip()),
            )

        row_lama = cursor.fetchone()
        if row_lama:
            row_id, row_link = row_lama
            if row_link != link_asli:
                if IS_POSTGRES:
                    cursor.execute("UPDATE artikel SET link = %s WHERE id = %s", (link_asli, row_id))
                else:
                    cursor.execute("UPDATE artikel SET link = ? WHERE id = ?", (link_asli, row_id))
            continue

        media = "Tidak ditemukan"
        if source_obj and hasattr(source_obj, "title"):
            media = source_obj.title

        waktu_tampilan = getattr(entry, "published", "Tidak ditemukan") or "Tidak ditemukan"
        waktu_iso = waktu_tampilan

        summary_text = getattr(entry, "summary", "") or ""
        judul = judul_raw.strip()
        url_berita_target = decode_google_news_link(
            link,
            source_url=source_url,
            article_title=judul,
            summary_text=summary_text,
        )
        isi_konten = ekstrak_isi_berita_aman(url_berita_target, fallback_text=summary_text, judul=judul)

        kata_kunci_bersih = keyword.lower().strip()
        if kata_kunci_bersih and not (kata_kunci_bersih in judul.lower() or kata_kunci_bersih in isi_konten.lower()):
            continue

        try:
            if IS_POSTGRES:
                cursor.execute(
                    """
                    INSERT INTO artikel (kata_kunci, judul, media, waktu_tampilan, waktu_iso, link, isi_konten)
                    VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (link) DO NOTHING
                    """,
                    (keyword.strip(), judul, media, waktu_tampilan, waktu_iso, link_asli, isi_konten),
                )
            else:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO artikel (kata_kunci, judul, media, waktu_tampilan, waktu_iso, link, isi_konten)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (keyword.strip(), judul, media, waktu_tampilan, waktu_iso, link_asli, isi_konten),
                )

            if IS_POSTGRES:
                if cursor.rowcount > 0:
                    jumlah_data_baru += 1
            else:
                if conn.total_changes > 0:
                    jumlah_data_baru += 1
        except Exception:
            pass

    conn.commit()
    conn.close()
    return jumlah_data_baru
