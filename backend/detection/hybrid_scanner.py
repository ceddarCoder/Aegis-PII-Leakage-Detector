"""
hybrid_scanner.py — Core PII detection engine (regex + validators + optional NLI).

Based on Script B from the analysis, with modifications:
- Accepts `use_nli` parameter to skip the transformer for fast mode.
- Returns start/end indices for each finding.
- In fast mode, uses keyword proximity to boost confidence.
"""

import re
import spacy
from transformers import pipeline
from functools import lru_cache
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
nlp = spacy.load("en_core_web_sm")
NLI_MODELS = [
    "typeform/distilbert-base-uncased-mnli",
    "facebook/bart-large-mnli",
    "cross-encoder/nli-deberta-v3-small",
]

def load_nli(models=NLI_MODELS):
    for model_id in models:
        try:
            print(f"Loading NLI model: {model_id} ...")
            p = pipeline("zero-shot-classification", model=model_id, device=-1)
            print(f"✓ {model_id}\n")
            return p
        except Exception as e:
            print(f"✗ {model_id}: {e}")
    raise RuntimeError("All NLI models failed.")

nli = load_nli()

# ---------------------------------------------------------------------------
# PII patterns (same as Script B)
# ---------------------------------------------------------------------------
PII_PATTERNS = {
    "AADHAAR": r"(?<!\d)[1-9]\d{3}[\s\-]?\d{4}[\s\-]?\d{4}(?!\d)",
    "PAN": r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
    "PASSPORT_IN": r"\b[A-PR-WY][1-9]\d{6}\b",
    "VOTER_ID": r"\b[A-Z]{3}[0-9]{7}\b",
    "DL_IN": r"\b[A-Z]{2}[0-9]{2}\s?[0-9]{11}\b",
    "SSN": r"(?<![\d.])\b\d{3}-\d{2}-\d{4}\b(?![\d.])",
    "CREDIT_CARD": r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|6011[0-9]{12}|3[47][0-9]{13})\b",
    "IFSC": r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
    "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
    "PHONE": r"(?<!\d)(\+91[-\s]?)?[6-9]\d{9}(?!\d)",
}

# ---------------------------------------------------------------------------
# NLI labels (unchanged)
# ---------------------------------------------------------------------------
HIGH_RISK_LABELS = {
    "someone's real personal information being shared or exposed",
    "private data accidentally or intentionally disclosed",
    "sensitive information belonging to a real individual",
}
MID_RISK_LABELS = {
    "information that may or may not be real personal data",
}
LOW_RISK_LABELS = {
    "a fictional, fake, or made-up example used for illustration",
    "masked, redacted, or anonymised data",
    "technical documentation or format specification",
}
CANDIDATE_LABELS = list(HIGH_RISK_LABELS | MID_RISK_LABELS | LOW_RISK_LABELS)

# ---------------------------------------------------------------------------
# Signal regexes (from Script B)
# ---------------------------------------------------------------------------
OWNERSHIP_RE = re.compile(
    r"\b(my|his|her|your|their|our|client'?s?|customer'?s?|user'?s?)\b",
    re.IGNORECASE,
)
MASKED_VALUE_RE = re.compile(r"[xX\*]{3,}|xxxx|\*{3,}", re.IGNORECASE)
DUMMY_CONTEXT_RE = re.compile(
    r"\b(dummy|fake|test\s+data|test\s+card|sample|demo|placeholder|"
    r"for\s+illustration|not\s+real|fictitious|mock[\s\-]?up|"
    r"documentation\s+example|format\s+example|use\s+\S+\s+as\s+a)\b",
    re.IGNORECASE,
)
TECHNICAL_CONTEXT_RE = re.compile(
    r"\b(dimensions?|ratios?|resolutions?|versions?|v\d+|subnets?|"
    r"ip\s+address|weights?|heights?|widths?|pixels?|px|cm|mm|inches?|"
    r"sizes?|configs?|coordinates?|measurements?)\b",
    re.IGNORECASE,
)
PII_KEYWORDS_RE = re.compile(
    r"\b(aadhaar|aadhar|pan\b|kyc|passport|voter\s?id|"
    r"driving\s?licen[cs]e|credit\s?card|debit\s?card|"
    r"bank\s?account|ifsc|ssn|social\s?security|"
    r"phone\s?number|mobile\s?number|whatsapp|"
    r"email\s+address|my\s+email|email\s+was|email\s+got|"
    r"confidential|leaked|disclosed|exposed|accidentally|mistakenly)\b",
    re.IGNORECASE,
)
PII_KEYWORD_FLOOR = 0.70   # applied after veto

