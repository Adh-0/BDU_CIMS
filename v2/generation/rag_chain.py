"""
rag_chain.py — Main RAG orchestrator.
Ties together retrieval, fusion, and generation into a single pipeline.
"""

import logging
import sys
from pathlib import Path
from typing import Generator

# Ensure v2 root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from retrieval.hybrid_retriever import HybridRetriever
from retrieval.fusion import reciprocal_rank_fusion
from generation.llm_client import LLMClient, CircuitBreakerOpen
from generation.prompts import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


class RAGChain:
    """Full RAG pipeline: validate → retrieve → fuse → generate.

    Usage:
        chain = RAGChain()
        result = chain.ask("What courses are available after 12th?")
        print(result["answer"])

        # Streaming:
        for token in chain.ask("Tell me about BDU", stream=True):
            print(token, end="")
    """

    def __init__(self):
        logger.info("Initializing RAG chain...")

        # Initialize retriever
        self.retriever = HybridRetriever(
            faiss_index_dir=config.FAISS_INDEX_DIR,
            bm25_index_path=config.BM25_INDEX_PATH,
            embedding_model=config.EMBEDDING_MODEL,
        )

        # Initialize LLM client
        self.llm = LLMClient(
            provider=config.LLM_PROVIDER,
            api_key=config.GROQ_API_KEY,
            model=(
                config.GROQ_MODEL
                if config.LLM_PROVIDER == "groq"
                else config.OLLAMA_MODEL
            ),
            base_url=config.OLLAMA_BASE_URL,
            timeout=config.LLM_TIMEOUT,
            max_tokens=config.LLM_MAX_TOKENS,
            temperature=config.LLM_TEMPERATURE,
        )

        self.top_k = config.RETRIEVAL_TOP_K
        self.final_k = config.RETRIEVAL_FINAL_K

        logger.info("RAG chain ready.")

    def ask(
        self,
        question: str,
        stream: bool = False,
    ) -> dict | Generator[str, None, None]:
        """Answer a question using the full RAG pipeline.

        Args:
            question: The user's question text.
            stream: If True, returns a generator yielding tokens.

        Returns:
            dict with "answer", "sources", "retrieval_count" keys,
            or a token generator if stream=True.
        """
        # ── 1. Validate input ────────────────────────────────────
        question = question.strip()
        if not question:
            return {
                "answer": "Please enter a question.",
                "sources": [],
                "retrieval_count": 0,
            }

        if len(question) > config.MAX_QUERY_LENGTH:
            return {
                "answer": f"Please keep your question under {config.MAX_QUERY_LENGTH} characters.",
                "sources": [],
                "retrieval_count": 0,
            }

        logger.info(f"Query: {question[:80]}{'...' if len(question) > 80 else ''}")

        # ── 2. Retrieve relevant chunks ──────────────────────────
        try:
            faiss_results, bm25_results = self.retriever.retrieve(
                question, k=self.top_k
            )
        except RuntimeError as e:
            logger.error(f"Retrieval failed: {e}")
            return {
                "answer": "The knowledge base is not available. Please ensure documents have been ingested.",
                "sources": [],
                "retrieval_count": 0,
            }

        # ── 3. Fuse results ──────────────────────────────────────
        fused = reciprocal_rank_fusion(
            faiss_results, bm25_results, top_n=self.final_k
        )

        contexts = [doc.content for doc in fused]
        sources = list({
            doc.metadata.get("source", "Unknown")
            for doc in fused
            if doc.metadata.get("source")
        })

        logger.info(
            f"Retrieved {len(fused)} chunks "
            f"(FAISS: {len(faiss_results)}, BM25: {len(bm25_results)})"
        )

        # ── 4. Build prompt ──────────────────────────────────────
        user_prompt = build_user_prompt(question, contexts)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # ── 5. Generate answer ───────────────────────────────────
        try:
            if stream:
                return self._stream_response(messages, sources, len(fused))
            else:
                answer = self.llm.generate(messages, stream=False)
                return {
                    "answer": answer,
                    "sources": sources,
                    "retrieval_count": len(fused),
                }
        except CircuitBreakerOpen:
            return {
                "answer": "The AI service is temporarily busy. Please try again in a minute.",
                "sources": [],
                "retrieval_count": len(fused),
            }
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return {
                "answer": "Sorry, I encountered an error generating a response. Please try again.",
                "sources": [],
                "retrieval_count": len(fused),
            }

    def _stream_response(
        self,
        messages: list[dict],
        sources: list[str],
        retrieval_count: int,
    ) -> Generator[str, None, None]:
        """Stream tokens from the LLM."""
        try:
            token_gen = self.llm.generate(messages, stream=True)
            for token in token_gen:
                yield token
        except CircuitBreakerOpen:
            yield "The AI service is temporarily busy. Please try again in a minute."
        except Exception as e:
            logger.error(f"Stream generation failed: {e}")
            yield "Sorry, I encountered an error. Please try again."

    @property
    def is_ready(self) -> bool:
        """Check if the chain is ready (indexes available)."""
        try:
            return (
                config.FAISS_INDEX_DIR.exists()
                and (config.FAISS_INDEX_DIR / "index.faiss").exists()
            )
        except Exception:
            return False
