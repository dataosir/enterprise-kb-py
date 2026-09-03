import logging
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import (
    ASYNC_INGEST,
    ASYNC_INGEST_THRESHOLD_MB,
    BASE_DIR,
    MAX_UPLOAD_SIZE_MB,
)
from app.models import (
    ChatRequest,
    ChatResponse,
    ConversationResponse,
    EsSyncResult,
    HealthResponse,
    IngestResult,
    JobStatusResponse,
    RagSettingsUpdate,
    ReindexResult,
    RetrievedChunk,
)
from app.models.domain import DocumentRecord
from app.services import bootstrap_sample_docs, get_rag_engine
from app.services.arq_pool import close_arq_pool, enqueue_ingest_job
from app.store import get_document_store
from app.store.object_storage import get_object_storage
from app.store.object_storage.factory import s3_status
from app.store.pg_client import pg_status
from app.store.conversation_store import conversation_store_type, get_conversation_store
from app.store.job_store import get_job_store
from app.store.redis_client import redis_status

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    engine = get_rag_engine()
    bootstrap_sample_docs(engine)
    yield
    await close_arq_pool()


app = FastAPI(
    title="Enterprise KB (Python)",
    description="本地企业知识库 RAG Demo — FastAPI + LangChain + Chroma",
    lifespan=lifespan,
)


@app.get("/api/settings/rag")
def get_rag_settings() -> dict:
    return get_rag_engine().get_settings()


@app.put("/api/settings/rag")
def update_rag_settings(req: RagSettingsUpdate) -> dict:
    payload = req.model_dump(exclude_unset=True)
    if not payload:
        raise HTTPException(status_code=400, detail="至少提供一个参数")

    try:
        return get_rag_engine().update_settings(
            top_k=req.top_k,
            chunk_size=req.chunk_size,
            chunk_overlap=req.chunk_overlap,
            score_threshold=req.score_threshold if "score_threshold" in payload else ...,
            fetch_k=req.fetch_k,
            use_mmr=req.use_mmr,
            mmr_lambda=req.mmr_lambda,
            use_rerank=req.use_rerank,
            temperature=req.temperature,
            history_turns=req.history_turns,
            max_context_chars=req.max_context_chars,
            system_prompt=req.system_prompt,
            snippet_length=req.snippet_length,
            retrieval_mode=req.retrieval_mode,
            hybrid_alpha=req.hybrid_alpha,
            rrf_k=req.rrf_k,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/settings/rag/reindex", response_model=ReindexResult)
def reindex_documents() -> ReindexResult:
    result = get_rag_engine().reindex_all()
    return ReindexResult(**result)


@app.post("/api/settings/rag/sync-es", response_model=EsSyncResult)
def sync_es_index() -> EsSyncResult:
    try:
        result = get_rag_engine().sync_es_index()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EsSyncResult(**result)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    store = get_document_store()
    engine = get_rag_engine()
    settings = engine.settings_store.get()
    es_store = engine.es_store
    stack = "FastAPI + LangChain"
    if engine.vectorstore.backend == "pgvector":
        stack += " + pgvector"
    else:
        stack += " + Chroma"
    if redis_status() == "connected":
        stack += " + Redis"
    if es_store.enabled:
        stack += " + Elasticsearch"
    if engine.object_storage.backend == "s3":
        stack += " + MinIO"
    return HealthResponse(
        status="UP",
        stack=stack,
        documents=store.count(),
        ready_documents=store.count_ready(),
        es_enabled=es_store.enabled,
        es_status=es_store.status(),
        retrieval_mode=settings.retrieval_mode,
        redis_status=redis_status(),
        conversation_store=conversation_store_type(),
        async_ingest_enabled=ASYNC_INGEST and redis_status() == "connected",
        vector_store=engine.vectorstore.backend,
        vector_status=engine.vectorstore.status(),
        vector_chunk_count=engine.vector_count(),
        pg_status=pg_status(),
        storage_backend=engine.object_storage.backend,
        storage_status=engine.object_storage.status(),
        s3_status=s3_status(),
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


@app.get("/api/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(conversation_id: str) -> ConversationResponse:
    store = get_conversation_store()
    return ConversationResponse(
        conversation_id=conversation_id,
        messages=store.get_messages(conversation_id),
    )


@app.delete("/api/conversations/{conversation_id}")
def clear_conversation(conversation_id: str) -> dict[str, str]:
    cleared = get_conversation_store().clear(conversation_id)
    if not cleared:
        raise HTTPException(status_code=404, detail="Conversation not found or already empty")
    return {"message": "会话已清空"}


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def get_job_status(job_id: str) -> JobStatusResponse:
    if redis_status() != "connected":
        raise HTTPException(status_code=503, detail="Redis 未配置或不可用")
    job = get_job_store().get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    data = get_job_store().to_api_dict(job)
    return JobStatusResponse(**data)


@app.post("/api/documents/upload", response_model=IngestResult)
async def upload_document(file: UploadFile = File(...)) -> IngestResult:
    from datetime import datetime, timezone

    storage = get_object_storage()

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
    storage_ref = storage.put_upload(doc_id, filename, content)

    use_async = (
        ASYNC_INGEST
        and redis_status() == "connected"
        and len(content) >= ASYNC_INGEST_THRESHOLD_MB * 1024 * 1024
    )

    if use_async:
        get_document_store().add(
            DocumentRecord(
                id=doc_id,
                filename=filename,
                file_path=storage_ref,
                file_size=len(content),
                chunk_count=0,
                status="PROCESSING",
                created_at=datetime.now(timezone.utc),
            )
        )
        try:
            job_store = get_job_store()
            job_id = job_store.create(doc_id, filename)
            enqueued = await enqueue_ingest_job(doc_id, job_id)
            if not enqueued:
                raise RuntimeError("任务入队失败")
        except Exception as exc:
            storage.delete(storage_ref)
            get_document_store().delete(doc_id)
            raise HTTPException(status_code=500, detail=f"异步入库任务创建失败: {exc}") from exc

        return IngestResult(
            doc_id=doc_id,
            filename=filename,
            chunk_count=0,
            status="PROCESSING",
            message="文档已接收，正在后台入库（可查询任务状态）",
            job_id=job_id,
        )

    try:
        chunk_count = get_rag_engine().ingest_file(
            storage_ref, filename, doc_id, file_size=len(content)
        )
    except Exception as exc:
        storage.delete(storage_ref)
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
