"""
github_scraper.py — GitHub ingestion layer for Aegis.

Uses the Git Trees API (/git/trees?recursive=1) instead of the Contents API.

WHY: The Contents API returns download_url with a baked-in commit SHA
(e.g. raw.githubusercontent.com/owner/repo/abc123/file.py). GitHub's CDN
caches this aggressively, so newly committed files or changes don't show up
until the cache expires (can be minutes to hours).

The Trees API returns file paths relative to the repo root. We then build
raw.githubusercontent.com URLs using the BRANCH NAME, not a SHA, so we
always get the current HEAD content. Cache-Control: no-cache headers are
also sent to prevent CDN serving stale responses.
"""

import os
import time
import logging
from pathlib import PurePosixPath

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "Aegis-PII-Scanner/1.0",
    "Cache-Control": "no-cache",          # ← bust GitHub CDN cache
    "Pragma": "no-cache",
    **({"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}),
}

# Same headers but for raw content downloads
RAW_HEADERS = {
    "User-Agent": "Aegis-PII-Scanner/1.0",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    **({"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}),
}

TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".env", ".env.example", ".env.local", ".env.dev", ".env.prod",
    ".md", ".txt", ".csv", ".sql", ".sh", ".bash", ".zsh",
    ".xml", ".html", ".htm", ".log",
    ".rb", ".php", ".java", ".go", ".rs", ".cs",
    ".properties", ".gradle", ".pom", ".tf", ".tfvars",
}

OCR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".bmp", ".tiff", ".webp"}

MAX_FILE_SIZE_BYTES  = 500_000   # 500 KB — skip large files
MAX_TREE_FILE_SIZE   = 1_000_000 # 1 MB — skip in tree listing

# Directories to always skip
_SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "__pycache__",
    ".venv", "venv", ".mypy_cache", ".pytest_cache", "coverage",
    "vendor", "target", "bin", "obj", ".next", ".nuxt",
    "static", "assets", "public", "fonts", "images",
}


# ─────────────────────────────────────────────────────────────
# HTTP helper
# ─────────────────────────────────────────────────────────────

def _get(url: str, params: dict | None = None, raw: bool = False, retries: int = 3) -> requests.Response | None:
    hdrs = RAW_HEADERS if raw else HEADERS
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=hdrs, params=params, timeout=15)
            if resp.status_code in (429, 403):
                retry_after = int(resp.headers.get("Retry-After", 30))
                logger.warning("Rate limited. Sleeping %ds.", retry_after)
                time.sleep(retry_after)
                continue
            if resp.status_code == 404:
                return None   # caller handles 404
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as exc:
            wait = 2 ** attempt
            logger.warning("Request error (%s). Retry in %ds.", exc, wait)
            time.sleep(wait)
    return None


# ─────────────────────────────────────────────────────────────
# Resolve the real default branch + latest commit SHA
# ─────────────────────────────────────────────────────────────

def get_repo_info(owner_repo: str) -> dict:
    """
    Fetch repo metadata: default_branch and latest HEAD sha.
    Returns {'default_branch': str, 'head_sha': str}
    """
    url  = f"https://api.github.com/repos/{owner_repo}"
    resp = _get(url)
    if not resp:
        return {"default_branch": "main", "head_sha": ""}

    data   = resp.json()
    branch = data.get("default_branch", "main")

    # Get the latest commit SHA on that branch
    ref_url  = f"https://api.github.com/repos/{owner_repo}/git/ref/heads/{branch}"
    ref_resp = _get(ref_url)
    sha = ""
    if ref_resp:
        sha = ref_resp.json().get("object", {}).get("sha", "")

    logger.info("Repo %s → branch=%s sha=%s", owner_repo, branch, sha[:8] if sha else "?")
    return {"default_branch": branch, "head_sha": sha}


# ─────────────────────────────────────────────────────────────
# File tree via Git Trees API (always reflects latest commit)
# ─────────────────────────────────────────────────────────────

