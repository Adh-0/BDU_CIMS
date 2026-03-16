"""
chunker.py — Smart text chunking with metadata preservation.
Splits documents into retrieval-friendly chunks without losing context.
"""

import hashlib
import logging
from dataclasses import dataclass, field

from langchain_text_splitters import RecursiveCharacterTextSplitter

from ingestion.loader import LoadedDocument

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """A chunk of text ready for embedding."""
    content: str
    chunk_id: str  # SHA256 hash of content (for dedup)
    metadata: dict = field(default_factory=dict)


def _compute_chunk_id(text: str) -> str:
    """Create a deterministic ID from chunk content."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def chunk_documents(
    documents: list[LoadedDocument],
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
) -> list[Chunk]:
    """Split documents into retrieval-optimized chunks.

    Strategy:
      - Tables are kept as single chunks (not split mid-row).
      - Text is split using RecursiveCharacterTextSplitter which
        respects paragraph and sentence boundaries.
      - Each chunk gets a unique ID (hash) for deduplication.
      - Original metadata is preserved and enhanced.

    Args:
        documents: List of LoadedDocument from the loader.
        chunk_size: Target chunk size in characters.
        chunk_overlap: Overlap between consecutive chunks.

    Returns:
        List of Chunk objects ready for embedding.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", ", ", " ", ""],
        length_function=len,
    )

    chunks = []
    seen_ids = set()

    for doc in documents:
        content_type = doc.metadata.get("content_type", "text")

        if content_type == "table":
            # Tables: keep as single chunk if small enough,
            # otherwise split at row boundaries
            if len(doc.content) <= chunk_size * 1.5:
                chunk_id = _compute_chunk_id(doc.content)
                if chunk_id not in seen_ids:
                    seen_ids.add(chunk_id)
                    chunks.append(Chunk(
                        content=doc.content,
                        chunk_id=chunk_id,
                        metadata={**doc.metadata, "chunk_type": "table"},
                    ))
            else:
                # For large tables, split by rows but keep header
                lines = doc.content.split("\n")
                header = "\n".join(lines[:2]) if len(lines) >= 2 else ""

                # Split remaining rows into groups
                data_lines = lines[2:]
                current_chunk_lines = [header] if header else []

                for line in data_lines:
                    current_chunk_lines.append(line)
                    current_text = "\n".join(current_chunk_lines)
                    if len(current_text) >= chunk_size:
                        chunk_id = _compute_chunk_id(current_text)
                        if chunk_id not in seen_ids:
                            seen_ids.add(chunk_id)
                            chunks.append(Chunk(
                                content=current_text,
                                chunk_id=chunk_id,
                                metadata={**doc.metadata, "chunk_type": "table"},
                            ))
                        # Start new chunk with header
                        current_chunk_lines = [header] if header else []

                # Don't forget remaining lines
                if current_chunk_lines and (not header or len(current_chunk_lines) > 1):
                    remaining = "\n".join(current_chunk_lines)
                    chunk_id = _compute_chunk_id(remaining)
                    if chunk_id not in seen_ids:
                        seen_ids.add(chunk_id)
                        chunks.append(Chunk(
                            content=remaining,
                            chunk_id=chunk_id,
                            metadata={**doc.metadata, "chunk_type": "table"},
                        ))

        else:
            # Text: use LangChain's recursive splitter
            splits = splitter.split_text(doc.content)
            for split in splits:
                split = split.strip()
                if len(split) < 30:
                    continue  # Skip tiny fragments

                chunk_id = _compute_chunk_id(split)
                if chunk_id not in seen_ids:
                    seen_ids.add(chunk_id)
                    chunks.append(Chunk(
                        content=split,
                        chunk_id=chunk_id,
                        metadata={**doc.metadata, "chunk_type": "text"},
                    ))

    logger.info(
        f"Chunking complete: {len(documents)} docs → {len(chunks)} chunks "
        f"(deduped {len(seen_ids)} unique)"
    )
    return chunks
