"""
pipeline.py
===========
TAHAP 2 & 3 — Automated scraping + storage (JSONL + CSV + Excel .xlsx)

Uses the extraction logic that is identical to the tools exposed by
web-scraper-mcp (scrape_url / scrape_urls).

Output record schema (one website = one record):
  source_url, source_category, source, page_title, meta_description,
  extracted_text, headings, links, scrape_status, scraped_at, error_message
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# Allow running as script from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.input_loader import load_urls, VALID_CATEGORIES
from src.scraper_core import scrape_urls


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Pemetaan kategori sumber → label risiko (untuk kolom Excel di AKHIR)
# Label: rendah | sedang | tinggi
# Kategori: legitimate | unknown | online_gambling | phishing
RISK_LEVEL_MAP = {
    "legitimate": (0, "rendah"),
    "unknown": (1, "sedang"),
    "online_gambling": (1, "sedang"),
    "phishing": (2, "tinggi"),
}


def category_to_risk(category: str) -> tuple[int, str]:
    """Return (risk_level, risk_label) from source_category. Tidak mengarang dari konten scrape."""
    cat = (category or "unknown").strip().lower()
    return RISK_LEVEL_MAP.get(cat, (1, "sedang"))


def build_record(
    input_rec: dict[str, Any],
    scrape_result: dict[str, Any],
) -> dict[str, Any]:
    """
    Canonical record = format MCP scrape_url + label SCAMGUARD.

    Field MCP (sama seperti output tool scrape_url):
      url, title, meta_description, text_content, links, images, success

    Field tambahan SCAMGUARD:
      source_category, risk_level, risk_label, source, notes,
      headings, keywords, canonical_url, og_*, scrape_status, scraped_at
    """
    success = scrape_result.get("success", False)
    headings = scrape_result.get("headings") or {}
    raw_links = scrape_result.get("links") or []
    raw_images = scrape_result.get("images") or []

    # Format link/image IDENTIK dengan MCP server (href/absolute_url/text, src/absolute_url/alt)
    link_list = []
    for ln in raw_links[:200]:
        link_list.append({
            "href": ln.get("href") or "",
            "absolute_url": ln.get("absolute_url") or ln.get("href") or "",
            "text": (ln.get("text") or "")[:200],
        })

    image_list = []
    for im in raw_images[:50]:
        image_list.append({
            "src": im.get("src") or "",
            "absolute_url": im.get("absolute_url") or im.get("src") or "",
            "alt": (im.get("alt") or "")[:200],
        })

    category = input_rec.get("source_category", "unknown")
    risk_level, risk_label = category_to_risk(category)
    og = scrape_result.get("og_tags") or {}

    return {
        # ── MCP-compatible (sama seperti scrape_url) ──
        "url": input_rec["url"],
        "title": scrape_result.get("title"),
        "meta_description": scrape_result.get("meta_description"),
        "text_content": scrape_result.get("text_content"),
        "links": link_list,
        "images": image_list,
        "success": success,

        # ── SCAMGUARD labels & extras ──
        "source_category": category,
        "risk_level": risk_level,
        "risk_label": risk_label,
        "source": input_rec.get("source", ""),
        "notes": input_rec.get("notes", ""),
        "keywords": scrape_result.get("keywords"),
        "canonical_url": scrape_result.get("canonical_url"),
        "og_site_name": og.get("site_name"),
        "og_title": og.get("title"),
        "og_description": og.get("description"),
        "og_image": og.get("image"),
        "headings": headings,
        "link_count": len(raw_links),
        "image_count": len(raw_images),
        "html_length": scrape_result.get("html_length"),
        "scrape_status": "success" if success else "failed",
        "error_message": scrape_result.get("error") if not success else None,
        "scraped_at": _now_iso(),

        # alias lama (kompatibilitas Excel / script lama)
        "source_url": input_rec["url"],
        "page_title": scrape_result.get("title"),
        "extracted_text": scrape_result.get("text_content"),
    }


def write_jsonl(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            # JSON-serialise nested structures
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _flatten_records(records: list[dict]) -> list[dict]:
    """Flatten nested headings/links into JSON strings for tabular formats."""
    rows = []
    for rec in records:
        row = dict(rec)
        row["headings_json"] = json.dumps(rec.get("headings") or {}, ensure_ascii=False)
        row["links_json"] = json.dumps(rec.get("links") or [], ensure_ascii=False)
        row["images_json"] = json.dumps(rec.get("images") or [], ensure_ascii=False)
        # remove nested objects that Excel/CSV cannot store directly
        row.pop("headings", None)
        row.pop("links", None)
        row.pop("images", None)
        # hapus alias lama biar Excel rapi (pakai url/title/text_content)
        for alias in ("source_url", "page_title", "extracted_text"):
            row.pop(alias, None)
        rows.append(row)
    return rows


def write_csv(records: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not records:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = [
        # MCP-style & konten dulu
        "url",
        "title",
        "meta_description",
        "text_content",
        "success",
        "source",
        "notes",
        "keywords",
        "canonical_url",
        "og_site_name",
        "og_title",
        "og_description",
        "og_image",
        "headings_json",
        "links_json",
        "link_count",
        "images_json",
        "image_count",
        "html_length",
        "scrape_status",
        "error_message",
        "scraped_at",
        # kategori & label di AKHIR Excel
        "source_category",
        "risk_level",
        "risk_label",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in _flatten_records(records):
            writer.writerow(row)


def write_xlsx(records: list[dict], path: Path) -> None:
    """Write Excel (.xlsx) file — siap dibuka di Microsoft Excel / LibreOffice."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import pandas as pd
    except ImportError as e:
        raise ImportError("pandas required for Excel output. pip install pandas openpyxl") from e

    if not records:
        pd.DataFrame().to_excel(path, index=False, engine="openpyxl")
        return

    df = pd.DataFrame(_flatten_records(records))
    # Prefer column order
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
    df = df[cols]
    df.to_excel(path, index=False, engine="openpyxl")


