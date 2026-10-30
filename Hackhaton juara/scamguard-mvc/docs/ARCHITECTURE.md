# Arsitektur Pipeline SCAMGUARD Dataset

```
┌─────────────────┐
│  Input Sources  │
│  CSV / JSON /   │
│  Manual URLs    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  input_loader   │  ← normalisasi kategori & URL
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  scraper_core   │  ← logika identik dengan tools MCP
│  (httpx+regex)  │     scrape_url / scrape_urls
│  + SSRF guard   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   pipeline.py   │  ← build record kanonik
│  JSONL + CSV    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  data/raw/      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   cleaning.py   │  ← dedup, clean text, split success/failed
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ data/cleaned/   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Manual / External│  ← PhishTank, VirusTotal, WHOIS, dsb.
│ Label Verification│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ data/verified/  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Stratified     │  ← train / val / test (no leakage)
│  Split          │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ data/ml_ready/  │  ← siap untuk BERT / Transformer
└─────────────────┘
```

## Hubungan dengan web-scraper-mcp

```
Original MCP Server (mcp_server/server.py)
├── scrape_url(url, selector?)
├── scrape_urls(urls[])
├── extract_emails(url)
└── extract_links(url, domain_filter?)

        │  (fungsi ekstraksi disalin / di-mirror)
        ▼

scraper_core.py
├── extract_title / extract_meta_description / extract_text_content
├── extract_links / extract_images
├── extract_headings          ← tambahan (selector h1/h2/h3 sudah didukung original)
├── is_safe_url               ← tambahan keamanan
└── scrape_url / scrape_urls  ← high-level async API
```

Pipeline batch **tidak** membutuhkan proses MCP server berjalan (lebih sederhana untuk pengumpulan dataset besar). Untuk integrasi dengan agent AI, gunakan `mcp_server/server.py` secara langsung.
