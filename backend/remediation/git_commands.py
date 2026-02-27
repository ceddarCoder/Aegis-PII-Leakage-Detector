"""
git_commands.py — Auto-remediation playbook generator.

Given a list of leaked file paths in a GitHub repository, generates the
exact shell commands required to:
  1. Permanently scrub the file from all git history (git filter-repo)
  2. Remove secrets from the working tree without losing the file
  3. Rotate credentials / revoke exposed documents

Output is a structured dict consumed by the Streamlit/Next.js dashboard
to render a copy-paste remediation modal.
"""

from dataclasses import dataclass, field


@dataclass
class RemediationStep:
    title: str
    description: str
    commands: list[str]
    warning: str = ""
    is_destructive: bool = False


@dataclass
class RemediationPlaybook:
    repo_name: str          # e.g. "octocat/my-repo"
    leaked_files: list[str] # relative paths within the repo
    entity_types: list[str] # PII types found
    steps: list[RemediationStep] = field(default_factory=list)
    general_advice: list[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# Playbook generator
# ─────────────────────────────────────────────────────────────

def generate_playbook(
    repo_name: str,
    leaked_files: list[str],
    entity_types: list[str],
    remote_url: str | None = None,
) -> RemediationPlaybook:
    """
    Generate a complete remediation playbook for a GitHub repository
    that has exposed PII.

    Args:
        repo_name:    'owner/repo' string
        leaked_files: List of relative file paths that contain PII
        entity_types: List of detected PII entity type strings
        remote_url:   Optional remote URL override (defaults to HTTPS)

    Returns:
        RemediationPlaybook with all steps and advice.
    """
    if not remote_url:
        remote_url = f"https://github.com/{repo_name}.git"

    playbook = RemediationPlaybook(
        repo_name=repo_name,
        leaked_files=leaked_files,
        entity_types=entity_types,
    )

    # ── Step 0: IMMEDIATE — Make repo private ─────────────────
    playbook.steps.append(RemediationStep(
        title="🔒 Step 0 — Immediately make the repository private",
        description=(
            "Before doing anything else, navigate to your repository settings on GitHub "
            "and set the visibility to Private. This stops new exposure while you clean up. "
            "If the data has been cached or forked, it may already be in the wild — proceed "
            "with all remaining steps regardless."
        ),
        commands=[
            "# Via GitHub CLI (gh):",
            f"gh repo edit {repo_name} --visibility private",
            "",
            "# Or navigate to:",
            f"# https://github.com/{repo_name}/settings → Danger Zone → Change visibility",
        ],
        warning="Making the repo private does NOT remove data from git history or search caches.",
        is_destructive=False,
    ))

    # ── Step 1: Clone a fresh copy ────────────────────────────
    repo_slug = repo_name.split("/")[-1]
    playbook.steps.append(RemediationStep(
        title="📥 Step 1 — Clone a fresh mirror of the repository",
        description=(
            "Work on a fresh clone to avoid corrupting your local working copy. "
            "We use --mirror to get all branches and refs."
        ),
        commands=[
            f"git clone --mirror {remote_url} {repo_slug}-mirror",
            f"cd {repo_slug}-mirror",
        ],
        is_destructive=False,
    ))

    # ── Step 2: Install git filter-repo ───────────────────────
    playbook.steps.append(RemediationStep(
        title="🛠  Step 2 — Install git-filter-repo",
        description=(
            "git-filter-repo is the recommended tool for rewriting git history. "
            "It is faster and safer than the deprecated git filter-branch."
        ),
        commands=[
            "pip install git-filter-repo",
            "# OR",
            "brew install git-filter-repo    # macOS",
            "# OR",
            "apt install git-filter-repo     # Debian/Ubuntu",
        ],
        is_destructive=False,
    ))

    # ── Step 3: Purge leaked files from history ───────────────
    purge_commands = []
    for filepath in leaked_files:
        purge_commands.append(
            f"git filter-repo --path '{filepath}' --invert-paths --force"
        )

    if len(leaked_files) > 1:
        # Batch approach using --paths-from-file
        paths_content = "\n".join(leaked_files)
        purge_commands = [
            f"# Create a file listing all paths to remove:",
            f"cat > /tmp/aegis_paths_to_remove.txt << 'EOF'",
            paths_content,
            "EOF",
            "",
            "# Purge all leaked files in a single pass:",
            "git filter-repo --paths-from-file /tmp/aegis_paths_to_remove.txt --invert-paths --force",
        ]

    playbook.steps.append(RemediationStep(
        title="🗑  Step 3 — Purge leaked files from ALL git history",
        description=(
            "This rewrites every commit that touched the leaked files. "
            "The files will be completely removed from the repository's history. "
            "⚠️ This changes commit SHAs — all collaborators will need to re-clone."
        ),
        commands=purge_commands,
        warning=(
            "DESTRUCTIVE: This operation rewrites git history. "
            "Coordinate with all contributors before proceeding. "
            "Commits pushed to forks remain unaffected — those must be deleted separately."
        ),
        is_destructive=True,
    ))

    # ── Step 4: Alternatively — redact secrets in-place ───────
    if leaked_files:
        sample_file = leaked_files[0]
        playbook.steps.append(RemediationStep(
            title="✏️  Step 3b — Alternative: Redact secrets in-place (keep file, remove value)",
            description=(
                "If you want to keep the file in the repo but remove only the secret value, "
                "use filter-repo's --replace-text option to overwrite the sensitive string "
                "across all historical commits."
            ),
            commands=[
                "# Create a replacements file:",
                "# Format: LITERAL_SECRET==>REDACTED",
                "echo 'YOUR_SECRET_VALUE==>***REDACTED***' > /tmp/replacements.txt",
                "",
                "# Apply replacements across all history:",
                "git filter-repo --replace-text /tmp/replacements.txt --force",
            ],
            warning="You must know the exact secret value to use this method.",
            is_destructive=True,
        ))

    # ── Step 5: Force-push the cleaned history ────────────────
    playbook.steps.append(RemediationStep(
        title="🚀 Step 4 — Force-push the cleaned history to GitHub",
        description=(
            "After rewriting history, push all refs back to GitHub. "
            "You may need to temporarily disable branch protection rules."
        ),
        commands=[
            "git push --mirror --force origin",
            "",
            "# If you get 'protected branch' errors, first disable protection:",
            f"# https://github.com/{repo_name}/settings/branches",
        ],
        warning="Force-pushing will break any open pull requests against affected branches.",
        is_destructive=True,
    ))

    # ── Step 6: Invalidate GitHub's cache ─────────────────────
    playbook.steps.append(RemediationStep(
        title="🧹 Step 5 — Invalidate GitHub's caches",
        description=(
            "GitHub caches raw file content. Submit a support request to "
            "remove cached versions of the exposed files."
        ),
        commands=[
            "# Contact GitHub Support:",
            "# https://support.github.com/contact",
            "# Request: 'Cached content removal after history rewrite'",
            "",
            "# Also contact Google to de-index cached pages:",
            "# https://search.google.com/search-console/removals",
        ],
        is_destructive=False,
    ))

    # ── Entity-specific advice ─────────────────────────────────
    playbook.general_advice = _entity_advice(entity_types)

    return playbook


def _entity_advice(entity_types: list[str]) -> list[str]:
    """Return entity-type-specific post-incident advice."""
    advice = []

    if "IN_AADHAAR" in entity_types:
        advice.append(
            "🪪 Aadhaar exposed: Contact UIDAI helpline (1947) and report the incident. "
            "Biometric lock your Aadhaar via the mAadhaar app or UIDAI portal "
            "(https://myaadhaar.uidai.gov.in) to prevent authentication misuse."
        )

    if "IN_PAN" in entity_types:
        advice.append(
            "🧾 PAN exposed: Notify your bank and financial institutions. "
            "Monitor your ITR and Form 26AS for unauthorized filings at "
            "https://incometax.gov.in"
        )

    if "IN_CARD" in entity_types:
        advice.append(
            "💳 Card number exposed: Contact your bank IMMEDIATELY to block and reissue the card. "
            "Check recent transactions for unauthorized charges. "
            "File a dispute for any fraudulent transactions."
        )

    if "IN_UPI" in entity_types:
        advice.append(
            "📲 UPI ID exposed: Contact your PSP bank to change your VPA. "
            "Monitor your linked account for unauthorized debit requests."
        )

    if "PHONE_NUMBER_INDIA" in entity_types or "PHONE_NUMBER" in entity_types:
        advice.append(
            "📞 Phone number exposed: Be vigilant about SIM-swap attempts. "
            "Contact your mobile operator to add a port-out protection PIN."
        )

    if "IN_PASSPORT" in entity_types:
        advice.append(
            "🛂 Passport number exposed: Report to the Passport Seva Kendra. "
            "Monitor for fraudulent visa applications. "
            "Consider applying for a new passport if identity fraud is suspected."
        )

    if "IN_ABHA" in entity_types:
        advice.append(
            "🏥 ABHA number exposed: Log into https://healthid.ndhm.gov.in and "
            "audit which healthcare providers have linked to your account. "
            "Revoke any unauthorized links."
        )

    if not advice:
        advice.append(
            "📋 General: Notify affected individuals per applicable data protection regulations "
            "(DPDP Act 2023 if data belongs to Indian residents). "
            "Document the incident with timestamps for compliance records."
        )

    return advice


# ─────────────────────────────────────────────────────────────
# Formatting helpers (for Streamlit display)
# ─────────────────────────────────────────────────────────────

def playbook_to_markdown(playbook: RemediationPlaybook) -> str:
    """Render a playbook as a Markdown string for display in Streamlit."""
    lines = [
        f"# 🛡 Aegis Remediation Playbook",
        f"**Repository:** `{playbook.repo_name}`",
        f"**Exposed files:** {len(playbook.leaked_files)}",
        f"**PII types detected:** {', '.join(playbook.entity_types)}",
        "",
        "---",
        "",
    ]

    for step in playbook.steps:
        lines.append(f"## {step.title}")
        lines.append(step.description)
        lines.append("")
        if step.warning:
            lines.append(f"> ⚠️ **Warning:** {step.warning}")
            lines.append("")
        lines.append("```bash")
        lines.extend(step.commands)
        lines.append("```")
        lines.append("")

    if playbook.general_advice:
        lines.append("---")
        lines.append("## 📋 Post-Incident Actions")
        for advice in playbook.general_advice:
            lines.append(f"- {advice}")
            lines.append("")

    return "\n".join(lines)
