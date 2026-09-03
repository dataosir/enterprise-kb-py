"""中间件思维导图数据源：组件职责、AI/传统分类、等价物、指标影响、实时健康状态。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _node(
    node_id: str,
    label: str,
    *,
    node_type: str,
    group: str,
    role: str,
    ai_native: bool | None = None,
    config: str = "",
    profile: str = "both",
    alternatives: list[dict[str, str]] | None = None,
    impacts: list[str] | None = None,
    health_key: str | None = None,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "label": label,
        "type": node_type,
        "group": group,
        "role": role,
        "ai_native": ai_native,
        "config": config,
        "profile": profile,
        "alternatives": alternatives or [],
        "impacts": impacts or [],
        "health_key": health_key,
    }


def build_middleware_graph() -> dict[str, Any]:
    """中间件影响关系图（思维导图）。"""
    nodes = [
        _node(
            "fastapi",
            "FastAPI",
            node_type="app",
            group="app",
            role="HTTP 路由、上传、问答 SSE、健康检查与 /metrics",
            ai_native=False,
            profile="both",
            impacts=["API 延迟", "并发承载"],
        ),
        _node(
            "langchain",
            "LangChain",
            node_type="glue",
            group="glue",
            role="Loader / Splitter / Chain 编排胶水层",
            ai_native=None,
            profile="both",
            alternatives=[
                {"name": "LlamaIndex", "pros": "索引抽象强", "cons": "学习曲线"},
                {"name": "自研 Pipeline", "pros": "可控、可去框架化", "cons": "初期工程量大"},
            ],
            impacts=["入库稳定性", "切分一致性"],
        ),
        _node(
            "llm",
            "DeepSeek LLM",
            node_type="ai",
            group="ai",
            role="根据检索上下文 + 历史轮次生成答案（RAG 的 G 环节）",
            ai_native=True,
            config="DEEPSEEK_API_KEY",
            alternatives=[
                {"name": "GPT-4o / 4o-mini", "pros": "生态好、RAGAS 默认裁判", "cons": "成本高"},
                {"name": "Ollama / vLLM", "pros": "数据不出域", "cons": "需 GPU 运维"},
            ],
            impacts=["Faithfulness", "Answer Relevancy", "生成延迟", "Token 成本"],
        ),
        _node(
            "embedding",
            "BGE Embedding",
            node_type="ai",
            group="ai",
            role="文本 → 向量，支撑语义检索与入库",
            ai_native=True,
            config="EMBEDDING_PROVIDER=local",
            alternatives=[
                {"name": "OpenAI Embedding", "pros": "免本地算力", "cons": "按 Token 计费"},
                {"name": "bge-large-zh", "pros": "中文效果更好", "cons": "更慢更重"},
            ],
            impacts=["Hit@K", "MRR", "入库耗时", "换模型需全量重建索引"],
        ),
        _node(
            "reranker",
            "BGE Reranker",
            node_type="ai",
            group="ai",
            role="Cross-Encoder 精排 fetch_k 候选，提升 Top1 稳定性",
            ai_native=True,
            config="RAG_USE_RERANK=true",
            alternatives=[
                {"name": "Cohere Rerank API", "pros": "免本地模型", "cons": "按次计费"},
                {"name": "不调 rerank", "pros": "零额外延迟", "cons": "Hit@1 波动大"},
            ],
            impacts=["Hit@1", "MRR", "检索延迟 +200~400ms"],
        ),
        _node(
            "chroma",
            "Chroma",
            node_type="ai",
            group="ai",
            role="Demo 嵌入式向量索引，similarity_search / MMR",
            ai_native=True,
            config="VECTOR_STORE=chroma",
            profile="demo",
            alternatives=[
                {"name": "pgvector", "pros": "生产级备份与扩展", "cons": "需 PG 容器"},
                {"name": "Pinecone / Qdrant", "pros": "托管或高性能", "cons": "额外集群"},
            ],
            impacts=["Hit@K", "向量 chunk 数", "多实例不可用"],
            health_key="vector_status",
        ),
        _node(
            "pgvector",
            "pgvector",
            node_type="ai_served",
            group="ai_served",
            role="PostgreSQL 向量扩展，生产向量索引 + 与元数据同库",
            ai_native=False,
            config="VECTOR_STORE=pgvector + DATABASE_URL",
            profile="enterprise",
            alternatives=[
                {"name": "Milvus / Qdrant", "pros": "专用向量性能", "cons": "独立运维"},
                {"name": "Chroma", "pros": "零运维 Demo", "cons": "难水平扩展"},
            ],
            impacts=["Hit@K", "备份/HA", "vector_chunk_count"],
            health_key="vector_status",
        ),
        _node(
            "elasticsearch",
            "Elasticsearch + IK",
            node_type="ai_served",
            group="ai_served",
            role="BM25 全文索引，hybrid 模式与向量 RRF 融合",
            ai_native=False,
            config="RAG_RETRIEVAL_MODE=hybrid",
            profile="enterprise",
            alternatives=[
                {"name": "OpenSearch", "pros": "ES 兼容开源分支", "cons": "生态略分裂"},
                {"name": "仅 vector", "pros": "架构最简单", "cons": "关键词类 Hit@1 波动"},
            ],
            impacts=["keyword 类 Hit@1", "hybrid 延迟 ~55ms", "专有名词召回"],
            health_key="es_status",
        ),
        _node(
            "redis",
            "Redis",
            node_type="traditional",
            group="traditional",
            role="多轮会话、ARQ 任务队列、异步入库 Job 状态",
            ai_native=False,
            config="REDIS_URL / CONVERSATION_STORE=auto",
            profile="enterprise",
            alternatives=[
                {"name": "进程内内存", "pros": "零依赖", "cons": "重启丢失、无法多实例"},
                {"name": "Celery + RabbitMQ", "pros": "企业级任务流", "cons": "比 ARQ 重"},
            ],
            impacts=["多轮上下文质量", "大文件入库不阻塞 API", "async_ingest"],
            health_key="redis_status",
        ),
        _node(
            "arq",
            "ARQ Worker",
            node_type="traditional",
            group="traditional",
            role="消费异步入库：解析 → 切分 → Embedding → 写向量库 + ES",
            ai_native=False,
            config="ASYNC_INGEST=auto",
            profile="enterprise",
            alternatives=[
                {"name": "Celery", "pros": "功能最全", "cons": "配置复杂"},
                {"name": "同步入库", "pros": "实现简单", "cons": "大 PDF 阻塞 API"},
            ],
            impacts=["入库吞吐", "API P99 延迟"],
            health_key="async_ingest_enabled",
        ),
        _node(
            "minio",
            "MinIO / S3",
            node_type="traditional",
            group="traditional",
            role="原始文件对象存储，多实例共享 uploads",
            ai_native=False,
            config="STORAGE_BACKEND=s3",
            profile="enterprise",
            alternatives=[
                {"name": "本地盘", "pros": "零依赖 Demo", "cons": "无法多实例"},
                {"name": "AWS S3 / OSS", "pros": "托管 SLA", "cons": "费用与合规"},
            ],
            impacts=["多实例一致性", "备份与生命周期"],
            health_key="storage_status",
        ),
        _node(
            "sqlite",
            "SQLite",
            node_type="traditional",
            group="traditional",
            role="Demo 文档元数据 catalog（id、路径、状态、chunk 数）",
            ai_native=False,
            profile="demo",
            alternatives=[
                {"name": "PostgreSQL", "pros": "生产级、可扩展", "cons": "需容器"},
            ],
            impacts=["文档列表", "入库状态追踪"],
        ),
        _node(
            "postgres",
            "PostgreSQL",
            node_type="traditional",
            group="traditional",
            role="企业元数据 + pgvector 宿主库",
            ai_native=False,
            config="DATABASE_URL",
            profile="enterprise",
            alternatives=[
                {"name": "MySQL", "pros": "普及", "cons": "无原生向量扩展"},
            ],
            impacts=["元数据一致性", "与向量同库事务"],
            health_key="pg_status",
        ),
        _node(
            "prometheus",
            "/metrics",
            node_type="ops",
            group="ops",
            role="Prometheus 格式：问答数、检索/生成耗时、Token、反馈计数",
            ai_native=False,
            profile="both",
            alternatives=[
                {"name": "OpenTelemetry", "pros": "标准链路追踪", "cons": "接入成本高"},
                {"name": "云 APM", "pros": "开箱即用", "cons": "vendor lock-in"},
            ],
            impacts=["线上 SLO", "成本观测", "延迟 P50/P95"],
        ),
        _node(
            "metric_hit1",
            "Hit@1 / MRR",
            node_type="metric",
            group="metrics",
            role="检索排名质量 — L2 benchmark 核心指标",
            impacts=["评测看板 L2", "baseline CI 门禁"],
        ),
        _node(
            "metric_faith",
            "Faithfulness",
            node_type="metric",
            group="metrics",
            role="生成是否忠于检索上下文 — L3 RAGAS",
            impacts=["防幻觉", "上线可信度"],
        ),
        _node(
            "metric_latency",
            "检索/生成延迟",
            node_type="metric",
            group="metrics",
            role="retrieval_ms、generation_ms、/metrics 直方图",
            impacts=["用户体验", "容量规划"],
        ),
        _node(
            "metric_cost",
            "Token / 算力成本",
            node_type="metric",
            group="metrics",
            role="LLM Token、本地 Embedding/Rerank 内存占用",
            impacts=["预算控制", "实例规格选型"],
        ),
    ]

    edges = [
        {"from": "fastapi", "to": "langchain", "effect": "路由到 RAG Pipeline"},
        {"from": "langchain", "to": "embedding", "effect": "切分后编码"},
        {"from": "embedding", "to": "chroma", "effect": "Demo 写向量"},
        {"from": "embedding", "to": "pgvector", "effect": "企业写向量"},
        {"from": "embedding", "to": "elasticsearch", "effect": "hybrid 时写 BM25"},
        {"from": "chroma", "to": "metric_hit1", "effect": "向量召回质量"},
        {"from": "pgvector", "to": "metric_hit1", "effect": "生产向量召回"},
        {"from": "elasticsearch", "to": "metric_hit1", "effect": "keyword 补召回"},
        {"from": "reranker", "to": "metric_hit1", "effect": "精排提升 Top1"},
        {"from": "reranker", "to": "metric_latency", "effect": "+200~400ms"},
        {"from": "llm", "to": "metric_faith", "effect": "生成质量上限"},
        {"from": "llm", "to": "metric_latency", "effect": "生成耗时"},
        {"from": "llm", "to": "metric_cost", "effect": "Token 计费"},
        {"from": "redis", "to": "llm", "effect": "多轮历史上下文"},
        {"from": "minio", "to": "arq", "effect": "大文件异步入库"},
        {"from": "arq", "to": "embedding", "effect": "异步编码入库"},
        {"from": "sqlite", "to": "fastapi", "effect": "文档元数据"},
        {"from": "postgres", "to": "pgvector", "effect": "同库元数据+向量"},
        {"from": "prometheus", "to": "metric_latency", "effect": "线上观测"},
        {"from": "metric_hit1", "to": "rag_system", "effect": "检索是否找对"},
        {"from": "metric_faith", "to": "rag_system", "effect": "回答是否可信"},
        {"from": "metric_latency", "to": "rag_system", "effect": "体验与 SLO"},
        {"from": "metric_cost", "to": "rag_system", "effect": "运营成本"},
    ]

    categories = [
        {"id": "ai", "label": "AI 原生", "color": "#f59e0b", "description": "因 RAG 语义检索与生成而引入"},
        {"id": "ai_served", "label": "传统 · 为 AI 服务", "color": "#a855f7", "description": "传统组件，在本项目中提升检索质量或规模"},
        {"id": "traditional", "label": "传统互联网", "color": "#3b82f6", "description": "缓存、队列、对象存储、关系库等通用基础设施"},
        {"id": "app", "label": "应用层", "color": "#64748b", "description": "Web API 与编排入口"},
        {"id": "glue", "label": "AI 框架胶水", "color": "#94a3b8", "description": "LangChain 等编排，非独立中间件"},
        {"id": "ops", "label": "可观测", "color": "#22c55e", "description": "传统运维，衡量 RAG SLO"},
        {"id": "metrics", "label": "受影响指标", "color": "#ef4444", "description": "L1–L4 评测与线上指标"},
    ]

    profiles = {
        "demo": {
            "label": "Demo Profile",
            "components": ["Chroma", "SQLite", "本地盘", "内存会话", "同步入库"],
            "containers": 0,
        },
        "enterprise": {
            "label": "Enterprise Profile",
            "components": ["pgvector", "PostgreSQL", "MinIO", "Redis", "ES", "ARQ"],
            "containers": 4,
        },
    }

    return {
        "root": {"id": "rag_system", "label": "RAG 系统质量", "type": "outcome"},
        "nodes": nodes,
        "edges": edges,
        "categories": categories,
        "profiles": profiles,
    }


def _health_status(health: dict[str, Any], key: str | None) -> str | None:
    if not key or not health:
        return None
    if key == "async_ingest_enabled":
        return "enabled" if health.get("async_ingest_enabled") else "disabled"
    value = health.get(key)
    if value is None:
        camel = "".join(w if i == 0 else w.capitalize() for i, w in enumerate(key.split("_")))
        value = health.get(camel)
    return str(value) if value is not None else None


def _active_profile(health: dict[str, Any]) -> str:
    if health.get("vector_store") == "pgvector" or health.get("vectorStore") == "pgvector":
        return "enterprise"
    if health.get("storage_backend") == "s3" or health.get("storageBackend") == "s3":
        return "enterprise"
    if health.get("redis_status") == "connected" or health.get("redisStatus") == "connected":
        return "enterprise"
    return "demo"


def _flow_step(
    step_id: str,
    order: int,
    title: str,
    *,
    description: str,
    middleware_ids: list[str],
    phase: str,
    optional: bool = False,
    branch: str | None = None,
    latency_hint: str = "",
    code_ref: str = "",
    output: str = "",
) -> dict[str, Any]:
    return {
        "id": step_id,
        "order": order,
        "title": title,
        "description": description,
        "middleware_ids": middleware_ids,
        "phase": phase,
        "optional": optional,
        "branch": branch,
        "latency_hint": latency_hint,
        "code_ref": code_ref,
        "output": output,
    }


def build_query_flow(health: dict[str, Any] | None = None) -> dict[str, Any]:
    """用户提问时各中间件参与的完整流程（与 RagEngine.chat/stream_chat 对齐）。"""
    health = health or {}
    profile = _active_profile(health)
    settings = health.get("rag_settings") or health.get("ragSettings") or {}
    retrieval_mode = (
        health.get("retrieval_mode")
        or health.get("retrievalMode")
        or settings.get("retrievalMode")
        or "vector"
    )
    use_rerank = bool(settings.get("useRerank"))
    use_mmr = bool(settings.get("useMmr"))
    score_threshold = settings.get("scoreThreshold")
    has_threshold = score_threshold is not None
    es_enabled = health.get("es_enabled") or health.get("esEnabled")
    es_status = health.get("es_status") or health.get("esStatus")
    hybrid_active = retrieval_mode == "hybrid" and es_enabled and es_status == "connected"
    vector_backend = health.get("vector_store") or health.get("vectorStore") or (
        "pgvector" if profile == "enterprise" else "chroma"
    )
    conv_store = health.get("conversation_store") or health.get("conversationStore") or (
        "redis" if profile == "enterprise" else "memory"
    )
    vector_mw = "pgvector" if vector_backend == "pgvector" else "chroma"

    steps = [
        _flow_step(
            "user_input",
            1,
            "用户输入问题",
            description="用户在 Web UI 或 API 中提交自然语言问题，可携带 conversation_id 维持多轮上下文。",
            middleware_ids=[],
            phase="input",
            output="question + conversation_id",
        ),
        _flow_step(
            "fastapi_route",
            2,
            "FastAPI 路由接收",
            description="POST /api/chat 或 SSE /api/chat/stream，鉴权后交给 RagEngine。",
            middleware_ids=["fastapi"],
            phase="input",
            code_ref="main.py → rag_engine.stream_chat()",
            latency_hint="< 5ms",
        ),
        _flow_step(
            "read_history",
            3,
            "读取多轮历史",
            description=f"从{'Redis' if conv_store == 'redis' else '进程内存'}加载最近 N 轮问答，格式化为 history 字符串注入 Prompt。",
            middleware_ids=["redis"] if conv_store == "redis" else [],
            phase="context",
            code_ref="conversation_store.get_turns()",
            latency_hint="~1–5ms",
            output="history 文本",
        ),
        _flow_step(
            "embed_query",
            4,
            "问题向量化",
            description="BGE Embedding 将用户问题编码为向量，用于语义相似度检索。",
            middleware_ids=["embedding"],
            phase="retrieval",
            code_ref="HuggingFaceEmbeddings.embed_query()",
            latency_hint="~5–15ms",
            output="query 向量",
        ),
        _flow_step(
            "vector_search",
            5,
            "向量相似度检索",
            description=f"在 {vector_backend} 中 similarity_search，取 fetch_k={settings.get('fetchK', 20)} 条候选 chunk。",
            middleware_ids=[vector_mw],
            phase="retrieval",
            branch="vector" if not use_mmr else None,
            code_ref="vectorstore.similarity_search_with_score(question, k=fetch_k)",
            latency_hint="~10–20ms",
            output="候选 chunk 列表 + 距离分数",
        ),
        _flow_step(
            "mmr_search",
            5,
            "MMR 多样性检索",
            description="Maximal Marginal Relevance：在相关性与多样性间权衡，减少 Top-K 内容重复。",
            middleware_ids=[vector_mw, "embedding"],
            phase="retrieval",
            optional=True,
            branch="mmr",
            code_ref="vectorstore.max_marginal_relevance_search()",
            latency_hint="~15–30ms",
            output="多样化 chunk 列表",
        ),
        _flow_step(
            "es_bm25",
            6,
            "ES BM25 全文检索",
            description="IK 分词后对 chunk 正文做关键词匹配，弥补向量检索对专有名词的不足。",
            middleware_ids=["elasticsearch"],
            phase="retrieval",
            optional=True,
            branch="hybrid",
            code_ref="es_store.search(question, size=fetch_k)",
            latency_hint="~30–50ms",
            output="BM25 排序 chunk 列表",
        ),
        _flow_step(
            "rrf_fuse",
            7,
            "RRF 融合排序",
            description=f"Reciprocal Rank Fusion 合并向量与 BM25 两路结果，alpha={settings.get('hybridAlpha', 0.5)}。",
            middleware_ids=["elasticsearch", vector_mw],
            phase="retrieval",
            optional=True,
            branch="hybrid",
            code_ref="fuse_hybrid_results(vector, bm25, alpha, rrf_k)",
            latency_hint="~1ms",
            output="融合后候选列表",
        ),
        _flow_step(
            "score_threshold",
            8,
            "相似度阈值过滤",
            description=f"丢弃距离分数 > {score_threshold} 的低相关 chunk（仅纯向量路径）。",
            middleware_ids=[vector_mw],
            phase="retrieval",
            optional=True,
            branch="threshold",
            code_ref="filter score <= score_threshold",
            output="过滤后候选",
        ),
        _flow_step(
            "rerank",
            9,
            "Cross-Encoder 精排",
            description=f"BGE Reranker 对 fetch_k 候选做 query-chunk 交叉编码，取 top_k={settings.get('topK', 4)}。",
            middleware_ids=["reranker"],
            phase="retrieval",
            optional=True,
            branch="rerank",
            code_ref="_reranker.rerank(question, results, top_k)",
            latency_hint="~200–400ms",
            output="精排后 Top-K chunk",
        ),
        _flow_step(
            "truncate_topk",
            10,
            "截取 Top-K",
            description="未开 rerank 时直接取前 top_k 条；组装 RetrievedChunk（filename、snippet、score）。",
            middleware_ids=["langchain"],
            phase="retrieval",
            code_ref="results[:top_k] → RetrievedChunk",
            output="sources[] 引用列表",
        ),
        _flow_step(
            "build_context",
            11,
            "拼接检索上下文",
            description=f"将 Top-K chunk 拼接为 context 字符串，截断至 max_context_chars={settings.get('maxContextChars', 4000)}。",
            middleware_ids=["langchain"],
            phase="generation",
            code_ref="build_context(sources, max_context_chars)",
            output="context 文本",
        ),
        _flow_step(
            "llm_generate",
            12,
            "LLM 流式生成答案",
            description="DeepSeek 根据 system_prompt + context + history + question 生成回答，SSE 逐 token 推送。",
            middleware_ids=["llm"],
            phase="generation",
            code_ref="chain = prompt | llm; chain.stream(...)",
            latency_hint="~800–1200ms",
            output="answer 文本",
        ),
        _flow_step(
            "save_turn",
            13,
            "写入会话记忆",
            description="将本轮 Q&A 追加到 conversation_id，供下一轮 history 使用。",
            middleware_ids=["redis"] if conv_store == "redis" else [],
            phase="output",
            code_ref="conversation_store.append_turn()",
            latency_hint="~1–5ms",
        ),
        _flow_step(
            "record_metrics",
            14,
            "可观测埋点",
            description="记录 retrieval_seconds、generation_seconds、Token 估算、问答计数到 Prometheus /metrics。",
            middleware_ids=["prometheus"],
            phase="output",
            code_ref="record_chat_metrics()",
            output="metrics 时序数据",
        ),
        _flow_step(
            "return_response",
            15,
            "返回答案与引用",
            description="SSE 结束或 JSON 返回 answer + sources（filename、snippet、score），前端展示引用卡片。",
            middleware_ids=["fastapi"],
            phase="output",
            output="answer + citations → 用户",
        ),
    ]

    active_branches: list[str] = ["vector"]
    if use_mmr and not hybrid_active:
        active_branches = ["mmr"]
    elif hybrid_active:
        active_branches = ["hybrid"]
    if has_threshold and not hybrid_active:
        active_branches.append("threshold")
    if use_rerank:
        active_branches.append("rerank")

    phases = [
        {"id": "input", "label": "接入", "color": "#64748b"},
        {"id": "context", "label": "上下文", "color": "#3b82f6"},
        {"id": "retrieval", "label": "检索", "color": "#f59e0b"},
        {"id": "generation", "label": "生成", "color": "#a855f7"},
        {"id": "output", "label": "输出", "color": "#22c55e"},
    ]

    return {
        "example_question": "退款多久到账？",
        "profile": profile,
        "vector_backend": vector_backend,
        "conversation_store": conv_store,
        "retrieval_mode": retrieval_mode,
        "active_branches": active_branches,
        "active_config": {
            "use_rerank": use_rerank,
            "use_mmr": use_mmr,
            "hybrid_active": hybrid_active,
            "score_threshold": score_threshold,
            "top_k": settings.get("topK"),
            "fetch_k": settings.get("fetchK"),
        },
        "phases": phases,
        "steps": steps,
        "edges": [
            {"from": "user_input", "to": "fastapi_route"},
            {"from": "fastapi_route", "to": "read_history"},
            {"from": "read_history", "to": "embed_query"},
            {"from": "embed_query", "to": "vector_search", "branch": "vector"},
            {"from": "embed_query", "to": "mmr_search", "branch": "mmr"},
            {"from": "embed_query", "to": "vector_search", "branch": "hybrid"},
            {"from": "vector_search", "to": "es_bm25", "branch": "hybrid"},
            {"from": "es_bm25", "to": "rrf_fuse", "branch": "hybrid"},
            {"from": "vector_search", "to": "score_threshold", "branch": "vector"},
            {"from": "rrf_fuse", "to": "rerank"},
            {"from": "mmr_search", "to": "rerank"},
            {"from": "vector_search", "to": "rerank", "branch": "vector"},
            {"from": "score_threshold", "to": "rerank"},
            {"from": "rrf_fuse", "to": "truncate_topk"},
            {"from": "mmr_search", "to": "truncate_topk"},
            {"from": "vector_search", "to": "truncate_topk"},
            {"from": "score_threshold", "to": "truncate_topk"},
            {"from": "rerank", "to": "truncate_topk"},
            {"from": "truncate_topk", "to": "build_context"},
            {"from": "build_context", "to": "llm_generate"},
            {"from": "llm_generate", "to": "save_turn"},
            {"from": "save_turn", "to": "record_metrics"},
            {"from": "record_metrics", "to": "return_response"},
        ],
    }


def build_middleware_map(health: dict[str, Any] | None = None) -> dict[str, Any]:
    """聚合思维导图 + 组件卡片 + 当前部署 Profile 与健康状态。"""
    graph = build_middleware_graph()
    health = health or {}
    profile = _active_profile(health)

    components: list[dict[str, Any]] = []
    for node in graph["nodes"]:
        if node["type"] in ("metric",):
            continue
        status = _health_status(health, node.get("health_key"))
        components.append(
            {
                **node,
                "status": status,
                "active": node.get("profile", "both") in ("both", profile),
            }
        )

    stack = health.get("stack", "")
    retrieval_mode = health.get("retrieval_mode") or health.get("retrievalMode", "vector")

    query_flow = build_query_flow(health)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "stack": stack,
        "retrieval_mode": retrieval_mode,
        "health": health,
        "graph": graph,
        "components": components,
        "query_flow": query_flow,
        "data_flows": {
            "ingest": [
                "上传 API",
                "→ MinIO/S3 或本地盘",
                "→ SQLite/PG 元数据",
                "→ [可选] Redis + ARQ 异步",
                "→ Loader + Splitter",
                "→ BGE Embedding",
                "→ Chroma / pgvector",
                "→ [hybrid] Elasticsearch",
            ],
            "query": [
                "用户问题",
                "→ Redis 读历史",
                "→ BGE Embedding → 向量库",
                "→ [hybrid] ES BM25 → RRF",
                "→ [可选] BGE Reranker",
                "→ DeepSeek 生成",
                "→ /metrics 记时",
            ],
        },
        "doc_links": {
            "middleware": "/docs/tech/MIDDLEWARE.md",
            "setup": "/docs/enterprise/MIDDLEWARE_SETUP.md",
            "evaluation": "/docs/tech/EVALUATION.md",
        },
    }
