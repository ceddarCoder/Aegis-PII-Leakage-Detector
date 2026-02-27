"""
pastebin_scraper.py — Pastebin ingestion layer for Aegis.

Strategy (in order of reliability):
  1. Pastebin Scraping API (https://scrape.pastebin.com/api_scraping.php)
     — requires whitelisted IP or Pastebin Pro account.
  2. Archive page HTML scraping (fallback, may be rate-limited).
  3. Honey-pot list (offline fallback for demo/testing).

The scraping API is the most reliable method and what we prefer.
"""

import re
import time
import logging
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/json,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

_BASE_URL = "https://pastebin.com"
_SCRAPE_API_URL = "https://scrape.pastebin.com/api_scraping.php"
_ARCHIVE_URL = "https://pastebin.com/archive"

# ─────────────────────────────────────────────────────────────
# Internal HTTP helper
# ─────────────────────────────────────────────────────────────

def _get(url: str, params: dict | None = None, timeout: int = 12) -> requests.Response | None:
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
        if resp.status_code == 429:
            logger.warning("Rate limited by Pastebin. Sleeping 30s.")
            time.sleep(30)
            resp = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp
    except requests.exceptions.HTTPError as exc:
        logger.error("HTTP error: %s — %s", exc.response.status_code, url)
        return None
    except requests.exceptions.RequestException as exc:
        logger.error("Request error: %s — %s", exc, url)
        return None


# ─────────────────────────────────────────────────────────────
# Method 1: Official Scraping API
# ─────────────────────────────────────────────────────────────

def _fetch_via_scrape_api(limit: int = 50) -> list[dict] | None:
    """
    Use Pastebin's official scraping API endpoint.
    Returns a list of paste dicts, or None if the endpoint is inaccessible
    (403 = IP not whitelisted).
    """
    resp = _get(_SCRAPE_API_URL, params={"limit": min(limit, 250)})
    if not resp:
        return None

    # API returns 403 with HTML body if IP not whitelisted
    ct = resp.headers.get("Content-Type", "")
    if "html" in ct or resp.status_code == 403:
        logger.info("Pastebin Scrape API requires whitelisted IP. Falling back.")
        return None

    try:
        data = resp.json()
    except Exception:
        logger.warning("Pastebin Scrape API returned non-JSON. Falling back.")
        return None

    pastes = []
    for item in data[:limit]:
        key = item.get("key", "")
        if not key:
            continue
        pastes.append({
            "paste_id": key,
            "url":      f"{_BASE_URL}/{key}",
            "raw_url":  f"{_BASE_URL}/raw/{key}",
            "title":    item.get("title", "Untitled"),
            "syntax":   item.get("syntax", "text"),
            "size":     int(item.get("size", 0)),
            "expire":   item.get("expire", "0"),
            "source":   "scrape_api",
        })

    logger.info("Scrape API returned %d pastes.", len(pastes))
    return pastes


# ─────────────────────────────────────────────────────────────
# Method 2: Archive page HTML scraping
# ─────────────────────────────────────────────────────────────

# Match paste keys in both old (/XXXXXXXX) and new (/XXXXXXXX?source=...) URL formats
_PASTE_KEY_RE = re.compile(r"^/([A-Za-z0-9]{8})(?:\?.*)?$")

# Navigation / non-paste paths to skip
_SKIP_PATHS = {
    "/archive", "/login", "/signup", "/faq", "/tools", "/doc_api",
    "/languages", "/night_mode", "/pro", "/contact", "/dmca",
    "/report-abuse", "/news", "/doc_scraping_api",
    "/doc_privacy_statement", "/doc_cookies_policy",
    "/doc_terms_of_service", "/doc_security_disclosure",
}


