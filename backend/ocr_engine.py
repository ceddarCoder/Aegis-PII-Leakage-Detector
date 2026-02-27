# """
# ocr_engine.py — OCR pipeline for visual PII extraction.

# Uses EasyOCR (PyTorch-based) to extract text from:
#   - Scanned KYC documents (Aadhaar card photos, PAN card images)
#   - Screenshots of config files or terminals
#   - PDFs with embedded images

# Detected markers for government documents:
#   - "GOVERNMENT OF INDIA"
#   - "REPUBLIC OF INDIA"
#   - "UNIQUE IDENTIFICATION AUTHORITY OF INDIA"
#   - "INCOME TAX DEPARTMENT"
# """

# import io
# import logging
# import tempfile
# import os
# from pathlib import Path

# logger = logging.getLogger(__name__)

# # Lazy-load EasyOCR and fitz (PyMuPDF) to avoid import-time overhead
# _reader = None


# def _get_reader():
#     global _reader
#     if _reader is None:
#         try:
#             import easyocr
#             # en + hi covers Hindi transliterations on Indian documents
#             _reader = easyocr.Reader(["en", "hi"], gpu=False, verbose=False)
#             logger.info("EasyOCR reader initialized.")
#         except ImportError:
#             logger.error("easyocr not installed. Run: pip install easyocr")
#             _reader = False
#         except Exception as exc:
#             logger.error("EasyOCR init failed: %s", exc)
#             _reader = False
#     return _reader


# # ─────────────────────────────────────────────────────────────
# # KYC Document Type Detection
# # ─────────────────────────────────────────────────────────────

# _KYC_MARKERS = {
#     "aadhaar": [
#         "unique identification authority",
#         "uidai", "aadhaar", "aadhar", "adhar", "enrolment",
#         "government of india",
#     ],
#     "pan": [
#         "income tax department", "permanent account number",
#         "govt. of india", "government of india", "pan card",
#     ],
#     "passport": [
#         "republic of india", "passport", "ministry of external affairs",
#         "place of birth", "date of issue", "date of expiry",
#     ],
#     "driving_licence": [
#         "driving licence", "transport department", "motor vehicles",
#         "valid till", "licence no",
#     ],
#     "voter_id": [
#         "election commission", "electors photo identity",
#         "epic no", "voter",
#     ],
# }


# def detect_document_type(text: str) -> str:
#     """
#     Classify extracted OCR text as a specific KYC document type.
#     Returns one of: 'aadhaar', 'pan', 'passport', 'driving_licence',
#     'voter_id', or 'unknown'.
#     """
#     text_lower = text.lower()
#     scores: dict[str, int] = {}

#     for doc_type, markers in _KYC_MARKERS.items():
#         score = sum(1 for m in markers if m in text_lower)
#         if score:
#             scores[doc_type] = score

#     if not scores:
#         return "unknown"
#     return max(scores, key=scores.get)


# # ─────────────────────────────────────────────────────────────
# # Image OCR
# # ─────────────────────────────────────────────────────────────

# def ocr_image_bytes(image_bytes: bytes, file_hint: str = "") -> dict:
#     """
#     Run EasyOCR on raw image bytes.

#     Returns:
#         {
#             'text': str,          — full extracted text
#             'doc_type': str,      — detected KYC document type
#             'confidence': float,  — mean OCR confidence
#             'word_count': int,
#             'error': str | None,
#         }
#     """
#     reader = _get_reader()
#     if reader is False:
#         return _ocr_error("EasyOCR not available. Install with: pip install easyocr torch torchvision")

#     try:
#         # EasyOCR accepts file paths or numpy arrays; easiest is a temp file
#         suffix = Path(file_hint).suffix.lower() or ".jpg"
#         with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
#             tmp.write(image_bytes)
#             tmp_path = tmp.name

#         try:
#             results = reader.readtext(tmp_path, detail=1, paragraph=False)
#         finally:
#             os.unlink(tmp_path)

#         if not results:
#             return _ocr_empty()

