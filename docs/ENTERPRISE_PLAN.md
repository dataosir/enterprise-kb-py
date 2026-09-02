# 企业级知识库技术方案

> 基于 `enterprise-kb-py` 当前 Demo 架构，规划向**可调试、可观测、可扩展**的企业级 RAG 系统演进。  
> 目标读者：负责搭建中间件与推进迭代的开发者。

---

## 1. 现状与差距

### 1.1 已有能力（Phase 1 ✅）

| 能力 | 实现 |
|------|------|
| 文档入库 | PDF / Word / MD / TXT → 切分 → BGE Embedding → Chroma |
| 向量检索 | `similarity_search_with_score`，Top-K 可调 |
| RAG 问答 | DeepSeek / Ollama，SSE 流式 |
| 文档管理 | SQLite 元数据，列表 / 删除 / 健康检查 |
| 运行时调参 | 页面可调 Top-K / Chunk Size / Overlap，支持重建索引 |
| 评测脚本 | `scripts/benchmark_rag_params.py` 离线对比 chunk/topK |

### 1.2 企业级常见缺口

```
┌─────────────────────────────────────────────────────────────────┐
│  检索层    纯向量 · 无阈值过滤 · 无混合检索 · 无 Rerank          │
│  生成层    固定 Prompt / Temperature · 无上下文预算控制          │
│  数据层    嵌入式 Chroma · 单机 SQLite · 本地文件存储            │
│  会话层    进程内存 · 重启丢失 · 无多实例共享                      │
│  安全层    无认证鉴权 · 无租户隔离 · 无审计日志                    │
│  运维层    无异步任务 · 无监控指标 · 无质量评估闭环                │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 设计原则

1. **渐进演进** — 每阶段可独立上线，不推翻现有 API
2. **可切换后端** — 向量库 / 会话 / 检索通过接口抽象，支持「本地 Demo」与「企业部署」两套 Profile
3. **参数可调试** — 企业调参面板覆盖检索、生成、索引三类旋钮
4. **与 Java 版对齐** — 核心概念（混合检索、Redis 会话、PGVector）与 `enterprise-kb` Java 版保持一致，便于迁移

---

## 2. 目标架构（企业版）

```
                         ┌──────────────┐
                         │   Web UI     │
                         │ 调参·监控·管理│
                         └──────┬───────┘
                                │ HTTPS
                         ┌──────▼───────┐
                         │  API Gateway │  ← Nginx / Traefik（可选）
                         │  JWT 鉴权     │
                         └──────┬───────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
       ┌────────────┐   ┌────────────┐   ┌────────────┐
       │  FastAPI   │   │  Worker    │   │  Eval Job  │
       │  同步 API   │   │  异步入库   │   │  RAGAS评测 │
       └─────┬──────┘   └─────┬──────┘   └─────┬──────┘
             │                │                │
    ┌────────┴────────────────┴────────────────┴────────┐
    │              RAG Pipeline（可插拔）                 │
    │  Query改写 → 混合检索 → 阈值过滤 → Rerank → 截断   │
    └────────┬──────────────────────────────────────────┘
             │
   ┌─────────┼─────────┬─────────────┬──────────────┐
   ▼         ▼         ▼             ▼              ▼
