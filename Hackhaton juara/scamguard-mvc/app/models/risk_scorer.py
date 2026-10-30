"""Model: skor risiko 0-100 dan kategori (proposal bab 3.4)."""

CATEGORIES = {
    "hi": {"name": "Risiko Tinggi", "tag": "Indikasi phishing",
           "explanation": "URL ini memiliki beberapa indikator yang umum ditemukan pada situs phishing. Meskipun tidak dapat dipastikan secara mutlak, kombinasi indikator tersebut menunjukkan potensi ancaman yang perlu diwaspadai.",
           "recommendation": "Jangan lanjutkan akses atau memasukkan data pribadi maupun kredensial akun pada website ini."},
    "md": {"name": "Risiko Sedang", "tag": "Perlu diperiksa",
           "explanation": "Ditemukan sejumlah indikator yang perlu diperhatikan lebih lanjut. Indikator ini belum tentu berarti situs berbahaya, tetapi sebaiknya Anda berhati-hati.",
           "recommendation": "Periksa kembali alamat domain dan hindari memasukkan informasi sensitif sebelum Anda memastikan keamanannya."},
    "lo": {"name": "Risiko Rendah", "tag": "Indikator minim",
           "explanation": "Indikator phishing yang teridentifikasi relatif sedikit berdasarkan pemeriksaan karakteristik URL. Hasil ini tidak menjamin bahwa situs sepenuhnya aman.",
           "recommendation": "Tetap pastikan keaslian website sebelum memberikan informasi pribadi."},
}


def build_result(analysis: dict) -> dict:
    score = min(100, sum(i["weight"] for i in analysis["indicators"]))
    level = "hi" if score >= 55 else "md" if score >= 25 else "lo"
    return {**analysis, "score": score, "level": level, **CATEGORIES[level]}
