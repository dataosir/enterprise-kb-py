"""Backward-compatible re-exports. Prefer app.services and app.models."""

from app.models import RetrievedChunk
from app.services import RagEngine, get_rag_engine

__all__ = ["RagEngine", "RetrievedChunk", "get_rag_engine"]
