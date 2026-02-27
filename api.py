"""
api.py — FastAPI backend for Aegis PII Scanner
Includes JWT-based authentication backed by MongoDB (Motor async driver).
"""

import time
import logging
import os
import datetime
from typing import Optional, List
from bson import ObjectId

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

# Backend modules
from backend.detection.presidio_engine import presidio_scan
from backend.scrapers.github_scraper import (
    list_user_public_repos,
    get_all_files,
    fetch_file_content,
)
from backend.scrapers.pastebin_scraper import get_recent_pastes, fetch_paste_raw
from backend.scrapers.social_media_scraper import scrape_social_profile
from backend.scrapers.telegram_scraper import scrape_telegram_channels_async
from backend.scoring.ess_calculator import calculate_ess, aggregate_ess
from backend.remediation.git_commands import generate_playbook, playbook_to_markdown
from backend.report_generator import generate_html_report
from backend.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
)
from backend.mongo import get_users_col, get_history_col, get_profile_col

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────
# App
# ──────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Aegis PII Scanner API",
    description="Scan public GitHub repos, Pastebin pastes, Reddit profiles, and Telegram channels for leaked PII",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: str = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_email: str
    user_name: str

class UserResponse(BaseModel):
    email: str
    full_name: str
    created_at: Optional[str] = None

class ScanHistoryItem(BaseModel):
    id: str
    scan_type: str
    target: str
    findings_count: int
    max_ess: float
    ess_label: str
    sources_scanned: int
    scan_duration: float
    created_at: Optional[str] = None

class SaveScanRequest(BaseModel):
    scan_type: str
    target: str
    findings_count: int
    max_ess: float
    ess_label: str
    sources_scanned: int
    scan_duration: float

class GitHubSingleRepoRequest(BaseModel):
    repo: str
    branch: str = "main"
    max_files: int = 40
    use_nlp: bool = False

class GitHubUserReposRequest(BaseModel):
    username: str
    max_repos: int = 5
    max_files_per_repo: int = 40
    use_nlp: bool = False

class PastebinRequest(BaseModel):
    limit: int = 15
    use_nlp: bool = False

class SocialRequest(BaseModel):
    reddit_username: Optional[str] = None
    reddit_max_posts: int = 20
    telegram_channels: Optional[List[str]] = None
    telegram_messages_per_channel: int = 50
    use_nlp: bool = False

class FindingResponse(BaseModel):
    type: str
    value: str
    value_masked: str
    snippet: str
    confidence: float
    risk: str
    annotation: str
    file_path: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    platform: Optional[str] = None
    content_type: Optional[str] = None

class ESSSummary(BaseModel):
    max_ess: float
    avg_ess: float
    label: str
    color: str
    total_sources: int
    all_types: List[str]

class ScanResponse(BaseModel):
    findings: List[FindingResponse]
    ess_summary: Optional[ESSSummary] = None
    total_sources_scanned: int
    scan_duration: float

class ProfileEntry(BaseModel):
    kind: str   # github | reddit | telegram | twitter | linkedin | email | website | custom
    label: str  # e.g. "Main GitHub"
    value: str  # URL / username / handle

class UserProfile(BaseModel):
    entries: List[ProfileEntry] = []
    notes: Optional[str] = None

class ProfileScanResult(BaseModel):
    scanned_at: str
    total_findings: int
    max_ess: float
    ess_label: str
    findings: List[FindingResponse]
    ess_summary: Optional[ESSSummary] = None

# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def run_scan_on_text(text: str, filename: str = "", use_nlp: bool = False) -> list:
    return presidio_scan(text, filename=filename, use_nlp=use_nlp)


def _doc_to_history_item(doc: dict) -> ScanHistoryItem:
    return ScanHistoryItem(
        id=str(doc["_id"]),
        scan_type=doc.get("scan_type", ""),
        target=doc.get("target", ""),
        findings_count=doc.get("findings_count", 0),
        max_ess=doc.get("max_ess", 0.0),
        ess_label=doc.get("ess_label", ""),
        sources_scanned=doc.get("sources_scanned", 0),
        scan_duration=doc.get("scan_duration", 0.0),
        created_at=doc.get("created_at", ""),
    )

# ──────────────────────────────────────────────────────────────────
# Auth endpoints
# ──────────────────────────────────────────────────────────────────

