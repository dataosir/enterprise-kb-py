from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.models.domain import DocumentRecord


class DocumentStore:
    """文档元数据持久化 — SQLite 本地存储，无需额外服务。"""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'READY',
                    created_at TEXT NOT NULL
                )
                """
            )

    def add(self, record: DocumentRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO documents (id, filename, file_path, file_size, chunk_count, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.filename,
                    record.file_path,
                    record.file_size,
                    record.chunk_count,
                    record.status,
                    record.created_at.isoformat(),
                ),
            )

    def get(self, doc_id: str) -> DocumentRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def list_all(self) -> list[DocumentRecord]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM documents ORDER BY created_at DESC").fetchall()
        return [self._row_to_record(row) for row in rows]

    def delete(self, doc_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            return cursor.rowcount > 0

    def count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM documents").fetchone()
        return int(row["cnt"])

    def count_ready(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM documents WHERE status = 'READY'"
            ).fetchone()
        return int(row["cnt"])

    def update_chunk_count(self, doc_id: str, chunk_count: int, status: str = "READY") -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE documents
                SET chunk_count = ?, status = ?
                WHERE id = ?
                """,
                (chunk_count, status, doc_id),
            )
            return cursor.rowcount > 0

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> DocumentRecord:
        return DocumentRecord(
            id=row["id"],
            filename=row["filename"],
            file_path=row["file_path"],
            file_size=row["file_size"],
            chunk_count=row["chunk_count"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )


_store: DocumentStore | None = None


def get_document_store() -> DocumentStore:
    global _store
    if _store is None:
        from app.config import DB_PATH

        _store = DocumentStore(DB_PATH)
    return _store
