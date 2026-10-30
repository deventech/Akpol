"""
cleaning.py
===========
TAHAP 4 — Data Cleaning & Deduplication

- Remove duplicate records (by source_url)
- Clean control characters / excessive whitespace from text fields
- Handle missing values (keep structure, mark empty)
- Split successful vs failed scrapes
- Basic completeness check
- NEVER invent content; never drop important textual evidence
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _clean_text(val: Optional[str], max_len: Optional[int] = None) -> Optional[str]:
    if val is None:
        return None
    if not isinstance(val, str):
        val = str(val)
    # Remove control chars except newline/tab
    val = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", val)
    # Collapse whitespace
    val = re.sub(r"[ \t]+", " ", val)
    val = re.sub(r"\n{3,}", "\n\n", val)
    val = val.strip()
    if max_len and len(val) > max_len:
        val = val[:max_len]
    return val if val else None


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def load_any(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return load_jsonl(path)
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
        # Expand flattened columns if present
        records = df.to_dict(orient="records")
        for r in records:
            if "headings_json" in r and isinstance(r["headings_json"], str):
                try:
                    r["headings"] = json.loads(r["headings_json"])
                except Exception:
                    r["headings"] = {}
            if "links_json" in r and isinstance(r["links_json"], str):
                try:
                    r["links"] = json.loads(r["links_json"])
                except Exception:
                    r["links"] = []
        return records
    raise ValueError(f"Unsupported format: {path.suffix}")


def clean_records(records: list[dict[str, Any]]) -> dict[str, list[dict]]:
    """
    Returns dict with keys:
      all_cleaned, success, failed, incomplete
    """
    seen_urls: set[str] = set()
    cleaned: list[dict] = []
    success: list[dict] = []
    failed: list[dict] = []
    incomplete: list[dict] = []

    for rec in records:
        url = (rec.get("source_url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        new = dict(rec)
        new["source_url"] = url
        new["page_title"] = _clean_text(rec.get("page_title"), max_len=500)
        new["meta_description"] = _clean_text(rec.get("meta_description"), max_len=1000)
        new["extracted_text"] = _clean_text(rec.get("extracted_text"), max_len=100_000)
        new["source_category"] = (rec.get("source_category") or "unknown").lower()
        new["scrape_status"] = (rec.get("scrape_status") or "unknown").lower()

        # Pastikan risk_level / risk_label ada (untuk file lama yang belum punya)
        cat = new["source_category"]
        risk_map = {
            "legitimate": (0, "aman"),
            "unknown": (1, "ragu-ragu"),
            "online_gambling": (1, "ragu-ragu"),
            "phishing": (2, "tidak aman"),
        }
        if "risk_level" not in new or new.get("risk_level") is None or str(new.get("risk_level")) == "nan":
            new["risk_level"], new["risk_label"] = risk_map.get(cat, (1, "ragu-ragu"))
        else:
            try:
                new["risk_level"] = int(float(new["risk_level"]))
            except (TypeError, ValueError):
                new["risk_level"], new["risk_label"] = risk_map.get(cat, (1, "ragu-ragu"))
            if not new.get("risk_label") or str(new.get("risk_label")) == "nan":
                new["risk_label"] = risk_map.get(cat, (1, "ragu-ragu"))[1]

        # headings may be dict or already string
        headings = rec.get("headings")
        if isinstance(headings, str):
            try:
                headings = json.loads(headings)
            except Exception:
                headings = {}
        if not isinstance(headings, dict):
            headings = {}
        # clean each heading list
        clean_h = {}
        for k in ("h1", "h2", "h3"):
            vals = headings.get(k) or []
            clean_h[k] = [_clean_text(v, 300) for v in vals if _clean_text(v, 300)]
        new["headings"] = clean_h

        cleaned.append(new)

        if new["scrape_status"] == "success":
            success.append(new)
            # completeness heuristic
            if not new.get("page_title") and not new.get("extracted_text"):
                incomplete.append(new)
        else:
            failed.append(new)

    return {
        "all_cleaned": cleaned,
        "success": success,
        "failed": failed,
        "incomplete": incomplete,
    }


def write_outputs(groups: dict[str, list], out_dir: Path, prefix: str = "cleaned") -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    def _write(name: str, data: list[dict]) -> None:
        if not data:
            return
        jsonl = out_dir / f"{prefix}_{name}.jsonl"
        csv_p = out_dir / f"{prefix}_{name}.csv"
        xlsx_p = out_dir / f"{prefix}_{name}.xlsx"
        with jsonl.open("w", encoding="utf-8") as f:
            for r in data:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        # Flatten nested fields for tabular formats
        rows = []
        for r in data:
            row = {k: v for k, v in r.items() if k not in ("headings", "links")}
            row["headings_json"] = json.dumps(r.get("headings") or {}, ensure_ascii=False)
            row["links_json"] = json.dumps(r.get("links") or [], ensure_ascii=False)
            row["images_json"] = json.dumps(r.get("images") or [], ensure_ascii=False)
            rows.append(row)
        df = pd.DataFrame(rows)
        df.to_csv(csv_p, index=False, encoding="utf-8")
        df.to_excel(xlsx_p, index=False, engine="openpyxl")
        print(f"  {name:12} → {jsonl.name} / {csv_p.name} / {xlsx_p.name}  ({len(data)} rows)")

    print(f"[+] Writing cleaned datasets to {out_dir}")
    for key in ("all_cleaned", "success", "failed", "incomplete"):
        _write(key, groups[key])


def main() -> None:
    parser = argparse.ArgumentParser(description="SCAMGUARD Dataset Cleaning")
    parser.add_argument("input", type=str, help="Raw JSONL or CSV file")
    parser.add_argument(
        "--out-dir",
        type=str,
        default="data/cleaned",
        help="Output directory",
    )
    parser.add_argument("--prefix", type=str, default="cleaned")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Loading {path}")
    records = load_any(path)
    print(f"[*] {len(records)} records loaded")

    groups = clean_records(records)
    print(
        f"[*] After dedup: {len(groups['all_cleaned'])} unique  |  "
        f"success={len(groups['success'])}  failed={len(groups['failed'])}  "
        f"incomplete={len(groups['incomplete'])}"
    )

    write_outputs(groups, Path(args.out_dir), prefix=args.prefix)
    print("[+] Cleaning finished.")


if __name__ == "__main__":
    main()
