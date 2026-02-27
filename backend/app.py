"""
app.py — Aegis PII Leakage Scanner — Streamlit Demo UI

Tabs:
  1. GitHub   — scan a single repo or all public repos of a user
  2. Pastebin — scan recent public pastes
  3. Combined — GitHub + Pastebin in one run
  4. Social   — scan public Twitter/X, Reddit, LinkedIn profiles
"""

import time
import sys
import os
import logging

import streamlit as st
import pandas as pd

# ── Path setup so we can import backend modules from the same directory ──
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "detection"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "scrapers"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "scoring"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend", "remediation"))

from presidio_engine import presidio_scan
from github_scraper import list_user_public_repos, get_all_files, fetch_file_content
from pastebin_scraper import get_recent_pastes, fetch_paste_raw
from ess_calculator import calculate_ess, ess_label, ess_color, aggregate_ess, ESSResult
from git_commands import generate_playbook, playbook_to_markdown
from report_generator import generate_html_report
from social_media_scraper import scrape_social_profile
from telegram_scraper import scrape_telegram_channels

logging.basicConfig(level=logging.WARNING)

# ─────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Aegis — Indian PII Leakage Scanner",
    page_icon="🛡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ────────────────────────────────────────────────
st.markdown("""
<style>
  .ess-gauge {
    font-size: 3rem;
    font-weight: 800;
    text-align: center;
    padding: 1rem;
    border-radius: 12px;
    margin-bottom: 1rem;
  }
  .stDataFrame { font-size: 0.85rem; }
  .tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
    margin: 2px;
  }
  .tag-critical { background: #ff2d2d22; color: #ff2d2d; border: 1px solid #ff2d2d55; }
  .tag-high     { background: #ff6b0022; color: #ff6b00; border: 1px solid #ff6b0055; }
  .tag-medium   { background: #ffc10722; color: #d4a017; border: 1px solid #ffc10755; }
  .tag-low      { background: #4fc3f722; color: #0288d1; border: 1px solid #4fc3f755; }

  /* Social platform badges */
  .platform-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    margin-right: 4px;
  }
  .badge-twitter  { background: #1da1f222; color: #1da1f2; border: 1px solid #1da1f255; }
  .badge-reddit   { background: #ff451522; color: #ff4515; border: 1px solid #ff451555; }
  .badge-linkedin { background: #0a66c222; color: #0a66c2; border: 1px solid #0a66c255; }
  .badge-telegram { background: #0088cc22; color: #0088cc; border: 1px solid #0088cc55; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────

st.title("🛡 Aegis — Context-Aware Indian PII Leakage Scanner")
st.caption("HackWithAI 2026 · Educational demo · No raw PII is stored · Scan public data only")
st.warning(
    "⚠️ **DEMO MODE** — Use only public repositories and test data. "
    "Do not scan repositories containing real personal information of others without authorization.",
    icon="⚠️",
)

# ─────────────────────────────────────────────────────────────
# Shared utilities
# ─────────────────────────────────────────────────────────────

_RISK_COLORS = {
    "Critical": "#ff2d2d",
    "High":     "#ff6b00",
    "Medium":   "#ffc107",
    "Low":      "#4fc3f7",
}

_RISK_BG = {
    "Critical": "#ff2d2d18",
    "High":     "#ff6b0018",
    "Medium":   "#ffc10718",
    "Low":      "#4fc3f718",
}


def style_risk(val):
    color = _RISK_COLORS.get(val, "#aaaaaa")
    bg    = _RISK_BG.get(val, "transparent")
    return f"background-color: {bg}; color: {color}; font-weight: 600;"


def render_ess_gauge(ess: float, label: str, color: str):
    st.markdown(
        f'<div class="ess-gauge" style="background:{color}22; color:{color}; '
        f'border: 2px solid {color}55;">'
        f'ESS: {ess:.1f} / 10<br>'
        f'<span style="font-size:1rem; font-weight:400;">{label}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_findings_table(findings: list[dict]):
    if not findings:
        st.info("No PII detected in scanned content.")
        return

    rows = []
    for f in findings:
        rows.append({
            "Type":         f["type"],
            "Masked Value": f["value_masked"],
            "Confidence":   f"{f['confidence']:.0%}",
            "Risk":         f["risk"],
            "Snippet":      f["snippet"][:120] + "…" if len(f["snippet"]) > 120 else f["snippet"],
            "Note":         f.get("annotation", ""),
        })

    df = pd.DataFrame(rows)

    st.dataframe(
        df.style
        .map(style_risk, subset=["Risk"])
        .set_properties(**{"text-align": "left"}, subset=["Snippet", "Note"])
        .set_table_styles([
            {"selector": "th", "props": [("font-weight", "bold")]},
        ]),
        use_container_width=True,
        height=min(60 + len(rows) * 38, 500),
    )


def run_scan_on_text(text: str, filename: str = "", use_nlp: bool = False) -> list[dict]:
    """Run the full detection pipeline on a text string."""
    findings = presidio_scan(text, filename=filename, use_nlp=use_nlp)
    return findings


def render_report_download(
    findings: list[dict],
    ess_results: list,
    scan_type: str,
    target: str,
    files_scanned: int,
    scan_duration: float = 0.0,
):
    """Render a download button for the HTML classification report."""
    if not findings:
        return
    with st.expander("📊 Download Classification Report", expanded=True):
        st.markdown(
            "Generate a **detailed, self-contained HTML report** with executive summary, "
            "ESS gauge, risk breakdown, entity classification, remediation guidance, and more."
        )
        report_html = generate_html_report(
            findings=findings,
            ess_results=ess_results,
            scan_type=scan_type,
            target=target,
            files_scanned=files_scanned,
            scan_duration_sec=scan_duration,
        )
        safe_target = target.replace('/', '_').replace(' ', '_')[:40]
        st.download_button(
            label="📥 Download Classification Report (.html)",
            data=report_html,
            file_name=f"aegis_report_{safe_target}_{scan_type}.html",
            mime="text/html",
            type="primary",
        )


def render_remediation(repo_name: str, all_findings: list[dict]):
    """Render the remediation playbook expander."""
    leaked_files = list({
        f.get("file_path", "")
        for f in all_findings
        if f.get("file_path")
    })
    entity_types = list({f["type"] for f in all_findings})

    if not leaked_files:
        return

    with st.expander("🛠 View Remediation Playbook", expanded=False):
        playbook = generate_playbook(repo_name, leaked_files, entity_types)
        md = playbook_to_markdown(playbook)
        st.markdown(md)
        st.download_button(
            label="📥 Download Playbook (.md)",
            data=md,
            file_name=f"aegis_remediation_{repo_name.replace('/', '_')}.md",
            mime="text/markdown",
        )


# ─────────────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────────────

tab_github, tab_pastebin, tab_combined, tab_social = st.tabs([
    "🐙 GitHub", "📋 Pastebin", "🔗 Combined", "📱 Social Media"
])


# ══════════════════════════════════════════════════════════════
# GitHub Tab
# ══════════════════════════════════════════════════════════════

with tab_github:
    st.markdown("### GitHub Repository Scanner")

    col_mode, col_nlp = st.columns([3, 1])
    with col_mode:
        scan_mode = st.radio(
            "Scan mode",
            ["Single Repository", "All Public Repos of User"],
            horizontal=True,
            index=0,
        )
    with col_nlp:
        use_nlp = st.toggle("NLP Filter (slow)", value=False,
                            help="HuggingFace transformer to suppress fake-data FPs. ~90 MB download on first use.")

    max_files_per_repo = st.slider(
        "Max files per repo",
        min_value=5, max_value=150, value=40, step=5,
        help="Cap files per repo. Priority extensions (.env, .json, .csv, .sql) scanned first.",
    )

    target_repos: list[dict] = []

    if scan_mode == "Single Repository":
        repo_input = st.text_input(
            "Repository (owner/repo)",
            placeholder="ceddarCoder/1b-1",
            value="ceddarCoder/1b-1",
        )
        branch_input = st.text_input("Branch", value="main", placeholder="main")
        if repo_input and "/" in repo_input:
            target_repos = [{"full_name": repo_input.strip(), "default_branch": branch_input.strip()}]
    else:
        col_u, col_m = st.columns([2, 1])
        with col_u:
            username = st.text_input("GitHub Username", placeholder="octocat")
        with col_m:
            max_repos = st.slider("Max repos", 1, 30, 5)
        if username:
            with st.spinner("Fetching repo list…"):
                target_repos = list_user_public_repos(username.strip(), max_repos=max_repos)
            if target_repos:
                st.success(f"Found {len(target_repos)} public repositories.")
            else:
                st.error("No public repos found. Check the username.")

    debug_mode = st.checkbox("Debug mode (show file previews)", value=False)

    scan_btn = st.button("🔍 Scan GitHub", type="primary", key="github_scan")

    _PRIORITY_EXTS = {".env", ".json", ".csv", ".txt", ".yml", ".yaml", ".sql", ".log", ".conf", ".ini"}

    if scan_btn:
        _gh_scan_start = time.time()
        if not target_repos:
            st.error("No repository targets found. Check your input.")
        else:
            all_findings: list[dict] = []
            ess_results: list[ESSResult] = []
            file_debug: list[dict] = []
            total_files_scanned = 0
            total_files_skipped = 0

            progress = st.progress(0.0, text="Initialising…")
            status   = st.empty()

            for repo_idx, repo in enumerate(target_repos):
                repo_name = repo["full_name"]
                branch    = repo.get("default_branch", "main")
                status.info(f"🔍 Scanning `{repo_name}` ({repo_idx + 1}/{len(target_repos)})…")

                files = get_all_files(repo_name, branch)
                text_files = [f for f in files if f["route"] == "text"]

                text_files.sort(key=lambda f: (
                    0 if any(f["path"].endswith(e) for e in _PRIORITY_EXTS) else 1,
                    f["path"],
                ))

                capped = text_files[:max_files_per_repo]
                total_files_scanned += len(capped)
                total_files_skipped += len(text_files) - len(capped)

                repo_findings: list[dict] = []

                for file_idx, item in enumerate(capped):
                    content = fetch_file_content(item["download_url"])
                    if not content:
                        continue

                    raw_findings = run_scan_on_text(
                        content,
                        filename=item["path"],
                        use_nlp=use_nlp,
                    )

                    for f in raw_findings:
                        f["file_path"]  = item["path"]
                        f["source"]     = f"GitHub: {repo_name}/{item['path']}"
                        f["source_url"] = f"https://github.com/{repo_name}/blob/{branch}/{item['path']}"
                        repo_findings.append(f)
                        all_findings.append(f)

                    if debug_mode:
                        file_debug.append({
                            "repo":    repo_name,
                            "path":    item["path"],
                            "preview": content[:400],
                            "matches": len(raw_findings),
                        })

                    pct = (repo_idx + (file_idx + 1) / max(len(capped), 1)) / len(target_repos)
                    progress.progress(min(pct, 0.99), text=f"Scanning `{item['path']}`…")

                if repo_findings:
                    ess = calculate_ess(repo_findings, source_type="github_public")
                    ess_results.append(ess)

            progress.progress(1.0, text="Scan complete.")
            status.empty()

            st.markdown("---")
            skipped_note = f" ({total_files_skipped} skipped by cap)" if total_files_skipped else ""
            st.markdown(f"#### Results — {len(all_findings)} findings across {total_files_scanned} files{skipped_note}")

            if ess_results:
                agg = aggregate_ess(ess_results)
                col_ess, col_meta = st.columns([1, 2])
                with col_ess:
                    render_ess_gauge(agg["max_ess"], agg["label"], agg["color"])
                with col_meta:
                    st.metric("Total Findings", len(all_findings))
                    st.metric("Files Scanned", total_files_scanned)
                    st.metric("Repos Scanned", len(target_repos))
                    if agg["all_types"]:
                        st.caption("Entity types found: " + " · ".join(agg["all_types"]))

            render_findings_table(all_findings)

            if all_findings and target_repos:
                render_report_download(
                    findings=all_findings,
                    ess_results=ess_results,
                    scan_type="github",
                    target=target_repos[0]["full_name"],
                    files_scanned=total_files_scanned,
                    scan_duration=time.time() - _gh_scan_start,
                )
                render_remediation(target_repos[0]["full_name"], all_findings)

            if debug_mode and file_debug:
                with st.expander("🐛 Debug: File Previews"):
                    for d in file_debug:
                        st.markdown(f"**`{d['repo']}/{d['path']}`** — {d['matches']} match(es)")
                        st.code(d["preview"], language="text")


# ══════════════════════════════════════════════════════════════
# Pastebin Tab
# ══════════════════════════════════════════════════════════════

with tab_pastebin:
    st.markdown("### Pastebin Recent Pastes Scanner")
    st.info(
        "Scans Pastebin's public archive. Uses the official Scraping API if available "
        "(requires whitelisted IP), otherwise falls back to archive page scraping.",
        icon="ℹ️",
    )

    col_limit, col_nlp_pb = st.columns([2, 1])
    with col_limit:
        paste_limit = st.slider("Number of recent pastes to scan", 5, 50, 15)
    with col_nlp_pb:
        use_nlp_pb = st.toggle("NLP Filter", value=False, key="pb_nlp")

    debug_paste = st.checkbox("Debug mode (paste previews)", value=False)

    if st.button("🔍 Scan Pastebin", type="primary", key="pastebin_scan"):
        _pb_scan_start = time.time()
        with st.spinner("Fetching recent pastes…"):
            pastes = get_recent_pastes(limit=paste_limit)

        if not pastes:
            st.error(
                "Could not fetch any pastes. "
                "Pastebin may be rate-limiting or the archive structure has changed."
            )
        else:
            st.success(f"Fetched {len(pastes)} pastes. Scanning…")

            all_findings: list[dict] = []
            ess_results: list[ESSResult] = []
            paste_debug: list[dict] = []

            progress = st.progress(0.0)
            status   = st.empty()

            for idx, paste in enumerate(pastes):
                status.info(f"Scanning paste `{paste['paste_id']}` ({idx + 1}/{len(pastes)})…")
                content = fetch_paste_raw(paste["raw_url"])

                if content:
                    raw_findings = run_scan_on_text(content, filename=paste['paste_id'], use_nlp=use_nlp_pb)

                    for f in raw_findings:
                        f["file_path"]  = paste["paste_id"]
                        f["source"]     = f"Pastebin: {paste['paste_id']}"
                        f["source_url"] = paste["url"]
                        all_findings.append(f)

                    if raw_findings:
                        ess = calculate_ess(raw_findings, source_type="pastebin")
                        ess_results.append(ess)

                    if debug_paste:
                        paste_debug.append({
                            "paste_id": paste["paste_id"],
                            "syntax":   paste.get("syntax", "text"),
                            "preview":  content[:400],
                            "matches":  len(raw_findings),
                        })

                progress.progress((idx + 1) / len(pastes))

            status.empty()

            st.markdown("---")
            st.markdown(f"#### Results — {len(all_findings)} findings across {len(pastes)} pastes")

            if ess_results:
                agg = aggregate_ess(ess_results)
                col_ess, col_meta = st.columns([1, 2])
                with col_ess:
                    render_ess_gauge(agg["max_ess"], agg["label"], agg["color"])
                with col_meta:
                    st.metric("Total Findings", len(all_findings))
                    st.metric("Pastes Scanned", len(pastes))
                    if agg["all_types"]:
                        st.caption("Entity types: " + " · ".join(agg["all_types"]))

            render_findings_table(all_findings)

            if all_findings:
                render_report_download(
                    findings=all_findings,
                    ess_results=ess_results,
                    scan_type="pastebin",
                    target=f"pastebin_recent_{paste_limit}",
                    files_scanned=len(pastes),
                    scan_duration=time.time() - _pb_scan_start,
                )

            if debug_paste and paste_debug:
                with st.expander("🐛 Debug: Paste Previews"):
                    for d in paste_debug:
                        st.markdown(
                            f"**Paste `{d['paste_id']}`** (syntax: `{d['syntax']}`) "
                            f"— {d['matches']} match(es)"
                        )
                        st.code(d["preview"], language="text")


# ══════════════════════════════════════════════════════════════
# Combined Tab
# ══════════════════════════════════════════════════════════════

with tab_combined:
    st.markdown("### Combined GitHub + Pastebin Scan")
    st.markdown(
        "Run both GitHub and Pastebin scans simultaneously and view a unified "
        "threat intelligence report with cross-platform ESS aggregation."
    )

    col_gh, col_pb = st.columns(2)

    with col_gh:
        st.markdown("#### GitHub Target")
        combined_repo = st.text_input("Repository (owner/repo)", key="combined_repo",
                                       placeholder="ceddarCoder/1b-1")
        combined_branch = st.text_input("Branch", value="main", key="combined_branch")

    with col_pb:
        st.markdown("#### Pastebin Target")
        combined_paste_limit = st.slider("Recent pastes", 5, 30, 10, key="combined_pb_limit")

    combined_nlp = st.toggle("NLP Filter", value=False, key="combined_nlp")

    if st.button("🔍 Run Combined Scan", type="primary", key="combined_scan"):
        if not combined_repo or "/" not in combined_repo:
            st.error("Enter a valid GitHub repository (owner/repo).")
        else:
            all_findings: list[dict] = []
            ess_results: list[ESSResult] = []
            total_files = 0

            st.markdown("**Scanning GitHub…**")
            progress_gh = st.progress(0.0)

            files = get_all_files(combined_repo.strip(), combined_branch.strip())
            text_files = [f for f in files if f["route"] == "text"]
            total_files = len(text_files)
            repo_findings: list[dict] = []

            for idx, item in enumerate(text_files):
                content = fetch_file_content(item["download_url"])
                if content:
                    raw = run_scan_on_text(content, use_nlp=combined_nlp)
                    for f in raw:
                        f["file_path"]  = item["path"]
                        f["source"]     = f"GitHub: {combined_repo}/{item['path']}"
                        f["source_url"] = (
                            f"https://github.com/{combined_repo}/blob/"
                            f"{combined_branch}/{item['path']}"
                        )
                        repo_findings.append(f)
                        all_findings.append(f)

                progress_gh.progress((idx + 1) / max(len(text_files), 1))
                time.sleep(0.8)

            if repo_findings:
                ess_results.append(calculate_ess(repo_findings, "github_public"))

            st.markdown("**Scanning Pastebin…**")
            progress_pb = st.progress(0.0)

            pastes = get_recent_pastes(limit=combined_paste_limit)
            for idx, paste in enumerate(pastes):
                content = fetch_paste_raw(paste["raw_url"])
                if content:
                    raw = run_scan_on_text(content, use_nlp=combined_nlp)
                    for f in raw:
                        f["file_path"]  = paste["paste_id"]
                        f["source"]     = f"Pastebin: {paste['paste_id']}"
                        f["source_url"] = paste["url"]
                        all_findings.append(f)

                    if raw:
                        ess_results.append(calculate_ess(raw, "pastebin"))

                progress_pb.progress((idx + 1) / max(len(pastes), 1))
                time.sleep(1.0)

            st.markdown("---")
            st.markdown(f"### Combined Threat Report — {len(all_findings)} Total Findings")

            if ess_results:
                agg = aggregate_ess(ess_results)

                col_ess, col_meta = st.columns([1, 2])
                with col_ess:
                    render_ess_gauge(agg["max_ess"], agg["label"], agg["color"])
                with col_meta:
                    st.metric("Total Findings", len(all_findings))
                    st.metric("GitHub Files", total_files)
                    st.metric("Pastebin Pastes", len(pastes))
                    st.metric("Max ESS", f"{agg['max_ess']:.1f} / 10")
                    st.metric("Avg ESS", f"{agg['avg_ess']:.1f} / 10")

            gh_findings = [f for f in all_findings if f["source"].startswith("GitHub")]
            pb_findings = [f for f in all_findings if f["source"].startswith("Pastebin")]

            if gh_findings:
                st.markdown("#### GitHub Findings")
                render_findings_table(gh_findings)
                render_remediation(combined_repo.strip(), gh_findings)

            if pb_findings:
                st.markdown("#### Pastebin Findings")
                render_findings_table(pb_findings)

            if all_findings:
                render_report_download(
                    findings=all_findings,
                    ess_results=ess_results,
                    scan_type="combined",
                    target=f"{combined_repo.strip()} + pastebin",
                    files_scanned=total_files + len(pastes),
                    scan_duration=0.0,
                )

            if not all_findings:
                st.info("No PII detected across GitHub and Pastebin.")


# ══════════════════════════════════════════════════════════════
# Social Media Tab (Reddit + Telegram)
# ══════════════════════════════════════════════════════════════

with tab_social:
    st.markdown("### 📱 Social Media PII Scanner")
    st.markdown(
        "Scan **public** Reddit profiles and Telegram channels for leaked PII. "
        "Reddit: profile bio + recent posts/comments. "
        "Telegram: recent messages from public channels."
    )
    st.info(
        "🔒 **Privacy:** Only public content is scanned. "
        "Telegram requires API credentials (set as environment variables).",
        icon="🔒",
    )

    # ── Two‑column layout ─────────────────────────────────────
    col_reddit, col_telegram = st.columns(2)

    with col_reddit:
        st.markdown(
            '<span class="platform-badge badge-reddit">🤖 Reddit</span>',
            unsafe_allow_html=True,
        )
        enable_reddit = st.checkbox("Enable Reddit scan", value=True, key="social_reddit_enable")
        reddit_username = st.text_input(
            "Reddit username",
            placeholder="spez  (without u/)",
            key="social_reddit_user",
            disabled=not enable_reddit,
        )
        reddit_max_posts = st.slider(
            "Max posts/comments",
            min_value=5, max_value=50, value=20, step=5,
            key="social_reddit_posts",
            disabled=not enable_reddit,
        )

    with col_telegram:
        st.markdown(
            '<span class="platform-badge badge-telegram">📱 Telegram</span>',
            unsafe_allow_html=True,
        )
        enable_telegram = st.checkbox("Enable Telegram scan", value=True, key="social_telegram_enable")
        telegram_channels = st.text_area(
            "Channel usernames (one per line)",
            placeholder="duckchan\ncybernews",
            height=100,
            key="social_telegram_channels",
            disabled=not enable_telegram,
        )
        telegram_messages = st.slider(
            "Messages per channel",
            min_value=10, max_value=200, value=50, step=10,
            key="social_telegram_msgs",
            disabled=not enable_telegram,
        )

    # ── Common options ────────────────────────────────────────
    st.markdown("---")
    col_opts1, col_opts2 = st.columns([2, 1])
    with col_opts1:
        social_use_nlp = st.toggle(
            "NLP Filter (slow)",
            value=False,
            key="social_nlp",
            help="HuggingFace transformer to reduce false positives.",
        )
    with col_opts2:
        social_debug = st.checkbox("Debug mode", value=False, key="social_debug")

    scan_social_btn = st.button("🔍 Scan Social Media", type="primary", key="social_scan")

    if scan_social_btn:
        _social_start = time.time()
        all_findings = []
        ess_results = []
        debug_items = []
        total_sources = 0

        progress = st.progress(0.0, text="Starting scan…")
        status = st.empty()

        # ── Reddit ────────────────────────────────────────────
        if enable_reddit and reddit_username.strip():
            total_sources += 1
            username = reddit_username.strip()
            status.info(f"🔍 Scraping Reddit: u/{username} …")

            try:
                reddit_items = scrape_social_profile(
                    platform="reddit",
                    username=username,
                    max_posts=reddit_max_posts,
                )
            except Exception as e:
                st.warning(f"Reddit scraping failed: {e}")
                reddit_items = []

            if reddit_items:
                platform_findings = []
                for item in reddit_items:
                    raw = run_scan_on_text(
                        item["content"],
                        filename=f"reddit_{item['post_id']}",
                        use_nlp=social_use_nlp,
                    )
                    for f in raw:
                        f["file_path"] = f"reddit/{username}/{item['post_id']}"
                        f["source"] = f"Reddit: u/{username} [{item['content_type']}]"
                        f["source_url"] = item["url"]
                        f["platform"] = "reddit"
                        f["content_type"] = item["content_type"]
                        platform_findings.append(f)
                        all_findings.append(f)

                    if social_debug:
                        debug_items.append({
                            "platform": "Reddit",
                            "username": username,
                            "id": item["post_id"],
                            "type": item["content_type"],
                            "preview": item["content"][:400],
                            "matches": len(raw),
                        })

                if platform_findings:
                    ess = calculate_ess(platform_findings, source_type="social_reddit")
                    ess_results.append(ess)

        # ── Telegram ──────────────────────────────────────────
        if enable_telegram and telegram_channels.strip():
            # Parse channels
            channel_list = [ch.strip() for ch in telegram_channels.split("\n") if ch.strip()]
            if channel_list:
                total_sources += len(channel_list)
                status.info(f"📱 Fetching Telegram messages from {len(channel_list)} channel(s) …")

                # Check API credentials
                if not os.getenv("TELEGRAM_API_ID") or not os.getenv("TELEGRAM_API_HASH"):
                    st.error("Telegram API credentials missing. Set TELEGRAM_API_ID and TELEGRAM_API_HASH.")
                else:
                    try:
                        all_messages = scrape_telegram_channels(channel_list, telegram_messages)
                    except Exception as e:
                        st.error(f"Telegram scraping failed: {e}")
                        all_messages = []

                    if all_messages:
                        # Group messages by channel for processing
                        channel_msgs = {}
                        for msg in all_messages:
                            channel_msgs.setdefault(msg["channel"], []).append(msg)

                        for channel, msgs in channel_msgs.items():
                            channel_findings = []
                            for msg in msgs:
                                raw = run_scan_on_text(
                                    msg["content"],
                                    filename=f"telegram_{channel}_{msg['message_id']}",
                                    use_nlp=social_use_nlp,
                                )
                                for f in raw:
                                    f["file_path"] = f"telegram/{channel}/{msg['message_id']}"
                                    f["source"] = f"Telegram: {channel}"
                                    f["source_url"] = msg["url"]
                                    f["platform"] = "telegram"
                                    f["content_type"] = "message"
                                    channel_findings.append(f)
                                    all_findings.append(f)

                                if social_debug:
                                    debug_items.append({
                                        "platform": "Telegram",
                                        "username": channel,
                                        "id": msg["message_id"],
                                        "type": "message",
                                        "preview": msg["content"][:400],
                                        "matches": len(raw),
                                    })

                            if channel_findings:
                                ess = calculate_ess(channel_findings, source_type="telegram")
                                ess_results.append(ess)

        progress.progress(1.0, text="Scan complete.")
        status.empty()

        # ── Display results ───────────────────────────────────
        st.markdown("---")
        st.markdown(
            f"#### Results — **{len(all_findings)}** PII findings "
            f"from **{total_sources}** source(s)"
        )

        if not all_findings:
            st.success("✅ No PII detected in scanned content.")
        else:
            # Aggregate ESS across all sources
            if ess_results:
                agg = aggregate_ess(ess_results)
                col_ess, col_meta = st.columns([1, 2])
                with col_ess:
                    render_ess_gauge(agg["max_ess"], agg["label"], agg["color"])
                with col_meta:
                    st.metric("Total Findings", len(all_findings))
                    st.metric("Sources Scanned", total_sources)
                    if agg["all_types"]:
                        st.caption("Entity types: " + " · ".join(agg["all_types"]))

            # Split findings by platform
            reddit_findings = [f for f in all_findings if f.get("platform") == "reddit"]
            telegram_findings = [f for f in all_findings if f.get("platform") == "telegram"]

            if reddit_findings:
                st.markdown(
                    '<span class="platform-badge badge-reddit">🤖 Reddit</span> '
                    f'**{reddit_username.strip()}** — {len(reddit_findings)} finding(s)',
                    unsafe_allow_html=True,
                )
                render_findings_table(reddit_findings)

            if telegram_findings:
                st.markdown(
                    '<span class="platform-badge badge-telegram">📱 Telegram</span> '
                    f'Channels scanned: {", ".join(channel_list)} — {len(telegram_findings)} finding(s)',
                    unsafe_allow_html=True,
                )
                render_findings_table(telegram_findings)

            # Download report
            target = "reddit:" + reddit_username.strip() if reddit_username.strip() else ""
            if channel_list:
                target += (" + " if target else "") + "telegram:" + ",".join(channel_list)
            render_report_download(
                findings=all_findings,
                ess_results=ess_results,
                scan_type="social_media",
                target=target,
                files_scanned=total_sources,
                scan_duration=time.time() - _social_start,
            )

        # ── Debug previews ───────────────────────────────────
        if social_debug and debug_items:
            with st.expander("🐛 Debug: Raw Content Previews"):
                for d in debug_items:
                    badge_class = "badge-reddit" if d["platform"] == "Reddit" else "badge-telegram"
                    st.markdown(
                        f'<span class="platform-badge {badge_class}">{d["platform"]}</span> '
                        f'**{d["username"]}** · `{d["id"]}` ({d["type"]}) — {d["matches"]} match(es)',
                        unsafe_allow_html=True,
                    )
                    st.code(d["preview"], language="text")