┌──────┐ ┌──────┐ ┌─────────┐ ┌──────────┐ ┌──────────┐
│Chroma│ │ES/   │ │PostgreSQL│ │  Redis   │ │ MinIO    │
│(Demo)│ │OpenS.│ │+pgvector │ │ 会话/缓存 │ │ 对象存储  │
└──────┘ └──────┘ └─────────┘ └──────────┘ └──────────┘
```

---

## 3. 分阶段实施路线

| 阶段 | 主题 | 周期建议 | 是否需要新中间件 |
|------|------|----------|------------------|
| **Phase 2a** | 检索增强 + 生成调参 | 1–2 周 | 否（纯代码） |
| **Phase 2b** | 混合检索 BM25 | 1 周 | Elasticsearch / OpenSearch（推荐） |
| **Phase 3** | 会话持久化 + 异步入库 | 1–2 周 | Redis + 任务队列 |
| **Phase 4** | 生产向量库 + 对象存储 | 2 周 | PostgreSQL + pgvector + MinIO |
| **Phase 5** | 认证鉴权 + 多租户 | 1–2 周 | 可选 Keycloak |
| **Phase 6** | 可观测 + RAGAS 评估 | 1–2 周 | Prometheus + Grafana（可选） |

以下按模块展开设计与中间件要求。

---

## 4. Phase 2a：检索增强 + 生成调参（无新中间件）

> **优先级最高**，改动集中在 `RagEngine`，页面侧栏扩展参数面板。

### 4.1 新增可调参数

| 参数 | 类型 | 默认值 | 生效方式 | 说明 |
|------|------|--------|----------|------|
| `score_threshold` | float | `null`（不过滤） | 立即 | L2 距离上限，超过则丢弃 |
| `fetch_k` | int | `20` | 立即 | 初筛候选数（Rerank / MMR 前） |
| `use_mmr` | bool | `false` | 立即 | 最大边际相关性，减少重复片段 |
| `mmr_lambda` | float | `0.5` | 立即 | 0=多样性，1=相关性 |
| `temperature` | float | `0.2` | 立即 | LLM 创造性 |
| `history_turns` | int | `3` | 立即 | 多轮对话保留轮数 |
| `max_context_chars` | int | `4000` | 立即 | 上下文总字符上限 |
| `system_prompt` | string | 内置模板 | 立即 | 企业约束策略 |
| `snippet_length` | int | `200` | 立即 | 预览展示长度 |

**存储**：扩展 `data/rag_settings.json`，API 扩展 `PUT /api/settings/rag`。

### 4.2 代码改造要点

```
app/services/
├── rag_engine.py          # 编排入口
├── retrieval/
│   ├── base.py            # Retriever 接口
│   ├── vector.py          # Chroma 向量检索（现有逻辑抽取）
│   ├── hybrid.py          # BM25 + 向量融合（Phase 2b）
│   └── reranker.py        # Cross-Encoder 重排
└── generation/
    └── context_builder.py # 按 max_context_chars 截断拼接
```

**检索流程（Phase 2a）**：

```
question
  → vectorstore.similarity_search_with_score(k=fetch_k)
  → filter(score <= score_threshold)        # 新增
  → optional MMR(fetch_k → top_k)           # 新增
  → context_builder.truncate(top_k, max_context_chars)
  → LLM
```

**Rerank（可选，仍无需中间件）**：

- 模型：`BAAI/bge-reranker-base`（本地）或 Cohere Rerank API
- 流程：`fetch_k=20` 初筛 → Rerank → 取 `top_k=4`
- 依赖：`pip install sentence-transformers`（已有）

### 4.3 页面改造

侧栏「RAG 参数」分区：

- **检索**：Top-K、Fetch-K、相似度阈值、MMR 开关 / Lambda
- **生成**：Temperature、历史轮数、最大上下文字符数、System Prompt 文本框
- **索引**：Chunk Size / Overlap（已有，需重建索引）

---

## 5. Phase 2b：混合检索 BM25 + 向量

### 5.1 为什么需要

纯向量检索对**专有名词、编号、精确关键词**召回弱；BM25 擅长字面匹配。企业文档（制度、合同、工单号）通常需要二者融合。

### 5.2 融合策略

```
                    ┌─────────────┐
           question │ Query 预处理 │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           ▼                               ▼
    ┌─────────────┐                 ┌─────────────┐
    │ Vector      │                 │ BM25        │
    │ Top fetch_k │                 │ Top fetch_k │
    └──────┬──────┘                 └──────┬──────┘
           │                               │
           └───────────────┬───────────────┘
                           ▼
                  ┌─────────────────┐
                  │ RRF 融合排序     │  score = Σ 1/(k+rank)
                  │ 或 加权线性融合   │  α·vec + (1-α)·bm25
                  └────────┬────────┘
                           ▼
                  ┌─────────────────┐
                  │ Rerank（可选）   │
                  └────────┬────────┘
                           ▼
                        Top-K