@app.post("/auth/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    users = get_users_col()
    existing = await users.find_one({"email": request.email.lower()})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    now = datetime.datetime.utcnow().isoformat()
    user_doc = {
        "email": request.email.lower(),
        "full_name": request.full_name,
        "hashed_password": get_password_hash(request.password),
        "is_active": True,
        "created_at": now,
        "last_login": now,
    }
    result = await users.insert_one(user_doc)
    uid = str(result.inserted_id)

    token = create_access_token({"sub": user_doc["email"], "name": user_doc["full_name"], "uid": uid})
    return TokenResponse(access_token=token, user_email=user_doc["email"], user_name=user_doc["full_name"])


@app.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    users = get_users_col()
    user = await users.find_one({"email": request.email.lower()})
    if not user or not verify_password(request.password, user["hashed_password"]):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is disabled")

    await users.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.datetime.utcnow().isoformat()}},
    )
    uid = str(user["_id"])
    token = create_access_token({"sub": user["email"], "name": user.get("full_name", ""), "uid": uid})
    return TokenResponse(access_token=token, user_email=user["email"], user_name=user.get("full_name", ""))


@app.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    users = get_users_col()
    user = await users.find_one({"email": current_user["email"]})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(
        email=user["email"],
        full_name=user.get("full_name", ""),
        created_at=user.get("created_at"),
    )

# ──────────────────────────────────────────────────────────────────
# Scan history endpoints
# ──────────────────────────────────────────────────────────────────

@app.post("/history/save", response_model=ScanHistoryItem)
async def save_scan_history(request: SaveScanRequest, current_user: dict = Depends(get_current_user)):
    history = get_history_col()
    doc = {
        "user_email": current_user["email"],
        "scan_type": request.scan_type,
        "target": request.target,
        "findings_count": request.findings_count,
        "max_ess": request.max_ess,
        "ess_label": request.ess_label,
        "sources_scanned": request.sources_scanned,
        "scan_duration": request.scan_duration,
        "created_at": datetime.datetime.utcnow().isoformat(),
    }
    result = await history.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_history_item(doc)


@app.get("/history", response_model=List[ScanHistoryItem])
async def get_scan_history(current_user: dict = Depends(get_current_user)):
    history = get_history_col()
    cursor = history.find({"user_email": current_user["email"]}).sort("created_at", -1).limit(100)
    docs = await cursor.to_list(length=100)
    return [_doc_to_history_item(d) for d in docs]


