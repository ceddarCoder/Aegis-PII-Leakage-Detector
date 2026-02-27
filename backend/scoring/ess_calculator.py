"""
ess_calculator.py — Exposure Severity Score (ESS) engine.

ESS is a 0–10 score that reflects:
  1. The inherent sensitivity of the data types found
  2. "Toxic combinations" — co-located PII that together enable identity fraud
  3. Exposure radius (public GitHub repo vs. obscure paste)
  4. Validation confidence (mathematically verified vs. regex-only match)
"""

from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────
# Sensitivity weights (base score per entity type, 1–10 scale)
# ─────────────────────────────────────────────────────────────

SENSITIVITY: dict[str, float] = {
    # Biometric / Government ID
    "IN_AADHAAR":         9.0,
    "IN_PASSPORT":        8.5,
    # Tax / Financial identity
    "IN_PAN":             8.0,
    "IN_GSTIN":           6.5,
    # Payment
    "IN_CARD":            9.5,
    "IN_UPI":             5.5,
    # Healthcare
    "IN_ABHA":            8.0,
    # Contact / Identity
    "PHONE_NUMBER_INDIA": 4.5,
    "PHONE_NUMBER":       4.0,
    "EMAIL_ADDRESS":      3.0,
    "PERSON":             2.5,
}

DEFAULT_SENSITIVITY = 2.0


# ─────────────────────────────────────────────────────────────
# Toxic combination multipliers
# ─────────────────────────────────────────────────────────────

# Each entry: (frozenset of entity types, multiplier, label)
# The highest applicable multiplier is used (they don't stack)
TOXIC_COMBOS: list[tuple[frozenset, float, str]] = [
    # Full KYC identity triad
    (frozenset({"IN_AADHAAR", "IN_PAN", "PHONE_NUMBER_INDIA"}), 1.90, "Full KYC triad"),
    # Card + identity = account takeover ready
    (frozenset({"IN_CARD", "IN_AADHAAR"}),                1.85, "Card + Aadhaar"),
    (frozenset({"IN_CARD", "IN_PAN"}),                    1.75, "Card + PAN"),
    # UPI + Phone = live payment vector
    (frozenset({"IN_UPI", "PHONE_NUMBER_INDIA"}),          1.60, "UPI + Phone"),
    # Identity pair
    (frozenset({"IN_AADHAAR", "IN_PAN"}),                 1.55, "Aadhaar + PAN"),
    # Healthcare identity
    (frozenset({"IN_ABHA", "IN_AADHAAR"}),                1.50, "ABHA + Aadhaar"),
    # Email + Phone = social engineering vector
    (frozenset({"EMAIL_ADDRESS", "PHONE_NUMBER_INDIA"}),   1.30, "Email + Phone"),
    # Person name + any government ID
    (frozenset({"PERSON", "IN_AADHAAR"}),                  1.25, "Name + Aadhaar"),
    (frozenset({"PERSON", "IN_PAN"}),                      1.20, "Name + PAN"),
]


# ─────────────────────────────────────────────────────────────
# Exposure radius multipliers
# ─────────────────────────────────────────────────────────────

EXPOSURE_RADIUS: dict[str, float] = {
    "github_public":  1.30,  # Indexed by search engines, highest exposure
    "pastebin":       1.15,  # Public but ephemeral
    "gitlab_public":  1.25,
    "unknown":        1.00,
}


@dataclass
class ESSResult:
    score: float                     # Final ESS (0.0 – 10.0)
    base_score: float                # Before multipliers
    toxic_combo_label: str           # Description of worst toxic combo found
    toxic_multiplier: float          # Applied toxic multiplier
    exposure_multiplier: float       # Applied exposure radius multiplier
    confidence_penalty: float        # Penalty for low-confidence findings
    types_found: list[str]           # Distinct entity types detected
    breakdown: dict = field(default_factory=dict)  # Step-by-step score breakdown


