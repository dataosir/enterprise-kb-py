# 00 · 产品概览

## 1. 产品定位

**enterprise-kb-py** 是一个**本地可运行的企业知识库 RAG Demo**，面向学习与企业方案验证，不是开箱即用的多租户 SaaS。

核心价值：用约 300 行核心 RAG 代码 + 可切换中间件后端，跑通「文档入库 → 检索 → 问答 → 调参 → 评测」全链路，并与 Java 版 `enterprise-kb` 概念对齐，便于迁移。

> 一句话：让开发者在本地**看得见、摸得着、调得动**企业级知识库 RAG。

## 2. 目标用户与场景

| 角色 | 场景 |
|---|---|
| RAG 学习者 | 理解切分、向量检索、Prompt 约束与引用来源 |
| 方案验证者 | 在 NAS / 内网搭中间件，对比 Chroma vs pgvector、纯向量 vs 混合检索 |
| 开源贡献者 | 按 Fxx 功能号独立提 PR，不破坏 Demo 零依赖模式 |
| Java 迁移者 | 验证 Python 侧检索策略后，迁回 Spring AI 企业版 |

## 3. 核心价值主张

1. **零中间件可跑**：默认 Chroma + SQLite + 本地文件，一条 `start.sh` 启动。
2. **渐进企业化**：Redis / ES / PG / MinIO 按需启用，未配置自动回退 Demo 模式。
3. **参数可调试**：页面 12 项 RAG 旋钮 + 检索预览，改完即看效果。
4. **可评测**：离线 benchmark 对比 chunk/topK，不消耗 LLM 费用。

## 4. 非目标（明确不做）

| 不做 | 原因 |
|---|---|
| 托管多租户 SaaS | 定位是开源 Demo + 内网部署参考 |
| 替代 Java 版全部能力 | Python 版侧重实验与验证 |
| 保证回答 100% 正确 | RAG 依赖文档质量与检索参数 |
| 默认开启高内存模型 | 6GB 设备友好；Rerank 默认关闭 |
| 文档中写真实凭据 | 开源安全；仅用占位符 |

## 5. 成功度量（产品层）

| 指标 | 说明 | 当前参照 |
|---|---|---|
| Demo 启动成功率 | 无中间件 `make dev` 可问答 | ✅ |
| 示例文档 Hit@K | benchmark 40 题（含 hard 混淆集） | ✅ sample-docs 6 篇 |
| 混合检索可用 | ES 配置后 hybrid 模式可预览 | ✅ Phase 2b |
| 会话重启不丢 | Redis 配置后会话持久化 | ✅ Phase 3 |
| 企业 Demo 验收 | 见 F05 / F12 / enterprise 方案 | 部分达成 |

## 6. 系统边界图（逻辑）

```
上传/示例文档(F01) → 文档管理(F02) → 向量库(F08) + 对象存储(F09)
                              ↓
用户提问(F03) ← 检索调参(F04) ← 混合检索(F05，可选 ES)
        ↓
会话(F06) · 异步入库(F07) · Web UI(F10)
        ↓
健康状态(F13) · 评测(F12) · 部署(F11)
认证多租户(F14) — 规划中
```

## 7. 相关文档

- 总目录：[`README.md`](README.md)
- 领域模型：[`01-domain-model.md`](01-domain-model.md)
- 用户流程：[`02-user-workflow.md`](02-user-workflow.md)
- 技术架构：[`../tech/ARCHITECTURE.md`](../tech/ARCHITECTURE.md)
- 企业演进：[`../enterprise/ENTERPRISE_PLAN.md`](../enterprise/ENTERPRISE_PLAN.md)
