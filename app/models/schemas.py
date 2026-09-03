from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    sources: list[dict]


class IngestResult(BaseModel):
    doc_id: str = Field(alias="docId")
    filename: str
    chunk_count: int = Field(alias="chunkCount")
    status: str
    message: str
    job_id: str | None = Field(default=None, alias="jobId")

    model_config = {"populate_by_name": True}


class JobStatusResponse(BaseModel):
    job_id: str = Field(alias="jobId")
    doc_id: str | None = Field(default=None, alias="docId")
    filename: str | None = None
    status: str
    chunk_count: int = Field(alias="chunkCount", default=0)
    message: str | None = None
    error: str | None = None
    created_at: str | None = Field(default=None, alias="createdAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")

    model_config = {"populate_by_name": True}


class ConversationResponse(BaseModel):
    conversation_id: str = Field(alias="conversationId")
    messages: list[dict]

    model_config = {"populate_by_name": True}


class HealthResponse(BaseModel):
    status: str
    stack: str
    documents: int
    ready_documents: int
    es_enabled: bool = Field(alias="esEnabled")
    es_status: str = Field(alias="esStatus")
    retrieval_mode: str = Field(alias="retrievalMode")
    redis_status: str = Field(alias="redisStatus", default="not_configured")
    conversation_store: str = Field(alias="conversationStore", default="memory")
    async_ingest_enabled: bool = Field(alias="asyncIngestEnabled", default=False)
    vector_store: str = Field(alias="vectorStore", default="chroma")
    vector_status: str = Field(alias="vectorStatus", default="connected")
    vector_chunk_count: int = Field(alias="vectorChunkCount", default=0)
    pg_status: str = Field(alias="pgStatus", default="not_configured")
    storage_backend: str = Field(alias="storageBackend", default="local")
    storage_status: str = Field(alias="storageStatus", default="connected")
    s3_status: str = Field(alias="s3Status", default="not_configured")

    model_config = {"populate_by_name": True}


class RagSettingsResponse(BaseModel):
    top_k: int = Field(alias="topK", ge=1, le=20)
    chunk_size: int = Field(alias="chunkSize", ge=128, le=4096)
    chunk_overlap: int = Field(alias="chunkOverlap", ge=0, le=1024)
    indexed_chunk_size: int = Field(alias="indexedChunkSize")
    indexed_chunk_overlap: int = Field(alias="indexedChunkOverlap")
    needs_reindex: bool = Field(alias="needsReindex")
    score_threshold: float | None = Field(default=None, alias="scoreThreshold")
    fetch_k: int = Field(alias="fetchK", ge=1, le=50)
    use_mmr: bool = Field(alias="useMmr")
    mmr_lambda: float = Field(alias="mmrLambda", ge=0.0, le=1.0)
    use_rerank: bool = Field(alias="useRerank")
    temperature: float = Field(ge=0.0, le=2.0)
    history_turns: int = Field(alias="historyTurns", ge=0, le=20)
    max_context_chars: int = Field(alias="maxContextChars", ge=500, le=32000)
    system_prompt: str = Field(alias="systemPrompt", min_length=1, max_length=4000)
    snippet_length: int = Field(alias="snippetLength", ge=50, le=1000)
    retrieval_mode: str = Field(alias="retrievalMode")
    hybrid_alpha: float = Field(alias="hybridAlpha", ge=0.0, le=1.0)
    rrf_k: int = Field(alias="rrfK", ge=1, le=200)
    es_enabled: bool = Field(alias="esEnabled")
    es_status: str = Field(alias="esStatus")
    es_chunk_count: int = Field(alias="esChunkCount", ge=0)
    vector_store: str = Field(alias="vectorStore", default="chroma")
    vector_status: str = Field(alias="vectorStatus", default="connected")
    vector_chunk_count: int = Field(alias="vectorChunkCount", default=0)
    storage_backend: str = Field(alias="storageBackend", default="local")
    storage_status: str = Field(alias="storageStatus", default="connected")

    model_config = {"populate_by_name": True}


class RagSettingsUpdate(BaseModel):
    top_k: int | None = Field(default=None, alias="topK", ge=1, le=20)
    chunk_size: int | None = Field(default=None, alias="chunkSize", ge=128, le=4096)
    chunk_overlap: int | None = Field(default=None, alias="chunkOverlap", ge=0, le=1024)
    score_threshold: float | None = Field(default=None, alias="scoreThreshold")
    fetch_k: int | None = Field(default=None, alias="fetchK", ge=1, le=50)
    use_mmr: bool | None = Field(default=None, alias="useMmr")
    mmr_lambda: float | None = Field(default=None, alias="mmrLambda", ge=0.0, le=1.0)
    use_rerank: bool | None = Field(default=None, alias="useRerank")
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    history_turns: int | None = Field(default=None, alias="historyTurns", ge=0, le=20)
    max_context_chars: int | None = Field(default=None, alias="maxContextChars", ge=500, le=32000)
    system_prompt: str | None = Field(default=None, alias="systemPrompt", min_length=1, max_length=4000)
    snippet_length: int | None = Field(default=None, alias="snippetLength", ge=50, le=1000)
    retrieval_mode: str | None = Field(default=None, alias="retrievalMode")
    hybrid_alpha: float | None = Field(default=None, alias="hybridAlpha", ge=0.0, le=1.0)
    rrf_k: int | None = Field(default=None, alias="rrfK", ge=1, le=200)

    model_config = {"populate_by_name": True}


class ReindexResult(BaseModel):
    reindexed: int
    total_chunks: int
    message: str


class EsSyncResult(BaseModel):
    synced_documents: int
    total_chunks: int
    message: str
