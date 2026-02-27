"""
social_media_scraper.py — Aegis Social Media Scraper

Scrapes public profile bio/info and recent posts/tweets for:
  - Twitter/X   (via nitter public instance fallback)
  - Reddit      (via Reddit's public JSON API — no key required)
  - LinkedIn    (via public profile page scraping)

All scraping targets only PUBLIC data. No authentication required.

Returns list of dicts:
  {
    "platform":    "twitter" | "reddit" | "linkedin",
    "username":    str,
    "post_id":     str,
    "content":     str,   # raw text to scan
    "url":         str,
    "content_type": "post" | "bio",
  }
"""

import re
import time
import logging
import requests
from bs4 import BeautifulSoup
from backend.ocr_engine import get_ocr_engine


logger = logging.getLogger(__name__)

# ── Shared HTTP session ───────────────────────────────────────────────────────

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
})

_DEFAULT_TIMEOUT = 15


async def scrape_reddit_profile_async(username, max_posts=25, ocr_enabled=False):
    ocr = get_ocr_engine()
    # ... fetch posts
    for post in posts:
        # ... existing text extraction
        if ocr_enabled and post.get('url') and post['url'].lower().endswith(('.jpg','.jpeg','.png','.webp')):
            ocr_text = await ocr.extract_text_from_url_async(post['url'])
            if ocr_text:
                results.append({
                    "platform": "reddit",
                    "username": username,
                    "post_id": f"{post['id']}_img",
                    "content": ocr_text,
                    "url": post['url'],
                    "content_type": "image_ocr",
                })
    return results

def _get(url: str, **kwargs) -> requests.Response | None:
    """Safe GET with timeout and error handling."""
    try:
        resp = _SESSION.get(url, timeout=_DEFAULT_TIMEOUT, **kwargs)
        resp.raise_for_status()
        return resp
    except requests.RequestException as exc:
        logger.warning("GET %s failed: %s", url, exc)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# Twitter / X  — via Nitter public instances (no auth required)
# ══════════════════════════════════════════════════════════════════════════════

# Multiple public Nitter instances for resilience
_NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
]


def _nitter_get(path: str) -> requests.Response | None:
    """Try each Nitter instance until one responds."""
    for base in _NITTER_INSTANCES:
        resp = _get(f"{base}{path}")
        if resp is not None:
            return resp
        time.sleep(0.3)
    return None


def scrape_twitter_profile(username: str, max_posts: int = 20) -> list[dict]:
    """
    Scrape public Twitter/X profile bio and recent tweets via Nitter.

    Args:
        username:  Twitter handle (with or without @)
        max_posts: Maximum number of tweets to return

    Returns:
        List of content dicts with 'bio' and 'post' entries.
    """
    username = username.lstrip("@").strip()
    results: list[dict] = []

    # ── Profile / Bio ─────────────────────────────────────────────────────────
    resp = _nitter_get(f"/{username}")
    if resp is None:
        logger.error("Twitter: could not reach any Nitter instance for @%s", username)
        return results

    soup = BeautifulSoup(resp.text, "html.parser")

    # Bio
    bio_tag = soup.select_one(".profile-bio")
    if bio_tag:
        bio_text = bio_tag.get_text(separator=" ", strip=True)
        if bio_text:
            results.append({
                "platform":     "twitter",
                "username":     username,
                "post_id":      f"{username}_bio",
                "content":      bio_text,
                "url":          f"https://twitter.com/{username}",
                "content_type": "bio",
            })

    # Display name + location (often PII-rich)
    name_tag = soup.select_one(".profile-card-fullname")
    loc_tag  = soup.select_one(".profile-location")
    website_tag = soup.select_one(".profile-website")

    extra_parts = []
    if name_tag:
        extra_parts.append(name_tag.get_text(strip=True))
    if loc_tag:
        extra_parts.append(loc_tag.get_text(strip=True))
    if website_tag:
        extra_parts.append(website_tag.get_text(strip=True))

    if extra_parts:
        results.append({
            "platform":     "twitter",
            "username":     username,
            "post_id":      f"{username}_profile_meta",
            "content":      " | ".join(extra_parts),
            "url":          f"https://twitter.com/{username}",
            "content_type": "bio",
        })

    # ── Tweets ────────────────────────────────────────────────────────────────
    tweet_tags = soup.select(".timeline-item .tweet-content")
    for i, tag in enumerate(tweet_tags[:max_posts]):
        text = tag.get_text(separator=" ", strip=True)
        if not text:
            continue

        # Try to extract tweet ID from nearest link
        link_tag = tag.find_parent(".timeline-item")
        tweet_url = f"https://twitter.com/{username}"
        if link_tag:
            a_tag = link_tag.select_one("a.tweet-link")
            if a_tag and a_tag.get("href"):
                href = a_tag["href"]
                tweet_url = f"https://twitter.com{href}" if href.startswith("/") else href
                tweet_id  = href.rstrip("/").split("/")[-1]
            else:
                tweet_id = f"tweet_{i}"
        else:
            tweet_id = f"tweet_{i}"

        results.append({
            "platform":     "twitter",
            "username":     username,
            "post_id":      tweet_id,
            "content":      text,
            "url":          tweet_url,
            "content_type": "post",
        })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# Reddit  — public JSON API (no key required)
