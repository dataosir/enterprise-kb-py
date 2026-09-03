# 企业知识库文档中心

> 本目录是项目的**唯一文档入口**。  
> **全库文件清单**见 [`INDEX.md`](INDEX.md)（增删改 `docs/` 内任意 `.md` 时须同步维护）。

---

## 分层一览

| 层 | 路径 | 职责 |
|---|---|---|
| 清单 | [`INDEX.md`](INDEX.md) | 权威文件表（一行一文） |
| 产品 | [`prd/`](prd/README.md) | 功能需求、验收标准、迭代契约（F01–F14） |
| 学习 | [`guides/`](guides/README.md) | RAG 概念、代码导读、动手实验 |
| 技术 | [`tech/`](tech/README.md) | 架构、数据流、技术选型 |
| 企业 | [`enterprise/`](enterprise/README.md) | 演进方案、中间件部署、RAG 评测 |

仓库根仅保留 [`README.md`](../README.md)（快速开始与 API 概览）；其余 Markdown 文档均在 `docs/` 下，深入阅读请从本目录进入。

---

## 推荐阅读路径

### 新手（跑通 Demo）

1. 根目录 [`README.md`](../README.md) — 一键启动
2. [`guides/LEARNING.md`](guides/LEARNING.md) — RAG 全流程与核心代码
3. [`tech/ARCHITECTURE.md`](tech/ARCHITECTURE.md) — 分层架构

### 进阶（企业能力）

1. [`prd/00-product-overview.md`](prd/00-product-overview.md) — 产品定位与功能全景
2. [`enterprise/ENTERPRISE_PLAN.md`](enterprise/ENTERPRISE_PLAN.md) — Phase 2–6 演进路线
3. [`enterprise/MIDDLEWARE_SETUP.md`](enterprise/MIDDLEWARE_SETUP.md) — Redis / ES / PG / MinIO 部署
4. [`enterprise/RAG_EVALUATION.md`](enterprise/RAG_EVALUATION.md) — 切分量化与 RAGAS 指标

### 迭代开发（按功能号）

1. [`prd/README.md`](prd/README.md) — F01–F14 功能索引
2. [`prd/05-roadmap-backlog.md`](prd/05-roadmap-backlog.md) — 未完成项与优先级

---

## 安全说明

- **凭据只写在本地 `.env`**，勿提交 Git（已在 `.gitignore` 中排除）
- 文档与 `.env.example` 仅使用占位符；生产环境请自行设置强密码
- 中间件默认仅内网可达，外网暴露须加 VPN 或反向代理 + 认证