#         lines = []
#         confidences = []
#         for (_bbox, text_segment, conf) in results:
#             lines.append(text_segment)
#             confidences.append(conf)

#         full_text = "\n".join(lines)
#         avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

#         return {
#             "text":       full_text,
#             "doc_type":   detect_document_type(full_text),
#             "confidence": round(avg_conf, 3),
#             "word_count": len(full_text.split()),
#             "error":      None,
#         }

#     except Exception as exc:
#         logger.error("OCR failed: %s", exc)
#         return _ocr_error(str(exc))


# # ─────────────────────────────────────────────────────────────
# # PDF OCR (rasterize pages → OCR each page)
# # ─────────────────────────────────────────────────────────────

# def ocr_pdf_bytes(pdf_bytes: bytes, max_pages: int = 5) -> dict:
#     """
#     Extract text from a PDF by:
#       1. Attempting direct text extraction (for text-based PDFs)
#       2. Falling back to page rasterization + EasyOCR (for scanned PDFs)

#     Returns same schema as ocr_image_bytes(), aggregated across pages.
#     """
#     try:
#         import fitz  # PyMuPDF
#     except ImportError:
#         return _ocr_error("PyMuPDF not installed. Run: pip install pymupdf")

#     try:
#         doc = fitz.open(stream=pdf_bytes, filetype="pdf")
#     except Exception as exc:
#         return _ocr_error(f"Failed to open PDF: {exc}")

#     all_text_parts = []
#     all_confidences = []
#     pages_processed = 0

#     for page_num in range(min(len(doc), max_pages)):
#         page = doc.load_page(page_num)

#         # Attempt direct text extraction first
#         direct_text = page.get_text("text").strip()
#         if direct_text and len(direct_text) > 50:
#             all_text_parts.append(direct_text)
#             all_confidences.append(0.95)  # high confidence for native text
#             pages_processed += 1
#             continue

#         # Rasterize and OCR
#         pix = page.get_pixmap(dpi=200)
#         img_bytes = pix.tobytes("png")
#         page_result = ocr_image_bytes(img_bytes, file_hint=f"page_{page_num}.png")

#         if not page_result.get("error") and page_result.get("text"):
#             all_text_parts.append(page_result["text"])
#             all_confidences.append(page_result["confidence"])

#         pages_processed += 1

#     doc.close()

#     if not all_text_parts:
#         return _ocr_empty()

#     full_text = "\n\n".join(all_text_parts)
#     avg_conf = sum(all_confidences) / len(all_confidences) if all_confidences else 0.0

#     return {
#         "text":            full_text,
#         "doc_type":        detect_document_type(full_text),
#         "confidence":      round(avg_conf, 3),
#         "word_count":      len(full_text.split()),
#         "pages_processed": pages_processed,
#         "error":           None,
#     }


# # ─────────────────────────────────────────────────────────────
# # Dispatcher: route by file extension
# # ─────────────────────────────────────────────────────────────

# def ocr_file(file_bytes: bytes, filename: str) -> dict:
#     """
#     Dispatch to the correct OCR function based on file extension.
#     Supports: .png, .jpg, .jpeg, .bmp, .tiff, .webp, .pdf
#     """
#     ext = Path(filename).suffix.lower()
#     if ext == ".pdf":
#         return ocr_pdf_bytes(file_bytes)
#     elif ext in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}:
#         return ocr_image_bytes(file_bytes, file_hint=filename)
#     else:
#         return _ocr_error(f"Unsupported file type: {ext}")


# # ─────────────────────────────────────────────────────────────
# # Helpers
# # ─────────────────────────────────────────────────────────────

# def _ocr_error(msg: str) -> dict:
#     return {"text": "", "doc_type": "unknown", "confidence": 0.0, "word_count": 0, "error": msg}


# def _ocr_empty() -> dict:
#     return {"text": "", "doc_type": "unknown", "confidence": 0.0, "word_count": 0, "error": None}

