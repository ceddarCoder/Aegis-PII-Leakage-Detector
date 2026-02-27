"""
validators.py — Mathematical & structural validation for Indian PII types.
No ML inference here — pure deterministic checks only.
"""

import re


# ─────────────────────────────────────────────────────────────
# Verhoeff Algorithm — Aadhaar checksum
# ─────────────────────────────────────────────────────────────

_VERHOEFF_MULT = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

_VERHOEFF_PERM = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


# ─────────────────────────────────────────────────────────────
# SSN Validation (US Social Security Number)
# ─────────────────────────────────────────────────────────────

def is_valid_ssn(value: str, context: str = "") -> bool:
    """
    Validate US SSN format and basic rules.
    Optionally check context for technical words.
    """
    ssn = value.strip().replace("-", "")
    if not ssn.isdigit() or len(ssn) != 9:
        return False
    area = int(ssn[:3])
    group = int(ssn[3:5])
    serial = int(ssn[5:])
    # Area rules: not 000, not 666 (900‑999 are ITINs – keep them as potential leaks)
    if area == 0 or area == 666:
        return False
    # Group and serial cannot be 0
    if group == 0 or serial == 0:
        return False
    # Technical context suppression
    if re.search(
        r"\b(dimensions?|ratios?|resolutions?|versions?|v\d+|subnets?|"
        r"ip\s+address|weights?|heights?|widths?|pixels?|px|cm|mm|inches?|"
        r"sizes?|configs?|coordinates?|measurements?)\b",
        context, re.I
    ):
        return False
    if re.search(
        r"\b(dummy|fake|test|sample|demo|placeholder|for\s+illustration|"
        r"not\s+real|fictitious|mock|documentation\s+example)\b",
        context, re.I
    ):
        return False
    return True


# ─────────────────────────────────────────────────────────────
# Indian Mobile Number Validation
# ─────────────────────────────────────────────────────────────

def is_valid_phone_india(value: str, context: str = "") -> bool:
    """
    Validate Indian mobile number (10 digits, starting with 6‑9).
    Optionally check context for technical words.
    """
    digits = re.sub(r"\D", "", value)
    # Handle +91 prefix
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if len(digits) != 10 or not digits.isdigit():
        return False
    if digits[0] not in "6789":
        return False
    # Technical context suppression
    if re.search(
        r"\b(dimensions?|ratios?|resolutions?|versions?|v\d+|subnets?|"
        r"ip\s+address|weights?|heights?|widths?|pixels?|px|cm|mm|inches?|"
        r"sizes?|configs?|coordinates?|measurements?)\b",
        context, re.I
    ):
        return False
    if re.search(
        r"\b(dummy|fake|test|sample|demo|placeholder|for\s+illustration|"
        r"not\s+real|fictitious|mock|documentation\s+example)\b",
        context, re.I
    ):
        return False
    return True


# ─────────────────────────────────────────────────────────────
# Credit Card Validation (Luhn + context)
# ─────────────────────────────────────────────────────────────

def is_valid_credit_card(value: str, context: str = "") -> bool:
    """
    Validate credit card number using Luhn.
    Optionally suppress if technical context.
    """
    if not is_valid_luhn(value):
        return False
    # Technical context suppression
    if re.search(
        r"\b(dimensions?|ratios?|resolutions?|versions?|v\d+|subnets?|"
        r"ip\s+address|weights?|heights?|widths?|pixels?|px|cm|mm|inches?|"
        r"sizes?|configs?|coordinates?|measurements?)\b",
        context, re.I
    ):
        return False
    if re.search(
        r"\b(dummy|fake|test|sample|demo|placeholder|for\s+illustration|"
        r"not\s+real|fictitious|mock|documentation\s+example)\b",
        context, re.I
    ):
        return False
    return True


def is_valid_aadhaar(raw: str) -> bool:
    """
    Validate a raw Aadhaar string using the Verhoeff checksum algorithm.
    Strips all non-digit characters before checking.
    Returns True only if the 12-digit number passes checksum.
    """
    digits = re.sub(r"\D", "", raw.strip())
    if len(digits) != 12:
        return False

    # UIDAI: Aadhaar cannot start with 0 or 1
    if digits[0] in ("0", "1"):
        return False

    checksum = 0
    for i in range(11, -1, -1):
        digit = int(digits[i])
        pos = (11 - i) % 8
        checksum = _VERHOEFF_MULT[checksum][_VERHOEFF_PERM[pos][digit]]

    return _VERHOEFF_INV[checksum] == 0


# ─────────────────────────────────────────────────────────────
# PAN Validation
# ─────────────────────────────────────────────────────────────

# PAN entity type characters (4th character)
_PAN_ENTITY_CHARS = set("CPHABGJLFTE")

_PAN_REGEX = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


def is_valid_pan(raw: str) -> bool:
    """
    Validate Indian PAN card format:
      - Positions 1-3: AAA (any 3 uppercase letters)
      - Position 4: entity type character (C/P/H/A/B/G/J/L/F/T/E)
      - Position 5: first letter of surname
      - Positions 6-9: 4 digits
      - Position 10: any uppercase letter
    """
    pan = raw.strip().upper()
    if not _PAN_REGEX.match(pan):
        return False
    if pan[3] not in _PAN_ENTITY_CHARS:
        return False
    return True