def _fetch_via_archive(limit: int = 50) -> list[dict] | None:
    """
    Scrape https://pastebin.com/archive to get recent public paste IDs.
    This is a fallback when the Scraping API is unavailable.

    Handles multiple page layouts defensively:
      - 2024-era: <table class="maintable"> with rows
      - 2025-2026: <a href="/KEY?source=archive"> links in list items
    """
    resp = _get(_ARCHIVE_URL)
    if not resp:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    pastes = []
    seen = set()

    # ── Strategy A: Modern layout (2025-2026) ─────────────────
    # Look for all <a> tags whose href matches /<8chars>?source=...
    for link in soup.find_all("a", href=True):
        href = link["href"]

        # Skip navigation links
        base_path = href.split("?")[0]
        if base_path in _SKIP_PATHS:
            continue
        # Skip language archive links like /archive/python
        if base_path.startswith("/archive/"):
            continue

        m = _PASTE_KEY_RE.match(href)
        if not m:
            continue

        key = m.group(1)
        if key in seen:
            continue
        seen.add(key)

        title = link.get_text(strip=True) or "Untitled"

        pastes.append({
            "paste_id": key,
            "url":      f"{_BASE_URL}/{key}",
            "raw_url":  f"{_BASE_URL}/raw/{key}",
            "title":    title,
            "syntax":   "text",
            "size":     0,
            "expire":   "N/A",
            "source":   "archive_scrape",
        })

        if len(pastes) >= limit:
            break

    # ── Strategy B: Legacy table layout fallback ──────────────
    if not pastes:
        rows = (
            soup.select("table.maintable tbody tr")
            or soup.select("table.maintable tr")
        )
        for row in rows:
            cells = row.find_all("td")
            if not cells:
                continue
            link = cells[0].find("a", href=True)
            if not link:
                continue
            href = link["href"]
            m = _PASTE_KEY_RE.match(href)
            if not m:
                continue
            key = m.group(1)
            if key in seen:
                continue
            seen.add(key)
            syntax = cells[2].get_text(strip=True) if len(cells) > 2 else "text"
            pastes.append({
                "paste_id": key,
                "url":      f"{_BASE_URL}/{key}",
                "raw_url":  f"{_BASE_URL}/raw/{key}",
                "title":    link.get_text(strip=True),
                "syntax":   syntax,
                "size":     0,
                "expire":   "N/A",
                "source":   "archive_scrape",
            })
            if len(pastes) >= limit:
                break

    if not pastes:
        logger.warning("Archive scraper found 0 pastes. Page structure may have changed.")
        return None

    logger.info("Archive scraper found %d pastes.", len(pastes))
    return pastes


# ─────────────────────────────────────────────────────────────
# Method 3: Honey-pot / demo paste list
# ─────────────────────────────────────────────────────────────

# Real public paste IDs for offline/demo use (updated 2026-02)
_DEMO_PASTE_IDS = [
    "QM9dUJUK",
    "Z22PGEq8",
    "u5pc8MJ8",
    "Mqqg16H2",
    "aV9H9xCr",
    "cgGchv3S",
    "0WZrjyqf",
    "YKNJdHdM",
]


def _fetch_demo_list() -> list[dict]:
    pastes = []
    for key in _DEMO_PASTE_IDS:
        pastes.append({
            "paste_id": key,
            "url":      f"{_BASE_URL}/{key}",
            "raw_url":  f"{_BASE_URL}/raw/{key}",
            "title":    "Demo Paste",
            "syntax":   "text",
            "size":     0,
            "expire":   "N/A",
            "source":   "demo_list",
        })
    return pastes


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def get_recent_pastes(limit: int = 30) -> list[dict]:
    """
    Fetch recent public Pastebin pastes.
    Tries scraping API → archive scrape → demo list, in that order.

    Returns a list of paste metadata dicts.
    """
    pastes = _fetch_via_scrape_api(limit)
    if pastes:
        return pastes[:limit]

    pastes = _fetch_via_archive(limit)
    if pastes:
        return pastes[:limit]

    logger.warning("All Pastebin fetch methods failed. Using demo list.")
    return _fetch_demo_list()[:limit]


def fetch_paste_raw(raw_url: str, max_bytes: int = 500_000) -> str | None:
    """
    Download the raw content of a single Pastebin paste.
    Returns None if the paste is inaccessible or exceeds max_bytes.
    """
    resp = _get(raw_url, timeout=10)
    if not resp:
        return None

    # Guard against extremely large pastes
    content = resp.content
    if len(content) > max_bytes:
        logger.info("Paste too large (%d bytes), truncating: %s", len(content), raw_url)
        content = content[:max_bytes]

    try:
        return content.decode("utf-8", errors="replace")
    except Exception:
        return None


def fetch_paste_metadata(paste_id: str) -> dict | None:
    """
    Fetch metadata for a single paste via the scraping API.
    Returns None if inaccessible.
    """
    url = f"https://scrape.pastebin.com/api_scrape_item_meta.php"
    resp = _get(url, params={"i": paste_id})
    if not resp:
        return None
    try:
        return resp.json()
    except Exception:
        return None
