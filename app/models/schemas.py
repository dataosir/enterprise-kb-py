from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    sources: list[dict]


class IngestResult(BaseModel):
    doc_id: str
    filename: str
    chunk_count: int
    status: str
    message: str


class HealthResponse(BaseModel):
    status: str
    stack: str
    documents: int
    ready_documents: int


class RagSettingsResponse(BaseModel):
    top_k: int = Field(alias="topK", ge=1, le=20)
    chunk_size: int = Field(alias="chunkSize", ge=128, le=4096)
    chunk_overlap: int = Field(alias="chunkOverlap", ge=0, le=1024)
    indexed_chunk_size: int = Field(alias="indexedChunkSize")
    indexed_chunk_overlap: int = Field(alias="indexedChunkOverlap")
    needs_reindex: bool = Field(alias="needsReindex")

    model_config = {"populate_by_name": True}


class RagSettingsUpdate(BaseModel):
    top_k: int | None = Field(default=None, alias="topK", ge=1, le=20)
    chunk_size: int | None = Field(default=None, alias="chunkSize", ge=128, le=4096)
    chunk_overlap: int | None = Field(default=None, alias="chunkOverlap", ge=0, le=1024)

    model_config = {"populate_by_name": True}


class ReindexResult(BaseModel):
    reindexed: int
    total_chunks: int
    message: str