"""
ocr_engine.py — OCR and KYC entity extraction using EasyOCR.

Provides a singleton OCREngine that can:
  - Extract text from image bytes or URLs.
  - Detect KYC documents based on trigger phrases.
  - Return a pre‑built KYC entity record for scoring.

Dependencies:
  - easyocr (optional, graceful fallback)
  - Pillow
  - requests
"""

import asyncio
import logging
import re
from typing import Optional, Dict, Any, List
from pathlib import Path

import requests
from PIL import Image
import io

# Import project configuration – adjust paths as needed
try:
    from config import OCR_LANGUAGES, KYC_TRIGGER_PHRASES, BASE_SCORES
    from detection.validators import redact
    from ingestion.base_ingestor import Document
except ImportError:
    # Fallback defaults for standalone use
    OCR_LANGUAGES = ['en']
    KYC_TRIGGER_PHRASES = [
        "GOVERNMENT OF INDIA",
        "INDIAN PASSPORT",
        "AADHAAR CARD",
        "PERMANENT ACCOUNT NUMBER",
        "ELECTION COMMISSION",
        "DRIVING LICENCE",
    ]
    BASE_SCORES = {"KYC_SCAN": 10.0}
    def redact(s: str) -> str:
        return s[:4] + "****" + s[-4:] if len(s) > 8 else s[:2] + "****"

    class Document:
        """Simple Document stub for standalone testing."""
        def __init__(self, content, source_url, repo_id=None, file_path=None,
                     platform="", is_ocr_derived=False, metadata=None):
            self.content = content
            self.source_url = source_url
            self.repo_id = repo_id
            self.file_path = file_path
            self.platform = platform
            self.is_ocr_derived = is_ocr_derived
            self.metadata = metadata or {}

logger = logging.getLogger(__name__)


