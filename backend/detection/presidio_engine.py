
# import re
# from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern

# from validators import (
#     is_valid_aadhaar,
#     is_valid_pan,
#     is_valid_gstin,
#     is_valid_luhn,
#     is_valid_upi,
#     is_valid_abha,
# )

# # ─────────────────────────────────────────────────────────────
# # File-level pre-screening
# # ─────────────────────────────────────────────────────────────

# _SKIP_FILENAME_RE = re.compile(
#     r"(package-lock\.json|yarn\.lock|poetry\.lock|Pipfile\.lock"
#     r"|composer\.lock|Gemfile\.lock"
#     r"|\.min\.js|\.min\.css|\.map$"
#     r"|/__pycache__/|/\.git/)",
#     re.IGNORECASE,
# )


# def should_skip_file(filename: str, content_sample: str) -> tuple[bool, str]:
#     if _SKIP_FILENAME_RE.search(filename):
#         return True, f"skipped: lock/minified file ({filename})"
#     sample = content_sample[:500]
#     if len(sample) > 50:
#         non_ascii = sum(1 for c in sample if ord(c) > 127)
#         if non_ascii / len(sample) > 0.3:
#             return True, "skipped: likely binary"
#     lines = content_sample[:2000].split("\n")
#     if lines and len(lines[0]) > 2000:
#         return True, "skipped: minified single-line"
#     return False, ""


# # ─────────────────────────────────────────────────────────────
# # Phone number extraction (standalone, strict)
# # ─────────────────────────────────────────────────────────────

# # Prefixed: +91 or 91 followed by 10-digit mobile number (starts 6-9)
# _PHONE_PREFIXED = re.compile(r"(?<![0-9])(?:\+91|91)[\s\-]?([6-9]\d{9})(?!\d)")

# # Bare 10-digit (starts 6-9) — only fires when context keyword is nearby
# _PHONE_BARE = re.compile(r"(?<!\d)([6-9]\d{9})(?!\d)")

# _PHONE_CTX = re.compile(
#     r"\b(phone|mobile|mob|ph|cell|contact|whatsapp|call|sms|tel|no\.?|number)\b",
#     re.IGNORECASE,
# )


# def extract_phone_numbers(text: str) -> list[dict]:
#     results = []
#     seen_spans = set()

#     # Prefixed — always report
#     for m in _PHONE_PREFIXED.finditer(text):
#         if m.span() not in seen_spans:
#             seen_spans.add(m.span())
#             results.append({
#                 "value":      m.group().strip(),
#                 "start":      m.start(),
#                 "end":        m.end(),
#                 "confidence": 0.88,
#             })

#     # Bare — only with context keyword within 80 chars
#     for m in _PHONE_BARE.finditer(text):
#         if any(not (m.end() <= s or m.start() >= e) for s, e in seen_spans):
#             continue
#         window = text[max(0, m.start() - 80): m.end() + 80]
#         if _PHONE_CTX.search(window):
#             seen_spans.add(m.span())
#             results.append({
#                 "value":      m.group().strip(),
#                 "start":      m.start(),
#                 "end":        m.end(),
#                 "confidence": 0.72,
#             })

#     return results


# # ─────────────────────────────────────────────────────────────
# # Aadhaar extraction (standalone — more control than Presidio regex)
# # ─────────────────────────────────────────────────────────────

# # Grouped 4-4-4: any digit as first digit (UIDAI issues 0-9 start in practice)
# # Allow 0-2 spaces or a hyphen between groups
# _AADHAAR_GROUPED = re.compile(r"(?<!\d)\d{4}[ \-]\d{4}[ \-]\d{4}(?!\d)")

# # Solid 12-digit, not preceded by + (phone) and not a phone number itself
# _AADHAAR_SOLID = re.compile(r"(?<![+\d])\d{12}(?!\d)")

# _AADHAAR_CTX = re.compile(
#     r"\b(aadhaar|aadhar|adhar|uidai|uid|enrolment|enrollment)\b",
#     re.IGNORECASE,
# )


