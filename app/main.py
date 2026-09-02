from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import BASE_DIR, SAMPLE_DOCS_DIR
from app.rag import RetrievedChunk, get_rag_engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    engine = get_rag_engine()
    if SAMPLE_DOCS_DIR.exists():
        for path in SAMPLE_DOCS_DIR.glob("*"):
            if path.is_file():
                engine.ingest_file(path, path.name)
    yield


app = FastAPI(title="Enterprise KB (Python)", lifespan=lifespan)


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


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "UP", "stack": "FastAPI + LangChain + Chroma"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    from uuid import uuid4

    conversation_id = req.conversation_id or str(uuid4())
    answer, sources = get_rag_engine().chat(req.question, conversation_id)
    return ChatResponse(
        answer=answer,
        conversation_id=conversation_id,
        sources=[_source_to_dict(s) for s in sources],
    )


@app.get("/api/chat/stream")
def stream_chat(question: str, conversation_id: str | None = None) -> StreamingResponse:
    from uuid import uuid4

    conv_id = conversation_id or str(uuid4())

    def event_stream():
        for token in get_rag_engine().stream_chat(question, conv_id):
            yield f"data: {token}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/chat/sources")
def preview_sources(question: str) -> list[dict]:
    return [_source_to_dict(s) for s in get_rag_engine().retrieve_sources(question)]


@app.post("/api/chat/conversation")
def new_conversation() -> dict[str, str]:
    from uuid import uuid4

    return {"conversationId": str(uuid4())}


@app.post("/api/documents/upload", response_model=IngestResult)
async def upload_document(file: UploadFile = File(...)) -> IngestResult:
    import shutil
    from uuid import uuid4

    from app.config import UPLOAD_DIR

    doc_id = str(uuid4())
    filename = Path(file.filename or "upload.txt").name
    saved_path = UPLOAD_DIR / f"{doc_id}_{filename}"

    with saved_path.open("wb") as out:
        shutil.copyfileobj(file.file, out)

    chunk_count = get_rag_engine().ingest_file(saved_path, filename, doc_id)
    return IngestResult(
        doc_id=doc_id,
        filename=filename,
        chunk_count=chunk_count,
        status="READY",
        message=f"文档已成功入库，共切分 {chunk_count} 个片段",
    )


def _source_to_dict(source: RetrievedChunk) -> dict:
    return {
        "filename": source.filename,
        "snippet": source.snippet,
        "score": source.score,
    }


app.mount("/", StaticFiles(directory=BASE_DIR / "static", html=True), name="static")
