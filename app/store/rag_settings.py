from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from app.config import CHUNK_OVERLAP, CHUNK_SIZE, TOP_K

logger = logging.getLogger(__name__)


@dataclass
class RagSettings:
    top_k: int
    chunk_size: int
    chunk_overlap: int
    indexed_chunk_size: int
    indexed_chunk_overlap: int

    @property
    def needs_reindex(self) -> bool:
        return (
            self.chunk_size != self.indexed_chunk_size
            or self.chunk_overlap != self.indexed_chunk_overlap
        )

    def to_api_dict(self) -> dict:
        return {
            "topK": self.top_k,
            "chunkSize": self.chunk_size,
            "chunkOverlap": self.chunk_overlap,
            "indexedChunkSize": self.indexed_chunk_size,
            "indexedChunkOverlap": self.indexed_chunk_overlap,
            "needsReindex": self.needs_reindex,
        }


class RagSettingsStore:
    """RAG 运行时参数 — 持久化到 JSON，支持页面动态调参。"""

    def __init__(self, settings_path: Path) -> None:
        self.settings_path = settings_path
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings = self._load()

    def get(self) -> RagSettings:
        return self._settings

    def update(
        self,
        *,
        top_k: int | None = None,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> RagSettings:
        if top_k is not None:
            self._settings.top_k = top_k
        if chunk_size is not None:
            self._settings.chunk_size = chunk_size
        if chunk_overlap is not None:
            self._settings.chunk_overlap = chunk_overlap
        self._save()
        return self._settings

    def mark_indexed(self) -> RagSettings:
        self._settings.indexed_chunk_size = self._settings.chunk_size
        self._settings.indexed_chunk_overlap = self._settings.chunk_overlap
        self._save()
        return self._settings

    def _load(self) -> RagSettings:
        if self.settings_path.exists():
            try:
                data = json.loads(self.settings_path.read_text(encoding="utf-8"))
                return RagSettings(
                    top_k=int(data.get("top_k", TOP_K)),
                    chunk_size=int(data.get("chunk_size", CHUNK_SIZE)),
                    chunk_overlap=int(data.get("chunk_overlap", CHUNK_OVERLAP)),
                    indexed_chunk_size=int(data.get("indexed_chunk_size", CHUNK_SIZE)),
                    indexed_chunk_overlap=int(
                        data.get("indexed_chunk_overlap", CHUNK_OVERLAP)
                    ),
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                logger.warning("Invalid rag settings file, using defaults")

        settings = RagSettings(
            top_k=TOP_K,
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            indexed_chunk_size=CHUNK_SIZE,
            indexed_chunk_overlap=CHUNK_OVERLAP,
        )
        self._save_settings(settings)
        return settings

    def _save(self) -> None:
        self._save_settings(self._settings)

    def _save_settings(self, settings: RagSettings) -> None:
        self.settings_path.write_text(
            json.dumps(asdict(settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


_store: RagSettingsStore | None = None


def get_rag_settings_store() -> RagSettingsStore:
    global _store
    if _store is None:
        from app.config import DATA_DIR

        _store = RagSettingsStore(DATA_DIR / "rag_settings.json")
    return _store
