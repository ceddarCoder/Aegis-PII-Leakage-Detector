# 🛡 Aegis — Context-Aware Indian PII Leakage Scanner
**HackWithAI 2026 · Educational Demo**

Aegis is a high-precision PII leak detection tool built for the Indian digital ecosystem.
It combines Regex pattern matching, cryptographic validation (Verhoeff, Luhn), and
HuggingFace Transformer disambiguation to eliminate false positives and surface real leaks.

---

## Project Structure

```
aegis/
├── backend/
│   ├── models.py                  # SQLAlchemy ORM (LeakRecord, Platform, ESSRecord)
│   ├── database.py                # SQLite session management
│   ├── detection/
│   │   ├── presidio_engine.py     # Phase A+B: Presidio + mathematical validators
│   │   ├── validators.py          # Verhoeff, Luhn, PAN, GSTIN, ABHA validators
│   │   ├── transformer_filter.py  # Phase C: HuggingFace fake-data disambiguation
│   │   └── ocr_engine.py          # Phase D: EasyOCR for KYC document images
│   ├── scrapers/
│   │   ├── github_scraper.py      # GitHub REST API ingestion (recursive traversal)
│   │   └── pastebin_scraper.py    # Pastebin scraping (API + archive fallback)
│   ├── scoring/
│   │   └── ess_calculator.py      # Exposure Severity Score (0-10) with toxic combos
│   └── remediation/
│       └── git_commands.py        # Auto-generate git filter-repo remediation playbooks
├── streamlit_demo/
│   └── app.py                     # Full Streamlit UI (GitHub + Pastebin + Combined tabs)
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Clone & install

```bash
git clone https://github.com/your-username/aegis.git
cd aegis
pip install -r requirements.txt
```

### 2. Download spaCy model

```bash
python -m spacy download en_core_web_lg
```

### 3. Set up environment variables

```bash
cp .env.example .env
# Edit .env and add your GitHub token:
# GITHUB_TOKEN=ghp_xxxxxxxxxxxx
```

`.env.example`:
```
GITHUB_TOKEN=your_github_token_here
AEGIS_DB_PATH=./aegis.db
```

### 4. Run the Streamlit demo

```bash
# From the project root:
streamlit run streamlit_demo/app.py
```

Or if running from `streamlit_demo/`:
```bash
cd streamlit_demo
streamlit run app.py
```

---

## Detection Pipeline

```
Input Text / Image
      │
      ▼
  Phase A — Presidio + Custom Indian Regex Recognizers
  (Aadhaar, PAN, GSTIN, Phone, UPI, ABHA, Card, Passport)
      │
      ▼
  Phase B — Mathematical Validation (Zero False Passes)
  ┌─ Aadhaar → Verhoeff checksum
  ├─ PAN     → Entity character + structure
  ├─ GSTIN   → State code + embedded PAN
  └─ Card    → Luhn algorithm
      │
      ▼
  Phase C — Transformer Disambiguation (optional, ~2s/finding)
  (cross-encoder/nli-MiniLM2-L6-H768 → detects "test", "dummy", "mock")
      │
      ▼
  Phase D — OCR (images/PDFs only)
  (EasyOCR → extract text → feed back into Phase A)
      │
      ▼
  ESS Scoring (0–10)
  ├─ Base sensitivity weight per entity type
  ├─ Toxic combination multipliers (e.g. Aadhaar + PAN = ×1.55)
  └─ Exposure radius multiplier (GitHub public = ×1.30)
      │
      ▼
  Remediation Playbook (git filter-repo commands)
```

---

## Exposure Severity Score (ESS)

| Score | Label    | Example                          |
|-------|----------|----------------------------------|
| 9–10  | CRITICAL | Card number + Aadhaar in same file |
| 7–9   | HIGH     | Aadhaar + PAN (KYC pair)         |
| 5–7   | MEDIUM   | Phone + UPI ID                   |
| 2.5–5 | LOW      | Email address only               |
| 0–2.5 | INFO     | Name fragments                   |

### Toxic Combination Multipliers

| Combination                    | Multiplier |
|-------------------------------|-----------|
| Aadhaar + PAN + Phone (KYC triad) | ×1.90  |
| Card + Aadhaar                 | ×1.85     |
| Card + PAN                     | ×1.75     |
| UPI ID + Phone                 | ×1.60     |
| Aadhaar + PAN                  | ×1.55     |

---

## Supported PII Types

| Type               | Validation Method         | Risk Level |
|--------------------|--------------------------|-----------|
| Aadhaar            | Verhoeff checksum        | Critical   |
| PAN                | Entity char + structure  | High       |
| GSTIN              | State code + PAN embed   | High       |
| Credit/Debit Card  | Luhn algorithm           | Critical   |
| ABHA               | 14-digit pattern         | High       |
| Passport (India)   | Structural regex         | High       |
| UPI ID             | VPA format               | Medium     |
| Indian Phone       | +91 prefix + 10 digits   | Medium     |
| Email Address      | Presidio built-in        | Low        |
| Person Name (NER)  | spaCy NER + code filter  | Low        |

---

## GitHub Token Setup

1. Go to https://github.com/settings/tokens
2. Generate a new **classic** token with `public_repo` scope
3. Add to `.env` as `GITHUB_TOKEN=ghp_...`

Without a token, GitHub API is limited to **60 requests/hour** (unauthenticated).
With a token: **5000 requests/hour**.

---

## Pastebin Note

The Pastebin scraping API (`scrape.pastebin.com`) requires a **whitelisted IP**.
For the hackathon demo, Aegis automatically falls back to archive page scraping.
To get API access: https://pastebin.com/doc_scraping_api

---

## License

Educational use only. Do not use to scan repositories or pastes without authorization.