def get_all_files(
    owner_repo: str,
    branch: str = "",          # empty = auto-detect from repo info
) -> list[dict]:
    """
    Fetch the full file tree using the Git Trees API with recursive=1.
    This always returns the current HEAD of the branch — no stale cache.

    Returns list of:
      {'path', 'name', 'size', 'route', 'raw_url'}
    where raw_url is a branch-name-based URL (not SHA-based).
    """
    # Auto-detect branch if not given
    if not branch:
        info   = get_repo_info(owner_repo)
        branch = info["default_branch"]

    # Resolve branch → SHA (required by Trees API)
    ref_url  = f"https://api.github.com/repos/{owner_repo}/git/ref/heads/{branch}"
    ref_resp = _get(ref_url)

    if not ref_resp:
        # Try master as fallback
        if branch == "main":
            logger.info("Branch 'main' not found, trying 'master'.")
            return get_all_files(owner_repo, "master")
        logger.error("Could not resolve branch '%s' for %s", branch, owner_repo)
        return []

    tree_sha = ref_resp.json().get("object", {}).get("sha", "")
    if not tree_sha:
        logger.error("No SHA found for branch '%s'", branch)
        return []

    # Fetch the full recursive tree
    tree_url  = f"https://api.github.com/repos/{owner_repo}/git/trees/{tree_sha}"
    tree_resp = _get(tree_url, params={"recursive": "1"})
    if not tree_resp:
        return []

    tree_data = tree_resp.json()

    if tree_data.get("truncated"):
        logger.warning(
            "Tree for %s is truncated (>100k files). Only partial results returned.",
            owner_repo,
        )

    files = []
    for item in tree_data.get("tree", []):
        if item.get("type") != "blob":
            continue

        path = item.get("path", "")
        size = item.get("size", 0)

        # Skip anything inside a noise directory
        parts = path.split("/")
        if any(p.lower() in _SKIP_DIRS for p in parts[:-1]):
            continue

        classified = _classify_path(path, size, owner_repo, branch)
        if classified["route"] != "skip":
            files.append(classified)

    logger.info("Tree API returned %d scannable files for %s@%s", len(files), owner_repo, branch)
    return files


def _classify_path(path: str, size: int, owner_repo: str, branch: str) -> dict:
    ext  = PurePosixPath(path).suffix.lower()
    name = PurePosixPath(path).name

    if size > MAX_TREE_FILE_SIZE:
        route = "skip"
    elif ext in TEXT_EXTENSIONS:
        route = "text"
    elif ext in OCR_EXTENSIONS:
        route = "ocr"
    else:
        route = "skip"

    # Build raw URL using BRANCH NAME — always points to current HEAD
    # Format: https://raw.githubusercontent.com/owner/repo/BRANCH/path
    raw_url = f"https://raw.githubusercontent.com/{owner_repo}/{branch}/{path}"

    return {
        "path":    path,
        "name":    name,
        "size":    size,
        "route":   route,
        "raw_url": raw_url,
        # Keep download_url as alias so existing callers work
        "download_url": raw_url,
    }


# ─────────────────────────────────────────────────────────────
# File content fetching — always bypasses CDN cache
# ─────────────────────────────────────────────────────────────

def fetch_file_content(download_url: str) -> str | None:
    """
    Download raw file content as UTF-8 text.
    Uses Cache-Control: no-cache to always get the latest version.
    """
    if not download_url:
        return None

    resp = _get(download_url, raw=True)
    if not resp:
        return None

    content_len = len(resp.content)
    if content_len > MAX_FILE_SIZE_BYTES:
        logger.info("Skipping large file (%d bytes): %s", content_len, download_url)
        return None

    try:
        return resp.content.decode("utf-8", errors="replace")
    except Exception:
        return None


def fetch_file_bytes(download_url: str) -> bytes | None:
    """Download raw file bytes — used for OCR routing."""
    if not download_url:
        return None
    resp = _get(download_url, raw=True)
    return resp.content if resp else None


# ─────────────────────────────────────────────────────────────
# Repo listing
# ─────────────────────────────────────────────────────────────

def list_user_public_repos(username: str, max_repos: int = 20) -> list[dict]:
    """
    Return public repos for a user, sorted by most recently updated.
    Each dict: {'full_name', 'name', 'html_url', 'default_branch', 'size_kb'}
    """
    url   = f"https://api.github.com/users/{username}/repos"
    repos: list[dict] = []
    page  = 1

    while len(repos) < max_repos:
        resp = _get(url, params={
            "per_page": 100, "page": page,
            "sort": "updated", "direction": "desc",
            "type": "public",
        })
        if not resp:
            break

        page_data = resp.json()
        if not page_data:
            break

        for repo in page_data:
            if not repo.get("private", False):
                repos.append({
                    "full_name":      repo["full_name"],
                    "name":           repo["name"],
                    "html_url":       repo["html_url"],
                    "default_branch": repo.get("default_branch", "main"),
                    "size_kb":        repo.get("size", 0),
                })
            if len(repos) >= max_repos:
                break

        if 'rel="next"' not in resp.headers.get("Link", ""):
            break
        page += 1

    return repos[:max_repos]


# ─────────────────────────────────────────────────────────────
# Convenience helpers
# ─────────────────────────────────────────────────────────────

def get_repo_text_files(owner_repo: str, branch: str = "") -> list[dict]:
    return [f for f in get_all_files(owner_repo, branch) if f["route"] == "text"]


def get_repo_ocr_files(owner_repo: str, branch: str = "") -> list[dict]:
    return [f for f in get_all_files(owner_repo, branch) if f["route"] == "ocr"]