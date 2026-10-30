"""
scraper_core.py
===============
Core web scraping logic extracted and adapted from the official
web-scraper-mcp repository (https://github.com/Rumblingb/web-scraper-mcp).

This module re-uses the exact same extraction functions (regex-based,
zero heavy dependencies) so that the SCAMGUARD pipeline stays faithful
to the original MCP tools:

  - scrape_url(url, selector?)
  - scrape_urls(urls[])
  - extract_emails(url)
  - extract_links(url, domain_filter?)

Additional helpers for headings (H1/H2/H3) are provided by calling the
same selector logic that the original server already supports.
"""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx

# ─── Constants (identical to original server.py) ─────────────────────────────

SELF_CLOSING_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})

DEFAULT_TIMEOUT = 30

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; WebScraperMCP/1.0; "
        "+https://github.com/Rumblingb/web-scraper-mcp)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Private / reserved networks that must never be contacted (SSRF protection)
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


# ─── HTML Entity Decoding (identical) ────────────────────────────────────────

_HTML_ENTITIES = {
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
    "&#x27;": "'",
    "&#x2F;": "/",
    "&nbsp;": " ",
    "&mdash;": "—",
    "&ndash;": "–",
    "&hellip;": "…",
    "&copy;": "©",
    "&reg;": "®",
    "&trade;": "™",
    "&bull;": "•",
    "&middot;": "·",
}


def decode_entities(text: str) -> str:
    for entity, char in _HTML_ENTITIES.items():
        text = text.replace(entity, char)
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    text = re.sub(r"&#x([0-9a-fA-F]+);", lambda m: chr(int(m.group(1), 16)), text)
    return text


# ─── Text Extraction (identical) ─────────────────────────────────────────────

def extract_title(html: str) -> Optional[str]:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    if m:
        return decode_entities(m.group(1).strip())
    return None


def extract_meta_description(html: str) -> Optional[str]:
    patterns = [
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']',
        r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']description["\']',
    ]
    for pattern in patterns:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            return decode_entities(m.group(1).strip())
    return None



def extract_canonical(html: str) -> Optional[str]:
    m = re.search(
        r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
        html, re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']',
            html, re.IGNORECASE,
        )
    return m.group(1).strip() if m else None


def extract_og_tags(html: str) -> dict[str, str]:
    """Extract Open Graph meta tags (og:title, og:description, og:site_name, etc.)."""
    og: dict[str, str] = {}
    patterns = [
        r'<meta[^>]+property=["\']og:([^"\']+)["\'][^>]+content=["\']([^"\']*)["\']',
        r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']og:([^"\']+)["\']',
    ]
    for i, pattern in enumerate(patterns):
        for m in re.finditer(pattern, html, re.IGNORECASE):
            if i == 0:
                key, val = m.group(1).lower(), m.group(2)
            else:
                val, key = m.group(1), m.group(2).lower()
            if key and val and key not in og:
                og[key] = decode_entities(val.strip())
    return og


def extract_keywords(html: str) -> Optional[str]:
    patterns = [
        r'<meta[^>]+name=["\']keywords["\'][^>]+content=["\']([^"\']*)["\']',
        r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']keywords["\']',
    ]
    for pattern in patterns:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            return decode_entities(m.group(1).strip())
    return None