```

### 5.3 实现方案对比

| 方案 | BM25 后端 | 优点 | 缺点 |
|------|-----------|------|------|
| **A（推荐）** | Elasticsearch / OpenSearch | 成熟、可扩展、支持中文分词 | 需部署 ES |
| B | `rank_bm25` + 内存索引 | 零中间件、适合 Demo | 重启重建、难扩展 |
| C | PostgreSQL `tsvector` | 与 PG 统一 | 需迁 PG，中文分词需额外配置 |

**推荐 A**：与 Java 版企业实践一致，索引与 Chroma 通过 `doc_id` + `chunk_id` 关联。

### 5.4 新增可调参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `retrieval_mode` | `vector` | `vector` / `hybrid` |
| `hybrid_alpha` | `0.5` | 向量权重（BM25 权重 = 1-α） |
| `rrf_k` | `60` | RRF 常数 |

### 5.5 ES 索引 Mapping（参考）

```json
{
  "mappings": {
    "properties": {
      "doc_id":    { "type": "keyword" },
      "chunk_id":  { "type": "keyword" },
      "filename":  { "type": "keyword" },
      "content":   { "type": "text", "analyzer": "ik_max_word" },
      "created_at":{ "type": "date" }
    }
  }
}
```

入库时**双写**：Chroma（向量）+ ES（全文）。删除文档时两边同步删。

---

## 6. Phase 3：会话持久化 + 异步入库

### 6.1 问题

- 当前 `_memory: dict` 存于进程内存，重启丢失，多实例不共享
- 大文件同步入库阻塞 API，上传超时

### 6.2 中间件：Redis

| 用途 | Key 设计 | TTL |
|------|----------|-----|
| 对话历史 | `conv:{tenant}:{conv_id}` → List[JSON] | 7 天 |
| 会话元数据 | `conv:meta:{conv_id}` | 7 天 |
| 限流 | `ratelimit:{user}:{minute}` | 1 分钟 |
| 任务状态 | `job:{job_id}` | 24 小时 |

**配置项**：

```bash
REDIS_URL=redis://localhost:6379/0
CONVERSATION_TTL_SECONDS=604800
```

### 6.3 中间件：任务队列（二选一）

| 方案 | 组件 | 适用场景 |
|------|------|----------|
| **轻量（推荐起步）** | Redis + ARQ / RQ | 单机或小集群，Python 原生 |
| 标准 | Celery + Redis/RabbitMQ | 多 Worker、复杂路由 |

**异步入库流程**：

```
POST /api/documents/upload
  → 保存文件到 MinIO/本地
  → 写入 metadata（status=PROCESSING）
  → 投递任务 ingest_document(doc_id)
  → 立即返回 { jobId, status: "PROCESSING" }

Worker:
  → Loader → Split → Embed → Chroma + ES
  → 更新 metadata（status=READY, chunkCount）
  → 可选 WebSocket / SSE 通知前端
```

**新增 API**：

| 端点 | 说明 |
|------|------|
| `GET /api/jobs/{job_id}` | 查询入库任务状态 |
| `GET /api/conversations/{id}` | 获取历史消息 |
| `DELETE /api/conversations/{id}` | 清空会话 |

---

## 7. Phase 4：生产向量库 + 对象存储

### 7.1 何时从 Chroma 迁移

- 文档量 > 10 万 chunk
- 需要多实例读写、备份恢复、SQL 联合查询
- 与业务库（用户、权限）同库管理

### 7.2 中间件：PostgreSQL + pgvector

```sql
CREATE EXTENSION vector;

