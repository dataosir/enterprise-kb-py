from __future__ import annotations

from langchain_core.documents import Document

from app.services.retrieval.es_store import Bm25Hit


def fuse_hybrid_results(
    vector_results: list[tuple[Document, float]],
    bm25_results: list[Bm25Hit],
    *,
    alpha: float,
    rrf_k: int,
) -> list[tuple[Document, float]]:
    """加权 RRF 融合向量与 BM25 检索结果。alpha 为向量权重，BM25 权重为 1-alpha。"""
    doc_map: dict[str, Document] = {}
    scores: dict[str, float] = {}

    for rank, (doc, _) in enumerate(vector_results):
        chunk_id = str(doc.metadata.get("chunk_id", ""))
        if not chunk_id:
            continue
        doc_map[chunk_id] = doc
        scores[chunk_id] = scores.get(chunk_id, 0.0) + alpha * (1.0 / (rrf_k + rank + 1))

    bm25_weight = 1.0 - alpha
    for rank, hit in enumerate(bm25_results):
        chunk_id = hit.chunk_id
        if not chunk_id:
            continue
        doc_map.setdefault(chunk_id, hit.to_document())
        scores[chunk_id] = scores.get(chunk_id, 0.0) + bm25_weight * (1.0 / (rrf_k + rank + 1))

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [(doc_map[chunk_id], score) for chunk_id, score in ranked if chunk_id in doc_map]
