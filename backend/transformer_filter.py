"""
transformer_filter.py — Phase C NLP disambiguation layer.

Uses a lightweight zero-shot classifier to determine whether a detected
PII value is real data or a test/dummy/example value.

Model: cross-encoder/nli-MiniLM2-L6-H768
  ~ 90 MB, fast inference, no GPU required.

Result is cached per (entity_type, snippet_hash) to avoid redundant calls.
"""

import hashlib
import logging
from functools import lru_cache
from typing import Literal

logger = logging.getLogger(__name__)

# Lazy-load the pipeline to avoid heavy import at module load time
_classifier = None


def _get_classifier():
    global _classifier
    if _classifier is None:
        try:
            from transformers import pipeline
            _classifier = pipeline(
                "zero-shot-classification",
                model="cross-encoder/nli-MiniLM2-L6-H768",
                # Explicitly set device to CPU so it works on any machine
                device=-1,
            )
            logger.info("Transformer classifier loaded successfully.")
        except Exception as exc:
            logger.error("Failed to load transformer model: %s", exc)
            _classifier = False  # sentinel: loading failed, skip NLP
    return _classifier


# Labels used for zero-shot classification
_CANDIDATE_LABELS = [
    "real personal data",
    "test or dummy data",
    "code variable or identifier",
    "example or sample data",
]

_REAL_LABEL = "real personal data"
_FAKE_LABELS = {"test or dummy data", "code variable or identifier", "example or sample data"}

# Confidence threshold: if fake label confidence > this, mark as false positive
_FAKE_THRESHOLD = 0.55


def _hash_snippet(snippet: str) -> str:
    return hashlib.md5(snippet.encode("utf-8", errors="replace")).hexdigest()


@lru_cache(maxsize=1024)
def _classify_cached(snippet_hash: str, snippet: str) -> str:
    """
    Cached zero-shot classification.
    Returns the top label string.
    """
    clf = _get_classifier()
    if clf is False:
        return _REAL_LABEL  # fallback: treat as real if model unavailable

    try:
        result = clf(snippet[:512], _CANDIDATE_LABELS)
        return result["labels"][0]
    except Exception as exc:
        logger.warning("Classifier inference failed: %s", exc)
        return _REAL_LABEL


def is_likely_test_data(snippet: str, entity_type: str | None = None) -> tuple[bool, float, str]:
    """
    Determine whether the snippet surrounding a detected PII value
    is likely to be test/dummy/fake data rather than real leaked PII.

    Returns:
        (is_fake: bool, fake_confidence: float, top_label: str)

    Usage:
        is_fake, conf, label = is_likely_test_data(snippet, "IN_AADHAAR")
        if is_fake:
            # downgrade or discard the finding
    """
    # Rule-based fast path: check for explicit fake-data markers in snippet
    snippet_lower = snippet.lower()
    _FAKE_KEYWORDS = {
        "test", "dummy", "fake", "example", "sample", "mock", "placeholder",
        "lorem", "ipsum", "foobar", "john doe", "jane doe", "xxx", "todo",
        "fixture", "seed", "factory", "stub", "demo", "temp", "tmp",
    }
    for kw in _FAKE_KEYWORDS:
        if kw in snippet_lower:
            return True, 0.95, "keyword match: " + kw

    # NLP classification — single inference call
    clf = _get_classifier()
    if clf is False:
        return False, 0.0, "model unavailable"

    try:
        result = clf(snippet[:512], _CANDIDATE_LABELS)
        label_scores = dict(zip(result["labels"], result["scores"]))

        fake_confidence = sum(
            label_scores.get(lbl, 0.0) for lbl in _FAKE_LABELS
        )
        is_fake = fake_confidence > _FAKE_THRESHOLD

        return is_fake, round(fake_confidence, 3), result["labels"][0]

    except Exception as exc:
        logger.warning("Classifier inference failed: %s", exc)
        return False, 0.0, "inference error"


def filter_findings_with_nlp(findings: list[dict]) -> list[dict]:
    """
    Run the transformer filter over a list of finding dicts (from presidio_engine).
    Findings flagged as likely fake data have their confidence downgraded and
    an annotation appended. Findings with confidence < 0.15 are dropped entirely.

    Only runs NLP on entity types where disambiguation is meaningful
    (skip EMAIL_ADDRESS and PHONE_NUMBER which are hard to fake-detect).
    """
    _NLP_ELIGIBLE = {
        "IN_AADHAAR", "IN_PAN", "IN_GSTIN", "IN_CARD",
        "PERSON", "IN_PASSPORT", "IN_ABHA", "IN_UPI",
    }

    filtered = []
    for finding in findings:
        if finding["type"] not in _NLP_ELIGIBLE:
            filtered.append(finding)
            continue

        is_fake, fake_conf, label = is_likely_test_data(
            finding["snippet"], finding["type"]
        )

        if is_fake:
            # Downgrade confidence
            finding["confidence"] = round(finding["confidence"] * (1 - fake_conf * 0.8), 3)
            existing_note = finding.get("annotation", "")
            finding["annotation"] = (
                f"{existing_note}; NLP: likely fake ({label}, p={fake_conf:.2f})"
                if existing_note
                else f"NLP: likely fake ({label}, p={fake_conf:.2f})"
            )

        # Drop near-zero confidence findings
        if finding["confidence"] < 0.15:
            continue

        filtered.append(finding)

    return filtered
