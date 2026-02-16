# Local RAG System with FAISS + Hugging Face Chat

This project implements a **local Retrieval-Augmented Generation (RAG) pipeline**
using FAISS for vector search and Sentence-Transformers for embeddings.
Answers are generated using Hugging Face `InferenceClient` chat models.

---

## ✨ Features

- Local document ingestion (PDF, DOCX, TXT, MD)
- Chunking and semantic embedding
- Persistent FAISS vector index
- Hugging Face chat-based Q&A
- Environment-based configuration
- Windows + Python 3.11 compatible

---

## 📁 Project Structure

```
RAG_CHAT/
├── PDF/                # Input documents (PDFs)
├── index/              # FAISS vector index (generated)
├── frontend/
│   ├── index.html      # Chat widget UI
│   └── widget.js       # Frontend logic
├── api.py              # Flask API server
├── ingest.py           # Document ingestion & indexing
├── query.py            # CLI question answering
├── requirements.txt
├── .env                # Hugging Face token (not tracked)
├── .gitignore
└── README.md
```

---

## 🧰 Requirements

- Windows 10/11
- Python 3.11+
- Hugging Face account + API token

---

## 🚀 Setup

### 1️⃣ Create virtual environment

```bash
python -m venv rag
rag\Scripts\activate
pip install -r requirements.txt
```
