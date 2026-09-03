# 02 · 用户主流程

## 1. 首次使用（Demo 模式）

```
克隆仓库 → ./start.sh → 编辑 .env（API Key）
    → 浏览器打开 :8081
    → 自动加载 sample-docs（6 篇）
    → 提问「退款多久到账？」→ 得回答 + 引用来源
```

| 步骤 | 用户动作 | 系统行为 | API |
|---|---|---|---|
| 1 | 启动服务 | bootstrap 示例文档（仅空库） | `GET /api/health` |
| 2 | 浏览侧栏 | 显示文档列表与 chunk 数 | `GET /api/documents` |
| 3 | 输入问题 | 检索 → LLM 生成 | `POST /api/chat` |
| 4 | 查看引用 | 展开 sources | 响应内 `sources` |

## 2. 上传自有知识库

```
选择文件 → 上传 → （大文件轮询 job）→ 列表状态 READY → 提问验证
```

| 文件大小 | 流程 | API |
|---|---|---|
| < 阈值（默认 1MB） | 同步入库，立即 READY | `POST /api/documents/upload` |
| ≥ 阈值 + Redis | 返回 jobId，后台 Worker 处理 | `GET /api/jobs/{id}` |
| ≥ 阈值，无 Redis | 同步入库（可能较慢） | 同上 |

## 3. 调参实验

```
侧栏调整参数 → 应用参数
    → （改 chunk）重建索引
    → （改 topK/阈值）预览检索效果
    → 正常提问对比回答
```

| 动作 | API |
|---|---|
| 读取当前参数 | `GET /api/settings/rag` |
| 保存参数 | `PUT /api/settings/rag` |
| 重建向量索引 | `POST /api/settings/rag/reindex` |
| 同步 ES 索引 | `POST /api/settings/rag/sync-es` |
| 预览检索（不调 LLM） | `GET /api/chat/sources?question=...` |

## 4. 企业 Profile 启用

```
部署中间件（见 enterprise/MIDDLEWARE_SETUP.md）
    → .env 配置 REDIS / ES / DATABASE / S3
    → make dev + make worker
    → 健康检查确认各组件 connected
    → 同步 ES / 重建索引 → 切换混合检索
```

| 能力 | 环境变量（占位） | 验证 |
|---|---|---|
| 会话持久化 | `REDIS_URL` | `conversationStore: redis` |
| 混合检索 | `ES_URL`, `RAG_RETRIEVAL_MODE=hybrid` | `esStatus: connected` |
| pgvector | `VECTOR_STORE=pgvector`, `DATABASE_URL` | `vectorStore: pgvector` |
| MinIO | `STORAGE_BACKEND=s3`, `S3_*` | `storageBackend: s3` |

## 5. 离线评测

```bash
make benchmark
# → data/benchmark/benchmark_rag_params.csv
```

不启动 Web UI，对比多组 chunk_size × top_k 的 Hit@1 / Hit@K。

## 6. 多轮对话

```
POST /api/chat/conversation  → 获得 conversationId
POST /api/chat { conversationId, question }  → 带历史
GET /api/conversations/{id}  → 查看历史
DELETE /api/conversations/{id}  → 清空
```

Redis 配置后重启服务，历史仍可恢复。

## 7. 相关文档

- 学习实验 Step 0–5：[`../guides/LEARNING.md`](../guides/LEARNING.md)
- 中间件部署：[`../enterprise/MIDDLEWARE_SETUP.md`](../enterprise/MIDDLEWARE_SETUP.md)
