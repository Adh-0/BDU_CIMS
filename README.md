# BDU CIMS — Retrieval-Augmented Generation (RAG) Chatbot

![Version](https://img.shields.io/badge/version-2.0-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-brightgreen)

An AI-powered institutional chatbot built for Bharathidasan University. It securely answers student questions regarding admissions, fees, and courses based exclusively on official university documents.

## 🌟 What's New in v2?

The `v2/` directory contains a complete production-ready rewrite of the system:
- **FastAPI backend** with Server-Sent Events (SSE) for real-time answer streaming.
- **Hybrid Search** combining FAISS (semantic) and BM25 (keyword) via Reciprocal Rank Fusion.
- **Groq & Ollama routing**: Develop instantly with Groq cloud models, deploy privately with local Ollama models.
- **Smart incremental ingestion**: SQLite hash-tracking ensures only new/changed documents are re-indexed.
- **XSS-Secured Frontend**: Safe DOM rendering.

*Read the [Full v2 Documentation](DOCUMENTATION_v2.0.md) for architecture details.*

---

## 🚀 Quick Start (v2)

### 1. Setup
```powershell
cd v2
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configuration
Copy the env template and add your Groq API key:
```powershell
copy .env.example .env
# Edit .env and set GROQ_API_KEY
```

### 3. Ingest Documents
Drop your PDF files into `v2/data/documents/` and run the indexer:
```powershell
python -m ingestion.run_ingest
```

### 4. Run Server
```powershell
python -m api.server
```
Visit `http://localhost:8000` to use the chatbot.

---

## Repository Structure

- `v2/` — **The active v2 production codebase.** 
- `PDF/`, `index/`, `api.py`, `ingest.py`, `query.py`, `frontend/` — *The legacy v1 codebase (kept for reference).*
- `DOCUMENTATION_v2.0.md` — Detailed v2 architecture and developer guide.
- `DOCUMENTATION_v0.1b.md` — Legacy v1 documentation.
