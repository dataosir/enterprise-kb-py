# 架构说明

## 定位

`enterprise-kb-py` 是一个**本地可运行的企业知识库 RAG Demo**，适合：

- 快速理解 RAG 全链路（入库 → 检索 → 生成）
- 作为开源学习项目，对照 Java 版 `enterprise-kb` 学习
- 在本地实验 chunk 大小、topK、模型切换等参数

**不是**生产级系统：无用户认证、无分布式部署、无混合检索/Rerank（可作为后续迭代方向）。

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                        Web UI (static/)                      │
│              聊天 · 上传 · 文档列表 · 健康状态                │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────────┐
│                    API 层 (app/main.py)                      │
│  /api/health  /api/documents  /api/chat  /api/documents/upload │
└──────────────────────────┬──────────────────────────────────┘
                           │
         ┌─────────────────┼─────────────────┐
         ▼                 ▼                 ▼
┌────────────────┐ ┌───────────────┐ ┌────────────────┐
│  RagEngine     │ │ DocumentStore │ │  Bootstrap     │
│  (services/)   │ │  (store/)     │ │  (services/)   │
│                │ │               │ │                │
│ · 文档切分     │ │ · SQLite 元数据│ │ · 首次加载     │
│ · 向量检索     │ │ · 文档列表     │ │   sample-docs  │
│ · LLM 对话     │ │ · 状态统计     │ │                │
└───────┬────────┘ └───────────────┘ └────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                     本地持久化 (data/)                         │
│   chroma/          uploads/           metadata.db             │
│   向量索引          上传文件            文档元数据               │
└───────────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                     外部依赖（可配置）                          │
│   DeepSeek / Ollama (对话)    BGE 本地模型 (Embedding)         │
└───────────────────────────────────────────────────────────────┘
```

## 数据流

### 1. 文档入库

```
上传文件 / sample-docs
    → Document Loader (PDF/Word/Markdown)
    → RecursiveCharacterTextSplitter (512/64)
    → HuggingFace BGE Embedding
    → Chroma 向量库
    → SQLite 记录元数据 (filename, chunkCount, status)
```

### 2. 问答检索

```
用户问题
    → Chroma similarity_search (topK=4)
    → 拼接完整 chunk 作为 context
    → ChatOpenAI (DeepSeek) + 最近 3 轮历史
    → 返回答案 + 引用来源
```

## 目录结构

```
app/
├── main.py              # FastAPI 路由（API 层）
├── config.py            # 环境变量与路径
├── models/
│   ├── domain.py        # 领域对象 (DocumentRecord, RetrievedChunk)
│   └── schemas.py       # API 请求/响应模型
├── store/
│   └── document_store.py  # SQLite 文档元数据
└── services/
    ├── rag_engine.py    # RAG 核心逻辑
    └── bootstrap.py     # 启动时加载示例文档
data/                    # 运行时数据（gitignore）
sample-docs/             # 内置示例知识
static/                  # Web UI
```

## 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| Web | FastAPI | 轻量、自带 OpenAPI 文档 |
| RAG 框架 | LangChain | 生态成熟，学习资料多 |
| 向量库 | Chroma (嵌入式) | 零运维，本地文件持久化 |
| Embedding | BGE-small-zh (本地) | DeepSeek 无 Embedding API，中文效果好 |
| LLM | DeepSeek (OpenAI 兼容) | 成本低，API 简单 |
| 元数据 | SQLite | 无需额外服务，适合 Demo |

## 与 Java 版对比

| 能力 | Python 版 | Java 版 |
|------|-----------|---------|
| 定位 | RAG 原理实验 | 企业级落地包装 |
| 向量库 | Chroma | SimpleVectorStore / PGVector |
| 元数据 | SQLite | H2 |
| 会话 | 内存 | Redis（规划） |
| 混合检索 | 未实现 | 规划中 |
| Docker | 单容器 | docker-compose + PGVector |

## 后续演进路线

按优先级排列，适合逐步开源迭代：

1. **Phase 1（当前）** — 跑通闭环：上传、检索、问答、文档管理
2. **Phase 2** — 检索增强：BM25 混合检索、Cross-Encoder Rerank、生成侧调参
3. **Phase 3** — 基础设施：Redis 会话、异步入库、pgvector / MinIO
4. **Phase 4** — 安全与运维：JWT 鉴权、多租户、RAGAS 评估、Prometheus

详细技术方案见 [ENTERPRISE_PLAN.md](../enterprise/ENTERPRISE_PLAN.md)；中间件部署见 [MIDDLEWARE_SETUP.md](../enterprise/MIDDLEWARE_SETUP.md)。

## 本地开发

```bash
make install    # 安装依赖
make dev        # 启动开发服务 (http://localhost:8081)
make reset      # 清空 data/ 重新初始化
```

API 文档：http://localhost:8081/docs
