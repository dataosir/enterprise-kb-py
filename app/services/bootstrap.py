from __future__ import annotations

import logging
from pathlib import Path

from app.config import SAMPLE_DOCS_DIR
from app.services.rag_engine import RagEngine

logger = logging.getLogger(__name__)


def bootstrap_sample_docs(engine: RagEngine) -> int:
    """首次启动时加载示例文档，避免重复入库。"""
    if engine.doc_store.count() > 0:
        logger.info("Document store not empty, skipping sample docs bootstrap")
        return 0

    if not SAMPLE_DOCS_DIR.exists():
        logger.warning("Sample docs directory not found: %s", SAMPLE_DOCS_DIR)
        return 0

    loaded = 0
    for path in sorted(SAMPLE_DOCS_DIR.glob("*")):
        if not path.is_file():
            continue
        chunk_count = engine.ingest_file(path, path.name)
        loaded += chunk_count
        logger.info("Bootstrapped sample doc: %s (%d chunks)", path.name, chunk_count)

    return loaded
