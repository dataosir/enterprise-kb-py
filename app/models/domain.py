from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class RetrievedChunk:
    filename: str
    content: str
    snippet: str
    score: float


@dataclass
class DocumentRecord:
    id: str
    filename: str
    file_path: str
    file_size: int
    chunk_count: int
    status: str
    created_at: datetime

    def to_api_dict(self) -> dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "fileSize": self.file_size,
            "chunkCount": self.chunk_count,
            "status": self.status,
            "createdAt": self.created_at.isoformat(),
        }
