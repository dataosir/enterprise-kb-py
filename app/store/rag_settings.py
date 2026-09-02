from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from app.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DEFAULT_SYSTEM_PROMPT,
    FETCH_K,
    HISTORY_TURNS,
    HYBRID_ALPHA,
    MAX_CONTEXT_CHARS,
    MMR_LAMBDA,
    RETRIEVAL_MODE,
    RRF_K,
    SCORE_THRESHOLD,
    SNIPPET_LENGTH,
    TEMPERATURE,
    TOP_K,
    USE_MMR,
    USE_RERANK,
)

logger = logging.getLogger(__name__)


@dataclass
class RagSettings:
    top_k: int
    chunk_size: int
    chunk_overlap: int
    indexed_chunk_size: int
    indexed_chunk_overlap: int
    score_threshold: float | None
    fetch_k: int
    use_mmr: bool
    mmr_lambda: float
    use_rerank: bool
    temperature: float
    history_turns: int
    max_context_chars: int
    system_prompt: str
    snippet_length: int
    retrieval_mode: str
    hybrid_alpha: float
    rrf_k: int

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
            "scoreThreshold": self.score_threshold,
            "fetchK": self.fetch_k,
            "useMmr": self.use_mmr,
            "mmrLambda": self.mmr_lambda,
            "useRerank": self.use_rerank,
            "temperature": self.temperature,
            "historyTurns": self.history_turns,
            "maxContextChars": self.max_context_chars,
            "systemPrompt": self.system_prompt,
            "snippetLength": self.snippet_length,
            "retrievalMode": self.retrieval_mode,
            "hybridAlpha": self.hybrid_alpha,
            "rrfK": self.rrf_k,
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
        score_threshold: float | None = ...,  # type: ignore[assignment]
        fetch_k: int | None = None,
        use_mmr: bool | None = None,
        mmr_lambda: float | None = None,
        use_rerank: bool | None = None,
        temperature: float | None = None,
        history_turns: int | None = None,
        max_context_chars: int | None = None,
        system_prompt: str | None = None,
        snippet_length: int | None = None,
        retrieval_mode: str | None = None,
        hybrid_alpha: float | None = None,
        rrf_k: int | None = None,
    ) -> RagSettings:
        if top_k is not None:
            self._settings.top_k = top_k
        if chunk_size is not None:
            self._settings.chunk_size = chunk_size
        if chunk_overlap is not None:
            self._settings.chunk_overlap = chunk_overlap
        if score_threshold is not ...:
            self._settings.score_threshold = score_threshold
        if fetch_k is not None:
            self._settings.fetch_k = fetch_k
        if use_mmr is not None:
            self._settings.use_mmr = use_mmr
        if mmr_lambda is not None:
            self._settings.mmr_lambda = mmr_lambda
        if use_rerank is not None:
            self._settings.use_rerank = use_rerank
        if temperature is not None:
            self._settings.temperature = temperature
        if history_turns is not None:
            self._settings.history_turns = history_turns
        if max_context_chars is not None:
            self._settings.max_context_chars = max_context_chars
        if system_prompt is not None:
            self._settings.system_prompt = system_prompt.strip() or DEFAULT_SYSTEM_PROMPT
        if snippet_length is not None:
            self._settings.snippet_length = snippet_length
        if retrieval_mode is not None:
            self._settings.retrieval_mode = retrieval_mode
        if hybrid_alpha is not None:
            self._settings.hybrid_alpha = hybrid_alpha
        if rrf_k is not None:
            self._settings.rrf_k = rrf_k

        self._validate()
        self._save()
        return self._settings

    def mark_indexed(self) -> RagSettings:
        self._settings.indexed_chunk_size = self._settings.chunk_size
        self._settings.indexed_chunk_overlap = self._settings.chunk_overlap
        self._save()
        return self._settings

    def _validate(self) -> None:
        settings = self._settings
        if settings.chunk_overlap >= settings.chunk_size:
            raise ValueError("chunk_overlap 必须小于 chunk_size")
        if settings.fetch_k < settings.top_k:
            raise ValueError("fetch_k 不能小于 top_k")
        if settings.use_mmr and settings.use_rerank:
            raise ValueError("MMR 与 Rerank 不能同时开启（内存与延迟考虑，请二选一）")
        if settings.retrieval_mode == "hybrid" and settings.use_mmr:
            raise ValueError("混合检索与 MMR 不能同时开启，请关闭 MMR 或切换为纯向量检索")
        if settings.retrieval_mode not in {"vector", "hybrid"}:
            raise ValueError("retrieval_mode 仅支持 vector 或 hybrid")
        if not 0.0 <= settings.hybrid_alpha <= 1.0:
            raise ValueError("hybrid_alpha 需在 0~1 之间")
        if settings.rrf_k < 1 or settings.rrf_k > 200:
            raise ValueError("rrf_k 需在 1~200 之间")
        if not 0.0 <= settings.mmr_lambda <= 1.0:
            raise ValueError("mmr_lambda 需在 0~1 之间")
        if not 0.0 <= settings.temperature <= 2.0:
            raise ValueError("temperature 需在 0~2 之间")
        if settings.history_turns < 0 or settings.history_turns > 20:
            raise ValueError("history_turns 需在 0~20 之间")
        if settings.max_context_chars < 500 or settings.max_context_chars > 32000:
            raise ValueError("max_context_chars 需在 500~32000 之间")
        if settings.snippet_length < 50 or settings.snippet_length > 1000:
            raise ValueError("snippet_length 需在 50~1000 之间")
        if settings.score_threshold is not None and settings.score_threshold <= 0:
            raise ValueError("score_threshold 需大于 0，或留空表示不过滤")

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
                    score_threshold=_parse_optional_float(data.get("score_threshold")),
                    fetch_k=int(data.get("fetch_k", FETCH_K)),
                    use_mmr=bool(data.get("use_mmr", USE_MMR)),
                    mmr_lambda=float(data.get("mmr_lambda", MMR_LAMBDA)),
                    use_rerank=bool(data.get("use_rerank", USE_RERANK)),
                    temperature=float(data.get("temperature", TEMPERATURE)),
                    history_turns=int(data.get("history_turns", HISTORY_TURNS)),
                    max_context_chars=int(data.get("max_context_chars", MAX_CONTEXT_CHARS)),
                    system_prompt=str(data.get("system_prompt", DEFAULT_SYSTEM_PROMPT)),
                    snippet_length=int(data.get("snippet_length", SNIPPET_LENGTH)),
                    retrieval_mode=str(data.get("retrieval_mode", RETRIEVAL_MODE)),
                    hybrid_alpha=float(data.get("hybrid_alpha", HYBRID_ALPHA)),
                    rrf_k=int(data.get("rrf_k", RRF_K)),
                )
            except (json.JSONDecodeError, TypeError, ValueError):
                logger.warning("Invalid rag settings file, using defaults")

        settings = _default_settings()
        self._save_settings(settings)
        return settings

    def _save(self) -> None:
        self._save_settings(self._settings)

    def _save_settings(self, settings: RagSettings) -> None:
        self.settings_path.write_text(
            json.dumps(asdict(settings), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _default_settings() -> RagSettings:
    return RagSettings(
        top_k=TOP_K,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        indexed_chunk_size=CHUNK_SIZE,
        indexed_chunk_overlap=CHUNK_OVERLAP,
        score_threshold=SCORE_THRESHOLD,
        fetch_k=FETCH_K,
        use_mmr=USE_MMR,
        mmr_lambda=MMR_LAMBDA,
        use_rerank=USE_RERANK,
        temperature=TEMPERATURE,
        history_turns=HISTORY_TURNS,
        max_context_chars=MAX_CONTEXT_CHARS,
        system_prompt=DEFAULT_SYSTEM_PROMPT,
        snippet_length=SNIPPET_LENGTH,
        retrieval_mode=RETRIEVAL_MODE,
        hybrid_alpha=HYBRID_ALPHA,
        rrf_k=RRF_K,
    )


def _parse_optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


_store: RagSettingsStore | None = None


def get_rag_settings_store() -> RagSettingsStore:
    global _store
    if _store is None:
        from app.config import DATA_DIR

        _store = RagSettingsStore(DATA_DIR / "rag_settings.json")
    return _store