# def _is_phone_number(digits12: str) -> bool:
#     """Return True if a 12-digit string looks like 91+mobile."""
#     return digits12.startswith("91") and digits12[2] in "6789"


# def extract_aadhaar(text: str) -> list[dict]:
#     results = []
#     seen_spans: list[tuple[int, int]] = []

#     def _add(value: str, start: int, end: int, base_conf: float):
#         # Skip if overlaps an already-found span
#         if any(not (end <= s or start >= e) for s, e in seen_spans):
#             return

#         raw_digits = re.sub(r"\D", "", value)

#         # 12 digits only
#         if len(raw_digits) != 12:
#             return

#         # Exclude phone numbers
#         if _is_phone_number(raw_digits):
#             return

#         # Verhoeff validation
#         valid = is_valid_aadhaar(raw_digits)
#         if not valid:
#             # Still report if there's an explicit Aadhaar context keyword nearby
#             window = text[max(0, start - 100): end + 100]
#             if not _AADHAAR_CTX.search(window):
#                 return  # no context + invalid checksum → drop
#             conf = 0.45  # low confidence: context match but bad checksum
#             annotation = "Verhoeff checksum failed — possible false positive"
#         else:
#             conf = 0.95
#             annotation = ""

#         # Boost confidence if context keyword present
#         window = text[max(0, start - 100): end + 100]
#         if _AADHAAR_CTX.search(window) and valid:
#             conf = min(conf + 0.03, 0.98)

#         seen_spans.append((start, end))
#         results.append({
#             "value":      value.strip(),
#             "start":      start,
#             "end":        end,
#             "confidence": conf,
#             "annotation": annotation,
#         })

#     # Grouped matches
#     for m in _AADHAAR_GROUPED.finditer(text):
#         _add(m.group(), m.start(), m.end(), 0.80)

#     # Solid matches (only if not already covered by grouped)
#     for m in _AADHAAR_SOLID.finditer(text):
#         _add(m.group(), m.start(), m.end(), 0.65)

#     return results


# # ─────────────────────────────────────────────────────────────
# # Build Presidio Analyzer
# # KEY FIX: Do NOT remove any recognizers.
# # Unwanted entity types are excluded by simply not listing them
# # in the entities= parameter of analyze(). Presidio skips recognizers
# # for entities not in that list — no removal needed.
# # ─────────────────────────────────────────────────────────────

# def _build_analyzer() -> AnalyzerEngine:
#     engine = AnalyzerEngine()
#     # Note: we keep all built-in recognizers intact.
#     # We only REQUEST our custom entities in analyze(), so built-in
#     # PhoneRecognizer, SpacyRecognizer (PERSON), etc. never fire.

#     # ── PAN ───────────────────────────────────────────────────
#     engine.registry.add_recognizer(PatternRecognizer(
#         supported_entity="IN_PAN",
#         patterns=[Pattern("PAN", r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", 0.75)],
#         context=["pan", "permanent account", "income tax", "tds", "form 16",
#                  "pan card", "pancard", "pan no", "pan number", "taxpayer"],
#         supported_language="en",
#     ))

#     # ── GSTIN ─────────────────────────────────────────────────
#     engine.registry.add_recognizer(PatternRecognizer(
#         supported_entity="IN_GSTIN",
#         patterns=[Pattern(
#             "GSTIN",
#             r"\b[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b",
#             0.80,
#         )],
#         context=["gst", "gstin", "goods and service", "tax invoice",
#                  "gstin no", "gst number", "gst registration"],
#         supported_language="en",
#     ))

