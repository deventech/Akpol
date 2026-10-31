"""
mcp_style_scrape.py
===================
Scrape URL (format MCP) + otomatis append ke SATU file Excel SCAMGUARD.

Default: semua hasil masuk ke data/raw/scamguard_dataset.xlsx
(tiap URL baru = baris baru di file yang sama)

Contoh:
  python -m src.mcp_style_scrape https://example.com --category legitimate
  python -m src.mcp_style_scrape https://situs-judol.com --category online_gambling
  python -m src.mcp_style_scrape https://a.com https://b.com --category unknown
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import build_record, _flatten_records
from src.scraper_core import scrape_url

try:
    import pandas as pd
except ImportError:
    pd = None


MASTER_XLSX = Path("data/raw/scamguard_dataset.xlsx")
MASTER_JSONL = Path("data/raw/scamguard_dataset.jsonl")
MASTER_CSV = Path("data/raw/scamguard_dataset.csv")


def to_mcp_payload(record: dict) -> dict:
    return {
        "url": record.get("url"),
        "title": record.get("title"),
        "meta_description": record.get("meta_description"),
        "text_content": record.get("text_content"),
        "links": record.get("links") or [],
        "images": record.get("images") or [],
        "success": record.get("success", False),
        "source_category": record.get("source_category"),
        "risk_level": record.get("risk_level"),
        "risk_label": record.get("risk_label"),
        "headings": record.get("headings") or {},
        "error": record.get("error_message"),
    }


def load_existing_rows(xlsx_path: Path) -> list[dict]:
    """Load existing Excel rows as list of dicts (flattened)."""
    if pd is None or not xlsx_path.exists():
        return []
    try:
        df = pd.read_excel(xlsx_path, engine="openpyxl")
        return df.to_dict(orient="records")
    except Exception:
        return []


def append_and_save(records: list[dict], xlsx_path: Path, jsonl_path: Path, csv_path: Path) -> int:
    """
    Append new records to master files.
    - Dedup by url (baris baru menimpa URL yang sama)
    - Return total jumlah baris setelah simpan
    """
    if pd is None:
        raise ImportError("pandas + openpyxl diperlukan. pip install pandas openpyxl")

    xlsx_path.parent.mkdir(parents=True, exist_ok=True)

    new_flat = _flatten_records(records)
    existing = load_existing_rows(xlsx_path)

    # Index by url
    by_url: dict[str, dict] = {}
    for row in existing:
        u = str(row.get("url") or row.get("source_url") or "").strip()
        if u:
            by_url[u] = row
    for row in new_flat:
        u = str(row.get("url") or row.get("source_url") or "").strip()
        if u:
            by_url[u] = row

    all_rows = list(by_url.values())
    df = pd.DataFrame(all_rows)

    preferred = [
        "url", "title", "meta_description", "text_content", "success",
        "source", "notes", "keywords",
        "canonical_url", "og_site_name", "og_title", "og_description", "og_image",
        "headings_json", "links_json", "link_count",
        "images_json", "image_count", "html_length",
        "scrape_status", "error_message", "scraped_at",
        # kategori dulu, lalu label — di AKHIR
        "source_category", "risk_level", "risk_label",
    ]
    cols = [c for c in preferred if c in df.columns] + [c for c in df.columns if c not in preferred]
    if cols:
        df = df[cols]

    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    df.to_csv(csv_path, index=False, encoding="utf-8")

    # JSONL: rewrite full master (MCP-style nested if possible from records)
    # Simpan versi flat + nested dari records baru digabung simple
    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in all_rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")

    return len(all_rows)


async def scrape_one(url: str, category: str) -> dict:
    try:
        result = await scrape_url(url)
    except Exception as e:
        result = {"url": url, "success": False, "error": str(e)}
    input_rec = {
        "url": url,
        "source_category": category,
        "source": "manual",
        "notes": "",
    }
    return build_record(input_rec, result)


async def main_async(urls: list[str], category: str, xlsx_path: Path) -> None:
    print(f"[*] URLs     : {len(urls)}")
    print(f"[*] Category : {category}")
    print(f"[*] Excel    : {xlsx_path}  (semua hasil jadi SATU file)")
    print()

    records = []
    for url in urls:
        print(f"[*] Scraping: {url}")
        rec = await scrape_one(url, category)
        records.append(rec)
        payload = to_mcp_payload(rec)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print()

    jsonl_path = xlsx_path.with_suffix(".jsonl")
    csv_path = xlsx_path.with_suffix(".csv")
    total = append_and_save(records, xlsx_path, jsonl_path, csv_path)

    print("[+] Tersimpan ke SATU file master:")
    print(f"    Excel  -> {xlsx_path}")
    print(f"    CSV    -> {csv_path}")
    print(f"    JSONL  -> {jsonl_path}")
    print(f"    Total baris sekarang: {total}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape URL(s) -> append ke SATU file Excel SCAMGUARD"
    )
    parser.add_argument(
        "urls",
        nargs="+",
        help="Satu atau lebih URL",
    )
    parser.add_argument(
        "--category",
        default="unknown",
        choices=["phishing", "legitimate", "online_gambling", "unknown"],
    )
    parser.add_argument(
        "--excel",
        default=str(MASTER_XLSX),
        help=f"Path file Excel master (default: {MASTER_XLSX})",
    )
    args = parser.parse_args()
    asyncio.run(main_async(args.urls, args.category, Path(args.excel)))


if __name__ == "__main__":
    main()
