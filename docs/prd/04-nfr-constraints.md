# 04 · 非功能约束（NFR）

## 1. 部署与资源

| 约束 | 说明 |
|---|---|
| 最低 Demo | 2GB RAM，可跑 Chroma + BGE-small |
| 推荐企业 NAS | 6GB RAM；ES 256MB 堆；Rerank 默认关 |
| 磁盘 | BGE ~100MB；每 1000 chunk 约数十 MB 向量 |
| Python | 3.10+ |
| 网络 | 首次需下载模型；LLM 需 API 或本地 Ollama |

## 2. 安全

| 约束 | 说明 |
|---|---|
| 凭据 | 仅 `.env` 本地配置，禁止写入 PRD/文档/Git |
| 文档占位 | `.env.example` 使用 `YOUR_HOST`、`<YOUR_PASSWORD>` |
| 默认无鉴权 | 内网部署须自行加反向代理或等待 F14 |
| 上传限制 | `MAX_UPLOAD_SIZE_MB` 默认 20 |
| CORS | 默认同源静态站 |

## 3. 可用性

| 约束 | 说明 |
|---|---|
| 中间件降级 | Redis/ES/PG/S3 不可用时回退 Demo 能力，不阻止启动 |
| 异步入库 | 依赖 Worker 进程；未启动则大文件卡住 PROCESSING |
| 数据持久化 | `data/` 目录；`make reset` 清空所有运行时数据 |

## 4. 可维护性

| 约束 | 说明 |
|---|---|
| 文档结构 | 根目录仅 `README.md`；其余在 `docs/` 分层 |
| PRD 同步 | 改 Fxx 行为须更新对应 PRD + `INDEX.md` |
| 功能号 | PR 注明 Fxx 便于追溯 |
| 开源 | 无个人 IP、SSH 账号、真实密码进入仓库 |

## 5. 性能（目标非保证）

| 场景 | 目标 |
|---|---|
| 小文档同步入库 | < 10s（含 embedding） |
| 问答延迟 | 取决于 LLM；检索 < 1s（本地 Chroma） |
| 混合检索 | ES 延迟 + 向量；6GB 设备可接受 |
| Benchmark | 全网格 < 5min（sample-docs） |

## 6. 兼容性

| 项 | 说明 |
|---|---|
| Java 版对齐 | 概念一致（混合检索、Redis 会话、pgvector） |
| API 版本 | 当前无 `/v1` 前缀；企业化时须规划迁移 |
| 浏览器 | 现代 Chromium / Firefox / Safari |

## 7. 相关文档

- 中间件资源：[`../enterprise/MIDDLEWARE_SETUP.md`](../enterprise/MIDDLEWARE_SETUP.md)
- 评测指标：[`../enterprise/RAG_EVALUATION.md`](../enterprise/RAG_EVALUATION.md)
