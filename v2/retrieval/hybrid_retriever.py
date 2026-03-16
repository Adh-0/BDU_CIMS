"""
hybrid_retriever.py — Combines FAISS (semantic) and BM25 (keyword) search.
Loads both indexes and retrieves documents using both strategies.
"""

import logging
import pickle
from dataclasses import dataclass, field
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


@dataclass
class RetrievedDoc:
    """A document returned from retrieval with its score."""
    content: str
    score: float
    metadata: dict = field(default_factory=dict)
    chunk_id: str = ""
    source: str = ""  # "faiss" or "bm25"


class HybridRetriever:
    """Retrieves relevant documents using both semantic and keyword search.

    Lazy-loads indexes on first query to keep startup fast.
    """

    def __init__(
        self,
        faiss_index_dir: Path,
        bm25_index_path: Path,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
        self.faiss_index_dir = Path(faiss_index_dir)
        self.bm25_index_path = Path(bm25_index_path)
        self.embedding_model_name = embedding_model

        # Lazy-loaded
        self._model = None
        self._faiss_index = None
        self._faiss_chunks = None
        self._bm25 = None
        self._bm25_chunks = None
        self._loaded = False

    def _load(self):
        """Load all indexes into memory."""
        if self._loaded:
            return

        logger.info("Loading search indexes...")

        # Load embedding model
        self._model = SentenceTransformer(self.embedding_model_name)

        # Load FAISS index
        faiss_path = self.faiss_index_dir / "index.faiss"
        chunks_path = self.faiss_index_dir / "chunks_store.pkl"

        if not faiss_path.exists():
            raise RuntimeError(
                f"FAISS index not found at {faiss_path}. Run ingestion first!"
            )

        self._faiss_index = faiss.read_index(str(faiss_path))
        with open(chunks_path, "rb") as f:
            self._faiss_chunks = pickle.load(f)

        logger.info(f"  FAISS: {self._faiss_index.ntotal} vectors loaded")

        # Load BM25 index
        if self.bm25_index_path.exists():
            with open(self.bm25_index_path, "rb") as f:
                bm25_data = pickle.load(f)
            self._bm25 = bm25_data["bm25"]
            self._bm25_chunks = bm25_data["chunks"]
            logger.info(f"  BM25:  {len(self._bm25_chunks)} docs loaded")
        else:
            logger.warning("BM25 index not found — using FAISS only")
            self._bm25 = None
            self._bm25_chunks = None

        self._loaded = True
        logger.info("Search indexes ready.")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def total_vectors(self) -> int:
        if self._faiss_index:
            return self._faiss_index.ntotal
        return 0

    def search_faiss(self, query: str, k: int = 10) -> list[RetrievedDoc]:
        """Semantic search using FAISS."""
        self._load()

        query_embedding = self._model.encode(
            [query], normalize_embeddings=True
        )
        query_embedding = np.array(query_embedding, dtype=np.float32)

        scores, indices = self._faiss_index.search(query_embedding, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._faiss_chunks):
                continue
            chunk = self._faiss_chunks[idx]
            results.append(RetrievedDoc(
                content=chunk["content"],
                score=float(score),
                metadata=chunk["metadata"],
                chunk_id=chunk["chunk_id"],
                source="faiss",
            ))
        return results

    def search_bm25(self, query: str, k: int = 10) -> list[RetrievedDoc]:
        """Keyword search using BM25."""
        self._load()

        if self._bm25 is None:
            return []

        tokenized_query = query.lower().split()
        scores = self._bm25.get_scores(tokenized_query)

        # Get top-k indices
        top_indices = np.argsort(scores)[::-1][:k]

        results = []
        for idx in top_indices:
            score = scores[idx]
            if score <= 0:
                continue  # No match
            chunk = self._bm25_chunks[idx]
            results.append(RetrievedDoc(
                content=chunk["content"],
                score=float(score),
                metadata=chunk["metadata"],
                chunk_id=chunk["chunk_id"],
                source="bm25",
            ))
        return results

    def retrieve(self, query: str, k: int = 10) -> tuple[list[RetrievedDoc], list[RetrievedDoc]]:
        """Run both FAISS and BM25 search, return raw results for fusion.

        Returns:
            Tuple of (faiss_results, bm25_results).
        """
        self._load()

        faiss_results = self.search_faiss(query, k=k)
        bm25_results = self.search_bm25(query, k=k)

        logger.debug(
            f"Retrieved {len(faiss_results)} FAISS + {len(bm25_results)} BM25 results"
        )
        return faiss_results, bm25_results
