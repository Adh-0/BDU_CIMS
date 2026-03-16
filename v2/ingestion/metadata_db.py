"""
metadata_db.py — SQLite tracker for ingested documents.
Enables incremental ingestion: only re-processes new or changed files.
"""

import hashlib
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filepath    TEXT UNIQUE NOT NULL,
    filename    TEXT NOT NULL,
    sha256_hash TEXT NOT NULL,
    file_size   INTEGER NOT NULL,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    ingested_at TEXT NOT NULL
);
"""


def _file_hash(filepath: Path) -> str:
    """Compute SHA256 hash of a file's contents."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


class MetadataDB:
    """SQLite database tracking which files have been ingested.

    Stores file paths, content hashes, and chunk counts so we can
    detect which files are new or changed on subsequent ingestion runs.
    """

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(CREATE_TABLE_SQL)
        self.conn.commit()
        logger.info(f"Metadata DB opened: {self.db_path}")

    def is_file_changed(self, filepath: Path) -> bool:
        """Check if a file is new or has changed since last ingestion.

        Returns True if:
          - File has never been ingested, OR
          - File's SHA256 hash differs from stored hash.
        """
        filepath_str = str(filepath.resolve())
        current_hash = _file_hash(filepath)

        row = self.conn.execute(
            "SELECT sha256_hash FROM documents WHERE filepath = ?",
            (filepath_str,),
        ).fetchone()

        if row is None:
            return True  # New file
        return row["sha256_hash"] != current_hash

    def record_ingestion(self, filepath: Path, chunk_count: int) -> None:
        """Record that a file has been successfully ingested."""
        filepath_resolved = str(filepath.resolve())
        file_hash = _file_hash(filepath)
        now = datetime.now(timezone.utc).isoformat()

        self.conn.execute(
            """
            INSERT INTO documents (filepath, filename, sha256_hash, file_size, chunk_count, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(filepath) DO UPDATE SET
                sha256_hash = excluded.sha256_hash,
                file_size = excluded.file_size,
                chunk_count = excluded.chunk_count,
                ingested_at = excluded.ingested_at
            """,
            (
                filepath_resolved,
                filepath.name,
                file_hash,
                filepath.stat().st_size,
                chunk_count,
                now,
            ),
        )
        self.conn.commit()

    def list_indexed_documents(self) -> list[dict]:
        """Return all indexed documents with their metadata."""
        rows = self.conn.execute(
            "SELECT filename, sha256_hash, chunk_count, file_size, ingested_at "
            "FROM documents ORDER BY ingested_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_total_chunks(self) -> int:
        """Return total number of chunks across all documents."""
        row = self.conn.execute(
            "SELECT COALESCE(SUM(chunk_count), 0) as total FROM documents"
        ).fetchone()
        return row["total"]

    def close(self):
        """Close the database connection."""
        self.conn.close()
