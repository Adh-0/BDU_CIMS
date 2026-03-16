# 📖 BDU CIMS Chatbot v2 — Project Documentation

> **Version:** `v2.0` · **Last Updated:** March 2026

---

## What Is This Project?

This is the **next-generation AI-powered chatbot** for Bharathidasan University (BDU). It answers questions about the university — admission details, fee structures, available courses, contact information, and more. 

Version 2.0 is a complete architectural rewrite designed for production reliability, better accuracy, and real-time streaming.

### Key Upgrades in v2

1. **Hybrid Retrieval (FAISS + BM25)**: v1 only used semantic search, which often missed exact keyword matches (like specific fee numbers). v2 uses both semantic and keyword search, merged via Reciprocal Rank Fusion (RRF) for highly accurate context retrieval.
2. **Groq & Ollama Support**: 
   - Uses **Groq** (Llama-3.3-70b) in the cloud for blazing fast development.
   - Supports **Ollama** (Llama-3.2:3b) for 100% local, on-premise deployment.
3. **Smart Ingestion Pipeline**: Extracts structured tables as markdown and validates text quality. Supports PDF, DOCX, TXT, MD, and CSV files.
4. **Incremental Ingestion**: Uses a SQLite metadata database with SHA256 hashing so only new or changed files are processed when you add documents.
5. **FastAPI & Streaming**: Replaced Flask with FastAPI. The UI now streams the answer word-by-word instantly via Server-Sent Events (SSE).
6. **Circuit Breaker**: Prevents the system from hanging if the LLM service goes down.
7. **XSS-Secured Frontend**: The chat widget safely renders markdown without `innerHTML` vulnerabilities.

---

## 📁 Project Structure (v2)

```
v2/
├── .env.example                  # Template for secrets
├── config.py                     # Centralized env-based configs
├── requirements.txt              # Pinned dependencies
│
├── ingestion/                    # 📥 Document pipeline
│   ├── loader.py                 # Multi-format doc extractor
│   ├── chunker.py                # Smart text & table splitting
│   ├── embedder.py               # FAISS + BM25 index generator
│   ├── metadata_db.py            # SQLite tracker for incremental updates
│   └── run_ingest.py             # CLI entrypoint
│
├── retrieval/                    # 🔍 Search pipeline
│   ├── hybrid_retriever.py       # Parallel semantic + keyword search
│   └── fusion.py                 # RRF merging algorithm
│
├── generation/                   # 🤖 AI Generation
│   ├── llm_client.py             # Groq/Ollama client with circuit breaker
│   ├── prompts.py                # Strict anti-hallucination rules
│   └── rag_chain.py              # Orchestrator
│
├── api/                          # 🌐 Web Server
│   ├── server.py                 # FastAPI app
│   └── middleware.py             # Request logging
│
├── frontend/                     # 💬 Chat UI
│   ├── index.html                # Host page
│   └── widget.js                 # Floating chat widget (XSS Safe)
│
├── data/documents/               # 📄 Drop your PDFs here
├── storage/                      # 💾 Generated indexes & DB
└── tests/eval_queries.json       # 🧪 Retrieval test suite
```

---

## 🚀 Setup & Installation

### 1. Create Virtual Environment

```powershell
cd v2
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env`:
```powershell
copy .env.example .env
```
Edit `.env` and add your **Groq API Key**:
```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here
```

### 3. Add Documents & Ingest

Place your university PDFs/files in `v2/data/documents/`. Run the ingestion pipeline to build the searchable index:

```powershell
python -m ingestion.run_ingest
```
*Note: You can run this command safely anytime you add new files. It will only process the new ones.*

### 4. Start the Server

```powershell
python -m api.server
```

The server will start at `http://localhost:8000`.
- **Chat Interface**: Open `http://localhost:8000` to interact with the widget.
- **API Documentation**: Open `http://localhost:8000/docs` to see the endpoints.

---

## 🔄 How the v2 Pipeline Works

1. **Ingestion (`run_ingest.py`)**: Reads a PDF with `pdfplumber`, extracts text and converts tables to markdown. Saves hashes in SQLite. Splits text. Embeds using `sentence-transformers`. Saves to FAISS (vectors) and BM25 (keywords).
2. **Search (`hybrid_retriever.py`)**: Takes a user query ("Fee for MCA?"). FAISS finds semantic matches. BM25 finds exact keyword matches. The `fusion.py` script combines the best of both.
3. **Generation (`rag_chain.py`)**: Hands the fused documents and the strict safety prompt to the Groq/Ollama LLM. Streams the generated answer back to the FastAPI `/chat/stream` endpoint.
4. **Display (`widget.js`)**: Safely updates the DOM with the streamed response.