@app.delete("/history/{record_id}")
async def delete_scan_history(record_id: str, current_user: dict = Depends(get_current_user)):
    history = get_history_col()
    result = await history.delete_one({"_id": ObjectId(record_id), "user_email": current_user["email"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Record not found")
    return {"deleted": record_id}

# ──────────────────────────────────────────────────────────────────
# Scan endpoints (JWT protected)
# ──────────────────────────────────────────────────────────────────

@app.post("/scan/github/single", response_model=ScanResponse)
async def scan_github_single(request: GitHubSingleRepoRequest, current_user: dict = Depends(get_current_user)):
    start_time = time.time()
    try:
        files = get_all_files(request.repo, request.branch)
        text_files = [f for f in files if f["route"] == "text"][:request.max_files]

        all_findings = []
        for file in text_files:
            content = fetch_file_content(file["download_url"])
            if not content:
                continue
            raw = run_scan_on_text(content, filename=file["path"], use_nlp=request.use_nlp)
            for f in raw:
                f["file_path"] = file["path"]
                f["source"] = f"GitHub: {request.repo}/{file['path']}"
                f["source_url"] = f"https://github.com/{request.repo}/blob/{request.branch}/{file['path']}"
                all_findings.append(f)

        ess_results = []
        if all_findings:
            files_group: dict = {}
            for f in all_findings:
                files_group.setdefault(f.get("file_path", "unknown"), []).append(f)
            for ff in files_group.values():
                ess_results.append(calculate_ess(ff, source_type="github_public"))

        agg = aggregate_ess(ess_results) if ess_results else None
        return ScanResponse(
            findings=[FindingResponse(**f) for f in all_findings],
            ess_summary=ESSSummary(**agg) if agg else None,
            total_sources_scanned=len(text_files),
            scan_duration=time.time() - start_time,
        )
    except Exception as e:
        logger.exception("GitHub single scan failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scan/github/user", response_model=ScanResponse)
async def scan_github_user(request: GitHubUserReposRequest, current_user: dict = Depends(get_current_user)):
    start_time = time.time()
    try:
        repos = list_user_public_repos(request.username, max_repos=request.max_repos)
        if not repos:
            raise HTTPException(status_code=404, detail="No public repos found for user")

        all_findings, ess_results, total_files = [], [], 0
        for repo in repos:
            repo_name = repo["full_name"]
            branch = repo.get("default_branch", "main")
            files = get_all_files(repo_name, branch)
            text_files = [f for f in files if f["route"] == "text"][:request.max_files_per_repo]
            total_files += len(text_files)

            repo_findings = []
            for file in text_files:
                content = fetch_file_content(file["download_url"])
                if not content:
                    continue
                raw = run_scan_on_text(content, filename=file["path"], use_nlp=request.use_nlp)
                for f in raw:
                    f["file_path"] = file["path"]
                    f["source"] = f"GitHub: {repo_name}/{file['path']}"
                    f["source_url"] = f"https://github.com/{repo_name}/blob/{branch}/{file['path']}"
                    repo_findings.append(f)
                    all_findings.append(f)
            if repo_findings:
                ess_results.append(calculate_ess(repo_findings, source_type="github_public"))

        agg = aggregate_ess(ess_results) if ess_results else None
        return ScanResponse(
            findings=[FindingResponse(**f) for f in all_findings],
            ess_summary=ESSSummary(**agg) if agg else None,
            total_sources_scanned=total_files,
            scan_duration=time.time() - start_time,
        )
    except Exception as e:
        logger.exception("User GitHub scan failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scan/pastebin", response_model=ScanResponse)
async def scan_pastebin(request: PastebinRequest, current_user: dict = Depends(get_current_user)):
    start_time = time.time()
    try:
        pastes = get_recent_pastes(limit=request.limit)
        if not pastes:
            raise HTTPException(status_code=404, detail="No pastes fetched")

        all_findings, ess_results = [], []
        for paste in pastes:
            content = fetch_paste_raw(paste["raw_url"])
            if not content:
                continue
            raw = run_scan_on_text(content, filename=paste["paste_id"], use_nlp=request.use_nlp)
            for f in raw:
                f["file_path"] = paste["paste_id"]
                f["source"] = f"Pastebin: {paste['paste_id']}"
                f["source_url"] = paste["url"]
                all_findings.append(f)
            if raw:
                ess_results.append(calculate_ess(raw, source_type="pastebin"))

        agg = aggregate_ess(ess_results) if ess_results else None
        return ScanResponse(
            findings=[FindingResponse(**f) for f in all_findings],
            ess_summary=ESSSummary(**agg) if agg else None,
            total_sources_scanned=len(pastes),
            scan_duration=time.time() - start_time,
        )
    except Exception as e:
        logger.exception("Pastebin scan failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scan/social", response_model=ScanResponse)
async def scan_social(request: SocialRequest, current_user: dict = Depends(get_current_user)):
    start_time = time.time()
    all_findings, ess_results, total_sources = [], [], 0

    try:
        if request.reddit_username:
            username = request.reddit_username.strip()
            if username:
                total_sources += 1
                reddit_items = scrape_social_profile(platform="reddit", username=username, max_posts=request.reddit_max_posts)
                if reddit_items:
                    platform_findings = []
                    for item in reddit_items:
                        raw = run_scan_on_text(item["content"], filename=f"reddit_{item['post_id']}", use_nlp=request.use_nlp)
                        for f in raw:
                            f["file_path"] = f"reddit/{username}/{item['post_id']}"
                            f["source"] = f"Reddit: u/{username} [{item['content_type']}]"
                            f["source_url"] = item["url"]
                            f["platform"] = "reddit"
                            f["content_type"] = item["content_type"]
                            platform_findings.append(f)
                            all_findings.append(f)
                    if platform_findings:
                        ess_results.append(calculate_ess(platform_findings, source_type="social_reddit"))

        if request.telegram_channels:
            channels = [ch.strip() for ch in request.telegram_channels if ch.strip()]
            if channels:
                total_sources += len(channels)
                if not os.getenv("TELEGRAM_API_ID") or not os.getenv("TELEGRAM_API_HASH"):
                    raise HTTPException(status_code=400, detail="Telegram API credentials missing")
                all_messages = await scrape_telegram_channels_async(channels, request.telegram_messages_per_channel)
                if all_messages:
                    channel_msgs: dict = {}
                    for msg in all_messages:
                        channel_msgs.setdefault(msg["channel"], []).append(msg)
                    for channel, msgs in channel_msgs.items():
                        channel_findings = []
                        for msg in msgs:
                            raw = run_scan_on_text(msg["content"], filename=f"telegram_{channel}_{msg['message_id']}", use_nlp=request.use_nlp)
                            for f in raw:
                                f["file_path"] = f"telegram/{channel}/{msg['message_id']}"
                                f["source"] = f"Telegram: {channel}"
                                f["source_url"] = msg["url"]
                                f["platform"] = "telegram"
                                f["content_type"] = "message"
                                channel_findings.append(f)
                                all_findings.append(f)
                        if channel_findings:
                            ess_results.append(calculate_ess(channel_findings, source_type="telegram"))

        agg = aggregate_ess(ess_results) if ess_results else None
        return ScanResponse(
            findings=[FindingResponse(**f) for f in all_findings],
            ess_summary=ESSSummary(**agg) if agg else None,
            total_sources_scanned=total_sources,
            scan_duration=time.time() - start_time,
        )
    except Exception as e:
        logger.exception("Social scan failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/report/html", response_class=HTMLResponse)
async def generate_report(request: Request, current_user: dict = Depends(get_current_user)):
    try:
        body = await request.json()
        findings = body.get("findings", [])
        ess_results = body.get("ess_results", [])
        scan_type = body.get("scan_type", "api")
        target = body.get("target", "unknown")
        files_scanned = body.get("files_scanned", 0)

        if not isinstance(findings, list):
            findings = []

        html = generate_html_report(
            findings=findings,
            ess_results=ess_results,
            scan_type=scan_type,
            target=target,
            files_scanned=files_scanned,
            scan_duration_sec=0.0,
        )
        return HTMLResponse(content=html, status_code=200)
    except Exception as e:
        logger.exception("Report generation failed")
        return HTMLResponse(
            content=f"<html><body><h1>Error generating report</h1><pre>{str(e)}</pre></body></html>",
            status_code=500,
        )


# ──────────────────────────────────────────────────────────────────
# Profile map endpoints
# ──────────────────────────────────────────────────────────────────

@app.get("/profile", response_model=UserProfile)
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Return the current user's saved profile map."""
    profiles = get_profile_col()
    doc = await profiles.find_one({"user_email": current_user["email"]})
    if not doc:
        return UserProfile(entries=[], notes=None)
    return UserProfile(
        entries=[ProfileEntry(**e) for e in doc.get("entries", [])],
        notes=doc.get("notes"),
    )


@app.put("/profile", response_model=UserProfile)
async def save_profile(profile: UserProfile, current_user: dict = Depends(get_current_user)):
    """Upsert the user's profile map."""
    profiles = get_profile_col()
    await profiles.update_one(
        {"user_email": current_user["email"]},
        {"$set": {
            "user_email": current_user["email"],
            "entries": [e.dict() for e in profile.entries],
            "notes": profile.notes,
            "updated_at": datetime.datetime.utcnow().isoformat(),
        }},
        upsert=True,
    )
    return profile


@app.post("/profile/scan", response_model=ProfileScanResult)
async def scan_profile(current_user: dict = Depends(get_current_user)):
    """Scan all entries in the user's profile map and persist + return results."""
    profiles = get_profile_col()
    doc = await profiles.find_one({"user_email": current_user["email"]})
    if not doc or not doc.get("entries"):
        raise HTTPException(status_code=404, detail="No profile entries to scan. Save your profile map first.")

    entries = [ProfileEntry(**e) for e in doc["entries"]]
    start_time = time.time()
    all_findings: list = []
    ess_results: list = []
    total_sources = 0

    for entry in entries:
        kind = entry.kind.lower()
        value = entry.value.strip()
        label = entry.label or kind

        try:
            if kind == "github":
                # Treat value as a GitHub username — scan up to 3 repos, 20 files each
                username = value.rstrip("/").split("/")[-1]  # handle full URLs too
                repos = list_user_public_repos(username, max_repos=3)
                for repo in repos:
                    repo_name = repo["full_name"]
                    branch = repo.get("default_branch", "main")
                    files = get_all_files(repo_name, branch)
                    text_files = [f for f in files if f["route"] == "text"][:20]
                    total_sources += len(text_files)
                    repo_findings: list = []
                    for file in text_files:
                        content = fetch_file_content(file["download_url"])
                        if not content:
                            continue
                        raw = run_scan_on_text(content, filename=file["path"])
                        for f in raw:
                            f["file_path"] = file["path"]
                            f["source"] = f"GitHub ({label}): {repo_name}/{file['path']}"
                            f["source_url"] = f"https://github.com/{repo_name}/blob/{branch}/{file['path']}"
                            f["platform"] = "github"
                            repo_findings.append(f)
                            all_findings.append(f)
                    if repo_findings:
                        ess_results.append(calculate_ess(repo_findings, source_type="github_public"))

            elif kind == "reddit":
                username = value.lstrip("@").rstrip("/").split("/")[-1]
                total_sources += 1
                items = scrape_social_profile(platform="reddit", username=username, max_posts=20)
                platform_findings: list = []
                for item in items or []:
                    raw = run_scan_on_text(item["content"], filename=f"reddit_{item['post_id']}")
                    for f in raw:
                        f["file_path"] = f"reddit/{username}/{item['post_id']}"
                        f["source"] = f"Reddit ({label}): u/{username}"
                        f["source_url"] = item["url"]
                        f["platform"] = "reddit"
                        f["content_type"] = item["content_type"]
                        platform_findings.append(f)
                        all_findings.append(f)
                if platform_findings:
                    ess_results.append(calculate_ess(platform_findings, source_type="social_reddit"))

            elif kind == "telegram":
                # value is a channel handle
                channel = value.lstrip("@")
                total_sources += 1
                if os.getenv("TELEGRAM_API_ID") and os.getenv("TELEGRAM_API_HASH"):
                    msgs = await scrape_telegram_channels_async([channel], 50)
                    channel_findings: list = []
                    for msg in msgs or []:
                        raw = run_scan_on_text(msg["content"], filename=f"telegram_{channel}")
                        for f in raw:
                            f["file_path"] = f"telegram/{channel}/{msg['message_id']}"
                            f["source"] = f"Telegram ({label}): {channel}"
                            f["source_url"] = msg.get("url", "")
                            f["platform"] = "telegram"
                            f["content_type"] = "message"
                            channel_findings.append(f)
                            all_findings.append(f)
                    if channel_findings:
                        ess_results.append(calculate_ess(channel_findings, source_type="telegram"))

            else:
                # email / website / twitter / linkedin / custom — scan the raw value string
                total_sources += 1
                raw = run_scan_on_text(value, filename=f"profile_{kind}")
                entry_findings: list = []
                for f in raw:
                    f["file_path"] = f"profile/{kind}"
                    f["source"] = f"{kind.title()} ({label}): {value}"
                    f["source_url"] = value if value.startswith("http") else ""
                    f["platform"] = kind
                    entry_findings.append(f)
                    all_findings.append(f)
                if entry_findings:
                    ess_results.append(calculate_ess(entry_findings, source_type="social_reddit"))

        except Exception as exc:
            logger.warning("Profile scan entry '%s' failed: %s", label, exc)
            continue

    agg = aggregate_ess(ess_results) if ess_results else None
    now = datetime.datetime.utcnow().isoformat()

    scan_result = {
        "scanned_at": now,
        "total_findings": len(all_findings),
        "max_ess": agg["max_ess"] if agg else 0.0,
        "ess_label": agg["label"] if agg else "NONE",
        "findings": all_findings,
        "ess_summary": agg,
    }

    # Persist last scan into the profile document
    await profiles.update_one(
        {"user_email": current_user["email"]},
        {"$set": {"last_scan": scan_result, "last_scanned_at": now}},
    )

    return ProfileScanResult(
        scanned_at=now,
        total_findings=len(all_findings),
        max_ess=agg["max_ess"] if agg else 0.0,
        ess_label=agg["label"] if agg else "NONE",
        findings=[FindingResponse(**f) for f in all_findings],
        ess_summary=ESSSummary(**agg) if agg else None,
    )


@app.get("/profile/scan/last", response_model=Optional[ProfileScanResult])
async def get_last_profile_scan(current_user: dict = Depends(get_current_user)):
    """Return the persisted results of the last profile scan."""
    profiles = get_profile_col()
    doc = await profiles.find_one({"user_email": current_user["email"]})
    if not doc or "last_scan" not in doc:
        return None
    ls = doc["last_scan"]
    return ProfileScanResult(
        scanned_at=ls.get("scanned_at", ""),
        total_findings=ls.get("total_findings", 0),
        max_ess=ls.get("max_ess", 0.0),
        ess_label=ls.get("ess_label", "NONE"),
        findings=[FindingResponse(**f) for f in ls.get("findings", [])],
        ess_summary=ESSSummary(**ls["ess_summary"]) if ls.get("ess_summary") else None,
    )


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}