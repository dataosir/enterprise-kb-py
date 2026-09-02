from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.documents import Document

logger = logging.getLogger(__name__)

DEFAULT_RERANK_MODEL = "BAAI/bge-reranker-base"


class Reranker:
    """Cross-Encoder 重排序 — 懒加载，默认关闭以节省内存。"""

    def __init__(self, model_name: str = DEFAULT_RERANK_MODEL) -> None:
        self.model_name = model_name
        self._model = None

    def rerank(
        self,
        query: str,
        candidates: list[tuple[Document, float]],
        top_k: int,
    ) -> list[tuple[Document, float]]:
        if not candidates:
            return []

        self._ensure_loaded()
        pairs = [(query, doc.page_content) for doc, _ in candidates]
        scores = self._model.predict(pairs)

        ranked = sorted(
            zip(candidates, scores, strict=False),
            key=lambda item: float(item[1]),
            reverse=True,
        )
        return [(doc, float(score)) for (doc, _), score in ranked[:top_k]]

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return

        from sentence_transformers import CrossEncoder

        logger.info("Loading rerank model: %s (may use ~400MB RAM)", self.model_name)
        self._model = CrossEncoder(self.model_name)
