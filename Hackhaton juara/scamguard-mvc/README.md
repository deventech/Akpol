# SCAMGUARD
Analisis URL dan konten website untuk deteksi dini ancaman phishing.
Tim Akpoll - INCEPTION 2026 Hackathon, Politeknik Negeri Jember.

## Menjalankan
```
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
python run.py                # buka http://127.0.0.1:5000
```

## Struktur (MVC)
- `app/models/`       logika analisis (URL, konten, skor risiko, klasifikasi)
- `app/controllers/`  route / penghubung request dan model
- `app/views/`        template HTML dan static (CSS/JS)
- `app/services/`     Web Scraper MCP, VirusTotal/PhishTank/WHOIS
- `data_pipeline/`    pembersihan data (CSV/JSONL)
- `ml/`               pelatihan model (tahap lanjut)

## Status
Prototipe: analisis baru berbasis karakteristik URL. Analisis konten dan model ML masih tahap rencana.
