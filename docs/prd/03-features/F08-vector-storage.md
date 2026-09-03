# F08 · 向量库切换（Chroma / pgvector）

## 1. 背景与目标

Demo 使用嵌入式 Chroma 零运维；企业生产环境需要 PostgreSQL + pgvector 支持多实例、备份与 SQL 生态。通过抽象层可配置切换，PG 不可用时回退 Chroma。

## 2. 用户故事 / 场景

- 作为开源用户，我零配置使用 Chroma，数据在 `data/chroma/`。
- 作为企业部署者，我配置 `VECTOR_STORE=pgvector`，向量存入 NAS 上的 PostgreSQL。
- 作为运维，健康检查显示 `vectorStore` 与 `vectorChunkCount`。

## 3. 功能范围

**In**

- 后端：`chroma`（默认）/ `pgvector`
- 统一接口：`add_documents`, `similarity_search`, `delete_by_doc_id`, `count`
- PG 表 `kb_chunks`（embedding + metadata）
- 启动时 PG 不可用 → 自动回退 Chroma + 日志
- 重建索引写入当前激活后端

**Out**

- Milvus / Qdrant / Weaviate
- 向量库在线迁移工具
- 分片与副本

## 4. 主流程与边界

1. `get_vectorstore()` 按 `VECTOR_STORE` 与环境变量选择实现。
2. 检索链路（混合/MMR/Rerank）对后端透明。
3. 切换后端需 `reindex` 全量导入，无自动迁移。

**边界**：Chroma 与 pgvector 数据不自动同步；切换等于空库重建。

## 5. 关键配置键

| 键 | 默认 | 用途 |
|---|---|---|
| `VECTOR_STORE` | chroma | chroma / pgvector |
| `DATABASE_URL` | — | PostgreSQL 连接串 |
| `CHROMA_PERSIST_DIR` | data/chroma | Chroma 路径 |

## 6. 代码锚点

- `app/services/vector_store/` — factory, chroma, pgvector
- `app/store/pg_client.py` — PG 连接与健康
- `app/services/rag_engine.py` — 向量库调用

## 7. 验收标准

- [ ] 默认 `vectorStore: chroma`，问答正常
- [ ] 配置有效 `DATABASE_URL` + `pgvector` 后 health 显示 `pgStatus: connected`
- [ ] 重建索引后 `vectorChunkCount > 0`
- [ ] PG 宕机时服务仍可启动（Chroma 回退）

## 8. 已知缺口 / 待迭代

- 无页面切换向量库（仅 .env）
- pgvector 索引类型（HNSW/IVFFlat）未暴露调参
- 与 Java 版 PG 表结构对齐文档待补充
