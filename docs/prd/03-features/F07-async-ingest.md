# F07 · 异步入库

## 1. 背景与目标

大文件切分与向量化耗时，同步上传会阻塞 HTTP 请求。通过 ARQ + Redis 队列后台处理，上传接口秒回，适合低内存设备控制并发（`max_jobs=1`）。

## 2. 用户故事 / 场景

- 作为用户，我上传 10MB PDF，立即看到 `PROCESSING`，稍后自动变 `READY`。
- 作为运维，我单独启动 `make worker`，与 API 进程分离。
- 作为 Demo 用户，无 Redis 时小文件同步、大文件仍同步（可能慢）。

## 3. 功能范围

**In**

- 阈值判断：`file_size >= ASYNC_INGEST_THRESHOLD_MB`
- 任务状态：PENDING → PROCESSING → COMPLETED / FAILED
- 任务查询：`GET /api/jobs/{id}`
- 前端轮询 job 状态直至完成
- Worker：`app/worker/settings.py`，`max_jobs=1`

**Out**

- 任务取消 / 重试 UI
- 优先级队列
- 分布式多 Worker 负载均衡文档

## 4. 主流程与边界

1. 上传 → 存文件 → 写 `PROCESSING` 元数据。
2. `enqueue_ingest_job(doc_id, path, filename)`。
3. Worker 执行 `ingest_file` → 更新 `READY` 或 `FAILED`。
4. 前端每 2s 轮询 job 或刷新文档列表。

**边界**：Worker 未启动 → 永久 `PROCESSING`；需在文档/运维中说明。

## 5. 关键配置键

| 键 | 默认 | 用途 |
|---|---|---|
| `REDIS_URL` | — | 队列依赖 |
| `ASYNC_INGEST` | auto | 异步入库开关 |
| `ASYNC_INGEST_THRESHOLD_MB` | 1 | 触发阈值 |

## 6. 代码锚点

- `app/store/job_store.py` — 任务状态
- `app/services/arq_pool.py` — 入队连接池
- `app/worker/settings.py` — Worker 入口
- `scripts/worker.sh` — 启动脚本
- `Makefile` — `make worker`

## 7. 验收标准

- [ ] 配置 Redis 后上传 ≥1MB 文件返回 `jobId`
- [ ] Worker 运行后文档变 `READY`，health `ready_documents` 增加
- [ ] `GET /api/jobs/{id}` 状态最终为 `COMPLETED`
- [ ] 无 Redis 时行为与同步入库一致

## 8. 已知缺口 / 待迭代

- 失败任务无一键重试
- 无队列深度监控（见 F13）
- Worker 崩溃中间状态需人工处理