def calculate_ess(
    findings: list[dict],
    source_type: str = "github_public",
) -> ESSResult:
    """
    Calculate the Exposure Severity Score for a set of findings
    from a single source (file, paste, etc.).

    Args:
        findings:    List of finding dicts from presidio_engine.presidio_scan()
        source_type: One of 'github_public', 'pastebin', 'gitlab_public', 'unknown'

    Returns:
        ESSResult dataclass with full scoring breakdown.
    """
    if not findings:
        return ESSResult(
            score=0.0, base_score=0.0,
            toxic_combo_label="none", toxic_multiplier=1.0,
            exposure_multiplier=1.0, confidence_penalty=0.0,
            types_found=[],
            breakdown={"note": "No findings"},
        )

    # ── Step 1: Base score = max sensitivity among found types ──
    types_found = list({f["type"] for f in findings})
    base_score = max(
        SENSITIVITY.get(t, DEFAULT_SENSITIVITY) for t in types_found
    )

    # ── Step 2: Toxic combination multiplier ───────────────────
    types_set = set(types_found)
    best_multiplier = 1.0
    best_label = "none"

    for combo, mult, label in TOXIC_COMBOS:
        if combo.issubset(types_set) and mult > best_multiplier:
            best_multiplier = mult
            best_label = label

    after_toxic = base_score * best_multiplier

    # ── Step 3: Exposure radius multiplier ────────────────────
    exposure_mult = EXPOSURE_RADIUS.get(source_type, 1.0)
    after_exposure = after_toxic * exposure_mult

    # ── Step 4: Confidence penalty ────────────────────────────
    # Average confidence of findings (findings with annotations/downgrades
    # already have reduced confidence from the validator)
    avg_confidence = sum(f["confidence"] for f in findings) / len(findings)
    # Penalty: low-confidence findings reduce the score
    confidence_penalty = round((1.0 - avg_confidence) * 1.5, 3)
    after_penalty = after_exposure - confidence_penalty

    # ── Step 5: Clamp to [0, 10] ──────────────────────────────
    final_score = round(max(0.0, min(10.0, after_penalty)), 2)

    return ESSResult(
        score=final_score,
        base_score=round(base_score, 3),
        toxic_combo_label=best_label,
        toxic_multiplier=round(best_multiplier, 3),
        exposure_multiplier=round(exposure_mult, 3),
        confidence_penalty=round(confidence_penalty, 3),
        types_found=sorted(types_found),
        breakdown={
            "base_score":           round(base_score, 3),
            "after_toxic_combo":    round(after_toxic, 3),
            "after_exposure":       round(after_exposure, 3),
            "confidence_penalty":   round(confidence_penalty, 3),
            "final_score":          final_score,
        },
    )


def ess_label(score: float) -> str:
    """Human-readable severity label for an ESS score."""
    if score >= 9.0:
        return "CRITICAL"
    if score >= 7.0:
        return "HIGH"
    if score >= 5.0:
        return "MEDIUM"
    if score >= 2.5:
        return "LOW"
    return "INFO"


def ess_color(score: float) -> str:
    """Hex color for ESS score (for UI rendering)."""
    if score >= 9.0:
        return "#ff2d2d"
    if score >= 7.0:
        return "#ff6b00"
    if score >= 5.0:
        return "#ffc107"
    if score >= 2.5:
        return "#4fc3f7"
    return "#aaaaaa"


def aggregate_ess(ess_results: list[ESSResult]) -> dict:
    """
    Aggregate ESS results across multiple sources (e.g., all files in a repo).
    Returns a summary dict suitable for the dashboard.
    """
    if not ess_results:
        return {"max_ess": 0.0, "avg_ess": 0.0, "label": "INFO", "color": "#aaaaaa"}

    scores = [r.score for r in ess_results]
    max_score = max(scores)
    avg_score = round(sum(scores) / len(scores), 2)

    all_types: set[str] = set()
    for r in ess_results:
        all_types.update(r.types_found)

    return {
        "max_ess":       max_score,
        "avg_ess":       avg_score,
        "label":         ess_label(max_score),
        "color":         ess_color(max_score),
        "total_sources": len(ess_results),
        "all_types":     sorted(all_types),
    }
