# 文档总索引（权威清单）

> **增删改 `docs/` 内任意 `.md` 时，必须同步更新本文件。**  
> 入口与阅读路径见 [`README.md`](README.md)。

---

## 根（`docs/`）

| 文件 | 职责 |
|---|---|
| [`README.md`](README.md) | 文档中心入口 + 分层说明 + 阅读路径 |
| [`INDEX.md`](INDEX.md) | **本文件**：全库文件清单权威源 |

---

## 学习层 `guides/`

| 文件 | 职责 |
|---|---|
| [`guides/README.md`](guides/README.md) | 学习层导读 |
| [`guides/LEARNING.md`](guides/LEARNING.md) | RAG 心智模型、核心代码精读、Step 0–5 实验路线 |

---

## 技术层 `tech/`

| 文件 | 职责 |
|---|---|
| [`tech/README.md`](tech/README.md) | 技术层导读 |
| [`tech/ARCHITECTURE.md`](tech/ARCHITECTURE.md) | 系统架构、数据流、目录结构、技术选型 |
| [`tech/MIDDLEWARE.md`](tech/MIDDLEWARE.md) | **中间件专题**：AI vs 传统分类、职责、等价物、优缺点、Profile 选型 |
| 中间件思维导图 | `http://127.0.0.1:8081/middleware-map.html` — SVG 交互图 + `/api/middleware/map` |
| [`tech/BACKLOG.md`](tech/BACKLOG.md) | **缺口专题**：未实现项矩阵、Sprint 顺序、验收命令 |
| [`tech/EVALUATION.md`](tech/EVALUATION.md) | L1–L4 评测专题：切分/benchmark/RAGAS/基线/可观测/反馈回流 |

---

## 企业层 `enterprise/`

| 文件 | 职责 |
|---|---|
| [`enterprise/README.md`](enterprise/README.md) | 企业层导读 |
| [`enterprise/ENTERPRISE_PLAN.md`](enterprise/ENTERPRISE_PLAN.md) | 企业级演进总方案（Phase 2–6） |
| [`enterprise/MIDDLEWARE_SETUP.md`](enterprise/MIDDLEWARE_SETUP.md) | 中间件 Docker 部署与运维 |
| [`enterprise/RAG_EVALUATION.md`](enterprise/RAG_EVALUATION.md) | 评测金字塔、指标定义、面试 Q&A（专题入口） |

---

## 产品层 `prd/`

| 文件 | 职责 | 关联 |
|---|---|---|
| [`prd/README.md`](prd/README.md) | PRD 层导读与 F01–F14 功能索引 | — |
| [`prd/00-product-overview.md`](prd/00-product-overview.md) | 定位 / 非目标 / 用户场景 | — |
| [`prd/01-domain-model.md`](prd/01-domain-model.md) | 文档、Chunk、会话、RAG 参数等领域对象 | — |
| [`prd/02-user-workflow.md`](prd/02-user-workflow.md) | 用户主流程与 API 映射 | — |
| [`prd/03-features/F01-document-ingest.md`](prd/03-features/F01-document-ingest.md) | 文档入库（切分/向量化/双写） | F01 |
| [`prd/03-features/F02-document-management.md`](prd/03-features/F02-document-management.md) | 文档列表 / 删除 / 状态 | F02 |
| [`prd/03-features/F03-rag-qa.md`](prd/03-features/F03-rag-qa.md) | RAG 问答 / 流式 / 引用 | F03 |
| [`prd/03-features/F04-retrieval-settings.md`](prd/03-features/F04-retrieval-settings.md) | 12 项运行时 RAG 调参 | F04 |
| [`prd/03-features/F05-hybrid-retrieval.md`](prd/03-features/F05-hybrid-retrieval.md) | BM25 + 向量混合检索 | F05 |
| [`prd/03-features/F06-conversation-session.md`](prd/03-features/F06-conversation-session.md) | 多轮会话 Redis 持久化 | F06 |
| [`prd/03-features/F07-async-ingest.md`](prd/03-features/F07-async-ingest.md) | 大文件异步入库 | F07 |
| [`prd/03-features/F08-vector-storage.md`](prd/03-features/F08-vector-storage.md) | Chroma / pgvector 切换 | F08 |
| [`prd/03-features/F09-object-storage.md`](prd/03-features/F09-object-storage.md) | 本地 / MinIO 对象存储 | F09 |
| [`prd/03-features/F10-web-ui.md`](prd/03-features/F10-web-ui.md) | Web 聊天 / 上传 / 调参面板 | F10 |
| [`prd/03-features/F11-deployment.md`](prd/03-features/F11-deployment.md) | 一键启动 / Docker / 打包 | F11 |
| [`prd/03-features/F12-evaluation.md`](prd/03-features/F12-evaluation.md) | 切分分析 + 检索 benchmark（含 hybrid） | F12 |
| [`prd/03-features/F13-health-status.md`](prd/03-features/F13-health-status.md) | 健康检查与中间件状态 | F13 |
| [`prd/03-features/F14-auth-multitenant.md`](prd/03-features/F14-auth-multitenant.md) | 认证与多租户（规划） | F14 |
| [`prd/04-nfr-constraints.md`](prd/04-nfr-constraints.md) | 非功能硬约束 | NFR |
| [`prd/05-roadmap-backlog.md`](prd/05-roadmap-backlog.md) | 迭代 backlog | backlog |

---

## 仓库根（非 `docs/`）

> **约定**：根目录仅保留 [`../README.md`](../README.md) 一份 Markdown；其余文档一律放在 `docs/` 下。  
> `sample-docs/` 为知识库示例内容，不属于项目文档。

| 文件 | 职责 |
|---|---|
| [`../README.md`](../README.md) | 项目简介、快速开始、API 表（**根目录唯一 .md**） |
| [`../.env.example`](../.env.example) | 环境变量模板（含中间件占位凭据） |
