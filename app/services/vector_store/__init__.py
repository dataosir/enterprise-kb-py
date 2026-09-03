"""向量库后端 — Chroma（Demo）/ pgvector（生产）。"""

from app.services.vector_store.factory import create_vector_store

__all__ = ["create_vector_store"]