#     # ── UPI ID (known handles only) ───────────────────────────
#     _UPI_HANDLES = (
#         r"okaxis|oksbi|okicici|okhdfcbank|ybl|ibl|paytm|apl"
#         r"|jupiteraxis|fam|naviaxis|axl|barodampay|cnrb"
#         r"|federal|kotak|rbl|upi|icici|sbi|hdfc|airtel|waicici"
#     )
#     engine.registry.add_recognizer(PatternRecognizer(
#         supported_entity="IN_UPI",
#         patterns=[Pattern(
#             "UPI VPA",
#             rf"\b[a-zA-Z0-9.\-_]{{2,40}}@(?:{_UPI_HANDLES})\b",
#             0.88,
#         )],
#         context=["upi", "gpay", "phonepe", "paytm", "bhim", "transfer", "vpa", "pay"],
#         supported_language="en",
#     ))

#     # ── ABHA ─────────────────────────────────────────────────
#     engine.registry.add_recognizer(PatternRecognizer(
#         supported_entity="IN_ABHA",
#         patterns=[Pattern("ABHA", r"\b\d{2}-\d{4}-\d{4}-\d{4}\b", 0.88)],
#         context=["abha", "ayushman", "health id", "uhid", "abdm", "health account"],
#         supported_language="en",
#     ))

#     # ── Card Number (grouped format strongly preferred) ───────
#     engine.registry.add_recognizer(PatternRecognizer(
#         supported_entity="IN_CARD",
#         patterns=[
#             Pattern("Card 4x4 spaced",  r"\b\d{4}[ \-]\d{4}[ \-]\d{4}[ \-]\d{4}\b", 0.80),
#             Pattern("Card 16d solid",   r"(?<!\d)\d{16}(?!\d)", 0.55),
#         ],
#         context=["card", "visa", "mastercard", "rupay", "maestro",
#                  "cvv", "cvc", "expiry", "exp date", "debit", "credit", "atm"],
#         supported_language="en",
#     ))

#     # ── Indian Passport ───────────────────────────────────────
#     engine.registry.add_recognizer(PatternRecognizer(
#         supported_entity="IN_PASSPORT",
#         patterns=[Pattern("Passport", r"\b[A-PR-WY][1-9]\d{6}\b", 0.72)],
#         context=["passport", "travel document", "republic of india",
#                  "ministry of external affairs", "passport no", "passport number"],
#         supported_language="en",
#     ))

#     return engine


# _ANALYZER = _build_analyzer()

# # Entities we ask Presidio to scan for (Aadhaar and Phone handled separately)
# _PRESIDIO_ENTITIES = [
#     "IN_PAN", "IN_GSTIN", "IN_UPI",
#     "IN_ABHA", "IN_CARD", "IN_PASSPORT",
#     "EMAIL_ADDRESS",
# ]

# _RISK_MAP = {
#     "IN_AADHAAR":  "Critical",
#     "IN_PAN":      "High",
#     "IN_GSTIN":    "High",
#     "IN_CARD":     "Critical",
#     "IN_PASSPORT": "High",
#     "IN_ABHA":     "High",
#     "IN_UPI":      "Medium",
#     "PHONE_NUMBER_INDIA": "Medium",
#     "EMAIL_ADDRESS":      "Low",
# }


# def _classify_risk(entity_type: str) -> str:
#     return _RISK_MAP.get(entity_type, "Low")


# # ─────────────────────────────────────────────────────────────
# # Phase B: Mathematical validation
# # ─────────────────────────────────────────────────────────────

# def _validate(entity_type: str, value: str) -> tuple[bool, float | None, str]:
#     if entity_type == "IN_PAN":
#         return (True, 0.90, "") if is_valid_pan(value) else (False, None, "PAN structure invalid")

#     if entity_type == "IN_GSTIN":
#         return (True, 0.88, "") if is_valid_gstin(value) else (False, None, "GSTIN invalid")

#     if entity_type == "IN_CARD":
#         digits = re.sub(r"[\s\-]", "", value)
#         return (True, 0.85, "") if is_valid_luhn(digits) else (False, None, "Luhn check failed")

#     if entity_type == "IN_UPI":
#         return (True, None, "") if is_valid_upi(value) else (False, None, "UPI format invalid")

#     if entity_type == "IN_ABHA":
#         return (True, 0.90, "") if is_valid_abha(value) else (False, None, "ABHA format invalid")

