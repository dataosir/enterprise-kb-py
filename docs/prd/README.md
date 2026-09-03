# 企业知识库 PRD 总目录

> 本文档体系由当前代码与 `docs/` **反向抽取**而成，用于按功能号独立迭代。  
> 文档总入口：[`../README.md`](../README.md)；全库清单：[`../INDEX.md`](../INDEX.md)。

**产品**：`enterprise-kb-py` — 本地可运行的企业知识库 RAG Demo / 开源学习工程  
**非目标**：自动下单、多租户 SaaS 生产托管、替代 Java 版 `enterprise-kb` 的全部企业能力

---

## 阅读顺序

1. [`00-product-overview.md`](00-product-overview.md) — 定位、用户、非目标
2. [`01-domain-model.md`](01-domain-model.md) — 核心概念与状态对象
3. [`02-user-workflow.md`](02-user-workflow.md) — 用户主流程与 API 映射
4. [`03-features/`](03-features/) — 功能拆解（F01–F14，可独立开 PR）
5. [`04-nfr-constraints.md`](04-nfr-constraints.md) — 非功能与硬约束
6. [`05-roadmap-backlog.md`](05-roadmap-backlog.md) — 迭代 backlog（链到企业方案 Phase 5–6）

---

## 功能索引（F01–F14）

| 编号 | 文档 | 一层摘要 | 主 API / 入口 | 状态 |
|---|---|---|---|---|
| F01 | [文档入库](03-features/F01-document-ingest.md) | 上传/切分/向量化/双写 | `POST /api/documents/upload` | ✅ |
| F02 | [文档管理](03-features/F02-document-management.md) | 列表/删除/示例引导 | `GET/DELETE /api/documents` | ✅ |
| F03 | [RAG 问答](03-features/F03-rag-qa.md) | 检索+生成+引用+流式 | `POST /api/chat` | ✅ |
| F04 | [检索与生成调参](03-features/F04-retrieval-settings.md) | 12 项运行时参数 | `PUT /api/settings/rag` | ✅ |
| F05 | [混合检索](03-features/F05-hybrid-retrieval.md) | BM25 + 向量 RRF 融合 | `retrievalMode=hybrid` | ✅ |
| F06 | [会话持久化](03-features/F06-conversation-session.md) | 多轮对话 Redis 存储 | `GET /api/conversations/{id}` | ✅ |
| F07 | [异步入库](03-features/F07-async-ingest.md) | 大文件后台处理 | `GET /api/jobs/{id}` | ✅ |
| F08 | [向量库切换](03-features/F08-vector-storage.md) | Chroma / pgvector | `VECTOR_STORE` | ✅ |
| F09 | [对象存储](03-features/F09-object-storage.md) | 本地 / MinIO S3 | `STORAGE_BACKEND` | ✅ |
| F10 | [Web UI](03-features/F10-web-ui.md) | 聊天/上传/调参面板 | `static/index.html` | ✅ |
| F11 | [部署与打包](03-features/F11-deployment.md) | 一键启动/Docker/分发 | `start.sh` / `make` | ✅ |
| F12 | [RAG 评测体系](03-features/F12-evaluation.md) | L1–L4 分层指标 + 基线 CI + 反馈回流 | `make eval-smoke` | ✅ |
| F13 | [健康与状态](03-features/F13-health-status.md) | 中间件/索引状态聚合 | `GET /api/health` | ✅ |
| F14 | [认证与多租户](03-features/F14-auth-multitenant.md) | JWT / 租户隔离 | — | 📋 规划 |

**迭代约定**：改某能力时，PR / 提交说明注明功能号（如「改 F05」），并同步对应 PRD 的「已知缺口」与验收标准。

---

## 命名约定

| 类型 | 模式 | 示例 |
|---|---|---|
| 总览章 | `NN-主题.md` | `00-product-overview.md` |
| 功能章 | `Fxx-能力短名.md` | `F03-rag-qa.md` |
| 语言 | 中文正文 | 与现有 `docs/` 一致 |

每份功能文档固定八段：背景与目标 → 用户故事 → In/Out → 主流程与边界 → 关键配置键 → 代码锚点 → 验收标准 → 已知缺口。

---

## 与文档体系的关系

| 文档 | 角色 |
|---|---|
| 本目录 `docs/prd/` | **需求与功能边界**（迭代契约） |
| [`../guides/`](../guides/README.md) | 怎么学：概念、实验、代码导读 |
| [`../tech/`](../tech/README.md) | 怎么做：架构、数据流、选型 |
| [`../enterprise/`](../enterprise/README.md) | 企业演进、中间件、评测规划 |
| 根目录 `README.md` | 用户向快速开始与 API 速查 |

技术方案细节见 [`../enterprise/ENTERPRISE_PLAN.md`](../enterprise/ENTERPRISE_PLAN.md)，PRD 只描述**做什么、验收什么**，不重复实现细节。

---

## 维护规则

1. **先改 PRD 再改行为**（或同 PR 内同步）：API / 参数 / 用户可见行为变更须更新对应 Fxx。
2. **验收可对 curl / UI**：每条验收尽量可命令或页面验证。
3. **凭据不进 PRD**：连接串、密码只引用 `.env.example` 占位符。
4. **增删 PRD 文件须同步** [`../INDEX.md`](../INDEX.md)。
