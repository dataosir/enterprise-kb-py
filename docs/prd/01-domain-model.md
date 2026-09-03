# 01 · 领域模型

## 1. 核心实体

| 实体 | 说明 | 持久化 |
|---|---|---|
| **Document** | 一篇上传或示例文档 | SQLite `documents` 表 |
| **Chunk** | 切分后的检索最小单位 | Chroma / pgvector `kb_chunks` |
| **DocumentRecord** | 文档元数据（文件名、状态、chunk 数） | SQLite |
| **RetrievedChunk** | 检索命中的片段（含 score、snippet） | 内存，API 返回 |
| **Conversation** | 多轮对话（question / answer 对） | 内存或 Redis |
| **RagSettings** | 运行时 RAG 参数（12+ 项） | `data/rag_settings.json` |
| **IngestJob** | 异步入库任务 | Redis（ARQ + job_store） |

## 2. 文档状态机

```
                    ┌─────────────┐
         上传/引导   │  PROCESSING │  异步入库中 / 同步处理中
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼                         ▼
       ┌─────────────┐           ┌─────────────┐
       │    READY    │           │   FAILED    │
       │  可检索问答  │           │  入库失败    │
       └──────┬──────┘           └─────────────┘
              │ 删除
              ▼
         （向量+元数据+存储文件一并清除）
```

## 3. 检索模式

| 模式 | 值 | 行为 |
|---|---|---|
| 纯向量 | `vector` | Chroma / pgvector 相似度搜索 |
| 混合检索 | `hybrid` | 向量 + ES BM25 → RRF 融合 |

混合检索依赖 ES；不可用时**自动回退**纯向量。

## 4. 存储后端 Profile

| 维度 | Demo 默认 | 企业可选 |
|---|---|---|
| 向量库 | `chroma`（`data/chroma/`） | `pgvector`（PostgreSQL） |
| 对象存储 | `local`（`data/uploads/`） | `s3`（MinIO） |
| 会话 | `memory` | `redis` |
| 入库 | 同步 | ≥ 阈值异步入队（ARQ） |

`auto` 模式：检测到 `REDIS_URL` 等环境变量后自动切换，否则保持 Demo。

## 5. RAG 参数分类

| 分类 | 参数示例 | 生效方式 |
|---|---|---|
| 索引 | `chunkSize`, `chunkOverlap` | 需重建索引 |
| 检索 | `topK`, `fetchK`, `scoreThreshold`, `useMmr`, `retrievalMode` | 立即 |
| 生成 | `temperature`, `historyTurns`, `maxContextChars`, `systemPrompt` | 立即 |

详见 F04。

## 6. 标识关联

```
doc_id (UUID)
  ├── SQLite documents.id
  ├── Chroma/PG metadata.doc_id
  ├── ES chunk_id（与向量 chunk 一一对应）
  └── S3 key: uploads/{doc_id}/{filename}
```

删除文档时必须**四端一致**清除（向量、ES、元数据、对象存储）。

## 7. 相关文档

- 文档入库：[`03-features/F01-document-ingest.md`](03-features/F01-document-ingest.md)
- 向量库：[`03-features/F08-vector-storage.md`](03-features/F08-vector-storage.md)
- 技术数据流：[`../tech/ARCHITECTURE.md`](../tech/ARCHITECTURE.md)