async def run_pipeline(
    input_records: list[dict[str, Any]],
    out_dir: Path,
    timeout: int = 30,
    concurrency: int = 5,
    prefix: str = "dataset",
) -> list[dict[str, Any]]:
    urls = [r["url"] for r in input_records]
    print(f"[*] Scraping {len(urls)} URLs (concurrency={concurrency}, timeout={timeout}s) …")

    results = await scrape_urls(urls, timeout=timeout, max_concurrency=concurrency)

    # Map back by URL (order is preserved by gather)
    url_to_input = {r["url"]: r for r in input_records}
    records = []
    for res in results:
        url = res.get("url")
        inp = url_to_input.get(url, {"url": url, "source_category": "unknown"})
        records.append(build_record(inp, res))

    # Write raw outputs (JSONL + CSV + Excel)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    jsonl_path = out_dir / f"{prefix}_{ts}.jsonl"
    csv_path = out_dir / f"{prefix}_{ts}.csv"
    xlsx_path = out_dir / f"{prefix}_{ts}.xlsx"
    write_jsonl(records, jsonl_path)
    write_csv(records, csv_path)
    write_xlsx(records, xlsx_path)

    ok = sum(1 for r in records if r["scrape_status"] == "success")
    fail = len(records) - ok
    print(f"[+] Done. Success={ok}  Failed={fail}")
    print(f"    JSONL → {jsonl_path}")
    print(f"    CSV   → {csv_path}")
    print(f"    Excel → {xlsx_path}")
    return records


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SCAMGUARD Dataset Collection Pipeline (uses web-scraper-mcp logic)"
    )
    parser.add_argument("--csv", type=str, help="Input CSV with 'url' column")
    parser.add_argument("--json", type=str, help="Input JSON file")
    parser.add_argument(
        "--url",
        action="append",
        dest="urls",
        help="Manual URL (can be repeated)",
    )
    parser.add_argument(
        "--category",
        default="unknown",
        choices=sorted(VALID_CATEGORIES),
        help="Default category for manual URLs",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="data/raw",
        help="Output directory for JSONL/CSV (default: data/raw)",
    )
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--prefix", type=str, default="dataset")
    args = parser.parse_args()

    if not any([args.csv, args.json, args.urls]):
        parser.error("Provide at least one of --csv, --json, or --url")

    records = load_urls(
        csv_path=args.csv,
        json_path=args.json,
        manual_urls=args.urls,
        default_category=args.category,
    )
    if not records:
        print("No valid URLs found.", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Loaded {len(records)} unique URLs")
    out_dir = Path(args.out_dir)
    asyncio.run(
        run_pipeline(
            records,
            out_dir=out_dir,
            timeout=args.timeout,
            concurrency=args.concurrency,
            prefix=args.prefix,
        )
    )


if __name__ == "__main__":
    main()
