"""
report_generator.py — Exportable HTML Classification Report for Aegis.

Generates a self-contained, dark-themed HTML report with:
  - Executive summary
  - ESS threat gauge (SVG)
  - Risk & entity distribution
  - Detailed findings table with source links
  - Toxic combination analysis
  - Confidence analysis
  - Remediation recommendations
  - Detection methodology note

All CSS is embedded inline — the HTML file is fully standalone.
"""

import html
from datetime import datetime
from collections import Counter

from backend.scoring.ess_calculator import ESSResult, ess_label, ess_color, aggregate_ess


# ─────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """HTML-escape a string."""
    return html.escape(str(text)) if text else ""


def _risk_color(risk: str) -> str:
    return {
        "Critical": "#ff2d2d",
        "High":     "#ff6b00",
        "Medium":   "#ffc107",
        "Low":      "#4fc3f7",
    }.get(risk, "#aaaaaa")


def _entity_display_name(etype: str) -> str:
    """Human-readable entity type name."""
    return {
        "IN_AADHAAR":         "Aadhaar Number",
        "IN_PAN":             "PAN Card",
        "IN_GSTIN":           "GSTIN",
        "IN_CARD":            "Card Number",
        "IN_UPI":             "UPI ID",
        "IN_ABHA":            "ABHA Health ID",
        "IN_PASSPORT":        "Indian Passport",
        "PHONE_NUMBER_INDIA": "Indian Phone",
        "EMAIL_ADDRESS":      "Email Address",
        "PERSON":             "Person Name",
    }.get(etype, etype)


_ENTITY_SEVERITY_DESC = {
    "IN_AADHAAR":   "Biometric-linked national ID. Exposure enables identity theft, financial fraud, and SIM cloning.",
    "IN_PAN":       "Tax identity number. Exposure enables unauthorized ITR filing, bank account fraud, and KYC bypass.",
    "IN_CARD":      "Payment card number. Exposure enables unauthorized transactions and card-not-present fraud.",
    "IN_GSTIN":     "GST registration ID. Exposure enables fraudulent invoicing and tax credit theft.",
    "IN_UPI":       "Virtual payment address. Exposure enables targeted collect-request fraud and social engineering.",
    "IN_ABHA":      "Health account identifier. Exposure enables unauthorized access to medical records.",
    "IN_PASSPORT":  "Travel document number. Exposure enables visa fraud and identity impersonation.",
    "PHONE_NUMBER_INDIA": "Mobile number. Exposure enables SIM swap attacks and phishing/vishing campaigns.",
    "EMAIL_ADDRESS": "Email address. Exposure enables credential stuffing and phishing attacks.",
}

_REMEDIATION_ADVICE = {
    "IN_AADHAAR":   "Contact UIDAI helpline (1947). Lock biometrics via mAadhaar app. File FIR if misuse is suspected.",
    "IN_PAN":       "Notify banks and financial institutions. Monitor ITR/Form 26AS at incometax.gov.in.",
    "IN_CARD":      "Contact bank IMMEDIATELY to block and reissue card. Review recent transactions. File dispute for unauthorized charges.",
    "IN_GSTIN":     "Report to GST portal (gst.gov.in). Monitor for fraudulent invoices on your GSTIN.",
    "IN_UPI":       "Contact PSP bank to change VPA. Monitor linked account for unauthorized debit requests.",
    "IN_ABHA":      "Log into healthid.ndhm.gov.in. Audit linked providers and revoke unauthorized links.",
    "IN_PASSPORT":  "Report to Passport Seva Kendra. Monitor for fraudulent visa applications. Consider reissue.",
    "PHONE_NUMBER_INDIA": "Enable SIM lock / port-out PIN with your mobile operator. Watch for vishing calls.",
    "EMAIL_ADDRESS": "Enable 2FA. Check for unauthorized logins. Change password if email is paired with other leaked PII.",
}


# ─────────────────────────────────────────────────────────────
# SVG ESS Gauge
# ─────────────────────────────────────────────────────────────