#     return True, None, ""


# # ─────────────────────────────────────────────────────────────
# # Public API
# # ─────────────────────────────────────────────────────────────

# def presidio_scan(
#     text: str,
#     filename: str = "",
#     language: str = "en",
#     chunk_size: int = 300_000,
# ) -> list[dict]:
#     if not text or not text.strip():
#         return []

#     skip, reason = should_skip_file(filename, text)
#     if skip:
#         return []

#     if len(text) > chunk_size:
#         findings = []
#         for offset in range(0, len(text), chunk_size):
#             chunk = text[offset: offset + chunk_size]
#             for f in presidio_scan(chunk, filename, language, chunk_size):
#                 f["start"] += offset
#                 f["end"]   += offset
#                 findings.append(f)
#         return _deduplicate(findings)

#     findings: list[dict] = []

#     # ── Aadhaar (standalone extractor) ───────────────────────
#     for item in extract_aadhaar(text):
#         findings.append(_make_finding(
#             "IN_AADHAAR",
#             item["value"],
#             item["confidence"],
#             item.get("annotation", ""),
#             text, item["start"], item["end"],
#         ))

#     # ── Phone (standalone extractor) ─────────────────────────
#     for item in extract_phone_numbers(text):
#         findings.append(_make_finding(
#             "PHONE_NUMBER_INDIA",
#             item["value"],
#             item["confidence"],
#             "",
#             text, item["start"], item["end"],
#         ))

#     # ── Presidio-managed entities ─────────────────────────────
#     raw_results = _ANALYZER.analyze(
#         text=text,
#         entities=_PRESIDIO_ENTITIES,
#         language=language,
#         score_threshold=0.50,
#     )

#     for res in raw_results:
#         entity_type = res.entity_type
#         value       = text[res.start: res.end]
#         base_conf   = round(res.score, 3)

#         valid, adj_conf, annotation = _validate(entity_type, value)
#         if not valid:
#             continue  # hard drop

#         confidence = adj_conf if adj_conf is not None else base_conf
#         findings.append(_make_finding(entity_type, value, confidence, annotation, text, res.start, res.end))

#     findings.sort(key=lambda x: x["confidence"], reverse=True)
#     return _deduplicate(findings)


# def _make_finding(entity_type, value, confidence, annotation, text, start, end) -> dict:
#     s = max(0, start - 80)
#     e = min(len(text), end + 80)
#     snippet = text[s:e].replace("\n", " ").strip()

#     v = value.strip()
#     masked = (v[:4] + "****" + v[-4:]) if len(v) > 8 else (v[:2] + "****")

#     return {
#         "type":         entity_type,
#         "value":        v,
#         "value_masked": masked,
#         "snippet":      snippet,
#         "confidence":   round(confidence, 3),
#         "risk":         _classify_risk(entity_type),
#         "annotation":   annotation,
#         "start":        start,
#         "end":          end,
#     }


# def _deduplicate(findings: list[dict]) -> list[dict]:
#     findings = sorted(findings, key=lambda x: x["confidence"], reverse=True)
#     seen: list[tuple[int, int]] = []
#     out = []
#     for f in findings:
#         s, e = f["start"], f["end"]
#         if not any(not (e <= ss or s >= se) for ss, se in seen):
#             seen.append((s, e))
#             out.append(f)
#     return out


"""
presidio_engine.py — Wrapper around hybrid_scanner with file screening, chunking,
and output formatting compatible with the Aegis app.
"""

import re
from backend.detection.hybrid_scanner import hybrid_scan

# ─────────────────────────────────────────────────────────────
# File-level pre-screening (unchanged from original)
# ─────────────────────────────────────────────────────────────

_SKIP_FILENAME_RE = re.compile(
    r"(package-lock\.json|yarn\.lock|poetry\.lock|Pipfile\.lock"
    r"|composer\.lock|Gemfile\.lock"
    r"|\.min\.js|\.min\.css|\.map$"
    r"|/__pycache__/|/\.git/)",
    re.IGNORECASE,
)

