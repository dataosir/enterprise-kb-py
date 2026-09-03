# F01 · 文档入库

## 1. 背景与目标

将企业文档（PDF / Word / Markdown / TXT）转化为可检索的向量片段，是 RAG 链路的起点。支持同步与异步入库，入库时双写向量库与 ES（若启用）。

## 2. 用户故事 / 场景

- 作为管理员，我上传一份制度 PDF，系统切分并向量化，之后员工可问答检索。
- 作为学习者，首次启动自动加载 `sample-docs/`，无需手动上传即可体验。
- 作为低内存部署者，大文件异步入库，上传接口立即返回。

## 3. 功能范围

**In**

- 支持格式：PDF、Word（.docx）、Markdown、纯文本
- 切分：`RecursiveCharacterTextSplitter`，参数来自 RagSettings
- 向量化：本地 BGE 或 OpenAI Embedding
- 双写：Chroma/pgvector + ES（ES 可用时）
- 元数据：SQLite 记录 filename、chunkCount、status
- 对象存储：本地或 S3 保存原始文件

**Out**

- OCR 扫描件识别
- 表格/图片结构化解析
- 增量更新（同 doc_id 覆盖策略未实现）

## 4. 主流程与边界

1. 接收上传 → 校验大小（`MAX_UPLOAD_SIZE_MB`）与扩展名。
2. 保存原始文件到对象存储。
3. 若异步入库：写 `PROCESSING` 元数据 → 入队 ARQ → 返回 `jobId`。
4. 同步/Worker：`Loader` → `splitter` → `add_documents` → 更新 `READY`。
5. ES 双写与向量库使用相同 `chunk_id`。

**边界**：Worker 未启动时大文件卡在 `PROCESSING`；ES 不可用则仅写向量库。

## 5. 关键配置键

| 键 | 默认 | 用途 |
|---|---|---|
| `RAG_CHUNK_SIZE` | 512 | 切分大小 |
| `RAG_CHUNK_OVERLAP` | 64 | 重叠 |
| `EMBEDDING_PROVIDER` | local | BGE / openai |
| `ASYNC_INGEST` | auto | 异步入库开关 |
| `ASYNC_INGEST_THRESHOLD_MB` | 1 | 异步阈值 |
| `MAX_UPLOAD_SIZE_MB` | 20 | 上传上限 |

## 6. 代码锚点

- `app/services/rag_engine.py` — `ingest_file()`
- `app/main.py` — `POST /api/documents/upload`
- `app/services/bootstrap.py` — 示例文档引导
- `app/worker/settings.py` — ARQ Worker 入库任务

## 7. 验收标准

- [ ] 上传 `.md` 后 `GET /api/documents` 显示 `READY` 且 `chunkCount > 0`
- [ ] 首次启动空库自动加载 3 篇 sample-docs，重启不重复
- [ ] 配置 Redis 后 ≥1MB 文件返回 `jobId`，Worker 完成后变 `READY`
- [ ] ES 启用时入库后 `sync-es` 或自动双写可检索

## 8. 已知缺口 / 待迭代

- 无按段落/标题的智能切分策略
- 同文件名重复上传会生成新 doc_id（无去重）
- 换 Embedding 模型需全量重建索引（无 UI 提示独立流程）
