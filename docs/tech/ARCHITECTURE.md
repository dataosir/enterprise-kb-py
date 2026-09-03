# 架构说明

## 定位

`enterprise-kb-py` 是一个**可本地运行、可渐进扩展到企业 Profile** 的知识库 RAG 系统，适合：

- 理解 RAG 全链路（入库 → 检索 → 生成）与分层评测闭环
- 作为开源学习项目，对照 Java 版 `enterprise-kb`
- 实验 chunk、topK、hybrid、rerank、MMR 等参数

**两套 Profile**：

| Profile | 典型配置 | 适用 |
|---------|----------|------|
| **Demo** | Chroma + SQLite + 本地盘 + 内存会话 | 零中间件、快速体验 |
| **Enterprise** | pgvector + ES + Redis + MinIO/S3 | docker-compose.enterprise.yml |

**尚未完成（Phase 5）**：JWT 鉴权、多租户隔离、审计日志。

## 系统架构

```
┌──────────────────────────────────────────────────────────────────────┐
│  Web UI (static/)                                                     │
│  聊天 · 上传 · 文档管理 · RAG 调参 · 检索预览 · 评测/中间件看板        │
└───────────────────────────────┬──────────────────────────────────────┘
                                │ HTTP / SSE
┌───────────────────────────────▼──────────────────────────────────────┐
│  API 层 (app/main.py)                                                 │
│  /api/health · /api/documents · /api/chat · /api/chat/stream         │
│  /api/settings/rag · /api/conversations/* · /api/jobs/*              │
│  /api/feedback · /api/eval/dashboard · /api/middleware/map           │
│  /metrics · eval-dashboard.html · middleware-map.html                │
└───────────────────────────────┬──────────────────────────────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  RagEngine      │   │ DocumentStore   │   │ Bootstrap       │
│  retrieval/     │   │ SQLite 元数据    │   │ sample-docs     │
│  generation/    │   │ 文档列表/状态    │   │ 首次自动入库     │
│  vector_store/  │   └─────────────────┘   └─────────────────┘
└────────┬────────┘
         │
    ┌────┴────┬────────────┬──────────────┐
    ▼         ▼            ▼              ▼
┌────────┐ ┌────────┐ ┌──────────┐ ┌──────────────┐
│ Chroma │ │ES/IK   │ │ Redis    │ │ MinIO/S3     │
│pgvector│ │(hybrid)│ │会话/ARQ  │ │ 对象存储      │
└────────┘ └────────┘ └──────────┘ └──────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│  外部模型（可配置）                                                    │
│  DeepSeek / Ollama (LLM)    BGE Embedding + BGE Reranker (本地)     │
└──────────────────────────────────────────────────────────────────────┘
```

## 数据流

### 1. 文档入库

```
上传文件 / sample-docs（6 篇）
    → Document Loader (PDF/Word/Markdown/TXT)
    → RecursiveCharacterTextSplitter（chunk_size/overlap 可调）
    → BGE Embedding
    → 向量库（Chroma 或 pgvector）
    → 可选 ES BM25 双写（hybrid 检索）
    → 可选 MinIO/S3 或本地 uploads/
    → SQLite 记录元数据（filename, chunkCount, status）
    → 大文件可选 ARQ 异步入库（status=PROCESSING + job_id）
```

### 2. 问答检索

```
用户问题
    → 会话历史（Redis 或内存，可配置 history_turns）
    → BGE Embedding 向量化
    → fetch_k 初筛（向量 / hybrid RRF / MMR）
    → 可选 score_threshold 过滤
    → 可选 BGE Cross-Encoder Rerank
    → context_builder 按 max_context_chars 截断
    → ChatOpenAI (DeepSeek) 流式/非流式生成
    → 返回答案 + 引用来源 + /metrics 埋点
```

## 目录结构

```
app/
├── main.py                    # FastAPI 路由
├── config.py                  # 环境变量与路径
├── models/
│   ├── domain.py
│   └── schemas.py
├── store/
│   └── document_store.py      # SQLite 文档元数据
├── services/
│   ├── rag_engine.py          # RAG 编排入口
│   ├── bootstrap.py           # 首次加载 sample-docs
│   ├── eval_dashboard.py      # 评测看板数据聚合
│   ├── middleware_map.py      # 中间件导图 + 问答流程
│   ├── retrieval/             # vector / hybrid / rerank / mmr
│   ├── generation/              # context_builder
│   ├── vector_store/            # chroma / pgvector
│   ├── conversation_store.py    # Redis / 内存会话
│   └── storage/                 # local / s3
├── observability/
│   └── metrics.py               # Prometheus 文本格式
└── worker/                      # ARQ 异步入库

scripts/                         # 评测脚本（L1–L4）
static/                          # Web UI + eval-dashboard + middleware-map
sample-docs/                     # 6 篇示例（含 hard 混淆集）
data/                            # 运行时数据（gitignore，baseline.json 除外）
```

## 技术选型

| 组件 | Demo 默认 | Enterprise 可选 | 说明 |
|------|-----------|-----------------|------|
| Web | FastAPI | 同左 | 自带 OpenAPI |
| RAG 框架 | LangChain | 同左 | |
| 向量库 | Chroma | pgvector | `VECTOR_STORE` 切换 |
| 全文检索 | — | Elasticsearch + IK | hybrid BM25 |
| Embedding | BGE-small-zh | 同左 | 本地模型 |
| Rerank | BGE-reranker-base | 同左 | Cross-Encoder |
| LLM | DeepSeek | Ollama 等 | OpenAI 兼容 API |
| 元数据 | SQLite | 同左 | 文档 catalog |
| 对象存储 | 本地 uploads/ | MinIO/S3 | `STORAGE_BACKEND` |
| 会话/队列 | 内存 | Redis + ARQ | `CONVERSATION_STORE` |

## 与 Java 版对比

| 能力 | Python 版 | Java 版 |
|------|-----------|---------|
| 定位 | RAG 实验 + 企业 Profile | 企业级落地包装 |
| 向量库 | Chroma / pgvector | PGVector |
| 混合检索 | ES + 向量 RRF ✅ | 规划中 |
| Rerank | BGE Cross-Encoder ✅ | 部分 |
| 会话 | 内存 / Redis ✅ | Redis |
| 评测闭环 | L1–L4 脚本 + CI ✅ | 部分 |
| 认证多租户 | 未实现 | 已有 |

## 演进路线（当前状态）

| Phase | 主题 | 状态 |
|-------|------|------|
| 1 | RAG 基础闭环 | ✅ |
| 2a | 检索调参 + Rerank | ✅ |
| 2b | BM25 混合检索 | ✅ |
| 3 | Redis 会话 + 异步入库 | ✅ |
| 4 | pgvector + MinIO | ✅ |
| 5 | JWT + 多租户 | 📋 未开始 |
| 6 | 可观测 + RAGAS 评测 | 🟡 部分完成（`/metrics`、评测看板、CI smoke；缺 OTel/Grafana） |

详细方案见 [ENTERPRISE_PLAN.md](../enterprise/ENTERPRISE_PLAN.md)；中间件专题见 [MIDDLEWARE.md](MIDDLEWARE.md)；评测专题见 [EVALUATION.md](EVALUATION.md)。

## 本地开发

```bash
make install    # 安装依赖
make dev        # 启动开发服务 (http://localhost:8081)
make reset      # 清空 data/ 重新初始化
make eval-smoke # L1+L2+基线门禁（CI 同款）
```

API 文档：http://localhost:8081/docs
