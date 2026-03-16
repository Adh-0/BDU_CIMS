"""
embedder.py — Embedding model and FAISS/BM25 index builder.
Converts text chunks into vectors and builds searchable indexes.
Uses atomic file operations to prevent index corruption.
"""

import logging
import pickle
import shutil
import tempfile
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi

from ingestion.chunker import Chunk

logger = logging.getLogger(__name__)

# Stored alongside the FAISS index for mapping vector IDs → chunk data
CHUNKS_STORE_FILENAME = "chunks_store.pkl"


class EmbeddingIndexBuilder:
    """Builds FAISS and BM25 indexes from text chunks.

    Uses sentence-transformers for embedding and stores the chunk
    data alongside the FAISS index so we can retrieve full content
    during search.
    """

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"  Embedding dimension: {self.dimension}")

    def build_faiss_index(
        self,
        chunks: list[Chunk],
        index_dir: Path,
    ) -> int:
        """Build a FAISS index from chunks and save atomically.

        The index is first written to a temp directory, then the final
        directory is replaced in one atomic rename operation. This prevents
        corruption if the process is killed mid-write.

        Args:
            chunks: List of Chunk objects to index.
            index_dir: Directory to save the FAISS index files.

        Returns:
            Number of vectors indexed.
        """
        if not chunks:
            logger.warning("No chunks to index!")
            return 0

        texts = [c.content for c in chunks]

        logger.info(f"Embedding {len(texts)} chunks...")
        embeddings = self.model.encode(
            texts,
            show_progress_bar=True,
            batch_size=64,
            normalize_embeddings=True,
        )
        embeddings = np.array(embeddings, dtype=np.float32)

        # Build FAISS index (Inner Product for normalized vectors = cosine similarity)
        index = faiss.IndexFlatIP(self.dimension)
        index.add(embeddings)

        # Prepare chunk data store (maps vector ID → chunk content + metadata)
        chunks_store = [
            {"content": c.content, "metadata": c.metadata, "chunk_id": c.chunk_id}
            for c in chunks
        ]

        # ── Atomic save: write to temp dir, then swap ──
        index_dir = Path(index_dir)
        temp_dir = Path(tempfile.mkdtemp(prefix="faiss_build_"))

        try:
            # Write to temp
            faiss.write_index(index, str(temp_dir / "index.faiss"))
            with open(temp_dir / CHUNKS_STORE_FILENAME, "wb") as f:
                pickle.dump(chunks_store, f)

            # Swap: remove old, rename new
            if index_dir.exists():
                shutil.rmtree(index_dir)
            index_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(temp_dir), str(index_dir))

            logger.info(f"FAISS index saved: {len(chunks)} vectors → {index_dir}")
            return len(chunks)

        except Exception:
            # Clean up temp on failure
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            raise

    def build_bm25_index(
        self,
        chunks: list[Chunk],
        bm25_path: Path,
    ) -> int:
        """Build a BM25 keyword index and save it.

        Args:
            chunks: List of Chunk objects to index.
            bm25_path: Path to save the pickled BM25 index.

        Returns:
            Number of documents indexed.
        """
        if not chunks:
            logger.warning("No chunks for BM25 index!")
            return 0

        # Tokenize: simple whitespace + lowercase
        tokenized = [c.content.lower().split() for c in chunks]
        bm25 = BM25Okapi(tokenized)

        # Save chunk content and metadata alongside BM25
        bm25_data = {
            "bm25": bm25,
            "chunks": [
                {"content": c.content, "metadata": c.metadata, "chunk_id": c.chunk_id}
                for c in chunks
            ],
        }

        bm25_path = Path(bm25_path)
        bm25_path.parent.mkdir(parents=True, exist_ok=True)

        # Atomic write
        temp_path = bm25_path.with_suffix(".tmp")
        try:
            with open(temp_path, "wb") as f:
                pickle.dump(bm25_data, f)
            temp_path.replace(bm25_path)
            logger.info(f"BM25 index saved: {len(chunks)} docs → {bm25_path}")
            return len(chunks)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise
