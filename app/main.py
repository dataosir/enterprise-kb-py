import logging
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import BASE_DIR, MAX_UPLOAD_SIZE_MB
from app.models import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    IngestResult,
    RetrievedChunk,
)
from app.services import bootstrap_sample_docs, get_rag_engine
from app.store import get_document_store

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    engine = get_rag_engine()
    bootstrap_sample_docs(engine)
    yield


app = FastAPI(
    title="Enterprise KB (Python)",
    description="本地企业知识库 RAG Demo — FastAPI + LangChain + Chroma",
    lifespan=lifespan,
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    store = get_document_store()
    return HealthResponse(
        status="UP",
        stack="FastAPI + LangChain + Chroma",
        documents=store.count(),
        ready_documents=store.count_ready(),
    )


@app.get("/api/documents")
def list_documents() -> list[dict]:
    return [doc.to_api_dict() for doc in get_document_store().list_all()]


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str) -> dict[str, str]:
    if not get_rag_engine().delete_document(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "文档已删除"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    conversation_id = req.conversation_id or str(uuid4())
    answer, sources = get_rag_engine().chat(req.question, conversation_id)
    return ChatResponse(
        answer=answer,
        conversation_id=conversation_id,
        sources=[_source_to_dict(s) for s in sources],
    )


@app.get("/api/chat/stream")
def stream_chat(question: str, conversation_id: str | None = None) -> StreamingResponse:
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
    return {"conversationId": str(uuid4())}


@app.post("/api/documents/upload", response_model=IngestResult)
async def upload_document(file: UploadFile = File(...)) -> IngestResult:
    from app.config import UPLOAD_DIR

    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    content = await file.read()
    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"文件大小超过限制（最大 {MAX_UPLOAD_SIZE_MB}MB）",
        )

    doc_id = str(uuid4())
    filename = Path(file.filename).name
    saved_path = UPLOAD_DIR / f"{doc_id}_{filename}"

    with saved_path.open("wb") as out:
        out.write(content)

    try:
        chunk_count = get_rag_engine().ingest_file(
            saved_path, filename, doc_id, file_size=len(content)
        )
    except Exception as exc:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"文档入库失败: {exc}") from exc

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