CREATE TABLE kb_chunks (
    id          UUID PRIMARY KEY,
    doc_id      UUID NOT NULL,
    filename    TEXT NOT NULL,
    content     TEXT NOT NULL,
    embedding   vector(512),   -- 与 BGE-small-zh 维度一致
    metadata    JSONB,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ON kb_chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
```

**抽象接口**：

```python
class VectorStore(Protocol):
    def add_documents(self, chunks: list[Document]) -> None: ...
    def similarity_search(self, query: str, k: int) -> list[ScoredChunk]: ...
    def delete_by_doc_id(self, doc_id: str) -> None: ...
```

实现类：`ChromaVectorStore`（Demo）、`PgVectorStore`（企业）。

**配置**：

```bash
VECTOR_STORE=chroma          # chroma | pgvector
DATABASE_URL=postgresql://kb:kb@localhost:5432/enterprise_kb
```

### 7.3 中间件：MinIO / S3

| 用途 | 路径规范 |
|------|----------|
| 原始文件 | `s3://kb-uploads/{tenant}/{doc_id}/{filename}` |
| 解析中间结果 | `s3://kb-cache/{doc_id}/parsed.json` |

```bash
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=kb-uploads
```

本地 Demo 可继续用 `data/uploads/`，通过 `STORAGE_BACKEND=local|s3` 切换。

### 7.4 元数据升级

SQLite → PostgreSQL 单库：

```sql
CREATE TABLE documents (
    id           UUID PRIMARY KEY,
    tenant_id    UUID,
    filename     TEXT NOT NULL,
    storage_key  TEXT NOT NULL,   -- S3 key 或本地路径
    file_size    BIGINT,
    chunk_count  INT DEFAULT 0,
    status       TEXT DEFAULT 'PROCESSING',
    created_at   TIMESTAMPTZ DEFAULT now()
);
```

---

## 8. Phase 5：认证鉴权 + 多租户

### 8.1 方案对比

| 方案 | 复杂度 | 说明 |
|------|--------|------|
| **JWT 自建** | 低 | FastAPI `Depends` + `python-jose`，适合内部系统 |
| API Key | 低 | 服务间调用 |
| **Keycloak** | 中 | OIDC/OAuth2，SSO，角色管理 |
| Auth0 / 企业 IdP | 低（接入） | 托管，按量付费 |

### 8.2 权限模型（RBAC）

```
角色          权限
────────────────────────────────────
viewer        问答、查看文档列表
editor        + 上传、删除自己的文档
admin         + 调参、重建索引、管理全部文档
super_admin   + 租户管理、系统配置
```

**数据隔离**：所有表加 `tenant_id`，检索时 `filter tenant_id = current_tenant`。

### 8.3 审计日志

```sql
CREATE TABLE audit_logs (
    id          BIGSERIAL PRIMARY KEY,
    tenant_id   UUID,
    user_id     UUID,
    action      TEXT,      -- CHAT / UPLOAD / DELETE / SETTINGS_CHANGE
    resource_id TEXT,
    detail      JSONB,
    created_at  TIMESTAMPTZ DEFAULT now()
);
```

---

## 9. Phase 6：可观测 + 质量评估

### 9.1 日志与指标

| 类型 | 工具 | 内容 |
|------|------|------|
| 结构化日志 | `structlog` + JSON | request_id、latency、token 用量 |
| 指标 | Prometheus | `rag_retrieval_latency_ms`、`llm_tokens_total` |
| 可视化 | Grafana | 仪表盘：QPS、P99、命中率 |
| 链路追踪 | OpenTelemetry | upload → embed → retrieve → generate |

**关键埋点**：

```python
# 每次问答记录
{
  "question": "...",
  "retrieval_ms": 45,
  "llm_ms": 1200,
  "sources": [{"filename": "...", "score": 0.32}],
  "answer_tokens": 256,
  "conversation_id": "..."
}
```

### 9.2 RAGAS 评估闭环

| 指标 | 含义 |
|------|------|
| `context_precision` | 检索片段是否相关 |
| `context_recall` | 是否召回了回答问题所需信息 |
| `faithfulness` | 回答是否忠于上下文（防幻觉） |
| `answer_relevancy` | 回答是否切题 |

**流程**：

```
scripts/benchmark_cases.json（已有）
  → 扩展 expected_answer 字段
  → scripts/eval_ragas.py 批量跑问答
  → 输出 eval_report.json + 写入 Grafana
  → 调参后对比（与 benchmark_rag_params 联动）
```

### 9.3 中间件（可选）

```yaml
# docker-compose.observability.yml
services:
  prometheus:
    image: prom/prometheus
    ports: ["9090:9090"]
  grafana:
    image: grafana/grafana
    ports: ["3000:3000"]
```

应用暴露 `GET /metrics`（`prometheus-fastapi-instrumentator`）。

---

## 10. 企业级参数全景（调参面板终态）

```
┌─ 索引（改后需重建）────────────────────────────────────┐
│  Chunk Size · Chunk Overlap · 切分策略（固定/按标题）   │
│  Embedding 模型（换模型需重建）                         │
├─ 检索（立即生效）──────────────────────────────────────┤
│  模式: vector / hybrid                                  │
│  Top-K · Fetch-K · 相似度阈值                           │
│  Hybrid α · RRF k                                       │
│  MMR 开关 · MMR λ                                       │
│  Rerank 开关 · Rerank Top-N                             │
├─ 生成（立即生效）──────────────────────────────────────┤
│  Temperature · 历史轮数 · 最大上下文字符数               │
│  System Prompt · Chat 模型（.env，重启生效）             │
└─ 高级（Phase 3+）─────────────────────────────────────┘
│  Query 改写开关 · HyDE · 多查询扩展                     │
```

---

## 11. 中间件清单与搭建指南

### 11.1 按阶段最小集

| 阶段 | 必须搭建 | 可选 |
|------|----------|------|
| Phase 2a | 无 | — |
| Phase 2b | **Elasticsearch 8.x** 或 OpenSearch 2.x | IK 中文分词插件 |
| Phase 3 | **Redis 7** | ARQ Worker 容器 |
| Phase 4 | **PostgreSQL 16 + pgvector** | **MinIO** |
| Phase 5 | — | Keycloak |
| Phase 6 | — | Prometheus + Grafana |

### 11.2 推荐 docker-compose 扩展

```yaml
# docker-compose.enterprise.yml（规划文件，按阶段启用）

services:
  kb:
    build: .
    depends_on: [redis, postgres, elasticsearch, minio]
    environment:
      REDIS_URL: redis://redis:6379/0
      DATABASE_URL: postgresql://kb:kb@postgres:5432/enterprise_kb
      ES_URL: http://elasticsearch:9200
      VECTOR_STORE: pgvector
      STORAGE_BACKEND: s3
      S3_ENDPOINT: http://minio:9000

  worker:
    build: .
    command: arq app.worker.WorkerSettings
    depends_on: [redis, postgres, elasticsearch]

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: enterprise_kb
      POSTGRES_USER: kb
      POSTGRES_PASSWORD: kb
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]

  elasticsearch:
    image: elasticsearch:8.15.0
    environment:
      discovery.type: single-node
      xpack.security.enabled: "false"
      ES_JAVA_OPTS: "-Xms512m -Xmx512m"
    ports: ["9200:9200"]

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    ports: ["9000:9000", "9001:9001"]
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin

volumes:
  pgdata:
```

### 11.3 各中间件资源建议（开发环境）

| 中间件 | 最低内存 | 端口 | 验证命令 |
|--------|----------|------|----------|
| Redis | 128MB | 6379 | `redis-cli ping` → PONG |
| PostgreSQL+pgvector | 512MB | 5432 | `psql -c "CREATE EXTENSION vector"` |
| Elasticsearch | 1GB | 9200 | `curl localhost:9200` |
| MinIO | 256MB | 9000/9001 | 浏览器开 Console |
| Keycloak | 512MB | 8080 | 管理台登录 |

### 11.4 中文分词（Elasticsearch）

```bash
# 安装 IK 分词器（版本与 ES 一致）
docker exec -it elasticsearch bash
bin/elasticsearch-plugin install \
  https://github.com/medcl/elasticsearch-analysis-ik/releases/download/v8.15.0/elasticsearch-analysis-ik-8.15.0.zip
# 重启 ES
```

---

## 12. 目录结构演进

```
app/
├── main.py
├── config.py
├── api/                    # 路由拆分
│   ├── chat.py
│   ├── documents.py
│   └── settings.py
├── models/
├── store/
│   ├── document_store.py   # 抽象 + SQLite / PG 实现
│   ├── vector_store/       # Chroma / PgVector
│   ├── search_store/       # ES BM25
│   ├── conversation_store/ # Memory / Redis
│   └── rag_settings.py
├── services/
│   ├── rag_engine.py       # 编排
│   ├── retrieval/
│   │   ├── vector.py
│   │   ├── hybrid.py
│   │   └── reranker.py
│   ├── generation/
│   │   └── context_builder.py
│   └── ingestion/
│       ├── loader.py
│       └── worker.py       # 异步入库
├── auth/                   # JWT / 租户
└── observability/          # metrics / tracing

docker-compose.yml              # Demo（当前）
docker-compose.enterprise.yml   # 企业全栈
docs/
├── ENTERPRISE_PLAN.md          # 本文档
├── MIDDLEWARE_SETUP.md         # 中间件安装与运维（飞牛 NAS 已部署）
├── ARCHITECTURE.md
└── LEARNING.md
```

---

## 13. API 演进（向后兼容）

| 现有 API | 企业扩展 |
|----------|----------|
| `PUT /api/settings/rag` | 扩展字段：threshold、temperature、prompt 等 |
| `POST /api/documents/upload` | 返回 `jobId`，大文件走异步 |
| `POST /api/chat` | Header `Authorization: Bearer <jwt>` |
| — | `GET /api/jobs/{id}` |
| — | `GET /api/metrics`（Prometheus） |
| — | `POST /api/eval/run`（触发 RAGAS 评测） |

---

## 14. 风险与决策点

| 决策 | 选项 | 建议 |
|------|------|------|
| BM25 后端 | ES vs 内存 rank_bm25 | 学习用 B；企业用 ES |
| 向量库 | Chroma vs pgvector | Demo 保持 Chroma；>1 万 chunk 迁 PG |
| 任务队列 | ARQ vs Celery | 先用 ARQ，够用再换 |
| 认证 | 自建 JWT vs Keycloak | 内部 MVP 用 JWT；对外 SSO 用 Keycloak |
| Embedding | 本地 BGE vs API | 中文企业文档继续 BGE；多语言考虑 API |

---

## 15. 实施优先级（行动清单）

### 你可先搭建的中间件（按顺序）

1. **Redis** — Phase 3 必用，提前搭好不影响现有 Demo
2. **Elasticsearch + IK** — Phase 2b 混合检索
3. **PostgreSQL + pgvector** — Phase 4 向量库迁移
4. **MinIO** — Phase 4 文件存储（可与 PG 并行）
5. **Prometheus + Grafana** — Phase 6，可最后加

### 开发侧推荐顺序

```
Week 1  Phase 2a  扩展调参面板 + score_threshold + context 预算 + Rerank
Week 2  Phase 2b  ES 混合检索 + 双写入库
Week 3  Phase 3    Redis 会话 + ARQ 异步入库
Week 4  Phase 4    pgvector 抽象 + MinIO
Week 5  Phase 5–6  JWT + RAGAS + Prometheus
```

---

## 16. 验收标准（企业级 Demo）

| 场景 | 验收条件 |
|------|----------|
| 精确关键词 | 问工单号 / 条款编号，混合检索 hit@1 > 纯向量 |
| 语义问答 | 「退款多久」类问题，faithfulness > 0.8（RAGAS） |
| 调参可观测 | 页面改 Top-K / 阈值，预览检索即时变化 |
| 多轮对话 | 重启服务后会话仍在（Redis） |
| 大文件上传 | 10MB PDF 上传 < 3s 返回，后台入库完成 |
| 多实例 | 2 个 API 实例共享会话与向量库 |
| 安全 | 无 Token 访问 API 返回 401 |

---

## 附录 A：环境变量汇总（企业版）

```bash
# === 已有 ===
DEEPSEEK_API_KEY=
OPENAI_BASE_URL=
OPENAI_CHAT_MODEL=
EMBEDDING_PROVIDER=local
LOCAL_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5

# === Phase 2a ===
RAG_SCORE_THRESHOLD=
RAG_FETCH_K=20
RAG_USE_MMR=false
RAG_TEMPERATURE=0.2
RAG_HISTORY_TURNS=3
RAG_MAX_CONTEXT_CHARS=4000

# === Phase 2b ===
RETRIEVAL_MODE=vector          # vector | hybrid
ES_URL=http://localhost:9200
HYBRID_ALPHA=0.5

# === Phase 3 ===
REDIS_URL=redis://localhost:6379/0
CONVERSATION_TTL_SECONDS=604800

# === Phase 4 ===
VECTOR_STORE=chroma            # chroma | pgvector
DATABASE_URL=postgresql://kb:kb@localhost:5432/enterprise_kb
STORAGE_BACKEND=local          # local | s3
S3_ENDPOINT=
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_BUCKET=kb-uploads

# === Phase 5 ===
JWT_SECRET=
JWT_ALGORITHM=HS256
AUTH_ENABLED=false

# === Phase 6 ===
OTEL_EXPORTER_OTLP_ENDPOINT=
PROMETHEUS_ENABLED=false
```

---

## 附录 B：与 Java 版 `enterprise-kb` 对齐矩阵

| 能力 | Python 版（本方案） | Java 版 |
|------|---------------------|---------|
| 向量库 | Chroma → pgvector | PGVector |
| 会话 | 内存 → Redis | Redis |
| 混合检索 | ES + 向量 | 规划中 |
| 调参面板 | 页面动态 | 配置中心 |
| 部署 | Docker Compose | K8s / Compose |

---

*文档版本：v1.0 · 与 main 分支 Phase 1 架构对齐*
