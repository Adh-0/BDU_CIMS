"""
run_ingest.py — CLI entrypoint for the document ingestion pipeline.
Processes all documents in data/documents/, builds FAISS + BM25 indexes.

Usage:
    cd d:\RAG_CHAT\v2
    python -m ingestion.run_ingest
"""

import logging
import sys
import time
from pathlib import Path

# Ensure v2 root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from ingestion.loader import load_document, SUPPORTED_EXTENSIONS
from ingestion.chunker import chunk_documents
from ingestion.embedder import EmbeddingIndexBuilder
from ingestion.metadata_db import MetadataDB

# ── Setup logging ────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("ingestion")


def main():
    start_time = time.time()

    print()
    print("=" * 50)
    print("  BDU RAG v2 — Document Ingestion Pipeline")
    print("=" * 50)
    print()

    # ── 1. Find documents ────────────────────────────────────────
    docs_dir = config.DOCUMENTS_DIR
    print(f"[SCAN] Documents directory: {docs_dir}")

    all_files = sorted(
        p for p in docs_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if not all_files:
        print(f"[WARN] No supported files found in {docs_dir}")
        print(f"       Supported formats: {', '.join(SUPPORTED_EXTENSIONS.keys())}")
        print(f"       Place your documents in: {docs_dir}")
        return

    print(f"[FOUND] {len(all_files)} supported files")
    for f in all_files:
        print(f"       • {f.name} ({f.stat().st_size / 1024:.1f} KB)")

    # ── 2. Check for changes (incremental ingestion) ─────────────
    db = MetadataDB(config.METADATA_DB_PATH)

    changed_files = [f for f in all_files if db.is_file_changed(f)]
    unchanged_count = len(all_files) - len(changed_files)

    if unchanged_count > 0:
        print(f"[SKIP] {unchanged_count} file(s) unchanged since last ingestion")

    if not changed_files:
        print("[DONE] All files up to date. Nothing to re-index.")
        print(f"       Total chunks in index: {db.get_total_chunks()}")
        db.close()
        return

    print(f"[PROC] Processing {len(changed_files)} new/changed file(s)...")
    print()

    # ── 3. Load documents ────────────────────────────────────────
    all_docs = []
    for filepath in changed_files:
        docs = load_document(filepath)
        if docs:
            print(f"  ✓ {filepath.name}: {len(docs)} segments extracted")
            all_docs.extend(docs)
        else:
            print(f"  ✗ {filepath.name}: no usable content extracted")

    if not all_docs:
        print("\n[ERROR] No content extracted from any file!")
        db.close()
        return

    # Show content type breakdown
    type_counts = {}
    for d in all_docs:
        ct = d.metadata.get("content_type", "unknown")
        type_counts[ct] = type_counts.get(ct, 0) + 1
    print(f"\n[LOAD] {len(all_docs)} segments total:")
    for ct, count in type_counts.items():
        print(f"       • {ct}: {count}")

    # ── 4. Chunk documents ───────────────────────────────────────
    print(f"\n[CHUNK] Splitting into chunks (size={config.CHUNK_SIZE}, overlap={config.CHUNK_OVERLAP})...")
    chunks = chunk_documents(all_docs, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
    print(f"[DONE] {len(chunks)} chunks created")

    # ── 5. Build indexes ─────────────────────────────────────────
    print("\n[INDEX] Building search indexes...")
    builder = EmbeddingIndexBuilder(model_name=config.EMBEDDING_MODEL)

    faiss_count = builder.build_faiss_index(chunks, config.FAISS_INDEX_DIR)
    print(f"  ✓ FAISS index: {faiss_count} vectors → {config.FAISS_INDEX_DIR}")

    bm25_count = builder.build_bm25_index(chunks, config.BM25_INDEX_PATH)
    print(f"  ✓ BM25 index:  {bm25_count} docs → {config.BM25_INDEX_PATH}")

    # ── 6. Update metadata DB ────────────────────────────────────
    # Record each file's ingestion (for incremental next time)
    # Note: we record the file as having contributed ALL chunks,
    # but in reality a full rebuild uses all files' chunks together.
    # This is fine — the hash check is what matters for incremental.
    for filepath in changed_files:
        file_chunks = [
            c for c in chunks
            if c.metadata.get("source") == filepath.name
        ]
        db.record_ingestion(filepath, len(file_chunks))

    # ── Summary ──────────────────────────────────────────────────
    elapsed = time.time() - start_time
    print()
    print("=" * 50)
    print(f"  ✅ Ingestion complete in {elapsed:.1f}s")
    print(f"     Files processed: {len(changed_files)}")
    print(f"     Chunks created:  {len(chunks)}")
    print(f"     FAISS vectors:   {faiss_count}")
    print(f"     BM25 documents:  {bm25_count}")
    print("=" * 50)
    print()

    db.close()


if __name__ == "__main__":
    main()