def extract_text_content(html: str) -> str:
    text = re.sub(
        r"<(script|style|noscript)[^>]*>.*?</\1\s*>",
        "",
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    text = re.sub(r"<[^>]+>", " ", text)
    text = decode_entities(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ─── Link Extraction (identical) ─────────────────────────────────────────────

def extract_links(html: str, base_url: str) -> list[dict]:
    links = []
    seen = set()
    for m in re.finditer(
        r'<a[^>]+href=["\']([^"\']*)["\']',
        html,
        re.IGNORECASE,
    ):
        href = m.group(1).strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        abs_url = urljoin(base_url, href)
        if abs_url in seen:
            continue
        seen.add(abs_url)

        remaining = html[m.end() :]
        text_m = re.match(r"[^<]*(?:<(?!a\b)[^>]*>)*([^<]*)", remaining, re.IGNORECASE)
        text = ""
        if text_m:
            raw = re.sub(r"<[^>]+>", " ", text_m.group(1)).strip()
            text = decode_entities(raw)

        links.append({
            "href": href,
            "absolute_url": abs_url,
            "text": text,
        })
    return links


def extract_links_filtered(
    html: str, base_url: str, domain_filter: str
) -> list[dict]:
    links = extract_links(html, base_url)
    domain_lower = domain_filter.lower()
    return [
        link
        for link in links
        if domain_lower in urlparse(link["absolute_url"]).netloc.lower()
    ]


# ─── Image Extraction (identical) ────────────────────────────────────────────

def extract_images(html: str, base_url: str) -> list[dict]:
    images = []
    seen = set()
    for m in re.finditer(
        r'<img[^>]+src=["\']([^"\']*)["\']',
        html,
        re.IGNORECASE,
    ):
        src = m.group(1).strip()
        if not src:
            continue
        abs_url = urljoin(base_url, src)
        if abs_url in seen:
            continue
        seen.add(abs_url)

        tag = html[m.start() : m.end()]
        alt_m = re.search(r'alt=["\']([^"\']*)["\']', tag, re.IGNORECASE)
        alt = decode_entities(alt_m.group(1)) if alt_m else ""

        images.append({
            "src": src,
            "absolute_url": abs_url,
            "alt": alt,
        })
    return images


# ─── Heading Extraction (uses same regex style as original) ──────────────────

def extract_headings(html: str) -> dict[str, list[str]]:
    """Extract H1, H2, H3 texts. Compatible with selector-based approach of MCP."""
    result: dict[str, list[str]] = {"h1": [], "h2": [], "h3": []}
    for level in ("h1", "h2", "h3"):
        pattern = re.compile(
            rf"<{level}[^>]*>(.*?)</{level}\s*>",
            re.DOTALL | re.IGNORECASE,
        )
        for m in pattern.finditer(html):
            raw = re.sub(r"<[^>]+>", " ", m.group(1))
            text = decode_entities(re.sub(r"\s+", " ", raw).strip())
            if text:
                result[level].append(text)
    return result


# ─── SSRF / Safety Guards ────────────────────────────────────────────────────

def is_safe_url(url: str) -> tuple[bool, str]:
    """
    Reject non-http(s), localhost, private IPs, and link-local addresses.
    Returns (ok, reason).
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"invalid URL: {e}"

    if parsed.scheme not in ("http", "https"):
        return False, f"scheme not allowed: {parsed.scheme}"

    hostname = parsed.hostname
    if not hostname:
        return False, "missing hostname"

    if hostname.lower() in ("localhost", "localhost.localdomain"):
        return False, "localhost not allowed"

    # Resolve and check every address
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        return False, f"DNS resolution failed: {e}"

    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        for net in _PRIVATE_NETWORKS:
            if ip in net:
                return False, f"private/reserved IP not allowed: {ip}"
    return True, "ok"


# ─── HTTP Fetch (identical + safety) ─────────────────────────────────────────

async def fetch_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    ok, reason = is_safe_url(url)
    if not ok:
        raise ValueError(f"URL blocked by safety policy: {reason}")

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
        limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    ) as client:
        resp = await client.get(url, headers=DEFAULT_HEADERS)
        resp.raise_for_status()
        # Basic content-type guard
        ctype = resp.headers.get("content-type", "").lower()
        if "text/html" not in ctype and "application/xhtml" not in ctype and "text/plain" not in ctype:
            # Still return body but caller can decide
            pass
        return resp.text


# ─── High-level helpers that mirror MCP tools ────────────────────────────────

async def scrape_url(
    url: str,
    selector: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """
    Mirror of MCP tool `scrape_url`.
    When selector is None → full page (title, meta, text, links, images, headings).
    When selector is given → element list (same as original).
    """
    html = await fetch_url(url, timeout=timeout)

    if selector:
        # Minimal selector support: we reuse the original find logic pattern
        # For pipeline we mainly need full page, so keep simple tag extraction
        # Full selector engine is in the original server.py
        elements = []
        tag_match = re.match(r"^([a-zA-Z0-9]+)", selector.strip())
        if tag_match:
            tag = tag_match.group(1)
            pattern = re.compile(rf"<{re.escape(tag)}([^>]*)>(.*?)</{re.escape(tag)}\s*>",
                                 re.DOTALL | re.IGNORECASE)
            for m in pattern.finditer(html):
                text = decode_entities(re.sub(r"<[^>]+>", " ", m.group(2)))
                text = re.sub(r"\s+", " ", text).strip()
                elements.append({"tag": tag, "text": text})
        return {
            "url": url,
            "selector": selector,
            "elements": elements,
            "success": True,
        }

    title = extract_title(html)
    meta = extract_meta_description(html)
    text_content = extract_text_content(html)
    links = extract_links(html, url)
    images = extract_images(html, url)
    headings = extract_headings(html)
    og = extract_og_tags(html)
    canonical = extract_canonical(html)
    keywords = extract_keywords(html)

    return {
        "url": url,
        "title": title,
        "meta_description": meta,
        "text_content": text_content,
        "links": links,
        "images": images,
        "headings": headings,
        "og_tags": og,
        "canonical_url": canonical,
        "keywords": keywords,
        "html_length": len(html),
        "success": True,
    }


async def scrape_urls(
    urls: list[str],
    timeout: int = DEFAULT_TIMEOUT,
    max_concurrency: int = 5,
) -> list[dict[str, Any]]:
    """
    Mirror of MCP tool `scrape_urls` with concurrency limit and safety.
    Returns richer data than the original batch tool for dataset purposes.
    """
    sem = asyncio.Semaphore(max_concurrency)

    async def _one(u: str) -> dict[str, Any]:
        async with sem:
            try:
                data = await scrape_url(u, timeout=timeout)
                data["success"] = True
                return data
            except Exception as e:
                return {
                    "url": u,
                    "success": False,
                    "error": str(e),
                }

    return await asyncio.gather(*[_one(u) for u in urls])


def scrape_url_sync(url: str, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """Synchronous convenience wrapper."""
    return asyncio.run(scrape_url(url, timeout=timeout))
