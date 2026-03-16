"""
server.py — FastAPI application for the BDU RAG Chatbot v2.
Serves the chat API, health endpoint, and frontend static files.

Usage:
    cd d:\RAG_CHAT\v2
    python -m api.server
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

# Ensure v2 root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from generation.rag_chain import RAGChain
from api.middleware import RequestLoggingMiddleware

# ── Logging ──────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("api")

# ── Global RAG chain (loaded on startup) ─────────────────────────
rag_chain: RAGChain | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load RAG chain on startup, clean up on shutdown."""
    global rag_chain

    logger.info("=" * 50)
    logger.info("  BDU RAG v2 — API Server Starting")
    logger.info("=" * 50)

    try:
        rag_chain = RAGChain()
        logger.info("RAG chain initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize RAG chain: {e}")
        logger.warning("Server will start but /chat will return errors until fixed.")

    yield

    logger.info("Server shutting down.")


# ── FastAPI App ──────────────────────────────────────────────────
app = FastAPI(
    title="BDU RAG Chatbot v2",
    description="AI-powered chatbot for Bharathidasan University",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging
app.add_middleware(RequestLoggingMiddleware)

# Static files (frontend)
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Request/Response Models ──────────────────────────────────────

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="The question to ask")


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []
    retrieval_count: int = 0


class HealthResponse(BaseModel):
    status: str
    index_loaded: bool
    llm_provider: str
    llm_model: str
    documents_indexed: int


# ── Endpoints ────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the frontend page."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>BDU RAG Chatbot v2</h1><p>Frontend not found.</p>")


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint for monitoring."""
    from ingestion.metadata_db import MetadataDB

    docs_count = 0
    try:
        db = MetadataDB(config.METADATA_DB_PATH)
        docs_count = db.get_total_chunks()
        db.close()
    except Exception:
        pass

    return HealthResponse(
        status="ok" if rag_chain and rag_chain.is_ready else "degraded",
        index_loaded=rag_chain.is_ready if rag_chain else False,
        llm_provider=config.LLM_PROVIDER,
        llm_model=config.GROQ_MODEL if config.LLM_PROVIDER == "groq" else config.OLLAMA_MODEL,
        documents_indexed=docs_count,
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Answer a question using the RAG pipeline."""
    if not rag_chain:
        return JSONResponse(
            status_code=503,
            content={"error": "RAG system not initialized. Run ingestion first."},
        )

    result = rag_chain.ask(req.query, stream=False)
    return ChatResponse(**result)


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Stream the answer token-by-token using Server-Sent Events."""
    if not rag_chain:
        return JSONResponse(
            status_code=503,
            content={"error": "RAG system not initialized."},
        )

    async def event_generator():
        try:
            token_gen = rag_chain.ask(req.query, stream=True)
            if isinstance(token_gen, dict):
                # Non-streaming fallback (error case)
                yield {"data": token_gen.get("answer", "Error occurred.")}
                return

            for token in token_gen:
                yield {"data": token}
            yield {"data": "[DONE]"}
        except Exception as e:
            logger.error(f"SSE stream error: {e}")
            yield {"data": "Error generating response."}

    return EventSourceResponse(event_generator())


# ── Run server ───────────────────────────────────────────────────

def main():
    import uvicorn
    print()
    print(f"Starting server at http://{config.API_HOST}:{config.API_PORT}")
    print(f"Frontend: http://localhost:{config.API_PORT}")
    print(f"API docs: http://localhost:{config.API_PORT}/docs")
    print(f"Health:   http://localhost:{config.API_PORT}/health")
    print()

    uvicorn.run(
        "api.server:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=False,
        log_level=config.LOG_LEVEL.lower(),
    )


if __name__ == "__main__":
    main()
