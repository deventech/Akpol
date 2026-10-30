# SCAMGUARD Dataset Collection Pipeline

Pipeline otomatis untuk mengumpulkan dataset website (phishing / legitimate / online_gambling / unknown) berbasis analisis URL & konten.

Pipeline ini **mengintegrasikan logika asli** dari repository:

> https://github.com/Rumblingb/web-scraper-mcp

(Repository tersebut sudah di-archive, namun source code `server.py` dan tools MCP-nya masih valid dan disalin ke folder `mcp_server/`.)

---

## Tools MCP yang benar-benar tersedia di repository asli

| Tool | Parameter | Deskripsi |
|------|-----------|-----------|
| `scrape_url` | `url` (wajib), `selector` (opsional) | Ambil 1 URL → title, meta description, text content, links, images. Jika selector diberikan, kembalikan elemen yang cocok. |
| `scrape_urls` | `urls[]` | Batch scrape beberapa URL (hasil lebih ringkas: title + snippet 500 karakter + jumlah link/image). |
| `extract_emails` | `url` | Ekstrak alamat email dari halaman. |
| `extract_links` | `url`, `domain_filter?` | Ekstrak semua hyperlink, opsional filter domain. |

**Tidak ada tool lain.** Semua fungsi di pipeline ini dibangun di atas ekstraksi yang sama (httpx + regex) yang dipakai server MCP di atas.

Headings (H1/H2/H3) diekstrak dengan pola regex yang konsisten dengan gaya parsing di `server.py` (karena original server mendukung selector `h1`, `h2`, `h3`).

---

## Struktur Folder

```
scamguard-dataset-pipeline/
├── mcp_server/                 # Salinan server MCP asli
│   ├── server.py
│   └── requirements.txt
├── src/
│   ├── scraper_core.py         # Logika scraping (mirror tools MCP)
│   ├── input_loader.py         # TAHAP 1 – baca CSV / JSON / manual
│   ├── pipeline.py             # TAHAP 2+3 – scrape + simpan JSONL/CSV/Excel
│   └── cleaning.py             # TAHAP 4 – cleaning & dedup
├── data/
│   ├── input/                  # Daftar URL sumber
│   ├── raw/                    # Hasil scraping mentah
│   ├── cleaned/                # Setelah cleaning
│   ├── verified/               # Setelah verifikasi label manual / eksternal
│   └── ml_ready/               # Siap untuk eksperimen model (split train/val/test)
├── scripts/
│   └── run_full_pipeline.sh
├── docs/
│   └── ARCHITECTURE.md
├── examples/
├── requirements.txt
└── README.md
```

---

## Instalasi

```bash
# Clone / extract project ini
cd scamguard-dataset-pipeline

# Dependencies pipeline
python3 -m pip install -r requirements.txt

# (Opsional) Jalankan MCP server asli
cd mcp_server
python3 -m pip install -r requirements.txt
python3 server.py          # stdio MCP server
```

### Menjalankan MCP Server (untuk client AI)

Tambahkan ke konfigurasi Claude Desktop / VS Code / Cline:

```json
{
  "mcpServers": {
    "web-scraper": {
      "command": "python",
      "args": ["/absolute/path/to/scamguard-dataset-pipeline/mcp_server/server.py"]
    }
  }
}
```

---

## TAHAP 1 — Input Data

Format kategori yang didukung (harus dipisah, **jangan** map `online_gambling` → `phishing`):

- `phishing`
- `legitimate`
- `online_gambling`
- `unknown`

### CSV

```csv
url,source_category,source,notes
https://example.com,legitimate,manual,IANA example
https://phish.example,phishing,phishtank,verified 2024-01
```

### JSON

```json
{
  "urls": [
    {"url": "https://example.com", "source_category": "legitimate", "source": "manual"}
  ]
}
```

### Manual

```bash
python3 -m src.pipeline --url https://example.com --url https://python.org --category legitimate
```

---

## TAHAP 2+3 — Scraping & Penyimpanan

```bash
python3 -m src.pipeline \
  --csv data/input/sample_urls.csv \
  --out-dir data/raw \
  --prefix sample \
  --concurrency 5 \
  --timeout 30
```

Atau dari JSON:

```bash
python3 -m src.pipeline --json data/input/sample_urls.json --out-dir data/raw
```

### Field output (satu record = satu website)

| Field | Tipe | Keterangan |
|-------|------|------------|
| `source_url` | str | URL asli |
| `source_category` | str | phishing / legitimate / online_gambling / unknown |
| `risk_level` | int | **0** = aman · **1** = ragu-ragu · **2** = tidak aman |
| `risk_label` | str | teks: `aman` / `ragu-ragu` / `tidak aman` |
| `source` | str | asal label (manual, phishtank, …) |
| `page_title` | str\|null | `<title>` |
| `meta_description` | str\|null | meta description |
| `extracted_text` | str\|null | teks terlihat (HTML di-strip) |
| `headings` | object | `{"h1": [...], "h2": [...], "h3": [...]}` |
| `links` | list | daftar `{url, text}` (maks 200) |
| `link_count` | int | jumlah link asli |
| `scrape_status` | str | `success` / `failed` |
| `error_message` | str\|null | pesan error jika gagal |
| `scraped_at` | str | ISO-8601 UTC |

### Label level risiko (kolom Excel)