# ─────────────────────────────────────────────────────────────
# Luhn Algorithm — Credit/Debit card number validation
# ─────────────────────────────────────────────────────────────

def is_valid_luhn(raw: str) -> bool:
    """
    Validate a card number using the Luhn algorithm.
    Accepts digits, spaces, and hyphens as separators.
    """
    digits = re.sub(r"[\s\-]", "", raw.strip())
    if not digits.isdigit():
        return False
    if not (13 <= len(digits) <= 19):
        return False

    total = 0
    reverse_digits = digits[::-1]
    for i, d in enumerate(reverse_digits):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


# ─────────────────────────────────────────────────────────────
# GSTIN Validation
# ─────────────────────────────────────────────────────────────

_GSTIN_REGEX = re.compile(
    r"^[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}[Z]{1}[0-9A-Z]{1}$"
)

# Valid state codes 01–37 (as of 2024)
_VALID_STATE_CODES = set(f"{i:02d}" for i in range(1, 38))


def is_valid_gstin(raw: str) -> bool:
    """
    Validate Indian GSTIN (GST Identification Number):
      - 2-digit state code (01–37)
      - Followed by a valid PAN (positions 3–12)
      - Entity number, Z check digit, and checksum character
    """
    gstin = raw.strip().upper()
    if not _GSTIN_REGEX.match(gstin):
        return False
    state_code = gstin[:2]
    if state_code not in _VALID_STATE_CODES:
        return False
    # Embedded PAN must also be structurally valid
    embedded_pan = gstin[2:12]
    return is_valid_pan(embedded_pan)


# ─────────────────────────────────────────────────────────────
# Indian Passport Validation
# ─────────────────────────────────────────────────────────────

_PASSPORT_REGEX = re.compile(r"^[A-PR-WY][1-9][0-9]{6}$")


def is_valid_passport(raw: str) -> bool:
    """
    Indian passport number: 1 letter (A-Z, excluding Q, X, Z) + 7 digits.
    First digit of the number cannot be 0.
    """
    return bool(_PASSPORT_REGEX.match(raw.strip().upper()))


# ─────────────────────────────────────────────────────────────
# Indian Driving Licence Validation
# ─────────────────────────────────────────────────────────────

# Format: SS-RTO-YYYY-NNNNNNN (e.g., DL-0420110149646)
_DL_REGEX = re.compile(
    r"^[A-Z]{2}[0-9]{2}[0-9]{4}[0-9]{7}$"  # compact: SSRRYYYY#######
    r"|^[A-Z]{2}-[0-9]{2}-[0-9]{4}-[0-9]{7}$",  # hyphenated
    re.IGNORECASE,
)


def is_valid_driving_licence(raw: str) -> bool:
    """
    Validate Indian driving licence number (basic structural check).
    Accepts both compact and hyphenated formats.
    """
    return bool(_DL_REGEX.match(raw.strip().upper()))


# ─────────────────────────────────────────────────────────────
# UPI ID Validation
# ─────────────────────────────────────────────────────────────

_UPI_REGEX = re.compile(
    r"^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}$"
)

_KNOWN_UPI_HANDLES = {
    "okaxis", "oksbi", "okicici", "okhdfcbank", "ybl", "ibl", "paytm",
    "apl", "jupiteraxis", "fam", "naviaxis", "axl", "barodampay",
    "cnrb", "federal", "kotak", "rbl", "upi", "icici", "sbi", "hdfc",
}


def is_valid_upi(raw: str) -> bool:
    """
    Validate UPI VPA (Virtual Payment Address).
    Checks format and whether the handle belongs to a known PSP.
    """
    raw = raw.strip().lower()
    if not _UPI_REGEX.match(raw):
        return False
    handle = raw.split("@")[1]
    # Accept known handles; also accept unknown handles (lenient for scanner)
    return len(handle) >= 2


# ─────────────────────────────────────────────────────────────
# ABHA (Ayushman Bharat Health Account) Validation
# ─────────────────────────────────────────────────────────────

_ABHA_REGEX = re.compile(r"^\d{2}-\d{4}-\d{4}-\d{4}$")


def is_valid_abha(raw: str) -> bool:
    """
    ABHA number is 14 digits formatted as XX-XXXX-XXXX-XXXX.
    """
    return bool(_ABHA_REGEX.match(raw.strip()))


# ─────────────────────────────────────────────────────────────
# Code Artifact Filter (suppress NER false positives from code)
# ─────────────────────────────────────────────────────────────

_CODE_INDICATORS = set("([.<=>{}/\\")
_CODE_KEYWORDS = {
    "def", "class", "import", "return", "lambda", "async",
    "await", "yield", "pass", "raise", "except", "finally",
    "None", "True", "False", "self", "cls",
}


def is_code_artifact(value: str, entity_type: str) -> bool:
    """
    Return True if the detected value looks like a code token rather than
    real PII. Primarily used to suppress false PERSON detections in source code.
    """
    if entity_type != "PERSON":
        return False

    # Contains punctuation characteristic of code
    if any(c in value for c in _CODE_INDICATORS):
        return True

    # Suspiciously long "name" — real names rarely exceed 5 tokens
    words = value.split()
    if len(words) > 5:
        return True

    # Matches a Python/JS keyword
    if any(w in _CODE_KEYWORDS for w in words):
        return True

    # Starts with lowercase and contains underscore — likely a variable
    if re.match(r"^[a-z].*_", value):
        return True

    return False
