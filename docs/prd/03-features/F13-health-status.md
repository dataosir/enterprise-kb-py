# F13 · 健康与状态

## 1. 背景与目标

单一端点聚合服务、文档、中间件与 RAG 配置状态，供运维监控、UI 顶栏与部署探活使用。

## 2. 用户故事 / 场景

- 作为运维，我 `curl /api/health` 确认 Redis、ES、PG、S3 是否连通。
- 作为 UI，顶栏展示 `redisStatus`、`esStatus`、`vectorStore` 等。
- 作为 K8s，用 health 做 liveness（当前无独立 readiness 细分）。

## 3. 功能范围

**In**

- `GET /api/health` 返回：
  - `status`, `documents`, `ready_documents`
  - `redisStatus`, `conversationStore`, `asyncIngestEnabled`
  - `esStatus`, `retrievalMode`
  - `vectorStore`, `vectorStatus`, `vectorChunkCount`, `pgStatus`
  - `storageBackend`, `storageStatus`, `s3Status`
  - `stack` 字符串摘要
- OpenAPI 文档：`/docs`

**Out**

- Prometheus metrics 端点（见 F12 `/metrics`）
- 分布式链路追踪
- 组件级独立 health（/health/redis 等）

## 4. 主流程与边界

启动时各 client 懒检测；health 调用时实时 ping（Redis PING、ES cluster health、PG SELECT 1、S3 head bucket）。

**边界**：频繁 health 可能对 ES/PG 造成轻量压力；生产建议配合缓存。

## 5. 关键配置键

由各子系统环境变量决定；无 health 专属项。

## 6. 代码锚点

- `app/main.py` — `health()`
- `app/store/redis_client.py` — `redis_status()`
- `app/store/pg_client.py` — `pg_status()`
- `app/services/retrieval/es_store.py` — ES 状态
- `app/store/object_storage/factory.py` — `s3_status()`

## 7. 验收标准

- [ ] Demo 模式返回 `status: UP`, `documents: 3`
- [ ] 配置 Redis 后 `redisStatus: connected`
- [ ] ES 未配置时 `esStatus: not_configured`（非 500）
- [ ] 响应符合 `HealthResponse` schema

## 8. 已知缺口 / 待迭代

- 无独立 `/metrics` 细分（已由 F12 `GET /metrics` 提供 Prometheus 文本）
- 无组件延迟分位数
- Worker 进程健康未纳入（仅 API）