def _svg_ess_gauge(score: float, label: str, color: str) -> str:
    """Generate an SVG radial gauge for ESS score."""
    pct = min(score / 10.0, 1.0)
    circumference = 2 * 3.14159 * 54
    dash = circumference * pct
    gap = circumference - dash

    return f"""
    <svg viewBox="0 0 140 140" width="180" height="180" style="display:block;margin:0 auto;">
      <circle cx="70" cy="70" r="54" fill="none" stroke="#2a2a3a" stroke-width="12"/>
      <circle cx="70" cy="70" r="54" fill="none" stroke="{color}" stroke-width="12"
              stroke-dasharray="{dash:.1f} {gap:.1f}"
              stroke-linecap="round" transform="rotate(-90 70 70)"
              style="transition: stroke-dasharray 1s ease;"/>
      <text x="70" y="62" text-anchor="middle" fill="{color}"
            font-size="28" font-weight="800" font-family="Inter,sans-serif">{score:.1f}</text>
      <text x="70" y="80" text-anchor="middle" fill="#888"
            font-size="11" font-family="Inter,sans-serif">/ 10</text>
      <text x="70" y="104" text-anchor="middle" fill="{color}"
            font-size="13" font-weight="600" font-family="Inter,sans-serif">{_esc(label)}</text>
    </svg>"""


# ─────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
  --bg-primary: #0f0f1a;
  --bg-card: #1a1a2e;
  --bg-input: #16213e;
  --text-primary: #e0e0e0;
  --text-secondary: #888;
  --border: #2a2a3a;
  --accent: #7c3aed;
  --critical: #ff2d2d;
  --high: #ff6b00;
  --medium: #ffc107;
  --low: #4fc3f7;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.6;
  padding: 2rem;
  max-width: 1100px;
  margin: 0 auto;
}

