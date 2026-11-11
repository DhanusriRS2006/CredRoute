# CredRoute — Explainable AI for Academic Credit Transfer

**CredRoute** is a Python-based prototype that assists universities in evaluating transfer-credit equivalence. It combines academic document extraction, rule-based eligibility checks, semantic topic matching, coverage-based recommendations, and human-readable explanations.

> **Project status:** Work in progress. This README describes the code in this repository snapshot. A later multi-transcript, semester-aware matching design is documented separately and should not be considered implemented in this snapshot.

## Problem

Course names and syllabi vary across universities, making manual transfer-credit comparisons time-consuming. CredRoute explores how document intelligence and semantic matching can help academic reviewers identify likely equivalences while keeping final decisions with university staff.

## Main capabilities

- Upload transcripts and source syllabi through a FastAPI interface.
- Extract transcript text using `pdfplumber`, with Gemini-based image/document extraction support.
- Check eligibility using percentage, category, institution recognition, and prior branch.
- Convert syllabus topics into semantic embeddings using `all-MiniLM-L6-v2` (384 dimensions).
- Compare source and target topics with cosine similarity and calculate topic coverage.
- Produce Accept / Partial / Redo recommendations and explanatory reasoning.
- Store target course information and evaluation records in PostgreSQL.

**Prototype limitations:** The current pipeline pools source syllabus topics across courses rather than enforcing course ownership. The results-page route currently uses sample results. The upload/evaluation path and configuration need additional integration testing before production use.

## Technology stack

| Area | Technology |
| --- | --- |
| Backend | Python, FastAPI, Jinja2 |
| Embeddings | SentenceTransformers, `all-MiniLM-L6-v2` |
| Matching | NumPy, cosine similarity |
| OCR/document parsing | pdfplumber, pdf2image, Pillow, Google Gemini |
| Database | PostgreSQL, psycopg2 |
| Testing | pytest |

## Processing flow

```text
Transcript + source syllabus
            |
            v
    Document extraction
            |
            v
     Eligibility rules
            |
            v
  Source topic embeddings
            |
            v
Target course/topic comparison
            |
            v
Coverage and status recommendation
            |
            v
  Reasoning + database records
```

## Repository structure

```text
CredRoute/
├── main.py                       # FastAPI routes and HTML templates
├── pipeline.py                   # Evaluation orchestration and DB writes
├── ocr_parser.py                 # Document extraction
├── eligibility_engine.py        # Rule-based eligibility
├── gpa_engine.py                 # GPA utilities
├── src/
│   ├── embeddings/              # Topic embedding helpers
│   ├── matching_engine/         # Cosine similarity and topic allocation helpers
│   ├── decision_engine/         # Recommendation thresholds
│   └── reasoning_generator/     # Explanations and Gemini fallback
├── templates/                   # Upload and results pages
├── tests/                       # Unit tests
└── requirements.txt
```

## Local setup (development)

1. Install Python 3.11+ and PostgreSQL.
2. Create a virtual environment and install the project dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install fastapi uvicorn jinja2 python-multipart pdfplumber pdf2image pillow pytest
```

3. Configure a local PostgreSQL database and the schema required by `pipeline.py` (`course`, `topic`, and `evaluation`). **Before running, replace the development-only hardcoded database credentials in `pipeline.py` with environment-based configuration.** Set up any Gemini credentials required by `ocr_parser.py` and `reasoning_generator.py` in your local environment; never commit credentials.
4. Start the API:

```powershell
python -m uvicorn main:app --reload
```

5. Open `http://127.0.0.1:8000/`.

**Setup caveat:** This snapshot is not a verified one-command installation. Its requirements list is incomplete, database schema/setup scripts need validation, and `pipeline.py` imports a `parse_document` function that is not present in the uploaded `ocr_parser.py`. Resolve those integration issues before expecting a full end-to-end evaluation to run.

## Tests

```powershell
python -m pytest tests -q
```

Tests are included but have not been confirmed passing for this snapshot.

## Design considerations

- Semantic similarity is a matching signal, not a probability of academic equivalence.
- Eligibility rules should be applied separately from AI similarity.
- Topic overlap alone cannot establish full course equivalence.
- Final transfer-credit decisions should be reviewed by authorized academic staff.
- Do not upload real student transcripts or personal information to a public repository.

## Planned improvements

- Multi-transcript support and completed-semester filtering.
- Hybrid semantic and lexical matching with course-title/language checks.
- Source-course allocation to prevent double counting.
- HOD review and final-decision workflow.
- More robust OCR caching, error handling, and regression tests.

