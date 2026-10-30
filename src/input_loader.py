"""
input_loader.py
===============
TAHAP 1 — Load URL lists from CSV, JSON, or manual input.

Expected columns / keys:
  - url            (required)
  - source_category  one of: phishing | legitimate | online_gambling | unknown
  - source         (optional) e.g. "phishtank", "manual", "openphish"
  - notes          (optional)

Categories are kept strictly separate; online_gambling is NEVER auto-mapped
to phishing.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, List, Optional
from urllib.parse import urlparse

VALID_CATEGORIES = frozenset({
    "phishing",
    "legitimate",
    "online_gambling",
    "unknown",
})


def _normalize_category(raw: Optional[str]) -> str:
    if not raw:
        return "unknown"
    cat = str(raw).strip().lower().replace("-", "_").replace(" ", "_")
    if cat in ("legit", "benign", "safe", "good"):
        return "legitimate"
    if cat in ("phish", "phishing_site", "malicious"):
        return "phishing"
    if cat in ("gambling", "judi", "judi_online", "online-gambling"):
        return "online_gambling"
    if cat in VALID_CATEGORIES:
        return cat
    return "unknown"


def _normalize_url(raw: str) -> Optional[str]:
    url = (raw or "").strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        return None
    return url


def load_from_csv(path: str | Path) -> List[dict[str, Any]]:
    """
    Read CSV. Required column: url
    Optional: source_category, source, notes
    """
    path = Path(path)
    records = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "url" not in [c.lower() for c in reader.fieldnames]:
            raise ValueError("CSV must contain a 'url' column")
        # normalise header case
        field_map = {c.lower(): c for c in reader.fieldnames}
        for row in reader:
            url = _normalize_url(row.get(field_map.get("url", "url"), ""))
            if not url:
                continue
            cat_raw = row.get(field_map.get("source_category", "source_category"), "")
            records.append({
                "url": url,
                "source_category": _normalize_category(cat_raw),
                "source": (row.get(field_map.get("source", "source"), "") or "csv").strip(),
                "notes": (row.get(field_map.get("notes", "notes"), "") or "").strip(),
            })
    return records


def load_from_json(path: str | Path) -> List[dict[str, Any]]:
    """
    Accepts either:
      - list of objects
      - object with key "urls" or "data" containing the list
    Each item needs at least "url".
    """
    path = Path(path)
    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict):
        items = data.get("urls") or data.get("data") or data.get("items") or []
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError("JSON must be a list or an object containing a list")

    records = []
    for item in items:
        if isinstance(item, str):
            url = _normalize_url(item)
            if url:
                records.append({
                    "url": url,
                    "source_category": "unknown",
                    "source": "json",
                    "notes": "",
                })
            continue
        if not isinstance(item, dict):
            continue
        url = _normalize_url(item.get("url") or item.get("source_url") or "")
        if not url:
            continue
        records.append({
            "url": url,
            "source_category": _normalize_category(
                item.get("source_category") or item.get("category") or item.get("label")
            ),
            "source": (item.get("source") or "json").strip(),
            "notes": (item.get("notes") or "").strip(),
        })
    return records


def load_manual(urls: Iterable[str], category: str = "unknown", source: str = "manual") -> List[dict[str, Any]]:
    """Load from a plain list of URL strings."""
    cat = _normalize_category(category)
    records = []
    for u in urls:
        url = _normalize_url(u)
        if url:
            records.append({
                "url": url,
                "source_category": cat,
                "source": source,
                "notes": "",
            })
    return records


def load_urls(
    csv_path: Optional[str | Path] = None,
    json_path: Optional[str | Path] = None,
    manual_urls: Optional[Iterable[str]] = None,
    default_category: str = "unknown",
) -> List[dict[str, Any]]:
    """
    Convenience aggregator. Later sources override earlier duplicates by URL.
    """
    seen: dict[str, dict] = {}
    for loader, arg in (
        (load_from_csv, csv_path),
        (load_from_json, json_path),
    ):
        if arg:
            for rec in loader(arg):
                seen[rec["url"]] = rec

    if manual_urls:
        for rec in load_manual(manual_urls, category=default_category):
            seen[rec["url"]] = rec

    return list(seen.values())
