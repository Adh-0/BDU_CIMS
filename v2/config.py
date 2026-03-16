"""
config.py — Centralized configuration for BDU RAG Chatbot v2.
All settings loaded from environment variables (.env file).
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env from v2 directory ──────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


# ── LLM Configuration ───────────────────────────────────────────
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq")  # "groq" or "ollama"

# Groq (cloud — development)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Ollama (local — deployment)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")


# ── Embedding Configuration ─────────────────────────────────────
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)


# ── Chunking Configuration ──────────────────────────────────────
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1200"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))


# ── Paths ────────────────────────────────────────────────────────
DOCUMENTS_DIR = BASE_DIR / "data" / "documents"
FAISS_INDEX_DIR = BASE_DIR / "storage" / "index"
BM25_INDEX_PATH = BASE_DIR / "storage" / "bm25" / "bm25_index.pkl"
METADATA_DB_PATH = BASE_DIR / "storage" / "metadata.db"


# ── LLM Generation ──────────────────────────────────────────────
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "30"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))


# ── Retrieval ────────────────────────────────────────────────────
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "10"))
RETRIEVAL_FINAL_K = int(os.getenv("RETRIEVAL_FINAL_K", "5"))


# ── API ──────────────────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MAX_QUERY_LENGTH = int(os.getenv("MAX_QUERY_LENGTH", "500"))


# ── Ensure directories exist ────────────────────────────────────
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)
BM25_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
