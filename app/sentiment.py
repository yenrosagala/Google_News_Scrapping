import streamlit as st


@st.cache_resource
def muat_kamus_sentimen_kompleks():
    kamus = {
        'sukses': 5, 'berhasil': 5, 'untung': 4, 'surplus': 5, 'tumbuh': 3, 'meningkat': 3,
        'naik': 2, 'pulih': 4, 'optimal': 4, 'bagus': 3, 'baik': 3, 'aman': 4, 'stabil': 4,
        'prestasi': 5, 'juara': 5, 'hebat': 4, 'unggul': 4, 'maju': 3, 'berkembang': 3,
        'efektif': 4, 'efisien': 4, 'inovasi': 4, 'apresiasi': 4, 'mendukung': 3, 'setuju': 3,
        'puas': 4, 'senang': 3, 'bahagia': 4, 'investasi': 2, 'bantuan': 3, 'membaik': 4,
        'gagal': -5, 'rugi': -4, 'krisis': -5, 'anjlok': -4, 'turun': -2, 'merosot': -4,
        'korupsi': -5, 'suap': -5, 'pungli': -4, 'tewas': -5, 'korban': -4, 'inflasi': -3,
        'defisit': -4, 'sanksi': -4, 'buruk': -4, 'bahaya': -4, 'ancaman': -4, 'hancur': -5,
        'kecewa': -4, 'marah': -4, 'protes': -3, 'ditangkap': -3, 'tersangka': -4, 'lemah': -3
    }
    return kamus


def hitung_sentimen_leksikon(teks):
    if not teks or "[Gagal Ekstrak]" in teks:
        return "Netral"
    kamus_leksikon = muat_kamus_sentimen_kompleks()
    teks_bersih = teks.lower().replace('.', ' ').replace(',', ' ').replace('?', ' ').replace('!', ' ')
    kata_kata = teks_bersih.split()
    total_skor = 0
    for kata in kata_kata:
        if kata in kamus_leksikon:
            total_skor += kamus_leksikon[kata]
    if total_skor > 1:
        return "Positif"
    if total_skor < -1:
        return "Negatif"
    return "Netral"
