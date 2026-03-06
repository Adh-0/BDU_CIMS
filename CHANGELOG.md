# CHANGELOG

## v0.2-beta (2026-03-06)

### Data Pipeline Overhaul
- Replaced PyPDF with **pdfplumber** for table-aware PDF extraction
- Smart table parsing: extracts structured rows instead of garbled text
- Vertical text cleanup for rotated PDF cells (e.g. "2-year", "Others", "SC/ST")
- **Topic separation**: course info and fee info stored in separate chunks
  - Fees no longer leak into course-related answers
- **Programme type labeling**: each course entry tagged as UG/PG/Integrated
  - Enables correct "after 12th" vs "after graduation" resolution
- Chunk parameters: size 800→1500, overlap 200→300

### Prompt Engineering
- BDU-specific system prompt with strict rules:
  - No unsolicited fees, no filler phrases, no hallucinated greetings
  - "after 12th" → UG/Integrated, "after graduation" → PG mapping
  - Controlled verbosity — answers stop naturally, don't fill token limit
- User prompt redesigned for focused, relevant answers
- LLM parameters: k 12→5, max_tokens 400→700, temperature 0.2

### Code Quality
- Module docstrings added to all files
- Emoji log messages replaced with ASCII tags ([DONE], [WARN], [LOAD], etc.)
- ASCII startup banners for ingest, query, and API scripts
- Requirements updated: pypdf → pdfplumber

---

## v0.1-beta (2025-02-15)

Initial release:
- Flask API server (`api.py`)
- RAG query engine with FAISS + HuggingFace Mistral-7B (`query.py`)
- PDF/DOCX/TXT document ingestion (`ingest.py`)
- Embeddable chat widget with Shadow DOM (`widget.js`)
- Suggestion buttons for common questions