def should_skip_file(filename: str, content_sample: str) -> tuple[bool, str]:
    if _SKIP_FILENAME_RE.search(filename):
        return True, f"skipped: lock/minified file ({filename})"
    sample = content_sample[:500]
    if len(sample) > 50:
        non_ascii = sum(1 for c in sample if ord(c) > 127)
        if non_ascii / len(sample) > 0.3:
            return True, "skipped: likely binary"
    lines = content_sample[:2000].split("\n")
    if lines and len(lines[0]) > 2000:
        return True, "skipped: minified single-line"
    return False, ""

# In presidio_engine.py, replace the risk map with:

_RISK_MAP = {
    "AADHAAR":      "Critical",
    "PAN":          "High",
    "GSTIN":        "High",
    "PASSPORT_IN":  "High",
    "VOTER_ID":     "Medium",
    "DL_IN":        "Medium",
    "SSN":          "Critical",
    "CREDIT_CARD":  "Critical",
    "IFSC":         "Low",
    "EMAIL":        "Low",
    "PHONE":        "Medium",
    "UPI":          "Medium",
    "ABHA":         "High",
}

def _classify_risk(entity_type: str, severity: str | None = None) -> str:
    if severity == "CONFIRMED_LEAK":
        return "Critical"
    if severity == "PROBABLE_LEAK":
        return "High"
    return _RISK_MAP.get(entity_type, "Low")

# ─────────────────────────────────────────────────────────────
# Output formatting helpers
# ─────────────────────────────────────────────────────────────

def _make_finding(item: dict, text: str) -> dict:
    """Convert hybrid_scanner output to app schema."""
    s = max(0, item["start"] - 80)
    e = min(len(text), item["end"] + 80)
    snippet = text[s:e].replace("\n", " ").strip()

    value = item["value"].strip()
    masked = (value[:4] + "****" + value[-4:]) if len(value) > 8 else (value[:2] + "****")

    return {
        "type":         item["type"],
        "value":        value,
        "value_masked": masked,
        "snippet":      snippet,
        "confidence":   round(item["risk_score"], 3),
        "risk":         _classify_risk(item["type"], item.get("severity")),
        "annotation":   item.get("decision", ""),
        "start":        item["start"],
        "end":          item["end"],
    }

def _deduplicate(findings: list[dict]) -> list[dict]:
    findings = sorted(findings, key=lambda x: x["confidence"], reverse=True)
    seen: list[tuple[int, int]] = []
    out = []
    for f in findings:
        s, e = f["start"], f["end"]
        if not any(not (e <= ss or s >= se) for ss, se in seen):
            seen.append((s, e))
            out.append(f)
    return out

# ─────────────────────────────────────────────────────────────
# Public API (now with use_nlp parameter)
# ─────────────────────────────────────────────────────────────

def presidio_scan(
    text: str,
    filename: str = "",
    language: str = "en",          # kept for compatibility, unused
    chunk_size: int = 300_000,
    use_nlp: bool = False,         # new parameter
) -> list[dict]:
    """
    Scan text for PII.
    - use_nlp: if True, run full NLI (slower); if False, fast regex+validators.
    """
    if not text or not text.strip():
        return []

    skip, reason = should_skip_file(filename, text)
    if skip:
        return []

    # Chunk large texts
    if len(text) > chunk_size:
        findings = []
        for offset in range(0, len(text), chunk_size):
            chunk = text[offset: offset + chunk_size]
            for f in presidio_scan(chunk, filename, language, chunk_size, use_nlp):
                f["start"] += offset
                f["end"]   += offset
                findings.append(f)
        return _deduplicate(findings)

    # Run the hybrid scanner
    raw_findings = hybrid_scan(text, use_nli=use_nlp)

    # Transform to app schema
    findings = [_make_finding(item, text) for item in raw_findings]

    return _deduplicate(findings)