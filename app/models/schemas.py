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
