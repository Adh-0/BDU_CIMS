"""
fusion.py — Reciprocal Rank Fusion for combining search results.
Merges FAISS (semantic) and BM25 (keyword) results into a single ranked list.
"""

import logging
from retrieval.hybrid_retriever import RetrievedDoc

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    faiss_results: list[RetrievedDoc],
    bm25_results: list[RetrievedDoc],
    k: int = 60,
    top_n: int = 5,
) -> list[RetrievedDoc]:
    """Merge two ranked result lists using Reciprocal Rank Fusion (RRF).

    RRF formula: score(doc) = Σ 1 / (k + rank_i)
    where rank_i is the document's rank in list i (1-indexed).

    This gives fair weight to both semantic and keyword matches.
    A document ranked #1 in both lists scores highest.
    A document appearing in only one list still contributes.

    Args:
        faiss_results: Ranked list from FAISS semantic search.
        bm25_results: Ranked list from BM25 keyword search.
        k: RRF constant (default 60 per the original paper).
        top_n: Number of final results to return.

    Returns:
        Top-N documents sorted by combined RRF score.
    """
    # Map chunk_id → (best doc, cumulative RRF score)
    scores: dict[str, float] = {}
    doc_map: dict[str, RetrievedDoc] = {}

    # Score FAISS results
    for rank, doc in enumerate(faiss_results, start=1):
        cid = doc.chunk_id
        rrf_score = 1.0 / (k + rank)
        scores[cid] = scores.get(cid, 0.0) + rrf_score
        if cid not in doc_map:
            doc_map[cid] = doc

    # Score BM25 results
    for rank, doc in enumerate(bm25_results, start=1):
        cid = doc.chunk_id
        rrf_score = 1.0 / (k + rank)
        scores[cid] = scores.get(cid, 0.0) + rrf_score
        if cid not in doc_map:
            doc_map[cid] = doc

    # Sort by combined score (descending)
    sorted_ids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

    results = []
    for cid in sorted_ids[:top_n]:
        doc = doc_map[cid]
        results.append(RetrievedDoc(
            content=doc.content,
            score=scores[cid],
            metadata=doc.metadata,
            chunk_id=cid,
            source="fusion",
        ))

    logger.debug(
        f"RRF fusion: {len(faiss_results)} FAISS + {len(bm25_results)} BM25 "
        f"→ {len(results)} fused (from {len(scores)} unique chunks)"
    )
    return results