# ══════════════════════════════════════════════════════════════════════════════

_REDDIT_BASE = "https://www.reddit.com"
_REDDIT_HEADERS = {
    "User-Agent": "Aegis-PII-Scanner/1.0 (educational demo; contact: demo@example.com)"
}


def scrape_reddit_profile(username: str, max_posts: int = 25) -> list[dict]:
    """
    Scrape public Reddit profile: about info and recent posts/comments.

    Args:
        username:  Reddit username (with or without u/)
        max_posts: Maximum number of posts+comments to return

    Returns:
        List of content dicts.
    """
    username = re.sub(r"^u/", "", username).strip()
    results: list[dict] = []

    # ── About / Bio ───────────────────────────────────────────────────────────
    about_url = f"{_REDDIT_BASE}/user/{username}/about.json"
    resp = _get(about_url, headers=_REDDIT_HEADERS)
    if resp is None:
        logger.error("Reddit: failed to fetch profile for u/%s", username)
        return results

    try:
        data = resp.json().get("data", {})
    except Exception:
        data = {}

    subreddit = data.get("subreddit", {})
    bio_parts = []

    public_desc = subreddit.get("public_description", "").strip()
    if public_desc:
        bio_parts.append(public_desc)

    display_name = subreddit.get("display_name_prefixed", "").strip()
    if display_name:
        bio_parts.append(display_name)

    if bio_parts:
        results.append({
            "platform":     "reddit",
            "username":     username,
            "post_id":      f"{username}_bio",
            "content":      " | ".join(bio_parts),
            "url":          f"https://reddit.com/user/{username}",
            "content_type": "bio",
        })

    # ── Recent submissions (posts) ────────────────────────────────────────────
    posts_url = f"{_REDDIT_BASE}/user/{username}/submitted.json?limit={max_posts}"
    resp = _get(posts_url, headers=_REDDIT_HEADERS)
    if resp:
        try:
            children = resp.json().get("data", {}).get("children", [])
        except Exception:
            children = []

        for child in children[:max_posts]:
            post = child.get("data", {})
            title    = post.get("title", "")
            selftext = post.get("selftext", "")
            combined = f"{title} {selftext}".strip()

            if combined:
                results.append({
                    "platform":     "reddit",
                    "username":     username,
                    "post_id":      post.get("id", "unknown"),
                    "content":      combined,
                    "url":          f"https://reddit.com{post.get('permalink', '')}",
                    "content_type": "post",
                })

        time.sleep(1.0)  # Reddit rate-limit courtesy

    # ── Recent comments ───────────────────────────────────────────────────────
    comments_url = f"{_REDDIT_BASE}/user/{username}/comments.json?limit={max_posts}"
    resp = _get(comments_url, headers=_REDDIT_HEADERS)
    if resp:
        try:
            children = resp.json().get("data", {}).get("children", [])
        except Exception:
            children = []

        remaining = max_posts - len(results)
        for child in children[:remaining]:
            comment = child.get("data", {})
            body = comment.get("body", "").strip()
            if body and body != "[deleted]" and body != "[removed]":
                results.append({
                    "platform":     "reddit",
                    "username":     username,
                    "post_id":      comment.get("id", "unknown"),
                    "content":      body,
                    "url":          f"https://reddit.com{comment.get('permalink', '')}",
                    "content_type": "post",
                })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# LinkedIn  — public profile scraping (no auth)
# ══════════════════════════════════════════════════════════════════════════════