class OCREngine:
    """
    Singleton EasyOCR reader with text extraction and KYC detection.
    """

    _instance = None
    _reader = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, languages: Optional[List[str]] = None):
        """
        Initialize with language list. If not provided, uses OCR_LANGUAGES from config.
        """
        if hasattr(self, '_initialized') and self._initialized:
            return
        self.languages = languages or OCR_LANGUAGES
        self._load_reader()
        self._initialized = True

    def _load_reader(self):
        """Lazy‑load EasyOCR reader (downloads model on first use)."""
        if self._reader is None:
            try:
                import easyocr
                self._reader = easyocr.Reader(self.languages, gpu=False)
                logger.info("✅ EasyOCR reader initialized with languages %s", self.languages)
            except ImportError:
                logger.warning("EasyOCR not installed. OCR functionality disabled.")
                self._reader = None
            except Exception as e:
                logger.error("Failed to initialize EasyOCR: %s", e)
                self._reader = None

    # ------------------------------------------------------------------
    # Synchronous extraction methods
    # ------------------------------------------------------------------

    def extract_text_from_bytes(self, image_bytes: bytes) -> str:
        """
        Run OCR on raw image bytes, return extracted text.
        Returns empty string if OCR fails or no text.
        """
        if self._reader is None:
            return ""

        try:
            # EasyOCR expects a file path or numpy array; we can pass bytes via a PIL image
            # Using readtext with bytes is not directly supported; we'll use PIL Image.open
            # and then convert to numpy array if needed. Simpler: save to bytes and use easyocr's image reading.
            # Let's use the reader.readtext with image passed as a numpy array.
            # We'll use PIL to open and then convert to RGB (EasyOCR works with numpy arrays).
            img = Image.open(io.BytesIO(image_bytes)).convert('RGB')
            # Convert PIL to numpy array
            import numpy as np
            img_np = np.array(img)

            results = self._reader.readtext(img_np, detail=0, paragraph=True)
            text = "\n".join(results).strip()
            return text
        except Exception as e:
            logger.exception("OCR on bytes failed")
            return ""

    def extract_text_from_url(self, url: str) -> str:
        """
        Download image from URL and run OCR.
        Returns extracted text (empty string on failure).
        """
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                content_type = resp.headers.get('content-type', '')
                if content_type.startswith('image/'):
                    return self.extract_text_from_bytes(resp.content)
                else:
                    logger.warning("URL %s does not point to an image (Content-Type: %s)", url, content_type)
            else:
                logger.warning("Failed to download %s: HTTP %d", url, resp.status_code)
        except Exception as e:
            logger.error("Error downloading/OCR from %s: %s", url, e)
        return ""

    def is_kyc_document(self, text: str) -> bool:
        """
        Check if extracted text contains any KYC trigger phrase.
        """
        text_upper = text.upper()
        for phrase in KYC_TRIGGER_PHRASES:
            if phrase.upper() in text_upper:
                return True
        return False

    def extract_kyc_entity(self, text: str, source_url: str) -> Optional[Dict[str, Any]]:
        """
        If the text appears to come from a KYC document, return a pre‑built
        dictionary that can be turned into a LeakRecord.

        Returns None if no KYC document detected.
        """
        if not self.is_kyc_document(text):
            return None

        # Use config values
        base_score = BASE_SCORES.get("KYC_SCAN", 10.0)
        severity = self._get_severity_tier(base_score)

        return {
            "pii_type": "KYC_SCAN",
            "matched_text": "[KYC Document]",
            "redacted_snippet": "[KYC Document]",
            "base_score": base_score,
            "severity_tier": severity,
            "validation_method": "ocr+keyword_match",
            "confidence": 0.95,
            "is_ocr_derived": True,
        }

    def _get_severity_tier(self, score: float) -> str:
        """Map base score to severity tier."""
        if score >= 9.0:
            return "Critical"
        elif score >= 7.0:
            return "High"
        elif score >= 5.0:
            return "Medium"
        elif score >= 2.5:
            return "Low"
        else:
            return "Info"

    # ------------------------------------------------------------------
    # Async wrappers for use in FastAPI endpoints / scrapers
    # ------------------------------------------------------------------

    async def extract_text_from_bytes_async(self, image_bytes: bytes) -> str:
        """Run OCR in a thread pool (non‑blocking)."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.extract_text_from_bytes, image_bytes)

    async def extract_text_from_url_async(self, url: str) -> str:
        """Run download + OCR in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.extract_text_from_url, url)

    async def extract_kyc_entity_async(self, text: str, source_url: str) -> Optional[Dict[str, Any]]:
        """Trivial async wrapper for KYC detection."""
        return self.extract_kyc_entity(text, source_url)

    # ------------------------------------------------------------------
    # Compatibility with the original OCRExtractor interface
    # ------------------------------------------------------------------

    def extract(
        self,
        image_bytes: bytes,
        source_url: str,
        repo_id: Optional[str] = None,
        file_path: Optional[str] = None,
    ) -> Optional[Document]:
        """
        Returns a Document with extracted text and is_ocr_derived=True.
        Used by the file upload endpoint.
        """
        text = self.extract_text_from_bytes(image_bytes)
        if not text:
            return None

        is_kyc = self.is_kyc_document(text)
        if is_kyc:
            # Optionally prepend a marker – the detection engine can use it
            text = f"[KYC_DOCUMENT_DETECTED]\n{text}"

        return Document(
            content=text,
            source_url=f"{source_url}_ocr",
            repo_id=repo_id,
            file_path=file_path,
            platform="upload",
            is_ocr_derived=True,
            metadata={"is_kyc": is_kyc, "original_url": source_url},
        )


# ------------------------------------------------------------------
# Singleton accessor
# ------------------------------------------------------------------
_ocr_engine_instance: Optional[OCREngine] = None


def get_ocr_engine(languages: Optional[List[str]] = None) -> OCREngine:
    """Return the singleton OCREngine instance."""
    global _ocr_engine_instance
    if _ocr_engine_instance is None:
        _ocr_engine_instance = OCREngine(languages)
    return _ocr_engine_instance


# Alias for backward compatibility with existing code that expects OCRExtractor
get_ocr_extractor = get_ocr_engine