| risk_level | risk_label | Dari `source_category` |
|------------|------------|------------------------|
| **0** | aman | `legitimate` |
| **1** | ragu-ragu | `unknown`, `online_gambling` |
| **2** | tidak aman | `phishing` |

Level diisi **hanya dari label sumber**, bukan dari isi konten hasil scraping.


File dihasilkan dalam **tiga format**:

- `data/raw/<prefix>_<timestamp>.jsonl`  (untuk processing Python)
- `data/raw/<prefix>_<timestamp>.csv`    (bisa dibuka di Excel)
- `data/raw/<prefix>_<timestamp>.xlsx`   (**Excel native** — siap dibuka di Microsoft Excel / Google Sheets / LibreOffice)

---

## TAHAP 4 — Cleaning

```bash
python3 -m src.cleaning data/raw/sample_YYYYMMDD_HHMMSS.jsonl \
  --out-dir data/cleaned \
  --prefix sample
```

Output:

- `cleaned_all_cleaned.*` – semua URL unik setelah dedup
- `cleaned_success.*` – hanya scrape berhasil
- `cleaned_failed.*` – scrape gagal
- `cleaned_incomplete.*` – berhasil tapi title + text kosong

Proses cleaning:

- Hapus duplikat berdasarkan `source_url`
- Bersihkan karakter kontrol & whitespace berlebih
- Tidak menghapus konten penting
- Memisahkan success / failed

---

## TAHAP 5 — Label Verification

**Label tidak boleh dibuat sembarangan dari hasil scraping.**

Rekomendasi:

1. Gunakan label dari sumber terpercaya (PhishTank, OpenPhish, VirusTotal, daftar resmi, dll.) dan **dokumentasikan** kolom `source` + tanggal verifikasi.
2. Untuk `online_gambling` simpan sebagai kategori terpisah.
3. Jika belum yakin → `unknown`.
4. Verifikasi manual disimpan di `data/verified/` dengan kolom tambahan misalnya:

```json
{
  "source_url": "...",
  "source_category": "phishing",
  "verification_source": "phishtank",
  "verification_status": "confirmed",
  "verified_at": "2026-10-30T12:00:00Z",
  "verifier_notes": "..."
}
```

Jangan menganggap “konten mencurigakan” dari scraping sebagai bukti phishing.

---

## TAHAP 6 — Dataset Final untuk ML (BERT / Transformer)

Pisahkan dengan jelas:

| Folder | Isi |
|--------|-----|
| `data/raw/` | Hasil scrape mentah |
| `data/cleaned/` | Setelah dedup & cleaning |
| `data/verified/` | Setelah label diverifikasi |
| `data/ml_ready/` | Split train/val/test (tanpa leakage) |

Contoh persiapan (setelah verifikasi):

```python
import pandas as pd
from sklearn.model_selection import train_test_split

df = pd.read_json("data/verified/verified.jsonl", lines=True)
# Hanya gunakan baris yang verified & success
df = df[(df.scrape_status == "success") & (df.verification_status == "confirmed")]

train, temp = train_test_split(df, test_size=0.3, stratify=df.source_category, random_state=42)
val, test = train_test_split(temp, test_size=0.5, stratify=temp.source_category, random_state=42)

train.to_json("data/ml_ready/train.jsonl", orient="records", lines=True, force_ascii=False)
val.to_json("data/ml_ready/val.jsonl", orient="records", lines=True, force_ascii=False)
test.to_json("data/ml_ready/test.jsonl", orient="records", lines=True, force_ascii=False)
```

**Tidak ada model yang dilatih di repository ini.** Hanya pipeline pengumpulan data.

---

## Keamanan yang diterapkan

- Hanya skema `http` / `https`
- Blokir localhost, IP privat, link-local, reserved ranges (anti-SSRF)
- Timeout default 30 detik
- Concurrency terbatas (default 5)
- Tidak melewati login / CAPTCHA / autentikasi
- Tidak melakukan eksploitasi
- User-Agent yang jelas menyatakan scraper

---

## Menjalankan contoh end-to-end

```bash
chmod +x scripts/run_full_pipeline.sh
./scripts/run_full_pipeline.sh
```

Atau langkah demi langkah:

```bash
python3 -m src.pipeline --csv data/input/sample_urls.csv --out-dir data/raw --prefix demo
python3 -m src.cleaning data/raw/demo_*.jsonl --out-dir data/cleaned --prefix demo
```

---

## Catatan penting

1. Repository asli `Rumblingb/web-scraper-mcp` sudah **archived** (read-only). Kode di `mcp_server/server.py` adalah salinan langsung dari sumber.
2. Pipeline ini **tidak** memanggil MCP server melalui protocol stdio saat batch scraping (lebih praktis & stabil). Ia memakai **fungsi ekstraksi yang sama** agar hasil konsisten dengan tool `scrape_url`.
3. Jika Anda ingin memakai MCP server secara native (misalnya dari Claude), gunakan `mcp_server/server.py` dan panggil tool `scrape_url` / `scrape_urls` dari client.
4. Jangan mengklaim dataset sudah “verified” atau model sudah dilatih sebelum proses tersebut benar-benar dilakukan.

---

## Lisensi

Kode pipeline SCAMGUARD: bebas digunakan untuk riset.
Kode MCP server asli: MIT (lihat `mcp_server/server.py` & repository asli).