def scrape_linkedin_profile(username: str, max_posts: int = 15) -> list[dict]:
    """
    Scrape public LinkedIn profile bio/about section and recent activity.

    Note: LinkedIn aggressively blocks scrapers. This targets only the
    public (logged-out) profile page which shows limited info.
    Activity/posts are scraped from the public activity feed if accessible.

    Args:
        username:  LinkedIn profile slug (e.g. 'john-doe-123abc')
        max_posts: Maximum activity items to return

    Returns:
        List of content dicts.
    """
    username = username.strip().lstrip("/")
    # Normalize: strip full URL if pasted
    username = re.sub(r"^.*linkedin\.com/in/", "", username).strip("/")

    results: list[dict] = []
    profile_url = f"https://www.linkedin.com/in/{username}/"

    # LinkedIn requires specific headers to serve public profile HTML
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    resp = _get(profile_url, headers=headers)
    if resp is None:
        logger.error("LinkedIn: failed to fetch profile for %s", username)
        return results

    soup = BeautifulSoup(resp.text, "html.parser")

    # ── Name ──────────────────────────────────────────────────────────────────
    name_candidates = [
        soup.select_one("h1.top-card-layout__title"),
        soup.select_one("h1.text-heading-xlarge"),
        soup.select_one("h1"),
    ]
    name_text = ""
    for tag in name_candidates:
        if tag:
            name_text = tag.get_text(strip=True)
            break

    # ── Headline ──────────────────────────────────────────────────────────────
    headline_candidates = [
        soup.select_one(".top-card-layout__headline"),
        soup.select_one(".text-body-medium.break-words"),
    ]
    headline_text = ""
    for tag in headline_candidates:
        if tag:
            headline_text = tag.get_text(strip=True)
            break

    # ── Location ──────────────────────────────────────────────────────────────
    loc_candidates = [
        soup.select_one(".top-card__subline-item"),
        soup.select_one(".not-first-middot span"),
        soup.select_one("[class*='location']"),
    ]
    loc_text = ""
    for tag in loc_candidates:
        if tag:
            loc_text = tag.get_text(strip=True)
            break

    # ── About / Summary ───────────────────────────────────────────────────────
    about_candidates = [
        soup.select_one(".summary"),
        soup.select_one("section.summary div.core-section-container__content"),
        soup.select_one("[class*='about'] p"),
    ]
    about_text = ""
    for tag in about_candidates:
        if tag:
            about_text = tag.get_text(separator=" ", strip=True)
            break

    # Combine all bio fields
    bio_parts = [p for p in [name_text, headline_text, loc_text, about_text] if p]
    if bio_parts:
        results.append({
            "platform":     "linkedin",
            "username":     username,
            "post_id":      f"{username}_bio",
            "content":      " | ".join(bio_parts),
            "url":          profile_url,
            "content_type": "bio",
        })

    # ── Experience / Education (public sections) ──────────────────────────────
    # These often contain real names, company names, dates
    exp_sections = soup.select("section.experience-section li, section.education-section li")
    for i, item in enumerate(exp_sections[:max_posts // 2]):
        text = item.get_text(separator=" ", strip=True)
        if len(text) > 20:
            results.append({
                "platform":     "linkedin",
                "username":     username,
                "post_id":      f"{username}_exp_{i}",
                "content":      text,
                "url":          profile_url,
                "content_type": "post",
            })

    # ── Public activity feed ──────────────────────────────────────────────────
    activity_url = f"https://www.linkedin.com/in/{username}/recent-activity/all/"
    resp_act = _get(activity_url, headers=headers)
    if resp_act:
        soup_act = BeautifulSoup(resp_act.text, "html.parser")
        posts = soup_act.select(".feed-shared-update-v2__description, .update-components-text")
        for i, p in enumerate(posts[:max_posts]):
            text = p.get_text(separator=" ", strip=True)
            if len(text) > 20:
                results.append({
                    "platform":     "linkedin",
                    "username":     username,
                    "post_id":      f"{username}_activity_{i}",
                    "content":      text,
                    "url":          activity_url,
                    "content_type": "post",
                })

    return results


# ══════════════════════════════════════════════════════════════════════════════
# Unified entry point
# ══════════════════════════════════════════════════════════════════════════════

PLATFORM_SCRAPERS = {
    "twitter":  scrape_twitter_profile,
    "reddit":   scrape_reddit_profile,
    "linkedin": scrape_linkedin_profile,
}


def scrape_social_profile(
    platform: str,
    username: str,
    max_posts: int = 20,
) -> list[dict]:
    """
    Unified scraper dispatcher.

    Args:
        platform:  "twitter", "reddit", or "linkedin"
        username:  Platform-specific handle/slug
        max_posts: Max posts/items to fetch

    Returns:
        List of content dicts ready for PII scanning.

    Raises:
        ValueError: If platform is not supported.
    """
    platform = platform.lower().strip()
    if platform not in PLATFORM_SCRAPERS:
        raise ValueError(
            f"Unsupported platform '{platform}'. "
            f"Choose from: {', '.join(PLATFORM_SCRAPERS)}"
        )
    return PLATFORM_SCRAPERS[platform](username, max_posts=max_posts)