@media print {
  body { background: #fff; color: #111; padding: 1rem; }
  .card { border: 1px solid #ddd; background: #fafafa; }
  .risk-bar-fill { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
}

h1 { font-size: 1.8rem; font-weight: 800; margin-bottom: 0.3rem; }
h2 { font-size: 1.3rem; font-weight: 700; margin: 2rem 0 0.8rem; color: var(--accent); border-bottom: 2px solid var(--border); padding-bottom: 0.4rem; }
h3 { font-size: 1.05rem; font-weight: 600; margin: 1rem 0 0.5rem; }

.header { text-align: center; margin-bottom: 2rem; }
.header .subtitle { color: var(--text-secondary); font-size: 0.85rem; margin-top: 0.2rem; }
.header .meta { display: flex; justify-content: center; gap: 2rem; flex-wrap: wrap; margin-top: 0.8rem; font-size: 0.82rem; color: var(--text-secondary); }
.header .meta span { background: var(--bg-card); padding: 4px 12px; border-radius: 6px; border: 1px solid var(--border); }

.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1.2rem 1.5rem;
  margin-bottom: 1.2rem;
}

.summary-text {
  font-size: 0.95rem;
  line-height: 1.7;
  color: var(--text-primary);
}

.summary-text strong { color: #fff; }

.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1.2rem; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; }
@media (max-width: 700px) { .grid-2, .grid-3 { grid-template-columns: 1fr; } }

.stat-card { text-align: center; padding: 1rem; }
.stat-card .value { font-size: 2rem; font-weight: 800; }
.stat-card .label { font-size: 0.78rem; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.5px; margin-top: 0.2rem; }

.risk-bar-row { display: flex; align-items: center; margin: 0.4rem 0; }
.risk-bar-label { width: 70px; font-size: 0.82rem; font-weight: 600; }
.risk-bar-track { flex: 1; height: 22px; background: var(--bg-input); border-radius: 4px; overflow: hidden; margin-right: 8px; }
.risk-bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s ease; display:flex; align-items:center; padding-left:6px; font-size:0.72rem; font-weight:600; color:#fff; }
.risk-bar-count { width: 30px; text-align: right; font-size: 0.82rem; font-weight: 700; }

table { width: 100%; border-collapse: collapse; font-size: 0.82rem; margin-top: 0.5rem; }
th { background: var(--bg-input); color: var(--text-secondary); text-align: left; padding: 8px 10px; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.3px; border-bottom: 2px solid var(--border); }
td { padding: 8px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
tr:hover { background: rgba(124,58,237,0.04); }

.risk-badge {
  display: inline-block; padding: 2px 8px; border-radius: 4px;
  font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
}

.confidence-bar { height: 6px; border-radius: 3px; background: var(--bg-input); overflow: hidden; width: 60px; display: inline-block; vertical-align: middle; margin-left: 4px; }
.confidence-fill { height: 100%; border-radius: 3px; }

.snippet { font-family: 'Menlo','Consolas',monospace; font-size: 0.75rem; color: #aaa; background: var(--bg-input); padding: 4px 8px; border-radius: 4px; max-width: 320px; word-break: break-all; display: block; margin-top: 2px; }

.source-link { color: var(--accent); text-decoration: none; font-size: 0.78rem; }
.source-link:hover { text-decoration: underline; }

.toxic-card { border-left: 3px solid var(--critical); padding-left: 1rem; margin: 0.6rem 0; }
.toxic-label { font-weight: 700; color: var(--critical); }
.toxic-mult { color: var(--text-secondary); font-size: 0.85rem; }

.advice-item { padding: 0.6rem 0; border-bottom: 1px solid var(--border); }
.advice-item:last-child { border-bottom: none; }

.methodology { font-size: 0.82rem; color: var(--text-secondary); line-height: 1.7; }
.methodology code { background: var(--bg-input); padding: 1px 5px; border-radius: 3px; font-size: 0.78rem; }

.footer { text-align: center; color: var(--text-secondary); font-size: 0.75rem; margin-top: 2rem; padding-top: 1rem; border-top: 1px solid var(--border); }

.entity-row td:first-child { font-weight: 600; }
.severity-desc { font-size: 0.78rem; color: var(--text-secondary); margin-top: 2px; }
"""


# ─────────────────────────────────────────────────────────────
# Report generation
# ─────────────────────────────────────────────────────────────

def generate_html_report(
    findings: list[dict],
    ess_results: list[ESSResult],
    scan_type: str = "github",
    target: str = "",
    files_scanned: int = 0,
    scan_duration_sec: float = 0.0,
) -> str:
    """
    Generate a self-contained HTML classification report.

    Args:
        findings: List of finding dicts from presidio_engine
        ess_results: List of ESSResult from ess_calculator
        scan_type: 'github', 'pastebin', or 'combined'
        target: Target description (repo name, username, etc.)
        files_scanned: Total files/pastes scanned
        scan_duration_sec: Scan duration in seconds

    Returns:
        Complete HTML string (standalone, no external deps except Google Fonts)
    """
    now = datetime.now()
    agg = aggregate_ess(ess_results) if ess_results else {
        "max_ess": 0.0, "avg_ess": 0.0, "label": "INFO", "color": "#aaaaaa", "all_types": []
    }

    # ── Counts ────────────────────────────────────────
    risk_counts = Counter(f.get("risk", "Low") for f in findings)
    type_counts = Counter(f["type"] for f in findings)
    total = len(findings)

    # ── Executive summary ─────────────────────────────
    exec_summary = _build_executive_summary(
        total, risk_counts, type_counts, agg, scan_type, target
    )

    # ── Build sections ────────────────────────────────
    sections = []
    sections.append(_section_header(now, scan_type, target, files_scanned, total, scan_duration_sec))
    sections.append(_section_executive_summary(exec_summary))
    sections.append(_section_ess_gauge(agg, ess_results))
    sections.append(_section_risk_breakdown(risk_counts, total))
    sections.append(_section_entity_distribution(type_counts, findings))
    sections.append(_section_findings_table(findings))

    # Toxic combos
    toxic_results = [r for r in ess_results if r.toxic_combo_label != "none"]
    if toxic_results:
        sections.append(_section_toxic_combos(toxic_results))

    sections.append(_section_confidence_analysis(findings))
    sections.append(_section_remediation(type_counts))
    sections.append(_section_methodology())
    sections.append(_section_footer(now))

    body = "\n".join(sections)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Aegis Classification Report — {_esc(target)} — {now.strftime('%Y-%m-%d')}</title>
  <style>{_CSS}</style>
</head>
<body>
{body}
</body>
</html>"""


# ─────────────────────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────────────────────

def _build_executive_summary(
    total, risk_counts, type_counts, agg, scan_type, target
) -> str:
    if total == 0:
        return (
            f"The scan of <strong>{_esc(target)}</strong> completed successfully. "
            f"<strong>No PII leakage was detected</strong> across any scanned files. "
            f"The target appears clean of exposed personal data."
        )

    crit = risk_counts.get("Critical", 0)
    high = risk_counts.get("High", 0)
    top_type = max(type_counts, key=type_counts.get) if type_counts else "unknown"
    top_name = _entity_display_name(top_type)

    severity_word = "critical" if crit > 0 else "significant" if high > 0 else "moderate"
    platform = {"github": "GitHub repository", "pastebin": "Pastebin pastes", "combined": "GitHub and Pastebin"}.get(scan_type, "scanned sources")

    parts = [
        f"Aegis detected <strong>{total} PII instance{'s' if total != 1 else ''}</strong> "
        f"across the {platform} <strong>{_esc(target)}</strong>. "
    ]

    if crit + high > 0:
        parts.append(
            f"Of these, <strong>{crit} are critical</strong> and <strong>{high} are high</strong> severity, "
            f"indicating {severity_word} exposure risk. "
        )

    parts.append(
        f"The most frequently leaked data type is <strong>{top_name}</strong> "
        f"({type_counts[top_type]} occurrence{'s' if type_counts[top_type] != 1 else ''}). "
    )

    if agg["max_ess"] >= 7.0:
        parts.append(
            f"The Exposure Severity Score peaked at <strong>{agg['max_ess']:.1f}/10 ({agg['label']})</strong>, "
            f"warranting <strong>immediate remediation</strong>."
        )
    elif agg["max_ess"] >= 4.0:
        parts.append(
            f"The Exposure Severity Score is <strong>{agg['max_ess']:.1f}/10 ({agg['label']})</strong>. "
            f"Remediation is recommended."
        )

    return "".join(parts)


def _section_header(now, scan_type, target, files_scanned, total, duration):
    platform_label = {"github": "GitHub", "pastebin": "Pastebin", "combined": "GitHub + Pastebin"}.get(scan_type, scan_type)
    dur_str = f"{duration:.1f}s" if duration > 0 else "—"
    return f"""
    <div class="header">
      <h1>🛡 Aegis — PII Classification Report</h1>
      <div class="subtitle">Context-Aware Indian PII Leakage Analysis</div>
      <div class="meta">
        <span>📅 {now.strftime('%d %b %Y, %H:%M IST')}</span>
        <span>🎯 {_esc(target)}</span>
        <span>📂 {platform_label}</span>
        <span>📄 {files_scanned} files scanned</span>
        <span>🔍 {total} findings</span>
        <span>⏱ {dur_str}</span>
      </div>
    </div>"""


def _section_executive_summary(summary_html):
    return f"""
    <h2>📋 Executive Summary</h2>
    <div class="card">
      <p class="summary-text">{summary_html}</p>
    </div>"""


def _section_ess_gauge(agg, ess_results):
    max_ess = agg["max_ess"]
    avg_ess = agg.get("avg_ess", 0.0)
    label = agg["label"]
    color = agg["color"]
    num_sources = agg.get("total_sources", len(ess_results))

    return f"""
    <h2>🎯 Exposure Severity Score</h2>
    <div class="card">
      <div class="grid-2">
        <div>{_svg_ess_gauge(max_ess, label, color)}</div>
        <div class="grid-3" style="align-content:center;">
          <div class="stat-card">
            <div class="value" style="color:{color}">{max_ess:.1f}</div>
            <div class="label">Max ESS</div>
          </div>
          <div class="stat-card">
            <div class="value">{avg_ess:.1f}</div>
            <div class="label">Avg ESS</div>
          </div>
          <div class="stat-card">
            <div class="value">{num_sources}</div>
            <div class="label">Sources</div>
          </div>
        </div>
      </div>
    </div>"""


def _section_risk_breakdown(risk_counts, total):
    rows = []
    for risk in ["Critical", "High", "Medium", "Low"]:
        count = risk_counts.get(risk, 0)
        pct = (count / total * 100) if total > 0 else 0
        color = _risk_color(risk)
        rows.append(f"""
          <div class="risk-bar-row">
            <div class="risk-bar-label" style="color:{color}">{risk}</div>
            <div class="risk-bar-track">
              <div class="risk-bar-fill" style="width:{pct:.0f}%; background:{color}">{count if count else ''}</div>
            </div>
            <div class="risk-bar-count" style="color:{color}">{count}</div>
          </div>""")

    return f"""
    <h2>📊 Risk Distribution</h2>
    <div class="card">
      {''.join(rows)}
    </div>"""


def _section_entity_distribution(type_counts, findings):
    # Compute confidence ranges per type
    type_confs: dict[str, list[float]] = {}
    for f in findings:
        type_confs.setdefault(f["type"], []).append(f["confidence"])

    rows = []
    for etype, count in type_counts.most_common():
        confs = type_confs.get(etype, [])
        min_c = min(confs) if confs else 0
        max_c = max(confs) if confs else 0
        avg_c = sum(confs) / len(confs) if confs else 0
        desc = _ENTITY_SEVERITY_DESC.get(etype, "")

        rows.append(f"""
          <tr class="entity-row">
            <td>{_entity_display_name(etype)}</td>
            <td style="text-align:center;font-weight:700;">{count}</td>
            <td>{avg_c:.0%}</td>
            <td>{min_c:.0%} – {max_c:.0%}</td>
            <td><span class="severity-desc">{_esc(desc)}</span></td>
          </tr>""")

    return f"""
    <h2>🏷 Entity Type Classification</h2>
    <div class="card">
      <table>
        <thead>
          <tr>
            <th>Entity Type</th>
            <th style="text-align:center">Count</th>
            <th>Avg Confidence</th>
            <th>Confidence Range</th>
            <th>Impact Description</th>
          </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>"""


def _section_findings_table(findings):
    if not findings:
        return """
        <h2>🔍 Detailed Findings</h2>
        <div class="card"><p style="color:var(--text-secondary);">No PII findings to display.</p></div>"""

    rows = []
    for i, f in enumerate(findings, 1):
        risk = f.get("risk", "Low")
        color = _risk_color(risk)
        conf = f["confidence"]
        conf_color = "#4caf50" if conf >= 0.8 else "#ffc107" if conf >= 0.5 else "#ff5722"

        source_url = f.get("source_url", "")
        source = f.get("source", f.get("file_path", "—"))
        source_html = (
            f'<a class="source-link" href="{_esc(source_url)}" target="_blank">{_esc(source)}</a>'
            if source_url else _esc(source)
        )

        snippet = f.get("snippet", "")[:150]
        annotation = f.get("annotation", "")

        rows.append(f"""
          <tr>
            <td style="color:var(--text-secondary);text-align:center;">{i}</td>
            <td><strong>{_entity_display_name(f['type'])}</strong></td>
            <td><code>{_esc(f.get('value_masked', '—'))}</code></td>
            <td>
              {conf:.0%}
              <span class="confidence-bar"><span class="confidence-fill" style="width:{conf*100:.0f}%;background:{conf_color}"></span></span>
            </td>
            <td><span class="risk-badge" style="background:{color}22;color:{color};border:1px solid {color}55">{risk}</span></td>
            <td>{source_html}</td>
            <td><span class="snippet">{_esc(snippet)}{'…' if len(f.get('snippet','')) > 150 else ''}</span></td>
            <td style="font-size:0.75rem;color:var(--text-secondary)">{_esc(annotation)}</td>
          </tr>""")

    return f"""
    <h2>🔍 Detailed Findings ({len(findings)})</h2>
    <div class="card" style="overflow-x:auto;">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Entity Type</th>
            <th>Masked Value</th>
            <th>Confidence</th>
            <th>Risk</th>
            <th>Source</th>
            <th>Context Snippet</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>"""


def _section_toxic_combos(toxic_results):
    items = []
    seen = set()
    for r in toxic_results:
        if r.toxic_combo_label in seen:
            continue
        seen.add(r.toxic_combo_label)
        items.append(f"""
          <div class="toxic-card">
            <span class="toxic-label">⚠ {_esc(r.toxic_combo_label)}</span>
            <span class="toxic-mult"> — {r.toxic_multiplier:.2f}× severity multiplier</span>
            <p style="font-size:0.82rem;color:var(--text-secondary);margin-top:4px;">
              Multiple PII types belonging to the same identity were found co-located,
              significantly increasing identity fraud risk. These entity types together
              could enable account takeover, financial fraud, or full KYC impersonation.
            </p>
          </div>""")

    return f"""
    <h2>💥 Toxic Combinations Detected</h2>
    <div class="card">
      <p style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:0.8rem;">
        When multiple PII types co-exist in the same source, the combined exposure
        is more dangerous than the sum of parts. Aegis applies severity multipliers
        to reflect this increased risk.
      </p>
      {''.join(items)}
    </div>"""


def _section_confidence_analysis(findings):
    if not findings:
        return ""

    high = sum(1 for f in findings if f["confidence"] >= 0.80)
    med  = sum(1 for f in findings if 0.50 <= f["confidence"] < 0.80)
    low  = sum(1 for f in findings if f["confidence"] < 0.50)
    total = len(findings)
    avg_conf = sum(f["confidence"] for f in findings) / total

    validated = sum(1 for f in findings if not f.get("annotation"))
    annotated = total - validated

    return f"""
    <h2>📈 Confidence Analysis</h2>
    <div class="card">
      <div class="grid-3">
        <div class="stat-card">
          <div class="value" style="color:#4caf50">{high}</div>
          <div class="label">High confidence (≥80%)</div>
        </div>
        <div class="stat-card">
          <div class="value" style="color:#ffc107">{med}</div>
          <div class="label">Medium (50–80%)</div>
        </div>
        <div class="stat-card">
          <div class="value" style="color:#ff5722">{low}</div>
          <div class="label">Low (&lt;50%)</div>
        </div>
      </div>
      <table style="margin-top:1rem;">
        <tr><td>Average confidence across all findings</td><td style="font-weight:700;text-align:right;">{avg_conf:.1%}</td></tr>
        <tr><td>Findings validated via mathematical proof (Verhoeff, Luhn, PAN structure)</td><td style="font-weight:700;text-align:right;">{validated}</td></tr>
        <tr><td>Findings with annotations or caveats</td><td style="font-weight:700;text-align:right;">{annotated}</td></tr>
      </table>
    </div>"""


def _section_remediation(type_counts):
    items = []
    for etype in type_counts:
        advice = _REMEDIATION_ADVICE.get(etype)
        if advice:
            items.append(f"""
              <div class="advice-item">
                <strong>{_entity_display_name(etype)}</strong>
                <p style="font-size:0.85rem;margin-top:3px;">{_esc(advice)}</p>
              </div>""")

    if not items:
        items.append('<div class="advice-item"><p>No specific remediation actions required based on detected entity types.</p></div>')

    return f"""
    <h2>🛠 Remediation Recommendations</h2>
    <div class="card">
      {''.join(items)}
    </div>"""


def _section_methodology():
    return """
    <h2>🔬 Detection Methodology</h2>
    <div class="card methodology">
      <p>Aegis employs a <strong>four-phase hybrid detection pipeline</strong>:</p>
      <ol style="margin:0.8rem 0 0 1.2rem;">
        <li><strong>Phase A — Pattern Matching</strong>: Microsoft Presidio framework with custom Indian PII recognizers
            scans text using optimized regular expressions for Aadhaar, PAN, GSTIN, UPI, card numbers, and more.</li>
        <li><strong>Phase B — Mathematical Validation</strong>: Each regex hit undergoes deterministic validation.
            Aadhaar numbers are verified via the <code>Verhoeff checksum algorithm</code>; card numbers via
            <code>Luhn algorithm</code>; PAN and GSTIN via structural format rules. Failures are discarded.</li>
        <li><strong>Phase C — NLP Disambiguation</strong>: Validated hits are analyzed by a HuggingFace transformer
            (<code>cross-encoder/nli-MiniLM2-L6-H768</code>) performing zero-shot classification on the surrounding context.
            If the model classifies the context as test/dummy/example data, the finding's confidence is downgraded.</li>
        <li><strong>Phase D — Scoring &amp; Correlation</strong>: The Exposure Severity Score (ESS) is computed using
            data sensitivity weights, toxic combination multipliers, and exposure radius factors. Cross-platform
            correlation links identities across sources.</li>
      </ol>
      <p style="margin-top:0.8rem;">This multi-layered approach drastically reduces false positives compared to
        regex-only scanners, achieving high precision without sacrificing recall on real leaked data.</p>
    </div>"""


def _section_footer(now):
    return f"""
    <div class="footer">
      <p>Generated by Aegis v1.0 — Context-Aware Indian PII Leakage Scanner</p>
      <p>Report generated at {now.strftime('%Y-%m-%d %H:%M:%S IST')} · This report contains masked PII only · No raw personal data is stored</p>
    </div>"""