# ---------------------------------------------------------------------------
# Validators (with context)
# ---------------------------------------------------------------------------
def valid_aadhaar(value: str, context: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if len(digits) != 12 or digits[0] in "01":
        return False
    if re.search(r"\b(account|a/c|card|dimension|size|px|cm|mm|inches)\b", context, re.I):
        return False
    return True

def valid_ssn(value: str, context: str) -> bool:
    parts = value.split("-")
    if len(parts) != 3:
        return False
    area, group, serial = parts
    area_int = int(area)
    if area_int == 0 or area_int == 666:
        return False
    if int(group) == 0 or int(serial) == 0:
        return False
    if TECHNICAL_CONTEXT_RE.search(context):
        return False
    if DUMMY_CONTEXT_RE.search(context):
        return False
    return True

def valid_phone(value: str, context: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    return len(digits) == 10 and digits[0] in "6789"

VALIDATORS = {
    "AADHAAR": valid_aadhaar,
    "SSN": valid_ssn,
    "PHONE": valid_phone,
}

# ---------------------------------------------------------------------------
# Helpers (sentence, NER, NLI)
# ---------------------------------------------------------------------------
def get_sentence(doc, span_start: int, span_end: int) -> str:
    for sent in doc.sents:
        if span_start >= sent.start_char and span_end <= sent.end_char:
            return sent.text
    return ""

def get_nearby_ner(doc, span_start: int, span_end: int) -> list[str]:
    return [
        ent.label_ for ent in doc.ents
        if ent.start_char >= span_start - 200 and ent.end_char <= span_end + 200
    ]

@dataclass
class NLIResult:
    top_label: str
    top_score: float
    distribution: dict[str, float]
    high_risk_mass: float
    low_risk_mass: float

@lru_cache(maxsize=512)
def run_nli(sentence: str) -> NLIResult:
    result = nli(sentence, candidate_labels=CANDIDATE_LABELS)
    dist = dict(zip(result["labels"], result["scores"]))
    high_mass = sum(dist.get(l, 0) for l in HIGH_RISK_LABELS)
    low_mass = sum(dist.get(l, 0) for l in LOW_RISK_LABELS)
    return NLIResult(
        top_label=result["labels"][0],
        top_score=result["scores"][0],
        distribution=dist,
        high_risk_mass=high_mass,
        low_risk_mass=low_mass,
    )

def severity(score: float) -> str | None:
    if score >= 0.82:
        return "CONFIRMED_LEAK"
    elif score >= 0.58:
        return "PROBABLE_LEAK"
    return None

# ---------------------------------------------------------------------------
# Core scanning function (with use_nli flag)
# ---------------------------------------------------------------------------
def hybrid_scan(text: str, use_nli: bool = True) -> list[dict]:
    """
    Scan text for PII.
    If use_nli=True, run full NLI context analysis (slower).
    If use_nli=False, use regex + validators + simple keyword boost (faster).
    Returns list of dicts with keys:
        type, value, start, end, risk_score, severity (if NLI), decision, distribution (if NLI)
    """
    doc = nlp(text) if use_nli else None  # only parse if needed for NLI/sentences
    findings = []

    for pii_type, pattern in PII_PATTERNS.items():
        for match in re.finditer(pattern, text):
            span_start, span_end = match.start(), match.end()
            value = match.group()

            # Validator check (always run)
            validator = VALIDATORS.get(pii_type)
            if validator:
                context = text[max(0, span_start-100): min(len(text), span_end+100)]
                if not validator(value, context):
                    continue

            if use_nli:
                # Full NLI mode
                sentence = get_sentence(doc, span_start, span_end)
                nearby_ner = get_nearby_ner(doc, span_start, span_end)

                # Compute risk using NLI (Script B logic)
                context = sentence or text
                if MASKED_VALUE_RE.search(value):
                    continue   # completely suppress masked values
                if DUMMY_CONTEXT_RE.search(context):
                    continue   # suppress dummy/test sentences

                # Special case: credit card bypass NLI
                if pii_type == "CREDIT_CARD":
                    risk_score = 0.87
                    reason = "high-risk structural type"
                    dist = {}
                else:
                    if not sentence.strip():
                        base_risk = 0.65
                        reason = "no sentence context"
                        dist = {}
                    else:
                        nli_result = run_nli(sentence)
                        dist = nli_result.distribution
                        base_risk = nli_result.high_risk_mass
                        reason = nli_result.top_label
                        # Low-risk veto
                        max_low = max((dist.get(l, 0) for l in LOW_RISK_LABELS), default=0)
                        if max_low > 0.28:
                            base_risk = min(base_risk, 0.52)

                # Keyword floor (applied after veto)
                if PII_KEYWORDS_RE.search(context):
                    base_risk = max(base_risk, PII_KEYWORD_FLOOR)

                # Ownership boost
                if OWNERSHIP_RE.search(context):
                    base_risk = min(base_risk + 0.10, 1.0)

                # PERSON entity nearby
                if "PERSON" in nearby_ner:
                    base_risk = min(base_risk + 0.07, 1.0)

                risk_score = round(base_risk, 3)
                sev = severity(risk_score)
                if sev is None:
                    continue  # below threshold

                findings.append({
                    "type": pii_type,
                    "value": value,
                    "start": span_start,
                    "end": span_end,
                    "risk_score": risk_score,
                    "severity": sev,
                    "decision": reason,
                    "distribution": dist,
                })
            else:
                # Fast mode: no NLI, use base confidence + keyword boost
                base_conf = 0.65  # default
                context = text[max(0, span_start-80): min(len(text), span_end+80)]
                if PII_KEYWORDS_RE.search(context):
                    base_conf = max(base_conf, 0.75)
                # Additional simple boosts could be added here
                findings.append({
                    "type": pii_type,
                    "value": value,
                    "start": span_start,
                    "end": span_end,
                    "risk_score": base_conf,
                    "severity": None,
                    "decision": "fast regex match",
                    "distribution": {},
                })

    return findings


"""
hybrid_scanner.py — Core PII detection engine (regex + validators + optional NLI).

Includes graceful fallback if spaCy or NLI models are missing.
Now uses validators.py for all structural checks.
"""

# import re
# import logging
# from functools import lru_cache
# from dataclasses import dataclass

# # Import all validators from the separate module
# import validators as v

# logger = logging.getLogger(__name__)

# # ---------------------------------------------------------------------------
# # Attempt to load spaCy model (for sentence splitting & NER)
# # ---------------------------------------------------------------------------
# try:
#     import spacy
#     nlp = spacy.load("en_core_web_sm")
#     logger.info("spaCy model loaded successfully.")
# except Exception as e:
#     logger.warning(f"Could not load spaCy model 'en_core_web_sm': {e}")
#     logger.warning("Sentence splitting and NER will be disabled. NLI will also be unavailable.")
#     nlp = None

# # ---------------------------------------------------------------------------
# # Attempt to load NLI model (zero-shot classifier)
# # ---------------------------------------------------------------------------
# NLI_MODELS = [
#     # "typeform/distilbert-base-uncased-mnli",
#     "facebook/bart-large-mnli",
#     "cross-encoder/nli-deberta-v3-small",
#     "typeform/distilbert-base-uncased-mnli",
# ]

# nli = None
# def load_nli():
#     global nli
#     from transformers import pipeline
#     for model_id in NLI_MODELS:
#         try:
#             logger.info(f"Loading NLI model: {model_id} ...")
#             nli = pipeline("zero-shot-classification", model=model_id, device=-1)
#             logger.info(f"✓ {model_id}")
#             return
#         except Exception as e:
#             logger.warning(f"✗ {model_id}: {e}")
#     logger.warning("All NLI models failed. NLI will be unavailable.")

# if nlp is not None:
#     try:
#         load_nli()
#     except Exception as e:
#         logger.warning(f"NLI loading failed: {e}")
# else:
#     logger.warning("Skipping NLI load because spaCy model is missing.")

# # ---------------------------------------------------------------------------
# # PII patterns (expanded with GSTIN, UPI, ABHA)
# # ---------------------------------------------------------------------------
# PII_PATTERNS = {
#     "AADHAAR":     r"(?<!\d)[1-9]\d{3}[\s\-]?\d{4}[\s\-]?\d{4}(?!\d)",
#     "PAN":         r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
#     "GSTIN":       r"\b[0-3][0-9][A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b",
#     "PASSPORT_IN": r"\b[A-PR-WY][1-9]\d{6}\b",
#     "VOTER_ID":    r"\b[A-Z]{3}[0-9]{7}\b",
#     "DL_IN":       r"\b[A-Z]{2}[0-9]{2}\s?[0-9]{11}\b",
#     "SSN":         r"(?<![\d.])\b\d{3}-\d{2}-\d{4}\b(?![\d.])",
#     "CREDIT_CARD": r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|6011[0-9]{12}|3[47][0-9]{13})\b",
#     "IFSC":        r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
#     "EMAIL":       r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
#     "PHONE":       r"(?<!\d)(\+91[-\s]?)?[6-9]\d{9}(?!\d)",
#     "UPI":         r"\b[a-zA-Z0-9.\-_]{2,40}@[a-zA-Z]{2,64}\b",
#     "ABHA":        r"\b\d{2}-\d{4}-\d{4}-\d{4}\b",
# }

# # ---------------------------------------------------------------------------
# # NLI labels (unchanged)
# # ---------------------------------------------------------------------------
# HIGH_RISK_LABELS = {
#     "someone's real personal information being shared or exposed",
#     "private data accidentally or intentionally disclosed",
#     "sensitive information belonging to a real individual",
# }
# MID_RISK_LABELS = {
#     "information that may or may not be real personal data",
# }
# LOW_RISK_LABELS = {
#     "a fictional, fake, or made-up example used for illustration",
#     "masked, redacted, or anonymised data",
#     "technical documentation or format specification",
# }
# CANDIDATE_LABELS = list(HIGH_RISK_LABELS | MID_RISK_LABELS | LOW_RISK_LABELS)

# # ---------------------------------------------------------------------------
# # Signal regexes (unchanged)
# # ---------------------------------------------------------------------------
# OWNERSHIP_RE = re.compile(
#     r"\b(my|his|her|your|their|our|client'?s?|customer'?s?|user'?s?)\b",
#     re.IGNORECASE,
# )
# MASKED_VALUE_RE = re.compile(r"[xX\*]{3,}|xxxx|\*{3,}", re.IGNORECASE)
# DUMMY_CONTEXT_RE = re.compile(
#     r"\b(dummy|fake|test\s+data|test\s+card|sample|demo|placeholder|"
#     r"for\s+illustration|not\s+real|fictitious|mock[\s\-]?up|"
#     r"documentation\s+example|format\s+example|use\s+\S+\s+as\s+a)\b",
#     re.IGNORECASE,
# )
# TECHNICAL_CONTEXT_RE = re.compile(
#     r"\b(dimensions?|ratios?|resolutions?|versions?|v\d+|subnets?|"
#     r"ip\s+address|weights?|heights?|widths?|pixels?|px|cm|mm|inches?|"
#     r"sizes?|configs?|coordinates?|measurements?)\b",
#     re.IGNORECASE,
# )
# PII_KEYWORDS_RE = re.compile(
#     r"\b(aadhaar|aadhar|pan\b|kyc|passport|voter\s?id|"
#     r"driving\s?licen[cs]e|credit\s?card|debit\s?card|"
#     r"bank\s?account|ifsc|ssn|social\s?security|"
#     r"phone\s?number|mobile\s?number|whatsapp|"
#     r"email\s+address|my\s+email|email\s+was|email\s+got|"
#     r"confidential|leaked|disclosed|exposed|accidentally|mistakenly)\b",
#     re.IGNORECASE,
# )
# PII_KEYWORD_FLOOR = 0.70

# # ---------------------------------------------------------------------------
# # Validators (now using validators.py)
# # ---------------------------------------------------------------------------
# def _valid_aadhaar(value: str, context: str) -> bool:
#     if not v.is_valid_aadhaar(value):
#         return False
#     # Suppress if technical context (dimensions, etc.)
#     if re.search(r"\b(account|a/c|card|dimension|size|px|cm|mm|inches)\b", context, re.I):
#         return False
#     return True

# def _valid_pan(value: str, context: str) -> bool:
#     return v.is_valid_pan(value)

# def _valid_gstin(value: str, context: str) -> bool:
#     return v.is_valid_gstin(value)

# def _valid_passport(value: str, context: str) -> bool:
#     return v.is_valid_passport(value)

# def _valid_voter_id(value: str, context: str) -> bool:
#     return bool(re.match(r"^[A-Z]{3}[0-9]{7}$", value.upper()))

# def _valid_dl(value: str, context: str) -> bool:
#     return v.is_valid_driving_licence(value)

# def _valid_ssn(value: str, context: str) -> bool:
#     return v.is_valid_ssn(value, context)

# def _valid_credit_card(value: str, context: str) -> bool:
#     return v.is_valid_credit_card(value, context)

# def _valid_ifsc(value: str, context: str) -> bool:
#     return bool(re.match(r"^[A-Z]{4}0[A-Z0-9]{6}$", value.upper()))

# def _valid_email(value: str, context: str) -> bool:
#     return bool(re.match(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$", value))

# def _valid_phone(value: str, context: str) -> bool:
#     return v.is_valid_phone_india(value, context)

# def _valid_upi(value: str, context: str) -> bool:
#     return v.is_valid_upi(value)

# def _valid_abha(value: str, context: str) -> bool:
#     return v.is_valid_abha(value)

# VALIDATORS = {
#     "AADHAAR":     _valid_aadhaar,
#     "PAN":         _valid_pan,
#     "GSTIN":       _valid_gstin,
#     "PASSPORT_IN": _valid_passport,
#     "VOTER_ID":    _valid_voter_id,
#     "DL_IN":       _valid_dl,
#     "SSN":         _valid_ssn,
#     "CREDIT_CARD": _valid_credit_card,
#     "IFSC":        _valid_ifsc,
#     "EMAIL":       _valid_email,
#     "PHONE":       _valid_phone,
#     "UPI":         _valid_upi,
#     "ABHA":        _valid_abha,
# }

# # ---------------------------------------------------------------------------
# # Helpers (sentence, NER, NLI) – unchanged
# # ---------------------------------------------------------------------------
# def get_sentence(doc, span_start: int, span_end: int) -> str:
#     if doc is None:
#         return ""
#     for sent in doc.sents:
#         if span_start >= sent.start_char and span_end <= sent.end_char:
#             return sent.text
#     return ""

# def get_nearby_ner(doc, span_start: int, span_end: int) -> list[str]:
#     if doc is None:
#         return []
#     return [
#         ent.label_ for ent in doc.ents
#         if ent.start_char >= span_start - 200 and ent.end_char <= span_end + 200
#     ]

# @dataclass
# class NLIResult:
#     top_label: str
#     top_score: float
#     distribution: dict[str, float]
#     high_risk_mass: float
#     low_risk_mass: float

# @lru_cache(maxsize=512)
# def run_nli(sentence: str) -> NLIResult:
#     if nli is None:
#         return NLIResult("", 0.0, {}, 0.0, 0.0)
#     result = nli(sentence, candidate_labels=CANDIDATE_LABELS)
#     dist = dict(zip(result["labels"], result["scores"]))
#     high_mass = sum(dist.get(l, 0) for l in HIGH_RISK_LABELS)
#     low_mass = sum(dist.get(l, 0) for l in LOW_RISK_LABELS)
#     return NLIResult(
#         top_label=result["labels"][0],
#         top_score=result["scores"][0],
#         distribution=dist,
#         high_risk_mass=high_mass,
#         low_risk_mass=low_mass,
#     )

# def severity(score: float) -> str | None:
#     if score >= 0.82:
#         return "CONFIRMED_LEAK"
#     elif score >= 0.58:
#         return "PROBABLE_LEAK"
#     return None

# # ---------------------------------------------------------------------------
# # Core scanning function (with use_nli flag)
# # ---------------------------------------------------------------------------
# def hybrid_scan(text: str, use_nli: bool = True) -> list[dict]:
#     """
#     Scan text for PII.
#     If use_nli=True, run full NLI context analysis (slower) – requires spaCy and NLI models.
#     If use_nli=False, use regex + validators + simple keyword boost (faster).
#     Returns list of dicts with keys:
#         type, value, start, end, risk_score, severity (if NLI), decision, distribution (if NLI)
#     """
#     # Check if we can actually do NLI when requested
#     if use_nli and (nlp is None or nli is None):
#         logger.warning("NLI requested but models are missing. Falling back to fast mode.")
#         use_nli = False

#     doc = nlp(text) if use_nli and nlp is not None else None
#     findings = []

#     for pii_type, pattern in PII_PATTERNS.items():
#         for match in re.finditer(pattern, text):
#             span_start, span_end = match.start(), match.end()
#             value = match.group()

#             # Validator check (always run)
#             validator = VALIDATORS.get(pii_type)
#             if validator:
#                 context = text[max(0, span_start-100): min(len(text), span_end+100)]
#                 if not validator(value, context):
#                     continue

#             if use_nli:
#                 # Full NLI mode (only if models are available)
#                 sentence = get_sentence(doc, span_start, span_end)
#                 nearby_ner = get_nearby_ner(doc, span_start, span_end)

#                 context = sentence or text
#                 if MASKED_VALUE_RE.search(value):
#                     continue
#                 if DUMMY_CONTEXT_RE.search(context):
#                     continue

#                 if pii_type == "CREDIT_CARD":
#                     risk_score = 0.87
#                     reason = "high-risk structural type"
#                     dist = {}
#                 else:
#                     if not sentence.strip():
#                         base_risk = 0.65
#                         reason = "no sentence context"
#                         dist = {}
#                     else:
#                         nli_result = run_nli(sentence)
#                         dist = nli_result.distribution
#                         base_risk = nli_result.high_risk_mass
#                         reason = nli_result.top_label
#                         max_low = max((dist.get(l, 0) for l in LOW_RISK_LABELS), default=0)
#                         if max_low > 0.28:
#                             base_risk = min(base_risk, 0.52)

#                 if PII_KEYWORDS_RE.search(context):
#                     base_risk = max(base_risk, PII_KEYWORD_FLOOR)

#                 if OWNERSHIP_RE.search(context):
#                     base_risk = min(base_risk + 0.10, 1.0)

#                 if "PERSON" in nearby_ner:
#                     base_risk = min(base_risk + 0.07, 1.0)

#                 risk_score = round(base_risk, 3)
#                 sev = severity(risk_score)
#                 if sev is None:
#                     continue

#                 findings.append({
#                     "type": pii_type,
#                     "value": value,
#                     "start": span_start,
#                     "end": span_end,
#                     "risk_score": risk_score,
#                     "severity": sev,
#                     "decision": reason,
#                     "distribution": dist,
#                 })
#             else:
#                 # Fast mode
#                 base_conf = 0.65
#                 context = text[max(0, span_start-80): min(len(text), span_end+80)]
#                 if PII_KEYWORDS_RE.search(context):
#                     base_conf = max(base_conf, 0.75)
#                 findings.append({
#                     "type": pii_type,
#                     "value": value,
#                     "start": span_start,
#                     "end": span_end,
#                     "risk_score": base_conf,
#                     "severity": None,
#                     "decision": "fast regex match",
#                     "distribution": {},
#                 })

#     return findings